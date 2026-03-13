from __future__ import annotations

from backend.operators.registry import registry
from backend.services.llm import llm_service


def _flatten_input_text(context: dict) -> str:
    chunks = []
    for artifact in context.get('inputs', []):
        data = artifact['data']
        chunks.append(artifact['title'])
        if artifact['type'] == 'evidence':
            for item in data.get('items', []):
                chunks.append(item.get('title', ''))
                chunks.append(item.get('snippet', ''))
        elif artifact['type'] == 'requirements':
            chunks.extend(map(str, data.get('items', [])))
        elif artifact['type'] == 'critique':
            chunks.extend(map(str, data.get('issues', [])))
        else:
            chunks.append(str(data))
    return ' '.join(chunks)


def synthesizer(context: dict) -> dict:
    goal = context['project']['goal']
    text = _flatten_input_text(context)
    fallback = {
        'components': [
            'project_state_engine',
            'execution_graph_runtime',
            'typed_artifact_store',
            'world_model',
            'embedding_index',
            'llm_adapter',
            'memory_adapter',
            'replanning_loop',
            'compression_cycle',
            'sandbox_harness',
        ],
        'notes': [
            'Memory should stay behind an adapter boundary.',
            'Search should remain a sidecar HTTP dependency.',
        ],
    }
    if 'search' in text.lower():
        fallback['components'].append('search_sidecar')
    if 'experiment' in text.lower() or 'hypothesis' in text.lower():
        fallback['components'].append('experiment_loop')
        fallback['components'].append('sandbox_harness')
    data = llm_service.complete_json(
        'Return compact architecture JSON with keys components and notes.',
        f'Goal: {goal}\nEvidence and requirements: {text}',
        fallback,
    )
    components = data.get('components', fallback['components'])
    notes = data.get('notes', fallback['notes'])
    return {
        'type': 'architecture',
        'title': 'Synthesized architecture',
        'data': {'goal': goal, 'components': components, 'notes': notes},
        'confidence': 0.74 if llm_service.available() else 0.72,
    }


def requirements_extractor(context: dict) -> dict:
    goal = context['project']['goal']
    fallback = {
        'items': [
            'persistent state',
            'typed artifacts',
            'execution dependencies',
            'validation and scoring',
            'world-model updates',
            'embedding-backed retrieval',
            'memory retrieval',
            'replanning',
            'llm adapter boundary',
            'sandboxed experiment harness',
        ]
    }
    if 'search' in goal.lower():
        fallback['items'].append('external web search sidecar')
    data = llm_service.complete_json(
        'Extract implementation requirements. Return JSON with key items as a list of strings.',
        f'Goal: {goal}',
        fallback,
    )
    items = data.get('items', fallback['items'])
    return {
        'type': 'requirements',
        'title': 'Extracted requirements',
        'data': {'items': items},
        'confidence': 0.72 if llm_service.available() else 0.7,
    }


registry.register('synthesizer', synthesizer)
registry.register('extract_requirements', requirements_extractor)
