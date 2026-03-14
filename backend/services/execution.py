from __future__ import annotations

from backend.db import db
from backend.operators.registry import registry
from backend.operators import critic, experimenter, planner_agent, repo_tools, researcher, reviser, synthesizer  # noqa: F401
from backend.services.artifacts import artifact_service
from backend.services.experiments import experiment_service
from backend.services.project_state import project_state_service
from backend.services.tasks import task_service
from backend.utils import dumps, loads, new_id, now_ts

# Canonical runtime imports (Step 5 — mirror runs into canonical registry)
from research_engine.core.runtime.run_registry import RunRegistry, RunStatus
from research_engine.core.runtime.artifact_validator import ArtifactValidator
from research_engine.core.runtime.postcondition_verifier import PostconditionVerifier

_canonical_registry = RunRegistry()
_canonical_validator = ArtifactValidator()
_canonical_verifier = PostconditionVerifier()


class ExecutionService:
    def create_node(
        self,
        project_id: str,
        task_id: str,
        operator: str,
        dependency_node_ids: list[str] | None = None,
        input_artifact_ids: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        node_id = new_id()
        ts = now_ts()
        metadata = metadata or {}
        dependency_node_ids = dependency_node_ids or []
        input_artifact_ids = input_artifact_ids or []
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO execution_nodes (id, project_id, task_id, operator, status, retries, is_stale, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (node_id, project_id, task_id, operator, 'pending', 0, 0, dumps(metadata), ts, ts),
            )
            for dep in dependency_node_ids:
                conn.execute('INSERT OR IGNORE INTO execution_deps (node_id, depends_on_node_id) VALUES (?, ?)', (node_id, dep))
            for artifact_id in input_artifact_ids:
                conn.execute('INSERT OR IGNORE INTO execution_inputs (node_id, artifact_id) VALUES (?, ?)', (node_id, artifact_id))
        return self.get_node(node_id)

    def get_node(self, node_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM execution_nodes WHERE id = ?', (node_id,)).fetchone()
        if not row:
            return None
        node = dict(row)
        node['metadata'] = loads(node.pop('metadata_json'), {})
        node['dependencies'] = [r['depends_on_node_id'] for r in db.conn.execute('SELECT depends_on_node_id FROM execution_deps WHERE node_id = ?', (node_id,)).fetchall()]
        node['inputs'] = [r['artifact_id'] for r in db.conn.execute('SELECT artifact_id FROM execution_inputs WHERE node_id = ?', (node_id,)).fetchall()]
        node['outputs'] = [r['artifact_id'] for r in db.conn.execute('SELECT artifact_id FROM execution_outputs WHERE node_id = ?', (node_id,)).fetchall()]
        return node

    def list_nodes(self, project_id: str, status: str | None = None) -> list[dict]:
        if status:
            rows = db.conn.execute('SELECT id FROM execution_nodes WHERE project_id = ? AND status = ? ORDER BY created_at', (project_id, status)).fetchall()
        else:
            rows = db.conn.execute('SELECT id FROM execution_nodes WHERE project_id = ? ORDER BY created_at', (project_id,)).fetchall()
        return [self.get_node(row['id']) for row in rows]

    def _dependencies_done(self, node: dict) -> bool:
        for dep_id in node['dependencies']:
            dep = self.get_node(dep_id)
            if not dep or dep['status'] != 'done':
                return False
        return True

    def _collect_resolved_input_ids(self, node: dict) -> list[str]:
        resolved = list(node['inputs'])
        for dep_id in node['dependencies']:
            for row in db.conn.execute('SELECT artifact_id FROM execution_outputs WHERE node_id = ?', (dep_id,)).fetchall():
                if row['artifact_id'] not in resolved:
                    resolved.append(row['artifact_id'])
        return resolved

    def next_ready_node(self, project_id: str) -> dict | None:
        rows = db.conn.execute(
            'SELECT id FROM execution_nodes WHERE project_id = ? AND status = ? ORDER BY is_stale DESC, created_at',
            (project_id, 'pending'),
        ).fetchall()
        for row in rows:
            node = self.get_node(row['id'])
            if node and self._dependencies_done(node):
                return node
        return None

    def run_once(self, project_id: str) -> dict | None:
        node = self.next_ready_node(project_id)
        if not node:
            return None
        operator = registry.get(node['operator'])
        if not operator:
            self._mark_status(node['id'], 'failed')
            task_service.update_status(node['task_id'], 'failed')
            return {'error': f'unknown operator: {node["operator"]}', 'node': node}

        # ── canonical run start ──────────────────────────────────────
        canonical_run = _canonical_registry.create_run(
            operator_name=node['operator'],
            inputs={'node_id': node['id'], 'project_id': project_id},
            metadata={'task_id': node['task_id']},
        )
        _canonical_registry.mark_running(canonical_run.run_id)

        self._mark_status(node['id'], 'running')
        task_service.update_status(node['task_id'], 'running')
        context = self._build_context(node)
        result = operator(context)
        artifact = artifact_service.create(
            project_id=project_id,
            artifact_type=result['type'],
            title=result['title'],
            data=result['data'],
            confidence=result.get('confidence', 0.5),
            source_task_id=node['task_id'],
            source_node_id=node['id'],
            parent_artifact_ids=context['resolved_input_ids'],
            revision_of_artifact_id=result.get('revision_of_artifact_id'),
            revision_note=result.get('revision_note'),
        )

        # ── canonical artifact validation ────────────────────────────
        validation = _canonical_validator.validate(
            artifact['id'], artifact['type'], artifact['data'],
        )
        # ── canonical postcondition verification ─────────────────────
        pc_report = _canonical_verifier.verify(
            node['operator'],
            {'node_id': node['id']},
            {'artifacts': [{'id': artifact['id'], 'type': artifact['type'], 'data': artifact['data']}]},
        )
        # ── canonical run finish ─────────────────────────────────────
        if validation.valid and pc_report.all_passed:
            _canonical_registry.mark_success(
                canonical_run.run_id,
                postcondition_report=pc_report.to_dict(),
            )
        else:
            status = RunStatus.ARTIFACT_INVALID if not validation.valid else RunStatus.VERIFIED_FAILURE
            _canonical_registry.mark_failure(
                canonical_run.run_id, status,
                error_message="; ".join(validation.errors) if validation.errors else "postcondition failed",
                postcondition_report=pc_report.to_dict(),
            )

        with db.transaction() as conn:
            conn.execute('INSERT OR IGNORE INTO execution_outputs (node_id, artifact_id) VALUES (?, ?)', (node['id'], artifact['id']))
        self._post_artifact_hooks(node, artifact, context)
        self._mark_status(node['id'], 'done')
        task_service.update_status(node['task_id'], 'done')
        db.conn.execute(
            'INSERT INTO runs (id, project_id, node_id, operator, status, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (new_id(), project_id, node['id'], node['operator'], 'done', dumps({'artifact_id': artifact['id']}), now_ts()),
        )
        db.conn.commit()
        return {'node': self.get_node(node['id']), 'artifact': artifact}

    def run_until_idle(self, project_id: str, max_steps: int) -> dict:
        results = []
        for _ in range(max_steps):
            step = self.run_once(project_id)
            if not step:
                break
            results.append(step)
        return {'steps': len(results), 'results': results, 'summary': project_state_service.summarize(project_id)}

    def _build_context(self, node: dict) -> dict:
        task = task_service.get(node['task_id'])
        project = project_state_service.get_project(node['project_id'])
        resolved_input_ids = self._collect_resolved_input_ids(node)
        inputs = [artifact_service.get(artifact_id) for artifact_id in resolved_input_ids]
        return {
            'project_id': node['project_id'],
            'project': project,
            'task': task,
            'node': node,
            'inputs': inputs,
            'resolved_input_ids': resolved_input_ids,
            **node['metadata'],
        }

    def _mark_status(self, node_id: str, status: str) -> None:
        db.conn.execute('UPDATE execution_nodes SET status = ?, updated_at = ? WHERE id = ?', (status, now_ts(), node_id))
        db.conn.commit()

    def _post_artifact_hooks(self, node: dict, artifact: dict, context: dict) -> None:
        from backend.services.conflict_resolution import conflict_resolution_service

        project_id = node['project_id']
        if artifact['type'] == 'experiment_plan':
            self._enqueue_experiment_execution(project_id, node, artifact)
        elif artifact['type'] == 'experiment_result':
            experiment_service.update_beliefs_from_result(project_id, artifact)
        elif artifact['type'] == 'patch_test_result':
            self._enqueue_patch_evaluation(project_id, node, artifact)
        elif artifact['type'] == 'task_list':
            self._materialize_task_list(project_id, node, artifact)
        elif artifact['type'] == 'code_patch':
            self._enqueue_patch_test(project_id, node, artifact, context)

        # Auto-conflict-resolution for claim-bearing artifacts
        if artifact['type'] in {'claims', 'architecture', 'hypothesis', 'requirements'}:
            pairs = conflict_resolution_service.detect_conflicts(project_id, artifact)
            if pairs:
                conflict_resolution_service.resolve(project_id, pairs)


    def _enqueue_experiment_execution(self, project_id: str, plan_node: dict, plan_artifact: dict) -> None:
        run_task = task_service.create(
            project_id,
            title=f'Run experiment for: {plan_artifact["data"].get("statement", plan_artifact["title"])}',
            kind='experiment_run',
            priority=4,
            rationale='generated from experiment plan',
            metadata={'plan_artifact_id': plan_artifact['id']},
        )
        run_node = self.create_node(
            project_id,
            run_task['id'],
            'experiment_runner',
            dependency_node_ids=[plan_node['id']],
            input_artifact_ids=[plan_artifact['id']],
        )
        eval_task = task_service.create(
            project_id,
            title='Evaluate experiment result',
            kind='experiment_evaluation',
            priority=3,
            rationale='generated from experiment run',
            metadata={'plan_artifact_id': plan_artifact['id']},
        )
        self.create_node(
            project_id,
            eval_task['id'],
            'evaluator',
            dependency_node_ids=[run_node['id']],
        )

    def _materialize_task_list(self, project_id: str, source_node: dict, artifact: dict) -> None:
        existing_titles = {task['title'] for task in task_service.list(project_id)}
        latest_arch = artifact_service.latest_by_type(project_id, 'architecture')
        latest_critique = artifact_service.latest_by_type(project_id, 'critique')
        for item in artifact['data'].get('tasks', []):
            title = str(item.get('title', '')).strip()
            if not title or title in existing_titles:
                continue
            kind = str(item.get('kind', 'followup'))
            priority = int(item.get('priority', 1))
            task = task_service.create(project_id, title=title, kind=kind, priority=priority, rationale='from planner agent')
            operator = 'researcher'
            input_artifact_ids: list[str] = []
            if kind in {'synthesis', 'architecture_revision'}:
                operator = 'reviser' if latest_arch and latest_critique else 'synthesizer'
                if latest_arch:
                    input_artifact_ids.append(latest_arch['id'])
                if latest_critique:
                    input_artifact_ids.append(latest_critique['id'])
            elif kind == 'experiment_design':
                operator = 'experiment_designer'
            elif kind == 'critique':
                operator = 'critic'
            self.create_node(
                project_id,
                task['id'],
                operator,
                dependency_node_ids=[source_node['id']],
                input_artifact_ids=input_artifact_ids,
            )
            existing_titles.add(title)

    def _enqueue_patch_test(self, project_id: str, source_node: dict, patch_artifact: dict, context: dict) -> None:
        patch_task = task_service.create(
            project_id,
            title=f'Run patch test for {patch_artifact["title"]}',
            kind='patch_test',
            priority=4,
            rationale='generated from code patch artifact',
            metadata={
                'repo_url': patch_artifact['data'].get('repo_url'),
                'repo_ref': patch_artifact['data'].get('repo_ref'),
                'install_command': patch_artifact['data'].get('install_command'),
                'test_command': patch_artifact['data'].get('test_command'),
                'base_path': '/workspace/artifacts',
                'reuse_project_session': True,
            },
        )
        self.create_node(
            project_id,
            patch_task['id'],
            'patch_test_runner',
            dependency_node_ids=[source_node['id']],
            input_artifact_ids=context.get('resolved_input_ids', []) + [patch_artifact['id']],
        )

    def _enqueue_patch_evaluation(self, project_id: str, source_node: dict, result_artifact: dict) -> None:
        task = task_service.create(
            project_id,
            title='Evaluate patch test result',
            kind='patch_evaluation',
            priority=3,
            rationale='generated from patch test result',
            metadata={'result_artifact_id': result_artifact['id']},
        )
        self.create_node(
            project_id,
            task['id'],
            'evaluator',
            dependency_node_ids=[source_node['id']],
            input_artifact_ids=[result_artifact['id']],
        )


execution_service = ExecutionService()
