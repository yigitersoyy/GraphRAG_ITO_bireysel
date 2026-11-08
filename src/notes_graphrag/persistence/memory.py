"""In-memory Store with the same semantics as the Neo4j store.

Used for demos and fast tests. It is not durable: all state is lost when the process exits.
Every read returns an immutable snapshot.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from notes_graphrag.core.errors import (
    Conflict,
    IdempotencyKeyReused,
    NoteDeleted,
    NotFound,
    StaleLease,
    ValidationFailed,
)
from notes_graphrag.domain.state_machines import (
    JobStatus,
    RevisionStatus,
    Stage,
    check_job,
    check_revision,
)
from notes_graphrag.ingestion.entity_resolution import KnownEntity, new_entity_id, resolve
from notes_graphrag.ingestion.extraction import ValidatedClaim
from notes_graphrag.persistence.base import REQUIRED_INDEXES
from notes_graphrag.persistence.models import (
    GATE_BUSY,
    GATE_IDLE,
    GATE_RECOVERING,
    PROBE_OWNER,
    GateStatus,
    Job,
    Note,
    ProbeRecord,
    Revision,
    StagedChunk,
    Submission,
)
from notes_graphrag.persistence.workspace import CatalogEntry, NoteLink, Topic, fold


@dataclass(frozen=True)
class IdemRec:
    payload_hash: str
    note_id: str
    revision_id: str
    job_id: str
    created_at: datetime


@dataclass
class MemClaim:
    claim_id: str
    revision_id: str
    chunk_id: str
    subject_id: str
    object_id: str
    claim: ValidatedClaim


@dataclass
class MemGate:
    state: str = GATE_IDLE
    owner: str | None = None
    token: str | None = None
    expires: datetime | None = None


@dataclass
class MemoryStore:
    workspace_id: str = "default"
    notes: dict[str, Note] = field(default_factory=dict)
    revisions: dict[str, Revision] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)
    # request_key -> (payload_hash, note_id, revision_id, job_id)
    idem: dict[str, IdemRec] = field(default_factory=dict)
    staged: dict[str, dict[str, StagedChunk]] = field(default_factory=dict)
    entities: dict[str, KnownEntity] = field(default_factory=dict)
    claims: dict[str, MemClaim] = field(default_factory=dict)
    gates: dict[str, MemGate] = field(default_factory=dict)
    graph_ver: int = 0
    probes: list[ProbeRecord] = field(default_factory=list)
    heartbeat_at: datetime | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    topics: dict[str, Topic] = field(default_factory=dict)
    metadata_ver: int = 0

    # ---- notes and submission -------------------------------------------------------------
    def submit(
        self,
        *,
        rkey: str,
        payload_hash: str,
        note_id: str | None,
        title: str,
        text: str,
        fingerprint: str,
        now: datetime,
    ) -> Submission:
        chash = hashlib.sha256(text.encode()).hexdigest()
        with self.lock:
            hit = self.idem.get(rkey)
            if hit is not None:
                if hit.payload_hash != payload_hash:
                    raise IdempotencyKeyReused("idempotency key reused with different payload")
                note = self.notes[hit.note_id]
                if note.deleted_at is not None:
                    raise NoteDeleted("note was deleted")
                return Submission(
                    note, self.revisions[hit.revision_id], self.jobs[hit.job_id], replayed=True
                )

            if note_id is None:
                note = Note(str(uuid.uuid4()), title, now, desired_revision_id="")
            else:
                note = self._live_note(note_id)
                cur = self.revisions[note.desired_revision_id]
                if (
                    cur.content_hash == chash
                    and cur.fingerprint == fingerprint
                    and cur.title == title
                    and cur.status != RevisionStatus.FAILED
                ):
                    job = self.job_for_revision(cur.revision_id)
                    assert job is not None
                    self.idem[rkey] = IdemRec(
                        payload_hash, note.note_id, cur.revision_id, job.job_id, now
                    )
                    return Submission(note, cur, job, replayed=True)
                self._supersede_queued(note.desired_revision_id)

            rev = Revision(
                str(uuid.uuid4()),
                note.note_id,
                title,
                text,
                chash,
                fingerprint,
                RevisionStatus.PENDING,
            )
            job = Job(
                str(uuid.uuid4()),
                note.note_id,
                rev.revision_id,
                payload_hash,
                JobStatus.QUEUED,
                available_at=now,
            )
            self.revisions[rev.revision_id] = rev
            self.jobs[job.job_id] = job
            note = replace(note, title=title, desired_revision_id=rev.revision_id, updated_at=now)
            self.notes[note.note_id] = note
            self.idem[rkey] = IdemRec(payload_hash, note.note_id, rev.revision_id, job.job_id, now)
            return Submission(note, rev, job, replayed=False)

    def _supersede_queued(self, revision_id: str) -> None:
        if not revision_id:
            return
        rev = self.revisions[revision_id]
        if rev.status not in (RevisionStatus.PENDING, RevisionStatus.PROCESSING):
            return
        job = self.job_for_revision(revision_id)
        if job is not None and job.status == JobStatus.QUEUED:
            check_job(job.status, JobStatus.SUPERSEDED)
            check_revision(rev.status, RevisionStatus.SUPERSEDED)
            self.jobs[job.job_id] = replace(job, status=JobStatus.SUPERSEDED)
            self.revisions[revision_id] = replace(rev, status=RevisionStatus.SUPERSEDED)

    def _live_note(self, note_id: str) -> Note:
        # Deleted notes look exactly like missing ones to new requests (architecture 7.3).
        note = self.notes.get(note_id)
        if note is None or note.deleted_at is not None:
            raise NotFound("note not found")
        return note

    def get_note(self, note_id: str) -> Note | None:
        with self.lock:
            return self.notes.get(note_id)

    def get_revision(self, revision_id: str) -> Revision | None:
        with self.lock:
            return self.revisions.get(revision_id)

    def list_notes(self, after: tuple[datetime, str] | None, limit: int) -> tuple[list[Note], bool]:
        with self.lock:
            rows = sorted(
                (n for n in self.notes.values() if n.deleted_at is None),
                key=lambda n: (n.created_at, n.note_id),
            )
            if after is not None:
                rows = [n for n in rows if (n.created_at, n.note_id) > after]
            return rows[:limit], len(rows) > limit

    def delete_note(self, note_id: str, now: datetime) -> None:
        with self.lock:
            note = self._live_note(note_id)
            self.notes[note_id] = replace(note, deleted_at=now, active_revision_id=None)
            self.graph_ver += 1
            for j in list(self.jobs.values()):
                if j.note_id == note_id and j.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                    self.jobs[j.job_id] = replace(
                        j, status=JobStatus.CANCELLED, lease_token=None, lease_expires_at=None
                    )
            for r in list(self.revisions.values()):
                if r.note_id == note_id and r.status not in (
                    RevisionStatus.CANCELLED,
                    RevisionStatus.SUPERSEDED,
                ):
                    self.revisions[r.revision_id] = replace(r, status=RevisionStatus.CANCELLED)

    # ---- jobs -------------------------------------------------------------------------------
    def get_job(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def job_for_revision(self, revision_id: str) -> Job | None:
        with self.lock:
            return next((j for j in self.jobs.values() if j.revision_id == revision_id), None)

    def retry_job(self, job_id: str, now: datetime) -> Job:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise NotFound("job not found")
            note = self.notes[job.note_id]
            if note.deleted_at is not None:
                raise NotFound("job not found")
            if job.status != JobStatus.FAILED:
                raise Conflict("only failed jobs can be retried", code="JOB_NOT_RETRYABLE")
            if note.desired_revision_id != job.revision_id:
                raise Conflict("job was superseded by a newer revision", code="JOB_SUPERSEDED")
            check_job(job.status, JobStatus.QUEUED)
            rev = self.revisions[job.revision_id]
            check_revision(rev.status, RevisionStatus.PENDING)
            self.jobs[job_id] = replace(
                job,
                status=JobStatus.QUEUED,
                attempt=0,
                error_code=None,
                available_at=now,
                lease_token=None,
                lease_expires_at=None,
            )
            self.revisions[rev.revision_id] = replace(rev, status=RevisionStatus.PENDING)
            return self.jobs[job_id]

    def acquire(self, now: datetime, lease_seconds: int) -> Job | None:
        with self.lock:
            candidates = [
                j
                for j in self.jobs.values()
                if (j.status == JobStatus.QUEUED and (j.available_at or now) <= now)
                or (
                    j.status == JobStatus.RUNNING
                    and j.lease_expires_at is not None
                    and j.lease_expires_at <= now
                )
            ]
            if not candidates:
                return None
            j = min(candidates, key=lambda x: (x.available_at or now, x.job_id))
            token = str(uuid.uuid4())
            new = replace(
                j,
                status=JobStatus.RUNNING,
                attempt=j.attempt + 1,
                lease_token=token,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
            )
            self.jobs[j.job_id] = new
            rev = self.revisions[j.revision_id]
            if rev.status == RevisionStatus.PENDING:
                self.revisions[rev.revision_id] = replace(rev, status=RevisionStatus.PROCESSING)
            return new

    def _fenced(self, job_id: str, token: str, now: datetime) -> Job:
        job = self.jobs[job_id]
        if (
            job.status != JobStatus.RUNNING
            or job.lease_token != token
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise StaleLease("lease lost")
        return job

    def heartbeat_job(self, job_id: str, token: str, now: datetime, lease_seconds: int) -> bool:
        with self.lock:
            try:
                job = self._fenced(job_id, token, now)
            except (KeyError, StaleLease):
                return False
            self.jobs[job_id] = replace(
                job, lease_expires_at=now + timedelta(seconds=lease_seconds)
            )
            return True

    def record_progress(
        self, job_id: str, token: str, now: datetime, stage: Stage, chunks_total: int
    ) -> None:
        with self.lock:
            job = self._fenced(job_id, token, now)
            self.jobs[job_id] = replace(job, stage=stage, chunks_total=chunks_total)

    def requeue(
        self, job_id: str, token: str, now: datetime, available_at: datetime, code: str
    ) -> bool:
        with self.lock:
            job = self.jobs[job_id]
            if job.status != JobStatus.RUNNING or job.lease_token != token:
                return False
            check_job(job.status, JobStatus.QUEUED)
            self.jobs[job_id] = replace(
                job,
                status=JobStatus.QUEUED,
                lease_token=None,
                lease_expires_at=None,
                available_at=available_at,
                error_code=code,
            )
            return True

    def fail(self, job_id: str, token: str, now: datetime, code: str) -> bool:
        with self.lock:
            job = self.jobs[job_id]
            if job.status != JobStatus.RUNNING or job.lease_token != token:
                return False
            check_job(job.status, JobStatus.FAILED)
            self.jobs[job_id] = replace(
                job,
                status=JobStatus.FAILED,
                error_code=code,
                lease_token=None,
                lease_expires_at=None,
            )
            rev = self.revisions[job.revision_id]
            if rev.status == RevisionStatus.PROCESSING:
                check_revision(rev.status, RevisionStatus.FAILED)
                self.revisions[rev.revision_id] = replace(rev, status=RevisionStatus.FAILED)
            return True

    # ---- staging and publication ------------------------------------------------------------
    def stage_chunk(self, job_id: str, token: str, now: datetime, staged: StagedChunk) -> None:
        with self.lock:
            job = self._fenced(job_id, token, now)
            bucket = self.staged.setdefault(job.revision_id, {})
            bucket[staged.chunk.chunk_id] = staged
            self.jobs[job_id] = replace(job, chunks_done=len(bucket))

    def staged_chunk_ids(self, revision_id: str) -> set[str]:
        with self.lock:
            return set(self.staged.get(revision_id, {}))

    def publish(
        self,
        job_id: str,
        token: str,
        now: datetime,
        expected_chunk_ids: list[str],
        embedding_profile: str,
        staged_profile: str,
    ) -> bool:
        with self.lock:
            job = self._fenced(job_id, token, now)
            rev = self.revisions[job.revision_id]
            note = self.notes[job.note_id]
            if note.deleted_at is not None:
                self.jobs[job_id] = replace(job, status=JobStatus.CANCELLED, lease_token=None)
                return False
            if note.desired_revision_id != rev.revision_id:
                self.jobs[job_id] = replace(job, status=JobStatus.SUPERSEDED, lease_token=None)
                if rev.status in (RevisionStatus.PENDING, RevisionStatus.PROCESSING):
                    self.revisions[rev.revision_id] = replace(rev, status=RevisionStatus.SUPERSEDED)
                return False

            staged = self.staged.get(rev.revision_id, {})
            if set(staged) != set(expected_chunk_ids):
                raise ValidationFailed("incomplete staging", code="INCOMPLETE_STAGING")
            if embedding_profile != staged_profile:
                raise ValidationFailed("embedding profile mismatch", code="PROFILE_MISMATCH")

            for sc in sorted(staged.values(), key=lambda s: s.chunk.ordinal):
                for vc in sc.claims:
                    ids = []
                    for ent in (vc.subject, vc.object):
                        ctx = {vc.subject.name, vc.object.name} - {ent.name}
                        found = resolve(ent.name, ent.kind, ctx, list(self.entities.values()))
                        if found is None:
                            found = new_entity_id()
                            self.entities[found] = KnownEntity(found, ent.kind, ent.name)
                        self.entities[found].context |= ctx
                        ids.append(found)
                    self.claims[vc.claim_id] = MemClaim(
                        vc.claim_id, rev.revision_id, sc.chunk.chunk_id, ids[0], ids[1], vc
                    )

            prev_id = note.active_revision_id
            if prev_id and prev_id != rev.revision_id:
                prev = self.revisions[prev_id]
                check_revision(prev.status, RevisionStatus.SUPERSEDED)
                self.revisions[prev_id] = replace(prev, status=RevisionStatus.SUPERSEDED)
            check_revision(rev.status, RevisionStatus.READY)
            self.revisions[rev.revision_id] = replace(rev, status=RevisionStatus.READY)
            self.notes[note.note_id] = replace(note, active_revision_id=rev.revision_id)
            self.jobs[job_id] = replace(
                job,
                status=JobStatus.SUCCEEDED,
                stage=Stage.PUBLISHING,
                lease_token=None,
                lease_expires_at=None,
                chunks_done=len(staged),
            )
            self.graph_ver += 1
            return True

    # ---- workspace state --------------------------------------------------------------------
    def heartbeat(self, now: datetime) -> None:
        with self.lock:
            self.heartbeat_at = now

    def last_heartbeat(self) -> datetime | None:
        with self.lock:
            return self.heartbeat_at

    def graph_version(self) -> int:
        with self.lock:
            return self.graph_ver

    # ---- capability probes ------------------------------------------------------------------
    def record_probe(
        self, fingerprint: str, passed: bool, results: list[dict[str, Any]], now: datetime
    ) -> None:
        with self.lock:
            rows = tuple({str(k): str(v) for k, v in r.items()} for r in results)
            self.probes.append(ProbeRecord(fingerprint, passed, now, rows))

    def latest_probe(self) -> ProbeRecord | None:
        with self.lock:
            return self.probes[-1] if self.probes else None

    # ---- shared inference slot ----------------------------------------------------------------
    def ensure_gate(self, endpoint_id: str) -> None:
        with self.lock:
            self.gates.setdefault(endpoint_id, MemGate())

    def gate_status(self, endpoint_id: str) -> GateStatus:
        with self.lock:
            g = self.gates.setdefault(endpoint_id, MemGate())
            return GateStatus(g.state, g.owner, g.expires)

    def gate_try_acquire(
        self, endpoint_id: str, owner: str, token: str, now: datetime, lease_seconds: int
    ) -> bool:
        with self.lock:
            g = self.gates.setdefault(endpoint_id, MemGate())
            if g.state == GATE_BUSY and g.expires is not None and g.expires <= now:
                # The holder vanished or timed out: the server may still be computing.
                g.state, g.owner, g.token, g.expires = GATE_RECOVERING, None, None, None
                return False
            allowed = g.state == GATE_RECOVERING if owner == PROBE_OWNER else g.state == GATE_IDLE
            if not allowed:
                return False
            g.state = GATE_BUSY
            g.owner = owner
            g.token = token
            g.expires = now + timedelta(seconds=lease_seconds)
            return True

    def gate_heartbeat(
        self, endpoint_id: str, token: str, now: datetime, lease_seconds: int
    ) -> None:
        with self.lock:
            g = self.gates.setdefault(endpoint_id, MemGate())
            if g.state == GATE_BUSY and g.token == token:
                g.expires = now + timedelta(seconds=lease_seconds)

    def gate_release(self, endpoint_id: str, token: str, target: str) -> None:
        if target not in (GATE_IDLE, GATE_RECOVERING):
            raise ValueError("invalid gate target")
        with self.lock:
            g = self.gates.setdefault(endpoint_id, MemGate())
            if g.state == GATE_BUSY and g.token == token:
                g.state, g.owner, g.token, g.expires = target, None, None, None

    # ---- retention ---------------------------------------------------------------------------
    def purge(
        self,
        now: datetime,
        content_retention_days: float,
        idempotency_retention_days: float,
    ) -> dict[str, int]:
        """Remove source content of notes deleted before the content cutoff, orphan entities,
        and idempotency records older than their retention. Note tombstones remain, so a delayed
        replay of a deleted note's request still answers NOTE_DELETED (architecture 7.2, 7.3)."""
        content_cutoff = now - timedelta(days=content_retention_days)
        idem_cutoff = now - timedelta(days=idempotency_retention_days)
        counts = {"revisions": 0, "claims": 0, "entities": 0, "idempotency": 0}
        with self.lock:
            for note in list(self.notes.values()):
                if note.deleted_at is None or note.deleted_at > content_cutoff:
                    continue
                rids = {r.revision_id for r in self.revisions.values() if r.note_id == note.note_id}
                if not rids:
                    continue
                for rid in rids:
                    self.revisions.pop(rid, None)
                    self.staged.pop(rid, None)
                    counts["revisions"] += 1
                for cid in [k for k, mc in self.claims.items() if mc.revision_id in rids]:
                    del self.claims[cid]
                    counts["claims"] += 1
                for jid in [j.job_id for j in self.jobs.values() if j.note_id == note.note_id]:
                    del self.jobs[jid]
                self.notes[note.note_id] = replace(
                    note, title="", desired_revision_id="", active_revision_id=None
                )
            used = {mc.subject_id for mc in self.claims.values()}
            used |= {mc.object_id for mc in self.claims.values()}
            for eid in [e for e in self.entities if e not in used]:
                del self.entities[eid]
                counts["entities"] += 1
            for rkey in [k for k, rec in self.idem.items() if rec.created_at < idem_cutoff]:
                del self.idem[rkey]
                counts["idempotency"] += 1
        return counts

    # ---- workspace --------------------------------------------------------------------------
    def metadata_version(self) -> int:
        with self.lock:
            return self.metadata_ver

    def list_topics(self) -> list[Topic]:
        with self.lock:
            return sorted(
                [
                    replace(
                        t,
                        note_count=sum(
                            n.topic_id == t.topic_id and n.deleted_at is None
                            for n in self.notes.values()
                        ),
                    )
                    for t in self.topics.values()
                ],
                key=lambda t: (t.name, t.topic_id),
            )

    def save_topic(
        self, topic_id: str | None, name: str, color_key: str, expected_version: int | None
    ) -> Topic:
        with self.lock:
            old = self.topics.get(topic_id or "")
            if topic_id and old is None:
                raise NotFound("topic not found")
            if old and old.version != expected_version:
                raise Conflict("topic changed; reload before saving", code="METADATA_CHANGED")
            if any(
                fold(t.name) == fold(name) and t.topic_id != topic_id for t in self.topics.values()
            ):
                raise Conflict("topic name already exists", code="TOPIC_EXISTS")
            topic = Topic(
                topic_id or str(uuid.uuid4()), name, color_key, old.version + 1 if old else 1
            )
            self.topics[topic.topic_id] = topic
            self.metadata_ver += 1
            return topic

    def delete_topic(self, topic_id: str, expected_version: int) -> None:
        with self.lock:
            topic = self.topics.get(topic_id)
            if topic is None:
                raise NotFound("topic not found")
            if topic.version != expected_version:
                raise Conflict("topic changed; reload before deleting", code="METADATA_CHANGED")
            for nid, n in self.notes.items():
                if n.topic_id == topic_id and n.deleted_at is None:
                    self.notes[nid] = replace(
                        n, topic_id=None, metadata_version=n.metadata_version + 1
                    )
            del self.topics[topic_id]
            self.metadata_ver += 1

    def set_note_topic(
        self, note_id: str, topic_id: str | None, expected_version: int, now: datetime
    ) -> Note:
        with self.lock:
            n = self._live_note(note_id)
            if n.metadata_version != expected_version:
                raise Conflict(
                    "note metadata changed; reload before saving", code="METADATA_CHANGED"
                )
            if topic_id and topic_id not in self.topics:
                raise NotFound("topic not found")
            n = replace(
                n, topic_id=topic_id, metadata_version=n.metadata_version + 1, updated_at=now
            )
            self.notes[note_id] = n
            self.metadata_ver += 1
            return n

    def catalog(
        self, q: str, topic_id: str | None, after: tuple[datetime, str] | None, limit: int
    ) -> tuple[list[CatalogEntry], bool, int]:
        with self.lock:
            entries = []
            for n in self.notes.values():
                if n.deleted_at is not None:
                    continue
                if topic_id is not None and (n.topic_id or "unsorted") != topic_id:
                    continue
                active = self.revisions.get(n.active_revision_id or "")
                text = active.text if active and active.status == RevisionStatus.READY else ""
                if q and fold(q) not in fold(n.title + "\n" + text):
                    continue
                desired = self.revisions[n.desired_revision_id]
                entries.append(
                    CatalogEntry(
                        n, text, desired.status.value, self.job_for_revision(n.desired_revision_id)
                    )
                )
            entries.sort(key=lambda e: (e.note.created_at, e.note.note_id))
            total = len(entries)
            if after:
                entries = [e for e in entries if (e.note.created_at, e.note.note_id) > after]
            return entries[:limit], len(entries) > limit, total

    def workspace_links(self, note_ids: list[str], limit: int) -> tuple[list[NoteLink], bool]:
        from collections import defaultdict
        from itertools import combinations

        with self.lock:
            by_entity: dict[str, set[str]] = defaultdict(set)
            for c in self.claims.values():
                rev = self.revisions.get(c.revision_id)
                n = self.notes.get(rev.note_id) if rev else None
                if (
                    not n
                    or n.note_id not in note_ids
                    or n.deleted_at is not None
                    or n.active_revision_id != c.revision_id
                    or not rev
                    or rev.status != RevisionStatus.READY
                ):
                    continue
                by_entity[c.subject_id].add(n.note_id)
                by_entity[c.object_id].add(n.note_id)
            pairs: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
            for eid in sorted(by_entity):
                for a, b in combinations(sorted(by_entity[eid]), 2):
                    pairs[a, b].append((eid, self.entities[eid].canonical_name))
            rows = [NoteLink(a, b, tuple(entities)) for (a, b), entities in sorted(pairs.items())]
            return rows[:limit], len(rows) > limit

    # ---- operations -------------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        from notes_graphrag.persistence.migrations import latest_version

        return {
            "reachable": True,
            "schema_version": latest_version(),
            "indexes_online": None,
            "required_indexes": list(REQUIRED_INDEXES),
            "persistence": "memory (non-durable)",
        }

    def schema_version(self) -> int:
        from notes_graphrag.persistence.migrations import latest_version

        return latest_version()
