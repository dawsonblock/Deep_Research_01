from __future__ import annotations

import re
from typing import Any


class RepoBenchmarkParserService:
    def parse(self, stdout: str, stderr: str, exit_code: int | None, test_command: str | None = None) -> dict[str, Any]:
        text = "\n".join(part for part in [stdout or '', stderr or ''] if part)
        command = (test_command or '').lower()
        parsers = []
        if 'pytest' in command:
            parsers.append(self._parse_pytest)
        if any(token in command for token in ['python -m unittest', 'unittest']):
            parsers.append(self._parse_unittest)
        if any(token in command for token in ['jest', 'vitest', 'mocha', 'npm test', 'pnpm test', 'yarn test']):
            parsers.append(self._parse_js_test)
        if 'cargo test' in command:
            parsers.append(self._parse_cargo)
        if 'go test' in command:
            parsers.append(self._parse_go_test)
        parsers.extend([
            self._parse_pytest,
            self._parse_unittest,
            self._parse_js_test,
            self._parse_cargo,
            self._parse_go_test,
            self._parse_generic,
        ])
        seen = set()
        for parser in parsers:
            if parser.__name__ in seen:
                continue
            seen.add(parser.__name__)
            parsed = parser(text, exit_code)
            if parsed.get('detected'):
                return self._attach_failure_hints(parsed, text, exit_code)
        return self._attach_failure_hints(self._parse_generic(text, exit_code), text, exit_code)

    def _base(self, framework: str, exit_code: int | None) -> dict[str, Any]:
        return {
            'detected': False,
            'framework': framework,
            'tests_total': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'tests_skipped': 0,
            'duration_seconds': None,
            'benchmark_case_count': 0,
            'benchmark_success_rate': 1.0 if exit_code in (0, None) else 0.0,
            'observations': [],
            'failing_tests': [],
            'hinted_paths': [],
            'failure_messages': [],
            'trace_excerpt': '',
            'stack_frames': [],
        }

    def _finalize(self, item: dict[str, Any], exit_code: int | None) -> dict[str, Any]:
        total = max(0, int(item.get('tests_total', 0) or 0))
        passed = max(0, int(item.get('tests_passed', 0) or 0))
        failed = max(0, int(item.get('tests_failed', 0) or 0))
        skipped = max(0, int(item.get('tests_skipped', 0) or 0))
        if total == 0 and (passed or failed or skipped):
            total = passed + failed + skipped
        item['tests_total'] = total
        if total > 0:
            item['benchmark_success_rate'] = round(max(0.0, min(1.0, passed / max(1, total))), 4)
        else:
            item['benchmark_success_rate'] = 1.0 if exit_code in (0, None) else 0.0
        if exit_code not in (0, None) and failed == 0 and total > 0:
            item['tests_failed'] = max(1, total - passed - skipped)
        return item

    def _attach_failure_hints(self, item: dict[str, Any], text: str, exit_code: int | None) -> dict[str, Any]:
        failing_tests: list[str] = []
        hinted_paths: list[str] = []
        failure_messages: list[str] = []
        stack_frames: list[dict[str, Any]] = []

        for test_name in re.findall(r'^(?:FAILED|ERROR)\s+([A-Za-z0-9_./:\[\]-]+)$', text, re.MULTILINE):
            if test_name not in failing_tests:
                failing_tests.append(test_name)
        for test_name in re.findall(r'^(?:___+\s+)?([A-Za-z0-9_./-]+::[A-Za-z0-9_./:\[\]-]+)', text, re.MULTILINE):
            if test_name not in failing_tests:
                failing_tests.append(test_name)
        for test_name in re.findall(r'^--- FAIL: ([A-Za-z0-9_./-]+)', text, re.MULTILINE):
            if test_name not in failing_tests:
                failing_tests.append(test_name)
        for test_name in re.findall(r'^\s*×\s+([A-Za-z0-9_./ -]+)', text, re.MULTILINE):
            norm = test_name.strip()
            if norm and norm not in failing_tests:
                failing_tests.append(norm)

        path_patterns = [
            r'([A-Za-z0-9_./\\-]+\.(?:py|pyi|js|jsx|ts|tsx|rs|go|java|kt|cpp|cc|c|h|hpp|json|toml|yaml|yml)):(\d+)',
            r'File "([^"]+)", line (\d+)',
            r'-->\s+([A-Za-z0-9_./\\-]+):(\d+):(\d+)',
        ]
        seen_paths = set()
        for pattern in path_patterns:
            for match in re.findall(pattern, text):
                path = match[0].replace('\\', '/')
                if path.startswith('/'):
                    marker = '/repo/'
                    if marker in path:
                        path = path.split(marker, 1)[1]
                    else:
                        path = path.rsplit('/', 1)[-1]
                if path and path not in seen_paths:
                    seen_paths.add(path)
                    hinted_paths.append(path)
                if len(stack_frames) < 12:
                    line = int(match[1]) if len(match) > 1 and str(match[1]).isdigit() else None
                    stack_frames.append({'path': path, 'line': line})

        for pattern in [
            r'Assertion(?:Error)?:?\s+(.+)',
            r'E\s+Assertion(?:Error)?:?\s+(.+)',
            r'assert(?:ion)?\s+failed:?\s+(.+)',
            r'(?:ValueError|TypeError|RuntimeError|KeyError|AttributeError|ImportError|ModuleNotFoundError|NameError|SyntaxError|FileNotFoundError|PermissionError|NotImplementedError|IndentationError|ZeroDivisionError|IndexError|OSError|IOError):\s+(.+)',
        ]:
            for msg in re.findall(pattern, text):
                norm = re.sub(r'\s+', ' ', msg).strip()
                if norm and norm not in failure_messages:
                    failure_messages.append(norm[:240])
                if len(failure_messages) >= 8:
                    break
            if len(failure_messages) >= 8:
                break

        trace_lines = []
        active = False
        for line in text.splitlines():
            stripped = line.rstrip()
            if any(token in stripped for token in ['Traceback (most recent call last):', 'FAILURES', 'short test summary info', 'AssertionError', 'AssertError', 'assert', '--- FAIL:', 'panicked at', 'FAILED']):
                active = True
            if active and stripped:
                trace_lines.append(stripped)
            if active and len(trace_lines) >= 18:
                break
        trace_excerpt = '\n'.join(trace_lines[:18])[:2400]

        item['failing_tests'] = failing_tests[:12]
        item['hinted_paths'] = hinted_paths[:16]
        item['failure_messages'] = failure_messages[:8]
        item['trace_excerpt'] = trace_excerpt
        item['stack_frames'] = stack_frames[:16]
        if (item.get('tests_failed') or exit_code not in (0, None)) and failure_messages:
            item['observations'].append('failure traces parsed from test output')
        return item

    def _parse_pytest(self, text: str, exit_code: int | None) -> dict[str, Any]:
        item = self._base('pytest', exit_code)
        match = re.search(r'=+\s*(.+?)\s+in\s+([0-9.]+)s\s*=+', text, re.IGNORECASE | re.DOTALL)
        if not match:
            return item
        summary, duration = match.group(1), match.group(2)
        counts = {
            'passed': 0,
            'failed': 0,
            'error': 0,
            'errors': 0,
            'skipped': 0,
            'xfailed': 0,
            'xpassed': 0,
        }
        for count, label in re.findall(r'(\d+)\s+([a-zA-Z_]+)', summary):
            label = label.lower()
            if label in counts:
                counts[label] += int(count)
        item.update({
            'detected': True,
            'tests_passed': counts['passed'] + counts['xpassed'],
            'tests_failed': counts['failed'] + counts['error'] + counts['errors'],
            'tests_skipped': counts['skipped'] + counts['xfailed'],
            'duration_seconds': float(duration),
        })
        bench_cases = len(re.findall(r'Benchmark[a-zA-Z0-9_\-]+\s+\d+\s+[0-9.]+\s+ns/op', text))
        if bench_cases:
            item['benchmark_case_count'] = bench_cases
            item['observations'].append('go-style benchmark lines detected in output')
        return self._finalize(item, exit_code)

    def _parse_unittest(self, text: str, exit_code: int | None) -> dict[str, Any]:
        item = self._base('unittest', exit_code)
        match = re.search(r'Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s', text)
        if not match:
            return item
        total = int(match.group(1))
        duration = float(match.group(2))
        failed = 0
        skipped = 0
        fail_m = re.search(r'FAILED\s*\((.*?)\)', text)
        if fail_m:
            parts = fail_m.group(1)
            for key in ['failures', 'errors']:
                m = re.search(key + r'=(\d+)', parts)
                if m:
                    failed += int(m.group(1))
            m = re.search(r'skipped=(\d+)', parts)
            if m:
                skipped += int(m.group(1))
        else:
            ok_m = re.search(r'OK\s*\((.*?)\)', text)
            if ok_m:
                m = re.search(r'skipped=(\d+)', ok_m.group(1))
                if m:
                    skipped += int(m.group(1))
        item.update({
            'detected': True,
            'tests_total': total,
            'tests_failed': failed,
            'tests_skipped': skipped,
            'tests_passed': max(0, total - failed - skipped),
            'duration_seconds': duration,
        })
        return self._finalize(item, exit_code)

    def _parse_js_test(self, text: str, exit_code: int | None) -> dict[str, Any]:
        item = self._base('javascript_test', exit_code)
        tests_line = re.search(r'Tests?:\s*(.+)', text)
        if not tests_line:
            return item
        summary = tests_line.group(1)
        counts = {'passed': 0, 'failed': 0, 'skipped': 0, 'todo': 0, 'total': 0}
        for count, label in re.findall(r'(\d+)\s+([a-zA-Z]+)', summary):
            label = label.lower()
            if label in counts:
                counts[label] = int(count)
        duration = None
        tm = re.search(r'(?:Time|Duration):\s*([0-9.]+)\s*s', text, re.IGNORECASE)
        if tm:
            duration = float(tm.group(1))
        item.update({
            'detected': True,
            'tests_total': counts['total'] or max(0, counts['passed'] + counts['failed'] + counts['skipped'] + counts['todo']),
            'tests_passed': counts['passed'],
            'tests_failed': counts['failed'],
            'tests_skipped': counts['skipped'] + counts['todo'],
            'duration_seconds': duration,
        })
        return self._finalize(item, exit_code)

    def _parse_cargo(self, text: str, exit_code: int | None) -> dict[str, Any]:
        item = self._base('cargo_test', exit_code)
        match = re.search(r'test result:\s*(?:ok|FAILED)\.\s*(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored;\s*(\d+)\s+measured;\s*(\d+)\s+filtered out', text, re.IGNORECASE)
        if not match:
            return item
        passed, failed, ignored, measured, _filtered = map(int, match.groups())
        item.update({
            'detected': True,
            'tests_total': passed + failed + ignored + measured,
            'tests_passed': passed,
            'tests_failed': failed,
            'tests_skipped': ignored,
            'benchmark_case_count': measured,
        })
        return self._finalize(item, exit_code)

    def _parse_go_test(self, text: str, exit_code: int | None) -> dict[str, Any]:
        item = self._base('go_test', exit_code)
        passes = len(re.findall(r'^--- PASS:', text, re.MULTILINE))
        fails = len(re.findall(r'^--- FAIL:', text, re.MULTILINE))
        skips = len(re.findall(r'^--- SKIP:', text, re.MULTILINE))
        bench = len(re.findall(r'^Benchmark\S+', text, re.MULTILINE))
        package_lines = re.findall(r'^(ok|FAIL)\s+\S+\s+([0-9.]+)s', text, re.MULTILINE)
        if not (passes or fails or skips or package_lines or bench):
            return item
        duration = None
        if package_lines:
            duration = sum(float(x[1]) for x in package_lines)
        item.update({
            'detected': True,
            'tests_total': max(0, passes + fails + skips),
            'tests_passed': passes,
            'tests_failed': fails,
            'tests_skipped': skips,
            'benchmark_case_count': bench,
            'duration_seconds': duration,
        })
        return self._finalize(item, exit_code)

    def _parse_generic(self, text: str, exit_code: int | None) -> dict[str, Any]:
        item = self._base('generic', exit_code)
        for label, attr in [('passed', 'tests_passed'), ('failed', 'tests_failed'), ('skipped', 'tests_skipped')]:
            for count in re.findall(r'(\d+)\s+' + label, text, re.IGNORECASE):
                item[attr] += int(count)
        bench = len(re.findall(r'Benchmark\S+\s+\d+\s+[0-9.]+\s+ns/op', text))
        item['benchmark_case_count'] = bench
        duration_match = re.search(r'([0-9.]+)s', text)
        if duration_match:
            try:
                item['duration_seconds'] = float(duration_match.group(1))
            except Exception:
                item['duration_seconds'] = None
        if item['tests_passed'] or item['tests_failed'] or item['tests_skipped'] or bench or exit_code not in (0, None):
            item['detected'] = True
        return self._finalize(item, exit_code)


repo_benchmark_parser_service = RepoBenchmarkParserService()
