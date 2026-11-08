"""Demo/live evaluation on one immutable corpus. Live mode requires an EMPTY isolated Neo4j."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from resource_monitor import ResourceMonitor  # noqa: E402

from notes_graphrag.answering.service import AnswerService  # noqa: E402
from notes_graphrag.api.dependencies import (  # noqa: E402
    build_context,
    build_gate,
    build_providers,
    build_storage,
)
from notes_graphrag.core.config import Settings  # noqa: E402
from notes_graphrag.core.errors import AppError  # noqa: E402
from notes_graphrag.domain.state_machines import JobStatus  # noqa: E402
from notes_graphrag.persistence.migrations import migrate  # noqa: E402
from notes_graphrag.providers.capability_probes import (  # noqa: E402
    profile_fingerprint,
    run_probes,
)
from notes_graphrag.providers.gate import GatedLM  # noqa: E402
from notes_graphrag.retrieval.service import Retriever  # noqa: E402

MODES = ("vector", "hybrid", "graph")


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def validate_dataset(notes: list[dict], questions: list[dict]) -> None:
    note_ids = {note["id"] for note in notes}
    if not notes or not questions or len(note_ids) != len(notes):
        raise ValueError("Dataset must be nonempty and note IDs unique")
    if len({q["id"] for q in questions}) != len(questions):
        raise ValueError("Question IDs must be unique")
    for question in questions:
        expected = question["expected_notes"]
        if bool(expected) != question["answerable"] or not set(expected) <= note_ids:
            raise ValueError("Expected note labels must exist and agree with answerability")


def endpoint_key(uri: str) -> tuple[str, int]:
    url = urlsplit(uri)
    host = (url.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "host.docker.internal"):
        host = "local"
    return host, url.port or 7687


def prepare_live(s: Settings, target: str, exclusive: bool) -> Settings:
    if not exclusive:
        raise ValueError(
            "Live evaluation requires --exclusive-model-server; stop other real-model traffic"
        )
    if not target or endpoint_key(target) == endpoint_key(s.neo4j_uri):
        raise ValueError("Use --target-uri pointing to a separate, empty Neo4j container/port")
    s.require_live_models()
    from neo4j import GraphDatabase

    isolated = s.model_copy(
        update={
            "neo4j_uri": target,
            "workspace_id": "eval-" + uuid.uuid4().hex,
            "graphrag_demo": False,
        }
    )
    with GraphDatabase.driver(
        target, auth=(s.neo4j_username, s.neo4j_password.get_secret_value())
    ) as driver:
        with driver.session(database=s.neo4j_database) as session:
            count = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
            if count:
                raise ValueError(
                    "Evaluation target is not empty. Use a fresh volume; no data was deleted"
                )
        migrate(driver, s.neo4j_database, s.embedding_dimensions)
    return isolated


class RecordingRetriever(Retriever):
    def reset(self) -> None:
        self.observed = []
        self.elapsed_ms = 0.0

    def retrieve(self, question):
        started = time.perf_counter()
        try:
            result = super().retrieve(question)
            self.observed.append(result)
            return result
        finally:
            self.elapsed_ms += (time.perf_counter() - started) * 1000


def distribution(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "p50": None, "p95": None}
    values = sorted(values)
    return {
        "count": len(values),
        "p50": round(statistics.median(values), 2),
        "p95": round(values[max(0, int(round(0.95 * (len(values) - 1))))], 2),
    }


def summarise(mode: str, rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    recall = [len(set(r["expected"]) & set(r["found"])) / len(r["expected"]) for r in answerable]
    hop2 = [r for r in answerable if r["hops"] == 2]
    return {
        "mode": mode,
        "counts": {
            "questions": len(rows),
            "answerable": len(answerable),
            "unanswerable": len(unanswerable),
            "errors": sum(r["error_code"] is not None for r in rows),
        },
        "evidence_recall_mean": round(statistics.mean(recall), 3) if recall else None,
        "full_evidence_hit": sum(set(r["expected"]) <= set(r["found"]) for r in answerable),
        "multi_hop_full_coverage": sum(set(r["expected"]) <= set(r["found"]) for r in hop2),
        "multi_hop_total": len(hop2),
        "abstention_correct": sum(r["status"] == "insufficient_evidence" for r in unanswerable),
        "answered_when_answerable": sum(r["status"] in ("answered", "partial") for r in answerable),
        "citations_all_valid": all(r["citations_valid"] and r["error_code"] is None for r in rows),
        "citation_count": sum(len(r["citations"]) for r in rows),
        "retrieval_ms": distribution([r["retrieval_ms"] for r in rows]),
        "end_to_end_ms": distribution([r["end_to_end_ms"] for r in rows]),
        "inference_wait_ms": distribution([r["inference_wait_ms"] for r in rows]),
        "first_pass_end_to_end_ms": distribution(
            [r["end_to_end_ms"] for r in rows if r["pass"] == 0]
        ),
        "warm_end_to_end_ms": distribution([r["end_to_end_ms"] for r in rows if r["pass"] > 0]),
        "semantic_review": "pending human review; citation offsets do not prove answer correctness",
        "per_question": rows,
    }


def ingest(ctx, notes: list[dict]) -> tuple[dict[str, str], list[dict]]:
    ids, jobs, rows = {}, {}, []
    started = time.perf_counter()
    for note in notes:
        sub = ctx.notes.create(note["title"], note["text"], "eval-" + uuid.uuid4().hex)
        ids[sub.note.note_id] = note["id"]
        jobs[sub.job.job_id] = (note["id"], time.perf_counter())
    deadline = time.monotonic() + max(120, len(notes) * ctx.settings.provider_timeout_seconds * 5)
    while jobs:
        if time.monotonic() > deadline:
            for _jid, (nid, t0) in jobs.items():
                rows.append(
                    {
                        "note_id": nid,
                        "status": "TIMEOUT",
                        "error_code": "INGESTION_TIMEOUT",
                        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
                    }
                )
            break
        ctx.store.heartbeat(datetime.now(UTC))
        worked = ctx.worker.run_once()
        for jid, (nid, t0) in list(jobs.items()):
            job = ctx.store.get_job(jid)
            if job and job.status in (
                JobStatus.SUCCEEDED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
                JobStatus.SUPERSEDED,
            ):
                rows.append(
                    {
                        "note_id": nid,
                        "status": job.status.value,
                        "error_code": job.error_code,
                        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
                    }
                )
                del jobs[jid]
        if worked is None:
            time.sleep(0.1)
    print(
        f"Ingestion: {sum(r['status'] == 'SUCCEEDED' for r in rows)}/{len(notes)} succeeded "
        f"in {time.perf_counter() - started:.1f}s",
        flush=True,
    )
    return ids, rows


def evaluate_mode(ctx, mode: str, questions: list[dict], ids: dict[str, str], repeats: int) -> dict:
    base = ctx.answers.retriever
    retriever = RecordingRetriever(
        ctx.knowledge, base.emb, ctx.settings, query_template=base.template, mode=mode
    )
    qa = AnswerService(
        ctx.knowledge,
        retriever,
        ctx.answers.chat,
        ctx.settings,
        review_answers=ctx.answers.review_answers,
    )
    rows = []
    for repeat in range(repeats):
        for q in questions:
            retriever.reset()
            started = time.perf_counter()
            gate_before = ctx.gate.wait_seconds_total
            row = {
                "qid": q["id"],
                "question": q["question"],
                "answerable": q["answerable"],
                "expected": q["expected_notes"],
                "found": [],
                "lang": q["lang"],
                "hops": q["hops"],
                "pass": repeat,
                "status": "error",
                "answer": "",
                "citations": [],
                "citations_valid": False,
                "error_code": None,
                "semantic_correct": None,
                "grounded": None,
                "review_guidance": q.get("review_guidance", "Check answer against cited passages"),
            }
            try:
                ans = qa.ask(q["question"])
                valid = True
                for c in ans.citations:
                    revision = ctx.store.get_revision(c.revision_id)
                    valid = (
                        valid
                        and revision is not None
                        and revision.text[c.start_char : c.end_char] == c.quote
                    )
                row.update(
                    status=ans.status,
                    answer=ans.answer,
                    citations=[asdict(c) for c in ans.citations],
                    citations_valid=valid,
                    answer_generation_attempts=ans.diagnostics.get("answer_generation_attempts", 0),
                    source_chain_check=ans.diagnostics.get("source_chain_check"),
                    semantic_review_calls=ans.diagnostics.get("semantic_review_calls", 0),
                    semantic_review=ans.diagnostics.get("semantic_review"),
                    semantic_review_uncertain=ans.diagnostics.get(
                        "semantic_review_uncertain", False
                    ),
                    source_qualifier_fallback=ans.diagnostics.get(
                        "source_qualifier_fallback", False
                    ),
                )
            except AppError as exc:
                row["error_code"] = exc.code
            except Exception as exc:
                row["error_code"] = type(exc).__name__
            if retriever.observed:
                last = retriever.observed[-1]
                found = set()
                for item in last.pack.items:
                    revision = ctx.store.get_revision(item.revision_id)
                    if revision and revision.note_id in ids:
                        found.add(ids[revision.note_id])
                row["found"] = sorted(found)
                row["evidence"] = [
                    {
                        "evidence_id": item.evidence_id,
                        "text": item.text,
                        "revision_id": item.revision_id,
                    }
                    for item in last.pack.items
                ]
            row.update(
                retrieval_ms=round(retriever.elapsed_ms, 2),
                end_to_end_ms=round((time.perf_counter() - started) * 1000, 2),
                inference_wait_ms=round((ctx.gate.wait_seconds_total - gate_before) * 1000, 2),
            )
            rows.append(row)
            print(
                f"{mode} pass={repeat} {q['id']}: {row['status']} {row['error_code'] or ''}",
                flush=True,
            )
    return summarise(mode, rows)


def extraction_report(ctx, notes, ids):
    by_eval = {eid: nid for nid, eid in ids.items()}
    rows = []
    for note in notes:
        claims = ctx.knowledge.claims_for_note(by_eval[note["id"]])
        actual = [
            {
                "subject": c.subject,
                "predicate": c.predicate,
                "object": c.object,
                "polarity": c.polarity,
                "modality": c.modality,
                "quote": c.evidence_quote,
            }
            for c in claims
        ]
        expected = note.get("expected_claims")

        def key(c):
            return tuple(
                str(c[k]).casefold()
                for k in ("subject", "predicate", "object", "polarity", "modality")
            )

        expected_set = {key(c) for c in expected} if expected is not None else set()
        actual_set = {key(c) for c in actual}
        rows.append(
            {
                "note_id": note["id"],
                "expected": expected,
                "actual": actual,
                "exact_matches": len(expected_set & actual_set) if expected is not None else None,
                "missing": len(expected_set - actual_set) if expected is not None else None,
                "extra": len(actual_set - expected_set) if expected is not None else None,
            }
        )
    return {
        "comparison": "Exact names/predicate/polarity/modality; aliases require human review",
        "notes": rows,
    }


def write_report(out: Path, report: dict, thresholds: dict | None) -> bool:
    summaries = report["summaries"]
    failures = []
    if thresholds:
        for s in summaries:
            if s["mode"] not in thresholds.get("modes", MODES):
                continue
            abstain_total = s["counts"]["unanswerable"]
            values = {
                "min_evidence_recall": s["evidence_recall_mean"] or 0,
                "min_abstention_rate": s["abstention_correct"] / abstain_total
                if abstain_total
                else 1,
                "max_end_to_end_p95_ms": s["end_to_end_ms"]["p95"] or float("inf"),
                "max_errors": s["counts"]["errors"],
            }
            for name, value in values.items():
                if name in thresholds:
                    failed = (
                        value < thresholds[name]
                        if name.startswith("min_")
                        else value > thresholds[name]
                    )
                    if failed:
                        failures.append(f"{s['mode']}: {name} failed ({value})")
    report["acceptance"] = {
        "thresholds": thresholds,
        "failures": failures,
        "quality_approved": False,
        "detail": "Human semantic review and agreed thresholds required",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# GraphRAG evaluation",
        "",
        f"Provider: **{report['provider']}**; split: **{report['split']}**.",
        "",
        "Citation validity is structural. Semantic correctness requires review.",
        "",
        "| Mode | Evidence recall | Correct abstentions | Errors | Answer p95 ms |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in summaries:
        lines.append(
            f"| {s['mode']} | {s['evidence_recall_mean']} | "
            f"{s['abstention_correct']}/{s['counts']['unanswerable']} | "
            f"{s['counts']['errors']} | {s['end_to_end_ms']['p95']} |"
        )
    lines += [
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(report["metadata"], indent=2),
        "```",
        "",
        "## Limits",
        "",
        "First pass can already have warm models after probe/ingestion.",
        "Warm pass timings are reported separately when --repeats is greater than one.",
        "RAM/VRAM are sampled whole-host figures. See report.json for ingestion failures.",
        "Failed requests remain in denominators and latency distributions.",
        "",
        "## Per-question review",
        "",
    ]
    for s in summaries:
        for r in s["per_question"]:
            lines += [
                f"### {s['mode']} / {r['qid']} / pass {r['pass']}",
                "",
                r["question"],
                "",
                f"Status: {r['status']}; error: {r['error_code']}",
                "",
                r["answer"] or "(no answer)",
                "",
                f"Review: {r['review_guidance']}",
                "",
            ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return not failures


def main() -> int:
    logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true")
    ap.add_argument(
        "--target-uri", help="Separate EMPTY evaluation Neo4j URI; uses .env credentials"
    )
    ap.add_argument("--exclusive-model-server", action="store_true")
    ap.add_argument(
        "--split",
        choices=("baseline", "validation", "holdout", "holdout2", "holdout3", "holdout4"),
        default="baseline",
    )
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--out", type=Path, default=ROOT / "reports/evaluation")
    ap.add_argument("--thresholds", type=Path, help="Previously agreed numeric thresholds (JSON)")
    args = ap.parse_args()
    if args.repeats < 1:
        ap.error("--repeats must be positive")
    suffix = "" if args.split == "baseline" else "." + args.split
    note_path = ROOT / "evaluation" / f"notes{suffix}.jsonl"
    question_path = ROOT / "evaluation" / f"questions{suffix}.jsonl"
    notes, questions = load(note_path), load(question_path)
    validate_dataset(notes, questions)
    run_dir = args.out / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6])
    monitor = ResourceMonitor()
    monitor.start()
    ctx = None
    providers = None
    report = {
        "provider": "LIVE LM Studio" if args.live else "DEMO rule-based fakes",
        "split": args.split,
        "summaries": [],
        "ingestion": [],
        "fatal_error": None,
    }
    source_hash = hashlib.sha256(
        (ROOT / "src/notes_graphrag/ingestion/worker.py").read_bytes()
        + (ROOT / "src/notes_graphrag/ingestion/extraction.py").read_bytes()
    ).hexdigest()
    answer_prompt_hash = hashlib.sha256(
        (ROOT / "src/notes_graphrag/prompts/answer_v1.txt").read_bytes()
    ).hexdigest()
    code = 0
    try:
        s = Settings() if args.live else Settings(_env_file=None)
        if args.live:
            s = prepare_live(s, args.target_uri, args.exclusive_model_server)
            store, _, connection = build_storage(s, "neo4j")
            providers = build_providers(s, demo=False)
            try:
                gate = build_gate(s, store, providers)
                probe = run_probes(
                    GatedLM(providers.lm, gate, "eval-probe"),
                    s,
                    embedding_provider=GatedLM(providers.emb, gate, "eval-embedding"),
                )
                report["probe"] = [asdict(r) for r in probe]
                if not all(r.ok for r in probe):
                    raise ValueError("Live capability probes failed; see report")
                store.record_probe(
                    profile_fingerprint(s),
                    True,
                    [{"name": r.name, "ok": r.ok, "code": r.code} for r in probe],
                    datetime.now(UTC),
                )
            finally:
                providers.close()
                connection.close()
            ctx = build_context(s, demo=False, backend="neo4j")
        else:
            ctx = build_context(s, demo=True, backend="memory")
        ids, report["ingestion"] = ingest(ctx, notes)
        report["extraction"] = extraction_report(ctx, notes, ids)
        for mode in MODES:
            report["summaries"].append(evaluate_mode(ctx, mode, questions, ids, args.repeats))
        if any(r["status"] != "SUCCEEDED" for r in report["ingestion"]):
            code = 1
        if any(s["counts"]["errors"] or not s["citations_all_valid"] for s in report["summaries"]):
            code = 1
    except Exception as exc:
        report["fatal_error"] = {
            "code": exc.code if isinstance(exc, AppError) else type(exc).__name__,
            "detail": str(exc)
            if type(exc) is ValueError
            else "See dependency/configuration checks",
        }
        print(f"Evaluation could not complete: {report['fatal_error']}", file=sys.stderr)
        code = 1
    finally:
        report["resources"] = monitor.finish()
        if ctx is not None and ctx.closeable is not None:
            ctx.closeable.close()
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        )
        report["metadata"] = {
            "commit": commit.stdout.strip(),
            "recorded_at": datetime.now(UTC).isoformat(),
            "working_tree_dirty": bool(
                subprocess.run(
                    ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
                ).stdout.strip()
            ),
            "extraction_source_hash": source_hash,
            "answer_source_hash": hashlib.sha256(
                b"".join(
                    (ROOT / "src/notes_graphrag/answering" / f).read_bytes()
                    for f in (
                        "service.py",
                        "citations.py",
                        "support.py",
                        "review.py",
                        "technology_kinds.py",
                        "qualifiers.py",
                    )
                )
            ).hexdigest(),
            "dataset_hash": hashlib.sha256(
                note_path.read_bytes() + question_path.read_bytes()
            ).hexdigest(),
            "answer_prompt_hash": answer_prompt_hash,
            "review_prompt_hash": hashlib.sha256(
                (ROOT / "src/notes_graphrag/prompts/review_v1.txt").read_bytes()
            ).hexdigest(),
            "answerability_prompt_hash": hashlib.sha256(
                (ROOT / "src/notes_graphrag/prompts/answerability_v1.txt").read_bytes()
            ).hexdigest(),
            "repeats": args.repeats,
            "settings": {
                name: getattr(ctx.settings, name)
                for name in (
                    "extraction_model",
                    "answer_model",
                    "chat_temperature",
                    "llm_instruction_suffix",
                    "embedding_model",
                    "embedding_dimensions",
                    "embedding_profile",
                    "embedding_query_template",
                    "embedding_document_prefix",
                    "lm_studio_context_tokens",
                    "max_context_tokens",
                    "extraction_max_output_tokens",
                    "answer_max_output_tokens",
                    "provider_timeout_seconds",
                    "question_timeout_seconds",
                )
            }
            if ctx
            else None,
        }
        thresholds = json.loads(args.thresholds.read_text("utf-8")) if args.thresholds else None
        if not write_report(run_dir, report, thresholds):
            code = 1
        # Compatibility with the existing CI artifact location.
        (args.out / "summary.json").write_text(
            json.dumps(report["summaries"], indent=2), encoding="utf-8"
        )
        print(f"Report: {run_dir / 'report.md'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
