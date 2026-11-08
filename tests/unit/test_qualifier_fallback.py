from dataclasses import replace

import pytest

from notes_graphrag.answering.citations import validate_answer
from notes_graphrag.answering.qualifiers import qualified_use_fallback
from notes_graphrag.retrieval.evidence import EvidenceItem, EvidencePack
from notes_graphrag.retrieval.source import ClaimRecord


def fixture(modality="POSSIBLE", quote="Project Kite may use SQLite later."):
    item = EvidenceItem("E1", "n", "r", "c", ["c"], "Kite", quote, 0, len(quote))
    claim = ClaimRecord(
        "cl",
        "p",
        "Project Kite",
        "USES",
        "t",
        "SQLite",
        "POSITIVE",
        modality,
        "c",
        quote,
        0,
        len(quote),
        None,
        "n",
        "r",
        "Kite",
    )
    return EvidencePack([item], [(claim, ["E1"])])


@pytest.mark.parametrize(
    "modality,quote",
    [
        ("POSSIBLE", "Project Kite may use SQLite later."),
        ("PLANNED", "The approved plan is for Project Kite to use SQLite later."),
    ],
)
def test_qualified_source_answers_a_certainty_question_without_claiming_deployment(modality, quote):
    pack = fixture(modality, quote)
    out = qualified_use_fallback("Is SQLite use by Project Kite definite?", pack)
    assert out and out.status == "partial" and quote in out.sentences[0].text
    assert out.missing_information and out.sentences[0].evidence_ids == ["E1"]
    assert validate_answer(out.model_dump_json(), pack)[0] is not None


@pytest.mark.parametrize(
    "change", [{"modality": "ASSERTED"}, {"polarity": "NEGATED"}, {"subject_id": "another-project"}]
)
def test_conflicting_or_ambiguous_support_is_not_overridden(change):
    pack = fixture()
    claim = replace(pack.claims[0][0], **change)
    pack.claims.append((claim, ["E1"]))
    assert qualified_use_fallback("Is Project Kite using SQLite now?", pack) is None


def test_unrepresented_source_or_missing_quote_blocks_fallback():
    pack = fixture()
    pack.items.append(replace(pack.items[0], evidence_id="E2", text="Project Kite uses SQLite."))
    assert qualified_use_fallback("Is Project Kite using SQLite now?", pack) is None
    pack = fixture()
    pack.items[0] = replace(pack.items[0], text="unrelated")
    assert qualified_use_fallback("Is Project Kite using SQLite now?", pack) is None


@pytest.mark.parametrize(
    "question",
    [
        "Which database does Project Kite use?",
        "Is Project Other using SQLite now?",
        "Is Project Kite using MongoDB now?",
    ],
)
def test_fallback_is_limited_to_explicit_question_pair_and_certainty(question):
    assert qualified_use_fallback(question, fixture()) is None


def test_a_modality_label_alone_is_not_sufficient():
    assert (
        qualified_use_fallback(
            "Is Project Kite using SQLite now?", fixture(quote="Project Kite uses SQLite.")
        )
        is None
    )
