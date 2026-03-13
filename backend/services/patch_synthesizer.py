from __future__ import annotations

import difflib
import json
import re
from typing import Any

from backend.config import get_settings
from backend.services.llm import llm_service


class PatchSynthesizerService:
    def synthesize(
        self,
        plan: dict[str, Any],
        repo_profile: dict[str, Any] | None = None,
        inspection: dict[str, Any] | None = None,
        task_meta: dict[str, Any] | None = None,
        failing_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_meta = dict(task_meta or {})
        repo_profile = repo_profile or {}
        inspection = inspection or {}
        failing_result = failing_result or {}
        plan_data = dict(plan.get('data') or {}) if 'data' in plan else dict(plan or {})
        snapshots = dict(inspection.get('snapshots') or {})
        framework = str(repo_profile.get('framework') or plan_data.get('repo_profile_name') or inspection.get('detected_framework') or 'generic')
        failure_context = self._failure_context(failing_result)
        targets = self._expanded_targets(plan_data, inspection, failure_context)
        goals = list(plan_data.get('goals') or [])
        file_patches: list[dict[str, Any]] = []
        for target in targets[:10]:
            path = str(target.get('path') or '').strip()
            if not path:
                continue
            before = snapshots.get(path, '')
            updated = self._updated_content(path, before, framework, target, goals, failure_context)
            diff = self._diff_text(path, before, updated)
            if not updated and not diff:
                continue
            file_patches.append({
                'path': path,
                'strategy': 'overwrite',
                'mode': int(target.get('mode', 0o644) or 0o644),
                'before_content': before,
                'content': updated,
                'diff': diff,
                'reason': str(target.get('reason') or 'synthesized patch'),
                'context_excerpt': str(target.get('context_excerpt') or self._context_excerpt(before, failure_context)),
                'symbol_matches': list(target.get('symbol_matches', []))[:6],
                'blame_score': float(target.get('blame_score', target.get('score', 0.0)) or 0.0),
            })
        if not file_patches:
            fallback_path = 'research_engine.patch-note.txt'
            before = snapshots.get(fallback_path, '')
            updated = before + ('\n' if before else '') + 'Patch synthesis fallback: inspect repo and supply a concrete target file for stronger patches.\n'
            file_patches.append({
                'path': fallback_path,
                'strategy': 'overwrite',
                'mode': 0o644,
                'before_content': before,
                'content': updated,
                'diff': self._diff_text(fallback_path, before, updated),
                'reason': 'generic fallback patch',
                'context_excerpt': self._context_excerpt(before, failure_context),
            })
        failure_analysis = dict(plan_data.get('failure_analysis') or {})
        fallback = {
            'repo_url': task_meta.get('repo_url') or plan_data.get('repo_url'),
            'repo_ref': task_meta.get('repo_ref') or plan_data.get('repo_ref'),
            'install_command': task_meta.get('install_command') or plan_data.get('install_command'),
            'test_command': task_meta.get('test_command') or plan_data.get('test_command'),
            'patch_format': 'unified_diff',
            'patch_text': '\n\n'.join([p['diff'] for p in file_patches if p.get('diff')]),
            'file_patches': file_patches,
            'notes': goals[:5] or ['synthesized from repo inspection and patch plan'],
            'failure_context': failure_context,
            'failure_analysis': failure_analysis,
            'patch_application': {'preferred_method': 'unified_diff_then_fallback_overwrite'},
        }
        if llm_service.available() and inspection.get('snapshots'):
            llm_patches = self._llm_synthesize_with_slices(
                framework=framework,
                goals=goals,
                targets=targets,
                snapshots=snapshots,
                failure_context=failure_context,
                file_patches=file_patches,
            )
            if llm_patches:
                fallback['file_patches'] = llm_patches
                fallback['patch_text'] = '\n\n'.join([p['diff'] for p in llm_patches if p.get('diff')])
        fallback['patch_summary'] = {
            'patch_count': len(fallback['file_patches']),
            'paths': [p['path'] for p in fallback['file_patches']],
            'framework': framework,
            'inspection_used': bool(inspection),
            'failure_paths': failure_context.get('hinted_paths', []),
            'derived_symbols': list(failure_analysis.get('derived_symbols', []))[:12],
            'ranked_target_paths': [t.get('path') for t in list(plan_data.get('ranked_targets', []))[:8]],
        }
        return fallback

    def _llm_synthesize_with_slices(
        self,
        framework: str,
        goals: list[str],
        targets: list[dict[str, Any]],
        snapshots: dict[str, str],
        failure_context: dict[str, Any],
        file_patches: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Send function-level slices (not whole files) to the LLM for surgical fixes.

        For each target that has symbol matches or is a source file, we extract
        the relevant function/class bodies via the AST service. The LLM receives
        only those slices, keeping prompts small and patches focused.
        """
        settings = get_settings()
        max_tokens = settings.patch_max_slice_tokens

        try:
            from backend.services.ast_analysis import ast_analysis_service
        except Exception:
            ast_analysis_service = None  # type: ignore[assignment]

        sliced_targets: list[dict[str, Any]] = []
        char_budget = max_tokens * 4  # rough chars-per-token estimate

        for target in targets[:settings.patch_max_targets]:
            path = str(target.get('path') or '').strip()
            if not path:
                continue
            content = snapshots.get(path, '')
            if not content:
                continue

            # Collect function-level slices for symbols that matched
            symbol_slices: list[dict[str, Any]] = []
            matched_symbols = target.get('symbol_matches') or []
            if ast_analysis_service and matched_symbols:
                for sym in matched_symbols[:6]:
                    sym_name = sym.get('name') or sym.get('symbol', '')
                    if not sym_name:
                        continue
                    fn_slice = ast_analysis_service.get_function_slice(content, sym_name, path=path)
                    if fn_slice:
                        symbol_slices.append(fn_slice)

            # If no symbol matches found specific slices, grab the first few defs
            if not symbol_slices and ast_analysis_service and content:
                all_slices = ast_analysis_service.get_all_slices(content, path=path)
                symbol_slices = all_slices[:4]

            # Build compact representation
            sliced_content = []
            total_chars = 0
            for sl in symbol_slices:
                src = sl.get('source', '')
                if total_chars + len(src) > char_budget:
                    break
                sliced_content.append({
                    'name': sl.get('name'),
                    'kind': sl.get('kind'),
                    'start_line': sl.get('start_line'),
                    'end_line': sl.get('end_line'),
                    'source': src,
                })
                total_chars += len(src)

            # Fallback: send a truncated version of the file
            if not sliced_content:
                sliced_content = [{'name': '_full_file_head_', 'kind': 'file_head', 'start_line': 1, 'end_line': None, 'source': content[:char_budget]}]

            sliced_targets.append({
                'path': path,
                'slices': sliced_content,
                'blame_reasons': target.get('blame_reasons', [])[:3],
                'blame_score': target.get('blame_score', target.get('score', 0)),
            })

        if not sliced_targets:
            return []

        prompt = {
            'framework': framework,
            'goals': goals[:5],
            'failure_context': {
                'failing_tests': failure_context.get('failing_tests', [])[:6],
                'failure_messages': failure_context.get('failure_messages', [])[:4],
                'trace_excerpt': failure_context.get('trace_excerpt', '')[:1600],
            },
            'targets': sliced_targets,
        }

        generated = llm_service.complete_json(
            'You are a code repair agent. For each target file, return a FIXED version of the '
            'provided function slices that directly addresses the failure. Return JSON with keys: '
            'file_patches (list of {path, content, reason, replaced_symbols: [{name, new_source}]}), notes (list of strings). '
            'The content field should be the COMPLETE new file content. '
            'If you can only fix individual functions, provide replaced_symbols with each symbol\'s new source.',
            json.dumps(prompt, ensure_ascii=False),
            {'file_patches': file_patches, 'notes': ['llm-synthesized with function slices']},
        )

        llm_patches: list[dict[str, Any]] = []
        for item in generated.get('file_patches', []):
            path = str(item.get('path') or '').strip()
            if not path:
                continue
            before = snapshots.get(path, '')
            content_out = str(item.get('content', ''))
            replaced_symbols = item.get('replaced_symbols') or []

            # If LLM provided per-symbol replacements, stitch them into the original file
            if replaced_symbols and before and not content_out.strip():
                content_out = self._stitch_symbol_replacements(before, replaced_symbols, path, ast_analysis_service)
            elif not content_out.strip():
                continue  # skip empty patches

            llm_patches.append({
                'path': path,
                'strategy': 'overwrite',
                'mode': int(item.get('mode', 0o644) or 0o644),
                'before_content': before,
                'content': content_out,
                'diff': self._diff_text(path, before, content_out),
                'reason': str(item.get('reason') or 'llm synthesized patch (function-slice)'),
                'context_excerpt': self._context_excerpt(before, failure_context),
                'replaced_symbols': [s.get('name') for s in replaced_symbols if s.get('name')],
            })
        return llm_patches

    @staticmethod
    def _stitch_symbol_replacements(
        original: str,
        replaced_symbols: list[dict[str, Any]],
        path: str,
        ast_service: Any,
    ) -> str:
        """Replace individual function/class bodies in *original* using AST line ranges.

        For each entry in *replaced_symbols* ``{name, new_source}``, look up the
        original symbol's line range via the AST service, and splice the new source
        in place of the old lines.
        """
        if not ast_service:
            return original

        lines = original.splitlines(keepends=True)
        # Build replacements sorted from bottom to top (so line numbers stay stable)
        edits: list[tuple[int, int, str]] = []
        for sym_rep in replaced_symbols:
            name = sym_rep.get('name', '')
            new_source = sym_rep.get('new_source', '')
            if not name or not new_source:
                continue
            fn_slice = ast_service.get_function_slice(original, name, path=path)
            if not fn_slice:
                continue
            start = fn_slice['start_line'] - 1  # 0-indexed
            end = fn_slice['end_line']            # exclusive
            edits.append((start, end, new_source))

        if not edits:
            return original

        # Apply bottom-up to preserve indices
        edits.sort(key=lambda e: e[0], reverse=True)
        for start, end, new_source in edits:
            # Ensure new_source ends with newline
            if new_source and not new_source.endswith('\n'):
                new_source += '\n'
            new_lines = new_source.splitlines(keepends=True)
            lines[start:end] = new_lines

        return ''.join(lines)

    def _failure_context(self, failing_result: dict[str, Any]) -> dict[str, Any]:
        data = dict(failing_result.get('data') or {}) if isinstance(failing_result, dict) else {}
        summary = dict(data.get('summary') or {})
        benchmark_parse = dict(summary.get('benchmark_parse') or {})
        result = dict(summary.get('result') or {})
        return {
            'metrics': dict(data.get('metrics') or {}),
            'failing_tests': list(benchmark_parse.get('failing_tests') or []),
            'hinted_paths': list(benchmark_parse.get('hinted_paths') or []),
            'failure_messages': list(benchmark_parse.get('failure_messages') or []),
            'trace_excerpt': str(benchmark_parse.get('trace_excerpt') or ''),
            'stdout': str(result.get('stdout') or '')[:2000],
            'stderr': str(result.get('stderr') or '')[:2000],
        }

    def _expanded_targets(self, plan_data: dict[str, Any], inspection: dict[str, Any], failure_context: dict[str, Any]) -> list[dict[str, Any]]:
        ranked = [dict(t) for t in (plan_data.get('ranked_targets') or []) if isinstance(t, dict)]
        base_targets = [dict(t) for t in (plan_data.get('targets') or []) if isinstance(t, dict)]
        targets = ranked + [t for t in base_targets if str(t.get('path') or '') not in {str(r.get('path') or '') for r in ranked}]
        known_paths = set(inspection.get('file_tree') or [])
        snapshots = dict(inspection.get('snapshots') or {})
        existing = {str(t.get('path') or '') for t in targets}
        for path in failure_context.get('hinted_paths', []):
            if path not in existing:
                targets.append({'path': path, 'reason': 'path extracted from failure trace', 'strategy': 'overwrite'})
                existing.add(path)
        failing_tests = failure_context.get('failing_tests') or []
        for item in failing_tests[:6]:
            candidate = item.split('::', 1)[0]
            if candidate in known_paths and candidate not in existing:
                targets.append({'path': candidate, 'reason': 'failing test identifier from benchmark parse', 'strategy': 'overwrite'})
                existing.add(candidate)
        if not targets and snapshots:
            for path in list(snapshots.keys())[:4]:
                targets.append({'path': path, 'reason': 'inspection snapshot fallback', 'strategy': 'overwrite'})
        return targets

    def _context_excerpt(self, before: str, failure_context: dict[str, Any]) -> str:
        if not before:
            return ''
        symbols = []
        for message in failure_context.get('failure_messages', []):
            symbols.extend(re.findall(r'([A-Za-z_][A-Za-z0-9_]{2,})', message))
        for test_name in failure_context.get('failing_tests', []):
            symbols.extend(re.findall(r'([A-Za-z_][A-Za-z0-9_]{2,})', test_name))
        lines = before.splitlines()
        for symbol in symbols[:10]:
            for idx, line in enumerate(lines):
                if symbol in line:
                    start = max(0, idx - 2)
                    end = min(len(lines), idx + 3)
                    return '\n'.join(lines[start:end])[:1200]
        return '\n'.join(lines[:8])[:1200]

    def _diff_text(self, path: str, before: str, after: str) -> str:
        return ''.join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f'a/{path}',
                tofile=f'b/{path}',
                lineterm='',
            )
        )

    def _python_failure_comment(self, failure_context: dict[str, Any]) -> str:
        messages = failure_context.get('failure_messages') or []
        failing_tests = failure_context.get('failing_tests') or []
        lines = ['# scaffold semantic patch context']
        if messages:
            lines.append(f"# observed failure: {messages[0]}")
        if failing_tests:
            lines.append(f"# failing test: {failing_tests[0]}")
        return '\n'.join(lines) + '\n'

    def _updated_content(self, path: str, before: str, framework: str, target: dict[str, Any], goals: list[str], failure_context: dict[str, Any]) -> str:
        path_l = path.lower()
        framework = framework.lower()
        failure_messages = failure_context.get('failure_messages') or []
        failing_tests = failure_context.get('failing_tests') or []
        hinted_paths = failure_context.get('hinted_paths') or []
        if path_l == 'pytest.ini':
            lines = [line for line in before.splitlines() if line.strip()]
            if not lines:
                lines = ['[pytest]']
            if lines[0].strip() != '[pytest]':
                lines.insert(0, '[pytest]')
            if not any(line.startswith('addopts') for line in lines):
                lines.append('addopts = -q')
            if not any(line.startswith('testpaths') for line in lines) and 'tests/' in str(goals):
                lines.append('testpaths = tests')
            return '\n'.join(lines).rstrip() + '\n'
        if path_l == 'pyproject.toml':
            text = before or '[project]\nname = "repo"\nversion = "0.0.0"\n'
            if '[tool.pytest.ini_options]' not in text:
                text += '\n[tool.pytest.ini_options]\naddopts = "-q"\n'
            return text
        if path_l == 'package.json':
            data = {}
            try:
                data = json.loads(before) if before.strip() else {}
            except Exception:
                data = {'name': 'repo', 'private': True}
            scripts = dict(data.get('scripts') or {})
            if framework == 'vitest':
                scripts['test'] = 'vitest run'
            elif framework == 'jest':
                scripts['test'] = 'jest --runInBand'
            else:
                scripts.setdefault('test', 'node --test')
            data['scripts'] = scripts
            return json.dumps(data, indent=2, sort_keys=True) + '\n'
        if path_l == 'cargo.toml':
            text = before or '[package]\nname = "repo"\nversion = "0.1.0"\nedition = "2021"\n'
            if '[profile.test]' not in text:
                text += '\n[profile.test]\nopt-level = 0\n'
            return text
        if path_l == 'go.mod':
            text = before or 'module example.com/repo\n\ngo 1.22\n'
            if 'go ' not in text:
                text += '\ngo 1.22\n'
            return text
        if path_l.endswith('.py'):
            comment = self._python_failure_comment(failure_context)
            if before:
                if comment.strip() in before:
                    return before
                insert_at = 0
                lines = before.splitlines(keepends=True)
                if lines and lines[0].startswith('#!'):
                    insert_at = 1
                if len(lines) > insert_at and 'coding' in lines[insert_at]:
                    insert_at += 1
                return ''.join(lines[:insert_at]) + comment + ''.join(lines[insert_at:])
            body = comment + ('\n'.join([f'# goal: {g}' for g in goals[:4]]) + '\n' if goals else '')
            body += 'def placeholder_fix():\n    return True\n'
            return body
        if path_l.endswith(('.ts', '.tsx', '.js', '.jsx')):
            note = '// scaffold semantic patch context\n'
            if failure_messages:
                note += f'// observed failure: {failure_messages[0]}\n'
            if failing_tests:
                note += f'// failing test: {failing_tests[0]}\n'
            return before if note.strip() in before else (note + before if before else note + 'export const scaffoldFix = true;\n')
        if path_l.endswith('.rs'):
            note = '// scaffold semantic patch context\n'
            if failure_messages:
                note += f'// observed failure: {failure_messages[0]}\n'
            return before if note.strip() in before else (note + before if before else note + 'pub fn scaffold_fix() -> bool { true }\n')
        if path_l.endswith('.go'):
            note = '// scaffold semantic patch context\n'
            if failure_messages:
                note += f'// observed failure: {failure_messages[0]}\n'
            return before if note.strip() in before else (note + before if before else note + 'package main\n\nfunc scaffoldFix() bool { return true }\n')
        if path_l.endswith('.txt') or path_l.endswith('.md') or path_l == '.':
            base = before
            extra = 'Patch synthesis note:\n- goals: ' + '; '.join(map(str, goals[:5])) + '\n'
            if hinted_paths:
                extra += '- hinted_paths: ' + ', '.join(hinted_paths[:6]) + '\n'
            if failure_messages:
                extra += '- failure: ' + failure_messages[0] + '\n'
            return base + ('\n' if base and not base.endswith('\n') else '') + extra
        if not before:
            header = '# synthesized patch for ' + path + '\n'
            if failure_messages:
                header += '# failure: ' + failure_messages[0] + '\n'
            if failing_tests:
                header += '# failing_test: ' + failing_tests[0] + '\n'
            return header + '# goals: ' + '; '.join(map(str, goals[:5])) + '\n'
        if failure_messages:
            marker = 'scaffold semantic patch context'
            if marker not in before:
                return before + ('\n' if not before.endswith('\n') else '') + f'\n# {marker}: {failure_messages[0]}\n'
        return before


patch_synthesizer_service = PatchSynthesizerService()
