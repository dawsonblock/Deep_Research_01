# Runtime Baseline

Recorded at the start of the `runtime_unification` branch to lock the current behaviour before refactoring begins.

## Test Baseline

| Metric | Value |
|--------|-------|
| Total tests | 225 |
| Passing | 225 |
| Failing | 0 |
| Framework | pytest |
| Command | `PYTHONPATH=. python -m pytest tests/ -q` |

## Backend Entrypoints

- `backend/main.py` — FastAPI application (`uvicorn backend.main:app`)
- `backend/db.py` — SQLite database via `backend.config.get_settings()`
- `backend/operators/registry.py` — operator dispatch registry

## Operator Registry

Operators registered in `backend/operators/registry.py`:

- `researcher`
- `critic`
- `experimenter`
- `planner_agent`
- `reviser`
- `synthesizer`
- `repo_tools`

Configuration: `configs/operator_registry.yaml`

## Artifact Schema

Artifacts are stored via `backend/services/artifacts.py` with columns:

- `id`, `project_id`, `type`, `title`, `data_json`, `confidence`
- `source_task_id`, `source_node_id`
- `parent_ids_json`, `lineage_json`
- `revision_of_artifact_id`, `revision_note`
- `created_at`, `updated_at`

Backend artifact types include: `claims`, `architecture`, `hypothesis`, `requirements`, `evidence`, `experiment_plan`, `experiment_result`, `code_patch`, `patch_test_result`, `critique`, `task_list`, `synthesis`.

## Experiment Runner Path

1. Planner creates `experiment_plan` artifact via `experiment_designer` operator
2. `ExecutionService._enqueue_experiment_execution()` creates `experiment_run` task
3. `experiment_runner` operator executes and produces `experiment_result`
4. `experiment_service.update_beliefs_from_result()` updates hypotheses
5. Evaluator operator reviews the result

## Graph Storage Format

### Backend (SQLite)

Tables: `claims`, `hypotheses`, `questions`, `evidence_links`, `conflict_pairs`, `conflict_resolutions`.

### Canonical Graph (`research_engine.graph.graph_store`)

In-memory typed graph with:

- **Node types** (`research_engine.graph.node_types.NodeType`): CLAIM, EVIDENCE, HYPOTHESIS, EXPERIMENT, RESULT, FINDING, THEORY, RESEARCH_FRONTIER, BELIEF_STATE, FINDING_VERSION, THEORY_VERSION, EVIDENCE_SNAPSHOT, EXPERIMENT_REVISION
- **Edge types** (`research_engine.graph.edge_types.EdgeType`): SUPPORTS, CONTRADICTS, TESTS, PRODUCED, SUMMARIZES, CONTRIBUTES_TO, INVESTIGATES, EXPLORES, SUPERSEDES, REVISES, INVALIDATED_BY, STRENGTHENED_BY, WEAKENED_BY, OBSERVED_AT

### Temporal Layer (`research_engine.graph.temporal`)

- `VersionTracker` — revision history per entity
- `TemporalGraph` — version nodes and causal edges
- `BeliefTimeline` — confidence evolution over time
- `StateSnapshot` — point-in-time graph snapshots

## Database Schema

Main tables (SQLite):

- `projects` — research projects
- `tasks` — pending/running/done tasks
- `artifacts` — all operator outputs
- `execution_nodes` — DAG nodes
- `execution_deps` — node dependencies
- `execution_inputs` / `execution_outputs` — artifact I/O
- `runs` — execution run log
- `claims`, `hypotheses`, `questions` — world model
- `evidence_links`, `conflict_pairs`, `conflict_resolutions` — reasoning state
- `embeddings` — vector embeddings

## API Routes

FastAPI routes defined in `backend/main.py`:

- `POST /projects` — create project
- `GET /projects` — list projects
- `GET /projects/{id}` — get project
- `POST /projects/{id}/tasks` — create task
- `GET /projects/{id}/tasks` — list tasks
- `POST /projects/{id}/step` — execute one step
- `POST /projects/{id}/run` — run until idle
- `GET /projects/{id}/artifacts` — list artifacts
- `GET /projects/{id}/world-model` — get world model state
- `GET /projects/{id}/execution-graph` — get execution DAG
- `POST /projects/{id}/sandbox/execute` — sandbox execution

## Artifact Directories

- `data/research_engine.db` — SQLite database
- Runtime artifacts stored in-database (no filesystem artifact directory)

## Import Discipline (current state)

- `backend/` imports from `research_engine` (canonical runtime, graph)
- `research_engine/` never imports from `backend/`
- `research_lab/` is the migration source; modules being moved to `research_engine/`
