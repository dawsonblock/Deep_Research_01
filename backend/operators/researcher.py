from __future__ import annotations

from backend.operators.registry import registry
from backend.services.artifacts import artifact_service
from backend.services.memory import memory_service
from backend.services.search import search_service


def researcher(context: dict) -> dict:
    project_id = context['project_id']
    query = context.get('query') or context['task']['title']
    memories = memory_service.search(project_id, query, limit=3)
    relevant_artifacts = [
        {'title': item['title'], 'snippet': artifact_service.to_search_text(item), 'source': 'artifact', 'url': ''}
        for item in context.get('inputs', [])
    ]
    external = search_service.search(query, limit=5)
    memory_hits = [
        {'title': f"Memory: {item['kind']}", 'snippet': item['content'], 'source': 'memory', 'url': ''}
        for item in memories
    ]
    items = relevant_artifacts + memory_hits + external
    confidence = 0.65 if external and external[0]['source'] != 'local_stub' else 0.5
    return {
        'type': 'evidence',
        'title': f'Evidence for {query}',
        'data': {'query': query, 'items': items},
        'confidence': confidence,
    }


registry.register('researcher', researcher)
