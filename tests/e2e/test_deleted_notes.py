from datetime import UTC, datetime, timedelta


def test_deleted_notes_are_only_in_deleted_list_not_unsorted_search_or_map(stack):
    client = stack.client
    deleted = stack.create(
        "TrashOnly document", "TrashOnly works on Project TrashOnly.", "trash"
    ).json()
    live = stack.create("Unassigned live document", "A separate live document.", "live").json()
    stack.drain()
    assert client.delete("/api/v1/notes/" + deleted["note_id"]).status_code == 204
    result = client.get("/api/v1/workspace/deleted-notes").json()
    assert result["total"] == 1
    item = result["items"][0]
    assert item["note_id"] == deleted["note_id"]
    assert item["title"] == "TrashOnly document" and item["deleted_at"]
    assert not item["content_purged"]
    assert set(item) == {"note_id", "title", "deleted_at", "content_purged"}
    assert client.get("/api/v1/notes/" + deleted["note_id"]).status_code == 404
    for path in ["/api/v1/search?q=TrashOnly", "/api/v1/workspace/notes?q=TrashOnly"]:
        assert client.get(path).json()["items"] == []
    unsorted = client.get("/api/v1/workspace/notes?topic_id=unsorted").json()
    assert [n["note_id"] for n in unsorted["items"]] == [live["note_id"]]
    assert deleted["note_id"] not in {
        n["note_id"] for n in client.get("/api/v1/workspace/map").json()["nodes"]
    }


def test_deleted_pagination_survives_equal_timestamps_and_content_retention(stack):
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    ids = [stack.create(f"Trash {i}", "Text.", f"trash-{i}").json()["note_id"] for i in range(3)]
    for id in ids:
        stack.ctx.store.delete_note(id, stamp)
    first = stack.client.get("/api/v1/workspace/deleted-notes?limit=2").json()
    assert first["total"] == 3 and len(first["items"]) == 2 and first["next_cursor"]
    second = stack.client.get(
        "/api/v1/workspace/deleted-notes", params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert [n["note_id"] for n in first["items"] + second["items"]] == sorted(ids, reverse=True)
    assert not second["next_cursor"]
    assert (
        stack.client.get(
            "/api/v1/workspace/notes", params={"cursor": first["next_cursor"]}
        ).status_code
        == 400
    )
    stack.ctx.store.purge(stamp + timedelta(days=2), 1, 30)
    purged = stack.client.get("/api/v1/workspace/deleted-notes").json()
    assert purged["total"] == 3
    assert all(n["content_purged"] and not n["title"] for n in purged["items"])
