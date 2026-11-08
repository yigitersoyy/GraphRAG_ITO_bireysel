from datetime import datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook
from tests.support.document_files import xls_bytes, xlsx_bytes

from notes_graphrag.core.config import Settings
from notes_graphrag.core.errors import PayloadTooLarge, ValidationFailed
from notes_graphrag.ingestion.documents import import_document

SETTINGS = Settings(_env_file=None)


def save(book):
    out = BytesIO()
    book.save(out)
    return out.getvalue()


def edit_zip(raw, updates):
    out = BytesIO()
    with ZipFile(BytesIO(raw)) as src, ZipFile(out, "w", ZIP_DEFLATED) as dst:
        for name in src.namelist():
            dst.writestr(name, updates.get(name, lambda v: v)(src.read(name)))
        for name in updates.keys() - set(src.namelist()):
            dst.writestr(name, updates[name](b""))
    return out.getvalue()


def test_xlsx_sheets_coordinates_types_hidden_data_and_formula_cache():
    book = Workbook()
    sheet = book.active
    sheet.title = "Bütçe"
    sheet.append(["Öykü", 120.5, True, datetime(2026, 11, 8), "=SUM(B1,2)"])
    sheet["B1"].number_format = '"₺"#,##0.00'
    sheet["A2"] = 0.25
    sheet["A2"].number_format = "0%"
    sheet["B2"] = "=1+1"
    hidden = book.create_sheet("Gizli")
    hidden.sheet_state = "hidden"
    hidden["C4"] = "Dahili kayıt"
    raw = edit_zip(
        save(book),
        {
            "xl/worksheets/sheet1.xml": lambda v: v.replace(b"<v />", b"<v></v>").replace(
                b"<f>SUM(B1,2)</f><v></v>", b"<f>SUM(B1,2)</f><v>122.5</v>"
            )
        },
    )
    text = import_document("rapor.XLSX", raw, SETTINGS)
    assert '"Bütçe"!A1 = "Öykü"' in text
    assert '"Bütçe"!B1 = 120.5; hücre biçimi:' in text and "₺" in text
    assert '"Bütçe"!C1 = true' in text and "2026-11-08T00:00:00" in text
    assert '"Bütçe"!A2 = 0.25; hücre biçimi: "0%"' in text
    assert 'formül "=SUM(B1,2)"; kayıtlı sonuç (hesaplanmadı): 122.5' in text
    assert '"=1+1"; kayıtlı sonuç yok (hesaplanmadı)' in text
    assert '[Çalışma sayfası: "Gizli"; gizli]' in text
    assert '"Gizli"!C4 = "Dahili kayıt"' in text


def test_xlsx_incorrect_dimensions_do_not_drop_cells():
    book = Workbook()
    book.active["A1"] = "Başlangıç"
    book.active["D8"] = "Son kayıt"
    raw = edit_zip(
        save(book),
        {"xl/worksheets/sheet1.xml": lambda v: v.replace(b'ref="A1:D8"', b'ref="A1:A1"')},
    )
    assert '!D8 = "Son kayıt"' in import_document("test.xlsx", raw, SETTINGS)


def test_xls_turkish_dates_percent_and_multiple_sheets():
    import xlwt

    book = xlwt.Workbook()
    sheet = book.add_sheet("Bütçe")
    sheet.write(0, 0, "Öykü")
    sheet.write(1, 0, datetime(2026, 11, 8), xlwt.easyxf(num_format_str="YYYY-MM-DD"))
    sheet.write(2, 0, 0.25, xlwt.easyxf(num_format_str="0%"))
    sheet.write(3, 0, False)
    sheet.write(4, 0, 0.5, xlwt.easyxf(num_format_str="hh:mm"))
    book.add_sheet("İkinci").write(0, 0, "İzmir")
    text = import_document("old.xls", save(book), SETTINGS)
    assert '"Bütçe"!A1 = "Öykü"' in text
    assert "2026-11-08T00:00:00" in text
    assert '0.25; hücre biçimi: "0%"' in text
    assert '"Bütçe"!A4 = false' in text
    assert '"Bütçe"!A5 = "12:00:00"' in text and "1899-12-31" not in text
    assert '"İkinci"!A1 = "İzmir"' in text


@pytest.mark.parametrize("extension", ["xlsx", "xls"])
def test_invalid_excel_is_actionable(extension):
    with pytest.raises(ValidationFailed) as exc:
        import_document("invalid." + extension, b"broken", SETTINGS)
    assert exc.value.code == "INVALID_DOCUMENT"


@pytest.mark.parametrize("kind", ["sheets", "rows", "columns", "text", "archive", "macro", "empty"])
def test_excel_limits_never_silently_truncate(kind):
    book = Workbook()
    if kind == "sheets":
        for i in range(50):
            book.create_sheet(str(i))
    elif kind == "rows":
        book.active["A10001"] = "far"
    elif kind == "columns":
        book.active["IW1"] = "far"
    elif kind == "text":
        for i in range(10):
            book.active.cell(i + 1, 1, "a" * 12000)
    raw = save(book)
    if kind == "archive":
        raw = edit_zip(raw, {"unused.bin": lambda _: b"a" * (20 * 1024 * 1024)})
    if kind == "macro":
        raw = edit_zip(raw, {"xl/vbaProject.bin": lambda _: b"macro"})
    with pytest.raises((ValidationFailed, PayloadTooLarge)):
        import_document("limit.xlsx", raw, SETTINGS)


def test_encrypted_xlsx_has_password_guidance():
    with pytest.raises(ValidationFailed) as exc:
        import_document("encrypted.xlsx", b"\xd0\xcf\x11\xe0" + b"x" * 30, SETTINGS)
    assert exc.value.code == "ENCRYPTED_DOCUMENT"


@pytest.mark.parametrize("extension,raw", [("xlsx", xlsx_bytes("")), ("xls", xls_bytes(""))])
def test_empty_workbook(extension, raw):
    with pytest.raises(ValidationFailed) as exc:
        import_document("empty." + extension, raw, SETTINGS)
    assert exc.value.code == "NO_DOCUMENT_TEXT"
