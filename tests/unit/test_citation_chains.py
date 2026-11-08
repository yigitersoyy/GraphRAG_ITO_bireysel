"""Source ranges alone do not establish a multi-step answer's provenance."""

import json

from tests.unit.test_answering import A, B, Env, ScriptedChat

from notes_graphrag.answering.citations import AnswerOutput, validate_answer
from notes_graphrag.answering.support import citation_chain_errors


def candidate(ids):
    return AnswerOutput.model_validate(
        {
            "status": "answered",
            "sentences": [{"text": "Ada's project uses Neo4j.", "evidence_ids": ids}],
        }
    )


def test_missing_person_to_project_link_is_not_silently_added():
    env = Env([A, B])
    pack = env.retriever.retrieve("Which database does Ada's project use?").pack
    ids = {i.text: i.evidence_id for i in pack.items}
    only_property = candidate([ids[B]])
    assert citation_chain_errors("Which database does Ada's project use?", only_property, pack)
    assert only_property.sentences[0].evidence_ids == [ids[B]]
    assert not citation_chain_errors(
        "Which database does Ada's project use?", candidate([ids[A], ids[B]]), pack
    )


def test_missing_chain_requests_one_regeneration_and_preserves_graph_source():
    env = Env([A, B])
    pack = env.retriever.retrieve("Which database does Ada's project use?").pack
    prop = next(i.evidence_id for i in pack.items if i.text == B)
    env.chat.outputs = [candidate([prop]).model_dump_json()]
    result = env.qa.ask("Which database does Ada's project use?", include_graph=True)
    assert env.chat.calls == 2 and result.diagnostics["answer_generation_attempts"] == 2
    assert {c.note_id for c in result.citations} == {n.note_id for n in env.notes}
    for edge in result.graph["edges"]:
        evidence = edge["evidence"]
        source = env.store.get_revision(evidence["revision_id"])
        assert source.text[evidence["start_char"] : evidence["end_char"]] == evidence["quote"]


def test_raw_text_without_claims_is_not_rejected_for_lacking_graph_annotations():
    env = Env(["A receipt was signed on Friday."], ScriptedChat(keyword="receipt"))
    pack = env.retriever.retrieve("When was the receipt signed?").pack
    out = AnswerOutput.model_validate(
        {
            "status": "answered",
            "sentences": [{"text": "On Friday.", "evidence_ids": [pack.items[0].evidence_id]}],
        }
    )
    assert not pack.claims and not citation_chain_errors("When was the receipt signed?", out, pack)


def test_answered_and_missing_information_are_inconsistent():
    out = candidate([]).model_dump()
    out["missing_information"] = ["unknown"]
    assert validate_answer(json.dumps(out), Env([A, B]).retriever.retrieve("Ada").pack)[0] is None
