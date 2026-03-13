from __future__ import annotations

from backend.operators.registry import registry
from backend.services.experiments import experiment_service
from backend.services.llm import llm_service
from backend.services.sandbox_harness import sandbox_harness_service
from backend.services.repo_profiles import repo_profile_service


def hypothesis_maker(context: dict) -> dict:
    architecture = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'architecture'), None)
    critique = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'critique'), None)

    # Template fallbacks (used when LLM is unavailable)
    statement = 'Execution-graph architecture improves repeatability for this project.'
    prediction = 'The graph-based path will produce a lower contradiction rate than a linear path and keep replayability above 0.7.'
    if architecture:
        component_count = len(architecture['data'].get('components', []))
        statement = f'This architecture with {component_count} components should benefit from explicit execution-graph control.'
    if critique and critique['data'].get('issues'):
        prediction = 'After revision, graph-based execution should reduce critique-derived contradiction rate relative to a linear baseline.'

    if llm_service.available():
        components = architecture['data'].get('components', []) if architecture else []
        issues = critique['data'].get('issues', []) if critique else []
        prompt = (
            f'Architecture components: {components[:20]}\n'
            f'Critique issues: {issues[:10]}\n\n'
            'Generate a research hypothesis for this project. '
            'Return a JSON object with keys: statement (concise hypothesis, 1-2 sentences) '
            'and prediction (measurable outcome, 1-2 sentences).'
        )
        llm_result = llm_service.complete_json(
            'You are a research scientist. Produce a testable hypothesis based on the given project artifacts.',
            prompt,
            fallback={'statement': statement, 'prediction': prediction},
        )
        statement = str(llm_result.get('statement', statement)).strip() or statement
        prediction = str(llm_result.get('prediction', prediction)).strip() or prediction

    return {
        'type': 'hypothesis',
        'title': 'Execution hypothesis',
        'data': {'statement': statement, 'prediction': prediction},
        'confidence': 0.72 if llm_service.available() else 0.62,
    }


