from __future__ import annotations

from backend.operators.registry import registry
from backend.services.llm import llm_service


def critic(context: dict) -> dict:
    issues: list[str] = []
    for artifact in context.get('inputs', []):
        if artifact['type'] == 'architecture':
            components = artifact['data'].get('components', [])
            required = {'execution_graph_runtime', 'typed_artifact_store', 'world_model', 'embedding_index', 'llm_adapter', 'sandbox_harness'}
            missing = sorted(required - set(components))
            for item in missing:
                issues.append(f'missing required component: {item}')
            if 'search_sidecar' not in components:
                issues.append('external evidence path is optional but currently absent')
        elif artifact['type'] == 'requirements':
            items = artifact['data'].get('items', [])
            if len(items) < 5:
                issues.append('requirements set is thin and should be expanded')
    if not issues:
        issues.append('no major structural gap found; next step is empirical validation')
    fallback = {'issues': issues}
    data = llm_service.complete_json(
        'Return critique JSON with key issues as a list of short strings.',
        f'Artifacts under review: {context.get("inputs", [])}',
        fallback,
    )
    return {
        'type': 'critique',
        'title': 'Critique',
        'data': {'issues': data.get('issues', issues)},
        'confidence': 0.76 if llm_service.available() else 0.74,
    }


registry.register('critic', critic)
