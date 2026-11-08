"""JSON views over store snapshots. Never exposes embeddings, prompts or credentials."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from notes_graphrag.core.errors import BadRequest
from notes_graphrag.domain.state_machines import JobStatus, RevisionStatus
from notes_graphrag.persistence.base import Store
from notes_graphrag.persistence.models import Job, Note
from notes_graphrag.retrieval.source import ClaimRecord

MAX_GRAPH_NODES, MAX_GRAPH_EDGES = 100, 150


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def encode_cursor(*parts: str) -> str:
    return base64.urlsafe_b64encode("\x1f".join(parts).encode()).decode()


def decode_cursor(cursor: str | None, n: int) -> list[str] | None:
    if not cursor:
        return None
    try:
        parts = base64.urlsafe_b64decode(cursor.encode()).decode().split("\x1f")
    except (ValueError, UnicodeDecodeError) as exc:
        raise BadRequest("invalid cursor", code="INVALID_CURSOR") from exc
    if len(parts) != n:
        raise BadRequest("invalid cursor", code="INVALID_CURSOR")
    return parts


def job_view(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "note_id": job.note_id,
        "revision_id": job.revision_id,
        "status": job.status.value,
        "stage": job.stage.value if job.stage and job.status == JobStatus.RUNNING else None,
        "attempt": job.attempt,
        "chunks_total": job.chunks_total,
        "chunks_done": job.chunks_done,
        "error_code": job.error_code,
    }


def note_state(store: Store, note: Note) -> str:
    desired = store.get_revision(note.desired_revision_id)
    if desired is None:
        return "processing"
    if desired.status == RevisionStatus.READY:
        return "ready"
    if desired.status == RevisionStatus.FAILED:
        return "failed_update" if note.active_revision_id else "failed"
    return "processing"


def note_view(store: Store, note: Note) -> dict[str, Any]:
    job = store.job_for_revision(note.desired_revision_id)
    return {
        "note_id": note.note_id,
        "title": note.title,
        "created_at": iso(note.created_at),
        "updated_at": iso(note.updated_at),
        "topic_id": note.topic_id,
        "metadata_version": note.metadata_version,
        "desired_revision_id": note.desired_revision_id,
        "state": note_state(store, note),
        "active_revision_id": note.active_revision_id,
        "pending_revision_id": (
            note.desired_revision_id
            if note.desired_revision_id != note.active_revision_id
            else None
        ),
        "job": job_view(job) if job else None,
    }


def graph_edges(
    claims: list[ClaimRecord],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], bool]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    limited = len(claims) > MAX_GRAPH_EDGES
    for c in claims[:MAX_GRAPH_EDGES]:
        new = {c.subject_id, c.object_id} - nodes.keys()
        if len(nodes) + len(new) > MAX_GRAPH_NODES:
            limited = True
            continue
        nodes[c.subject_id] = {"id": c.subject_id, "label": c.subject}
        nodes[c.object_id] = {"id": c.object_id, "label": c.object}
        edges.append(
            {
                "id": c.claim_id,
                "source": c.subject_id,
                "target": c.object_id,
                "predicate": c.predicate,
                "polarity": c.polarity,
                "modality": c.modality,
                "evidence": {
                    "note_id": c.note_id,
                    "revision_id": c.revision_id,
                    "title": c.title,
                    "start_char": c.evidence_start,
                    "end_char": c.evidence_end,
                    "quote": c.evidence_quote,
                },
            }
        )
    return nodes, edges, limited
