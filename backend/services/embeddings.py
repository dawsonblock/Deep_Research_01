from __future__ import annotations

from typing import Any

import httpx
import numpy as np

from backend.config import get_settings
from backend.db import db
from backend.utils import dumps, loads, normalize_text, now_ts, tokenize


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        self.provider = settings.embedding_provider.lower()
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self.base_url = settings.llm_api_base_url.rstrip('/')
        self.api_key = settings.llm_api_key
        self.timeout = settings.llm_timeout_seconds

    def _local_hash_embedding(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in tokenize(text):
            idx = hash(token) % self.dim
            vec[idx] += 1.0 + (len(token) / 10.0)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.astype(float).tolist()

    def _remote_embedding(self, text: str) -> list[float] | None:
        if not self.api_key:
            return None
        headers = {'Authorization': f'Bearer {self.api_key}'}
        payload = {'model': self.model, 'input': text}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f'{self.base_url}/embeddings', headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            vector = data['data'][0]['embedding']
            return [float(x) for x in vector]
        except Exception:
            return None

    def embed_text(self, text: str) -> list[float]:
        text = normalize_text(text)
        if self.provider in {'openai', 'openrouter', 'compatible'}:
            vector = self._remote_embedding(text)
            if vector:
                return vector
        return self._local_hash_embedding(text)

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        av = np.array(a, dtype=np.float32)
        bv = np.array(b, dtype=np.float32)
        denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
        if denom == 0.0:
            return 0.0
        return float(np.dot(av, bv) / denom)

    def upsert_artifact_embedding(self, artifact_id: str, text: str) -> None:
        vector = self.embed_text(text)
        db.conn.execute(
            'INSERT INTO artifact_embeddings (artifact_id, model, vector_json, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(artifact_id) DO UPDATE SET model = excluded.model, vector_json = excluded.vector_json, updated_at = excluded.updated_at',
            (artifact_id, self.model if self.provider != 'local_hash' else 'local_hash', dumps(vector), now_ts()),
        )
        db.conn.commit()

    def upsert_memory_embedding(self, memory_id: str, text: str) -> None:
        vector = self.embed_text(text)
        db.conn.execute(
            'INSERT INTO memory_embeddings (memory_id, model, vector_json, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(memory_id) DO UPDATE SET model = excluded.model, vector_json = excluded.vector_json, updated_at = excluded.updated_at',
            (memory_id, self.model if self.provider != 'local_hash' else 'local_hash', dumps(vector), now_ts()),
        )
        db.conn.commit()

    def search_artifacts(self, project_id: str, query: str, limit: int = 5, artifact_type: str | None = None) -> list[dict[str, Any]]:
        qv = self.embed_text(query)
        sql = 'SELECT a.*, ae.vector_json FROM artifacts a JOIN artifact_embeddings ae ON a.id = ae.artifact_id WHERE a.project_id = ?'
        params: list[Any] = [project_id]
        if artifact_type:
            sql += ' AND a.type = ?'
            params.append(artifact_type)
        rows = db.conn.execute(sql, params).fetchall()
        scored = []
        for row in rows:
            item = dict(row)
            item['data'] = loads(item.pop('data_json'), {})
            score = self.cosine_similarity(qv, loads(item.pop('vector_json'), []))
            item['retrieval_score'] = score
            scored.append(item)
        scored.sort(key=lambda x: x['retrieval_score'], reverse=True)
        return scored[:limit]

    def search_memories(self, project_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        qv = self.embed_text(query)
        rows = db.conn.execute(
            'SELECT m.*, me.vector_json FROM memories m JOIN memory_embeddings me ON m.id = me.memory_id WHERE m.project_id = ? ORDER BY m.updated_at DESC',
            (project_id,),
        ).fetchall()
        scored = []
        for row in rows:
            item = dict(row)
            item['metadata'] = loads(item.pop('metadata_json'), {})
            score = self.cosine_similarity(qv, loads(item.pop('vector_json'), []))
            item['retrieval_score'] = score
            scored.append(item)
        scored.sort(key=lambda x: x['retrieval_score'], reverse=True)
        return scored[:limit]


embedding_service = EmbeddingService()
