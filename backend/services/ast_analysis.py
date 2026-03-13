"""AST-aware symbol extraction and function-level slicing.

Uses Python's ``ast`` module for .py files and enhanced regex + bracket
counting for JS/TS/Rust/Go.  Optionally delegates to ``tree-sitter`` when
the ``AST_USE_TREE_SITTER`` config flag is set and the package is installed.

Public surface
--------------
``ast_analysis_service``  – module-level singleton of :class:`ASTAnalysisService`.

Key methods:
    ``get_symbols(content, language)``       → list of SymbolInfo dicts
    ``get_function_slice(content, symbol, language)`` → FunctionSlice | None
    ``get_all_slices(content, language)``    → list of FunctionSlice dicts
    ``detect_language(path)``                → language key string
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
from typing import Any

from backend.config import get_settings


# ---------------------------------------------------------------------------
# Type aliases (plain dicts – avoids Pydantic import for a service-layer util)
# ---------------------------------------------------------------------------
SymbolInfo = dict[str, Any]
# keys: name, kind, start_line, end_line, parent, source, language

FunctionSlice = dict[str, Any]
# keys: name, kind, start_line, end_line, source, parent, language


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
_EXT_TO_LANG: dict[str, str] = {
    '.py': 'python',
    '.pyi': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.rs': 'rust',
    '.go': 'go',
}


class ASTAnalysisService:
    """Language-aware AST parsing and symbol extraction."""

    # ---- public API -------------------------------------------------------

    def detect_language(self, path: str) -> str:
        """Return a canonical language key for *path*, or ``'unknown'``."""
        _, ext = os.path.splitext(path.lower())
        return _EXT_TO_LANG.get(ext, 'unknown')

    def get_symbols(self, content: str, language: str | None = None, path: str | None = None) -> list[SymbolInfo]:
        """Return all top-level and nested symbols found in *content*.

        If *language* is ``None`` it is inferred from *path*.
        """
        language = language or (self.detect_language(path) if path else 'unknown')
        settings = get_settings()
        max_syms = settings.ast_max_symbols_per_file

        if settings.ast_use_tree_sitter and self._tree_sitter_available():
            try:
                return self._tree_sitter_symbols(content, language)[:max_syms]
            except Exception:
                pass  # fall through to built-in parsers

        dispatch = {
            'python': self._python_symbols,
            'javascript': self._js_ts_symbols,
            'typescript': self._js_ts_symbols,
            'rust': self._rust_symbols,
            'go': self._go_symbols,
        }
        parser = dispatch.get(language, self._regex_fallback_symbols)
        return parser(content, language)[:max_syms]

    def get_function_slice(
        self,
        content: str,
        symbol_name: str,
        language: str | None = None,
        path: str | None = None,
    ) -> FunctionSlice | None:
        """Return the source slice for the *first* symbol matching *symbol_name*."""
        symbols = self.get_symbols(content, language=language, path=path)
        for sym in symbols:
            if sym['name'] == symbol_name:
                return self._to_slice(sym)
        # Try case-insensitive as fallback
        name_l = symbol_name.lower()
        for sym in symbols:
            if sym['name'].lower() == name_l:
                return self._to_slice(sym)
        return None

    def get_all_slices(self, content: str, language: str | None = None, path: str | None = None) -> list[FunctionSlice]:
        """Return slices for every symbol in *content*."""
        return [self._to_slice(s) for s in self.get_symbols(content, language=language, path=path)]

    def build_symbol_index(self, snapshots: dict[str, str]) -> dict[str, list[SymbolInfo]]:
        """Build a ``{lowered_name: [SymbolInfo, …]}`` index over all *snapshots*.

        This is a drop-in replacement for ``FailureAnalysisService._build_symbol_index``
        but with proper AST parsing instead of single-line regex.
        """
        from collections import defaultdict
        index: dict[str, list[SymbolInfo]] = defaultdict(list)
        for path, content in snapshots.items():
            if not isinstance(content, str) or not content.strip():
                continue
            lang = self.detect_language(path)
            if lang == 'unknown':
                continue
            try:
                symbols = self.get_symbols(content, language=lang, path=path)
            except Exception:
                continue
            for sym in symbols:
                key = sym['name'].lower()
                sym_copy = dict(sym)
                sym_copy['path'] = path
                index[key].append(sym_copy)
        return dict(index)

    # ---- Python (ast module) ----------------------------------------------

    def _python_symbols(self, content: str, language: str) -> list[SymbolInfo]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._regex_fallback_symbols(content, language)
        lines = content.splitlines()
        symbols: list[SymbolInfo] = []
        self._walk_python_node(tree, lines, symbols, parent=None)
        return symbols

    def _walk_python_node(self, node: ast.AST, lines: list[str], symbols: list[SymbolInfo], parent: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = child.lineno
                end = self._python_end_line(child, lines)
                kind = 'method' if parent else 'function'
                source = '\n'.join(lines[start - 1:end])
                symbols.append({
                    'name': child.name,
                    'kind': kind,
                    'start_line': start,
                    'end_line': end,
                    'parent': parent,
                    'source': source[:self._max_slice_chars()],
                    'language': 'python',
                })
                # Recurse into function body for nested defs
                self._walk_python_node(child, lines, symbols, parent=child.name)
            elif isinstance(child, ast.ClassDef):
                start = child.lineno
                end = self._python_end_line(child, lines)
                source = '\n'.join(lines[start - 1:end])
                symbols.append({
                    'name': child.name,
                    'kind': 'class',
                    'start_line': start,
                    'end_line': end,
                    'parent': parent,
                    'source': source[:self._max_slice_chars()],
                    'language': 'python',
                })
                # Recurse into class body for methods
                self._walk_python_node(child, lines, symbols, parent=child.name)

    @staticmethod
    def _python_end_line(node: ast.AST, lines: list[str]) -> int:
        """Compute the last line of an AST node, using end_lineno if available (3.8+)."""
        if hasattr(node, 'end_lineno') and node.end_lineno is not None:
            return node.end_lineno
        # Fallback: walk children to find the max lineno
        max_line = getattr(node, 'lineno', 1)
        for child in ast.walk(node):
            ln = getattr(child, 'end_lineno', None) or getattr(child, 'lineno', None)
            if ln and ln > max_line:
                max_line = ln
        return min(max_line, len(lines))

    # ---- JS / TS (regex + bracket counting) -------------------------------

    _JS_TS_DEF_RE = re.compile(
        r'(?P<indent>[ \t]*)'
        r'(?:export\s+)?(?:default\s+)?'
        r'(?:'
        r'(?:async\s+)?function\s*\*?\s*(?P<func>[A-Za-z_$][A-Za-z0-9_$]*)'
        r'|class\s+(?P<cls>[A-Za-z_$][A-Za-z0-9_$]*)'
        r'|(?:const|let|var)\s+(?P<arrow>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\('
        r'|(?P<method>[A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{'
        r')',
        re.MULTILINE,
    )

    def _js_ts_symbols(self, content: str, language: str) -> list[SymbolInfo]:
        lines = content.splitlines()
        symbols: list[SymbolInfo] = []
        for m in self._JS_TS_DEF_RE.finditer(content):
            name = m.group('func') or m.group('cls') or m.group('arrow') or m.group('method')
            if not name:
                continue
            kind = 'class' if m.group('cls') else 'function'
            start = content[:m.start()].count('\n') + 1
            end = self._bracket_end(lines, start - 1)
            source = '\n'.join(lines[start - 1:end])
            symbols.append({
                'name': name,
                'kind': kind,
                'start_line': start,
                'end_line': end,
                'parent': None,
                'source': source[:self._max_slice_chars()],
                'language': language,
            })
        return symbols

    # ---- Rust (regex + bracket counting) ----------------------------------

    _RUST_DEF_RE = re.compile(
        r'^[ \t]*(?:pub(?:\s*\([^)]*\))?\s+)?'
        r'(?:'
        r'(?:async\s+)?fn\s+(?P<func>[A-Za-z_][A-Za-z0-9_]*)'
        r'|struct\s+(?P<struct>[A-Za-z_][A-Za-z0-9_]*)'
        r'|enum\s+(?P<enum>[A-Za-z_][A-Za-z0-9_]*)'
        r'|impl(?:<[^>]*>)?\s+(?P<impl>[A-Za-z_][A-Za-z0-9_]*)'
        r'|trait\s+(?P<trait>[A-Za-z_][A-Za-z0-9_]*)'
        r')',
        re.MULTILINE,
    )

    def _rust_symbols(self, content: str, language: str) -> list[SymbolInfo]:
        lines = content.splitlines()
        symbols: list[SymbolInfo] = []
        for m in self._RUST_DEF_RE.finditer(content):
            name = m.group('func') or m.group('struct') or m.group('enum') or m.group('impl') or m.group('trait')
            if not name:
                continue
            kind = 'function' if m.group('func') else ('struct' if m.group('struct') else ('enum' if m.group('enum') else ('impl' if m.group('impl') else 'trait')))
            start = content[:m.start()].count('\n') + 1
            end = self._bracket_end(lines, start - 1)
            source = '\n'.join(lines[start - 1:end])
            symbols.append({
                'name': name,
                'kind': kind,
                'start_line': start,
                'end_line': end,
                'parent': None,
                'source': source[:self._max_slice_chars()],
                'language': 'rust',
            })
        return symbols

    # ---- Go (regex + bracket counting) ------------------------------------

    _GO_DEF_RE = re.compile(
        r'^(?:'
        r'func\s+(?:\([^)]+\)\s*)?(?P<func>[A-Za-z_][A-Za-z0-9_]*)'
        r'|type\s+(?P<type>[A-Za-z_][A-Za-z0-9_]*)\s+(?:struct|interface)'
        r')',
        re.MULTILINE,
    )

    def _go_symbols(self, content: str, language: str) -> list[SymbolInfo]:
        lines = content.splitlines()
        symbols: list[SymbolInfo] = []
        for m in self._GO_DEF_RE.finditer(content):
            name = m.group('func') or m.group('type')
            if not name:
                continue
            kind = 'function' if m.group('func') else 'type'
            start = content[:m.start()].count('\n') + 1
            end = self._bracket_end(lines, start - 1)
            source = '\n'.join(lines[start - 1:end])
            symbols.append({
                'name': name,
                'kind': kind,
                'start_line': start,
                'end_line': end,
                'parent': None,
                'source': source[:self._max_slice_chars()],
                'language': 'go',
            })
        return symbols

    # ---- generic regex fallback -------------------------------------------

    _GENERIC_DEF_RE = re.compile(
        r'^\s*(?:export\s+)?(?:pub\s+)?(?:async\s+)?'
        r'(?:def|fn|func|function|class|struct|enum|trait|impl|type|interface|const|let|var)\s+'
        r'([A-Za-z_$][A-Za-z0-9_$]*)',
        re.MULTILINE,
    )

    def _regex_fallback_symbols(self, content: str, language: str) -> list[SymbolInfo]:
        lines = content.splitlines()
        symbols: list[SymbolInfo] = []
        for m in self._GENERIC_DEF_RE.finditer(content):
            name = m.group(1)
            start = content[:m.start()].count('\n') + 1
            end = min(start + 20, len(lines))  # rough estimate
            source = '\n'.join(lines[start - 1:end])
            symbols.append({
                'name': name,
                'kind': 'definition',
                'start_line': start,
                'end_line': end,
                'parent': None,
                'source': source[:self._max_slice_chars()],
                'language': language,
            })
        return symbols

    # ---- bracket counting utility -----------------------------------------

    @staticmethod
    def _bracket_end(lines: list[str], start_idx: int) -> int:
        """Find the line where braces/indentation ends for a block starting at *start_idx*.

        Uses ``{`` / ``}`` counting.  Falls back to start + 30 if no braces.
        """
        max_lines = get_settings().ast_max_slice_lines
        depth = 0
        opened = False
        for i in range(start_idx, min(start_idx + max_lines, len(lines))):
            for ch in lines[i]:
                if ch == '{':
                    depth += 1
                    opened = True
                elif ch == '}':
                    depth -= 1
            if opened and depth <= 0:
                return i + 1  # 1-indexed
        return min(start_idx + 30 + 1, len(lines))

    # ---- tree-sitter (optional) -------------------------------------------

    @staticmethod
    def _tree_sitter_available() -> bool:
        return importlib.util.find_spec('tree_sitter') is not None

    def _tree_sitter_symbols(self, content: str, language: str) -> list[SymbolInfo]:
        """Parse using tree-sitter if the correct language grammar is installed."""
        # Lazy import so the rest of the module works without tree-sitter
        import tree_sitter_languages  # type: ignore[import-untyped]
        from tree_sitter import Parser  # type: ignore[import-untyped]

        lang_map = {
            'python': 'python',
            'javascript': 'javascript',
            'typescript': 'typescript',
            'rust': 'rust',
            'go': 'go',
        }
        ts_lang_name = lang_map.get(language)
        if not ts_lang_name:
            return self._regex_fallback_symbols(content, language)

        ts_language = tree_sitter_languages.get_language(ts_lang_name)
        parser = Parser()
        parser.set_language(ts_language)
        tree = parser.parse(content.encode())
        lines = content.splitlines()
        symbols: list[SymbolInfo] = []
        self._walk_tree_sitter(tree.root_node, lines, symbols, language, parent=None)
        return symbols

    _TS_SYMBOL_TYPES = {
        'function_definition', 'function_declaration', 'async_function_declaration',
        'method_definition', 'class_definition', 'class_declaration',
        'function_item', 'impl_item', 'struct_item', 'enum_item', 'trait_item',
        'function_declaration',  # Go
        'type_declaration',
        'arrow_function',
        'variable_declarator',
    }

    def _walk_tree_sitter(self, node, lines: list[str], symbols: list[SymbolInfo], language: str, parent: str | None) -> None:
        if node.type in self._TS_SYMBOL_TYPES:
            name = None
            kind = 'function'
            for child in node.children:
                if child.type in ('identifier', 'name', 'type_identifier', 'property_identifier'):
                    name = child.text.decode()
                    break
            if name:
                if 'class' in node.type:
                    kind = 'class'
                elif 'struct' in node.type:
                    kind = 'struct'
                elif 'impl' in node.type:
                    kind = 'impl'
                elif 'trait' in node.type:
                    kind = 'trait'
                elif 'enum' in node.type:
                    kind = 'enum'
                elif 'type' in node.type:
                    kind = 'type'
                elif 'method' in node.type:
                    kind = 'method'
                start = node.start_point[0] + 1
                end = node.end_point[0] + 1
                source = '\n'.join(lines[start - 1:end])
                symbols.append({
                    'name': name,
                    'kind': kind,
                    'start_line': start,
                    'end_line': end,
                    'parent': parent,
                    'source': source[:self._max_slice_chars()],
                    'language': language,
                })
                parent = name
        for child in node.children:
            self._walk_tree_sitter(child, lines, symbols, language, parent)

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _to_slice(sym: SymbolInfo) -> FunctionSlice:
        return {
            'name': sym['name'],
            'kind': sym['kind'],
            'start_line': sym['start_line'],
            'end_line': sym['end_line'],
            'source': sym.get('source', ''),
            'parent': sym.get('parent'),
            'language': sym.get('language', 'unknown'),
        }

    @staticmethod
    def _max_slice_chars() -> int:
        try:
            return get_settings().ast_max_slice_lines * 120
        except Exception:
            return 24_000


ast_analysis_service = ASTAnalysisService()
