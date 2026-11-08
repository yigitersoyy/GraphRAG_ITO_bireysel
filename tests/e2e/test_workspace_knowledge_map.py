TEXT = "Ada works on Project Atlas. Project Atlas uses Neo4j."


def test_map_shows_only_published_active_relations_and_exact_sources(stack):
    c = stack.client
    sub = stack.create("Map source", TEXT, "source").json()
    before = c.get("/api/v1/workspace/map").json()
    assert before["entities"] == [] and before["relations"] == []
    stack.drain()
    graph = c.get("/api/v1/workspace/map").json()
    assert {"Ada", "Project Atlas", "Neo4j"} <= {n["label"] for n in graph["entities"]}
    assert len(graph["relations"]) == 2
    assert not graph["relations_limited"]
    for edge in graph["relations"]:
        source = edge["evidence"]
        assert source["note_id"] == sub["note_id"]
        assert TEXT[source["start_char"] : source["end_char"]] == source["quote"]
    assert len(stack.ctx.knowledge.claims_for_notes([sub["note_id"]], 1)) == 1
    assert stack.ctx.knowledge.claims_for_notes([], 151) == []
    replaced = c.put(
        "/api/v1/notes/" + sub["note_id"],
        headers={"Idempotency-Key": "replacement"},
        json={"title": "Map source", "text": TEXT.replace("Neo4j", "Postgres")},
    ).json()
    stack.drain()
    graph = c.get("/api/v1/workspace/map").json()
    assert "Neo4j" not in {n["label"] for n in graph["entities"]}
    assert "Postgres" in {n["label"] for n in graph["entities"]}
    assert {r["evidence"]["revision_id"] for r in graph["relations"]} == {replaced["revision_id"]}
    c.delete("/api/v1/notes/" + sub["note_id"])
    graph = c.get("/api/v1/workspace/map").json()
    assert graph["entities"] == [] and graph["relations"] == []
