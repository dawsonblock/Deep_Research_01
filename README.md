# Research Engine Scaffold

A compact local scaffold for a persistent research runtime.

It includes:

- typed artifacts with validation and scoring
- artifact lineage and revision history
- task and execution graphs
- world model with claims, questions, and hypotheses
- embedding-backed memory distillation and retrieval
- SearXNG sidecar client for external search
- project state, milestones, and checkpoints
- compression and replanning loops
- experiment planning, execution, and evaluation
- optional LLM adapter behind a single service boundary
- FastAPI API

This is a working scaffold, not a production-grade autonomous system.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API.

## Suggested flow

1. `POST /projects`
2. `POST /projects/{project_id}/bootstrap`
3. `POST /projects/{project_id}/run-until-idle`
4. `POST /projects/{project_id}/replan`
5. `POST /projects/{project_id}/run-until-idle`
6. `GET /projects/{project_id}/experiments`
7. `GET /projects/{project_id}/artifacts`
8. `POST /projects/{project_id}/compress`
9. `GET /projects/{project_id}/summary`

## Artifact versioning

Artifacts now carry:

- `lineage_id`
- `version`
- `revision_note`

You can:

- revise an artifact with `POST /artifacts/revise`
- inspect a lineage with `GET /artifacts/{artifact_id}/lineage`

## Experiment loop

Experiment planning creates an `experiment_plan` artifact.
When one is produced, the runtime automatically schedules:

- an `experiment_runner` node
- an `evaluator` node

Experiment runs are persisted in `experiment_runs` and exposed at:

- `GET /projects/{project_id}/experiments`

The default runner is deterministic and grounded in current project state. It does not execute external benchmarks or shell commands.

## Optional sidecars

### SearXNG
Set `SEARXNG_BASE_URL` in `.env` if you run a SearXNG server separately.

### LLM provider
The scaffold keeps a single adapter boundary in `backend/services/llm.py`.
Set these variables if you want model-backed operators:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_MODEL=gpt-4.1-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

Without those, the runtime uses deterministic local fallbacks and hash-vector embeddings.

## Current limits

- experiment execution is still an internal project-state benchmark, not a real lab harness
- artifact revisions are versioned, but merge/conflict resolution is still manual
- operator planning remains heuristic even when an LLM adapter is enabled


## OpenSandbox integration

This build now includes an optional OpenSandbox-backed harness for real experiment execution.

What it adds:
- sandbox status endpoint: `GET /sandbox/status`
- ad hoc sandbox execution: `POST /projects/{project_id}/sandbox/run`
- experiment plans can carry a `job` block with `runner=opensandbox`
- `experiment_runner` dispatches to OpenSandbox when configured, otherwise falls back cleanly

Environment variables:
- `OPENSANDBOX_ENABLED`
- `OPEN_SANDBOX_DOMAIN`
- `OPEN_SANDBOX_API_KEY`
- `OPEN_SANDBOX_PROTOCOL`
- `OPEN_SANDBOX_TIMEOUT_SECONDS`
- `OPEN_SANDBOX_USE_SERVER_PROXY`
- `OPEN_SANDBOX_DEFAULT_IMAGE`
- `OPEN_SANDBOX_PYTHON_IMAGE`

Notes:
- the SDK is optional at import time; the scaffold still runs without it
- the harness is isolated behind `backend/services/sandbox_harness.py`
- OpenSandbox is used as a sidecar execution substrate, not merged into the control-plane core


## Sandbox session and repo test support

This build adds persistent OpenSandbox session records, direct command execution, artifact materialization, and repo clone/install/test evaluation through API routes.


## Persistent sandbox workspace lineage mapping

This version adds a stable workspace mapping from artifact lineages to sandbox filesystem paths.

What it does:
- each artifact lineage gets a persistent workspace root inside a sandbox session
- latest revisions are written to `current.json`
- versioned snapshots are written under `versions/vN.json`
- a manifest is written per lineage

New routes:
- `GET /sandbox/sessions/{session_id}/workspace-lineages`
- `POST /sandbox/sessions/{session_id}/sync-lineages`

## Automatic repo benchmark parsing

Repo evaluation now parses common test and benchmark output formats automatically.

Current parsers include:
- pytest
- unittest
- jest/vitest-style summaries
- cargo test
- go test
- generic fallback parser

Repo-eval responses now include:
- `benchmark_parse`
- parsed test counts
- benchmark case count
- benchmark success rate


## v7 upgrades

- repository inspection before repo profile inference
- repo inspection API and artifact type
- unified-diff patch synthesis with before/after snapshots
- patch artifacts now carry `patch_text`, `diff`, and `before_content`
