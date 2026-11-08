"""Filename-family grouping, independent of model extraction and source revisions."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import datetime

from notes_graphrag.core.errors import Conflict
from notes_graphrag.persistence.base import Store
from notes_graphrag.persistence.workspace import COLORS, Topic, fold


def suggested_topic(title: str, topics: Sequence[Topic] = ()) -> str | None:
    name = re.sub(r"\.(txt|md|pdf|docx|xlsx|xls)$", "", title.strip(), flags=re.I)
    name = re.sub(r"^\d+[_.\-\s]+", "", name)
    words = re.sub(r"[_\-\s]+", " ", name).strip()
    # Respect names already chosen by the user, including multiword topics.
    for topic in sorted(topics, key=lambda t: len(t.name), reverse=True):
        if fold(words) == fold(topic.name) or fold(words).startswith(fold(topic.name) + " "):
            return topic.name
    # Plain prose titles are not guessed. Structured file families have an explicit prefix.
    if "_" not in title and not re.match(r"^\d+[.\-]", title.strip()):
        return None
    prefix = re.split(r"[_\-]+", name, maxsplit=1)[0].strip()
    if not 2 <= len(prefix) <= 80 or not any(c.isalpha() for c in prefix):
        return None
    return prefix.upper() if 3 <= len(prefix) <= 5 else prefix[:1].upper() + prefix[1:]


def assign_automatic_topic(store: Store, note_id: str, now: datetime) -> str | None:
    note = store.get_note(note_id)
    if note is None or note.deleted_at is not None or note.topic_id or note.metadata_version != 0:
        return None
    topics = store.list_topics()
    name = suggested_topic(note.title, topics)
    if not name:
        return None
    topic = next((t for t in topics if fold(t.name) == fold(name)), None)
    if topic is None:
        start = int(hashlib.sha256(fold(name).encode()).hexdigest()[:8], 16) % (len(COLORS) - 1)
        palette = COLORS[:-1]
        color = next(
            (
                palette[(start + i) % len(palette)]
                for i in range(len(palette))
                if palette[(start + i) % len(palette)] not in {t.color_key for t in topics}
            ),
            palette[start],
        )
        try:
            topic = store.save_topic(None, name, color, None)
        except Conflict as exc:
            if exc.code != "TOPIC_EXISTS":
                raise
            topic = next((t for t in store.list_topics() if fold(t.name) == fold(name)), None)
            if topic is None:
                raise
    # A manual move/deletion racing this assignment wins via the existing metadata CAS.
    store.set_note_topic(note_id, topic.topic_id, note.metadata_version, now)
    return topic.topic_id
