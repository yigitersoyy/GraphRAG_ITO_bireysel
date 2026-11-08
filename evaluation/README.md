# Evaluation

The baseline is `notes.jsonl` (9 notes) and `questions.jsonl` (16 questions: 11 answerable,
5 unanswerable). `notes.validation.jsonl` and `questions.validation.jsonl` add an independent
6-note/8-question set covering Turkish, English, negation, uncertain future statements,
conflicting sources, same-name entities and multi-note questions. The baseline is for development.
After inspecting validation failures on 7 November, validation is a **regression** set, not an
unseen test. `notes.holdout.jsonl` (8 notes) and `questions.holdout.jsonl` (10 questions) were
written and frozen before the next final measurement. Run them with `--split holdout` on a
separate empty target. Do not tune prompts, thresholds or labels after seeing those results.
This agent-authored small holdout is not an independent human assessment.

On 8 November, `holdout` became regression data for the next changes. A fresh `holdout2`
contains 8 notes / 12 questions, including positive language-use evidence as well as absent
personal attributes, approved plans, possibility and explicitly incompatible only-primary
database records. Use `--split holdout2` on a fresh empty target. Freeze source, prompts,
dataset and thresholds before inspecting its results; do not tune on that run.

The positive-language probes made holdout2 and holdout3 development/regression data.
The final unseen-before-freeze set is **holdout4**, with 5 notes / 8 questions.
Source, prompts, data and thresholds were frozen before inspecting it. Two passes across
three methods completed 48 requests with no errors; each method answered 12/12 answerable
cases and correctly abstained on 4/4 absent cases, evidence recall 1.000. Five annotated
claims matched exactly. No model/prompt/dataset/threshold tuning followed this run.
A subsequent English/Turkish absence-message selection fix and Nginx DNS fix are documented
separately in [delivery](../docs/TESLIM_RAPORU.md). This small agent-authored set is not
independent human certification; `quality_approved` intentionally remains false.

## Demo

```bash
uv run python scripts/evaluate.py --repeats 2
uv run python scripts/evaluate.py --split validation
uv run python scripts/evaluate.py --split holdout
uv run python scripts/evaluate.py --split holdout2
uv run python scripts/evaluate.py --split holdout3
uv run python scripts/evaluate.py --split holdout4
```

Demo providers are rule-based fakes. They exercise the evaluation infrastructure and do not
measure model quality. The runner uses the same application wiring and query preprocessing as
the API. Notes are ingested once; vector, hybrid and graph retrieval share that immutable corpus.
The answer path's own retrieval is measured, without an extra retrieval before each answer.

Each run creates a unique timestamped directory with `report.json`, `report.md` and `summary.json`.
The requested output root also contains `summary.json` for compatibility with CI artifact upload.

## Live LM Studio

Configure `.env` for real models, dimensions and document/query preprocessing. Use an empty,
dedicated Neo4j container/volume. Normal real-model API/worker traffic must be stopped, because
different databases cannot share the same inference lock. A memory/demo application may stay up.
The flag below acknowledges that exclusive model access has been arranged; it does not stop
other applications or make the model server exclusive by itself.

PowerShell example:

```powershell
# Stop this project's managed live services, if running.
.\scripts\stop.ps1 -Mode live

# Creates a separate volume; default local Bolt port is 27687.
docker compose -p notes-graphrag-eval-baseline -f compose.evaluation.yaml up -d --wait
.\.venv\Scripts\python.exe scripts/evaluate.py --live --target-uri bolt://127.0.0.1:27687 --exclusive-model-server --repeats 2 --out reports/evaluation-live
```

The target uses `.env` Neo4j credentials. The runner refuses the configured primary database URI
(including common localhost aliases), refuses any target containing nodes, and never runs a
wipe query. It initializes migrations only after the empty-target check. The evaluated data is
retained, so another run requires a fresh volume/project. Do not point it at user data.

For regression or holdout, provision a different empty project and free ports:

```powershell
$env:EVAL_BOLT_PORT='27689'
$env:EVAL_HTTP_PORT='27476'
docker compose -p notes-graphrag-eval-validation -f compose.evaluation.yaml up -d --wait
.\.venv\Scripts\python.exe scripts/evaluate.py --live --split validation --target-uri bolt://127.0.0.1:27689 --exclusive-model-server --repeats 2 --out reports/evaluation-validation
```

