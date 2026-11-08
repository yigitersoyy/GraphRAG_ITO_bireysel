"""Different endpoints and answer models must be genuinely probed."""

import json

import httpx
import pytest
from pydantic import SecretStr

from notes_graphrag.answering.citations import AnswerOutput
from notes_graphrag.api.dependencies import build_context, build_providers
from notes_graphrag.core.config import Settings
from notes_graphrag.core.errors import DependencyUnavailable
from notes_graphrag.providers.capability_probes import profile_fingerprint, run_probes
from notes_graphrag.providers.lmstudio_provider import LMStudioProvider
from notes_graphrag.providers.schema import strict_schema


def settings(**over):
    return Settings(
        _env_file=None,
        **{
            "extraction_model": "extract",
            "answer_model": "answer",
            "embedding_model": "embed",
            "embedding_dimensions": 4,
            "embedding_query_template": "search_query: {question}",
            "embedding_document_prefix": "search_document: ",
            **over,
        },
    )


def test_qwen35_reasoning_is_disabled_in_both_chat_paths_and_profile():
    seen = []

    def handle(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}]},
        )

    provider = LMStudioProvider(
        base_url="http://model/v1", enable_thinking=False, transport=httpx.MockTransport(handle)
    )
    provider.chat_text(model="qwen/qwen3.5-9b", system="s", user="u", max_tokens=100)
    provider.chat_json(
        model="qwen/qwen3.5-9b",
        system="s",
        user="u",
        max_tokens=100,
        schema_name="ok",
        schema={"type": "object"},
    )
    assert all(
        b["reasoning_effort"] == "none" and b["chat_template_kwargs"] == {"enable_thinking": False}
        for b in seen
    )
    assert profile_fingerprint(
        settings(chat_template_enable_thinking=False)
    ) != profile_fingerprint(settings())


def test_split_endpoints_with_different_tokens_and_answer_schema_failure():
    requests = []

    def handle(req):
        requests.append(req)
        is_chat = req.url.host == "chat"
        expected_token = "Bearer c-token" if is_chat else "Bearer e-token"
        assert req.headers["authorization"] == expected_token
        if req.url.path.endswith("/models"):
            ids = ["extract", "answer"] if is_chat else ["embed"]
            return httpx.Response(200, json={"data": [{"id": x} for x in ids]})
        body = json.loads(req.content)
        if is_chat:
            content = '{"ready": true}' if "response_format" in body else "ok"
            truncated = body["model"] == "answer" and "response_format" in body
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": content},
                            "finish_reason": "length" if truncated else "stop",
                        }
                    ]
                },
            )
        vectors = []
        for i, text in enumerate(body["input"]):
            assert text.startswith(("search_query: ", "search_document: "))
            vectors.append(
                {
                    "index": i,
                    "embedding": [
                        float("database" in text or "Neo4j" in text),
                        float("recipe" in text),
                        float("yağmur" in text),
                        0.1,
                    ],
                }
            )
        return httpx.Response(200, json={"data": vectors})

    chat = LMStudioProvider(
        base_url="http://chat/v1",
        api_key=SecretStr("c-token"),
        transport=httpx.MockTransport(handle),
    )
    emb = LMStudioProvider(
        base_url="http://embed/v1",
        api_key=SecretStr("e-token"),
        embedding_model="embed",
        embedding_dimensions=4,
        transport=httpx.MockTransport(handle),
    )
    try:
        results = {r.name: r for r in run_probes(chat, settings(), embedding_provider=emb)}
        assert results["models"].ok and results["chat_bilingual"].ok
        assert results["structured_output"].code == "OUTPUT_TRUNCATED"
        assert results["embeddings"].ok and results["retrieval_fixture"].ok
        models = [
            json.loads(r.content)["model"]
            for r in requests
            if r.url.path.endswith("/chat/completions")
        ]
        assert "extract" in models and "answer" in models
    finally:
        chat.close()
        emb.close()


def test_same_endpoint_can_use_an_embedding_specific_token():
    providers = build_providers(settings(embedding_api_key=SecretStr("embedding-only")), demo=False)
    try:
        assert providers.emb is not providers.lm
    finally:
        providers.close()


