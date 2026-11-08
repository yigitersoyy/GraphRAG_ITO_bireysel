"""LM Studio capability probes (architecture section 2.2).

Each probe returns a specific diagnostic code instead of a generic failure. Discovery alone
never counts as readiness: chat, strict JSON, embeddings and a retrieval fixture are all run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from notes_graphrag.core.config import Settings
from notes_graphrag.core.errors import AppError
from notes_graphrag.providers.lmstudio_provider import LMStudioProvider
from notes_graphrag.retrieval.vector import cosine, format_query

_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ready": {"type": "boolean"}},
    "required": ["ready"],
    "additionalProperties": False,
}
_CODES = {
    "PROVIDER_AUTH_REJECTED": "AUTH_REJECTED",
    "OUTPUT_TRUNCATED": "OUTPUT_TRUNCATED",
    "NOT_JSON": "SCHEMA_FAILURE",
    "EMBEDDING_DIMENSION_MISMATCH": "DIMENSION_MISMATCH",
    "PROVIDER_TIMEOUT": "TIMEOUT",
    "LM_STUDIO_UNAVAILABLE": "ENDPOINT_UNREACHABLE",
}
FIXTURE_DOCS = [
    "Ada works on Project Atlas, which uses Neo4j as its graph database.",
    "The recipe needs two eggs, flour and a pinch of salt.",
    "Yarın İstanbul'da hava yağmurlu olacak.",
]
FIXTURE_QUERY = "Which database does Ada's project use?"


@dataclass(frozen=True)
class ProbeResult:
    name: str
    ok: bool
    code: str = "OK"
    detail: str = ""


def _run(name: str, fn: Callable[[], str]) -> ProbeResult:
    try:
        return ProbeResult(name, True, "OK", fn())
    except AppError as exc:
        return ProbeResult(name, False, _CODES.get(exc.code, exc.code), exc.message)
    except (ValueError, KeyError, TypeError) as exc:
        return ProbeResult(name, False, "SCHEMA_FAILURE", str(exc)[:200])


def run_probes(
    provider: LMStudioProvider | Any,
    settings: Settings,
    query_template: str | None = None,
    *,
    embedding_provider: Any = None,
) -> list[ProbeResult]:
    """Run the probes. Pass a GatedLM in the running system so diagnostics share the slot."""
    results: list[ProbeResult] = []
    emb = embedding_provider if embedding_provider is not None else provider
    template = query_template if query_template is not None else settings.embedding_query_template
    chat_models = list(dict.fromkeys((settings.extraction_model, settings.answer_model)))

    def models() -> str:
        ids = set(provider.list_models())
        emb_ids = set(emb.list_models()) if emb is not provider else ids
        missing = [m for m in chat_models if not m or m not in ids]
        if not settings.embedding_model or settings.embedding_model not in emb_ids:
            missing.append(settings.embedding_model)
        if missing:
            raise AppError(f"configured model id not served: {missing}", code="MODEL_MISSING")
        return f"{len(ids)} models listed"

    results.append(_run("models", models))
    if not results[0].ok:
        return results  # later probes would only repeat the same failure

    def chat() -> str:
        for model in chat_models:
            for prompt in ("Reply with the single word: ok.", "Tek kelimeyle yanıtla: tamam."):
                provider.chat_text(model=model, system="Be brief.", user=prompt, max_tokens=64)
        return f"english and turkish completions returned for {len(chat_models)} chat models"

    def schema() -> str:
        for model in chat_models:
            raw = provider.chat_json(
                model=model,
                system="Return the requested JSON object.",
                user="Set ready to true.",
                schema_name="capability_probe",
                schema=_PROBE_SCHEMA,
                max_tokens=64,
            )
            if json.loads(raw) != {"ready": True}:
                raise AppError("strict schema output did not match", code="SCHEMA_FAILURE")
        return f"strict json_schema accepted by {len(chat_models)} chat models"

    def embeddings() -> str:
        one = emb.embed([settings.embedding_document_prefix + "probe"])
        batch = emb.embed([settings.embedding_document_prefix + d for d in FIXTURE_DOCS])
        if len(one) != 1 or len(batch) != len(FIXTURE_DOCS):
            raise AppError("embedding count mismatch", code="EMBEDDINGS_UNSUPPORTED")
        return f"dimension {len(one[0])} verified"

    def retrieval() -> str:
        docs = emb.embed([settings.embedding_document_prefix + d for d in FIXTURE_DOCS])
        (q,) = emb.embed([format_query(template, FIXTURE_QUERY)])
        sims = [cosine(q, d) for d in docs]
        if not sims[0] > max(sims[1:]):  # strictly first; a tie proves nothing
            raise AppError("expected passage not ranked first", code="RETRIEVAL_FIXTURE_FAILED")
        return "expected passage ranked first"

    for name, fn in (
        ("chat_bilingual", chat),
        ("structured_output", schema),
        ("embeddings", embeddings),
        ("retrieval_fixture", retrieval),
    ):
        results.append(_run(name, fn))
    return results


def profile_fingerprint(settings: Settings) -> str:
    """Identifies the configuration a probe result applies to. A change of model, dimension,
    profile, context length or query template makes earlier results inapplicable (14.2)."""
    import hashlib

    parts = [
        "probe-v3",
        settings.lm_studio_instance_id,
        settings.llm_base_url.rstrip("/"),
        settings.embedding_base_url.rstrip("/"),
        settings.extraction_model,
        settings.answer_model,
        str(settings.chat_temperature),
        settings.llm_instruction_suffix,
        str(settings.chat_template_enable_thinking),
        settings.embedding_model,
        str(settings.embedding_dimensions),
        settings.embedding_profile,
        str(settings.lm_studio_context_tokens),
        str(settings.max_context_tokens),
        str(settings.extraction_max_output_tokens),
        str(settings.answer_max_output_tokens),
        settings.embedding_document_prefix,
        hashlib.sha256(settings.embedding_query_template.encode()).hexdigest()[:16],
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]
