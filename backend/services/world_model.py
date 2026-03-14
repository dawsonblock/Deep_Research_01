from __future__ import annotations

from backend.db import db
from backend.utils import new_id, normalize_text, now_ts

# Canonical graph mirror (Step 7 — mirror writes into canonical graph)
from research_engine.graph.graph_store import GraphStore
from research_engine.graph.world_model_adapter import WorldModelAdapter

_canonical_graph = GraphStore()
_canonical_adapter = WorldModelAdapter(_canonical_graph)


class WorldModelService:
    def update_from_artifact(self, artifact: dict) -> dict:
        created = {'claims': [], 'questions': [], 'hypotheses': []}
        atype = artifact['type']
        data = artifact['data']
        if atype == 'claims':
            for line in data.get('claims', []):
                created['claims'].append(self.create_claim(artifact['project_id'], artifact['id'], line, 0.65))
        elif atype == 'critique':
            for issue in data.get('issues', []):
                question = f'How should we address: {issue}'
                created['questions'].append(self.create_question(artifact['project_id'], artifact['id'], question, 2))
        elif atype == 'hypothesis':
            created['hypotheses'].append(
                self.create_hypothesis(
                    artifact['project_id'],
                    artifact['id'],
                    data.get('statement', ''),
                    data.get('prediction', ''),
                    artifact['confidence'],
                )
            )
        elif atype == 'requirements':
            for item in data.get('items', []):
                created['claims'].append(self.create_claim(artifact['project_id'], artifact['id'], f'Requirement: {item}', artifact['confidence']))
        elif atype == 'architecture':
            for component in data.get('components', []):
                created['claims'].append(self.create_claim(artifact['project_id'], artifact['id'], f'Architecture component: {component}', artifact['confidence']))
        elif atype == 'evidence':
            for item in data.get('items', []):
                title = item.get('title') if isinstance(item, dict) else str(item)
                created['claims'].append(self.create_claim(artifact['project_id'], artifact['id'], f'Evidence item: {title}', max(0.4, artifact['confidence'] - 0.1)))
        return created

    def create_claim(self, project_id: str, artifact_id: str | None, content: str, confidence: float) -> dict:
        claim_id = new_id()
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO claims (id, project_id, artifact_id, content, confidence, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (claim_id, project_id, artifact_id, normalize_text(content), confidence, 'active', ts, ts),
            )
        claim = self.get_claim(claim_id)
        # Mirror to canonical graph
        try:
            _canonical_adapter.mirror_claim(claim)
        except Exception:
            pass  # canonical mirror is best-effort; never break backend flow
        return claim

    def get_claim(self, claim_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM claims WHERE id = ?', (claim_id,)).fetchone()
        return dict(row) if row else None

    def create_question(self, project_id: str, artifact_id: str | None, content: str, priority: int = 1) -> dict:
        question_id = new_id()
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO questions (id, project_id, artifact_id, content, priority, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (question_id, project_id, artifact_id, normalize_text(content), priority, 'open', ts, ts),
            )
        return self.get_question(question_id)

    def get_question(self, question_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM questions WHERE id = ?', (question_id,)).fetchone()
        return dict(row) if row else None

    def create_hypothesis(self, project_id: str, artifact_id: str | None, statement: str, prediction: str, confidence: float) -> dict:
        hypothesis_id = new_id()
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO hypotheses (id, project_id, artifact_id, statement, prediction, confidence, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (hypothesis_id, project_id, artifact_id, normalize_text(statement), normalize_text(prediction), confidence, 'active', ts, ts),
            )
        hypothesis = self.get_hypothesis(hypothesis_id)
        # Mirror to canonical graph
        try:
            _canonical_adapter.mirror_hypothesis(hypothesis)
        except Exception:
            pass  # canonical mirror is best-effort
        return hypothesis

    def get_hypothesis(self, hypothesis_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM hypotheses WHERE id = ?', (hypothesis_id,)).fetchone()
        return dict(row) if row else None

    def low_confidence_claims(self, project_id: str, threshold: float = 0.5) -> list[dict]:
        rows = db.conn.execute('SELECT * FROM claims WHERE project_id = ? AND confidence < ? ORDER BY confidence ASC', (project_id, threshold)).fetchall()
        return [dict(row) for row in rows]

    def open_questions(self, project_id: str) -> list[dict]:
        rows = db.conn.execute('SELECT * FROM questions WHERE project_id = ? AND status = ? ORDER BY priority DESC, created_at', (project_id, 'open')).fetchall()
        return [dict(row) for row in rows]

    def active_hypotheses(self, project_id: str) -> list[dict]:
        rows = db.conn.execute('SELECT * FROM hypotheses WHERE project_id = ? AND status = ? ORDER BY created_at DESC', (project_id, 'active')).fetchall()
        return [dict(row) for row in rows]

    def close_question(self, question_id: str) -> None:
        db.conn.execute('UPDATE questions SET status = ?, updated_at = ? WHERE id = ?', ('closed', now_ts(), question_id))
        db.conn.commit()

    def update_hypothesis_confidence(self, hypothesis_id: str, confidence: float) -> None:
        db.conn.execute('UPDATE hypotheses SET confidence = ?, updated_at = ? WHERE id = ?', (confidence, now_ts(), hypothesis_id))
        db.conn.commit()


world_model_service = WorldModelService()
