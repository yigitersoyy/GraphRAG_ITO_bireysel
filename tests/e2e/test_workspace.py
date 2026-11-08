"""The workspace uses both stores and never turns unpublished text into graph support."""

import pytest

TEXT = "Ada works on Project Atlas. Project Atlas uses Neo4j."


def topic(stack, name="Projeler", color="purple"):
    r = stack.client.post("/api/v1/topics", json={"name": name, "color_key": color})
    assert r.status_code == 201, r.text
    return r.json()


def test_topic_assignment_is_fenced_and_independent_of_ingestion(stack):
    t = topic(stack)
    n = stack.create("Atlas", TEXT, "a").json()
    client = stack.client
    result = client.patch(
        f"/api/v1/notes/{n['note_id']}/metadata",
        json={"topic_id": t["topic_id"], "expected_version": 0},
    )
    assert result.status_code == 200, result.text
    assert result.json()["metadata_version"] == 1
    assert (
        client.get(f"/api/v1/notes/{n['note_id']}").json()["desired_revision_id"]
        == n["revision_id"]
    )
    assert (
        client.patch(
            f"/api/v1/notes/{n['note_id']}/metadata", json={"topic_id": None, "expected_version": 0}
        ).status_code
        == 409
    )
    counts = client.get("/api/v1/topics").json()["items"]
    assert counts[0]["note_count"] == 1
    renamed = client.patch(
        "/api/v1/topics/" + t["topic_id"],
        json={"name": "Araştırma", "color_key": "orange", "expected_version": 1},
    )
    assert renamed.status_code == 200
    assert (
        client.patch(
            "/api/v1/topics/" + t["topic_id"],
            json={"name": "Stale", "color_key": "blue", "expected_version": 1},
        ).status_code
        == 409
    )
    assert (
        client.delete("/api/v1/topics/" + t["topic_id"] + "?expected_version=1").status_code == 409
    )
    assert (
        client.delete("/api/v1/topics/" + t["topic_id"] + "?expected_version=2").status_code == 200
    )
    final = client.get(f"/api/v1/notes/{n['note_id']}").json()
    assert final["topic_id"] is None and final["metadata_version"] == 2


def test_catalog_filters_before_pagination_and_scopes_the_cursor(stack):
    t = topic(stack)
    ids = []
    for i in range(51):
        ids.append(stack.create(f"Not {i:03d}", TEXT, f"n{i}").json()["note_id"])
    stack.client.patch(
        f"/api/v1/notes/{ids[-1]}/metadata", json={"topic_id": t["topic_id"], "expected_version": 0}
    )
    first = stack.client.get("/api/v1/workspace/notes").json()
    assert len(first["items"]) == 50 and first["total"] == 51 and first["next_cursor"]
    second = stack.client.get(
        "/api/v1/workspace/notes", params={"cursor": first["next_cursor"]}
    ).json()
    assert len(second["items"]) == 1
    assert not ({n["note_id"] for n in first["items"]} & {n["note_id"] for n in second["items"]})
    filtered = stack.client.get(
        "/api/v1/workspace/notes", params={"topic_id": t["topic_id"]}
    ).json()
    assert filtered["total"] == 1 and filtered["items"][0]["note_id"] == ids[-1]
    assert (
        stack.client.get(
            "/api/v1/workspace/notes", params={"q": "Not 050", "cursor": first["next_cursor"]}
        ).status_code
        == 400
    )
    assert stack.client.get("/api/v1/workspace/notes", params={"q": "Not 050"}).json()["total"] == 1
    stack.client.delete("/api/v1/notes/" + ids[-1])
    assert (
        stack.client.get("/api/v1/workspace/notes", params={"topic_id": t["topic_id"]}).json()[
            "total"
        ]
        == 0
    )


def test_map_and_search_only_use_active_ready_support(stack):
    a = stack.create("İş Planı", TEXT, "a").json()
    b = stack.create("Ekip", "Grace works on Project Atlas.", "b").json()
    pending = stack.client.get("/api/v1/workspace/map").json()
    assert len(pending["nodes"]) == 2 and pending["edges"] == []
    assert stack.client.get("/api/v1/search", params={"q": "Neo4j"}).json()["items"] == []
    stack.drain()
    m = stack.client.get("/api/v1/workspace/map").json()
    assert len(m["edges"]) == 1 and m["edges"][0]["kind"] == "shared_entity"
    assert "Project Atlas" in [e["name"] for e in m["edges"][0]["entities"]]
    assert m["similarity_available"] is False
    assert (
        stack.client.get("/api/v1/workspace/notes", params={"q": "iş planı"}).json()["total"] == 1
    )
    assert (
        stack.client.get("/api/v1/search", params={"q": "neo4j", "kind": "note"}).json()["items"][
            0
        ]["id"]
        == a["note_id"]
    )
    # Replacement is pending: old active support remains, new text is not searchable.
    stack.client.put(
        "/api/v1/notes/" + a["note_id"],
        headers={"Idempotency-Key": "replace"},
        json={"title": "İş Planı", "text": "Ada works on Project Borealis."},
    )
    assert stack.client.get("/api/v1/search", params={"q": "Borealis"}).json()["items"] == []
    stack.drain()
    assert stack.client.get("/api/v1/workspace/map").json()["edges"] == []
    assert stack.client.get("/api/v1/search", params={"q": "Neo4j"}).json()["items"] == []
    stack.client.delete("/api/v1/notes/" + b["note_id"])
    assert len(stack.client.get("/api/v1/workspace/map").json()["nodes"]) == 1


@pytest.mark.parametrize(
    "body", [{"name": "   "}, {"name": "bad\x00name"}, {"name": "x", "color_key": "fake"}]
)
def test_topics_validate_names_and_color_keys(stack, body):
    assert stack.client.post("/api/v1/topics", json=body).status_code == 422


def test_duplicate_topic_name_and_unknown_topic_are_rejected(stack):
    topic(stack, "İş")
    assert stack.client.post("/api/v1/topics", json={"name": "iş"}).status_code == 409
    n = stack.create("Test", TEXT, "unknown").json()
    assert (
        stack.client.patch(
            f"/api/v1/notes/{n['note_id']}/metadata",
            json={"topic_id": "missing", "expected_version": 0},
        ).status_code
        == 404
    )


def test_catalog_pages_cover_101_notes_without_gaps(stack):
    client = stack.client
    assert client.get("/api/v1/workspace/notes").json()["total"] == 0
    expected = set()
    for i in range(101):
        expected.add(stack.create(f"Page {i}", TEXT, f"page-{i}").json()["note_id"])
        if i in (0, 49, 50):
            result = client.get("/api/v1/workspace/notes").json()
            assert result["total"] == i + 1
            assert bool(result["next_cursor"]) == (i >= 50)
    seen = []
    cursor = None
    while True:
        result = client.get(
            "/api/v1/workspace/notes", params={"cursor": cursor} if cursor else {}
        ).json()
        seen.extend(n["note_id"] for n in result["items"])
        cursor = result["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 101 and set(seen) == expected
