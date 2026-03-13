from __future__ import annotations

from backend.operators.registry import registry
from backend.services.failure_analysis import failure_analysis_service
from backend.services.llm import llm_service
from backend.services.patch_synthesizer import patch_synthesizer_service
from backend.services.repo_inspection import repo_inspection_service
from backend.services.repo_profiles import repo_profile_service
from backend.services.sandbox_harness import sandbox_harness_service


def repo_inspector(context: dict) -> dict:
    task_meta = dict(context.get('task', {}).get('metadata') or {})
    repo_url = context.get('repo_url') or task_meta.get('repo_url') or ''
    try:
        result = repo_inspection_service.inspect(
            project_id=context['project_id'],
            repo_url=repo_url,
            repo_ref=context.get('repo_ref') or task_meta.get('repo_ref'),
            session_id=task_meta.get('session_id'),
            image=task_meta.get('image'),
            reuse_project_session=bool(task_meta.get('reuse_project_session', True)),
            create_artifact=False,
            prefer_workspace=bool(task_meta.get('prefer_workspace', True)),
        )
    except Exception as exc:
        result = {
            'inspected': False,
            'method': 'operator_error',
            'error': str(exc),
            'repo_url': repo_url,
            'file_tree': [],
            'snapshots': {},
            'symbol_table': {},
            'file_symbols': {},
        }
    return {
        'type': 'repo_inspection',
        'title': f"Repo inspection: {result.get('repo_name') or 'repository'}",
        'data': result,
        'confidence': 0.84 if result.get('inspected') else 0.48,
    }


def repo_profiler(context: dict) -> dict:
    task_meta = dict(context.get('task', {}).get('metadata') or {})
    profile = repo_profile_service.infer_profile(
        project_id=context['project_id'],
        repo_url=context.get('repo_url') or task_meta.get('repo_url'),
        repo_ref=context.get('repo_ref') or task_meta.get('repo_ref'),
        install_command=context.get('install_command') or task_meta.get('install_command'),
        test_command=context.get('test_command') or task_meta.get('test_command'),
        artifact_ids=context.get('resolved_input_ids', []),
        persist=True,
    )
    return {
        'type': 'repo_profile',
        'title': f"Repo profile: {profile['name']}",
        'data': profile,
        'confidence': 0.78,
    }


