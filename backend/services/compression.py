from __future__ import annotations

from collections import defaultdict

from backend.services.artifacts import artifact_service


class CompressionService:
    def compress_artifacts(self, project_id: str) -> dict:
        artifacts = artifact_service.list(project_id)
        buckets: dict[str, list[dict]] = defaultdict(list)
        for artifact in artifacts:
            if artifact['type'] in {'summary', 'memory_summary', 'evidence'}:
                buckets[artifact['type']].append(artifact)
        created = []
        for artifact_type, items in buckets.items():
            if len(items) < 3:
                continue
            summary_text = '; '.join(item['title'] for item in items[:8])
            created.append(
                artifact_service.create(
                    project_id=project_id,
                    artifact_type='memory_summary',
                    title=f'Compressed {artifact_type} bundle',
                    data={'text': summary_text, 'artifact_ids': [item['id'] for item in items[:8]]},
                    confidence=0.68,
                    parent_artifact_ids=[item['id'] for item in items[:8]],
                )
            )
        return {'created_artifact_ids': [item['id'] for item in created], 'count': len(created)}


compression_service = CompressionService()
