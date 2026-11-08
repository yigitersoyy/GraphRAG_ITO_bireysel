# Notes → Knowledge Graph (GraphRAG + Neo4j + LM Studio)

Turns personal notes (Turkish or English) into a source-backed knowledge graph. Questions are
answered from retrieved passages with citations; the graph shows how entities connect.

On this configured Windows machine, double-click **`BASLAT.cmd`** to prepare Docker,
local models and project services, then open the UI automatically. **`DURDUR.cmd`**
stops this project's services while preserving notes. See [one-click usage](docs/windows.md).

- Current implementation status and Python UI decision: [cleanup and migration results](docs/TEMIZLIK_VE_PYTHON_GECISI.md).
- Qwen3.5-9B, up to 50 mixed files per selection, and circular graph nodes: [usage and validation](docs/QWEN35_TOPLU_YUKLEME_VE_GRAF.md).
- Architecture and backlog: [MIMARI_VE_YAPILACAKLAR.md](docs/MIMARI_VE_YAPILACAKLAR.md).
- Windows installation and lifecycle: [windows.md](docs/windows.md).
- Upload PDF, Word (.docx), Excel (.xlsx/.xls), TXT and Markdown, with editable text preview: [document import](docs/BELGE_YUKLEME.md).
- Filename-family topic nodes and drag/drop moves from the list: [grouping and transfer](docs/KONU_GRUPLAMA_VE_TASIMA.md).
- Reference-based React workspace: [design](docs/ARAYUZ_TASARIMI.md), [implementation and checks](docs/ARAYUZ_UYGULAMA_RAPORU.md).
- Completed local delivery, measurements and remaining limits: [delivery report](docs/TESLIM_RAPORU.md). Earlier infrastructure verification: [report](docs/ARAYUZ_ONCESI_DOGRULAMA.md).
- Phases and honest status: `docs/DEVELOPMENT_PLAN.md`.
- Running and recovering the system: `docs/operations.md`.
- Decisions: `docs/decisions/`.

## Quick start (no LM Studio needed: demo providers)

The main UI is a dark, full-window note map with colored topics, a note inspector,
list/topic views, keyboard search and source-backed answers. Windows native setup requires
Python 3.12 and Node.js 24; Docker builds the frontend with its own Node stage.

On Windows, from PowerShell in the repository root:

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1 -Mode demo
```

Open `http://localhost:8501`. This memory demo loses notes on exit. Stop it with
`.\scripts\stop.ps1 -Mode demo`. For persistent notes, set `NEO4J_PASSWORD` in `.env`,
start Docker Desktop and run `.\scripts\start.ps1 -Mode persistent-demo -Build` instead.
Modes use separate Compose projects/volumes. Use different port options if running them together.

The cross-platform equivalent after `uv sync --frozen --group dev` is
`uv run python scripts/runtime.py start --mode demo`.

For the manual Linux/container flow:

```bash
export NEO4J_PASSWORD='choose-a-strong-password'   # or put it in .env (never commit .env)
scripts/build_wheelhouse.sh                        # locked dependencies + app wheel, on the host
GRAPHRAG_DEMO=1 docker compose -p notes-graphrag-persistent-demo up -d --wait neo4j
GRAPHRAG_DEMO=1 docker compose -p notes-graphrag-persistent-demo run --rm migrate
GRAPHRAG_DEMO=1 docker compose -p notes-graphrag-persistent-demo build api worker ui
GRAPHRAG_DEMO=1 docker compose -p notes-graphrag-persistent-demo up -d api worker ui
uv run python scripts/smoke.py --api-base http://127.0.0.1:8000
```

Demo providers are deterministic rule-based fakes. They prove the plumbing, not model quality.

## With LM Studio

Start LM Studio on the host with the chat and embedding models loaded, set the model IDs and
`LLM_BASE_URL`/`EMBEDDING_BASE_URL` in `.env`. Containers use the separate
`COMPOSE_LLM_BASE_URL`/`COMPOSE_EMBEDDING_BASE_URL` settings, defaulting to
`host.docker.internal`. Set query/document preprocessing to match the embedding model.
Run `.\scripts\start.ps1 -Mode live -Build` (or `scripts/runtime.py start --mode live --build`).
It migrates, records gated capability probes from the container, then checks API readiness
and worker heartbeat. It never falls back to demo providers when a real model fails.