Stop these projects after measurement using the same `-p` and `-f` options. Volumes are kept.
If a port is already occupied, choose another port; never remove an unrelated database to free it.

## Metrics and interpretation

- Evidence recall and full coverage of expected notes, including two-hop coverage.
- Correct abstentions on answerable/unanswerable labels, with counts and denominators.
- Invalid citation offsets, provider errors, timeouts and failed ingestion. Failed questions
  remain in denominators and latency distributions; an ingestion failure is not silently dropped.
- Extraction output per note. Annotated validation notes also report exact matches, missing
  claims and extra claims by subject/predicate/object/polarity/modality. Aliases need review.
- Retrieval, full answer, inference admission wait and queue-to-completion ingestion latency.
  Inference wait includes time spent waiting for recovery, if recovery is needed.
- First measured pass and later warm passes separately. Probes and ingestion can warm the model
  before the first measured answer; the first pass is not a true cold-load benchmark.
- Sampled whole-host RAM and NVIDIA VRAM usage every two seconds, including other applications.
  These are sampled peaks, not exact model-process peaks. Unavailable readings are explicit.
- Commit, dirty working-tree indicator, dataset hash, prompt/source hashes and effective model,
  context and preprocessing settings. Answer source hashes and bounded regeneration counts
  are recorded too. Never API keys or database passwords.

A valid citation is a structural check, not proof of semantic support. Each answer includes
pending `semantic_correct` and `grounded` review fields and per-question review guidance.
Read the answers against their source passages; preserve both sides of contradictions and
negation/uncertainty. No model-quality approval is issued automatically.

The bounded citation-chain check only detects missing cited links on available one/two-hop
entity paths. It does not establish semantic truth or question relevance, infer absent claims,
or disambiguate same-name entities. It asks the model to regenerate once; it never appends
citations to a deficient answer on the model's behalf. Raw passages without graph claims
remain answerable. Answer graph edges carry their immutable source revision and quote range.

Real-model candidates receive model-assisted review of their cited original passages.
Explicit information kinds and the candidate kind are assessed separately. Invalid schema,
citations, provenance chains and known language/database type conflicts remain hard failures.
Review requests at most one regeneration; model-only semantic disagreement after repair may
return a structurally valid answer with `semantic_review_uncertain`, shown visibly in the UI.
Malformed review does not gain this exception. Proposed abstention gets an advisory original-
passage answerability check, not a global pre-gate. A narrowly bounded qualified-use fallback
may quote source-backed possible/planned usage when an explicit certainty question lacks
asserted usage; ambiguous IDs, contradictory/negated claims or unrepresented source reject it.
The provider, inference gate and question deadline are shared. Demo skips semantic review.
Live evaluation records review calls, attempts, uncertainty and source-qualifier fallback,
plus source/prompt hashes. Review is not an independent truth oracle.

Extraction wire output is relationship-first (`relations`); it is converted to the unchanged
internal claim representation before ontology, identity and exact source validation. The
pipeline fingerprint changes, so a pre-upgrade job cannot reuse staged chunks under the new
extractor. See [8 November quality work](../docs/KALITE_DOGRULAMA_V3.md).

An optional `--thresholds path/to/agreed.json` checks `min_evidence_recall`,
`min_abstention_rate`, `max_errors` and `max_end_to_end_p95_ms` for selected `modes`.
Agree thresholds using a baseline before assessing the validation set. A successful exit without
thresholds means the run completed without infrastructure/citation errors; it does not mean
all answers were correct. Any fatal dependency, failed ingestion or question error exits nonzero
and is included in the report.

The initial engineering targets are in `evaluation/thresholds.example.json`.
Use `--thresholds evaluation/thresholds.example.json` to apply them explicitly.
The 7 November live baseline/validation results and agent review limitations are
summarized in [the verification report](../docs/ARAYUZ_ONCESI_DOGRULAMA.md).

With small datasets, percentages are unstable. Report counts and model versions, not a single
unqualified accuracy number. GPU/model tests are opt-in and are not part of normal CI.
