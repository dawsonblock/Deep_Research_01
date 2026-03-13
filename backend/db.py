from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from backend.config import get_settings


class Database:
    def __init__(self) -> None:
        settings = get_settings()
        self.conn = sqlite3.connect(settings.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()
        self.run_migrations()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def init_schema(self) -> None:
        schema = [
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                current_milestone_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS milestones (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                success_conditions_json TEXT NOT NULL,
                status TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                label TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                rationale TEXT,
                metadata_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS execution_nodes (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                operator TEXT NOT NULL,
                status TEXT NOT NULL,
                retries INTEGER NOT NULL,
                is_stale INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS execution_deps (
                node_id TEXT NOT NULL,
                depends_on_node_id TEXT NOT NULL,
                PRIMARY KEY (node_id, depends_on_node_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS execution_inputs (
                node_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                PRIMARY KEY (node_id, artifact_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS execution_outputs (
                node_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                PRIMARY KEY (node_id, artifact_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                title TEXT NOT NULL,
                data_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                score REAL NOT NULL,
                source_task_id TEXT,
                source_node_id TEXT,
                version INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                lineage_id TEXT,
                revision_note TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS artifact_links (
                source_artifact_id TEXT NOT NULL,
                target_artifact_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                PRIMARY KEY (source_artifact_id, target_artifact_id, relation)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS validations (
                id TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                validator_name TEXT NOT NULL,
                status TEXT NOT NULL,
                score REAL NOT NULL,
                details_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                artifact_id TEXT,
                content TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                artifact_id TEXT,
                content TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS hypotheses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                artifact_id TEXT,
                statement TEXT NOT NULL,
                prediction TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS evidence_links (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                strength REAL NOT NULL,
                created_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                source_artifact_id TEXT,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS memory_links (
                memory_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                PRIMARY KEY (memory_id, artifact_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS artifact_embeddings (
                artifact_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                node_id TEXT,
                operator TEXT,
                status TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS experiment_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                plan_artifact_id TEXT NOT NULL,
                hypothesis_text TEXT,
                method TEXT NOT NULL,
                input_artifact_ids_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sandbox_sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                remote_sandbox_id TEXT,
                image TEXT NOT NULL,
                working_dir TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                last_used_at INTEGER NOT NULL,
                expires_at INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sandbox_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                session_id TEXT,
                run_kind TEXT NOT NULL,
                command_text TEXT,
                status TEXT NOT NULL,
                exit_code INTEGER,
                summary_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS sandbox_workspace_lineages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                lineage_id TEXT NOT NULL,
                latest_artifact_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                workspace_root TEXT NOT NULL,
                current_path TEXT NOT NULL,
                manifest_path TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE (session_id, lineage_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS repo_execution_profiles (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                language TEXT NOT NULL,
                framework TEXT NOT NULL,
                install_command TEXT,
                test_command TEXT NOT NULL,
                setup_commands_json TEXT NOT NULL,
                parser_hint TEXT,
                patch_strategy TEXT,
                metadata_json TEXT NOT NULL,
                source_artifact_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS conflict_log (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                claim_a_id TEXT NOT NULL,
                claim_b_id TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                resolution TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """,
        ]
        with self.transaction() as conn:
            for statement in schema:
                conn.execute(statement)

    def run_migrations(self) -> None:
        self._ensure_column('artifacts', 'lineage_id', 'TEXT')
        self._ensure_column('artifacts', 'revision_note', 'TEXT')
        with self.transaction() as conn:
            conn.execute('UPDATE artifacts SET lineage_id = COALESCE(lineage_id, id)')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_sandbox_workspace_lineages_session_lineage ON sandbox_workspace_lineages(session_id, lineage_id)')

    def _ensure_column(self, table: str, column: str, column_type: str) -> None:
        existing = {row['name'] for row in self.conn.execute(f'PRAGMA table_info({table})').fetchall()}
        if column not in existing:
            with self.transaction() as conn:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {column_type}')


db = Database()
