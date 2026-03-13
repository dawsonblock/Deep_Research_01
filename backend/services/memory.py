from __future__ import annotations

from backend.db import db
from backend.services.embeddings import embedding_service
from backend.utils import dumps, jaccard_score, loads, new_id, normalize_text, now_ts


class MemoryService:
    def create_from_artifact(self, artifact: dict) -> dict:
        content = self._distill_artifact(artifact)
        metadata = {'artifact_type': artifact['type'], 'artifact_score': artifact['score']}
        memory_id = new_id()
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO memories (id, project_id, kind, source_artifact_id, content, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (memory_id, artifact['project_id'], 'artifact_memory', artifact['id'], content, dumps(metadata), ts, ts),
            )
            conn.execute('INSERT OR IGNORE INTO memory_links (memory_id, artifact_id) VALUES (?, ?)', (memory_id, artifact['id']))
        embedding_service.upsert_memory_embedding(memory_id, content)
        return self.get(memory_id)

    def _distill_artifact(self, artifact: dict) -> str:
        data = artifact['data']
        if artifact['type'] == 'requirements':
            return 'Requirements: ' + '; '.join(map(str, data.get('items', [])))
        if artifact['type'] == 'architecture':
            return 'Architecture: ' + '; '.join(map(str, data.get('components', [])))
        if artifact['type'] == 'critique':
            return 'Critique: ' + '; '.join(map(str, data.get('issues', [])))
        if artifact['type'] == 'evidence':
            items = data.get('items', [])
            return 'Evidence: ' + '; '.join(str(item.get('title', item)) for item in items)
        if 'text' in data:
            return normalize_text(str(data.get('text', '')))
        return normalize_text(str(data))

    def get(self, memory_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM memories WHERE id = ?', (memory_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item['metadata'] = loads(item.pop('metadata_json'), {})
        return item

    def search(self, project_id: str, query: str, limit: int = 5) -> list[dict]:
        vector_hits = embedding_service.search_memories(project_id, query, limit=max(limit * 3, 10))
        rescored = []
        for item in vector_hits:
            lexical = jaccard_score(query, item['content'])
            item['retrieval_score'] = round((item['retrieval_score'] * 0.7) + (lexical * 0.3), 4)
            if item['retrieval_score'] > 0:
                rescored.append(item)
        rescored.sort(key=lambda x: x['retrieval_score'], reverse=True)
        return rescored[:limit]

    def consolidate(self, project_id: str, similarity_threshold: float = 0.9) -> dict:
        memories = [self.get(row['id']) for row in db.conn.execute('SELECT id FROM memories WHERE project_id = ? ORDER BY created_at', (project_id,)).fetchall()]
        removed = []
        kept = []
        for memory in memories:
            duplicate = False
            for survivor in kept:
                score = max(
                    jaccard_score(memory['content'], survivor['content']),
                    embedding_service.cosine_similarity(
                        embedding_service.embed_text(memory['content']),
                        embedding_service.embed_text(survivor['content']),
                    ),
                )
                if score >= similarity_threshold:
                    db.conn.execute('DELETE FROM memories WHERE id = ?', (memory['id'],))
                    db.conn.execute('DELETE FROM memory_embeddings WHERE memory_id = ?', (memory['id'],))
                    removed.append(memory['id'])
                    duplicate = True
                    break
            if not duplicate:
                kept.append(memory)
        db.conn.commit()
        return {'kept': len(kept), 'removed': removed}


memory_service = MemoryService()
