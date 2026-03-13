from __future__ import annotations

from backend.operators.registry import registry
from backend.services.llm import llm_service


def planner_agent(context: dict) -> dict:
    tasks = []
    for artifact in context.get('inputs', []):
        if artifact['type'] == 'critique':
            for issue in artifact['data'].get('issues', []):
                tasks.append({'title': f'Investigate: {issue}', 'kind': 'followup', 'priority': 3})
        elif artifact['type'] == 'requirements':
            tasks.append({'title': 'Synthesize architecture from requirements', 'kind': 'synthesis', 'priority': 4})
    if not tasks:
        tasks.append({'title': 'Gather more evidence', 'kind': 'research', 'priority': 2})
    fallback = {'tasks': tasks}
    data = llm_service.complete_json(
        'Return task planning JSON with key tasks. Each task needs title, kind, priority.',
        f'Input artifacts: {context.get("inputs", [])}',
        fallback,
    )
    cleaned = []
    for task in data.get('tasks', tasks):
        if not isinstance(task, dict) or not task.get('title'):
            continue
        cleaned.append({'title': str(task['title']), 'kind': str(task.get('kind', 'followup')), 'priority': int(task.get('priority', 1))})
    if not cleaned:
        cleaned = tasks
    return {
        'type': 'task_list',
        'title': 'Planned follow-up tasks',
        'data': {'tasks': cleaned},
        'confidence': 0.72 if llm_service.available() else 0.7,
    }


registry.register('planner_agent', planner_agent)
