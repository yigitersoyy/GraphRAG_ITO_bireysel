from tests.support.document_files import docx_bytes


def test_new_file_families_reuse_existing_topic_and_leave_extraction_unchanged(stack):
    c = stack.client
    existing = c.post("/api/v1/topics", json={"name": "kvkk", "color_key": "purple"}).json()
    notes = []
    for i, title in enumerate(
        ["01_kvkk_6698_kanun_bolum_01", "02_kvkk_veri_imha_bolum_01", "03_bddk_5411_kanun_bolum_01"]
    ):
        r = stack.create(title, "Ada works on Project Atlas. Project Atlas uses Neo4j.", str(i))
        assert r.status_code == 202, r.text
        notes.append(c.get("/api/v1/notes/" + r.json()["note_id"]).json())
    assert notes[0]["topic_id"] == notes[1]["topic_id"] == existing["topic_id"]
    assert notes[2]["topic_id"] != existing["topic_id"]
    topics = c.get("/api/v1/topics").json()["items"]
    assert len(topics) == 2 and {t["name"] for t in topics} == {"kvkk", "BDDK"}
    assert all(n["metadata_version"] == 1 for n in notes)
    ids = [n["desired_revision_id"] for n in notes]
    stack.drain()
    for n, rid in zip(notes, ids, strict=True):
        current = c.get("/api/v1/notes/" + n["note_id"]).json()
        assert current["state"] == "ready" and current["desired_revision_id"] == rid


def test_manual_move_and_idempotent_replay_never_reapply_automatic_grouping(stack):
    c = stack.client
    first = stack.create("01_kvkk_kanun_bolum_01", "Note text.", "repeat").json()
    note = c.get("/api/v1/notes/" + first["note_id"]).json()
    other = c.post("/api/v1/topics", json={"name": "Başka konu", "color_key": "blue"}).json()
    moved = c.patch(
        "/api/v1/notes/" + note["note_id"] + "/metadata",
        json={"topic_id": other["topic_id"], "expected_version": note["metadata_version"]},
    )
    assert moved.status_code == 200
    replay = stack.create("01_kvkk_kanun_bolum_01", "Note text.", "repeat").json()
    assert replay["replayed"] and replay["note_id"] == note["note_id"]
    assert c.get("/api/v1/notes/" + note["note_id"]).json()["topic_id"] == other["topic_id"]
    stale = c.patch(
        "/api/v1/notes/" + note["note_id"] + "/metadata",
        json={"topic_id": None, "expected_version": note["metadata_version"]},
    )
    assert stale.status_code == 409


def test_explicit_manual_creation_skips_automatic_topic(stack):
    c = stack.client
    r = c.post(
        "/api/v1/notes",
        json={"title": "01_kvkk_bolum_01", "text": "Note text.", "auto_topic": False},
        headers={"Idempotency-Key": "manual"},
    )
    assert r.status_code == 202
    assert c.get("/api/v1/notes/" + r.json()["note_id"]).json()["topic_id"] is None
    assert c.get("/api/v1/topics").json()["items"] == []


def test_uploaded_document_uses_same_automatic_grouping(stack):
    c = stack.client
    r = c.post(
        "/api/v1/notes/upload",
        files={"file": ("01_kvkk_6698.docx", docx_bytes())},
        data={"title": "01_kvkk_6698_kanun_bolum_01"},
        headers={"Idempotency-Key": "file"},
    )
    assert r.status_code == 202, r.text
    note = c.get("/api/v1/notes/" + r.json()["note_id"]).json()
    topics = c.get("/api/v1/topics").json()["items"]
    assert note["topic_id"] == topics[0]["topic_id"] and topics[0]["name"] == "KVKK"
