# Refactor Baseline

Recorded at the start of the `runtime-unification` branch to document canonical module locations before refactoring.

## Active Entrypoints

| Role | File |
|------|------|
| API entrypoint | `backend/main.py` |
| Execution entrypoint | `backend/services/execution.py` |
| Planner entrypoint | `backend/services/planner.py` |
| Sandbox entrypoint | `backend/services/sandbox_harness.py` |

## Current Canonical Runtime Modules

These are the authoritative implementations that all other code should delegate to:

- `research_engine/core/runtime/artifact_validator.py`
- `research_engine/core/runtime/postcondition_verifier.py`
- `research_engine/core/runtime/run_registry.py`
- `research_engine/core/runtime/verified_executor.py`

## Test Baseline

| Metric | Value |
|--------|-------|
| Total tests | 225 |
| Passing | 225 |
| Failing | 0 |
| Framework | pytest |
| Command | `PYTHONPATH=. python -m pytest tests/ -q` |
