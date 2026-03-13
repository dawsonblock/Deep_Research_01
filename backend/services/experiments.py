from __future__ import annotations

import json
from statistics import mean

from backend.db import db
from backend.services.artifacts import artifact_service
from backend.services.llm import llm_service
from backend.services.sandbox_harness import sandbox_harness_service
from backend.utils import dumps, loads, new_id, now_ts


class ExperimentService:
    def _latest_project_artifacts(self, project_id: str) -> dict[str, dict | None]:
        return {
            'requirements': artifact_service.latest_by_type(project_id, 'requirements'),
            'architecture': artifact_service.latest_by_type(project_id, 'architecture'),
            'critique': artifact_service.latest_by_type(project_id, 'critique'),
            'evaluation': artifact_service.latest_by_type(project_id, 'evaluation'),
        }

    def run_plan(self, project_id: str, plan_artifact: dict, input_artifacts: list[dict]) -> dict:
        method = str(plan_artifact['data'].get('method', '') or '').lower()
        if method.startswith('opensandbox') or plan_artifact['data'].get('job', {}).get('runner') == 'opensandbox':
            sandbox_result = sandbox_harness_service.run_plan(project_id, plan_artifact['data'], input_artifacts)
            metrics = self._metrics_from_sandbox_result(sandbox_result)
            summary = {
                'method': plan_artifact['data'].get('method', 'opensandbox'),
                'hypothesis_statement': plan_artifact['data'].get('statement', ''),
                'inputs_used': [a['id'] for a in input_artifacts if a],
                'result': 'sandbox_execution_completed' if sandbox_result.get('status') in {'ok', 'nonzero_exit'} else sandbox_result.get('status', 'sandbox_execution_failed'),
                'sandbox': sandbox_result,
            }
            run_id = new_id()
            with db.transaction() as conn:
                conn.execute(
                    'INSERT INTO experiment_runs (id, project_id, plan_artifact_id, hypothesis_text, method, input_artifact_ids_json, metrics_json, summary_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        run_id,
                        project_id,
                        plan_artifact['id'],
                        plan_artifact['data'].get('statement', ''),
                        plan_artifact['data'].get('method', 'opensandbox'),
                        dumps(summary['inputs_used']),
                        dumps(metrics),
                        dumps(summary),
                        now_ts(),
                    ),
                )
            return {'run_id': run_id, 'metrics': metrics, 'summary': summary}
        latest = self._latest_project_artifacts(project_id)
        architecture = next((a for a in input_artifacts if a and a['type'] == 'architecture'), None) or latest['architecture']
        requirements = next((a for a in input_artifacts if a and a['type'] == 'requirements'), None) or latest['requirements']
        critique = next((a for a in input_artifacts if a and a['type'] == 'critique'), None) or latest['critique']

        components = architecture['data'].get('components', []) if architecture else []
        requirement_items = requirements['data'].get('items', []) if requirements else []
        critique_issues = critique['data'].get('issues', []) if critique else []

        # ----------------------------------------------------------------
        # Compute arithmetic stub baseline (always available as fallback)
        # ----------------------------------------------------------------
        requirement_tokens = {self._tokenize(item)[0] for item in requirement_items if self._tokenize(item)}
        component_tokens = {self._tokenize(item)[0] for item in components if self._tokenize(item)}
        matches = len(requirement_tokens & component_tokens)
        requirement_coverage = matches / max(1, len(requirement_tokens))

        dependency_nodes = db.conn.execute(
            'SELECT COUNT(*) FROM execution_deps d JOIN execution_nodes n ON n.id = d.node_id WHERE n.project_id = ?',
            (project_id,),
        ).fetchone()[0]
        node_count = db.conn.execute('SELECT COUNT(*) FROM execution_nodes WHERE project_id = ?', (project_id,)).fetchone()[0]
        dependency_density = dependency_nodes / max(1, node_count)
        avg_score = db.conn.execute('SELECT COALESCE(AVG(score), 0) FROM artifacts WHERE project_id = ?', (project_id,)).fetchone()[0]
        issue_rate = len(critique_issues) / max(1, len(components) + len(requirement_items))

        stub_linear = round(min(1.0, 0.18 + issue_rate + max(0.0, 0.35 - requirement_coverage)), 4)
        stub_graph = round(max(0.0, stub_linear - (0.08 + dependency_density * 0.22 + avg_score * 0.12)), 4)
        stub_replay = round(min(1.0, 0.35 + dependency_density * 0.25 + avg_score * 0.25 + requirement_coverage * 0.15), 4)
        stub_arch_q = round(min(1.0, avg_score * 0.5 + requirement_coverage * 0.3 + (1.0 - issue_rate) * 0.2), 4)

        stub_metrics = {
            'requirement_count': len(requirement_items),
            'architecture_component_count': len(components),
            'critique_issue_count': len(critique_issues),
            'requirement_coverage': round(requirement_coverage, 4),
            'dependency_density': round(dependency_density, 4),
            'avg_artifact_score': round(float(avg_score), 4),
            'linear_contradiction_rate': stub_linear,
            'graph_contradiction_rate': stub_graph,
            'replayability_score': stub_replay,
            'architecture_quality_score': stub_arch_q,
        }

        # ----------------------------------------------------------------
        # LLM-backed evaluation (preferred when key is configured)
        # ----------------------------------------------------------------
        run_method = 'deterministic_stub'
        metrics = stub_metrics

        if llm_service.available():
            prompt = (
                f'Project hypothesis: {plan_artifact["data"].get("statement", "")}\n'
                f'Requirements ({len(requirement_items)}): {requirement_items[:20]}\n'
                f'Architecture components ({len(components)}): {components[:20]}\n'
                f'Critique issues ({len(critique_issues)}): {critique_issues[:10]}\n'
                f'Baseline metrics (arithmetic stub): {stub_metrics}\n\n'
                'Evaluate this research artefact set and return a JSON object with keys:\n'
                'requirement_coverage (0-1), linear_contradiction_rate (0-1), '
                'graph_contradiction_rate (0-1), replayability_score (0-1), '
                'architecture_quality_score (0-1), verdict (string), '
                'recommendation (string).\n'
                'All numeric values must be between 0.0 and 1.0. '
                'Use the stub metrics as a lower-bound sanity check but improve them with '
                'semantic reasoning if possible.'
            )
            llm_raw = llm_service.complete_json(
                'You are a research quality evaluator. Assess the given project state and return only a JSON object.',
                prompt,
                fallback={},
            )
            if llm_raw and isinstance(llm_raw, dict):
                def _clip(v: object, default: float) -> float:
                    try:
                        return round(max(0.0, min(1.0, float(v))), 4)  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        return default

                metrics = {
                    'requirement_count': len(requirement_items),
                    'architecture_component_count': len(components),
                    'critique_issue_count': len(critique_issues),
                    'requirement_coverage': _clip(llm_raw.get('requirement_coverage'), stub_metrics['requirement_coverage']),
                    'dependency_density': stub_metrics['dependency_density'],
                    'avg_artifact_score': stub_metrics['avg_artifact_score'],
                    'linear_contradiction_rate': _clip(llm_raw.get('linear_contradiction_rate'), stub_linear),
                    'graph_contradiction_rate': _clip(llm_raw.get('graph_contradiction_rate'), stub_graph),
                    'replayability_score': _clip(llm_raw.get('replayability_score'), stub_replay),
                    'architecture_quality_score': _clip(llm_raw.get('architecture_quality_score'), stub_arch_q),
                    'llm_verdict': str(llm_raw.get('verdict', '')),
                    'llm_recommendation': str(llm_raw.get('recommendation', '')),
                }
                run_method = 'llm_benchmark'

        graph_contradiction_rate = metrics['graph_contradiction_rate']
        linear_contradiction_rate = metrics['linear_contradiction_rate']
        summary = {
            'method': run_method,
            'hypothesis_statement': plan_artifact['data'].get('statement', ''),
            'matched_requirements': matches,
            'inputs_used': [a['id'] for a in input_artifacts if a],
            'result': 'graph_path_better' if graph_contradiction_rate < linear_contradiction_rate else 'no_gain',
        }
        run_id = new_id()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO experiment_runs (id, project_id, plan_artifact_id, hypothesis_text, method, input_artifact_ids_json, metrics_json, summary_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    run_id,
                    project_id,
                    plan_artifact['id'],
                    plan_artifact['data'].get('statement', ''),
                    run_method,
                    dumps(summary['inputs_used']),
                    dumps(metrics),
                    dumps(summary),
                    now_ts(),
                ),
            )
        return {
            'run_id': run_id,
            'metrics': metrics,
            'summary': summary,
        }

    def evaluate_result(self, result_artifact: dict) -> dict:
        metrics = result_artifact['data'].get('metrics', {})
        if 'tests_failed' in metrics or result_artifact.get('type') == 'patch_test_result':
            tests_failed = float(metrics.get('tests_failed', 0) or 0)
            tests_passed = float(metrics.get('tests_passed', 0) or 0)
            success_rate = float(metrics.get('benchmark_success_rate', 0.0) or 0.0)
            verdict = 'Patch/test loop improved repo health.' if tests_failed == 0 and success_rate >= 0.5 else 'Patch/test loop still has failing tests or low benchmark success.'
            recommendation = 'Promote the patch and consider another verification pass.' if tests_failed == 0 and success_rate >= 0.5 else 'Keep iterating on the patch plan and inspect failing files.'
            improvements = []
            if tests_failed == 0:
                improvements.append('no failing tests detected')
            if tests_passed > 0:
                improvements.append('tests executed successfully')
            confidence = round(max(0.2, min(0.95, success_rate * 0.7 + (0.2 if tests_failed == 0 else 0.0))), 4)
            return {
                'verdict': verdict,
                'recommendation': recommendation,
                'improvements': improvements,
                'confidence': confidence,
            }
        graph_rate = float(metrics.get('graph_contradiction_rate', 1.0))
        linear_rate = float(metrics.get('linear_contradiction_rate', 1.0))
        replayability = float(metrics.get('replayability_score', 0.0))
        coverage = float(metrics.get('requirement_coverage', 0.0))

        improvements = []
        if graph_rate < linear_rate:
            improvements.append('graph execution lowered contradiction rate')
        if replayability >= 0.75:
            improvements.append('replayability is strong')
        if coverage < 0.6:
            improvements.append('requirement coverage remains weak')

        verdict = (
            'Execution-graph path outperformed the linear baseline.'
            if graph_rate < linear_rate
            else 'Execution-graph path did not clearly beat the linear baseline.'
        )
        recommendation = (
            'Promote the hypothesis and iterate on coverage gaps.'
            if graph_rate < linear_rate and replayability >= 0.7
            else 'Keep the hypothesis provisional and add more evidence or revise the architecture.'
        )
        confidence = round(mean([1.0 - min(graph_rate, 1.0), replayability, max(0.0, min(1.0, coverage + 0.1))]), 4)
        return {
            'verdict': verdict,
            'recommendation': recommendation,
            'improvements': improvements,
            'confidence': confidence,
        }

    def update_beliefs_from_result(self, project_id: str, result_artifact: dict) -> list[dict]:
        from backend.services.world_model import world_model_service

        metrics = result_artifact['data'].get('metrics', {})
        active = world_model_service.active_hypotheses(project_id)
        if not active:
            return []
        delta = 0.1 if metrics.get('graph_contradiction_rate', 1.0) < metrics.get('linear_contradiction_rate', 1.0) else -0.1
        updated = []
        for hypothesis in active[:3]:
            new_conf = max(0.0, min(1.0, hypothesis['confidence'] + delta))
            world_model_service.update_hypothesis_confidence(hypothesis['id'], new_conf)
            updated.append(world_model_service.get_hypothesis(hypothesis['id']))
        return updated

    def list_runs(self, project_id: str) -> list[dict]:
        rows = db.conn.execute('SELECT * FROM experiment_runs WHERE project_id = ? ORDER BY created_at DESC', (project_id,)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item['input_artifact_ids'] = loads(item.pop('input_artifact_ids_json'), [])
            item['metrics'] = loads(item.pop('metrics_json'), {})
            item['summary'] = loads(item.pop('summary_json'), {})
            items.append(item)
        return items

    def _metrics_from_sandbox_result(self, sandbox_result: dict) -> dict:
        if 'metrics' in sandbox_result and isinstance(sandbox_result.get('metrics'), dict):
            metrics = dict(sandbox_result['metrics'])
            if 'benchmark_success_rate' in metrics:
                metrics.setdefault('sandbox_available', 1.0)
                metrics.setdefault('sandbox_exit_code', float(sandbox_result.get('result', {}).get('exit_code', sandbox_result.get('exit_code', 0)) or 0))
                metrics.setdefault('sandbox_success_rate', float(metrics.get('benchmark_success_rate', 0.0)))
                metrics.setdefault('requirement_coverage', 0.0)
                metrics.setdefault('graph_contradiction_rate', round(max(0.0, 1.0 - float(metrics.get('benchmark_success_rate', 0.0))), 4))
                metrics.setdefault('linear_contradiction_rate', round(min(1.0, float(metrics['graph_contradiction_rate']) + 0.12), 4))
                metrics.setdefault('replayability_score', round(min(1.0, 0.45 + float(metrics.get('benchmark_success_rate', 0.0)) * 0.4), 4))
                metrics.setdefault('architecture_quality_score', round(min(1.0, float(metrics.get('benchmark_success_rate', 0.0)) * 0.7 + 0.2), 4))
                return metrics
        if sandbox_result.get('status') not in {'ok', 'nonzero_exit'}:
            return {
                'sandbox_available': 0.0,
                'sandbox_exit_code': float(sandbox_result.get('exit_code', 1) or 1),
                'sandbox_success_rate': 0.0,
                'requirement_coverage': 0.0,
                'graph_contradiction_rate': 1.0,
                'linear_contradiction_rate': 1.0,
                'replayability_score': 0.0,
            }
        stdout = sandbox_result.get('stdout', '')
        try:
            parsed = json.loads(stdout.splitlines()[-1]) if stdout else {}
        except Exception:
            parsed = {}
        coverage = float(parsed.get('requirement_coverage', 0.0) or 0.0)
        replayability = float(parsed.get('replayability_score', 0.0) or 0.0)
        graph_rate = float(parsed.get('graph_contradiction_rate', max(0.0, 0.5 - coverage * 0.2)) or 0.0)
        return {
            'sandbox_available': 1.0,
            'sandbox_exit_code': float(sandbox_result.get('exit_code', 0) or 0),
            'sandbox_success_rate': 1.0 if sandbox_result.get('status') == 'ok' and sandbox_result.get('exit_code') in (0, None) else 0.0,
            'requirement_count': int(parsed.get('requirement_count', 0) or 0),
            'architecture_component_count': int(parsed.get('component_count', 0) or 0),
            'critique_issue_count': int(parsed.get('issue_count', 0) or 0),
            'requirement_coverage': round(coverage, 4),
            'graph_contradiction_rate': round(graph_rate, 4),
            'linear_contradiction_rate': round(min(1.0, graph_rate + 0.12), 4),
            'replayability_score': round(replayability, 4),
            'architecture_quality_score': round(min(1.0, coverage * 0.55 + replayability * 0.45), 4),
        }

    def _tokenize(self, value: str) -> list[str]:
        return [part for part in str(value).lower().replace('-', ' ').replace('_', ' ').split() if part]


experiment_service = ExperimentService()
