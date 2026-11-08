"""Shared workspace read models. Topic membership never changes extraction state."""

from __future__ import annotations

from dataclasses import dataclass

from notes_graphrag.persistence.models import Job, Note

COLORS = ("purple", "blue", "teal", "orange", "pink", "green", "yellow", "gray")


def fold(value: str) -> str:
    return value.casefold().replace("\u0307", "").replace("ı", "i")


@dataclass(frozen=True)
class Topic:
    topic_id: str
    name: str
    color_key: str
    version: int = 1
    note_count: int = 0


@dataclass(frozen=True)
class CatalogEntry:
    note: Note
    active_text: str
    desired_status: str
    job: Job | None


@dataclass(frozen=True)
class NoteLink:
    source: str
    target: str
    entities: tuple[tuple[str, str], ...]
