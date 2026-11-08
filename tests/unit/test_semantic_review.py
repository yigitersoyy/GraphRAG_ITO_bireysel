"""Model-assisted semantic review rejects candidates and abstentions with bounded repair."""

import json

import pytest
from tests.unit.test_answering import A, B, Env, ScriptedChat

from notes_graphrag.answering.review import AnswerReview, explicit_requested_kind
from notes_graphrag.core.errors import GenerationInvalid, KnowledgeBaseChanged, QuestionTimeout
from notes_graphrag.providers.schema import strict_schema


class ReviewedChat(ScriptedChat):
    def __init__(self, answers, verdicts):
        super().__init__(outputs=answers)
        self.verdicts = list(verdicts)
        self.review_prompts = []
        self.availability_prompts = []
        self.available = True

    def chat_json(self, **kwargs):
        if kwargs["schema_name"] == "answerability":
            self.availability_prompts.append(kwargs["user"])
            return json.dumps(
                {"answerable": self.available, "reason": "Source support assessment."}
            )
        if kwargs["schema_name"] == "answer_review":
            self.review_prompts.append(kwargs["user"])
            verdict = self.verdicts.pop(0)
            if verdict == "malformed":
                return "{}"
            return json.dumps(
                {
                    "requested_kind": "DATABASE"
                    if verdict == "relabel"
                    else (
                        "PROGRAMMING_LANGUAGE"
                        if verdict in ("mismatch", "language_supported")
                        else "OTHER"
                    ),
                    "candidate_kind": "DATABASE"
                    if verdict in ("mismatch", "relabel")
                    else ("PROGRAMMING_LANGUAGE" if verdict == "language_supported" else "OTHER"),
                    "supported": verdict
                    in ("supported", "mismatch", "relabel", "language_supported"),
                    "reason": "Check the actual subject and attribute, not an adjacent fact.",
                }
            )
        return super().chat_json(**kwargs)


def insufficient():
    return json.dumps(
        {"status": "insufficient_evidence", "sentences": [], "missing_information": []}
    )


def reviewed(chat):
    env = Env([A, B], chat)
    env.qa.review_answers = True
    return env


@pytest.mark.parametrize("verdict", ["mismatch", "relabel"])
def test_source_linked_but_wrong_attribute_is_regenerated_and_not_returned(verdict):
    chat = ReviewedChat([], [verdict])
    chat.available = False
    env = reviewed(chat)
    # First answer is source-linked but not evidence of Ada's language. Second abstains.
    pack = env.retriever.retrieve("Which programming language does Ada use?").pack
    chat.outputs = [
        json.dumps(
            {
                "status": "answered",
                "sentences": [
                    {"text": "Ada uses Neo4j.", "evidence_ids": [i.evidence_id for i in pack.items]}
                ],
            }
        ),
        insufficient(),
    ]
    result = env.qa.ask("Which programming language does Ada use?")
    assert result.status == "insufficient_evidence" and not result.citations
    assert result.diagnostics["semantic_review_calls"] == 2
    assert result.diagnostics["answer_generation_attempts"] == 1
    assert chat.calls == 1 and len(chat.availability_prompts) == 1
    assert "QUESTION" in chat.review_prompts[0] and A in chat.review_prompts[0]


def test_unnecessary_abstention_is_also_reviewed_and_can_be_repaired():
    chat = ReviewedChat([insufficient()], ["supported"])
    result = reviewed(chat).qa.ask("Which database does Ada's project use?")
    assert result.status == "answered" and "Neo4j" in result.answer
    assert chat.calls == 2 and len(chat.review_prompts) == 1
    assert len(chat.availability_prompts) == 1


def test_malformed_review_still_fails_closed():
    chat = ReviewedChat([], ["malformed", "malformed"])
    with pytest.raises(GenerationInvalid):
        reviewed(chat).qa.ask("Which database does Ada's project use?")
    assert chat.calls == 2 and len(chat.review_prompts) == 2


def test_model_only_disagreement_requests_repair_then_returns_visible_uncertainty():
    chat = ReviewedChat([], ["unsupported", "unsupported"])
    result = reviewed(chat).qa.ask("Which database does Ada's project use?")
    assert result.status == "answered" and result.citations
    assert result.diagnostics["semantic_review_uncertain"] is True
    assert chat.calls == 2 and len(chat.review_prompts) == 2


def test_advisory_fallback_never_bypasses_bad_citations():
    raw = json.dumps({"status": "answered", "sentences": [{"text": "x", "evidence_ids": ["E99"]}]})
    chat = ReviewedChat([raw, raw], [])
    with pytest.raises(GenerationInvalid):
        reviewed(chat).qa.ask("Which database does Ada's project use?")
    assert not chat.review_prompts


