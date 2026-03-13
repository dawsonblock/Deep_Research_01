# Research Engine Scaffold v9

A compact, persistent local scaffold for an autonomous research runtime.

This repository provides a powerful, typed foundation for agentic memory, planning, scaling, and execution. It includes mechanisms for maintaining state, evolving artifacts over time, resolving claim conflicts natively, and safely evaluating code via sandbox harnesses.

---

## 🚀 Key Features

- **Typed Artifact Engine**: Data structures (requirements, architectures, claims, code patches) with built-in validation and scoring.
- **Lineage & Revision History**: Automatic tracking of artifact versions. Includes **Lineage Branching** (v9) to seamlessly merge multiple artifacts while preserving ancestral lineage.
- **Task & Execution Graphs**: Directed acyclic evaluation mapping for complex multi-step generation.
- **World Model Reasoning**: A dynamic knowledge store containing claims, questions, and hypotheses.
- **Automatic Conflict Resolution (v9)**: Detects competing or negating claims across artifacts using embeddings (semantic clash) and polarity checks. Resolves conflicts by suppressing weaker claims or escalating ties back to the world model as manual `contested` questions.
- **LLM-Backed Experiments (v9)**: Experiment runners benchmark project state. If an LLM (e.g. GPT-4) is connected, it explicitly handles logic validation (graph vs. linear contradiction rate); otherwise, it falls back to a deterministic arithmetic stub.
- **OpenSandbox Integration (v8+)**: Safe sidecar execution and evaluation of patches against real GitHub repositories. Includes persistent workspace lineages and automatic repo benchmark parsing (pytest, jest, cargo, go).
- **SearXNG Support**: External sidecar search capabilities for retrieving grounded data.

---

## 🛠 Quick Start

Ensure you have Python 3.9+ installed.

```bash
# 1. Setup virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the FastAPI server
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to interact with the interactive API.

### Environment Configuration (`.env`)

The scaffold operates gracefully with local deterministic fallbacks, but setting up providers unlocks true reasoning and search capabilities.

```env
# Optional: LLM configuration for intelligent operators and experiment evaluation
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxxxxxxxxxx
LLM_MODEL=gpt-4o
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

# Optional: SearXNG sidecar for web-based research
SEARXNG_BASE_URL=http://localhost:8080

# Optional: OpenSandbox connection for code testing and execution
OPENSANDBOX_ENABLED=true
OPEN_SANDBOX_DOMAIN=api.opensandbox.io
OPEN_SANDBOX_API_KEY=...
OPEN_SANDBOX_PROTOCOL=https
```

---

## 🔄 Suggested API Flow

The scaffold interacts via a clean REST workflow. A typical run involves planning, executing up to an idle bound, evaluating, and compressing state.

1. **Initialize**: `POST /projects`
2. **Contextualize**: `POST /projects/{project_id}/bootstrap`
3. **Execute**: `POST /projects/{project_id}/run-until-idle`
4. **Adapt & Plan**: `POST /projects/{project_id}/replan`
5. **Resume**: `POST /projects/{project_id}/run-until-idle`
6. **Evaluate**: `GET /projects/{project_id}/experiments`
7. **Inspect Output**: `GET /projects/{project_id}/artifacts`
8. **Distill Memory**: `POST /projects/{project_id}/compress`
9. **Final Review**: `GET /projects/{project_id}/summary`

---

## 🧬 Artifact Evolution & V9 Upgrades

### Artifact Versioning
Artifacts are automatically versioned and track revisions. 
- Modify an artifact: `POST /artifacts/revise`
- View an artifact's tree: `GET /artifacts/{artifact_id}/lineage`
- **[New in v9]** Merge artifacts: `POST /artifacts/merge` (Handles ≥2 parents, inheriting lineage from the dominant score).

### Automatic Multi-Agent Conflict Resolution (v9)
When large operator networks run concurrently, artifacts may generate clashing claims (e.g. _"System is fast"_ vs _"System is slow"_). 
The `ConflictResolutionService` automatically intervenes at creation:
- **Dominance**: If a new claim is structurally stronger (+0.15 delta) it automatically suppresses the old claim.
- **Escalation**: Tightly contested claims are flagged as `contested` and pushed into the World Model as a `question` for manual/LLM adjudication.
- **Auditing**: All events are stored in the DB and accessible via `GET /projects/{project_id}/conflicts`.

### Experiment Loop Upgrades (v9)
Plans output `experiment_plan` artifacts triggering `experiment_runner` and `evaluator` nodes.

Experiments now specify their validation method:
- **`llm_benchmark`**: Leverages the LLM for deep semantic reasoning (verifying requirement coverage vs code constraints).
- **`opensandbox`**: Dispatches the task to the secure execution harness for a live unit test or build loop.
- **`deterministic_stub`**: Safely falls back to local arithmetic approximations if the platform is offline or un-credentialed.

---

## 📦 Sandbox & Repo Evaluation Capabilities

This scaffold supports robust testing of actual repositories:

- **Sandbox Sessions**: Creates isolated ephemeral or persistent containers.
- **Workspace Mapping**: `current.json`, `manifest.json`, and version snapshots are actively structured in the sandbox for immediate debugging via `GET /sandbox/sessions/{session_id}/workspace-lineages`.
- **Repo Inspection**: Analyzes source code layout before inferring the best test/install commands.
- **Benchmark Parsing**: Scrapes `stdout` to natively detect testing success rates across Pytest, Unittest, Jest, Cargo, and Go.

---
_Disclaimer: This backend is a foundational scaffolding for autonomous systems architecture research. It provides the datastores, execution engines, and API boundaries required to develop higher-level cognitive swarms._
