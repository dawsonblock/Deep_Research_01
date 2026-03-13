from __future__ import annotations

from backend.db import db
from backend.utils import dumps, loads, new_id, now_ts


class ProjectStateService:
    def create_project(self, name: str, goal: str) -> dict:
        project_id = new_id()
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO projects (id, name, goal, status, current_milestone_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (project_id, name, goal, 'active', None, ts, ts),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        return dict(row) if row else None

    def add_milestone(self, project_id: str, title: str, success_conditions: list[str]) -> dict:
        milestone_id = new_id()
        ts = now_ts()
        position = db.conn.execute('SELECT COALESCE(MAX(position), -1) + 1 FROM milestones WHERE project_id = ?', (project_id,)).fetchone()[0]
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO milestones (id, project_id, title, success_conditions_json, status, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (milestone_id, project_id, title, dumps(success_conditions), 'pending', position, ts, ts),
            )
            project = self.get_project(project_id)
            if project and not project['current_milestone_id']:
                conn.execute('UPDATE projects SET current_milestone_id = ?, updated_at = ? WHERE id = ?', (milestone_id, ts, project_id))
        return self.get_milestone(milestone_id)

    def get_milestone(self, milestone_id: str) -> dict | None:
        row = db.conn.execute('SELECT * FROM milestones WHERE id = ?', (milestone_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item['success_conditions'] = loads(item.pop('success_conditions_json'), [])
        item['progress'] = self._milestone_progress(item)
        return item

    def list_milestones(self, project_id: str) -> list[dict]:
        rows = db.conn.execute('SELECT * FROM milestones WHERE project_id = ? ORDER BY position', (project_id,)).fetchall()
        return [self.get_milestone(row['id']) for row in rows]

    def checkpoint(self, project_id: str, label: str) -> dict:
        self.evaluate_milestones(project_id)
        snapshot = {
            'project': self.get_project(project_id),
            'milestones': self.list_milestones(project_id),
            'task_count': db.conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id = ?', (project_id,)).fetchone()[0],
            'artifact_count': db.conn.execute('SELECT COUNT(*) FROM artifacts WHERE project_id = ?', (project_id,)).fetchone()[0],
            'memory_count': db.conn.execute('SELECT COUNT(*) FROM memories WHERE project_id = ?', (project_id,)).fetchone()[0],
            'experiment_run_count': db.conn.execute('SELECT COUNT(*) FROM experiment_runs WHERE project_id = ?', (project_id,)).fetchone()[0],
            'sandbox_session_count': db.conn.execute('SELECT COUNT(*) FROM sandbox_sessions WHERE project_id = ?', (project_id,)).fetchone()[0],
            'sandbox_run_count': db.conn.execute('SELECT COUNT(*) FROM sandbox_runs WHERE project_id = ?', (project_id,)).fetchone()[0],
            'sandbox_workspace_lineage_count': db.conn.execute('SELECT COUNT(*) FROM sandbox_workspace_lineages WHERE project_id = ?', (project_id,)).fetchone()[0],
            'repo_profile_count': db.conn.execute('SELECT COUNT(*) FROM repo_execution_profiles WHERE project_id = ?', (project_id,)).fetchone()[0],
        }
        checkpoint_id = new_id()
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO checkpoints (id, project_id, label, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)',
                (checkpoint_id, project_id, label, dumps(snapshot), ts),
            )
        return {'id': checkpoint_id, 'label': label, 'snapshot': snapshot, 'created_at': ts}

    def summarize(self, project_id: str) -> dict:
        self.evaluate_milestones(project_id)
        project = self.get_project(project_id)
        if not project:
            raise ValueError('project not found')
        summary = {
            'project': project,
            'milestones': self.list_milestones(project_id),
            'tasks': {
                'pending': db.conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = ?', (project_id, 'pending')).fetchone()[0],
                'running': db.conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = ?', (project_id, 'running')).fetchone()[0],
                'done': db.conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = ?', (project_id, 'done')).fetchone()[0],
                'failed': db.conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = ?', (project_id, 'failed')).fetchone()[0],
            },
            'artifacts': {
                'count': db.conn.execute('SELECT COUNT(*) FROM artifacts WHERE project_id = ?', (project_id,)).fetchone()[0],
                'avg_score': db.conn.execute('SELECT COALESCE(AVG(score), 0) FROM artifacts WHERE project_id = ?', (project_id,)).fetchone()[0],
            },
            'world_model': {
                'claims': db.conn.execute('SELECT COUNT(*) FROM claims WHERE project_id = ?', (project_id,)).fetchone()[0],
                'questions': db.conn.execute('SELECT COUNT(*) FROM questions WHERE project_id = ?', (project_id,)).fetchone()[0],
                'hypotheses': db.conn.execute('SELECT COUNT(*) FROM hypotheses WHERE project_id = ?', (project_id,)).fetchone()[0],
            },
            'memory_count': db.conn.execute('SELECT COUNT(*) FROM memories WHERE project_id = ?', (project_id,)).fetchone()[0],
            'experiment_run_count': db.conn.execute('SELECT COUNT(*) FROM experiment_runs WHERE project_id = ?', (project_id,)).fetchone()[0],
            'sandbox': {
                'session_count': db.conn.execute('SELECT COUNT(*) FROM sandbox_sessions WHERE project_id = ?', (project_id,)).fetchone()[0],
                'repo_profile_count': db.conn.execute('SELECT COUNT(*) FROM repo_execution_profiles WHERE project_id = ?', (project_id,)).fetchone()[0],
                'active_session_count': db.conn.execute('SELECT COUNT(*) FROM sandbox_sessions WHERE project_id = ? AND status IN (?, ?)', (project_id, 'running', 'paused')).fetchone()[0],
                'run_count': db.conn.execute('SELECT COUNT(*) FROM sandbox_runs WHERE project_id = ?', (project_id,)).fetchone()[0],
                'workspace_lineage_count': db.conn.execute('SELECT COUNT(*) FROM sandbox_workspace_lineages WHERE project_id = ?', (project_id,)).fetchone()[0],
            },
        }
        return summary

    def evaluate_milestones(self, project_id: str) -> list[dict]:
        milestone_rows = db.conn.execute('SELECT * FROM milestones WHERE project_id = ? ORDER BY position', (project_id,)).fetchall()
        first_incomplete = None
        for row in milestone_rows:
            milestone = dict(row)
            milestone['success_conditions'] = loads(milestone.pop('success_conditions_json'), [])
            progress = self._milestone_progress(milestone)
            new_status = 'done' if progress['complete'] else ('running' if progress['matched_conditions'] > 0 else 'pending')
            if row['status'] != new_status:
                db.conn.execute('UPDATE milestones SET status = ?, updated_at = ? WHERE id = ?', (new_status, now_ts(), row['id']))
            if new_status != 'done' and first_incomplete is None:
                first_incomplete = row['id']
        project = self.get_project(project_id)
        if project:
            db.conn.execute('UPDATE projects SET current_milestone_id = ?, updated_at = ? WHERE id = ?', (first_incomplete, now_ts(), project_id))
            db.conn.commit()
        return self.list_milestones(project_id)

    def _milestone_progress(self, milestone: dict) -> dict:
        project_id = milestone['project_id']
        conditions = milestone.get('success_conditions', [])
        matched = 0
        details = []
        for condition in conditions:
            ok, detail = self._evaluate_condition(project_id, condition)
            matched += 1 if ok else 0
            details.append({'condition': condition, 'met': ok, 'detail': detail})
        return {
            'complete': bool(conditions) and matched == len(conditions),
            'matched_conditions': matched,
            'total_conditions': len(conditions),
            'details': details,
        }

    def _evaluate_condition(self, project_id: str, condition: str) -> tuple[bool, dict]:
        if condition.startswith('artifact_type:'):
            parts = condition.split(':')
            artifact_type = parts[1]
            min_count = int(parts[2]) if len(parts) > 2 else 1
            count = db.conn.execute('SELECT COUNT(*) FROM artifacts WHERE project_id = ? AND type = ? AND status = ?', (project_id, artifact_type, 'pass')).fetchone()[0]
            return count >= min_count, {'count': count, 'min_count': min_count, 'artifact_type': artifact_type}
        if condition.startswith('avg_score>='):
            threshold = float(condition.split('>=', 1)[1])
            avg_score = db.conn.execute('SELECT COALESCE(AVG(score), 0) FROM artifacts WHERE project_id = ?', (project_id,)).fetchone()[0]
            return avg_score >= threshold, {'avg_score': avg_score, 'threshold': threshold}
        if condition.startswith('task_status:'):
            _, status, min_count_s = condition.split(':')
            min_count = int(min_count_s)
            count = db.conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id = ? AND status = ?', (project_id, status)).fetchone()[0]
            return count >= min_count, {'count': count, 'min_count': min_count, 'status': status}
        if condition.startswith('world_model:'):
            _, entity, min_count_s = condition.split(':')
            table = {'claims': 'claims', 'questions': 'questions', 'hypotheses': 'hypotheses'}[entity]
            min_count = int(min_count_s)
            count = db.conn.execute(f'SELECT COUNT(*) FROM {table} WHERE project_id = ?', (project_id,)).fetchone()[0]
            return count >= min_count, {'count': count, 'min_count': min_count, 'entity': entity}
        if condition.startswith('sandbox_sessions:'):
            min_count = int(condition.split(':',1)[1])
            count = db.conn.execute('SELECT COUNT(*) FROM sandbox_sessions WHERE project_id = ?', (project_id,)).fetchone()[0]
            return count >= min_count, {'count': count, 'min_count': min_count, 'entity': 'sandbox_sessions'}
        if condition.startswith('sandbox_workspace_lineages:'):
            min_count = int(condition.split(':',1)[1])
            count = db.conn.execute('SELECT COUNT(*) FROM sandbox_workspace_lineages WHERE project_id = ?', (project_id,)).fetchone()[0]
            return count >= min_count, {'count': count, 'min_count': min_count, 'entity': 'sandbox_workspace_lineages'}
        return False, {'reason': 'unsupported condition format'}


project_state_service = ProjectStateService()
