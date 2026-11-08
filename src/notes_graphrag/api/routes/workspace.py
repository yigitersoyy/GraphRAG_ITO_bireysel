"""Workspace catalog, explicit topics and a bounded note map (no LLM calls)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from notes_graphrag.api.common import ctx_of, ok
from notes_graphrag.api.routes.graph import _edges
from notes_graphrag.api.views import decode_cursor, encode_cursor, iso, job_view
from notes_graphrag.core.errors import BadRequest
from notes_graphrag.persistence.base import Store
from notes_graphrag.persistence.workspace import COLORS, CatalogEntry, fold

router = APIRouter(prefix="/api/v1")


class TopicBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color_key: Literal["purple", "blue", "teal", "orange", "pink", "green", "yellow", "gray"] = (
        "purple"
    )
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value or not value.isprintable():
            raise ValueError("topic name must be printable and nonempty")
        return value


class MetadataBody(BaseModel):
    topic_id: str | None = Field(default=None, min_length=1, max_length=100)
    expected_version: int = Field(ge=0)


def catalog_view(entry: CatalogEntry) -> dict[str, Any]:
    n, status = entry.note, entry.desired_status
    state = (
        "ready"
        if status == "READY"
        else ("failed_update" if n.active_revision_id else "failed")
        if status == "FAILED"
        else "processing"
    )
    return dict(
        note_id=n.note_id,
        title=n.title,
        created_at=iso(n.created_at),
        updated_at=iso(n.updated_at),
        topic_id=n.topic_id,
        metadata_version=n.metadata_version,
        active_revision_id=n.active_revision_id,
        desired_revision_id=n.desired_revision_id,
        pending_revision_id=(
            n.desired_revision_id if n.desired_revision_id != n.active_revision_id else None
        ),
        state=state,
        job=job_view(entry.job) if entry.job else None,
    )


def catalog_page(
    store: Store, q: str, topic_id: str | None, cursor: str | None, limit: int
) -> tuple[list[CatalogEntry], str | None, int]:
    signature = hashlib.sha256(f"{fold(q)}\x00{topic_id}".encode()).hexdigest()[:24]
    parts = decode_cursor(cursor, 3)
    after = None
    if parts:
        if parts[0] != signature:
            raise BadRequest("cursor belongs to different filters", code="INVALID_CURSOR")
        try:
            stamp = datetime.fromisoformat(parts[1])
            if stamp.tzinfo is None:
                raise ValueError("timezone required")
        except ValueError as exc:
            raise BadRequest("invalid cursor timestamp", code="INVALID_CURSOR") from exc
        after = (stamp, parts[2])
    entries, more, total = store.catalog(q, topic_id, after, limit)
    nxt = (
        encode_cursor(signature, entries[-1].note.created_at.isoformat(), entries[-1].note.note_id)
        if more and entries
        else None
    )
    return entries, nxt, total


@router.get("/topics")
def topics(request: Request) -> JSONResponse:
    store = ctx_of(request).store
    return ok(
        request,
        dict(
            items=[asdict(t) for t in store.list_topics()],
            metadata_version=store.metadata_version(),
            color_keys=list(COLORS),
        ),
    )


@router.post("/topics")
def create_topic(request: Request, body: TopicBody) -> JSONResponse:
    topic = ctx_of(request).store.save_topic(None, body.name, body.color_key, None)
    return ok(request, asdict(topic), 201)


@router.patch("/topics/{topic_id}")
def edit_topic(request: Request, topic_id: str, body: TopicBody) -> JSONResponse:
    if body.expected_version is None:
        raise BadRequest("expected_version is required")
    topic = ctx_of(request).store.save_topic(
        topic_id, body.name, body.color_key, body.expected_version
    )
    return ok(request, asdict(topic))


@router.delete("/topics/{topic_id}")
def delete_topic(
    request: Request, topic_id: str, expected_version: Annotated[int, Query(ge=1)]
) -> JSONResponse:
    ctx_of(request).store.delete_topic(topic_id, expected_version)
    return ok(request, dict(deleted=True))


@router.patch("/notes/{note_id}/metadata")
def note_metadata(request: Request, note_id: str, body: MetadataBody) -> JSONResponse:
    n = ctx_of(request).store.set_note_topic(
        note_id, body.topic_id, body.expected_version, datetime.now(UTC)
    )
    return ok(
        request,
        dict(
            note_id=n.note_id,
            topic_id=n.topic_id,
            metadata_version=n.metadata_version,
            updated_at=iso(n.updated_at),
        ),
    )


@router.get("/workspace/notes")
def catalog(
    request: Request,
    q: str = "",
    topic_id: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> JSONResponse:
    entries, nxt, total = catalog_page(ctx_of(request).store, q[:200], topic_id, cursor, limit)
    return ok(request, dict(items=[catalog_view(e) for e in entries], next_cursor=nxt, total=total))


@router.get("/workspace/map")
def note_map(
    request: Request,
    topic_id: str | None = None,
    q: str = "",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=300)] = 300,
) -> JSONResponse:
    store = ctx_of(request).store
    before = store.graph_version()
    entries, nxt, total = catalog_page(store, q[:200], topic_id, cursor, limit)
    links, edges_limited = store.workspace_links([e.note.note_id for e in entries], 600)
    selected = [e.note.note_id for e in entries]
    claims = ctx_of(request).knowledge.claims_for_notes(selected, 151)
    entities, relations, relations_limited = _edges(claims)
    return ok(
        request,
        dict(
            nodes=[catalog_view(e) for e in entries],
            topics=[asdict(t) for t in store.list_topics()],
            entities=list(entities.values()),
            relations=relations,
            relations_limited=relations_limited,
            edges=[
                dict(
                    id=f"shared:{link.source}:{link.target}",
                    source=link.source,
                    target=link.target,
                    kind="shared_entity",
                    entities=[dict(entity_id=eid, name=name) for eid, name in link.entities],
                )
                for link in links
            ],
            next_cursor=nxt,
            total=total,
            limited=bool(nxt) or edges_limited or relations_limited,
            edges_limited=edges_limited,
            graph_version=store.graph_version(),
            metadata_version=store.metadata_version(),
            changed_during_read=before != store.graph_version(),
            similarity_available=False,
        ),
    )


@router.get("/search")
def search(
    request: Request,
    q: Annotated[str, Query(max_length=200)] = "",
    kind: Literal["all", "note", "entity", "topic"] = "all",
    limit: Annotated[int, Query(ge=1, le=30)] = 12,
) -> JSONResponse:
    ctx = ctx_of(request)
    needle = fold(q.strip())
    if not needle:
        return ok(request, dict(items=[], limited=False))
    items: list[dict[str, Any]] = []
    limited = False
    if kind in ("all", "note"):
        entries, more, _ = ctx.store.catalog(q.strip(), None, None, limit)
        limited |= more
        for entry in entries:
            raw = entry.active_text
            at = fold(raw).find(needle)
            snippet = raw[max(0, at - 30) : max(0, at - 30) + 140].replace("\n", " ") if raw else ""
            items.append(
                dict(
                    kind="note",
                    id=entry.note.note_id,
                    label=entry.note.title,
                    snippet=snippet,
                    topic_id=entry.note.topic_id,
                )
            )
    if kind in ("all", "entity"):
        matches = [
            e
            for e in ctx.knowledge.entities()
            if any(needle in fold(s) for s in (e.name, *e.aliases))
        ]
        limited |= len(matches) > limit
        items.extend(
            dict(kind="entity", id=e.entity_id, label=e.name, snippet="Kaynaklı varlık")
            for e in matches[:limit]
        )
    if kind in ("all", "topic"):
        matches_t = [t for t in ctx.store.list_topics() if needle in fold(t.name)]
        limited |= len(matches_t) > limit
        items.extend(
            dict(kind="topic", id=t.topic_id, label=t.name, snippet=f"{t.note_count} not")
            for t in matches_t[:limit]
        )
    return ok(request, dict(items=items, limited=limited))
