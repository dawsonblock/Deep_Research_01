from __future__ import annotations

from backend.db import db
from backend.services.embeddings import embedding_service
from backend.services.memory import memory_service
from backend.services.project_state import project_state_service
from backend.services.validation import validation_service
from backend.services.world_model import world_model_service
from backend.utils import dumps, loads, new_id, now_ts


class ArtifactService:
    def create(
        self,
        project_id: str,
        artifact_type: str,
        title: str,
        data: dict,
        confidence: float = 0.5,
        source_task_id: str | None = None,
        source_node_id: str | None = None,
        parent_artifact_ids: list[str] | None = None,
        revision_of_artifact_id: str | None = None,
        lineage_id: str | None = None,
        revision_note: str | None = None,
    ) -> dict:
        artifact_id = new_id()
        ts = now_ts()
        status, validator_score, details = validation_service.validate(artifact_type, data)
        score = round((validator_score * 0.7) + (confidence * 0.3), 4)
        version = 1
        resolved_lineage_id = lineage_id
        if revision_of_artifact_id:
            base = self.get(revision_of_artifact_id)
            if not base:
                raise ValueError(f'base artifact not found: {revision_of_artifact_id}')
            version = int(base.get('version', 1)) + 1
            resolved_lineage_id = base.get('lineage_id') or base['id']
            if not revision_note:
                revision_note = f'revision from version {base.get("version", 1)}'
            if not title:
                title = base['title']
        if not resolved_lineage_id:
            resolved_lineage_id = artifact_id
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO artifacts (id, project_id, type, status, title, data_json, confidence, score, source_task_id, source_node_id, version, created_at, updated_at, lineage_id, revision_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    artifact_id,
                    project_id,
                    artifact_type,
                    status,
                    title,
                    dumps(data),
                    confidence,
                    score,
                    source_task_id,
                    source_node_id,
                    version,
                    ts,
                    ts,
                    resolved_lineage_id,
                    revision_note,
                ),
            )
            conn.execute(
                'INSERT INTO validations (id, artifact_id, validator_name, status, score, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (new_id(), artifact_id, f'{artifact_type}_validator', status, validator_score, dumps(details), ts),
            )
            for parent_id in parent_artifact_ids or []:
                conn.execute(
                    'INSERT OR IGNORE INTO artifact_links (source_artifact_id, target_artifact_id, relation) VALUES (?, ?, ?)',
                    (parent_id, artifact_id, 'derived_to'),
                )
            if revision_of_artifact_id:
                conn.execute(
                    'INSERT OR IGNORE INTO artifact_links (source_artifact_id, target_artifact_id, relation) VALUES (?, ?, ?)',
                    (revision_of_artifact_id, artifact_id, 'supersedes'),
                )
        artifact = self.get(artifact_id)
        embedding_service.upsert_artifact_embedding(artifact_id, self.to_search_text(artifact))
        world_model_service.update_from_artifact(artifact)
        if status == 'pass' and score >= 0.45:
            memory_service.create_from_artifact(artifact)
        project_state_service.evaluate_milestones(project_id)
        return artifact

    def create_revision(
        self,
        base_artifact_id: str,
        title: str,
        data: dict,
        confidence: float = 0.5,
        source_task_id: str | None = None,
        source_node_id: str | None = None,
        parent_artifact_ids: list[str] | None = None,
        revision_note: str | None = None,
    ) -> dict:
        base = self.get(base_artifact_id)
        if not base:
            raise ValueError('base artifact not found')
        return self.create(
            project_id=base['project_id'],
            artifact_type=base['type'],
            title=title or base['title'],
            data=data,
            confidence=confidence,
            source_task_id=source_task_id,
            source_node_id=source_node_id,
            parent_artifact_ids=(parent_artifact_ids or []) + [base_artifact_id],
            revision_of_artifact_id=base_artifact_id,
            revision_note=revision_note,
        )

    def to_search_text(self, artifact: dict) -> str:
        parts = [artifact['type'], artifact['title']]
        data = artifact['data']
        if artifact.get('revision_note'):
            parts.append(str(artifact['revision_note']))
        if 'text' in data:
            parts.append(str(data['text']))
        for key in ('items', 'components', 'issues', 'tasks', 'steps', 'notes', 'targets', 'goals', 'file_patches', 'setup_commands', 'detected_files', 'file_tree'):
            if key in data and isinstance(data[key], list):
                if key == 'file_patches':
                    parts.extend(str(item.get('path', '')) + ' ' + str(item.get('reason', '')) for item in data[key] if isinstance(item, dict))
                else:
                    parts.extend(map(str, data[key]))
        if 'snapshots' in data and isinstance(data['snapshots'], dict):
            parts.extend(list(data['snapshots'].keys())[:20])
        if 'patch_text' in data:
            parts.append(str(data['patch_text'])[:4000])
        if 'metrics' in data and isinstance(data['metrics'], dict):
            parts.extend(f'{k}:{v}' for k, v in data['metrics'].items())
        if 'verdict' in data:
            parts.append(str(data['verdict']))
        if 'method' in data:
            parts.append(str(data['method']))
        return ' '.join(parts)

    def get(self, artifact_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM artifacts WHERE id = ?', (artifact_id,)).fetchone()
        if not row:
            return None
        artifact = dict(row)
        artifact['data'] = loads(artifact.pop('data_json'), {})
        artifact['validations'] = self.validations(artifact_id)
        artifact['parents'] = self.parents(artifact_id)
        artifact['children'] = self.children(artifact_id)
        return artifact

    def validations(self, artifact_id: str) -> list[dict]:
        rows = db.conn.execute('SELECT * FROM validations WHERE artifact_id = ? ORDER BY created_at', (artifact_id,)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item['details'] = loads(item.pop('details_json'), {})
            items.append(item)
        return items

    def list(self, project_id: str, artifact_type: str | None = None) -> list[dict]:
        if artifact_type:
            rows = db.conn.execute('SELECT id FROM artifacts WHERE project_id = ? AND type = ? ORDER BY created_at DESC', (project_id, artifact_type)).fetchall()
        else:
            rows = db.conn.execute('SELECT id FROM artifacts WHERE project_id = ? ORDER BY created_at DESC', (project_id,)).fetchall()
        return [self.get(row['id']) for row in rows]

    def lineage(self, lineage_id: str) -> list[dict]:
        rows = db.conn.execute(
            'SELECT id FROM artifacts WHERE lineage_id = ? ORDER BY version ASC, created_at ASC',
            (lineage_id,),
        ).fetchall()
        return [self.get(row['id']) for row in rows]

    def latest_for_lineage(self, lineage_id: str) -> dict | None:
        row = db.conn.execute(
            'SELECT id FROM artifacts WHERE lineage_id = ? ORDER BY version DESC, created_at DESC LIMIT 1',
            (lineage_id,),
        ).fetchone()
        return self.get(row['id']) if row else None

    def latest_by_type(self, project_id: str, artifact_type: str) -> dict | None:
        row = db.conn.execute(
            'SELECT id FROM artifacts WHERE project_id = ? AND type = ? ORDER BY created_at DESC LIMIT 1',
            (project_id, artifact_type),
        ).fetchone()
        return self.get(row['id']) if row else None

    def parents(self, artifact_id: str) -> list[dict]:
        rows = db.conn.execute(
            'SELECT source_artifact_id, relation FROM artifact_links WHERE target_artifact_id = ? ORDER BY relation, source_artifact_id',
            (artifact_id,),
        ).fetchall()
        return [
            {'artifact_id': row['source_artifact_id'], 'relation': row['relation']}
            for row in rows
        ]

    def children(self, artifact_id: str) -> list[dict]:
        rows = db.conn.execute(
            'SELECT target_artifact_id, relation FROM artifact_links WHERE source_artifact_id = ? ORDER BY relation, target_artifact_id',
            (artifact_id,),
        ).fetchall()
        return [
            {'artifact_id': row['target_artifact_id'], 'relation': row['relation']}
            for row in rows
        ]

    def output_artifacts_for_node(self, node_id: str) -> list[dict]:
        rows = db.conn.execute('SELECT artifact_id FROM execution_outputs WHERE node_id = ?', (node_id,)).fetchall()
        return [self.get(row['artifact_id']) for row in rows]

    def merge_artifacts(
        self,
        project_id: str,
        artifact_type: str,
        title: str,
        data: dict,
        source_artifact_ids: list[str],
        confidence: float = 0.6,
        revision_note: str | None = None,
    ) -> dict:
        """Create a single artifact that branches from multiple parent lineages.

        All source artifacts are recorded with relation='merged_from' in
        artifact_links.  The new artifact inherits lineage_id from whichever
        source has the highest confidence score so the primary lineage chain
        remains unbroken.
        """
        if not source_artifact_ids:
            raise ValueError('source_artifact_ids must not be empty')

        # Pick the dominant (highest-confidence) source to inherit lineage from
        dominant: dict | None = None
        for sid in source_artifact_ids:
            src = self.get(sid)
            if src and (dominant is None or float(src.get('confidence', 0)) > float(dominant.get('confidence', 0))):
                dominant = src

        if not dominant:
            raise ValueError('none of the source artifact ids could be found')

        inherited_lineage_id = dominant.get('lineage_id') or dominant['id']
        note = revision_note or f'Merged from {len(source_artifact_ids)} sources: {", ".join(source_artifact_ids)}'

        artifact_id = new_id()
        ts = now_ts()
        from backend.services.validation import validation_service
        status, validator_score, details = validation_service.validate(artifact_type, data)
        score = round((validator_score * 0.7) + (confidence * 0.3), 4)

        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO artifacts (id, project_id, type, status, title, data_json, confidence, score, source_task_id, source_node_id, version, created_at, updated_at, lineage_id, revision_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    artifact_id,
                    project_id,
                    artifact_type,
                    status,
                    title,
                    dumps(data),
                    confidence,
                    score,
                    None,
                    None,
                    int(dominant.get('version', 1)) + 1,
                    ts,
                    ts,
                    inherited_lineage_id,
                    note,
                ),
            )
            conn.execute(
                'INSERT INTO validations (id, artifact_id, validator_name, status, score, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (new_id(), artifact_id, f'{artifact_type}_validator', status, validator_score, dumps(details), ts),
            )
            for sid in source_artifact_ids:
                conn.execute(
                    'INSERT OR IGNORE INTO artifact_links (source_artifact_id, target_artifact_id, relation) VALUES (?, ?, ?)',
                    (sid, artifact_id, 'merged_from'),
                )

        artifact = self.get(artifact_id)
        embedding_service.upsert_artifact_embedding(artifact_id, self.to_search_text(artifact))
        world_model_service.update_from_artifact(artifact)
        if status == 'pass' and score >= 0.45:
            memory_service.create_from_artifact(artifact)
        project_state_service.evaluate_milestones(project_id)
        return artifact


artifact_service = ArtifactService()
