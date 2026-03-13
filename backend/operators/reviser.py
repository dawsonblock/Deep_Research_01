from __future__ import annotations

from backend.operators.registry import registry
from backend.services.llm import llm_service


def reviser(context: dict) -> dict:
    architecture = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'architecture'), None)
    critique = next((artifact for artifact in context.get('inputs', []) if artifact['type'] == 'critique'), None)
    base_components = list(architecture['data'].get('components', [])) if architecture else []
    issues = list(critique['data'].get('issues', [])) if critique else []
    additions = []
    for issue in issues:
        text = str(issue).lower()
        if 'search' in text and 'search_sidecar' not in base_components:
            additions.append('search_sidecar')
        if 'memory' in text and 'memory_adapter' not in base_components:
            additions.append('memory_adapter')
        if 'validation' in text and 'validation_layer' not in base_components:
            additions.append('validation_layer')
        if 'experiment' in text and 'experiment_loop' not in base_components:
            additions.append('experiment_loop')
        if 'sandbox' in text and 'sandbox_harness' not in base_components:
            additions.append('sandbox_harness')
    revised_components = list(dict.fromkeys(base_components + additions))
    if not revised_components:
        revised_components = ['execution_graph_runtime', 'typed_artifact_store', 'world_model']
    fallback = {
        'components': revised_components,
        'notes': [
            'Revised from critique feedback.',
            *[f'Addressed: {issue}' for issue in issues[:4]],
        ],
    }
    data = llm_service.complete_json(
        'Revise the architecture. Return JSON with keys components and notes.',
        f'Architecture: {architecture}\nCritique: {critique}',
        fallback,
    )
    revision_note = ' | '.join(issues[:3]) if issues else 'revision requested'
    return {
        'type': 'architecture',
        'title': architecture['title'] if architecture else 'Revised architecture',
        'data': {
            'goal': context['project']['goal'],
            'components': data.get('components', revised_components),
            'notes': data.get('notes', fallback['notes']),
        },
        'confidence': min(0.95, (architecture.get('confidence', 0.7) if architecture else 0.7) + 0.04),
        'revision_of_artifact_id': architecture['id'] if architecture else None,
        'revision_note': revision_note,
    }


registry.register('reviser', reviser)
