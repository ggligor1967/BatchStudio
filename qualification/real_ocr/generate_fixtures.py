#!/usr/bin/env python3
"""Generate the byte-stable synthetic fixtures used by real-OCR qualification."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

IMAGE_SIZE = (1600, 400)
PDF_PAGE_SIZE = (576, 144)
IMAGE_TEXT = "BATCHSTUDIO OCR 7319"
SCANNED_PDF_TEXT = "SCANNED PDF OCR 4827"
NATIVE_PDF_TEXT = "NATIVE PDF TEXT 5631"


def render_text_image(text: str) -> Image.Image:
    image = Image.new("L", IMAGE_SIZE, color=255)
    font = ImageFont.load_default(size=72)
    draw = ImageDraw.Draw(image)
    draw.text((IMAGE_SIZE[0] // 2, IMAGE_SIZE[1] // 2), text, fill=0, font=font, anchor="mm")
    return image


def encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", compress_level=9, optimize=False)
    return buffer.getvalue()


def write_scanned_pdf(path: Path) -> None:
    raster_bytes = encode_png(render_text_image(SCANNED_PDF_TEXT))
    pdf = Canvas(str(path), pagesize=PDF_PAGE_SIZE, pageCompression=0, invariant=1)
    pdf.setAuthor("BatchStudio")
    pdf.setCreator("BatchStudio V11-06 fixture generator")
    pdf.setSubject("Synthetic image-only OCR qualification fixture")
    pdf.setTitle("BatchStudio scanned OCR fixture")
    pdf.drawImage(
        ImageReader(BytesIO(raster_bytes)),
        0,
        0,
        width=PDF_PAGE_SIZE[0],
        height=PDF_PAGE_SIZE[1],
        preserveAspectRatio=False,
        mask=None,
    )
    pdf.showPage()
    pdf.save()


def write_native_pdf(path: Path) -> None:
    pdf = Canvas(str(path), pagesize=PDF_PAGE_SIZE, pageCompression=0, invariant=1)
    pdf.setAuthor("BatchStudio")
    pdf.setCreator("BatchStudio V11-06 fixture generator")
    pdf.setSubject("Synthetic native-text qualification fixture")
    pdf.setTitle("BatchStudio native PDF fixture")
    pdf.setFont("Helvetica", 28)
    pdf.drawString(36, 64, NATIVE_PDF_TEXT)
    pdf.showPage()
    pdf.save()


def generate_fixtures(output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "known_text.png").write_bytes(encode_png(render_text_image(IMAGE_TEXT)))
    write_scanned_pdf(output_directory / "scanned_text.pdf")
    write_native_pdf(output_directory / "native_text.pdf")


def verify_reproducible_fixtures(expected_directory: Path) -> None:
    with TemporaryDirectory(prefix="batchstudio-real-ocr-fixtures-") as temporary_directory:
        generated_directory = Path(temporary_directory)
        generate_fixtures(generated_directory)
        mismatches = [
            name
            for name in ("known_text.png", "scanned_text.pdf", "native_text.pdf")
            if (generated_directory / name).read_bytes() != (expected_directory / name).read_bytes()
        ]
    if mismatches:
        raise RuntimeError(f"Fixture regeneration mismatch: {', '.join(mismatches)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).with_name("fixtures"),
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()

    if arguments.check:
        verify_reproducible_fixtures(arguments.output_directory)
        print("Controlled OCR fixtures reproduce byte-for-byte.")
    else:
        generate_fixtures(arguments.output_directory)
        print(f"Generated controlled OCR fixtures in {arguments.output_directory.resolve()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
