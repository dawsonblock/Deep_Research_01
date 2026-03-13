from __future__ import annotations

from typing import Any

from backend.utils import normalize_text


class ValidationService:
    def validate(self, artifact_type: str, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        validator = getattr(self, f'_validate_{artifact_type}', self._validate_default)
        status, score, details = validator(data)
        return status, float(max(0.0, min(1.0, score))), details

    def _validate_default(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        ok = bool(data)
        return ('pass' if ok else 'fail', 0.6 if ok else 0.0, {'reason': 'non-empty object required'})

    def _validate_summary(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        text = normalize_text(str(data.get('text', '')))
        if not text:
            return 'fail', 0.0, {'reason': 'summary.text missing'}
        score = 0.8 if len(text) >= 40 else 0.45
        return ('pass' if score >= 0.45 else 'fail', score, {'length': len(text)})

    def _validate_evidence(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        items = data.get('items', [])
        if not isinstance(items, list) or not items:
            return 'fail', 0.0, {'reason': 'evidence.items must be a non-empty list'}
        score = min(1.0, 0.3 + 0.1 * len(items))
        return 'pass', score, {'count': len(items)}

    def _validate_requirements(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        items = data.get('items', [])
        if not isinstance(items, list) or len(items) < 2:
            return 'fail', 0.2, {'reason': 'need at least 2 requirements'}
        unique = len(set(map(str, items)))
        score = min(1.0, 0.4 + 0.1 * unique)
        return 'pass', score, {'count': len(items), 'unique_count': unique}

    def _validate_architecture(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        components = data.get('components', [])
        if not isinstance(components, list) or len(components) < 3:
            return 'fail', 0.2, {'reason': 'need at least 3 components'}
        score = min(1.0, 0.4 + 0.08 * len(components))
        return 'pass', score, {'count': len(components)}

    def _validate_critique(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        issues = data.get('issues', [])
        if not isinstance(issues, list):
            return 'fail', 0.0, {'reason': 'issues must be a list'}
        score = 0.7 if issues else 0.5
        return 'pass', score, {'count': len(issues)}

    def _validate_task_list(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        tasks = data.get('tasks', [])
        if not isinstance(tasks, list) or not tasks:
            return 'fail', 0.0, {'reason': 'tasks required'}
        return 'pass', min(1.0, 0.4 + 0.08 * len(tasks)), {'count': len(tasks)}

    def _validate_hypothesis(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        statement = normalize_text(str(data.get('statement', '')))
        prediction = normalize_text(str(data.get('prediction', '')))
        ok = bool(statement and prediction)
        return ('pass' if ok else 'fail', 0.75 if ok else 0.0, {'has_statement': bool(statement), 'has_prediction': bool(prediction)})

    def _validate_experiment_plan(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        steps = data.get('steps', [])
        ok = isinstance(steps, list) and len(steps) >= 2
        return ('pass' if ok else 'fail', 0.8 if ok else 0.2, {'count': len(steps) if isinstance(steps, list) else 0})

    def _validate_experiment_result(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        metrics = data.get('metrics', {})
        ok = isinstance(metrics, dict) and bool(metrics)
        return ('pass' if ok else 'fail', 0.85 if ok else 0.0, {'metric_count': len(metrics) if isinstance(metrics, dict) else 0})

    def _validate_evaluation(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        verdict = normalize_text(str(data.get('verdict', '')))
        ok = bool(verdict)
        return ('pass' if ok else 'fail', 0.75 if ok else 0.0, {'verdict': verdict})

    def _validate_memory_summary(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        text = normalize_text(str(data.get('text', '')))
        ok = bool(text)
        return ('pass' if ok else 'fail', 0.7 if ok else 0.0, {'length': len(text)})

    def _validate_repo_inspection(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        files = data.get('file_tree', [])
        ok = isinstance(files, list) and bool(files)
        return ('pass' if ok else 'fail', 0.82 if ok else 0.25, {'file_count': len(files) if isinstance(files, list) else 0, 'framework': data.get('detected_framework')})

    def _validate_repo_profile(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        required = [str(data.get('name', '')).strip(), str(data.get('framework', '')).strip(), str(data.get('test_command', '')).strip()]
        ok = all(required)
        return ('pass' if ok else 'fail', 0.78 if ok else 0.15, {'has_name': bool(required[0]), 'has_framework': bool(required[1]), 'has_test_command': bool(required[2])})

    def _validate_code_patch_plan(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        targets = data.get('targets', [])
        ok = isinstance(targets, list) and bool(targets)
        return ('pass' if ok else 'fail', 0.74 if ok else 0.2, {'target_count': len(targets) if isinstance(targets, list) else 0})

    def _validate_code_patch(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        patches = data.get('file_patches', [])
        patch_text = str(data.get('patch_text', '')).strip()
        ok = (isinstance(patches, list) and bool(patches)) or bool(patch_text)
        score = 0.85 if ok and patch_text else (0.78 if ok else 0.2)
        return ('pass' if ok else 'fail', score, {'patch_count': len(patches) if isinstance(patches, list) else 0, 'has_patch_text': bool(patch_text)})

    def _validate_patch_test_result(self, data: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        metrics = data.get('metrics', {})
        ok = isinstance(metrics, dict) and bool(metrics)
        return ('pass' if ok else 'fail', 0.82 if ok else 0.2, {'metric_count': len(metrics) if isinstance(metrics, dict) else 0})


validation_service = ValidationService()
