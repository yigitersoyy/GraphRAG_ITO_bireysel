"""Evaluation safety, failure accounting and single-pass retrieval measurement."""

import pytest
from neo4j import GraphDatabase
from scripts.evaluate import evaluate_mode, ingest, prepare_live, summarise

from notes_graphrag.api.dependencies import build_context
from notes_graphrag.core.config import Settings
from notes_graphrag.retrieval.service import Retriever


def test_live_evaluation_rejects_primary_database_alias_before_connecting(monkeypatch):
    def unexpected(*a, **kw):
        pytest.fail("The primary database must not even be opened")

    monkeypatch.setattr(GraphDatabase, "driver", unexpected)
    with pytest.raises(ValueError, match="separate"):
        prepare_live(Settings(_env_file=None), "bolt://localhost:7687", True)


def test_live_evaluation_requires_exclusive_model_access():
    with pytest.raises(ValueError, match="exclusive"):
        prepare_live(Settings(_env_file=None), "bolt://localhost:27687", False)


def test_nonempty_live_target_is_not_migrated_or_erased(monkeypatch):
    queries = []

    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def session(self, **kw):
            return self

        def run(self, query):
            queries.append(query)
            return self

        def single(self):
            return {"n": 1}

    monkeypatch.setattr(GraphDatabase, "driver", lambda *a, **kw: Fake())
    s = Settings(_env_file=None, extraction_model="c", answer_model="c", embedding_model="e")
    with pytest.raises(ValueError, match="not empty"):
        prepare_live(s, "bolt://127.0.0.1:27687", True)
    assert queries == ["MATCH (n) RETURN count(n) AS n"]


def test_measurement_uses_the_same_retrieval_as_the_answer(monkeypatch):
    ctx = build_context(Settings(_env_file=None), demo=True)
    ids, jobs = ingest(
        ctx,
        [
            {
                "id": "n1",
                "title": "Atlas",
                "text": "Ada works on Project Atlas. Project Atlas uses Neo4j.",
            }
        ],
    )
    calls = []
    original = Retriever.retrieve

    def recorded(self, question):
        calls.append(question)
        return original(self, question)

    monkeypatch.setattr(Retriever, "retrieve", recorded)
    summary = evaluate_mode(
        ctx,
        "graph",
        [
            {
                "id": "q1",
                "lang": "en",
                "hops": 2,
                "question": "Which database does Ada's project use?",
                "answerable": True,
                "expected_notes": ["n1"],
            }
        ],
        ids,
        1,
    )
    assert len(calls) == 1
    assert jobs[0]["status"] == "SUCCEEDED"
    assert summary["full_evidence_hit"] == 1 and summary["citations_all_valid"]
    assert summary["per_question"][0]["semantic_correct"] is None
    ctx.closeable.close()


def test_failed_request_stays_in_metrics_denominators():
    row = {
        "answerable": True,
        "expected": ["n"],
        "found": [],
        "hops": 1,
        "status": "error",
        "error_code": "PROVIDER_TIMEOUT",
        "citations_valid": False,
        "citations": [],
        "retrieval_ms": 100,
        "end_to_end_ms": 500,
        "inference_wait_ms": 10,
        "pass": 0,
    }
    summary = summarise("graph", [row])
    assert summary["counts"]["errors"] == 1
    assert summary["evidence_recall_mean"] == 0
    assert summary["answered_when_answerable"] == 0
    assert summary["end_to_end_ms"]["p95"] == 500
