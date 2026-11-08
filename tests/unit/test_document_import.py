import subprocess

import pytest
from fastapi.testclient import TestClient
from tests.support.document_files import docx_bytes, pdf_bytes, xls_bytes, xlsx_bytes

from notes_graphrag.api.app import create_app
from notes_graphrag.api.dependencies import build_context
from notes_graphrag.core.config import Settings
from notes_graphrag.core.errors import ValidationFailed
from notes_graphrag.ingestion.documents import import_document


@pytest.fixture
def stack():
    ctx = build_context(Settings(_env_file=None), demo=True, backend="memory")
    with TestClient(create_app(ctx)) as client:
        yield ctx, client


def send(client, name, raw, preview=False, key="document-import"):
    return client.post(
        "/api/v1/notes/upload" + ("/preview" if preview else ""),
        files={"file": (name, raw, "application/octet-stream")},
        data={} if preview else {"title": "Belge"},
        headers={} if preview else {"Idempotency-Key": key},
    )


@pytest.mark.parametrize(
    "name,raw",
    [
        ("note.PDF", pdf_bytes()),
        ("note.DOCX", docx_bytes()),
        ("note.XLSX", xlsx_bytes()),
        ("note.XLS", xls_bytes()),
    ],
)
def test_preview_upload_ingest_answer_and_exact_source(stack, name, raw):
    ctx, client = stack
    preview = send(client, name, raw, preview=True)
    assert preview.status_code == 200, preview.text
    assert client.get("/api/v1/workspace/notes").json()["total"] == 0
    created = send(client, name, raw)
    assert created.status_code == 202, created.text
    sub = created.json()
    assert send(client, name, raw).json()["replayed"]
    while ctx.worker.run_once():
        pass
    assert client.get("/api/v1/jobs/" + sub["job_id"]).json()["status"] == "SUCCEEDED"
    rev = client.get(f"/api/v1/notes/{sub['note_id']}/revisions/{sub['revision_id']}").json()
    assert rev["text"] == preview.json()["text"]
    answer = client.post(
        "/api/v1/questions", json={"question": "Which database does Ada's project use?"}
    ).json()
    assert answer["status"] == "answered", answer
    assert "Neo4j" in answer["answer"]
    for citation in answer["citations"]:
        assert rev["text"][citation["start_char"] : citation["end_char"]] == citation["quote"]
    assert client.delete("/api/v1/notes/" + sub["note_id"]).status_code == 204


def test_word_turkish_hyperlink_table_order_and_no_deleted_text():
    xml = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
    <w:p><w:r><w:t>Öykü, İzmir'de </w:t></w:r>
    <w:hyperlink><w:r><w:t>çalışıyor.</w:t></w:r></w:hyperlink></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Proje Çınar</w:t><w:tab/>
    <w:t>Neo4j</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:p><w:del><w:r><w:delText>Eski gizli cümle</w:delText></w:r></w:del>
    <w:r><w:t>Sonuç</w:t><w:br/><w:t>Hazır</w:t></w:r></w:p>
    </w:body></w:document>"""
    text = import_document("tr.docx", docx_bytes(xml=xml), Settings(_env_file=None))
    assert text == "Öykü, İzmir'de çalışıyor.\n\nProje Çınar\tNeo4j\n\nSonuç\nHazır"


@pytest.mark.parametrize(
    "name,raw,code,status",
    [
        ("broken.pdf", b"not a pdf", "INVALID_DOCUMENT", 422),
        ("broken.docx", b"not a zip", "INVALID_DOCUMENT", 422),
        ("protected.pdf", pdf_bytes(encrypted=True), "ENCRYPTED_DOCUMENT", 422),
        ("scan.pdf", pdf_bytes(text="", image_only=True), "OCR_REQUIRED", 422),
        ("empty.pdf", pdf_bytes(text=""), "OCR_REQUIRED", 422),
        ("empty.docx", docx_bytes(text=""), "NO_DOCUMENT_TEXT", 422),
        ("old.doc", b"old", "UNSUPPORTED_MEDIA_TYPE", 415),
        ("huge.pdf", b"a" * (10 * 1024 * 1024 + 1), "PAYLOAD_TOO_LARGE", 413),
        ("long.pdf", pdf_bytes(pages=201), "PAYLOAD_TOO_LARGE", 413),
        ("long.docx", docx_bytes(text="a" * 100001), "PAYLOAD_TOO_LARGE", 413),
        ("bomb.docx", docx_bytes(text="a" * (20 * 1024 * 1024)), "PAYLOAD_TOO_LARGE", 413),
        (
            "unsafe.docx",
            docx_bytes(
                xml='<!DOCTYPE x [<!ENTITY x "secret">]>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&x;</w:t>'
                "</w:r></w:p></w:body></w:document>"
            ),
            "INVALID_DOCUMENT",
            422,
        ),
    ],
)
def test_bad_documents_rejected_without_creating_notes(stack, name, raw, code, status):
    _, client = stack
    for preview in (True, False):
        response = send(client, name, raw, preview=preview)
        assert response.status_code == status, response.text
        assert response.json()["error"]["code"] == code
    assert client.get("/api/v1/workspace/notes").json()["total"] == 0


def test_parser_timeout_has_actionable_error(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("parser", 20)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(ValidationFailed) as exc:
        import_document("t.pdf", b"%PDF-", Settings(_env_file=None))
    assert exc.value.code == "DOCUMENT_TIMEOUT"
