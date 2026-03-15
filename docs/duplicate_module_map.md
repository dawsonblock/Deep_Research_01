# Duplicate Module Map

Maps duplicate module families between `research_engine/` (canonical) and `research_lab/` (migration source).

## Duplicate Families

| Canonical (`research_engine/`) | Duplicate (`research_lab/`) |
|---|---|
| `research_engine/agents/core/*` | `research_lab/agents/core/*` (not present — agents under `research_lab/agents/synthesis/`) |
| `research_engine/analysis/conflicts/*` | `research_lab/analysis/conflicts/*` (not present — conflicts in `research_lab/knowledge/`) |
| `research_engine/analysis/hypotheses/*` | `research_lab/analysis/hypotheses/*` (not present) |
| `research_engine/core/artifacts/*` | `research_lab/core/artifacts/*` (not present — no `core/` in `research_lab/`) |
| `research_engine/core/runtime/*` | `research_lab/core/runtime/*` (not present) |
| `research_engine/experiments/*` | `research_lab/experiments/*` |
| `research_engine/graph/*` | `research_lab/knowledge/graph/*` |
| `research_engine/planner/*` | `research_lab/planner/*` |
| `research_engine/sandbox/*` | `research_lab/sandbox/*` |
| `research_engine/retrieval/*` | `research_lab/retrieval/*` |
| `research_engine/reflection/*` | `research_lab/reflection/*` |
| `research_engine/operators/evolution/*` | `research_lab/operators/evolution/*` |

## Modules Unique to `research_lab/`

These contain logic that should be mined before deletion:

- `research_lab/knowledge/belief/belief_graph.py`
- `research_lab/knowledge/belief/belief_update.py`
- `research_lab/knowledge/query/graph_queries.py`
- `research_lab/knowledge/query/graph_traversal.py`
- `research_lab/knowledge/reasoning/*`
- `research_lab/memory/episodic/episodic_memory.py`
- `research_lab/memory/failures/failure_patterns.py`
- `research_lab/memory/semantic/knowledge_archive.py`
- `research_lab/memory/topic_history.py`
- `research_lab/operators/extraction/*`
- `research_lab/operators/evolution/operator_mutator.py`
- `research_lab/operators/evolution/operator_optimizer.py`
- `research_lab/operators/evolution/operator_trial_runner.py`
- `research_lab/planner/action_rules.py`
- `research_lab/planner/information_gain.py`
- `research_lab/planner/task_selector.py`
- `research_lab/reflection/critique/critique_engine.py`
- `research_lab/diagnostics/*`
- `research_lab/ingestion/*`
- `research_lab/agenda/*`

## Migration Order

1. `research_engine/core/runtime/` — already canonical
2. `research_engine/core/artifacts/` — add `artifact_types.py`
3. `research_engine/graph/` — merge from `research_lab/knowledge/graph/`
4. `research_engine/planner/` — merge from `research_lab/planner/`
5. `research_engine/sandbox/` — already canonical
6. `research_engine/experiments/` — merge from `research_lab/experiments/`
7. `research_engine/agents/core/` — already canonical
8. Belief, memory, meta — new modules
