# Operations

Use the [Windows guide](windows.md) for setup, mode-specific start/stop, diagnostics and model
configuration; the [README](../README.md#architecture) describes the architecture and UI decision.
React is the supported UI, served through Nginx or the native Python static/proxy server.
The lifecycle manager separates the `notes-graphrag-persistent-demo` and `notes-graphrag-live`
Compose projects and volumes. Memory demos lose data on exit. See the
[evaluation guide](../evaluation/README.md) for isolated model-quality measurements.

## Services

| Service | Role | Started by |
| --- | --- | --- |
| Neo4j 5.26 Community | Authoritative store, vector and full-text indexes | `compose.yaml` (`neo4j`) |
| migrate | Applies Cypher migrations, then exits | `compose.yaml` (`migrate`) |
| api | FastAPI on port 8000 (loopback by default) | `compose.yaml` (`api`) |
| worker | Ingestion loop: leases jobs, extracts, embeds, publishes | `compose.yaml` (`worker`) |
| ui | React workspace + Nginx proxy on loopback port 8501 | `compose.yaml` (`ui`) |
| LM Studio | Chat and embedding models | Host, not Compose |

Run exactly one worker in the MVP. Lease fencing keeps extra workers safe, but scaling is not tested
for throughput.

## First start

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
# Set NEO4J_PASSWORD and actual model/profile settings; keep .env out of git.
scripts/build_wheelhouse.sh     # builds deps and the app wheel on the host (see below)
docker compose build migrate api worker ui
docker compose up -d --wait neo4j
docker compose run --rm migrate
docker compose run --rm api probe --record   # live mode only
docker compose up -d api worker ui
curl --fail http://127.0.0.1:8000/health/ready
```

The Python app stage is installed offline from locked wheels; the frontend build stage uses
`npm ci` and `frontend/package-lock.json` and needs package registry access on its first build.
All runtime browser assets are served locally. The wheelhouse script prepares locked backend-only
dependencies and the application wheel in `wheelhouse/backend/` for offline image installation.
Run it again after any dependency or source change.

Set `GRAPHRAG_DEMO=1` to run every service with the deterministic demo providers, for example to
test the stack without LM Studio. Demo mode uses 64-dimensional embeddings, so run it against a
database that was migrated in demo mode. The migration guard refuses a mismatch.
Set this variable for every Compose call in that sequence and skip the live-only probe.
For daily use, prefer the lifecycle commands in the Windows guide to keep project names,
volumes and recorded ports consistent.

## Schema and the vector dimension guard

- `notes-graphrag migrate` applies versioned migrations once and records a checksum for each.
- An applied migration that has been edited is refused.
- An existing `chunk_embedding_v1` index whose dimension differs from `EMBEDDING_DIMENSIONS` is
  refused. Demo embeddings have 64 dimensions; live dimensions must match the configured model.
  Changing the embedding model or profile requires a full reindex, not an index reuse.
- `api` refuses to start on a schema version that does not match the code.

## Backup and restore

Neo4j Community has no online dump, so backup stops the database container briefly.

```bash
scripts/neo4j_backup.sh <neo4j-container> ./backups
scripts/neo4j_restore.sh <target-container> ./backups
```

Both shell commands delegate to `scripts/neo4j_archive.py`. Restore requires an empty,
stopped target and never overwrites an existing database. Backup checks directory access
before stopping the source; a failed dump restarts a previously running source.
Use a new output directory for each backup.

Capability probe records are part of the database too. The test suite clears the database it runs
against, so a stack that was tested must be probed again (`notes-graphrag probe --record`) before
readiness returns to 200.

Backups contain note text and embeddings. Store them with the same care as the database.

Recovery time objective is not defined and backup age is not monitored. Verify restores on a
separate empty target, including note/revision properties and online indexes. Readable exports
from `scripts/export_notes.py` preserve active/pending note revisions, not the full database history.

## Inference slot and recovery

All LM Studio calls (chat and embedding, from API and worker) pass through one database-backed slot
per endpoint (`InferenceGate`):

- A caller acquires the slot, and a heartbeat keeps the lease alive while the call runs.
- A timeout (`PROVIDER_TIMEOUT`) marks the slot `RECOVERING`. Nothing else is admitted until a small
  probe call succeeds.
- A holder that disappears (crashed process) leaves an expired lease. The next caller moves the slot to
  `RECOVERING` and the probe path runs. A crashed holder is therefore never silently overlapped with a
  new request.
- A busy slot returns `503 INFERENCE_BUSY` to interactive callers after `INFERENCE_SLOT_WAIT_SECONDS`.

Check the slot with `GET /api/v1/system/status` (`inference_slot.state`).

Limit: the probe is a timed heuristic. It proves the endpoint answers, not that the previous GPU job
has actually stopped. Validate timeout/recovery behaviour against the actual model server.

## Failure behaviour (verified in tests)

| Failure | Behaviour | Test |
| --- | --- | --- |
| Worker crashes mid-job | Lease expires; next acquire reclaims; attempt counter increments; the old token cannot write | `test_expired_lease_is_reclaimed_and_cannot_write` (both stores), `test_api_on_neo4j_end_to_end_with_stopped_worker_recovery` |
| Two workers race for one job | Exactly one acquires | `test_concurrent_acquire_gives_one_owner_per_job` |
| Two identical submissions race | One job; the loser retries and replays | `test_concurrent_identical_submissions_create_exactly_one_job` |
| Transient provider error | Requeued with backoff, then failed after `JOB_MAX_ATTEMPTS` | `test_transient_failure_requeues_then_fails` |
| Note deleted during processing | Publication refused; job cancelled | `test_delete_during_processing_blocks_publication` |
| Previous revision on failed update | Still served | `test_failed_update_keeps_previous_revision` |
| Separate worker process | Processes an API submission and heartbeats | `test_worker_in_separate_process_processes_api_submission` |
| Database unavailable | 503 envelope, retryable; no 500s during a real `docker restart` | chaos S6 (`scripts/chaos_stack.py`) |
| Provider slow past its timeout | Job retried; slot RECOVERING until a probe succeeds; no overlapping calls | chaos S1, `test_timeout_leaves_slot_recovering...` |
| Provider rejects the token | Fails at once with PROVIDER_AUTH_REJECTED, not retried | chaos S3, `test_bad_chat_outputs_are_classified` |
| Wrong embedding dimension from the runtime | Fails with EMBEDDING_DIMENSION_MISMATCH | chaos S4, `test_wrong_embedding_dimension...` |
| Diagnostic probe during ordinary traffic | Shares the slot; never overlaps | `test_diagnostic_probes_cannot_bypass_the_shared_slot` |
| Replay of a request whose content was purged | Still 409 NOTE_DELETED, no new note | `test_purge_removes_deleted_content_but_keeps_replay_protection` |
| Oversized or chunked body | 413 envelope, with or without Content-Length | chaos S9, `test_body_over_limit...` |

## Test database safety

Destructive Neo4j tests clear the database they point at, so they require
`NEO4J_TEST_WIPE=1`. They reject live database addresses found in `.env` and
`reports/runtime/live.json`, including loopback aliases, even if the live worker is stopped.
They also refuse a fresh worker heartbeat (under 120 seconds). Use an explicitly separate,
disposable target; stopping a live service does not make its data disposable. CI uses its own
throwaway service container.

## Readiness is backed by evidence

`/health/ready` returns 200 only when the database answers, the schema matches the code, the
required indexes are online, and, in production mode, a capability probe passed recently for
this exact configuration. The probe records its result and a fingerprint of the models,
dimension, profile, context length and query template. A changed setting makes an earlier result
inapplicable, and so does an older result than `CAPABILITY_PROBE_MAX_AGE_HOURS` (default 24).

```bash
notes-graphrag probe --record     # runs the probes through the shared inference slot and stores the result
```

Demo mode cannot be probed and is reported as exempt. Readiness in demo mode says so explicitly.

## Retention

- Deleted notes keep a tombstone. Their revisions, chunks, claims and jobs are removed after
  `DELETED_CONTENT_RETENTION_DAYS` (default 1). Entities left without claims are removed too.
  The document title and deletion timestamp remain after content purge. Old records whose titles
  were already cleared display a fallback title; the original name is not reconstructed.
- Idempotency records are kept for `IDEMPOTENCY_RETENTION_DAYS` (default 30). Within that period a
  replayed request for a deleted note still answers `409 NOTE_DELETED` and never creates a new
  note. After it, the same key is a new operation.
- The worker runs this maintenance about every `MAINTENANCE_INTERVAL_SECONDS` (default 3600). It is
  idempotent. Counts are logged when anything was removed.

`GET /api/v1/workspace/deleted-notes?limit=50&cursor=...` returns tombstone metadata only:
`note_id`, `title`, `deleted_at`, `content_purged`, total and next cursor. Results are ordered
newest deletion first with an ID tie-breaker. The UI's **Liste → Silinenler** view is separate
from unassigned active notes (**Düzenlenmemiş**). Deleted content is excluded from the normal
catalog, search, graph and answer sources before and after purge. The UI has no restore or
permanent-delete action.

## Workspace metadata and sources

`/api/v1/workspace/notes` paginates the catalog; cursors are bound to search/topic filters.
`/api/v1/workspace/map` exposes bounded notes, topics, shared-entity links and source-backed
relations with explicit limit flags. Topic/filename-series links are organizational metadata,
not model-extracted claims. Calculated semantic similarity is unavailable.

Topic edits and `PATCH /api/v1/notes/{id}/metadata` require the expected metadata version;
conflicts do not overwrite another edit. Topic assignment does not change source revisions or
enqueue extraction. Clients refresh on both graph and metadata versions. Search cancels stale
requests and refreshes with workspace versions, so deleted notes and their entities disappear
from open search results. See [topic management](KONU_GRUPLAMA_VE_TASIMA.md).

Extraction uses relationship-first wire output (`relations`) converted to the internal
entities/claims representation before validation. A model-supplied quote must match a unique,
exact substring of the note; the server computes its offsets and schema version. Missing or
ambiguous quotes, invalid relation types and inconsistent entity references are rejected rather
than silently dropped. Legacy numeric offsets are still strictly checked. Answer wire schemas
require sentence and citation fields. Citations and answer-graph edges refer to immutable
revisions, with ranges measured in Unicode code points rather than UTF-16 units.

## Request limits

- Ordinary bodies larger than `MAX_REQUEST_BYTES` (default 2 MiB) get `413 PAYLOAD_TOO_LARGE`, whether or not
  the client sent a Content-Length. The two document upload endpoints instead allow
  `MAX_UPLOAD_BYTES` + 2 MiB multipart overhead (default 12 MiB). Files are independently
  limited to 1 MiB for UTF-8 text and 10 MiB for PDF/Word/Excel; extracted text remains bounded
  by `MAX_NOTE_CHARS` (100,000) and `MAX_NOTE_BYTES` (1 MiB). See [document import](BELGE_YUKLEME.md).
- Notes may not contain control characters except tab, line feed and carriage return
  (`422 CONTROL_CHARACTERS`). NUL is never accepted.
- Every failure, including unknown routes, wrong methods and malformed JSON, uses the same error
  envelope with a `request_id`.

## Chaos run (fault injection against the Compose stack)

`scripts/chaos_stack.py` injects faults into the production path (`GRAPHRAG_DEMO=0`) and checks what
the API and database report. Prerequisites:

1. The stack is up: `docker compose up -d --wait neo4j`, then `migrate`, then `api worker`.
2. The LM Studio contract simulator runs on all interfaces so containers can reach it:
   `uv run python -m tests.support.lmstudio_sim --host 0.0.0.0 --port 1234`.
   It is a stand-in for the HTTP contract, not LM Studio and not a model.
3. The probes were recorded: `notes-graphrag probe --record` (same environment as the containers).

Scenarios: provider slow past its timeout (slot goes RECOVERING, job completes after recovery),
provider down (retries run out, question returns a retryable 503), rejected token (not retried),
wrong embedding dimension, worker crashed mid-job (SIGKILL inside the container; the supervisor
restarts it, the lease expires and the job is reclaimed), database restarted during traffic, API
restarted, a 60-request burst, an oversized body, and a check that note and question text never
reach the logs.

Two details that matter when reproducing this:

- `docker kill` counts as a manual stop, and restart policies do not recover manual stops. A crash
  is simulated by signalling the worker process itself. The stack runs with `init: true`, so the
  worker is not PID 1, which the kernel would otherwise shield from in-container signals.
- A simulator started from a shell dies when that shell or session is restarted. Check
  `curl localhost:1234/sim/state` before a run.

## Known limits (be explicit with users)

- **Live validation is model-specific.** The Windows launcher profile uses Qwen3.5-9B and
  Nomic v1.5 (768 dimensions). Earlier Qwen3 8B measurements do not certify the newer model;
  see [evaluation provenance and limitations](../evaluation/README.md).
- **Model quality is a separate acceptance criterion.** Live evaluation records failed
  extraction, missing evidence, structural citation checks and pending semantic review. A
  successful health probe or demo run must not be presented as real-model quality approval.
- Persistence is Neo4j. The in-memory store is for demos and tests only and loses data on exit.
- No authentication. Keep the API on loopback or behind an authenticated gateway.
- Full-text search does not stem (see decision 0001).
- The relevance gate is permissive: one shared common word can make unrelated passages count as
  evidence (evaluation q16). Tightening it needs a held-out set, not tuning on this one.
- Entity resolution is conservative and simple: it has no manual merge or split.
- One worker is the tested configuration. Several workers are safe by design (leases and fencing),
  but throughput with more than one was not measured.
- Tests clear the Neo4j database they run against. Run them on a disposable instance only.
- Intermittent Windows hangs were observed in the Neo4j driver's concurrent identical-submission
  test at `BoltSocketBase.at_eof`. A later passing run does not establish that the issue is fixed.
  Keep timed-out/failed runs visible and investigate the driver/pool separately if it recurs.

## Long-running job ownership

Workers renew the job lease and workspace heartbeat while inference is running. Renewal is
token-fenced and rejects expired, reassigned or cancelled jobs. Recovery probes use 64 tokens;
batch probe startup may wait for an old slot lease to expire, while interactive admission
keeps its short wait budget.

## Extraction pipeline upgrades

A job revision records the extraction pipeline fingerprint. After changing prompts/model/profile,
an old pending or resumed job fails with `PIPELINE_CHANGED` rather than mixing staged chunks.
Retrying its current failed revision creates a fresh revision/job under the new fingerprint.
The retry API returns that job; follow its new ID. Published revisions remain searchable until
a replacement is successfully published. Existing notes are not bulk reindexed on startup.

The bounded citation-chain check is a provenance guard, not proof of semantic correctness.
Model-only disagreement after one repair is visible as `semantic_review_uncertain`;
schema/citation/known-type errors remain hard failures. Limited source-qualifier fallback
preserves possible/planned wording and does not infer confirmed use. See
[evaluation and review semantics](../evaluation/README.md#metrics-and-interpretation).

The Nginx UI uses Docker's embedded DNS resolver with a five-second cache and a variable
upstream, so recreating API does not require recreating UI. See [Nginx variable proxy resolution](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass)
and [Docker DNS services](https://docs.docker.com/engine/network/#dns-services).
