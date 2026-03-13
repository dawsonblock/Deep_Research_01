from __future__ import annotations

import asyncio
import concurrent.futures
import importlib.util
import json
import re
import shlex
import threading
from datetime import timedelta
from typing import Any

from backend.config import get_settings
from backend.db import db
from backend.services.artifacts import artifact_service
from backend.services.repo_parsers import repo_benchmark_parser_service
from backend.services.repo_profiles import repo_profile_service
from backend.utils import dumps, loads, new_id, now_ts


class SandboxHarnessService:
    def __init__(self) -> None:
        settings = get_settings()
        self.domain = settings.opensandbox_domain
        self.api_key = settings.opensandbox_api_key
        self.protocol = settings.opensandbox_protocol
        self.timeout_seconds = settings.opensandbox_timeout_seconds
        self.default_image = settings.opensandbox_default_image
        self.default_python_image = settings.opensandbox_python_image
        self.default_workdir = settings.opensandbox_default_workdir
        self.default_repo_dir = settings.opensandbox_repo_dir
        self.default_ttl_minutes = settings.opensandbox_session_ttl_minutes
        self.use_server_proxy = settings.opensandbox_use_server_proxy
        self.enabled = settings.opensandbox_enabled

    def sdk_installed(self) -> bool:
        return importlib.util.find_spec('opensandbox') is not None

    def available(self) -> bool:
        return bool(self.enabled and self.domain and self.api_key and self.sdk_installed())

    def status(self) -> dict[str, Any]:
        session_count = db.conn.execute('SELECT COUNT(*) FROM sandbox_sessions').fetchone()[0]
        run_count = db.conn.execute('SELECT COUNT(*) FROM sandbox_runs').fetchone()[0]
        return {
            'enabled': self.enabled,
            'configured': bool(self.domain and self.api_key),
            'sdk_installed': self.sdk_installed(),
            'available': self.available(),
            'domain': self.domain,
            'default_image': self.default_image,
            'default_python_image': self.default_python_image,
            'default_workdir': self.default_workdir,
            'default_repo_dir': self.default_repo_dir,
            'default_ttl_minutes': self.default_ttl_minutes,
            'use_server_proxy': self.use_server_proxy,
            'session_count': session_count,
            'run_count': run_count,
        }

    def _connection_config(self):
        from opensandbox.config import ConnectionConfig

        return ConnectionConfig(
            domain=self.domain,
            api_key=self.api_key,
            protocol=self.protocol,
            use_server_proxy=self.use_server_proxy,
            request_timeout=timedelta(seconds=self.timeout_seconds),
        )

    def list_sessions(self, project_id: str) -> list[dict[str, Any]]:
        rows = db.conn.execute('SELECT * FROM sandbox_sessions WHERE project_id = ? ORDER BY created_at DESC', (project_id,)).fetchall()
        return [self._row_to_session(r) for r in rows]

    def list_runs(self, session_id: str) -> list[dict[str, Any]]:
        rows = db.conn.execute('SELECT * FROM sandbox_runs WHERE session_id = ? ORDER BY created_at DESC', (session_id,)).fetchall()
        return [self._row_to_run(r) for r in rows]

    def list_workspace_lineages(self, session_id: str) -> list[dict[str, Any]]:
        rows = db.conn.execute('SELECT * FROM sandbox_workspace_lineages WHERE session_id = ? ORDER BY updated_at DESC, created_at DESC', (session_id,)).fetchall()
        return [self._row_to_workspace_lineage(r) for r in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = db.conn.execute('SELECT * FROM sandbox_sessions WHERE id = ?', (session_id,)).fetchone()
        return self._row_to_session(row) if row else None

    def _row_to_session(self, row) -> dict[str, Any]:
        item = dict(row)
        item['metadata'] = loads(item.pop('metadata_json'), {})
        return item

    def _row_to_run(self, row) -> dict[str, Any]:
        item = dict(row)
        item['summary'] = loads(item.pop('summary_json'), {})
        return item

    def _row_to_workspace_lineage(self, row) -> dict[str, Any]:
        return dict(row)

    def _safe_slug(self, value: str, max_len: int = 48) -> str:
        slug = re.sub(r'[^a-zA-Z0-9._-]+', '-', str(value).strip().lower()).strip('-')
        return (slug or 'artifact')[:max_len]

    def _run_async(self, coro):
        """Run an async coroutine from sync code, safe even inside a running event loop (e.g. FastAPI)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            result_box: list = [None]
            exc_box: list = [None]
            def _target():
                try:
                    result_box[0] = asyncio.run(coro)
                except Exception as exc:
                    exc_box[0] = exc
            thread = threading.Thread(target=_target, daemon=True)
            thread.start()
            thread.join(timeout=self.timeout_seconds + 60)
            if exc_box[0] is not None:
                raise exc_box[0]
            return result_box[0]
        return asyncio.run(coro)

    def _upsert_workspace_lineage(self, session_id: str, project_id: str, artifact: dict, base_path: str) -> dict[str, Any]:
        lineage_id = artifact.get('lineage_id') or artifact['id']
        existing = db.conn.execute('SELECT * FROM sandbox_workspace_lineages WHERE session_id = ? AND lineage_id = ?', (session_id, lineage_id)).fetchone()
        slug = self._safe_slug(f"{artifact.get('type', 'artifact')}-{artifact.get('title', 'artifact')}")
        workspace_root = (dict(existing)['workspace_root'] if existing else f"{base_path.rstrip('/')}/{artifact.get('type', 'artifact')}/{slug}-{lineage_id[:8]}")
        current_path = f"{workspace_root}/current.json"
        manifest_path = f"{workspace_root}/manifest.json"
        ts = now_ts()
        if existing:
            db.conn.execute(
                'UPDATE sandbox_workspace_lineages SET latest_artifact_id = ?, artifact_type = ?, workspace_root = ?, current_path = ?, manifest_path = ?, updated_at = ? WHERE id = ?',
                (artifact['id'], artifact.get('type', 'artifact'), workspace_root, current_path, manifest_path, ts, existing['id']),
            )
            db.conn.commit()
            row = db.conn.execute('SELECT * FROM sandbox_workspace_lineages WHERE id = ?', (existing['id'],)).fetchone()
        else:
            mapping_id = new_id()
            db.conn.execute(
                'INSERT INTO sandbox_workspace_lineages (id, session_id, project_id, lineage_id, latest_artifact_id, artifact_type, workspace_root, current_path, manifest_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (mapping_id, session_id, project_id, lineage_id, artifact['id'], artifact.get('type', 'artifact'), workspace_root, current_path, manifest_path, ts, ts),
            )
            db.conn.commit()
            row = db.conn.execute('SELECT * FROM sandbox_workspace_lineages WHERE id = ?', (mapping_id,)).fetchone()
        return self._row_to_workspace_lineage(row)

    def _lineage_files(self, artifact: dict, mapping: dict[str, Any]) -> list[dict[str, Any]]:
        version = int(artifact.get('version', 1) or 1)
        version_path = f"{mapping['workspace_root']}/versions/v{version}.json"
        manifest = {
            'lineage_id': artifact.get('lineage_id') or artifact['id'],
            'latest_artifact_id': artifact['id'],
            'artifact_type': artifact.get('type'),
            'title': artifact.get('title'),
            'version': version,
            'revision_note': artifact.get('revision_note'),
            'workspace_root': mapping['workspace_root'],
            'current_path': mapping['current_path'],
            'version_path': version_path,
            'updated_at': now_ts(),
        }
        payload = {
            'artifact': artifact,
            'lineage': artifact_service.lineage(artifact.get('lineage_id') or artifact['id']),
            'mapping': manifest,
        }
        return [
            {'path': mapping['current_path'], 'data': dumps(payload), 'mode': 0o644},
            {'path': version_path, 'data': dumps(payload), 'mode': 0o644},
            {'path': mapping['manifest_path'], 'data': dumps(manifest), 'mode': 0o644},
        ]

    def create_session(
        self,
        project_id: str,
        image: str | None = None,
        working_dir: str | None = None,
        metadata: dict[str, Any] | None = None,
        ttl_minutes: int | None = None,
    ) -> dict[str, Any]:
        session_id = new_id()
        ts = now_ts()
        ttl_minutes = ttl_minutes or self.default_ttl_minutes
        expires_at = ts + ttl_minutes * 60 if ttl_minutes else None
        image = image or self.default_image
        working_dir = working_dir or self.default_workdir
        metadata = dict(metadata or {})
        metadata.setdefault('created_via', 'api')
        remote_sandbox_id = None
        status = 'stub'
        if self.available():
            try:
                remote_sandbox_id = self._run_async(self._remote_create_session(image=image, working_dir=working_dir, metadata=metadata, ttl_minutes=ttl_minutes))
                status = 'running'
            except Exception as exc:
                metadata['create_error'] = str(exc)
                status = 'error'
        elif self.enabled:
            status = 'configured_unavailable'
            metadata['create_error'] = 'OpenSandbox not fully configured or SDK missing'
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO sandbox_sessions (id, project_id, provider, remote_sandbox_id, image, working_dir, status, metadata_json, created_at, updated_at, last_used_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (session_id, project_id, 'opensandbox', remote_sandbox_id, image, working_dir, status, dumps(metadata), ts, ts, ts, expires_at),
            )
        return self.get_session(session_id)

    def ensure_project_session(
        self,
        project_id: str,
        image: str | None = None,
        working_dir: str | None = None,
        metadata: dict[str, Any] | None = None,
        ttl_minutes: int | None = None,
    ) -> dict[str, Any]:
        row = db.conn.execute(
            'SELECT id FROM sandbox_sessions WHERE project_id = ? AND status IN (?, ?) ORDER BY last_used_at DESC, created_at DESC LIMIT 1',
            (project_id, 'running', 'paused'),
        ).fetchone()
        if row:
            return self.get_session(row['id'])
        return self.create_session(project_id, image=image, working_dir=working_dir, metadata=metadata, ttl_minutes=ttl_minutes)

    def pause_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            raise ValueError('sandbox session not found')
        metadata = dict(session.get('metadata') or {})
        if session.get('remote_sandbox_id') and self.available() and session['status'] == 'running':
            try:
                self._run_async(self._remote_pause(session['remote_sandbox_id']))
                status = 'paused'
            except Exception as exc:
                metadata['pause_error'] = str(exc)
                status = 'error'
        else:
            status = 'paused' if session['status'] != 'killed' else session['status']
        db.conn.execute('UPDATE sandbox_sessions SET status = ?, metadata_json = ?, updated_at = ?, last_used_at = ? WHERE id = ?', (status, dumps(metadata), now_ts(), now_ts(), session_id))
        db.conn.commit()
        return self.get_session(session_id)

    def resume_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            raise ValueError('sandbox session not found')
        metadata = dict(session.get('metadata') or {})
        status = 'running'
        if session.get('remote_sandbox_id') and self.available():
            try:
                self._run_async(self._remote_resume(session['remote_sandbox_id']))
            except Exception as exc:
                metadata['resume_error'] = str(exc)
                status = 'error'
        db.conn.execute('UPDATE sandbox_sessions SET status = ?, metadata_json = ?, updated_at = ?, last_used_at = ? WHERE id = ?', (status, dumps(metadata), now_ts(), now_ts(), session_id))
        db.conn.commit()
        return self.get_session(session_id)

    def renew_session(self, session_id: str, ttl_minutes: int | None = None) -> dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            raise ValueError('sandbox session not found')
        ttl_minutes = ttl_minutes or self.default_ttl_minutes
        metadata = dict(session.get('metadata') or {})
        if session.get('remote_sandbox_id') and self.available():
            try:
                self._run_async(self._remote_renew(session['remote_sandbox_id'], ttl_minutes))
            except Exception as exc:
                metadata['renew_error'] = str(exc)
        expires_at = now_ts() + ttl_minutes * 60
        db.conn.execute('UPDATE sandbox_sessions SET metadata_json = ?, expires_at = ?, updated_at = ?, last_used_at = ? WHERE id = ?', (dumps(metadata), expires_at, now_ts(), now_ts(), session_id))
        db.conn.commit()
        return self.get_session(session_id)

    def kill_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            raise ValueError('sandbox session not found')
        metadata = dict(session.get('metadata') or {})
        if session.get('remote_sandbox_id') and self.available() and session['status'] != 'killed':
            try:
                self._run_async(self._remote_kill(session['remote_sandbox_id']))
            except Exception as exc:
                metadata['kill_error'] = str(exc)
        db.conn.execute('UPDATE sandbox_sessions SET status = ?, metadata_json = ?, updated_at = ?, last_used_at = ? WHERE id = ?', ('killed', dumps(metadata), now_ts(), now_ts(), session_id))
        db.conn.commit()
        return self.get_session(session_id)

    def materialize_artifacts(self, project_id: str, session_id: str, artifact_ids: list[str], base_path: str = '/workspace/artifacts') -> dict[str, Any]:
        session = self.get_session(session_id)
        if not session or session['project_id'] != project_id:
            raise ValueError('sandbox session not found for project')
        file_entries: list[dict[str, Any]] = []
        lineage_mappings: list[dict[str, Any]] = []
        for artifact_id in artifact_ids:
            artifact = artifact_service.get(artifact_id)
            if not artifact:
                continue
            latest = artifact_service.latest_for_lineage(artifact.get('lineage_id') or artifact['id']) or artifact
            mapping = self._upsert_workspace_lineage(session_id, project_id, latest, base_path)
            lineage_mappings.append(mapping)
            file_entries.extend(self._lineage_files(latest, mapping))
        deduped = []
        seen_paths = set()
        for entry in file_entries:
            if entry['path'] in seen_paths:
                continue
            seen_paths.add(entry['path'])
            deduped.append(entry)
        result = {
            'status': 'prepared',
            'session_id': session_id,
            'file_count': len(deduped),
            'paths': [f['path'] for f in deduped],
            'workspace_lineages': lineage_mappings,
        }
        if deduped and session.get('remote_sandbox_id') and self.available() and session['status'] in {'running', 'paused'}:
            try:
                self._run_async(self._write_files_to_session(session, deduped))
                result['status'] = 'written'
            except Exception as exc:
                result['status'] = 'write_failed'
                result['error'] = str(exc)
        self._record_run(project_id, session_id, 'materialize', f'materialize:{len(deduped)}', result, exit_code=0 if result['status'] in {'prepared', 'written'} else 1)
        return result

    def sync_workspace_lineages(self, project_id: str, session_id: str, base_path: str = '/workspace/artifacts', artifact_type: str | None = None) -> dict[str, Any]:
        artifacts = artifact_service.list(project_id, artifact_type=artifact_type)
        latest_by_lineage = {}
        for artifact in artifacts:
            lineage_id = artifact.get('lineage_id') or artifact['id']
            existing = latest_by_lineage.get(lineage_id)
            if not existing or int(artifact.get('version', 1) or 1) > int(existing.get('version', 1) or 1):
                latest_by_lineage[lineage_id] = artifact
        return self.materialize_artifacts(project_id, session_id, [a['id'] for a in latest_by_lineage.values()], base_path=base_path)

    def run_plan(self, project_id: str, plan_data: dict[str, Any], input_artifacts: list[dict]) -> dict[str, Any]:
        job = dict(plan_data.get('job') or {})
        if not job:
            return {'status': 'no_job', 'runner': 'none', 'reason': 'experiment plan did not define a sandbox job'}
        if job.get('type') == 'patch_test':
            artifact_ids = [a['id'] for a in input_artifacts if a]
            patch_artifact_ids = [a['id'] for a in input_artifacts if a and a.get('type') == 'code_patch']
            return self.run_patch_test_loop(
                project_id=project_id,
                session_id=job.get('session_id'),
                repo_url=str(job.get('repo_url') or ''),
                repo_ref=job.get('repo_ref'),
                install_command=job.get('install_command'),
                test_command=str(job.get('test_command') or 'pytest -q'),
                image=job.get('image'),
                reuse_project_session=bool(job.get('reuse_project_session', True)),
                artifact_ids=artifact_ids,
                patch_artifact_ids=patch_artifact_ids,
                base_path=str(job.get('artifact_base_path') or '/workspace/artifacts'),
                create_result_artifact=False,
                repo_profile_id=job.get('repo_profile_id'),
            )
        if job.get('type') == 'repo_test':
            artifact_ids = [a['id'] for a in input_artifacts if a]
            return self.run_repo_evaluation(
                project_id=project_id,
                session_id=job.get('session_id'),
                repo_url=str(job.get('repo_url') or ''),
                repo_ref=job.get('repo_ref'),
                install_command=job.get('install_command'),
                test_command=str(job.get('test_command') or 'pytest -q'),
                image=job.get('image'),
                reuse_project_session=bool(job.get('reuse_project_session', True)),
                artifact_ids=artifact_ids,
                base_path=str(job.get('artifact_base_path') or '/workspace/artifacts'),
                create_result_artifact=False,
                repo_profile_id=job.get('repo_profile_id'),
            )
        return self._run_async(self._run_job_for_project(project_id, job, input_artifacts))

    def run_command(
        self,
        project_id: str | None,
        command: str,
        files: list[dict[str, Any]] | None = None,
        image: str | None = None,
        env: dict[str, str] | None = None,
        working_dir: str | None = None,
        session_id: str | None = None,
        reuse_project_session: bool = False,
    ) -> dict[str, Any]:
        files = files or []
        env = env or {}
        session = None
        if session_id:
            session = self.get_session(session_id)
            if not session:
                raise ValueError('sandbox session not found')
        elif reuse_project_session and project_id:
            session = self.ensure_project_session(project_id, image=image, working_dir=working_dir)
        job = {
            'type': 'command',
            'command': command,
            'files': files,
            'image': image or (session['image'] if session else self.default_image),
            'env': env,
            'working_dir': working_dir or (session['working_dir'] if session else self.default_workdir),
        }
        if not self.available():
            summary = {
                'status': 'sandbox_unavailable',
                'runner': 'opensandbox',
                'reason': 'OpenSandbox is not configured or SDK is not installed',
                'job': job,
                'session_id': session['id'] if session else None,
            }
            if project_id:
                self._record_run(project_id, session['id'] if session else None, 'command', command, summary, exit_code=1)
            return summary
        result = self._run_async(self._run_job(job, session=session, keep_session=bool(session)))
        if project_id:
            self._record_run(project_id, session['id'] if session else None, 'command', command, result, exit_code=result.get('exit_code'))
        return result

    def run_repo_evaluation(
        self,
        project_id: str,
        repo_url: str,
        repo_ref: str | None = None,
        install_command: str | None = None,
        test_command: str = 'pytest -q',
        image: str | None = None,
        session_id: str | None = None,
        reuse_project_session: bool = True,
        artifact_ids: list[str] | None = None,
        base_path: str = '/workspace/artifacts',
        create_result_artifact: bool = False,
        repo_profile_id: str | None = None,
    ) -> dict[str, Any]:
        if not repo_url:
            raise ValueError('repo_url is required')
        artifact_ids = artifact_ids or []
        profile = repo_profile_service.get(repo_profile_id) if repo_profile_id else None
        if not profile:
            profile = repo_profile_service.infer_profile(
                project_id=project_id,
                repo_url=repo_url,
                repo_ref=repo_ref,
                install_command=install_command,
                test_command=test_command,
                artifact_ids=artifact_ids,
                persist=True,
            )
        install_command = install_command or profile.get('install_command')
        test_command = test_command or profile.get('test_command') or 'pytest -q'
        repo_ref = repo_ref or profile.get('metadata', {}).get('repo_ref')
        repo_dir = self.default_repo_dir
        pre_patch_inspection = None
        session = self.get_session(session_id) if session_id else None
        if not session and reuse_project_session:
            session = self.ensure_project_session(project_id, image=image or self.default_python_image, working_dir=self.default_workdir, metadata={'purpose': 'repo_test', 'repo_profile_name': profile['name']})
        if not session and project_id:
            session = self.create_session(project_id, image=image or self.default_python_image, working_dir=self.default_workdir, metadata={'purpose': 'repo_test', 'repo_profile_name': profile['name']})
        materialization = None
        if artifact_ids and session:
            materialization = self.materialize_artifacts(project_id, session['id'], artifact_ids, base_path=base_path)
        commands = [
            f'rm -rf {shlex.quote(repo_dir)}',
            f'git clone --depth 1 {shlex.quote(repo_url)} {shlex.quote(repo_dir)}',
        ]
        if repo_ref:
            commands.extend([
                f'cd {shlex.quote(repo_dir)} && git fetch --depth 1 origin {shlex.quote(repo_ref)}',
                f'cd {shlex.quote(repo_dir)} && git checkout {shlex.quote(repo_ref)}',
            ])
        for setup in profile.get('setup_commands', []):
            commands.append(setup)
        if install_command:
            commands.append(f'cd {shlex.quote(repo_dir)} && {install_command}')
        commands.append(f'cd {shlex.quote(repo_dir)} && {test_command}')
        command = ' && '.join(commands)
        result = self.run_command(
            project_id=project_id,
            command=command,
            image=image or (session['image'] if session else self.default_python_image),
            session_id=session['id'] if session else None,
            working_dir=self.default_workdir,
            reuse_project_session=bool(session and not session_id),
        )
        patch_apply = self._extract_patch_apply_summary(result.get('stdout', ''))
        parsed = repo_benchmark_parser_service.parse(result.get('stdout', ''), result.get('stderr', ''), result.get('exit_code'), test_command)
        metrics = {
            'sandbox_available': 1.0 if result.get('status') in {'ok', 'nonzero_exit'} else 0.0,
            'sandbox_exit_code': float(result.get('exit_code', 1) or 1),
            'sandbox_success_rate': 1.0 if result.get('exit_code') in (0, None) and result.get('status') == 'ok' else 0.0,
            'stdout_line_count': float(len((result.get('stdout') or '').splitlines())),
            'stderr_line_count': float(len((result.get('stderr') or '').splitlines())),
            'benchmark_detected': 1.0 if parsed.get('detected') else 0.0,
            'tests_total': float(parsed.get('tests_total', 0) or 0),
            'tests_passed': float(parsed.get('tests_passed', 0) or 0),
            'tests_failed': float(parsed.get('tests_failed', 0) or 0),
            'tests_skipped': float(parsed.get('tests_skipped', 0) or 0),
            'benchmark_case_count': float(parsed.get('benchmark_case_count', 0) or 0),
            'benchmark_success_rate': float(parsed.get('benchmark_success_rate', 0.0) or 0.0),
            'profile_match': 1.0,
        }
        if parsed.get('duration_seconds') is not None:
            metrics['duration_seconds'] = float(parsed['duration_seconds'])
        summary = {
            'status': result.get('status', 'unknown'),
            'repo_url': repo_url,
            'repo_ref': repo_ref,
            'repo_dir': repo_dir,
            'session_id': session['id'] if session else None,
            'artifact_ids': artifact_ids,
            'repo_profile': profile,
            'workspace_lineages': materialization.get('workspace_lineages', []) if materialization else [],
            'materialization': materialization,
            'pre_patch_inspection': pre_patch_inspection,
            'result': result,
            'benchmark_parse': parsed,
            'metrics': metrics,
        }
        run_id = self._record_run(project_id, session['id'] if session else None, 'repo_test', command, summary, exit_code=result.get('exit_code'))
        summary['run_id'] = run_id
        if create_result_artifact:
            artifact = artifact_service.create(
                project_id=project_id,
                artifact_type='experiment_result',
                title='Repo test result',
                data={'metrics': metrics, 'summary': summary, 'session_id': session['id'] if session else None, 'repo_profile': profile},
                confidence=0.85 if metrics['benchmark_success_rate'] >= 0.8 else (0.7 if metrics['benchmark_success_rate'] >= 0.5 else 0.35),
                parent_artifact_ids=artifact_ids,
            )
            summary['artifact_id'] = artifact['id']
        return summary

    def _record_run(self, project_id: str, session_id: str | None, run_kind: str, command_text: str | None, summary: dict[str, Any], exit_code: int | None = None) -> str:
        run_id = new_id()
        status = str(summary.get('status') or ('ok' if exit_code in (0, None) else 'error'))
        ts = now_ts()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO sandbox_runs (id, project_id, session_id, run_kind, command_text, status, exit_code, summary_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (run_id, project_id, session_id, run_kind, command_text, status, exit_code, dumps(summary), ts),
            )
            if session_id:
                conn.execute('UPDATE sandbox_sessions SET last_used_at = ?, updated_at = ? WHERE id = ?', (ts, ts, session_id))
        return run_id

    async def _remote_create_session(self, image: str, working_dir: str, metadata: dict[str, Any], ttl_minutes: int) -> str:
        from opensandbox import Sandbox

        sandbox = await Sandbox.create(
            image,
            connection_config=self._connection_config(),
            timeout=timedelta(minutes=ttl_minutes),
            env={'PYTHONUNBUFFERED': '1'},
            metadata={str(k): str(v) for k, v in metadata.items()},
        )
        try:
            return str(sandbox.id)
        finally:
            await sandbox.close()

    async def _remote_pause(self, remote_sandbox_id: str) -> None:
        from opensandbox.manager import SandboxManager

        async with await SandboxManager.create(connection_config=self._connection_config()) as manager:
            await manager.pause_sandbox(remote_sandbox_id)

    async def _remote_resume(self, remote_sandbox_id: str) -> None:
        from opensandbox import Sandbox

        sandbox = await Sandbox.resume(remote_sandbox_id, connection_config=self._connection_config())
        await sandbox.close()

    async def _remote_renew(self, remote_sandbox_id: str, ttl_minutes: int) -> None:
        from opensandbox.manager import SandboxManager

        async with await SandboxManager.create(connection_config=self._connection_config()) as manager:
            await manager.renew_sandbox(remote_sandbox_id, timedelta(minutes=ttl_minutes))

    async def _remote_kill(self, remote_sandbox_id: str) -> None:
        from opensandbox.manager import SandboxManager

        async with await SandboxManager.create(connection_config=self._connection_config()) as manager:
            await manager.kill_sandbox(remote_sandbox_id)

    async def _connect_session_sandbox(self, session: dict[str, Any]):
        from opensandbox import Sandbox

        if session['status'] == 'paused':
            sandbox = await Sandbox.resume(session['remote_sandbox_id'], connection_config=self._connection_config())
            db.conn.execute('UPDATE sandbox_sessions SET status = ?, updated_at = ?, last_used_at = ? WHERE id = ?', ('running', now_ts(), now_ts(), session['id']))
            db.conn.commit()
            return sandbox
        sandbox = await Sandbox.connect(session['remote_sandbox_id'], connection_config=self._connection_config())
        return sandbox

    async def _write_files_to_session(self, session: dict[str, Any], files: list[dict[str, Any]]) -> None:
        from opensandbox.models.filesystem import WriteEntry

        sandbox = await self._connect_session_sandbox(session)
        try:
            await sandbox.files.write_files([WriteEntry(path=f['path'], data=f.get('data', ''), mode=int(f.get('mode', 0o644))) for f in files])
        finally:
            await sandbox.close()

    async def _run_job_for_project(self, project_id: str, job: dict[str, Any], input_artifacts: list[dict]) -> dict[str, Any]:
        session = None
        if job.get('session_id'):
            session = self.get_session(str(job['session_id']))
        elif job.get('reuse_project_session'):
            session = self.ensure_project_session(project_id, image=job.get('image'))
        result = await self._run_job(job, input_artifacts=input_artifacts, session=session, keep_session=bool(session))
        self._record_run(project_id, session['id'] if session else None, 'plan_job', result.get('command'), result, exit_code=result.get('exit_code'))
        return result

    async def _run_job(self, job: dict[str, Any], input_artifacts: list[dict] | None = None, session: dict[str, Any] | None = None, keep_session: bool = False) -> dict[str, Any]:
        input_artifacts = input_artifacts or []
        image = (job.get('image') or self.default_python_image) if job.get('type') == 'python_script' else (job.get('image') or self.default_image)
        if session and session.get('image'):
            image = session['image']
        env = {str(k): str(v) for k, v in dict(job.get('env') or {}).items()}
        files = list(job.get('files') or [])
        working_dir = str(job.get('working_dir') or (session['working_dir'] if session else self.default_workdir))
        if job.get('type') == 'python_script':
            script_path = job.get('script_path', f'{working_dir}/run_experiment.py')
            script = job.get('script') or self._default_python_script(input_artifacts)
            files.append({'path': script_path, 'data': script, 'mode': 0o644})
            command = job.get('command') or f'python {script_path}'
        else:
            command = str(job.get('command') or '').strip()
        if not command:
            return {'status': 'invalid_job', 'runner': 'opensandbox', 'reason': 'command missing', 'job': job}
        if working_dir:
            command = f'cd {shlex.quote(working_dir)} && {command}'
        if session and session.get('remote_sandbox_id') and self.available():
            sandbox = await self._connect_session_sandbox(session)
            ephemeral = False
        else:
            if not self.available():
                return {'status': 'sandbox_unavailable', 'runner': 'opensandbox', 'reason': 'OpenSandbox is not configured or SDK is not installed', 'job': job, 'session_id': session['id'] if session else None}
            from opensandbox import Sandbox
            sandbox = await Sandbox.create(
                image,
                connection_config=self._connection_config(),
                timeout=timedelta(seconds=self.timeout_seconds),
                env=env,
            )
            ephemeral = True
        try:
            if files:
                from opensandbox.models.filesystem import WriteEntry
                await sandbox.files.write_files([WriteEntry(path=f['path'], data=f.get('data', ''), mode=int(f.get('mode', 0o644))) for f in files])
            execution = await sandbox.commands.run(command)
            stdout = '\n'.join(msg.text for msg in execution.logs.stdout)
            stderr = '\n'.join(msg.text for msg in execution.logs.stderr)
            exit_code = getattr(execution, 'exit_code', None)
            return {
                'status': 'ok' if exit_code in (0, None) else 'nonzero_exit',
                'runner': 'opensandbox',
                'image': image,
                'command': command,
                'exit_code': exit_code,
                'stdout': stdout[:12000],
                'stderr': stderr[:12000],
                'files_written': [f['path'] for f in files],
                'session_id': session['id'] if session else None,
                'remote_sandbox_id': session.get('remote_sandbox_id') if session else str(getattr(sandbox, 'id', '')),
                'working_dir': working_dir,
            }
        finally:
            try:
                if ephemeral and not keep_session:
                    await sandbox.kill()
            except Exception:
                pass
            await sandbox.close()

    def _default_python_script(self, input_artifacts: list[dict]) -> str:
        payload = [
            {
                'id': a.get('id'),
                'type': a.get('type'),
                'title': a.get('title'),
                'data': a.get('data'),
            }
            for a in input_artifacts
        ]
        payload_json = json.dumps(payload)
        return f"""import json
ARTIFACTS = json.loads({json.dumps(payload_json)})
requirements = []
components = []
issues = []
for artifact in ARTIFACTS:
    data = artifact.get('data') or {{}}
    if artifact.get('type') == 'requirements':
        requirements.extend([str(x) for x in data.get('items', [])])
    elif artifact.get('type') == 'architecture':
        components.extend([str(x) for x in data.get('components', [])])
    elif artifact.get('type') == 'critique':
        issues.extend([str(x) for x in data.get('issues', [])])
req_tokens = {{x.lower().replace('-', ' ').replace('_', ' ').split()[0] for x in requirements if x}}
comp_tokens = {{x.lower().replace('-', ' ').replace('_', ' ').split()[0] for x in components if x}}
coverage = (len(req_tokens & comp_tokens) / max(1, len(req_tokens))) if req_tokens else 0.0
issue_rate = len(issues) / max(1, len(components) + len(requirements))
result = {{
  'requirement_count': len(requirements),
  'component_count': len(components),
  'issue_count': len(issues),
  'requirement_coverage': round(coverage, 4),
  'issue_rate': round(issue_rate, 4),
  'graph_contradiction_rate': round(max(0.0, 0.28 + issue_rate - coverage * 0.22), 4),
  'replayability_score': round(min(1.0, 0.45 + coverage * 0.35 + max(0.0, 0.2 - issue_rate)), 4),
}}
print(json.dumps(result))
"""



    def _extract_patch_apply_summary(self, stdout: str) -> dict[str, Any]:
        for line in reversed((stdout or '').splitlines()):
            line = line.strip()
            if not line or not line.startswith('{'):
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if 'apply_method' in payload or 'applied_count' in payload:
                return payload
        return {}

    def _patch_files_from_artifacts(self, patch_artifact_ids: list[str]) -> dict[str, Any]:
        patch_files: list[dict[str, Any]] = []
        combined_diffs: list[str] = []
        for artifact_id in patch_artifact_ids:
            artifact = artifact_service.get(artifact_id)
            if not artifact or artifact['type'] != 'code_patch':
                continue
            patch_text = str(artifact['data'].get('patch_text', '') or '').strip()
            if patch_text:
                combined_diffs.append(patch_text)
            for item in artifact['data'].get('file_patches', []):
                path = str(item.get('path') or '').strip()
                if not path:
                    continue
                diff = str(item.get('diff', '') or '').strip()
                if diff:
                    combined_diffs.append(diff)
                patch_files.append({
                    'path': path,
                    'content': str(item.get('content', '')),
                    'mode': int(item.get('mode', 0o644)),
                    'strategy': str(item.get('strategy', 'overwrite')),
                    'reason': str(item.get('reason', '')),
                    'artifact_id': artifact_id,
                    'diff': diff,
                })
        combined_patch = '\n\n'.join(part for part in combined_diffs if part).strip()
        return {'patches': patch_files, 'combined_patch': combined_patch}

    def _patch_support_files(self, patch_bundle: dict[str, Any], repo_dir: str) -> tuple[list[dict[str, Any]], str]:
        patch_files = list(patch_bundle.get('patches') or [])
        combined_patch = str(patch_bundle.get('combined_patch') or '')
        payload = {'repo_dir': repo_dir, 'patches': patch_files, 'combined_patch': combined_patch}
        payload_json = json.dumps(payload)
        payload_path = f'{self.default_workdir}/patches/patches.json'
        applier_path = f'{self.default_workdir}/patches/apply_patches.py'
        combined_patch_path = f'{self.default_workdir}/patches/combined.patch'
        applier = f"""import json
import subprocess
from pathlib import Path

payload = json.loads({json.dumps(payload_json)})
repo_dir = Path(payload['repo_dir'])
patches = list(payload.get('patches', []))
combined_patch = str(payload.get('combined_patch', '') or '')
combined_patch_path = Path({json.dumps(combined_patch_path)})
combined_patch_path.parent.mkdir(parents=True, exist_ok=True)
apply_method = 'none'
attempts = []
fallback_paths = []
if combined_patch.strip():
    combined_patch_path.write_text(combined_patch)
    for cmd in ([['git', 'apply', '--recount', '--whitespace=fix', str(combined_patch_path)]], [['patch', '-p1', '-i', str(combined_patch_path)]]):
        cmd = cmd[0]
        try:
            proc = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True)
            attempts.append({{'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-1000:], 'stderr': proc.stderr[-1000:]}})
            if proc.returncode == 0:
                apply_method = cmd[0]
                break
        except Exception as exc:
            attempts.append({{'cmd': cmd, 'error': str(exc)}})
for patch in patches:
    path = repo_dir / patch['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    strategy = patch.get('strategy', 'overwrite')
    use_fallback = apply_method == 'none' or strategy in {{'append', 'prepend', 'skip_if_exists'}}
    if not use_fallback and patch.get('diff'):
        continue
    content = patch.get('content', '')
    if strategy == 'append' and path.exists():
        path.write_text(path.read_text() + content)
    elif strategy == 'prepend' and path.exists():
        path.write_text(content + path.read_text())
    elif strategy == 'skip_if_exists' and path.exists():
        continue
    else:
        path.write_text(content)
    fallback_paths.append(patch['path'])
print(json.dumps({{'apply_method': apply_method, 'applied_count': len(patches), 'fallback_paths': fallback_paths, 'attempts': attempts, 'combined_patch_path': str(combined_patch_path), 'diff_present': bool(combined_patch.strip())}}))
"""
        files = [
            {'path': payload_path, 'data': payload_json, 'mode': 0o644},
            {'path': applier_path, 'data': applier, 'mode': 0o644},
        ]
        if combined_patch.strip():
            files.append({'path': combined_patch_path, 'data': combined_patch, 'mode': 0o644})
        command = f'python {shlex.quote(applier_path)}'
        return files, command


    def run_patch_test_loop(
        self,
        project_id: str,
        repo_url: str,
        repo_ref: str | None = None,
        install_command: str | None = None,
        test_command: str | None = None,
        image: str | None = None,
        session_id: str | None = None,
        reuse_project_session: bool = True,
        artifact_ids: list[str] | None = None,
        patch_artifact_ids: list[str] | None = None,
        base_path: str = '/workspace/artifacts',
        create_result_artifact: bool = False,
        repo_profile_id: str | None = None,
    ) -> dict[str, Any]:
        if not repo_url:
            raise ValueError('repo_url is required')
        artifact_ids = artifact_ids or []
        patch_artifact_ids = patch_artifact_ids or []
        profile = repo_profile_service.get(repo_profile_id) if repo_profile_id else None
        if not profile:
            profile = repo_profile_service.infer_profile(
                project_id=project_id,
                repo_url=repo_url,
                repo_ref=repo_ref,
                install_command=install_command,
                test_command=test_command,
                artifact_ids=artifact_ids + patch_artifact_ids,
                persist=True,
            )
        install_command = install_command or profile.get('install_command')
        test_command = test_command or profile.get('test_command') or 'pytest -q'
        repo_ref = repo_ref or profile.get('metadata', {}).get('repo_ref')
        session = self.get_session(session_id) if session_id else None
        if not session and reuse_project_session:
            session = self.ensure_project_session(project_id, image=image or self.default_python_image, working_dir=self.default_workdir, metadata={'purpose': 'patch_test', 'repo_profile_name': profile['name']})
        if not session and project_id:
            session = self.create_session(project_id, image=image or self.default_python_image, working_dir=self.default_workdir, metadata={'purpose': 'patch_test', 'repo_profile_name': profile['name']})
        materialization = None
        if artifact_ids and session:
            materialization = self.materialize_artifacts(project_id, session['id'], artifact_ids, base_path=base_path)
        pre_patch_inspection = None
        if session:
            try:
                from backend.services.repo_inspection import repo_inspection_service

                pre_patch_inspection = repo_inspection_service.inspect(
                    project_id=project_id,
                    repo_url=repo_url,
                    repo_ref=repo_ref,
                    session_id=session['id'],
                    image=image or session.get('image') or self.default_python_image,
                    reuse_project_session=True,
                    create_artifact=False,
                    prefer_workspace=True,
                )
            except Exception as exc:
                pre_patch_inspection = {'inspected': False, 'method': 'patch_cycle_preinspect_failed', 'error': str(exc), 'repo_url': repo_url, 'repo_ref': repo_ref}
        patch_bundle = self._patch_files_from_artifacts(patch_artifact_ids)
        patch_files = list(patch_bundle.get('patches') or [])
        support_files, patch_apply_command = self._patch_support_files(patch_bundle, self.default_repo_dir)
        repo_dir = self.default_repo_dir
        commands = [
            f'rm -rf {shlex.quote(repo_dir)}',
            f'git clone --depth 1 {shlex.quote(repo_url)} {shlex.quote(repo_dir)}',
        ]
        if repo_ref:
            commands.extend([
                f'cd {shlex.quote(repo_dir)} && git fetch --depth 1 origin {shlex.quote(repo_ref)}',
                f'cd {shlex.quote(repo_dir)} && git checkout {shlex.quote(repo_ref)}',
            ])
        for setup in profile.get('setup_commands', []):
            commands.append(setup)
        if install_command:
            commands.append(f'cd {shlex.quote(repo_dir)} && {install_command}')
        if patch_files:
            commands.append(patch_apply_command)
        commands.append(f'cd {shlex.quote(repo_dir)} && {test_command}')
        command = ' && '.join(commands)
        result = self.run_command(
            project_id=project_id,
            command=command,
            files=support_files,
            image=image or (session['image'] if session else self.default_python_image),
            session_id=session['id'] if session else None,
            working_dir=self.default_workdir,
            reuse_project_session=bool(session and not session_id),
        )
        patch_apply = self._extract_patch_apply_summary(result.get('stdout', ''))
        parsed = repo_benchmark_parser_service.parse(result.get('stdout', ''), result.get('stderr', ''), result.get('exit_code'), test_command)
        metrics = {
            'sandbox_available': 1.0 if result.get('status') in {'ok', 'nonzero_exit'} else 0.0,
            'sandbox_exit_code': float(result.get('exit_code', 1) or 1),
            'sandbox_success_rate': 1.0 if result.get('exit_code') in (0, None) and result.get('status') == 'ok' else 0.0,
            'tests_total': float(parsed.get('tests_total', 0) or 0),
            'tests_passed': float(parsed.get('tests_passed', 0) or 0),
            'tests_failed': float(parsed.get('tests_failed', 0) or 0),
            'tests_skipped': float(parsed.get('tests_skipped', 0) or 0),
            'benchmark_case_count': float(parsed.get('benchmark_case_count', 0) or 0),
            'benchmark_success_rate': float(parsed.get('benchmark_success_rate', 0.0) or 0.0),
            'patch_file_count': float(len(patch_files)),
            'failure_hint_count': float(len(parsed.get('hinted_paths', []) or [])),
            'failing_test_count': float(len(parsed.get('failing_tests', []) or [])),
            'pre_patch_inspection_file_count': float(len((pre_patch_inspection or {}).get('file_tree', []) or [])),
            'patch_apply_success': 1.0 if patch_apply.get('apply_method') not in {'', 'none', None} or patch_apply.get('fallback_paths') else 0.0,
        }
        if parsed.get('duration_seconds') is not None:
            metrics['duration_seconds'] = float(parsed['duration_seconds'])
        summary = {
            'status': result.get('status', 'unknown'),
            'repo_url': repo_url,
            'repo_ref': repo_ref,
            'repo_dir': repo_dir,
            'session_id': session['id'] if session else None,
            'artifact_ids': artifact_ids,
            'patch_artifact_ids': patch_artifact_ids,
            'repo_profile': profile,
            'patch_files': patch_files,
            'patch_apply': patch_apply,
            'workspace_lineages': materialization.get('workspace_lineages', []) if materialization else [],
            'materialization': materialization,
            'pre_patch_inspection': pre_patch_inspection,
            'result': result,
            'benchmark_parse': parsed,
            'metrics': metrics,
        }
        run_id = self._record_run(project_id, session['id'] if session else None, 'patch_test_loop', command, summary, exit_code=result.get('exit_code'))
        summary['run_id'] = run_id

        # ── Iterative refinement loop ───────────────────────────────
        from backend.config import get_settings
        settings = get_settings()
        max_iters = settings.patch_loop_max_iterations
        improvement_threshold = settings.patch_loop_improvement_threshold
        iteration_history: list[dict[str, Any]] = [{'iteration': 0, 'metrics': dict(metrics)}]

        if max_iters > 0 and metrics.get('benchmark_success_rate', 0.0) < 1.0 and session:
            for iteration in range(1, max_iters + 1):
                prev_rate = metrics.get('benchmark_success_rate', 0.0)
                refinement = self._attempt_iterative_refinement(
                    project_id=project_id,
                    session=session,
                    repo_url=repo_url,
                    repo_ref=repo_ref,
                    repo_dir=repo_dir,
                    install_command=install_command,
                    test_command=test_command,
                    image=image,
                    profile=profile,
                    parsed=parsed,
                    pre_patch_inspection=pre_patch_inspection,
                    patch_files=patch_files,
                    iteration=iteration,
                )
                if refinement.get('skipped'):
                    iteration_history.append({'iteration': iteration, 'skipped': True, 'reason': refinement.get('reason', 'unknown')})
                    break
                new_metrics = refinement.get('metrics', metrics)
                new_rate = new_metrics.get('benchmark_success_rate', 0.0)
                iteration_history.append({'iteration': iteration, 'metrics': dict(new_metrics), 'improvement': new_rate - prev_rate})
                if new_rate > prev_rate:
                    metrics = new_metrics
                    parsed = refinement.get('parsed', parsed)
                    result = refinement.get('result', result)
                    summary['metrics'] = metrics
                    summary['benchmark_parse'] = parsed
                    summary['result'] = result
                if new_rate >= 1.0:
                    break
                if new_rate - prev_rate < improvement_threshold:
                    break
        summary['iteration_history'] = iteration_history
        summary['total_iterations'] = len(iteration_history)
        # ── End iterative refinement ────────────────────────────────

        if create_result_artifact:
            artifact = artifact_service.create(
                project_id=project_id,
                artifact_type='patch_test_result',
                title='Patch test result',
                data={'metrics': metrics, 'summary': summary, 'session_id': session['id'] if session else None, 'repo_profile': profile},
                confidence=0.86 if metrics['benchmark_success_rate'] >= 0.8 else (0.72 if metrics['benchmark_success_rate'] >= 0.5 else 0.35),
                parent_artifact_ids=artifact_ids + patch_artifact_ids,
            )
            summary['artifact_id'] = artifact['id']
        return summary

    def _attempt_iterative_refinement(
        self,
        project_id: str,
        session: dict[str, Any],
        repo_url: str,
        repo_ref: str | None,
        repo_dir: str,
        install_command: str | None,
        test_command: str,
        image: str | None,
        profile: dict[str, Any],
        parsed: dict[str, Any],
        pre_patch_inspection: dict[str, Any] | None,
        patch_files: list[dict[str, Any]],
        iteration: int,
    ) -> dict[str, Any]:
        """Run one re-analysis → re-patch → re-test cycle. Returns new metrics or {skipped: True}."""
        try:
            from backend.services.failure_analysis import failure_analysis_service
            from backend.services.patch_synthesizer import patch_synthesizer_service
        except Exception:
            return {'skipped': True, 'reason': 'imports_unavailable'}

        inspection = pre_patch_inspection or {}
        if not parsed.get('failing_tests') and not parsed.get('hinted_paths'):
            return {'skipped': True, 'reason': 'no_actionable_failures'}

        # Re-analyze failures with current results
        try:
            analysis = failure_analysis_service.analyze(inspection, parsed, profile)
        except Exception as exc:
            return {'skipped': True, 'reason': f'failure_analysis_error: {exc}'}

        ranked_targets = analysis.get('ranked_targets', [])[:6]
        if not ranked_targets:
            return {'skipped': True, 'reason': 'no_ranked_targets'}

        # Build a lightweight plan from the re-analysis
        targets = []
        for ranked in ranked_targets:
            path = str(ranked.get('path', '')).strip()
            if not path:
                continue
            targets.append({
                'path': path,
                'reason': '; '.join(ranked.get('blame_reasons', [])[:2]) or 'iterative re-analysis',
                'strategy': str(ranked.get('strategy') or 'overwrite'),
                'score': float(ranked.get('score', 0.0) or 0.0),
                'blame_reasons': list(ranked.get('blame_reasons', []))[:6],
                'symbol_matches': list(ranked.get('symbol_matches', []))[:6],
                'context_excerpt': str(ranked.get('context_excerpt') or ''),
            })
        if not targets:
            return {'skipped': True, 'reason': 'no_targets_after_reanalysis'}

        retry_plan = {
            'type': 'code_patch_plan',
            'data': {
                'targets': targets,
                'repo_url': repo_url,
                'repo_ref': repo_ref,
                'install_command': install_command,
                'test_command': test_command,
                'iteration': iteration,
                'failure_context': {
                    'failing_tests': list(parsed.get('failing_tests', []))[:10],
                    'hinted_paths': list(parsed.get('hinted_paths', []))[:8],
                    'error_summary': str(parsed.get('error_summary', '')),
                },
            },
        }

        # Re-synthesize patches
        try:
            synthesized = patch_synthesizer_service.synthesize(
                plan=retry_plan,
                repo_profile=profile,
                inspection=inspection,
                task_meta={'repo_url': repo_url, 'repo_ref': repo_ref, 'iteration': iteration},
                failing_result={'type': 'patch_test_result', 'data': {'benchmark_parse': parsed}},
            )
        except Exception as exc:
            return {'skipped': True, 'reason': f'synthesis_error: {exc}'}

        file_patches = synthesized.get('file_patches') or []
        if not file_patches:
            return {'skipped': True, 'reason': 'no_patches_synthesized'}

        # Build apply command for new patches
        patch_bundle = {'patches': file_patches, 'combined_patch': synthesized.get('patch_text', '')}
        support_files, patch_apply_command = self._patch_support_files(patch_bundle, repo_dir)

        # Re-apply patches and re-run tests (repo is already cloned and installed)
        commands = [patch_apply_command, f'cd {shlex.quote(repo_dir)} && {test_command}']
        command = ' && '.join(commands)

        try:
            re_result = self.run_command(
                project_id=project_id,
                command=command,
                files=support_files,
                image=image or session.get('image') or self.default_python_image,
                session_id=session.get('id'),
                working_dir=self.default_workdir,
                reuse_project_session=True,
            )
        except Exception as exc:
            return {'skipped': True, 'reason': f'execution_error: {exc}'}

        re_parsed = repo_benchmark_parser_service.parse(
            re_result.get('stdout', ''), re_result.get('stderr', ''), re_result.get('exit_code'), test_command,
        )
        re_metrics = {
            'sandbox_available': 1.0 if re_result.get('status') in {'ok', 'nonzero_exit'} else 0.0,
            'sandbox_exit_code': float(re_result.get('exit_code', 1) or 1),
            'sandbox_success_rate': 1.0 if re_result.get('exit_code') in (0, None) and re_result.get('status') == 'ok' else 0.0,
            'tests_total': float(re_parsed.get('tests_total', 0) or 0),
            'tests_passed': float(re_parsed.get('tests_passed', 0) or 0),
            'tests_failed': float(re_parsed.get('tests_failed', 0) or 0),
            'tests_skipped': float(re_parsed.get('tests_skipped', 0) or 0),
            'benchmark_case_count': float(re_parsed.get('benchmark_case_count', 0) or 0),
            'benchmark_success_rate': float(re_parsed.get('benchmark_success_rate', 0.0) or 0.0),
            'patch_file_count': float(len(file_patches)),
            'failure_hint_count': float(len(re_parsed.get('hinted_paths', []) or [])),
            'failing_test_count': float(len(re_parsed.get('failing_tests', []) or [])),
            'iteration': float(iteration),
        }
        return {'metrics': re_metrics, 'parsed': re_parsed, 'result': re_result}


sandbox_harness_service = SandboxHarnessService()
