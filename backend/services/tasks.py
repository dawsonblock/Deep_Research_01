from __future__ import annotations

from backend.db import db
from backend.utils import dumps, loads, new_id, now_ts


class TaskService:
    def create(self, project_id: str, title: str, kind: str = 'analysis', priority: int = 0, rationale: str | None = None, metadata: dict | None = None) -> dict:
        task_id = new_id()
        ts = now_ts()
        metadata = metadata or {}
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO tasks (id, project_id, title, kind, status, priority, rationale, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (task_id, project_id, title, kind, 'pending', priority, rationale, dumps(metadata), ts, ts),
            )
        return self.get(task_id)

    def get(self, task_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return None
        task = dict(row)
        task['metadata'] = loads(task.pop('metadata_json'), {})
        return task

    def list(self, project_id: str, status: str | None = None) -> list[dict]:
        if status:
            rows = db.conn.execute('SELECT * FROM tasks WHERE project_id = ? AND status = ? ORDER BY priority DESC, created_at', (project_id, status)).fetchall()
        else:
            rows = db.conn.execute('SELECT * FROM tasks WHERE project_id = ? ORDER BY priority DESC, created_at', (project_id,)).fetchall()
        return [self.get(row['id']) for row in rows]

    def update_status(self, task_id: str, status: str) -> None:
        db.conn.execute('UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?', (status, now_ts(), task_id))
        db.conn.commit()


task_service = TaskService()
