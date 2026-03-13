from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any

from backend.config import get_settings


class FailureAnalysisService:
    def analyze(self, inspection: dict[str, Any] | None, benchmark_parse: dict[str, Any] | None, repo_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = get_settings()
        inspection = inspection or {}
        benchmark_parse = benchmark_parse or {}
        repo_profile = repo_profile or {}
        file_tree = list(inspection.get("file_tree") or [])
        snapshots = dict(inspection.get("snapshots") or {})
        hinted_paths = [str(p) for p in (benchmark_parse.get("hinted_paths") or []) if p]
        failing_tests = [str(t) for t in (benchmark_parse.get("failing_tests") or []) if t]
        failure_messages = [str(m) for m in (benchmark_parse.get("failure_messages") or []) if m]
        stack_frames = [dict(frame) for frame in (benchmark_parse.get("stack_frames") or []) if isinstance(frame, dict)]
        trace_excerpt = str(benchmark_parse.get("trace_excerpt") or "")

        derived_symbols = self._derive_symbols(failing_tests, failure_messages, trace_excerpt, stack_frames)

        # Use AST-based symbol index when available, fall back to regex
        symbol_index = self._build_symbol_index_ast(snapshots)

        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)
        symbol_matches: dict[str, list[dict[str, Any]]] = defaultdict(list)

        known_paths = set(file_tree) | set(snapshots.keys())

        # Configurable scoring weights
        w_hinted = settings.blame_weight_hinted_path
        w_stack = settings.blame_weight_stack_frame
        w_symbol = settings.blame_weight_symbol_match
        w_fail_test = settings.blame_weight_failing_test
        w_related = settings.blame_weight_related_source
        w_config = settings.blame_weight_config_file
        w_fallback = settings.blame_weight_fallback

        for path in hinted_paths:
            self._bump(scores, reasons, path, w_hinted, 'path extracted from failure trace')
        for frame in stack_frames:
            path = str(frame.get('path') or '')
            line = frame.get('line')
            if path:
                self._bump(scores, reasons, path, w_stack, f'stack frame hit at line {line}' if line else 'stack frame hit')

        for test_name in failing_tests:
            candidate = test_name.split('::', 1)[0].strip()
            if candidate in known_paths:
                self._bump(scores, reasons, candidate, w_fail_test, 'failing test file')
            related = self._related_source_candidates(candidate, file_tree)
            for rel in related:
                self._bump(scores, reasons, rel, w_related, f'related source for failing test {candidate}')

        for symbol in derived_symbols:
            matches = symbol_index.get(symbol.lower(), [])
            for match in matches:
                path = str(match.get('path') or '')
                if not path:
                    continue
                self._bump(scores, reasons, path, w_symbol, f'symbol match for {symbol}')
                symbol_matches[path].append(match)

        framework = str(repo_profile.get('framework') or inspection.get('detected_framework') or 'generic').lower()
        config_candidates = []
        if framework == 'pytest':
            config_candidates = ['pytest.ini', 'pyproject.toml', 'tox.ini']
        elif framework in {'jest', 'vitest', 'node'}:
            config_candidates = ['package.json', 'vitest.config.ts', 'vitest.config.js', 'jest.config.ts', 'jest.config.js', 'tsconfig.json']
        elif framework == 'cargo':
            config_candidates = ['Cargo.toml']
        elif framework == 'go_test':
            config_candidates = ['go.mod']
        for candidate in config_candidates:
            if candidate in known_paths:
                self._bump(scores, reasons, candidate, w_config, f'{framework} configuration file')

        if not scores:
            for path in list(snapshots.keys())[:6] or file_tree[:6]:
                self._bump(scores, reasons, path, w_fallback, 'fallback ranked target')

        ranked_targets = []
        for path, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
            ranked_targets.append({
                'path': path,
                'score': round(float(score), 4),
                'blame_score': round(float(score), 4),
                'blame_reasons': reasons.get(path, [])[:6],
                'symbol_matches': symbol_matches.get(path, [])[:8],
                'strategy': 'overwrite',
                'context_excerpt': self._excerpt_for_path(path, snapshots.get(path, ''), symbol_matches.get(path, []), trace_excerpt),
            })

        return {
            'derived_symbols': derived_symbols[:settings.blame_max_derived_symbols],
            'ranked_targets': ranked_targets[:settings.blame_max_ranked_targets],
            'symbol_map': {path: matches[:8] for path, matches in symbol_matches.items()},
            'trace_excerpt': trace_excerpt[:2000],
        }

    def _bump(self, scores: dict[str, float], reasons: dict[str, list[str]], path: str, score: float, reason: str) -> None:
        norm_path = path.replace('\\', '/').strip()
        if not norm_path:
            return
        scores[norm_path] += float(score)
        if reason not in reasons[norm_path]:
            reasons[norm_path].append(reason)

    def _derive_symbols(self, failing_tests: list[str], failure_messages: list[str], trace_excerpt: str, stack_frames: list[dict[str, Any]]) -> list[str]:
        symbols: list[str] = []
        candidates = []
        candidates.extend(failing_tests)
        candidates.extend(failure_messages)
        candidates.append(trace_excerpt)
        candidates.extend([str(frame.get('path') or '') for frame in stack_frames])
        name_patterns = [
            r'([A-Za-z_][A-Za-z0-9_]{2,})',
        ]
        skip = {'assertionerror', 'traceback', 'failed', 'error', 'expect', 'received', 'tests', 'test', 'line', 'file'}
        for text in candidates:
            for pattern in name_patterns:
                for token in re.findall(pattern, text):
                    token_l = token.lower()
                    if token_l in skip or token_l.isdigit():
                        continue
                    if token_l.endswith(('test', 'spec')) and len(token_l) <= 5:
                        continue
                    if token_l not in [s.lower() for s in symbols]:
                        symbols.append(token)
        return symbols

    def _build_symbol_index_ast(self, snapshots: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
        """Build symbol index using AST-based parsing (falls back to regex)."""
        try:
            from backend.services.ast_analysis import ast_analysis_service
            index = ast_analysis_service.build_symbol_index(snapshots)
            if index:
                return index
        except Exception:
            pass
        # Fallback to regex-based scanning
        return self._build_symbol_index_regex(snapshots)

    def _build_symbol_index_regex(self, snapshots: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
        """Legacy regex-based symbol index (fallback when AST parsing fails)."""
        index: dict[str, list[dict[str, Any]]] = defaultdict(list)
        patterns = [
            re.compile(r'^\s*(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE),
            re.compile(r'^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE),
            re.compile(r'^\s*(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE),
            re.compile(r'^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(', re.MULTILINE),
            re.compile(r'^\s*(?:pub\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE),
            re.compile(r'^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE),
        ]
        for path, content in snapshots.items():
            if not isinstance(content, str):
                continue
            lines = content.splitlines()
            for pattern in patterns:
                for match in pattern.finditer(content):
                    symbol = match.group(1)
                    line_no = content[: match.start()].count('\n') + 1
                    excerpt = '\n'.join(lines[max(0, line_no - 3): min(len(lines), line_no + 2)])[:1200]
                    index[symbol.lower()].append({
                        'symbol': symbol,
                        'path': path,
                        'line': line_no,
                        'excerpt': excerpt,
                    })
        return index

    def _related_source_candidates(self, candidate: str, file_tree: list[str]) -> list[str]:
        if not candidate:
            return []
        rels: list[str] = []
        base = os.path.basename(candidate)
        root, ext = os.path.splitext(base)
        variants = {root}
        for prefix in ('test_', 'spec_', 'tests_'):
            if root.startswith(prefix):
                variants.add(root[len(prefix):])
        for suffix in ('_test', '_spec', '.test', '.spec'):
            if root.endswith(suffix):
                variants.add(root[: -len(suffix)])
        for path in file_tree:
            pbase = os.path.basename(path)
            proot, pext = os.path.splitext(pbase)
            if proot in variants and path != candidate:
                rels.append(path)
            elif any(v and v in proot for v in variants) and path != candidate:
                rels.append(path)
        return rels[:6]

    def _excerpt_for_path(self, path: str, content: str, matches: list[dict[str, Any]], trace_excerpt: str) -> str:
        # Prefer AST-derived source from symbol matches
        for match in matches:
            source = match.get('source') or match.get('excerpt') or ''
            if source:
                return str(source)[:1200]
        if content:
            # Try to get a meaningful slice via AST for the first symbol we find
            try:
                from backend.services.ast_analysis import ast_analysis_service
                slices = ast_analysis_service.get_all_slices(content, path=path)
                if slices:
                    return str(slices[0].get('source', ''))[:1200]
            except Exception:
                pass
            return '\n'.join(content.splitlines()[:10])[:1200]
        return trace_excerpt[:1200]


failure_analysis_service = FailureAnalysisService()
