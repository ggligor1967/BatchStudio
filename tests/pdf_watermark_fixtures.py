"""Byte-deterministic synthetic PDFs for the V12-04 geometry contract."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path


PdfBox = tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class PageFixture:
    media_box: PdfBox
    crop_box: PdfBox | None = None
    rotation: int = 0


@dataclass(frozen=True, slots=True)
class PdfFixture:
    fixture_id: str
    filename: str
    pages: tuple[PageFixture, ...]
    expected_sha256: str


A4_PORTRAIT = PageFixture(("0", "0", "595.275591", "841.889764"))
A4_LANDSCAPE = PageFixture(("0", "0", "841.889764", "595.275591"))
LETTER_PORTRAIT = PageFixture(("0", "0", "612", "792"))
SMALL_PAGE = PageFixture(("0", "0", "240", "320"))
LARGE_PAGE = PageFixture(("0", "0", "1200", "1800"))


PDF_WATERMARK_FIXTURES = (
    PdfFixture(
        "F1",
        "f1-a4-portrait.pdf",
        (A4_PORTRAIT,),
        "703639ed602f3002e240d37802a628abf12c16461128cc81f0f08510edef5069",
    ),
    PdfFixture(
        "F2",
        "f2-a4-landscape.pdf",
        (A4_LANDSCAPE,),
        "83654eb49db99371a80a1cb34e6e6eb1ce3013595d1c74dccc8290bacdcd32af",
    ),
    PdfFixture(
        "F3",
        "f3-letter-portrait.pdf",
        (LETTER_PORTRAIT,),
        "cb581373f39056ffa85cb7772c736217cca152a4466b1614a3b2fcaa208ac203",
    ),
    PdfFixture(
        "F4",
        "f4-small.pdf",
        (SMALL_PAGE,),
        "a295250fe7aa0e36ef6e3c9d952282bd48300bbd44b8244e992613d9961280ed",
    ),
    PdfFixture(
        "F5",
        "f5-large.pdf",
        (LARGE_PAGE,),
        "9fcb470c3bcc2df4ae74c98cabcc66067e1b6d67111f86af90e197b544a7e129",
    ),
    PdfFixture(
        "F6",
        "f6-mixed-size.pdf",
        (A4_PORTRAIT, PageFixture(("0", "0", "500", "500")), A4_LANDSCAPE),
        "1189fff829d804c51b418d1afaab4b20617d36ae3ab84eeb15cc3e0399bb8dff",
    ),
    PdfFixture(
        "F7",
        "f7-rotated-90.pdf",
        (PageFixture(LETTER_PORTRAIT.media_box, rotation=90),),
        "f527a6b802df328590618a703283719a56bb0646f83dd6697acfff56819e60d6",
    ),
    PdfFixture(
        "F8",
        "f8-rotated-180.pdf",
        (PageFixture(LETTER_PORTRAIT.media_box, rotation=180),),
        "a96fac93012ad3b862c7719832582b15c376f9af7820b810ceaa295acc4d0eca",
    ),
    PdfFixture(
        "F9",
        "f9-rotated-270.pdf",
        (PageFixture(LETTER_PORTRAIT.media_box, rotation=270),),
        "fc7d79be67052959e6c61b33322c81a4c97b8c80cc2c26bd770e180d0cc0edc2",
    ),
    PdfFixture(
        "F10",
        "f10-crop-box.pdf",
        (PageFixture(LETTER_PORTRAIT.media_box, crop_box=("36", "72", "576", "720")),),
        "1b1561a66083252d1ffa6c8ce4bfa08f0ab3d4be4a021752d8dbbf8fc89de793",
    ),
    PdfFixture(
        "F11",
        "f11-mixed-geometry.pdf",
        (
            PageFixture(SMALL_PAGE.media_box, rotation=90),
            PageFixture(A4_PORTRAIT.media_box, rotation=270),
            PageFixture(
                LARGE_PAGE.media_box,
                crop_box=("100", "150", "1100", "1650"),
                rotation=180,
            ),
        ),
        "b2c628aed0b420ad24002e1f34076fd7c1090df872a22ed399e2e42e17ff64f5",
    ),
)


def build_pdf_fixture(fixture: PdfFixture) -> bytes:
    """Build a minimal PDF with stable object order, offsets, and source markers."""
    page_object_ids = [4 + page_index * 2 for page_index in range(len(fixture.pages))]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Count {len(page_object_ids)} /Kids "
            f"[{' '.join(f'{object_id} 0 R' for object_id in page_object_ids)}] >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    for page_index, page in enumerate(fixture.pages, start=1):
        page_object_id = page_object_ids[page_index - 1]
        content_object_id = page_object_id + 1
        page_entries = [
            "/Type /Page",
            "/Parent 2 0 R",
            f"/MediaBox [{_format_box(page.media_box)}]",
            "/Resources << /Font << /F1 3 0 R >> >>",
            f"/Contents {content_object_id} 0 R",
        ]
        if page.crop_box is not None:
            page_entries.append(f"/CropBox [{_format_box(page.crop_box)}]")
        if page.rotation:
            page_entries.append(f"/Rotate {page.rotation}")
        objects.append(("<< " + " ".join(page_entries) + " >>").encode("ascii"))

        visible_box = page.crop_box or page.media_box
        marker_x = _format_decimal(Decimal(visible_box[0]) + Decimal("20"))
        marker_y = _format_decimal(Decimal(visible_box[1]) + Decimal("20"))
        marker = f"SOURCE_{fixture.fixture_id}_P{page_index}"
        content = (
            "q\n"
            "0.8 w\n"
            f"{marker_x} {marker_y} 40 30 re\n"
            "S\n"
            "Q\n"
            "BT\n"
            "/F1 12 Tf\n"
            f"{marker_x} {marker_y} Td\n"
            f"({marker}) Tj\n"
            "ET\n"
        ).encode("ascii")
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"endstream"
        )

    return _serialize_pdf(objects)


def write_pdf_fixture(root: Path, fixture: PdfFixture) -> Path:
    path = root / fixture.filename
    path.write_bytes(build_pdf_fixture(fixture))
    return path


def fixture_sha256(fixture: PdfFixture) -> str:
    return sha256(build_pdf_fixture(fixture)).hexdigest()


def _format_box(box: PdfBox) -> str:
    return " ".join(_format_decimal(Decimal(value)) for value in box)


def _format_decimal(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _serialize_pdf(objects: list[bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)