def patch_planner(context: dict) -> dict:
    task_meta = dict(context.get('task', {}).get('metadata') or {})
    repo_profile = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'repo_profile'), None)
    critique = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'critique'), None)
    inspection = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'repo_inspection'), None)
    experiment_result = next((artifact for artifact in context.get('inputs', []) if artifact['type'] in {'experiment_result', 'patch_test_result'}), None)
    profile_data = repo_profile['data'] if repo_profile else repo_profile_service.infer_profile(
        project_id=context['project_id'],
        repo_url=task_meta.get('repo_url'),
        repo_ref=task_meta.get('repo_ref'),
        install_command=task_meta.get('install_command'),
        test_command=task_meta.get('test_command'),
        artifact_ids=context.get('resolved_input_ids', []),
        persist=False,
    )
    issues = list((critique or {}).get('data', {}).get('issues', []))
    metrics = dict((experiment_result or {}).get('data', {}).get('metrics', {}))
    benchmark_parse = dict(((experiment_result or {}).get('data', {}).get('summary') or {}).get('benchmark_parse') or {})
    inspection_data = (inspection or {}).get('data', {})
    analysis = failure_analysis_service.analyze(inspection_data, benchmark_parse, profile_data)

    # Pull AST-derived file_symbols from inspection for richer target context
    file_symbols = dict(inspection_data.get('file_symbols') or {})
    snapshots = dict(inspection_data.get('snapshots') or {})

    targets = []
    seen_paths = set()
    for ranked in analysis.get('ranked_targets', [])[:10]:
        path = str(ranked.get('path') or '').strip()
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        # Attach AST symbol list for this file if available
        ast_symbols = file_symbols.get(path, [])
        # Enrich symbol_matches with AST-derived slices for top symbols
        symbol_matches = list(ranked.get('symbol_matches', []))[:6]
        if not symbol_matches and ast_symbols and snapshots.get(path):
            try:
                from backend.services.ast_analysis import ast_analysis_service
                for sym_info in ast_symbols[:4]:
                    fn_slice = ast_analysis_service.get_function_slice(snapshots[path], sym_info['name'], path=path)
                    if fn_slice:
                        symbol_matches.append({
                            'symbol': sym_info['name'],
                            'name': sym_info['name'],
                            'kind': fn_slice.get('kind'),
                            'path': path,
                            'line': fn_slice.get('start_line'),
                            'source': fn_slice.get('source', '')[:1200],
                        })
            except Exception:
                pass
        targets.append({
            'path': path,
            'reason': '; '.join(ranked.get('blame_reasons', [])[:2]) or 'ranked from failure analysis',
            'strategy': str(ranked.get('strategy') or 'overwrite'),
            'score': float(ranked.get('score', 0.0) or 0.0),
            'blame_score': float(ranked.get('blame_score', ranked.get('score', 0.0)) or 0.0),
            'blame_reasons': list(ranked.get('blame_reasons', []))[:6],
            'symbol_matches': symbol_matches,
            'context_excerpt': str(ranked.get('context_excerpt') or ''),
            'ast_symbols': [{'name': s.get('name'), 'kind': s.get('kind'), 'start_line': s.get('start_line'), 'end_line': s.get('end_line')} for s in ast_symbols[:12]],
        })

    detected_files = list(inspection_data.get('detected_files', []))
    framework_defaults = []
    if profile_data['framework'] == 'pytest':
        framework_defaults = ['pytest.ini' if 'pytest.ini' in detected_files else ('pyproject.toml' if 'pyproject.toml' in detected_files else 'pytest.ini')]
    elif profile_data['framework'] in {'jest', 'vitest'}:
        framework_defaults = ['package.json']
        if 'tsconfig.json' in detected_files:
            framework_defaults.append('tsconfig.json')
    elif profile_data['framework'] == 'cargo':
        framework_defaults = ['Cargo.toml']
    elif profile_data['framework'] == 'go_test':
        framework_defaults = ['go.mod']
    for path in framework_defaults:
        if path not in seen_paths:
            seen_paths.add(path)
            targets.append({'path': path, 'reason': f'{profile_data["framework"]} configuration fallback', 'strategy': 'overwrite', 'score': 1.0, 'blame_score': 1.0, 'blame_reasons': [f'{profile_data["framework"]} configuration fallback'], 'symbol_matches': [], 'context_excerpt': ''})

    if metrics.get('tests_failed', 0) and not targets:
        targets.append({'path': '.', 'reason': 'tests are failing but no concrete file could be ranked', 'strategy': 'manual_review', 'score': 0.5, 'blame_score': 0.5, 'blame_reasons': ['fallback manual review target'], 'symbol_matches': [], 'context_excerpt': ''})

    failure_context = {
        'failing_tests': benchmark_parse.get('failing_tests', [])[:8],
        'hinted_paths': benchmark_parse.get('hinted_paths', [])[:8],
        'failure_messages': benchmark_parse.get('failure_messages', [])[:5],
        'trace_excerpt': benchmark_parse.get('trace_excerpt', ''),
        'derived_symbols': analysis.get('derived_symbols', [])[:12],
    }
    fallback = {
        'repo_profile_name': profile_data['name'],
        'repo_url': task_meta.get('repo_url') or profile_data.get('metadata', {}).get('repo_url'),
        'repo_ref': task_meta.get('repo_ref') or profile_data.get('metadata', {}).get('repo_ref'),
        'install_command': task_meta.get('install_command') or profile_data.get('install_command'),
        'test_command': task_meta.get('test_command') or profile_data.get('test_command'),
        'targets': targets,
        'ranked_targets': targets,
        'goals': issues[:5] or benchmark_parse.get('failure_messages', [])[:3] or ['reduce failing test count', 'improve sandbox benchmark success rate'],
        'patch_style': 'unified_diff',
        'failure_context': failure_context,
        'failure_analysis': analysis,
    }
    data = llm_service.complete_json(
        'Return JSON with keys repo_profile_name, repo_url, repo_ref, install_command, test_command, targets, ranked_targets, goals, patch_style, failure_context, failure_analysis. Preserve score/blame information on ranked targets.',
        f'Context inputs: {context.get("inputs", [])}',
        fallback,
    )
    return {
        'type': 'code_patch_plan',
        'title': 'Patch plan',
        'data': {
            'repo_profile_name': data.get('repo_profile_name', fallback['repo_profile_name']),
            'repo_url': data.get('repo_url', fallback['repo_url']),
            'repo_ref': data.get('repo_ref', fallback['repo_ref']),
            'install_command': data.get('install_command', fallback['install_command']),
            'test_command': data.get('test_command', fallback['test_command']),
            'targets': data.get('targets', fallback['targets']),
            'ranked_targets': data.get('ranked_targets', fallback['ranked_targets']),
            'goals': data.get('goals', fallback['goals']),
            'patch_style': data.get('patch_style', fallback['patch_style']),
            'failure_context': data.get('failure_context', fallback['failure_context']),
            'failure_analysis': data.get('failure_analysis', fallback['failure_analysis']),
        },
        'confidence': 0.78 if targets else 0.52,
    }
