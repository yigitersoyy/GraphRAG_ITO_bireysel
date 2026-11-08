# Development plan and status

Source: the architecture document (Notes → Knowledge Graph). Phases follow its section 17.

## Local delivery (2026-11-08)

Latest completed extension: Qwen3.5-9B is the sole extraction/answer model; Nomic
embeddings remain separate. Multiple selection accepts up to 50 mixed files with
per-file retries. The light graph uses blue documents, red topics and gray source
entities / filename-derived chapter series. See [current usage and validation](QWEN35_TOPLU_YUKLEME_VE_GRAF.md).
Older model quality measurements below are historical and do not certify this model.

Latest requested extension: filename-family automatic topic assignment and list drag/drop
between topic nodes, with keyboard/mobile selection and metadata CAS. Existing 14 notes
are grouped into KVKK (4) and BDDK (10), preserving all desired revision IDs.
See [grouping and transfer validation](KONU_GRUPLAMA_VE_TASIMA.md).

One-click Windows startup is implemented via `BASLAT.cmd`, with a companion
`DURDUR.cmd`. Docker readiness, local model loading, persistent-service recovery,
crash-released locks and browser-after-readiness are validated. See
[one-click delivery](TEK_TIK_BASLATMA.md) for measured cold/warm results and limits.

User-requested extensions after initial delivery: PDF, Word (.docx) and Excel (.xlsx/.xls) imports now share
the existing revision/job/source pipeline, with a read-only editable text preview.
Excel preserves sheet/cell addresses and saved values, without evaluating formulas.
See [document import](BELGE_YUKLEME.md) for formats, limits and additional validation.

A–F local single-user scope is complete. D13/D14/D16 sampled acceptance passed.
The final fresh holdout4 has 5 notes / 8 questions, repeated twice across three methods:
48 requests, zero errors, each method 12/12 answerable and 4/4 correct abstentions,
evidence recall 1.000. The earlier holdout3 is now regression data; its final replay
passed 8/8 answerable and 4/4 abstentions per method. This is agent-authored sampled
validation, not independent human certification of general model correctness.

Relationship-first extraction, hard provenance/type guards, one answer repair and visible
model-review uncertainty are implemented. Existing published notes are not bulk reindexed.
Both English and Turkish HTTP lifecycle smokes passed through the final UI proxy.
Docker DNS refresh survives API recreation without restarting the UI.
See [delivery and evidence](TESLIM_RAPORU.md) for tests, measurements and limits.
G authenticated external access remains conditional and unrequested. The sections below
record historical slices, including failures that were subsequently fixed.

## Current model quality follow-up (2026-11-07)

Continuing the main checklist, the extraction schema now preserves field guidance through
reference inlining. Qualifier instructions distinguish possibility from an approved plan.
Bounded answer validation checks cited one/two-hop provenance chains and answer graph edges
carry immutable source ranges. Changed-pipeline jobs require a fresh revision on retry.
The six-note regression now matches all seven annotated relationships, including POSSIBLE;
its multi-note answer cites both sources in all modes. Baseline graph abstention improved
to 5/5, but baseline ingestion remains 7/9 and recall 0.864. The frozen 8-note/10-question
holdout ran twice: ingestion 8/8 and recall 1.0 in every mode, but abstention 4/6 per mode.
An approved plan was mislabeled ASSERTED and a language question received a database answer.
D13, D14 and D16 remain open; neither structural citations nor complete chains imply semantic correctness.

**281 Python tests pass** with both stores and no skips; Ruff/format/mypy pass. Five real-API
Playwright flows pass, including opening an answer graph edge's source revision. Earlier
counts below describe their historical slices. See [quality follow-up](KALITE_IYILESTIRME_RAPORU.md)
for the final held-out results, known limits and next acceptance criteria. General model
quality remains unapproved; external access is still conditional.

## Current UI update (2026-11-07)

The user approved the reference-based design and requested implementation. The React/TypeScript workspace is now the main UI: colored topic clusters, organic Canvas outlines, a note inspector/editor, list pagination, topic management, keyboard search and source-backed answers. Migration 005 adds explicit metadata without rewriting note revisions. Native and Compose lifecycle commands now start the compiled workspace. See [UI implementation and verification](ARAYUZ_UYGULAMA_RAPORU.md).

**272 Python tests pass**, including both stores and 0/1/50/51/101-note catalog cases. **Five real-API Playwright flows and two frontend source-range tests pass**. The final 300-note/600-edge sample recorded p95 frame interval 7.1 ms during local headless Edge pan; it is not an independent benchmark. General model quality remains unapproved; UI work does not remove the earlier semantic limitations.

## Backend verification before UI (2026-11-07)

Windows A–D implementation is complete; the user requested a stop before UI changes. See [the implementation checklist](MIMARI_VE_YAPILACAKLAR.md) and [verification report](ARAYUZ_ONCESI_DOGRULAMA.md). The older verification summary below is historical.

The full suite now passes **256 tests** against isolated Neo4j 5.26.32 and memory stores. Windows setup/lifecycle, persistent restart, empty-target restore, container-to-LM-Studio probes, English/Turkish HTTP smoke, timeout recovery, real worker crash/reclaim and concurrent API/worker traffic were exercised. Long-running jobs now renew both job and workspace leases with ownership fencing.

