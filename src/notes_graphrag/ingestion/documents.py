"""Bounded, local document-to-text conversion. Never executes embedded content.

Binary parsers run in a short-lived process; only normalized text enters the existing
revision/citation pipeline. No original file or document password is retained.
"""

from __future__ import annotations

import io
import json
import logging
import subprocess
import sys
import zipfile
from pathlib import PurePosixPath
from threading import BoundedSemaphore
from typing import Any

from notes_graphrag.core.config import Settings
from notes_graphrag.core.errors import PayloadTooLarge, ValidationFailed
from notes_graphrag.ingestion.validation import decode_text, normalize_text, validate_filename

MAX_PAGES = 200
MAX_EXPANDED_BYTES = 20 * 1024 * 1024
PARSER_TIMEOUT = 20
_slots = BoundedSemaphore(2)
_WORD_NAMESPACES = (
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
)


def import_document(filename: str, raw: bytes, settings: Settings) -> str:
    validate_filename(filename)
    suffix = PurePosixPath(filename.lower()).suffix
    limit = settings.max_note_bytes if suffix in (".txt", ".md") else settings.max_upload_bytes
    if len(raw) > limit:
        raise PayloadTooLarge("Dosya boyut sınırını aşıyor (metin: 1 MiB; PDF/Word/Excel: 10 MiB).")
    if suffix in (".txt", ".md"):
        return decode_text(raw, settings)
    # A timeout also kills and waits for the parser child. No file or shell interpolation.
    try:
        with _slots:
            result = subprocess.run(
                [sys.executable, "-m", __name__, suffix, str(settings.max_note_chars)],
                input=raw,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=PARSER_TIMEOUT,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise ValidationFailed(
            "Belge zamanında okunamadı. Daha küçük parçalara ayırıp yeniden yükleyin.",
            code="DOCUMENT_TIMEOUT",
        ) from exc
    try:
        payload = json.loads(result.stdout)
        if result.returncode or not isinstance(payload, dict):
            raise ValueError("parser failed")
        if payload.get("code"):
            cls = PayloadTooLarge if payload["code"] == "PAYLOAD_TOO_LARGE" else ValidationFailed
            raise cls(payload["message"], code=payload["code"])
        text = payload["text"]
        if not isinstance(text, str):
            raise ValueError("invalid text")
    except (ValueError, KeyError) as exc:
        raise ValidationFailed(
            "Belge okunamadı. Dosyayı yeniden PDF, DOCX veya XLSX olarak kaydedin.",
            code="INVALID_DOCUMENT",
        ) from exc
    if len(text.encode("utf-8")) > settings.max_note_bytes:
        raise PayloadTooLarge("Çıkarılan metin çok büyük. Belgeyi parçalara ayırın.")
    return normalize_text(text, settings)


def _checked_join(parts: list[str], limit: int) -> str:
    text = "\n\n".join(parts)
    if len(text) > limit:
        raise PayloadTooLarge("Çıkarılan metin 100.000 karakter sınırını aşıyor; belgeyi bölün.")
    return text


def _pdf(raw: bytes, limit: int) -> str:
    from pypdf import PdfReader
    from pypdf.generic import DictionaryObject

    if not raw.startswith(b"%PDF-"):
        raise ValidationFailed("Dosya geçerli bir PDF değil.", code="INVALID_DOCUMENT")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise ValidationFailed(
            "Şifreli PDF yüklenemiyor. Şifresiz bir kopyasını yükleyin.", code="ENCRYPTED_DOCUMENT"
        )
    if len(reader.pages) > MAX_PAGES:
        raise PayloadTooLarge("PDF en fazla 200 sayfa olabilir. Belgeyi bölerek yükleyin.")
    parts: list[str] = []
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            parts.append(f"[Sayfa {index}]\n{text}")
            _checked_join(parts, limit)
        resources = page.get("/Resources")
        resources = resources.get_object() if resources is not None else None
        if not text and isinstance(resources, DictionaryObject) and resources.get("/XObject"):
            raise ValidationFailed(
                f"PDF'nin {index}. sayfasında okunabilir metin yok. "
                "Taranmış sayfalara OCR uygulayıp yeniden yükleyin.",
                code="OCR_REQUIRED",
            )
    if not parts:
        raise ValidationFailed(
            "PDF'de okunabilir metin yok. Taranmış belgeye OCR uygulayıp yeniden yükleyin.",
            code="OCR_REQUIRED",
        )
    return _checked_join(parts, limit)


def _docx(raw: bytes, limit: int) -> str:
    from defusedxml import ElementTree

    if raw.startswith(b"\xd0\xcf\x11\xe0"):
        raise ValidationFailed(
            "Şifreli veya eski Word dosyası. Şifresiz DOCX olarak kaydedip yükleyin.",
            code="ENCRYPTED_DOCUMENT",
        )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > MAX_EXPANDED_BYTES:
            raise PayloadTooLarge("Word belgesinin açılmış boyutu çok büyük. Belgeyi bölün.")
        if len({e.filename for e in entries}) != len(entries):
            raise ValueError("duplicate archive members")
        if any(e.flag_bits & 1 for e in entries):
            raise ValidationFailed("Şifreli Word yüklenemiyor.", code="ENCRYPTED_DOCUMENT")
        if any(e.filename.lower().endswith("vbaproject.bin") for e in entries):
            raise ValidationFailed("Makrolu Word belgesini makrosuz DOCX olarak kaydedin.")
        root = ElementTree.fromstring(archive.read("word/document.xml"))
        namespace = root.tag.split("}")[0].lstrip("{")
        if namespace not in _WORD_NAMESPACES or root.tag != f"{{{namespace}}}document":
            raise ValueError("not a Word document")
        w = "{" + namespace + "}"
        if any(e.tag == w + "altChunk" for e in root.iter()):
            raise ValidationFailed("Gömülü içeriği Word'de açıp normal DOCX olarak kaydedin.")
        body = root.find(w + "body")
        if body is None:
            raise ValueError("missing body")
        parts = []
        # Iteration preserves paragraph/table order, including hyperlinks and split runs.
        for paragraph in body.iter(w + "p"):
            fragments = []
            for element in paragraph.iter():
                if element.tag == w + "t":
                    fragments.append(element.text or "")
                elif element.tag == w + "tab":
                    fragments.append("\t")
                elif element.tag in (w + "br", w + "cr"):
                    fragments.append("\n")
            text = "".join(fragments).strip()
            if text:
                parts.append(text)
                _checked_join(parts, limit)
        if not parts:
            raise ValidationFailed(
                "Word belgesinde okunabilir metin yok. Görsellere OCR uygulayın.",
                code="NO_DOCUMENT_TEXT",
            )
        return _checked_join(parts, limit)


def _main() -> None:
    logging.disable(logging.CRITICAL)
    # Unix address-space ceiling; Windows still has byte/page/archive/time limits.
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    payload: dict[str, Any]
    try:
        raw = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            raise PayloadTooLarge("Belge 10 MiB sınırını aşıyor.")
        from notes_graphrag.ingestion.spreadsheets import xls_text, xlsx_text

        parser = {".pdf": _pdf, ".docx": _docx, ".xlsx": xlsx_text, ".xls": xls_text}[sys.argv[1]]
        payload = {"text": parser(raw, int(sys.argv[2]))}
    except (ValidationFailed, PayloadTooLarge) as exc:
        payload = {"code": exc.code, "message": exc.message}
    except Exception:
        payload = {
            "code": "INVALID_DOCUMENT",
            "message": "Belge bozuk veya desteklenmiyor. Yeniden PDF/DOCX/XLSX olarak kaydedin.",
        }
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    _main()
