from __future__ import annotations

from pprint import pprint

from backend.services.artifacts import artifact_service
from backend.services.execution import execution_service
from backend.services.experiments import experiment_service
from backend.services.planner import planner_service
from backend.services.project_state import project_state_service


if __name__ == '__main__':
    project = project_state_service.create_project(
        name='Demo Research Project',
        goal='Design a compact autonomous research runtime with memory, vector retrieval, llm adapters, search sidecars, and an experiment loop.',
    )
    print('Created project:')
    pprint(project)

    from backend.main import bootstrap_project
    from backend.models import BootstrapProjectRequest

    bootstrap_project(project['id'], BootstrapProjectRequest())
    result = execution_service.run_until_idle(project['id'], max_steps=12)
    print('\nRun until idle:')
    pprint(result['summary'])

    replanned = planner_service.replan(project['id'])
    print('\nReplanner created tasks and nodes:')
    pprint(replanned)

    result = execution_service.run_until_idle(project['id'], max_steps=20)
    print('\nRun replanned work:')
    pprint(result['summary'])

    experiments = experiment_service.list_runs(project['id'])
    print('\nExperiment runs:')
    pprint(experiments)

    architecture = artifact_service.latest_by_type(project['id'], 'architecture')
    if architecture:
        revised = artifact_service.create_revision(
            base_artifact_id=architecture['id'],
            title=architecture['title'],
            data={
                'goal': architecture['data'].get('goal'),
                'components': list(dict.fromkeys(architecture['data'].get('components', []) + ['artifact_versioning'])),
                'notes': architecture['data'].get('notes', []) + ['Added artifact versioning to the scaffold.'],
            },
            confidence=min(0.95, architecture['confidence'] + 0.05),
            revision_note='manual demo revision',
        )
        print('\nCreated revision:')
        pprint(revised)
        print('\nArchitecture lineage:')
        pprint(artifact_service.lineage(revised['lineage_id']))



    from backend.services.tasks import task_service

    repo_metadata = {'repo_url': 'https://github.com/example/demo-repo', 'test_command': 'pytest -q'}

    repo_inspect_task = task_service.create(
        project['id'],
        title='Inspect demo repository files',
        kind='repo_inspection',
        priority=5,
        rationale='demo repo inspection',
        metadata=repo_metadata,
    )
    inspect_node = execution_service.create_node(
        project['id'],
        repo_inspect_task['id'],
        'repo_inspector',
        metadata=repo_metadata,
    )

    repo_profile_task = task_service.create(
        project['id'],
        title='Infer repository execution profile',
        kind='repo_profile',
        priority=4,
        rationale='demo repo profile generation',
        metadata=repo_metadata,
    )
    execution_service.create_node(
        project['id'],
        repo_profile_task['id'],
        'repo_profiler',
        dependency_node_ids=[inspect_node['id']],
        metadata=repo_metadata,
    )

    print('\nRun repo inspection/profile work:')
    pprint(execution_service.run_until_idle(project['id'], max_steps=8)['summary'])

    patch_plan_task = task_service.create(
        project['id'],
        title='Plan repository code patch',
        kind='patch_planning',
        priority=4,
        rationale='demo patch planning',
        metadata=repo_metadata,
    )
    latest_profile = artifact_service.latest_by_type(project['id'], 'repo_profile')
    latest_inspection = artifact_service.latest_by_type(project['id'], 'repo_inspection')
    latest_critique = artifact_service.latest_by_type(project['id'], 'critique')
    latest_result = artifact_service.latest_by_type(project['id'], 'experiment_result')
    execution_service.create_node(
        project['id'],
        patch_plan_task['id'],
        'patch_planner',
        input_artifact_ids=[a['id'] for a in [latest_profile, latest_inspection, latest_critique, latest_result] if a],
        metadata=repo_metadata,
    )

    print('\nRun patch planning work:')
    pprint(execution_service.run_until_idle(project['id'], max_steps=6)['summary'])

    patch_gen_task = task_service.create(
        project['id'],
        title='Generate repository code patch',
        kind='patch_generation',
        priority=4,
        rationale='demo patch generation',
        metadata=repo_metadata,
    )
    latest_patch_plan = artifact_service.latest_by_type(project['id'], 'code_patch_plan')
    execution_service.create_node(
        project['id'],
        patch_gen_task['id'],
        'patch_generator',
        input_artifact_ids=[a['id'] for a in [latest_patch_plan, latest_profile, latest_inspection] if a],
        metadata=repo_metadata,
    )

    print('\nRun patch generation work:')
    pprint(execution_service.run_until_idle(project['id'], max_steps=8)['summary'])

    print('\nFinal summary:')
    pprint(project_state_service.summarize(project['id']))