def patch_generator(context: dict) -> dict:
    task_meta = dict(context.get('task', {}).get('metadata') or {})
    plan = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'code_patch_plan'), None)
    repo_profile = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'repo_profile'), None)
    inspection = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'repo_inspection'), None)
    failing_result = next((artifact for artifact in context.get('inputs', []) if artifact['type'] in {'patch_test_result', 'experiment_result'}), None)
    if not inspection and (task_meta.get('repo_url') or (plan and plan['data'].get('repo_url'))):
        try:
            inspected = repo_inspection_service.inspect(
                project_id=context['project_id'],
                repo_url=task_meta.get('repo_url') or plan['data'].get('repo_url') or '',
                repo_ref=task_meta.get('repo_ref') or plan['data'].get('repo_ref'),
                session_id=task_meta.get('session_id'),
                image=task_meta.get('image'),
                reuse_project_session=bool(task_meta.get('reuse_project_session', True)),
                create_artifact=False,
                prefer_workspace=True,
            )
            inspection = {'type': 'repo_inspection', 'data': inspected}
        except Exception as exc:
            inspection = {'type': 'repo_inspection', 'data': {
                'inspected': False, 'method': 'ad_hoc_inspect_failed', 'error': str(exc),
                'file_tree': [], 'snapshots': {}, 'symbol_table': {}, 'file_symbols': {},
            }}
    if not plan:
        fallback = {
            'repo_url': task_meta.get('repo_url'),
            'repo_ref': task_meta.get('repo_ref'),
            'install_command': task_meta.get('install_command'),
            'test_command': task_meta.get('test_command'),
            'patch_format': 'unified_diff',
            'patch_text': '',
            'file_patches': [],
            'notes': ['no patch plan was available'],
            'patch_summary': {'patch_count': 0, 'paths': [], 'framework': (repo_profile or {}).get('data', {}).get('framework', 'generic'), 'inspection_used': bool(inspection)},
        }
        return {'type': 'code_patch', 'title': 'Generated code patch', 'data': fallback, 'confidence': 0.25}
    try:
        synthesized = patch_synthesizer_service.synthesize(
            plan=plan,
            repo_profile=(repo_profile or {}).get('data', {}),
            inspection=(inspection or {}).get('data', {}),
            task_meta=task_meta,
            failing_result=failing_result,
        )
    except Exception as exc:
        synthesized = {
            'repo_url': task_meta.get('repo_url'),
            'patch_format': 'unified_diff',
            'patch_text': '',
            'file_patches': [],
            'notes': [f'patch synthesis failed: {exc}'],
            'failure_context': {},
            'patch_summary': {'patch_count': 0, 'paths': [], 'framework': (repo_profile or {}).get('data', {}).get('framework', 'generic'), 'inspection_used': bool(inspection), 'error': str(exc)},
        }
    return {
        'type': 'code_patch',
        'title': 'Generated code patch',
        'data': synthesized,
        'confidence': 0.76 if synthesized.get('patch_text') else 0.5,
    }


def patch_test_runner(context: dict) -> dict:
    task_meta = dict(context.get('task', {}).get('metadata') or {})
    patch_artifacts = [artifact for artifact in context.get('inputs', []) if artifact['type'] == 'code_patch']
    repo_profile = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'repo_profile'), None)
    patch = patch_artifacts[-1] if patch_artifacts else None
    repo_url = task_meta.get('repo_url') or (patch['data'].get('repo_url') if patch else None) or (repo_profile['data'].get('metadata', {}).get('repo_url') if repo_profile else None)
    repo_ref = task_meta.get('repo_ref') or (patch['data'].get('repo_ref') if patch else None) or (repo_profile['data'].get('metadata', {}).get('repo_ref') if repo_profile else None)
    install_command = task_meta.get('install_command') or (patch['data'].get('install_command') if patch else None) or (repo_profile['data'].get('install_command') if repo_profile else None)
    test_command = task_meta.get('test_command') or (patch['data'].get('test_command') if patch else None) or (repo_profile['data'].get('test_command') if repo_profile else None) or 'pytest -q'
    try:
        result = sandbox_harness_service.run_patch_test_loop(
            project_id=context['project_id'],
            session_id=task_meta.get('session_id'),
            repo_url=repo_url,
            repo_ref=repo_ref,
            install_command=install_command,
            test_command=test_command,
            image=task_meta.get('image'),
            reuse_project_session=bool(task_meta.get('reuse_project_session', True)),
            artifact_ids=context.get('resolved_input_ids', []),
            patch_artifact_ids=[artifact['id'] for artifact in patch_artifacts],
            base_path=str(task_meta.get('base_path') or '/workspace/artifacts'),
            create_result_artifact=False,
            repo_profile_id=repo_profile['id'] if repo_profile else task_meta.get('repo_profile_id'),
        )
    except Exception as exc:
        result = {
            'status': 'operator_error',
            'error': str(exc),
            'metrics': {
                'sandbox_available': 0.0,
                'sandbox_exit_code': 1.0,
                'sandbox_success_rate': 0.0,
                'tests_total': 0.0,
                'tests_passed': 0.0,
                'tests_failed': 0.0,
                'benchmark_success_rate': 0.0,
            },
        }
    return {
        'type': 'patch_test_result',
        'title': 'Patch test result',
        'data': {
            'run_id': result.get('run_id'),
            'metrics': result.get('metrics', {}),
            'summary': result,
            'repo_url': repo_url,
        },
        'confidence': 0.8 if result.get('metrics', {}).get('benchmark_success_rate', 0.0) >= 0.5 else 0.45,
    }


registry.register('repo_inspector', repo_inspector)
registry.register('repo_profiler', repo_profiler)
registry.register('patch_planner', patch_planner)
registry.register('patch_generator', patch_generator)
registry.register('patch_test_runner', patch_test_runner)