def experiment_designer(context: dict) -> dict:
    statement = context.get('hypothesis_statement') or 'Execution graph improves repeatability.'
    prediction = context.get('prediction') or 'Graph-based execution will reduce contradiction rate and improve replayability.'
    task_metadata = dict(context.get('task', {}).get('metadata') or {})
    repo_url = context.get('repo_url') or task_metadata.get('repo_url')
    repo_ref = context.get('repo_ref') or task_metadata.get('repo_ref')
    install_command = context.get('install_command') or task_metadata.get('install_command')
    test_command = context.get('test_command') or task_metadata.get('test_command') or 'pytest -q'

    requirements = []
    architecture = []
    repo_profile = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'repo_profile'), None)
    for artifact in context.get('inputs', []):
        if artifact['type'] == 'requirements':
            requirements.extend(map(str, artifact['data'].get('items', [])))
        if artifact['type'] == 'architecture':
            architecture.extend(map(str, artifact['data'].get('components', [])))
    profile_data = repo_profile['data'] if repo_profile else None
    if repo_url and not profile_data:
        profile_data = repo_profile_service.infer_profile(
            project_id=context['project_id'],
            repo_url=repo_url,
            repo_ref=repo_ref,
            install_command=install_command,
            test_command=test_command,
            artifact_ids=context.get('resolved_input_ids', []),
            persist=False,
        )

    if repo_url:
        fallback = {
            'statement': statement,
            'prediction': prediction,
            'method': 'opensandbox_repo_test' if sandbox_harness_service.status().get('enabled') else 'repo_test_stub',
            'repo_profile_name': (profile_data or {}).get('name'),
            'metrics': ['sandbox_success_rate', 'sandbox_exit_code', 'stdout_line_count', 'stderr_line_count'],
            'steps': [
                'Ensure a persistent sandbox session for this project.',
                'Clone the target repository in the sandbox workspace.',
                'Optionally install dependencies.',
                'Run the test command and capture exit code and output.',
            ],
            'job': {
                'runner': 'opensandbox',
                'type': 'repo_test',
                'image': sandbox_harness_service.default_python_image,
                'repo_profile_id': profile_data.get('id') if profile_data else None,
                'repo_url': repo_url,
                'repo_ref': repo_ref,
                'install_command': install_command,
                'test_command': test_command,
                'reuse_project_session': True,
                'artifact_base_path': '/workspace/artifacts',
            },
        }
    else:
        fallback = {
            'statement': statement,
            'prediction': prediction,
            'method': 'opensandbox_python_benchmark' if sandbox_harness_service.status().get('enabled') else 'project_state_benchmark',
            'metrics': ['linear_contradiction_rate', 'graph_contradiction_rate', 'replayability_score', 'requirement_coverage'],
            'steps': [
                'Collect latest requirements, architecture, and critique artifacts.',
                'Compute architecture coverage against requirements.',
                'Estimate contradiction rate with and without explicit execution-graph dependencies.',
                'Update hypothesis confidence from the resulting metrics.',
            ],
            'job': {
                'runner': 'opensandbox',
                'type': 'python_script',
                'image': sandbox_harness_service.default_python_image,
                'script_path': '/workspace/run_experiment.py',
                'command': 'python /workspace/run_experiment.py',
                'env': {'PYTHONUNBUFFERED': '1'},
                'reuse_project_session': True,
            },
        }
    prompt = (
        f'Hypothesis: {statement}\nPrediction: {prediction}\n'
        f'Requirements: {requirements}\nArchitecture: {architecture}\nRepo URL: {repo_url or ""}'
    )
    data = llm_service.complete_json(
        'Return experiment plan JSON with keys statement, prediction, method, metrics, steps, and job.',
        prompt,
        fallback,
    )
    return {
        'type': 'experiment_plan',
        'title': 'Experiment plan',
        'data': {
            'statement': data.get('statement', statement),
            'prediction': data.get('prediction', prediction),
            'method': data.get('method', fallback['method']),
            'metrics': data.get('metrics', fallback['metrics']),
            'steps': data.get('steps', fallback['steps']),
            'job': data.get('job', fallback['job']),
        },
        'confidence': 0.76 if llm_service.available() else 0.74,
    }


def experiment_runner(context: dict) -> dict:
    plan = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'experiment_plan'), None)
    if not plan:
        return {
            'type': 'experiment_result',
            'title': 'Experiment result',
            'data': {'metrics': {}, 'summary': {'error': 'experiment plan missing', 'method': 'none'}},
            'confidence': 0.2,
        }
    result = experiment_service.run_plan(context['project_id'], plan, context.get('inputs', []))
    run_method = result['summary'].get('method', 'unknown')
    return {
        'type': 'experiment_result',
        'title': 'Experiment result',
        'data': {
            'plan_artifact_id': plan['id'],
            'run_id': result['run_id'],
            'method': run_method,
            'metrics': result['metrics'],
            'summary': result['summary'],
        },
        'confidence': 0.88 if run_method == 'llm_benchmark' else (0.82 if run_method == 'opensandbox' else 0.64),
    }


def evaluator(context: dict) -> dict:
    result_artifact = next((artifact for artifact in context.get('inputs', []) if artifact['type'] in {'experiment_result', 'patch_test_result'}), None)
    if not result_artifact:
        return {
            'type': 'evaluation',
            'title': 'Evaluation',
            'data': {'verdict': 'No experiment result was provided.', 'recommendation': 'Run an experiment before evaluating.'},
            'confidence': 0.2,
        }
    evaluation = experiment_service.evaluate_result(result_artifact)
    return {
        'type': 'evaluation',
        'title': 'Evaluation',
        'data': evaluation,
        'confidence': evaluation['confidence'],
    }


registry.register('experiment_designer', experiment_designer)
registry.register('experiment_runner', experiment_runner)
registry.register('evaluator', evaluator)
registry.register('hypothesis_maker', hypothesis_maker)