def test_live_mode_never_silently_falls_back_to_demo():
    with pytest.raises(DependencyUnavailable, match="ANSWER_MODEL"):
        build_providers(settings(answer_model=""), demo=False)


def test_semantic_review_is_enabled_for_real_context_and_disabled_for_demo():
    live = build_context(settings(), demo=False)
    demo = build_context(Settings(_env_file=None), demo=True)
    try:
        assert live.answers.review_answers is True
        assert demo.answers.review_answers is False
    finally:
        live.closeable.close()
        demo.closeable.close()


@pytest.mark.parametrize(
    "change",
    [
        {"llm_base_url": "http://other/v1"},
        {"embedding_base_url": "http://embedding/v1"},
        {"lm_studio_instance_id": "other-instance"},
        {"embedding_document_prefix": "document: "},
        {"embedding_query_template": "query: {question}"},
        {"answer_max_output_tokens": 512},
        {"chat_temperature": 0.2},
        {"llm_instruction_suffix": "\n/no_think"},
    ],
)
def test_probe_evidence_is_invalidated_by_effective_configuration(change):
    assert profile_fingerprint(settings()) != profile_fingerprint(settings(**change))


def test_tokens_are_not_serialized_into_probe_fingerprints():
    assert profile_fingerprint(
        settings(lm_studio_api_key=SecretStr("first"))
    ) == profile_fingerprint(settings(lm_studio_api_key=SecretStr("second")))


def test_wire_schema_requires_sentences_and_citations_even_with_parser_defaults():
    schema = strict_schema(AnswerOutput.model_json_schema())
    assert set(schema["required"]) == {"status", "sentences", "missing_information"}
    sentence = schema["properties"]["sentences"]["items"]
    assert set(sentence["required"]) == {"text", "evidence_ids"}
    assert sentence["additionalProperties"] is False
    assert "default" not in json.dumps(schema)


def test_model_profile_options_apply_to_both_chat_and_recovery_calls():
    payloads = []

    def handle(req):
        payloads.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ready":true}'}, "finish_reason": "stop"}]},
        )

    provider = LMStudioProvider(
        base_url="http://local/v1",
        temperature=0.2,
        instruction_suffix="\n/no_think",
        transport=httpx.MockTransport(handle),
    )
    try:
        provider.chat_text(model="m", system="s", user="u", max_tokens=4)
        provider.chat_json(
            model="m", system="s", user="u", max_tokens=64, schema_name="probe", schema={}
        )
        assert all(p["temperature"] == 0.2 for p in payloads)
        assert all(p["messages"][-1]["content"] == "u\n/no_think" for p in payloads)
    finally:
        provider.close()


def test_deployment_model_preprocessing_does_not_leak_into_demo_embeddings():
    ctx = build_context(settings(), demo=True)
    observed = []
    original = ctx.worker.emb.inner.embed

    def record(texts):
        observed.extend(texts)
        return original(texts)

    ctx.worker.emb.inner.embed = record
    text = "Ada works on Project Atlas. Project Atlas uses Neo4j."
    question = "Which database does Ada's project use?"
    try:
        ctx.notes.create("Atlas", text, "demo-profile-check")
        ctx.worker.run_once()
        answer = ctx.answers.ask(question)
        assert answer.status == "answered"
        assert observed[:2] == [text, question]
    finally:
        ctx.closeable.close()


def test_recovery_probe_has_enough_budget_for_a_final_response(monkeypatch):
    seen = []

    class Runtime:
        def __init__(self, **kw):
            pass

        def chat_text(self, **kw):
            seen.append(kw["max_tokens"])
            if kw["max_tokens"] < 16:
                raise ValueError("reasoning prefix consumed the output budget")
            return "ok"

        def close(self):
            pass

    monkeypatch.setattr("notes_graphrag.api.dependencies.LMStudioProvider", Runtime)
    providers = build_providers(settings(), demo=False)
    try:
        providers.probe()
        assert seen == [64]
    finally:
        providers.close()