The local Qwen 2.5 7B and Qwen3 8B / Nomic 768-dimensional connection was exercised on 7 November 2026.
See [Windows instructions](docs/windows.md) for the tested configuration, and the latest
verification status in [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md). Connection probes
and valid citation offsets do not establish semantic answer quality.

## Local development without containers

```bash
uv sync --group dev
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest                    # unit + in-memory contract tests; Neo4j tests skip without env
```

Neo4j tests (contract and integration) need a disposable database:

```bash
export NEO4J_TEST_URI=bolt://127.0.0.1:7687 NEO4J_TEST_PASSWORD=... NEO4J_TEST_WIPE=1
uv run pytest
```

`NEO4J_TEST_WIPE=1` clears that database. The tests refuse to run while a worker heartbeat is fresh.
Use a disposable database, never your notes database. On Windows with a conflicting system temp
directory, use a dedicated `--basetemp reports/pytest-local` directory.

## Evaluation

`uv run python scripts/evaluate.py --repeats 2` runs the deterministic demo. `--live`
uses the real providers and a separate **empty** Neo4j target. It never clears an existing
database. Baseline and validation datasets are separate; reports include failed ingestion,
question errors, timings, sampled memory, model configuration and pending semantic review.
See [evaluation/README.md](evaluation/README.md) for the complete procedure.

## Layout

```
src/notes_graphrag/
  api/            FastAPI app, routes, dependency wiring
  ingestion/      validation, chunker, extraction schema, entity resolution, worker, note service
  persistence/    Store contract, memory store, Neo4j store and knowledge view, migrations
  providers/      LM Studio adapter, capability probes, inference gate, demo fakes
  retrieval/      lexical/vector candidates, RRF, bounded graph expansion, evidence packing
  answering/      structured answers, citation validation, rendering
migrations/       versioned Cypher (checksummed; applied once)
frontend/         main React/TypeScript workspace, Cytoscape + local Canvas cluster outlines
evaluation/       small labelled set and runner (demo results are not model quality)
scripts/          smoke test, LM Studio probe, backup/restore, wheelhouse, evaluation
```

## Historical verification (6 November 2026)

- 215 tests pass against Neo4j 5.26.32 Community: unit tests, one contract suite run against both the
  memory store and Neo4j, an HTTP case matrix on both stores, browser UI flows, the LM Studio contract
  over real sockets (against a simulator), and Neo4j integration tests.
- A fault-injection run against the Compose stack passes 28 of 28 checks: provider timeouts and slot
  recovery, rejected tokens, a worker crash with lease reclaim, a database restart during traffic,
  API restart, bursts, oversized bodies, and no note text in logs (`scripts/chaos_stack.py`).
- Backup and restore were exercised on the final schema (`docs/operations.md`).

## Current verification

The approved UI is now implemented in `frontend/`. The `ui` Docker target serves its compiled
assets through Nginx on 8501, proxying `/api` and `/health` to the API on the same origin.
Native demos use `scripts/frontend_server.py` for the same static/proxy arrangement.
The former Streamlit UI and its Docker target have been retired. React is the single
supported UI: the isolated NiceGUI prototype did not meet the agreed initial graph
load budget. The comparison and rollback evidence are recorded in the current status document.
Migration 005 adds topics and metadata lookup; it preserves existing notes and revisions.
See [the delivery report](docs/TESLIM_RAPORU.md) for current test results and [the UI slice report](docs/ARAYUZ_UYGULAMA_RAPORU.md) for the earlier interface checks.

The earlier 7 November work adds Windows lifecycle tools, the Compose UI service, split endpoint probes,
real evaluation and source-checked recovery of unique quote offsets. Neo4j restart persistence and
restore into an empty volume were exercised locally. Detailed results and any remaining model
quality limits are recorded in [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md). UI design and
interaction changes are awaiting the user's design choices.

## Security notes

No authentication: keep the API on loopback or behind an authenticated gateway. Note text and
embeddings live in Neo4j and in backups. Logs carry IDs, timings and status codes, not note text.
