from __future__ import annotations

import math

from backend.db import db
from backend.utils import dumps, loads, new_id, now_ts

# Negative polarity words used as a lightweight contradiction heuristic when
# no embedding vectors are available.
_NEGATION_TERMS = frozenset([
    'not', 'no', "don't", "doesn't", "isn't", "aren't", "won't",
    "can't", "cannot", "never', 'without', 'lack', 'lacks', 'fail",
    "fails", "broken", "missing", "absent", "excluded",
])

# Threshold below which two claim embeddings are considered to be talking
# about the same topic (high similarity) yet might contradict each other.
_SIMILARITY_TOPIC_THRESHOLD = 0.82
# If two on-topic claims have a polarity conflict we flag them.
_POLARITY_CONFLICT_CONFIDENCE_SWING = 0.15


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a)) or 1.0


def _cosine(a: list[float], b: list[float]) -> float:
    return _dot(a, b) / (_norm(a) * _norm(b))


def _load_embedding(artifact_id: str) -> list[float] | None:
    row = db.conn.execute(
        'SELECT vector_json FROM artifact_embeddings WHERE artifact_id = ?',
        (artifact_id,),
    ).fetchone()
    if not row:
        return None
    try:
        vec = loads(row['vector_json'], None)
        return vec if isinstance(vec, list) and vec else None
    except Exception:
        return None


def _has_negation(text: str) -> bool:
    tokens = set(text.lower().split())
    return bool(tokens & _NEGATION_TERMS)


def _extract_claim_texts(artifact: dict) -> list[str]:
    """Return plain-text claim strings from an artifact of various types."""
    data = artifact.get('data') or {}
    atype = artifact.get('type', '')
    texts: list[str] = []
    if atype == 'claims':
        texts.extend(str(c) for c in data.get('claims', []))
    elif atype == 'architecture':
        texts.extend(str(c) for c in data.get('components', []))
    elif atype == 'requirements':
        texts.extend(str(i) for i in data.get('items', []))
    elif atype == 'hypothesis':
        s = data.get('statement', '')
        p = data.get('prediction', '')
        if s:
            texts.append(s)
        if p:
            texts.append(p)
    return [t.strip() for t in texts if t.strip()]


