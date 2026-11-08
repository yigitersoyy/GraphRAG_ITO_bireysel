"""Small in-memory documents for import tests; no user files are read."""

from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def xlsx_bytes(text="Ada works on Project Atlas. Project Atlas uses Neo4j."):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Projeler"
    sheet["A1"] = text
    out = BytesIO()
    book.save(out)
    return out.getvalue()


def xls_bytes(text="Ada works on Project Atlas. Project Atlas uses Neo4j."):
    import xlwt

    book = xlwt.Workbook()
    sheet = book.add_sheet("Projeler")
    sheet.write(0, 0, text)
    out = BytesIO()
    book.save(out)
    return out.getvalue()


def docx_bytes(text="Ada works on Project Atlas. Project Atlas uses Neo4j.", xml=None):
    document = xml or (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p></w:body></w:document>"
    )
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", document)
        z.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0"?><Types '
                'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document.main+xml"/></Types>'
            ),
        )
        z.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0"?><Relationships '
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
            ),
        )
    return out.getvalue()


def pdf_bytes(
    text="Ada works on Project Atlas. Project Atlas uses Neo4j.",
    encrypted=False,
    pages=1,
    image_only=False,
):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        if image_only:
            image = DictionaryObject({NameObject("/Subtype"): NameObject("/Image")})
            objects = DictionaryObject({NameObject("/Im1"): image})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): objects})
        elif text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            content = DecodedStreamObject()
            # Hex strings preserve punctuation without PDF literal-string escaping.
            content.set_data(
                f"BT /F1 12 Tf 40 740 Td <{text.encode('ascii').hex()}> Tj ET".encode()
            )
            page[NameObject("/Contents")] = content
    if encrypted:
        writer.encrypt("test-only")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()
