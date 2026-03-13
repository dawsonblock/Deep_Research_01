from __future__ import annotations

import json
import os
import shlex
from typing import Any

from backend.services.artifacts import artifact_service
from backend.services.sandbox_harness import sandbox_harness_service


class RepoInspectionService:
    KEY_FILES = [
        'pyproject.toml',
        'requirements.txt',
        'setup.py',
        'pytest.ini',
        'tox.ini',
        'package.json',
        'tsconfig.json',
        'jest.config.js',
        'jest.config.cjs',
        'jest.config.ts',
        'vitest.config.ts',
        'vitest.config.js',
        'Cargo.toml',
        'go.mod',
        'Makefile',
    ]

    def inspect(
        self,
        project_id: str,
        repo_url: str,
        repo_ref: str | None = None,
        session_id: str | None = None,
        image: str | None = None,
        reuse_project_session: bool = True,
        create_artifact: bool = True,
        prefer_workspace: bool = True,
    ) -> dict[str, Any]:
        if not repo_url:
            raise ValueError('repo_url is required')
        result = self._inspect_remote(project_id, repo_url, repo_ref, session_id, image, reuse_project_session, prefer_workspace)
        if create_artifact:
            artifact = artifact_service.create(
                project_id=project_id,
                artifact_type='repo_inspection',
                title=f'Repo inspection: {self._repo_name(repo_url)}',
                data=result,
                confidence=0.86 if result.get('inspected') else 0.48,
            )
            result['artifact_id'] = artifact['id']
        return result

    def latest_for_project(self, project_id: str, repo_url: str | None = None) -> dict[str, Any] | None:
        artifacts = artifact_service.list(project_id, 'repo_inspection')
        for artifact in artifacts:
            data = artifact.get('data', {})
            if repo_url and data.get('repo_url') and data.get('repo_url') != repo_url:
                continue
            return artifact
        return None

    def ensure_fresh_for_patch_cycle(
        self,
        project_id: str,
        repo_url: str,
        repo_ref: str | None = None,
        session_id: str | None = None,
        image: str | None = None,
        reuse_project_session: bool = True,
    ) -> dict[str, Any]:
        return self.inspect(
            project_id=project_id,
            repo_url=repo_url,
            repo_ref=repo_ref,
            session_id=session_id,
            image=image,
            reuse_project_session=reuse_project_session,
            create_artifact=True,
            prefer_workspace=True,
        )

    def _repo_name(self, repo_url: str) -> str:
        name = repo_url.rstrip('/').split('/')[-1]
        return name[:-4] if name.endswith('.git') else name

    def _infer_from_signals(self, repo_url: str, repo_ref: str | None, file_tree: list[str], snapshots: dict[str, str], result: dict[str, Any]) -> dict[str, Any]:
        lower_tree = [p.lower() for p in file_tree]
        joined = ' '.join(lower_tree)
        signals = {
            'has_pyproject': 'pyproject.toml' in lower_tree,
            'has_requirements': 'requirements.txt' in lower_tree,
            'has_pytest_ini': 'pytest.ini' in lower_tree,
            'has_package_json': 'package.json' in lower_tree,
            'has_tsconfig': 'tsconfig.json' in lower_tree,
            'has_jest_config': any(name in lower_tree for name in ['jest.config.js', 'jest.config.cjs', 'jest.config.ts']),
            'has_vitest_config': any(name in lower_tree for name in ['vitest.config.ts', 'vitest.config.js']),
            'has_cargo_toml': 'cargo.toml' in lower_tree,
            'has_go_mod': 'go.mod' in lower_tree,
            'has_makefile': 'makefile' in lower_tree,
            'tests_dir_present': any(p.startswith('tests/') or '/tests/' in p for p in lower_tree),
        }
        package_json = snapshots.get('package.json') or ''
        pyproject = snapshots.get('pyproject.toml') or ''
        signals['declares_pytest'] = 'pytest' in pyproject.lower() or 'pytest' in joined
        signals['declares_jest'] = '"jest"' in package_json.lower() or ' jest' in joined
        signals['declares_vitest'] = 'vitest' in package_json.lower() or 'vitest' in joined
        language = 'generic'
        framework = 'generic'
        if signals['has_pyproject'] or signals['has_requirements'] or signals['has_pytest_ini']:
            language = 'python'
            framework = 'pytest' if signals['declares_pytest'] or signals['tests_dir_present'] or signals['has_pytest_ini'] else 'python'
        elif signals['has_package_json']:
            language = 'typescript' if signals['has_tsconfig'] else 'javascript'
            framework = 'vitest' if signals['declares_vitest'] or signals['has_vitest_config'] else ('jest' if signals['declares_jest'] or signals['has_jest_config'] else 'node')
        elif signals['has_cargo_toml']:
            language = 'rust'
            framework = 'cargo'
        elif signals['has_go_mod']:
            language = 'go'
            framework = 'go_test'
        result['signals'] = signals
        result['detected_language'] = language
        result['detected_framework'] = framework
        result['repo_name'] = self._repo_name(repo_url)
        result['repo_url'] = repo_url
        result['repo_ref'] = repo_ref
        return result

    def _inspect_script(self) -> str:
        return f"""import json, os
from pathlib import Path
repo_dir = Path({sandbox_harness_service.default_repo_dir!r})
key_files = {self.KEY_FILES!r}
all_files = []
if repo_dir.exists():
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in {{'.git', 'node_modules', '.venv', 'venv', 'target', '__pycache__'}}]
        for f in files:
            path = Path(root) / f
            rel = str(path.relative_to(repo_dir)).replace('\\\\', '/')
            all_files.append(rel)
all_files = sorted(all_files)[:500]
snapshots = {{}}
interesting = set(key_files)
interesting.update([f for f in all_files if f.endswith(('.py', '.js', '.ts', '.tsx', '.rs', '.go'))][:12])
for rel in sorted(interesting):
    path = repo_dir / rel
    if path.exists() and path.is_file():
        try:
            snapshots[rel] = path.read_text()[:16000]
        except Exception:
            snapshots[rel] = ''
print(json.dumps({{'file_tree': all_files, 'snapshots': snapshots, 'repo_exists': repo_dir.exists()}}))
"""

    def _inspect_remote(
        self,
        project_id: str,
        repo_url: str,
        repo_ref: str | None,
        session_id: str | None,
        image: str | None,
        reuse_project_session: bool,
        prefer_workspace: bool,
    ) -> dict[str, Any]:
        repo_dir = sandbox_harness_service.default_repo_dir
        files = [{'path': f'{sandbox_harness_service.default_workdir}/inspect_repo.py', 'data': self._inspect_script(), 'mode': 0o644}]
        commands = []
        if prefer_workspace:
            commands.append(
                f'if [ ! -d {shlex.quote(repo_dir)}/.git ]; then rm -rf {shlex.quote(repo_dir)} && git clone --depth 1 {shlex.quote(repo_url)} {shlex.quote(repo_dir)}; fi'
            )
        else:
            commands.extend([
                f'rm -rf {shlex.quote(repo_dir)}',
                f'git clone --depth 1 {shlex.quote(repo_url)} {shlex.quote(repo_dir)}',
            ])
        if repo_ref:
            commands.extend([
                f'cd {shlex.quote(repo_dir)} && git fetch --depth 1 origin {shlex.quote(repo_ref)} || true',
                f'cd {shlex.quote(repo_dir)} && git checkout {shlex.quote(repo_ref)} || true',
            ])
        commands.append(f'python {shlex.quote(sandbox_harness_service.default_workdir)}/inspect_repo.py')
        result = sandbox_harness_service.run_command(
            project_id=project_id,
            command=' && '.join(commands),
            files=files,
            image=image or sandbox_harness_service.default_python_image,
            session_id=session_id,
            working_dir=sandbox_harness_service.default_workdir,
            reuse_project_session=reuse_project_session,
        )
        parsed: dict[str, Any] = {}
        stdout = result.get('stdout', '') or ''
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                break
            except Exception:
                continue
        file_tree = parsed.get('file_tree', []) if isinstance(parsed, dict) else []
        snapshots = parsed.get('snapshots', {}) if isinstance(parsed, dict) else {}
        base = {
            'inspected': bool(file_tree),
            'method': 'opensandbox_workspace_scan' if prefer_workspace and file_tree else ('opensandbox_clone_scan' if file_tree else 'heuristic_fallback'),
            'sandbox_result': {
                'status': result.get('status'),
                'exit_code': result.get('exit_code'),
                'session_id': result.get('session_id'),
            },
            'workspace_reused': bool(prefer_workspace),
            'file_tree': file_tree,
            'detected_files': [p for p in file_tree if os.path.basename(p) in self.KEY_FILES],
            'snapshots': snapshots,
        }
        if not file_tree:
            guess_tree = []
            url_l = repo_url.lower()
            if any(tok in url_l for tok in ['python', 'pytest']):
                guess_tree = ['pyproject.toml', 'tests/test_smoke.py']
                snapshots = {'pyproject.toml': '[project]\nname = "guessed-python-project"\n'}
            elif any(tok in url_l for tok in ['node', 'javascript', 'typescript', 'react']):
                guess_tree = ['package.json']
                snapshots = {'package.json': '{"name":"guessed-node-project","scripts":{"test":"vitest run"}}'}
            base.update({'file_tree': guess_tree, 'detected_files': guess_tree, 'snapshots': snapshots})
        result = self._infer_from_signals(repo_url, repo_ref, base['file_tree'], base['snapshots'], base)
        result = self._enrich_with_ast(result)
        return result

    def _enrich_with_ast(self, result: dict[str, Any]) -> dict[str, Any]:
        """Attach AST-derived symbol_table and file_symbols to inspection results."""
        snapshots = result.get('snapshots') or {}
        if not snapshots:
            result['symbol_table'] = {}
            result['file_symbols'] = {}
            return result
        try:
            from backend.services.ast_analysis import ast_analysis_service
            symbol_index = ast_analysis_service.build_symbol_index(snapshots)
            # file_symbols: {path: [{name, kind, start_line, end_line}, ...]}
            file_symbols: dict[str, list[dict[str, Any]]] = {}
            for entries in symbol_index.values():
                for entry in entries:
                    path = entry.get('path', '')
                    if path not in file_symbols:
                        file_symbols[path] = []
                    file_symbols[path].append({
                        'name': entry.get('name'),
                        'kind': entry.get('kind'),
                        'start_line': entry.get('start_line'),
                        'end_line': entry.get('end_line'),
                        'parent': entry.get('parent'),
                        'language': entry.get('language'),
                    })
            result['symbol_table'] = symbol_index
            result['file_symbols'] = file_symbols
        except Exception:
            result['symbol_table'] = {}
            result['file_symbols'] = {}
        return result


repo_inspection_service = RepoInspectionService()