def test_known_database_is_never_returned_as_a_language_even_after_repair():
    chat = ReviewedChat([], ["supported", "supported"])
    env = reviewed(chat)
    # Default answer contains Neo4j. An optimistic critic cannot approve a known type conflict.
    with pytest.raises(GenerationInvalid):
        env.qa.ask("Which programming language does Ada use?")


def test_structurally_invalid_candidate_does_not_reach_review():
    chat = ReviewedChat(['{"status":"answered","sentences":[]}'], ["supported"])
    result = reviewed(chat).qa.ask("Which database does Ada's project use?")
    assert result.status == "answered" and chat.calls == 2 and len(chat.review_prompts) == 1


def test_publication_during_review_discards_even_an_abstention():
    chat = ReviewedChat([insufficient(), insufficient()], ["supported", "supported"])
    chat.available = False
    env = reviewed(chat)
    original = chat.chat_json

    def changed(**kwargs):
        if kwargs["schema_name"] == "answerability":
            env.store.graph_ver += 1
        return original(**kwargs)

    chat.chat_json = changed
    with pytest.raises(KnowledgeBaseChanged):
        env.qa.ask("Which database does Ada's project use?")


def test_review_obeys_the_same_question_deadline():
    chat = ReviewedChat([], ["supported"])
    env = reviewed(chat)
    env.qa.clock = lambda: 0
    original = chat.chat_json

    def late(**kwargs):
        if kwargs["schema_name"] == "answer_review":
            env.qa.clock = lambda: 1000
        return original(**kwargs)

    chat.chat_json = late
    with pytest.raises(QuestionTimeout):
        env.qa.ask("Which database does Ada's project use?")


def test_proposed_abstention_is_checked_without_showing_the_candidate_or_graph_hints():
    chat = ReviewedChat([insufficient()], [])
    chat.available = False
    result = reviewed(chat).qa.ask("Which language does Ada use?")
    assert result.status == "insufficient_evidence" and chat.calls == 1
    assert result.diagnostics["answer_generation_attempts"] == 1
    assert result.diagnostics["semantic_review_calls"] == 1
    assert A in chat.availability_prompts[0]
    assert "CANDIDATE" not in chat.availability_prompts[0]
    assert "EXTRACTED CLAIMS" not in chat.availability_prompts[0]


@pytest.mark.parametrize(
    "question",
    [
        "Which programming language does Nia use?",
        "Nia hangi programlama dilini kullanıyor?",
        "What programming languages does this project use?",
    ],
)
def test_explicit_language_request_cannot_be_relabeled_by_the_model(question):
    assert explicit_requested_kind(question) == "PROGRAMMING_LANGUAGE"
    assert explicit_requested_kind("Which database uses a programming language?") is None


def test_type_mismatch_keeps_repair_when_actual_language_evidence_exists():
    chat = ReviewedChat([], ["relabel", "language_supported"])
    env = Env(["Quinn uses Python."], chat)
    env.qa.review_answers = True
    pack = env.retriever.retrieve("Which programming language does Quinn use?").pack
    eid = pack.items[0].evidence_id
    chat.outputs = [
        json.dumps({"status": "answered", "sentences": [{"text": text, "evidence_ids": [eid]}]})
        for text in ("Quinn uses Neo4j.", "Quinn uses Python.")
    ]
    result = env.qa.ask("Which programming language does Quinn use?")
    assert result.status == "answered" and "Python" in result.answer
    assert chat.calls == 2 and len(chat.availability_prompts) == 1
    assert result.diagnostics["semantic_review_calls"] == 3


@pytest.mark.parametrize(
    "question",
    [
        "Which programming language does Quinn use?",
        "Quinn hangi programlama dilini kullanıyor?",
    ],
)
@pytest.mark.parametrize("kind", ["supported", "language_supported"])
def test_supported_language_answer_is_not_rejected_for_an_unspecified_category(question, kind):
    chat = ReviewedChat([], [kind])
    env = Env(["Quinn uses Python."], chat)
    env.qa.review_answers = True
    pack = env.retriever.retrieve(question).pack
    chat.outputs = [
        json.dumps(
            {
                "status": "answered",
                "sentences": [
                    {"text": "Quinn uses Python.", "evidence_ids": [pack.items[0].evidence_id]}
                ],
            }
        )
    ]
    result = env.qa.ask(question)
    assert result.status == "answered" and "Python" in result.answer
    assert not chat.availability_prompts


def test_review_wire_grounds_reason_before_committing_to_a_kind():
    schema = strict_schema(AnswerReview.model_json_schema())
    assert next(iter(schema["properties"])) == "reason"
