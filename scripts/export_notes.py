"""Read-only snapshot of active/pending revisions exposed by a running API."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api-base", default="http://127.0.0.1:8000")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    notes = []
    with httpx.Client(base_url=args.api_base, timeout=20) as client:
        cursor = None
        while True:
            r = client.get("/api/v1/notes", params={"limit": 100, "cursor": cursor})
            r.raise_for_status()
            page = r.json()
            for note in page["items"]:
                revisions = {}
                for key in ("active_revision_id", "pending_revision_id"):
                    rid = note.get(key)
                    if rid:
                        rev = client.get(f"/api/v1/notes/{note['note_id']}/revisions/{rid}")
                        rev.raise_for_status()
                        revisions[rid] = rev.json()
                notes.append({"note": note, "revisions": revisions})
            cursor = page["next_cursor"]
            if not cursor:
                break
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves earlier snapshots.
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(
            {
                "exported_at": datetime.now(UTC).isoformat(),
                "notes": notes,
                "scope": "active/pending revisions only; not complete revision history",
            },
            output,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Exported {len(notes)} notes. Contains private note text; keep outside git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
