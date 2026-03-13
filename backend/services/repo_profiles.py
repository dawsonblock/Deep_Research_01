from __future__ import annotations

from typing import Any

from backend.db import db
from backend.utils import dumps, loads, new_id, now_ts


class RepoProfileService:
    def infer_profile(
        self,
        project_id: str,
        repo_url: str | None = None,
        repo_ref: str | None = None,
        install_command: str | None = None,
        test_command: str | None = None,
        artifact_ids: list[str] | None = None,
        persist: bool = False,
        source_artifact_id: str | None = None,
    ) -> dict[str, Any]:
        artifact_ids = artifact_ids or []
        artifact_hints: list[str] = []
        inspection_artifact = None
        inspection_data: dict[str, Any] = {}
        latest_repo_profile = self.latest(project_id)
        if latest_repo_profile and not (repo_url or test_command or install_command or artifact_ids):
            return latest_repo_profile

        from backend.services.artifacts import artifact_service

        if artifact_ids:
            for artifact_id in artifact_ids:
                artifact = artifact_service.get(artifact_id)
                if not artifact:
                    continue
                artifact_hints.append(artifact['title'])
                artifact_hints.append(artifact['type'])
                data = artifact.get('data', {})
                if artifact['type'] == 'repo_inspection' and not inspection_artifact:
                    inspection_artifact = artifact
                    inspection_data = dict(data)
                for key in ('method', 'statement', 'prediction', 'text', 'detected_framework', 'detected_language'):
                    if key in data:
                        artifact_hints.append(str(data[key]))
                for key in ('issues', 'components', 'items', 'steps', 'detected_files', 'file_tree'):
                    if isinstance(data.get(key), list):
                        artifact_hints.extend(map(str, data[key][:20]))
        if not inspection_artifact:
            latest_inspection = artifact_service.latest_by_type(project_id, 'repo_inspection')
            if latest_inspection and (not repo_url or latest_inspection.get('data', {}).get('repo_url') == repo_url):
                inspection_artifact = latest_inspection
                inspection_data = dict(latest_inspection.get('data', {}))
        hint_text = ' '.join(artifact_hints).lower()
        repo_url_l = (repo_url or '').lower()
        test_command_l = (test_command or '').lower()
        install_command_l = (install_command or '').lower()

        framework = 'generic'
        language = 'generic'
        name = 'generic_shell'
        parser_hint = 'generic'
        patch_strategy = 'materialize_overwrite'
        setup_commands: list[str] = []
        inferred_install = install_command
        inferred_test = test_command or 'pytest -q'

        if inspection_data:
            metadata_inspection = {
                'detected_framework': inspection_data.get('detected_framework'),
                'detected_language': inspection_data.get('detected_language'),
                'detected_files': inspection_data.get('detected_files', []),
                'artifact_id': inspection_artifact['id'] if inspection_artifact else None,
            }
            if inspection_data.get('detected_framework') == 'pytest' or inspection_data.get('detected_language') == 'python':
                framework = 'pytest' if inspection_data.get('signals', {}).get('declares_pytest') or inspection_data.get('signals', {}).get('has_pytest_ini') else 'python'
                language = 'python'
                name = 'python_pytest' if framework == 'pytest' else 'python_project'
                parser_hint = 'pytest' if framework == 'pytest' else 'generic'
                inferred_install = inferred_install or 'python -m pip install -U pip && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi && if [ -f pyproject.toml ]; then pip install -e . || true; fi'
                inferred_test = test_command or ('pytest -q' if framework == 'pytest' else 'python -m pytest -q')
                setup_commands = ['python --version', 'pip --version']
                patch_strategy = 'file_overlay'
            elif inspection_data.get('detected_framework') in {'jest', 'vitest', 'node'} or inspection_data.get('detected_language') in {'javascript', 'typescript'}:
                framework = inspection_data.get('detected_framework') if inspection_data.get('detected_framework') in {'jest', 'vitest'} else 'jest'
                language = inspection_data.get('detected_language') or 'javascript'
                name = 'node_vitest' if framework == 'vitest' else 'node_jest'
                parser_hint = framework
                inferred_install = inferred_install or 'if [ -f package-lock.json ]; then npm ci; elif [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; elif [ -f yarn.lock ]; then yarn install --frozen-lockfile; else npm install; fi'
                inferred_test = test_command or ('npx vitest run' if framework == 'vitest' else 'npm test -- --runInBand')
                setup_commands = ['node --version', 'npm --version']
                patch_strategy = 'file_overlay'
            elif inspection_data.get('detected_framework') == 'cargo' or inspection_data.get('detected_language') == 'rust':
                framework = 'cargo'
                language = 'rust'
                name = 'rust_cargo'
                parser_hint = 'cargo'
                inferred_install = inferred_install or 'rustc --version && cargo --version'
                inferred_test = test_command or 'cargo test -- --nocapture'
                setup_commands = ['rustc --version', 'cargo --version']
                patch_strategy = 'file_overlay'
            elif inspection_data.get('detected_framework') == 'go_test' or inspection_data.get('detected_language') == 'go':
                framework = 'go_test'
                language = 'go'
                name = 'go_test'
                parser_hint = 'go'
                inferred_install = inferred_install or 'go version'
                inferred_test = test_command or 'go test ./...'
                setup_commands = ['go version']
                patch_strategy = 'file_overlay'
        if any(token in test_command_l for token in ['pytest', 'py.test']) or '.py' in repo_url_l or 'python' in hint_text:
            framework = 'pytest'
            language = 'python'
            name = 'python_pytest'
            parser_hint = 'pytest'
            inferred_install = inferred_install or 'python -m pip install -U pip && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi && if [ -f pyproject.toml ]; then pip install -e . || true; fi'
            inferred_test = test_command or 'pytest -q'
            setup_commands = ['python --version', 'pip --version']
            patch_strategy = 'file_overlay'
        elif any(token in test_command_l for token in ['jest', 'vitest', 'npm test', 'pnpm test', 'yarn test']) or any(token in repo_url_l for token in ['package.json', 'node', 'javascript', 'typescript']) or any(token in hint_text for token in ['jest', 'vitest', 'node', 'typescript', 'javascript']):
            framework = 'vitest' if 'vitest' in test_command_l or 'vitest' in hint_text else 'jest'
            language = 'typescript' if any(token in hint_text for token in ['typescript', 'tsconfig']) else 'javascript'
            name = 'node_vitest' if framework == 'vitest' else 'node_jest'
            parser_hint = framework
            inferred_install = inferred_install or 'if [ -f package-lock.json ]; then npm ci; elif [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; elif [ -f yarn.lock ]; then yarn install --frozen-lockfile; else npm install; fi'
            inferred_test = test_command or ('npx vitest run' if framework == 'vitest' else 'npm test -- --runInBand')
            setup_commands = ['node --version', 'npm --version']
            patch_strategy = 'file_overlay'
        elif any(token in test_command_l for token in ['cargo test', 'cargo nextest']) or any(token in hint_text for token in ['cargo', 'rust']) or repo_url_l.endswith('.rs'):
            framework = 'cargo'
            language = 'rust'
            name = 'rust_cargo'
            parser_hint = 'cargo'
            inferred_install = inferred_install or 'rustc --version && cargo --version'
            inferred_test = test_command or 'cargo test -- --nocapture'
            setup_commands = ['rustc --version', 'cargo --version']
            patch_strategy = 'file_overlay'
        elif any(token in test_command_l for token in ['go test']) or any(token in hint_text for token in ['go.mod', 'golang', 'go test']):
            framework = 'go_test'
            language = 'go'
            name = 'go_test'
            parser_hint = 'go'
            inferred_install = inferred_install or 'go version'
            inferred_test = test_command or 'go test ./...'
            setup_commands = ['go version']
            patch_strategy = 'file_overlay'

        profile = {
            'name': name,
            'language': language,
            'framework': framework,
            'repo_url': repo_url,
            'repo_ref': repo_ref,
            'install_command': inferred_install,
            'test_command': inferred_test,
            'setup_commands': setup_commands,
            'parser_hint': parser_hint,
            'patch_strategy': patch_strategy,
            'metadata': {
                'heuristics': {
                    'repo_url': repo_url,
                    'test_command': test_command,
                    'install_command': install_command,
                    'artifact_ids': artifact_ids,
                    'hint_count': len(artifact_hints),
                'inspection_artifact_id': inspection_artifact['id'] if inspection_artifact else None,
                'inspection_framework': inspection_data.get('detected_framework'),
                }
            },
            'source_artifact_id': source_artifact_id,
        }
        if persist:
            return self.create(project_id=project_id, **profile)
        return profile

    def create(
        self,
        project_id: str,
        name: str,
        language: str,
        framework: str,
        install_command: str | None,
        test_command: str,
        setup_commands: list[str] | None = None,
        parser_hint: str | None = None,
        patch_strategy: str | None = None,
        metadata: dict[str, Any] | None = None,
        source_artifact_id: str | None = None,
        repo_url: str | None = None,
        repo_ref: str | None = None,
    ) -> dict[str, Any]:
        ts = now_ts()
        existing = db.conn.execute(
            'SELECT id FROM repo_execution_profiles WHERE project_id = ? AND name = ? ORDER BY updated_at DESC LIMIT 1',
            (project_id, name),
        ).fetchone()
        metadata = dict(metadata or {})
        if repo_url:
            metadata.setdefault('repo_url', repo_url)
        if repo_ref:
            metadata.setdefault('repo_ref', repo_ref)
        if existing:
            profile_id = existing['id']
            with db.transaction() as conn:
                conn.execute(
                    'UPDATE repo_execution_profiles SET language = ?, framework = ?, install_command = ?, test_command = ?, setup_commands_json = ?, parser_hint = ?, patch_strategy = ?, metadata_json = ?, source_artifact_id = ?, updated_at = ? WHERE id = ?',
                    (language, framework, install_command, test_command, dumps(setup_commands or []), parser_hint, patch_strategy, dumps(metadata), source_artifact_id, ts, profile_id),
                )
            return self.get(profile_id)
        profile_id = new_id()
        with db.transaction() as conn:
            conn.execute(
                'INSERT INTO repo_execution_profiles (id, project_id, name, language, framework, install_command, test_command, setup_commands_json, parser_hint, patch_strategy, metadata_json, source_artifact_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (profile_id, project_id, name, language, framework, install_command, test_command, dumps(setup_commands or []), parser_hint, patch_strategy, dumps(metadata), source_artifact_id, ts, ts),
            )
        return self.get(profile_id)

    def get(self, profile_id: str) -> dict[str, Any] | None:
        row = db.conn.execute('SELECT * FROM repo_execution_profiles WHERE id = ?', (profile_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item['setup_commands'] = loads(item.pop('setup_commands_json'), [])
        item['metadata'] = loads(item.pop('metadata_json'), {})
        return item

    def list(self, project_id: str) -> list[dict[str, Any]]:
        rows = db.conn.execute('SELECT id FROM repo_execution_profiles WHERE project_id = ? ORDER BY updated_at DESC, created_at DESC', (project_id,)).fetchall()
        return [self.get(r['id']) for r in rows]

    def latest(self, project_id: str) -> dict[str, Any] | None:
        row = db.conn.execute('SELECT id FROM repo_execution_profiles WHERE project_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1', (project_id,)).fetchone()
        return self.get(row['id']) if row else None


repo_profile_service = RepoProfileService()