Live Qwen3 8B / Nomic 768-dimensional evaluation is implemented and recorded. Baseline ingestion passed 7/9 notes, recall 0.864; graph abstention 4/5. Validation passed 6/6 notes, recall 1.0, abstention 4/4 per mode across two passes. Numeric validation targets passed; general quality is not approved. Remaining issues include two failed baseline extractions, POSSIBLE/PLANNED classification, incomplete vector citation chains and irrelevant graph answers. GPU sampled peak was 5685 MiB; warm p95 was 4.60–5.07 seconds on this small validation set.

Next: agree on the user's UI design before phase E; implement pagination/status/offline graph assets with that design. External access/auth remains unimplemented. Original demo notes were backed up; no automatic migration was performed.

## Status

| Phase | Scope | Status | Evidence |
| --- | --- | --- | --- |
| 0 Bootstrap | Package, lock, config, Compose, CI | Done | `uv.lock`, `compose.yaml`, CI workflow |
| 1 Persistence and notes | Store contract, Neo4j repository, idempotency, leases | Done (Neo4j 5.26.32) | 23 contract tests, each run on both stores (46 cases) |
| 2 Text ingestion | Chunker, validation, staged publication | Done | chunker and publication tests; case matrix in `tests/e2e` |
| 3 Real extraction | LM Studio adapter, schema validation, entity resolution | Live Qwen3 verified; quality limitations above | `tests/integration/test_lmstudio_http.py` (16 tests) |
| 4 Search | Vector and full-text indexes, active filter, RRF | Done (Neo4j indexes) | scoped candidate tests; Turkish case folding test |
| 5 Graph retrieval | Entity linking, bounded expansion, evidence packing | Done | expansion limit tests; 2-hop contract test |
| 6 Answers | Structured answers, citation validation, abstention, graph version | Live smoke and evaluation run; semantic limitations above | answer and citation tests |
| 7 Interface | FastAPI + React workspace; legacy Streamlit retained | Approved first UI slice implemented | Workspace API cases on both stores; real-API Playwright; source-range tests |
| 8 Reliability | Inference gate, lease fencing, restart recovery, retention, backup | Live timeout and worker restart recovery verified | chaos run 28/28; mutation checks; measured backup and restore |
| 9 Evaluation | Dataset, baselines, live smoke, operations guide | Live baseline and separate validation measured; quality not approved | `evaluation/`, `scripts/evaluate.py`, `docs/operations.md` |

## Verification summary (2026-11-06)

- **Test suite:** 215 tests pass against Neo4j 5.26.32 Community: unit, one contract suite run on
  both stores, the HTTP case matrix on both stores, Streamlit flows, the LM Studio contract over real
  sockets, Neo4j integration tests (migrations, concurrency, Turkish full text, separate worker
  process, API end to end).
- **Chaos run against the Compose stack** (`scripts/chaos_stack.py`, production mode, simulator as
  the provider): 28 of 28 checks pass. Covers slow provider and slot recovery, provider down,
  rejected token, wrong dimension, worker crash with lease reclaim, database restart during traffic,
  API restart, a 60-request burst, oversized body, and no note text in logs.
- **Mutation checks:** five deliberately broken rules (lease fencing, deleted-note visibility, body
  limit, control characters, purge and replay protection) and the gate's admission control. Each is
  caught by at least one test. Restoring the code makes the tests pass again.
- **Backup and restore:** re-verified on the final schema (migrations 1 to 4).
- **Evaluation:** demo providers only. Results validate plumbing, not model quality.

## Historical definition of done (2026-11-06; superseded by current update)

- Installs from the committed lockfile: yes (`uv sync --frozen`).
- Schema setup repeatable and checks index compatibility: yes (migrations with checksums and a
  dimension guard).
- LM Studio serves the configured models from the actual caller: **not verified** (no LM Studio here).
- Structured output, Turkish/English, embedding dimension, retrieval probes on recorded profiles:
  **the probe logic and recording are verified against the simulator; the live probe is not run.**
- Concurrent API/worker inference within memory limits: the single-slot guarantee is verified on the
  wire with the simulator; GPU memory limits were **not measured**.
- Worker resumes durable work after a restart: yes (lease reclaim; chaos S5).
- Notes created, replaced, deleted without stale evidence: yes.
- Every claim traceable to an exact passage in an immutable revision: yes (offset check on read).
- Turkish and English extraction pass the evaluation cases: **not measured with a real model.**
- Hybrid search and graph traversal respect scope and limits: yes.
- Answers have valid citations or state insufficient evidence: yes (citation validation).
- Contradictions, uncertainty, negation preserved: prompt and data model support it; **not evaluated
  with a real model.**
- UI exposes progress, failures, evidence, source passages: yes (Streamlit flow tests and a screenshot
  from an earlier session). Markdown in note titles is escaped.
- Unit, contract, integration and deterministic end-to-end tests pass: yes (215).
- Real LM Studio smoke test passes: **not run.**
- Evaluation report identifies dataset, models, prompts, counts, limits: partly (demo providers only).
- Logs and history contain no credentials or unintended note content: verified in chaos S10; no
  secrets were committed.
- Backup and restore exercised on disposable data: yes, on the final schema.
- Tested installation and startup instructions saved: yes (`docs/operations.md`, `README.md`).

## Current open items

1. Next UI slice if requested: calculated semantic similarity, optional tags and persistent graph positions. The approved first slice is implemented.
2. Model quality improvements documented in the current verification report; do not treat valid offsets as semantic correctness.
3. Independent review and broader real-note evaluation before claiming general quality.
4. External access/auth only if requested (phase G).
