"""Extraction schema and the ordered validation pipeline (architecture 6.3)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from notes_graphrag.domain.ontology import (
    PREDICATES,
    EntityKind,
    Modality,
    Polarity,
    predicate_allows,
)
from notes_graphrag.providers.schema import strict_schema

SCHEMA_VERSION: Literal["1"] = "1"
_NS = uuid.UUID("0b6e5a4c-7e0b-4f55-8c5e-3b4a1f2d9c21")


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class Evidence(Span):
    quote: str = Field(min_length=1, max_length=2000)


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(min_length=1, max_length=32)
    name: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Full verbatim entity name. Keep Project/Proje and the following name together. "
            "Do not include a preceding person name or a Turkish case suffix."
        ),
    )
    kind: EntityKind
    mentions: list[Span] = Field(default_factory=list, max_length=50)


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_local_id: str
    predicate: str = Field(json_schema_extra={"enum": list(PREDICATES)})
    object_local_id: str
    polarity: Polarity = Field(
        default=Polarity.POSITIVE,
        description=(
            "POSITIVE unless the relationship itself is explicitly denied; "
            "NEGATED for does not / değil / kullanmıyor. Future time is not negation."
        ),
    )
    modality: Modality = Field(
        default=Modality.ASSERTED,
        description=(
            "POSSIBLE for may/might/could or Turkish -ebilir/-abilir; "
            "this overrides a future date. "
            "PLANNED only for an explicitly committed/approved plan for THIS relationship. "
            "REPORTED for an attributed report, otherwise ASSERTED."
        ),
    )
    evidence: Evidence
    temporal_text: str | None = Field(default=None, max_length=200)


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = SCHEMA_VERSION
    entities: list[ExtractedEntity] = Field(default_factory=list, min_length=0, max_length=100)
    claims: list[ExtractedClaim] = Field(default_factory=list, min_length=0, max_length=200)


class WireRelation(BaseModel):
    """Generate evidence and relationship before committing to entity boundaries/types."""

    model_config = ConfigDict(extra="forbid")
    quote: str = Field(min_length=1, max_length=2000)
    predicate: str = Field(json_schema_extra={"enum": list(PREDICATES)})
    modality: Modality = Field(
        default=Modality.ASSERTED, description=ExtractedClaim.model_fields["modality"].description
    )
    polarity: Polarity = Field(
        default=Polarity.POSITIVE, description=ExtractedClaim.model_fields["polarity"].description
    )
    subject: ExtractedEntity
    object: ExtractedEntity
    temporal_text: str | None = Field(default=None, max_length=200)


class RelationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relations: list[WireRelation] = Field(min_length=0, max_length=200)


def extraction_wire_schema() -> dict[str, object]:
    """Relationship-first wire format; persisted extraction/claim schema stays version 1."""
    schema = strict_schema(RelationOutput.model_json_schema())
    fields = schema["properties"]["relations"]["items"]["properties"]
    for role in ("subject", "object"):
        entity = fields[role]
        entity["properties"].pop("mentions")
        entity["required"].remove("mentions")
        entity["properties"] = {
            key: entity["properties"][key] for key in ("local_id", "kind", "name")
        }
    return schema


def _relations_to_internal(data: dict[str, Any]) -> dict[str, Any]:
    out = RelationOutput.model_validate(data)
    entities: dict[str, ExtractedEntity] = {}
    claims = []
    for relation in out.relations:
        for entity in (relation.subject, relation.object):
            previous = entities.get(entity.local_id)
            if previous and (previous.name, previous.kind) != (entity.name, entity.kind):
                raise ValueError("one local_id describes different entities")
            entities[entity.local_id] = entity
        claims.append(
            {
                "subject_local_id": relation.subject.local_id,
                "predicate": relation.predicate,
                "object_local_id": relation.object.local_id,
                "polarity": relation.polarity.value,
                "modality": relation.modality.value,
                "evidence": {"quote": relation.quote},
                "temporal_text": relation.temporal_text,
            }
        )
    return {"entities": [e.model_dump(mode="json") for e in entities.values()], "claims": claims}


def anchor_unique_evidence(raw_json: str, chunk_text: str) -> str:
    """Derive offsets only for unique, verbatim source quotes; never guess ambiguous matches.

    This does not relax validate_extraction: schema, ontology, identity and revision-global
    offset checks still apply to its output.
    """
    try:
        data = json.loads(raw_json)
        if isinstance(data, dict) and "relations" in data:
            data = _relations_to_internal(data)
        if not isinstance(data, dict) or not isinstance(data.get("claims", []), list):
            return raw_json
        for claim in data.get("claims", []):
            ev = claim.get("evidence") if isinstance(claim, dict) else None
            if isinstance(ev, dict) and "start" not in ev and "end" not in ev:
                quote = ev.get("quote")
                if not isinstance(quote, str) or not quote:
                    return raw_json
                start = chunk_text.find(quote)
                if start < 0 or chunk_text.find(quote, start + 1) != -1:
                    return raw_json
                ev.update(start=start, end=start + len(quote))
        out = ExtractionOutput.model_validate(data)
    except (ValueError, TypeError):
        return raw_json
    changed = data != json.loads(raw_json)
    for entity in out.entities:
        if len(entity.mentions) != 1:
            continue
        mention = entity.mentions[0]
        if chunk_text[mention.start : mention.end] == entity.name:
            continue
        start = chunk_text.find(entity.name)
        if start >= 0 and chunk_text.find(entity.name, start + 1) == -1:
            mention.start, mention.end = start, start + len(entity.name)
            changed = True
    for claim in out.claims:
        ev = claim.evidence
        if chunk_text[ev.start : ev.end] == ev.quote:
            continue
        start = chunk_text.find(ev.quote)
        if start >= 0 and chunk_text.find(ev.quote, start + 1) == -1:
            ev.start, ev.end = start, start + len(ev.quote)
            changed = True
    return json.dumps(out.model_dump(mode="json"), ensure_ascii=False) if changed else raw_json


@dataclass(frozen=True)
class ValidatedClaim:
    claim_id: str
    subject: ExtractedEntity
    object: ExtractedEntity
    predicate: str
    polarity: Polarity
    modality: Modality
    evidence_start: int  # revision-global
    evidence_end: int
    evidence_quote: str
    temporal_text: str | None


@dataclass
class ValidationReport:
    claims: list[ValidatedClaim] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def claim_id(revision_id: str, subj: str, pred: str, obj: str, start: int, end: int) -> str:
    return str(uuid.uuid5(_NS, f"{revision_id}|{subj}|{pred}|{obj}|{start}|{end}"))


def validate_extraction(
    raw_json: str,
    *,
    revision_id: str,
    revision_text: str,
    chunk_start: int,
    chunk_text: str,
) -> ValidationReport:
    """Validate in the documented order. Spans from the model are chunk-local."""
    report = ValidationReport()
    try:
        out = ExtractionOutput.model_validate_json(raw_json)
    except ValueError as exc:
        report.errors.append(f"schema: {exc}")
        return report

    ids = [e.local_id for e in out.entities]
    if len(ids) != len(set(ids)):
        report.errors.append("duplicate local entity ids")
        return report
    by_id = {e.local_id: e for e in out.entities}

    for e in out.entities:
        if e.kind == EntityKind.PROJECT and not e.name.startswith(("Project ", "Proje ")):
            matches = list(re.finditer(r"(?<!\w)" + re.escape(e.name) + r"(?!\w)", chunk_text))
            prefixes = [re.search(r"\b(Project|Proje) $", chunk_text[: m.start()]) for m in matches]
            if matches and all(prefixes):
                full_names = {f"{p.group(1)} {e.name}" for p in prefixes if p}
                if len(full_names) == 1:
                    report.errors.append(
                        f"entity {e.local_id}: truncated project name; "
                        f"use {next(iter(full_names))!r}"
                    )
        for m in e.mentions:
            if m.end > len(chunk_text) or m.start >= m.end:
                report.errors.append(f"entity {e.local_id}: mention span out of range")

    for c in out.claims:
        subj, obj = by_id.get(c.subject_local_id), by_id.get(c.object_local_id)
        if subj is None or obj is None:
            report.errors.append("claim references unknown entity")
            continue
        if not predicate_allows(c.predicate, subj.kind, obj.kind):
            report.errors.append(f"claim {c.predicate}: incompatible {subj.kind}->{obj.kind}")
            continue
        ev = c.evidence
        if ev.end > len(chunk_text) or ev.start >= ev.end:
            report.errors.append("claim evidence span out of range")
            continue
        if chunk_text[ev.start : ev.end] != ev.quote:
            report.errors.append("claim evidence quote does not match span")
            continue
        g0, g1 = chunk_start + ev.start, chunk_start + ev.end
        if revision_text[g0:g1] != ev.quote:
            report.errors.append("claim evidence not found at revision offset")
            continue
        # Cheap support check: both entity names must appear in the quote or
        # the chunk (names may be pronoun-resolved only through the chunk).
        if subj.name not in chunk_text or obj.name not in chunk_text:
            report.errors.append("claim entity name absent from source chunk")
            continue
        report.claims.append(
            ValidatedClaim(
                claim_id(revision_id, subj.name, c.predicate, obj.name, g0, g1),
                subj,
                obj,
                c.predicate,
                c.polarity,
                c.modality,
                g0,
                g1,
                ev.quote,
                c.temporal_text,
            )
        )
    return report
