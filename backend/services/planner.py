from __future__ import annotations

from backend.services.artifacts import artifact_service
from backend.services.execution import execution_service
from backend.services.repo_profiles import repo_profile_service
from backend.services.tasks import task_service
from backend.services.world_model import world_model_service


class PlannerService:
    def replan(self, project_id: str) -> dict:
        created_tasks = []
        created_nodes = []
        seen_titles = {task['title'] for task in task_service.list(project_id)}

        for claim in world_model_service.low_confidence_claims(project_id):
            title = f'Increase evidence for claim: {claim["content"]}'
            if title in seen_titles:
                continue
            task = task_service.create(
                project_id,
                title=title,
                kind='research',
                priority=3,
                rationale='low-confidence claim detected',
                metadata={'claim_id': claim['id']},
            )
            node = execution_service.create_node(
                project_id,
                task['id'],
                'researcher',
                input_artifact_ids=[claim['artifact_id']] if claim.get('artifact_id') else [],
                metadata={'query': claim['content']},
            )
            created_tasks.append(task)
            created_nodes.append(node)
            seen_titles.add(title)

        for question in world_model_service.open_questions(project_id)[:5]:
            title = question['content']
            if title in seen_titles:
                continue
            task = task_service.create(
                project_id,
                title=title,
                kind='question_resolution',
                priority=question['priority'],
                rationale='open question detected',
                metadata={'question_id': question['id']},
            )
            node = execution_service.create_node(
                project_id,
                task['id'],
                'researcher',
                input_artifact_ids=[question['artifact_id']] if question.get('artifact_id') else [],
                metadata={'query': question['content']},
            )
            created_tasks.append(task)
            created_nodes.append(node)
            seen_titles.add(title)


        if not world_model_service.active_hypotheses(project_id):
            latest_architecture = artifact_service.latest_by_type(project_id, 'architecture')
            latest_critique = artifact_service.latest_by_type(project_id, 'critique')
            title = 'Form execution hypothesis'
            if latest_architecture and title not in seen_titles:
                task = task_service.create(
                    project_id,
                    title=title,
                    kind='hypothesis',
                    priority=4,
                    rationale='no active hypothesis exists yet',
                    metadata={'artifact_id': latest_architecture['id']},
                )
                inputs = [latest_architecture['id']]
                if latest_critique:
                    inputs.append(latest_critique['id'])
                node = execution_service.create_node(
                    project_id,
                    task['id'],
                    'hypothesis_maker',
                    input_artifact_ids=inputs,
                )
                created_tasks.append(task)
                created_nodes.append(node)
                seen_titles.add(title)

        for hypothesis in world_model_service.active_hypotheses(project_id):
            if 0.3 <= hypothesis['confidence'] <= 0.8:
                title = f'Design experiment for hypothesis: {hypothesis["statement"]}'
                if title in seen_titles:
                    continue
                task = task_service.create(
                    project_id,
                    title=title,
                    kind='experiment_design',
                    priority=4,
                    rationale='mid-confidence hypothesis should be tested',
                    metadata={'hypothesis_id': hypothesis['id']},
                )
                node = execution_service.create_node(
                    project_id,
                    task['id'],
                    'experiment_designer',
                    input_artifact_ids=[hypothesis['artifact_id']] if hypothesis.get('artifact_id') else [],
                    metadata={'hypothesis_statement': hypothesis['statement'], 'prediction': hypothesis['prediction']},
                )
                created_tasks.append(task)
                created_nodes.append(node)
                seen_titles.add(title)


        latest_architecture = artifact_service.latest_by_type(project_id, 'architecture')
        latest_critique = artifact_service.latest_by_type(project_id, 'critique')
        latest_repo_inspection = artifact_service.latest_by_type(project_id, 'repo_inspection')
        latest_repo_profile = artifact_service.latest_by_type(project_id, 'repo_profile')
        latest_patch = artifact_service.latest_by_type(project_id, 'code_patch')
        latest_patch_result = artifact_service.latest_by_type(project_id, 'patch_test_result')
        latest_experiment_result = artifact_service.latest_by_type(project_id, 'experiment_result')

        repo_url = None
        repo_ref = None
        install_command = None
        test_command = None
        for task in task_service.list(project_id):
            metadata = dict(task.get('metadata') or {})
            if metadata.get('repo_url'):
                repo_url = repo_url or metadata.get('repo_url')
                repo_ref = repo_ref or metadata.get('repo_ref')
                install_command = install_command or metadata.get('install_command')
                test_command = test_command or metadata.get('test_command')

        if repo_url and not latest_repo_inspection:
            title = 'Inspect repository files'
            if title not in seen_titles:
                task = task_service.create(
                    project_id,
                    title=title,
                    kind='repo_inspection',
                    priority=5,
                    rationale='repo-aware execution should inspect real repository files before profile inference',
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref},
                )
                node = execution_service.create_node(
                    project_id,
                    task['id'],
                    'repo_inspector',
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref},
                )
                created_tasks.append(task)
                created_nodes.append(node)
                seen_titles.add(title)

        if repo_url and not latest_repo_profile:
            title = 'Infer repository execution profile'
            if title not in seen_titles:
                task = task_service.create(
                    project_id,
                    title=title,
                    kind='repo_profile',
                    priority=4,
                    rationale='repo-aware sandbox execution needs a concrete profile',
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref, 'install_command': install_command, 'test_command': test_command},
                )
                node = execution_service.create_node(
                    project_id,
                    task['id'],
                    'repo_profiler',
                    input_artifact_ids=[a['id'] for a in [latest_architecture, latest_critique, latest_experiment_result, latest_repo_inspection] if a],
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref, 'install_command': install_command, 'test_command': test_command},
                )
                created_tasks.append(task)
                created_nodes.append(node)
                seen_titles.add(title)

        failing_result = None
        for candidate in [latest_patch_result, latest_experiment_result]:
            if not candidate:
                continue
            metrics = candidate['data'].get('metrics', {})
            if float(metrics.get('tests_failed', 0) or 0) > 0 or float(metrics.get('sandbox_exit_code', 0) or 0) != 0.0:
                failing_result = candidate
                break

        if repo_url and latest_repo_profile and failing_result and not latest_patch:
            title = 'Plan repository code patch'
            if title not in seen_titles:
                task = task_service.create(
                    project_id,
                    title=title,
                    kind='patch_planning',
                    priority=5,
                    rationale='failing repo evaluation detected',
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref, 'install_command': install_command, 'test_command': test_command},
                )
                node = execution_service.create_node(
                    project_id,
                    task['id'],
                    'patch_planner',
                    input_artifact_ids=[a['id'] for a in [latest_repo_profile, latest_repo_inspection, latest_critique, failing_result] if a],
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref, 'install_command': install_command, 'test_command': test_command},
                )
                created_tasks.append(task)
                created_nodes.append(node)
                seen_titles.add(title)

        latest_patch_plan = artifact_service.latest_by_type(project_id, 'code_patch_plan')
        if latest_patch_plan and not latest_patch:
            title = 'Generate repository code patch'
            if title not in seen_titles:
                task = task_service.create(
                    project_id,
                    title=title,
                    kind='patch_generation',
                    priority=5,
                    rationale='patch plan exists but no code patch artifact exists yet',
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref, 'install_command': install_command, 'test_command': test_command},
                )
                node = execution_service.create_node(
                    project_id,
                    task['id'],
                    'patch_generator',
                    input_artifact_ids=[a['id'] for a in [latest_patch_plan, latest_repo_profile, latest_repo_inspection] if a],
                    metadata={'repo_url': repo_url, 'repo_ref': repo_ref, 'install_command': install_command, 'test_command': test_command},
                )
                created_tasks.append(task)
                created_nodes.append(node)
                seen_titles.add(title)

        if latest_architecture and latest_critique and latest_critique['data'].get('issues'):
            title = f'Revise architecture v{latest_architecture["version"]}'
            if title not in seen_titles:
                task = task_service.create(
                    project_id,
                    title=title,
                    kind='architecture_revision',
                    priority=4,
                    rationale='latest critique indicates changes are required',
                    metadata={'artifact_id': latest_architecture['id'], 'critique_id': latest_critique['id']},
                )
                node = execution_service.create_node(
                    project_id,
                    task['id'],
                    'reviser',
                    input_artifact_ids=[latest_architecture['id'], latest_critique['id']],
                )
                created_tasks.append(task)
                created_nodes.append(node)
                seen_titles.add(title)

        return {
            'created_task_ids': [task['id'] for task in created_tasks],
            'created_node_ids': [node['id'] for node in created_nodes],
            'count': len(created_tasks),
        }


planner_service = PlannerService()