class ConflictResolutionService:
    """Auto-detects and resolves conflicts between world-model claims."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_conflicts(self, project_id: str, new_artifact: dict) -> list[dict]:
        """Return a list of conflict-pair dicts for the just-created artifact.

        Each pair: {
            'claim_a_id': str,   # from an existing active claim
            'claim_b_id': str,   # derived from the new artifact
            'similarity': float,
            'conflict_type': 'polarity' | 'semantic_duplicate',
        }
        The caller is responsible for calling resolve() on the results.
        """
        new_texts = _extract_claim_texts(new_artifact)
        if not new_texts:
            return []

        # Fetch active claims for this project (excluding claims derived from
        # the new artifact itself to avoid self-conflict).
        rows = db.conn.execute(
            "SELECT id, content, confidence, artifact_id FROM claims "
            "WHERE project_id = ? AND status = 'active' AND artifact_id != ?",
            (project_id, new_artifact['id']),
        ).fetchall()
        if not rows:
            return []

        new_embedding = _load_embedding(new_artifact['id'])
        conflicts: list[dict] = []

        for row in rows:
            existing_text: str = row['content']
            existing_id: str = row['id']
            existing_conf: float = float(row['confidence'])
            existing_art_id: str | None = row['artifact_id']

            # ---- Embedding similarity check ----
            existing_emb = _load_embedding(existing_art_id) if existing_art_id else None

            if new_embedding and existing_emb and len(new_embedding) == len(existing_emb):
                similarity = _cosine(new_embedding, existing_emb)
                if similarity >= _SIMILARITY_TOPIC_THRESHOLD:
                    # High topic overlap — check for polarity flip
                    new_has_neg = any(_has_negation(t) for t in new_texts)
                    old_has_neg = _has_negation(existing_text)
                    if new_has_neg != old_has_neg:
                        conflicts.append({
                            'claim_a_id': existing_id,
                            'claim_b_id': None,  # resolved against the whole artifact
                            'artifact_b_id': new_artifact['id'],
                            'similarity': round(similarity, 4),
                            'conflict_type': 'polarity',
                            'existing_confidence': existing_conf,
                        })
                        continue
            else:
                similarity = 0.0

            # ---- Keyword polarity fallback (no embeddings) ----
            for new_text in new_texts:
                shared_words = (
                    set(existing_text.lower().split()) &
                    set(new_text.lower().split()) -
                    {'the', 'a', 'an', 'of', 'in', 'to', 'and', 'or', 'is', 'are', 'be'}
                )
                if len(shared_words) >= 4:
                    new_has_neg = _has_negation(new_text)
                    old_has_neg = _has_negation(existing_text)
                    if new_has_neg != old_has_neg:
                        conflicts.append({
                            'claim_a_id': existing_id,
                            'claim_b_id': None,
                            'artifact_b_id': new_artifact['id'],
                            'similarity': round(len(shared_words) / max(1, len(set(existing_text.lower().split()))), 4),
                            'conflict_type': 'polarity_keyword',
                            'existing_confidence': existing_conf,
                        })
                        break

        return conflicts

    def resolve(self, project_id: str, conflict_pairs: list[dict]) -> list[dict]:
        """Apply dominance or escalation to each conflict pair.

        Resolution rules
        ----------------
        1. If the *existing* claim confidence is >= new artifact confidence + 0.1  →
           suppress the new artifact's claims (they inherit lower authority).
        2. If the *new* artifact confidence is >= existing confidence + 0.1  →
           suppress the existing claim.
        3. Near-tie  →  mark the existing claim 'contested', create a world-model
           question, log the event.

        Returns the list of log records created.
        """
        from backend.services.world_model import world_model_service

        log_records: list[dict] = []
        for pair in conflict_pairs:
            existing_id: str = pair['claim_a_id']
            artifact_b_id: str = pair['artifact_b_id']
            existing_conf: float = float(pair.get('existing_confidence', 0.5))

            # Get new artifact's confidence
            art_row = db.conn.execute(
                'SELECT confidence FROM artifacts WHERE id = ?',
                (artifact_b_id,),
            ).fetchone()
            new_conf: float = float(art_row['confidence']) if art_row else 0.5

            swing = new_conf - existing_conf

            if swing >= _POLARITY_CONFLICT_CONFIDENCE_SWING:
                # New artifact wins — suppress old claim
                resolution = 'suppressed_existing'
                self._set_claim_status(existing_id, 'suppressed')
            elif swing <= -_POLARITY_CONFLICT_CONFIDENCE_SWING:
                # Existing wins — mark incoming artifact claims as lower priority
                # (we flag the artifact as having contested downstream)
                resolution = 'suppressed_incoming'
                # Suppress any claims already written from the new artifact
                rows = db.conn.execute(
                    "SELECT id FROM claims WHERE artifact_id = ? AND status = 'active'",
                    (artifact_b_id,),
                ).fetchall()
                for r in rows:
                    self._set_claim_status(r['id'], 'suppressed')
            else:
                # Near-tie — escalate to world model
                resolution = 'contested'
                self._set_claim_status(existing_id, 'contested')
                question_text = (
                    f'Conflicting claims detected between existing claim '
                    f'(id={existing_id}) and new artifact (id={artifact_b_id}). '
                    'Which should take precedence?'
                )
                world_model_service.create_question(
                    project_id,
                    artifact_id=artifact_b_id,
                    content=question_text,
                    priority=3,
                )

            record = self._log_conflict(
                project_id=project_id,
                claim_a_id=existing_id,
                claim_b_id=artifact_b_id,
                conflict_type=pair.get('conflict_type', 'unknown'),
                resolution=resolution,
            )
            log_records.append(record)

        return log_records

    def unresolve(self, conflict_id: str) -> dict | None:
        """Restore both sides of a conflict back to 'active' status."""
        row = db.conn.execute(
            'SELECT * FROM conflict_log WHERE id = ?',
            (conflict_id,),
        ).fetchone()
        if not row:
            return None
        record = dict(row)
        # Restore originating claim
        self._set_claim_status(record['claim_a_id'], 'active')
        # Restore any suppressed claims from the incoming artifact
        rows = db.conn.execute(
            "SELECT id FROM claims WHERE artifact_id = ? AND status IN ('suppressed', 'contested')",
            (record['claim_b_id'],),
        ).fetchall()
        for r in rows:
            self._set_claim_status(r['id'], 'active')
        # Update log entry
        with db.transaction() as conn:
            conn.execute(
                "UPDATE conflict_log SET resolution = 'unresolved' WHERE id = ?",
                (conflict_id,),
            )
        return self.get_conflict(conflict_id)

    def list_conflicts(self, project_id: str) -> list[dict]:
        rows = db.conn.execute(
            'SELECT * FROM conflict_log WHERE project_id = ? ORDER BY created_at DESC',
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_conflict(self, conflict_id: str) -> dict | None:
        row = db.conn.execute(
            'SELECT * FROM conflict_log WHERE id = ?',
            (conflict_id,),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _set_claim_status(self, claim_id: str, status: str) -> None:
        db.conn.execute(
            'UPDATE claims SET status = ?, updated_at = ? WHERE id = ?',
            (status, now_ts(), claim_id),
        )
        db.conn.commit()

    def _log_conflict(
        self,
        project_id: str,
        claim_a_id: str,
        claim_b_id: str,
        conflict_type: str,
        resolution: str,
    ) -> dict:
        log_id = new_id()
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO conflict_log '
                '(id, project_id, claim_a_id, claim_b_id, conflict_type, resolution, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (log_id, project_id, claim_a_id, claim_b_id, conflict_type, resolution, ts),
            )
        return {
            'id': log_id,
            'project_id': project_id,
            'claim_a_id': claim_a_id,
            'claim_b_id': claim_b_id,
            'conflict_type': conflict_type,
            'resolution': resolution,
            'created_at': ts,
        }


conflict_resolution_service = ConflictResolutionService()
