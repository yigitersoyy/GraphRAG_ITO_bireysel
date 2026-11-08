"""Read spreadsheet values as source text; never evaluate formulas or external links."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime, time, timedelta
from typing import Any

from notes_graphrag.core.errors import PayloadTooLarge, ValidationFailed

MAX_SHEETS = 50
MAX_ROWS = 10_000
MAX_COLUMNS = 256
MAX_CELLS = 20_000


def _value(value: Any) -> str:
    if isinstance(value, (datetime, date, time)):
        value = value.isoformat()
    elif isinstance(value, timedelta):
        value = str(value)
    elif isinstance(value, float) and value.is_integer():
        value = int(value)
    return json.dumps(value, ensure_ascii=False, default=str)


class _Text:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.size = 0
        self.cells = 0
        self.parts = [
            "[Excel: kayıtlı hücre değerleri; formüller yeniden hesaplanmadı. "
            "Gizli sayfa ve satırlar da dahildir.]"
        ]

    def add(self, line: str) -> None:
        self.size += len(line) + 1
        if self.size > self.limit:
            raise PayloadTooLarge(
                "Excel metni çok uzun. Daha az sayfa/satır içeren dosyalar yükleyin."
            )
        self.parts.append(line)

    def cell(self, sheet: str, coordinate: str, text: str) -> str:
        self.cells += 1
        if self.cells > MAX_CELLS:
            raise PayloadTooLarge("Excel en fazla 20.000 dolu hücre içerebilir. Dosyayı bölün.")
        return f"{_value(sheet)}!{coordinate} = {text}"

    def finish(self) -> str:
        if not self.cells:
            raise ValidationFailed(
                "Excel dosyasında okunabilir hücre yok.", code="NO_DOCUMENT_TEXT"
            )
        result = "\n".join(self.parts)
        if len(result) > self.limit:
            raise PayloadTooLarge("Excel metni çok uzun. Dosyayı bölün.")
        return result


def _bounds(sheets: int, rows: int = 0, columns: int = 0) -> None:
    if sheets > MAX_SHEETS or rows > MAX_ROWS or columns > MAX_COLUMNS:
        raise PayloadTooLarge(
            "Excel sınırı: 50 sayfa; her sayfada 10.000 satır ve 256 sütun. Dosyayı bölün."
        )


def xlsx_text(raw: bytes, limit: int) -> str:
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    if raw.startswith(b"\xd0\xcf\x11\xe0"):
        raise ValidationFailed(
            "Şifreli veya XLS biçimindeki dosyayı şifresiz XLSX olarak kaydedin.",
            code="ENCRYPTED_DOCUMENT",
        )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > 20 * 1024 * 1024:
            raise PayloadTooLarge("Excel arşivinin açılmış boyutu çok büyük. Dosyayı bölün.")
        if len({e.filename for e in entries}) != len(entries):
            raise ValueError("duplicate archive members")
        if any(e.flag_bits & 1 for e in entries):
            raise ValidationFailed("Şifreli Excel yüklenemiyor.", code="ENCRYPTED_DOCUMENT")
        if any(e.filename.lower().endswith("vbaproject.bin") for e in entries):
            raise ValidationFailed("Makrolu dosyayı makrosuz XLSX olarak kaydedin.")
    out = _Text(limit)
    book = load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    cached = None
    try:
        cached = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
        _bounds(len(book.sheetnames))
        for sheet in book.worksheets:
            saved = cached[sheet.title]
            state = "görünür" if sheet.sheet_state == "visible" else "gizli"
            out.add(f"[Çalışma sayfası: {_value(sheet.title)}; {state}]")
            # Ignore untrustworthy declared dimensions; read actual cells, including gaps.
            sheet.reset_dimensions()
            saved.reset_dimensions()
            for row_number, (row, values) in enumerate(zip(sheet.rows, saved.rows, strict=True), 1):
                _bounds(0, row_number)
                cells = []
                for column, (cell, value) in enumerate(zip(row, values, strict=True), 1):
                    if cell.value is None:
                        continue
                    _bounds(0, 0, column)
                    if cell.data_type == "f":
                        formula = cell.value
                        if not isinstance(formula, str):
                            formula = getattr(formula, "text", "desteklenmeyen formül")
                        text = f"formül {_value(formula)}; "
                        text += (
                            "kayıtlı sonuç yok (hesaplanmadı)"
                            if value.value is None
                            else f"kayıtlı sonuç (hesaplanmadı): {_value(value.value)}"
                        )
                    else:
                        text = _value(cell.value)
                    if cell.number_format not in ("General", "@"):
                        text += f"; hücre biçimi: {_value(cell.number_format)}"
                    cells.append(
                        out.cell(sheet.title, f"{get_column_letter(column)}{row_number}", text)
                    )
                if cells:
                    out.add(" | ".join(cells))
        return out.finish()
    finally:
        book.close()
        if cached is not None:
            cached.close()


def xls_text(raw: bytes, limit: int) -> str:
    import xlrd
    from openpyxl.utils import get_column_letter

    out = _Text(limit)
    book = xlrd.open_workbook(
        file_contents=raw, on_demand=True, formatting_info=True, logfile=io.StringIO()
    )
    try:
        _bounds(book.nsheets)
        for sheet in book.sheets():
            _bounds(0, sheet.nrows, sheet.ncols)
            state = "görünür" if sheet.visibility == 0 else "gizli"
            out.add(f"[Çalışma sayfası: {_value(sheet.name)}; {state}]")
            for row in range(sheet.nrows):
                cells = []
                for column in range(sheet.ncols):
                    cell = sheet.cell(row, column)
                    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        continue
                    value: Any = cell.value
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        serial = float(cell.value)
                        converted = xlrd.xldate_as_datetime(serial, book.datemode)
                        value = converted.time() if 0 <= serial < 1 else converted
                    elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                        value = bool(value)
                    elif cell.ctype == xlrd.XL_CELL_ERROR:
                        value = xlrd.error_text_from_code.get(int(cell.value), "Excel hücre hatası")
                    text = _value(value)
                    number_format = book.format_map.get(book.xf_list[cell.xf_index or 0].format_key)
                    if number_format and number_format.format_str not in ("General", "@"):
                        text += f"; hücre biçimi: {_value(number_format.format_str)}"
                    cells.append(
                        out.cell(sheet.name, f"{get_column_letter(column + 1)}{row + 1}", text)
                    )
                if cells:
                    out.add(" | ".join(cells))
        return out.finish()
    finally:
        book.release_resources()
