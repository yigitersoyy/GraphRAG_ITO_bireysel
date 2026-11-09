# Notes → Knowledge Graph (GraphRAG + Neo4j + LM Studio)

Turns personal notes (Turkish or English) into a source-backed knowledge graph. Questions are
answered from retrieved passages with citations; the graph shows how entities connect.

On this configured Windows machine, double-click **`BASLAT.cmd`** to prepare Docker,
local models and project services, then open the UI automatically. **`DURDUR.cmd`**
stops this project's services while preserving notes. See [one-click usage](docs/windows.md).

- [Windows installation and service lifecycle](docs/windows.md)
- [Document formats, previews and upload limits](docs/BELGE_YUKLEME.md)
- [Automatic topic grouping and moving notes](docs/KONU_GRUPLAMA_VE_TASIMA.md)
- [Operations, backup and recovery](docs/operations.md)
- [Evaluation procedure and limitations](evaluation/README.md)
- [Full-text analyzer decision](docs/decisions/0001-fulltext-analyzer.md)

## Workspace

The React workspace provides a graph, note inspector/editor, paginated lists, topic management,
Ctrl+K search and source-backed answers. Upload up to 50 mixed PDF, DOCX, XLSX, XLS, TXT or Markdown
files per selection. Each file becomes a separate note; failed files can be retried without
duplicating successful uploads. Single-file previews can be edited before saving.

The graph distinguishes topics, filename-derived document series, notes and extracted entities.
Topic membership and chapter links are organizational metadata; extracted claims have source
passages. Answers highlight their source documents and related nodes; clear the highlight to
return to the full map. Filters control labels, links, arrows and node sizes. Dragging preserves
the camera and produces a temporary spring response that can be disabled in the view controls;
reduced-motion preferences disable that animation. Positions are not saved to the API.

The map is bounded to 300 notes, 600 shared-entity links, 100 source entities and 150 extracted
relations per response; partial views are indicated. Lists and search provide access beyond a
single map page. Deleted notes appear separately under **Liste → Silinenler**, showing titles
and deletion dates without making deleted content available to search, graphs or answers.

Source links open the cited immutable revision. Citation ranges count Unicode code points,
including emoji, rather than JavaScript UTF-16 units. A failed update leaves the previous
published revision searchable until its replacement is ready. Topic moves change metadata
with version checks and do not rerun extraction.

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

The Windows launcher profile uses Qwen3.5-9B for extraction/answers and a separate Nomic
768-dimensional embedding model. Configure the actual served IDs and preprocessing as described
in the [Windows guide](docs/windows.md); `.env.example` leaves chat IDs unset and uses a different
embedding profile. Model/profile changes require compatible indexes and fresh capability probes.
Connection probes and valid citation offsets do not establish semantic answer quality.

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

`NEO4J_TEST_WIPE=1` clears that database. Tests reject configured live database addresses and
refuse to run while a worker heartbeat is fresh.
Use a disposable database, never your notes database. On Windows with a conflicting system temp
directory, use a dedicated `--basetemp reports/pytest-local` directory.

Frontend checks, from `frontend/`:

```bash
npm ci
npm run build
npm test
```

For browser tests, start a separate demo from the repository root:

```bash
uv run python scripts/runtime.py start --mode demo --api-port 18001 --ui-port 18502
```

Then run `npm run test:e2e` from `frontend/`. The tests require an empty memory demo.
Stop it with `uv run python scripts/runtime.py stop --mode demo` from the repository root.
See the [Windows guide](docs/windows.md#kontroller) for lifecycle and performance checks.

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
frontend/         React/TypeScript workspace and locally bundled Cytoscape graph
evaluation/       small labelled set and runner (demo results are not model quality)
scripts/          smoke test, LM Studio probe, backup/restore, wheelhouse, evaluation
```

## Architecture

The browser uses same-origin `/api` and `/health` routes through Nginx in Docker or
`scripts/frontend_server.py` in native demos. FastAPI handles requests; the ingestion worker
chunks notes, extracts claims, embeds passages and publishes validated revisions. Neo4j stores
notes, revisions, jobs, topics, claims and search indexes. API, worker and capability probes share
a database-backed inference gate for LM Studio calls. Model credentials stay on the server.
Migration 005 adds topics and metadata lookup without rewriting existing note revisions.

React is the single supported UI; Streamlit was retired. In a local comparison
of three cold-browser runs with 300 synthetic notes, NiceGUI 4.0.0's median first usable graph
took 3,216 ms against React's 1,901 ms, exceeding the 2,626 ms migration budget. Its pan performance
passed, but the startup failure prevented migration. This was a local experiment, not a general
framework benchmark. The React benchmark remains available as `npm run benchmark` against an
empty memory demo; local historical evidence is under `reports/ui-benchmark/`.

Calculated semantic-similarity links, manual entity merge/split, persistent dragged positions,
OCR and multi-user access are not implemented. Model-assisted semantic review can be uncertain;
read cited passages when the UI displays a warning. Independent evaluation on broader real-note
collections is still needed before claiming general model quality.

## Security notes

No authentication: keep the API on loopback or behind an authenticated gateway. Note text and
embeddings live in Neo4j and in backups. Logs carry IDs, timings and status codes, not note text.
