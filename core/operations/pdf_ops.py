from __future__ import annotations

import io
from dataclasses import dataclass
from math import cos, isfinite, radians, sin
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from core.contracts import OperationResult
from core.operations.base import AggregateOperation, Operation
from core.security import exclusive_output, resolve_safe_output


WATERMARK_FONT = "Helvetica"
WATERMARK_MAX_FONT_SIZE = 60.0
WATERMARK_ANGLE = 45.0


@dataclass(frozen=True, slots=True)
class _PageWatermarkGeometry:
    visible_width: float
    visible_height: float
    overlay_to_page: tuple[float, float, float, float, float, float]


class PDFWatermarkOperation(Operation):
    id = "pdf_watermark"
    name = "PDF Watermark"
    description = "Add text watermark to PDF documents"
    accepted_types = {"pdf"}
    output_type = "pdf"

    def _execute(
        self, file_path: Path, output_path: Path, dry_run: bool = False
    ) -> OperationResult:
        if dry_run:
            return OperationResult(
                success=True, output_path=output_path, message="Dry run watermark"
            )

        try:
            reader = PdfReader(str(file_path))
            writer = PdfWriter()
            text = str(self.config.get("text", "CONFIDENTIAL"))

            for page in reader.pages:
                geometry = _get_page_watermark_geometry(page)
                watermark = _create_watermark_page(text, geometry)
                output_page = writer.add_page(page)
                output_page.merge_transformed_page(
                    watermark,
                    geometry.overlay_to_page,
                    expand=False,
                )

            with exclusive_output(output_path) as output_file:
                writer.write(output_file)

            return OperationResult(
                success=True,
                output_path=output_path,
                message=f"Watermarked {len(reader.pages)} pages",
            )
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        try:
            PdfReader(str(file_path))
            return True
        except Exception:
            return False

    def get_config_schema(self):
        return {"text": {"type": "str", "default": "CONFIDENTIAL"}}


def _get_page_watermark_geometry(page) -> _PageWatermarkGeometry:
    left, bottom, right, top = (float(value) for value in page.cropbox)
    if not all(isfinite(value) for value in (left, bottom, right, top)):
        raise ValueError("PDF page CropBox must contain finite coordinates")

    crop_width = right - left
    crop_height = top - bottom
    if crop_width <= 0 or crop_height <= 0:
        raise ValueError("PDF page CropBox must have positive width and height")

    raw_rotation = float(page.rotation)
    if not isfinite(raw_rotation) or raw_rotation % 90 != 0:
        raise ValueError("PDF page rotation must be a multiple of 90 degrees")
    rotation = int(raw_rotation) % 360

    if rotation == 0:
        visible_width, visible_height = crop_width, crop_height
        overlay_to_page = (1.0, 0.0, 0.0, 1.0, left, bottom)
    elif rotation == 90:
        visible_width, visible_height = crop_height, crop_width
        overlay_to_page = (0.0, 1.0, -1.0, 0.0, left + crop_width, bottom)
    elif rotation == 180:
        visible_width, visible_height = crop_width, crop_height
        overlay_to_page = (-1.0, 0.0, 0.0, -1.0, left + crop_width, bottom + crop_height)
    else:
        visible_width, visible_height = crop_height, crop_width
        overlay_to_page = (0.0, -1.0, 1.0, 0.0, left, bottom + crop_height)

    return _PageWatermarkGeometry(
        visible_width=visible_width,
        visible_height=visible_height,
        overlay_to_page=overlay_to_page,
    )


def _create_watermark_page(text: str, geometry: _PageWatermarkGeometry):
    font_size = _fit_watermark_font_size(text, geometry)
    ascent, descent = pdfmetrics.getAscentDescent(WATERMARK_FONT, font_size)
    centered_baseline = -(ascent + descent) / 2

    packet = io.BytesIO()
    watermark_canvas = canvas.Canvas(
        packet,
        pagesize=(geometry.visible_width, geometry.visible_height),
    )
    watermark_canvas.setFont(WATERMARK_FONT, font_size)
    watermark_canvas.setFillGray(0.5, alpha=0.3)
    watermark_canvas.saveState()
    watermark_canvas.translate(geometry.visible_width / 2, geometry.visible_height / 2)
    watermark_canvas.rotate(WATERMARK_ANGLE)
    watermark_canvas.drawCentredString(0, centered_baseline, text)
    watermark_canvas.restoreState()
    watermark_canvas.save()

    packet.seek(0)
    return PdfReader(packet).pages[0]


def _fit_watermark_font_size(text: str, geometry: _PageWatermarkGeometry) -> float:
    if not text:
        return WATERMARK_MAX_FONT_SIZE

    text_width = pdfmetrics.stringWidth(text, WATERMARK_FONT, WATERMARK_MAX_FONT_SIZE)
    ascent, descent = pdfmetrics.getAscentDescent(WATERMARK_FONT, WATERMARK_MAX_FONT_SIZE)
    text_height = ascent - descent
    angle = radians(WATERMARK_ANGLE)
    rotated_width = abs(cos(angle)) * text_width + abs(sin(angle)) * text_height
    rotated_height = abs(sin(angle)) * text_width + abs(cos(angle)) * text_height
    scale = min(
        1.0,
        geometry.visible_width / rotated_width,
        geometry.visible_height / rotated_height,
    )
    return WATERMARK_MAX_FONT_SIZE * scale


class PDFAggregateMergeOperation(AggregateOperation):
    id = "pdf_merge"
    name = "PDF Merge"
    description = "Merge multiple PDF files into one output"
    accepted_types = {"pdf"}
    output_type = "pdf"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._writer: Optional[PdfWriter] = None
        self._output_path: Optional[Path] = None
        self._dry_run = False
        self._consumed = 0

    def get_config_schema(self):
        return {
            "output_filename": {"type": "str", "default": "merged_output.pdf"},
        }

    def begin(self, output_path: Path, dry_run: bool = False) -> None:
        self._output_path = resolve_safe_output(output_path.parent, output_path.name, required_suffix=".pdf")
        self._dry_run = dry_run
        self._consumed = 0
        self._writer = None if dry_run else PdfWriter()

    def consume(self, file_path: Path) -> OperationResult:
        try:
            if not self.validate(file_path):
                return OperationResult(success=False, error=f"Invalid PDF: {file_path.name}")

            self._consumed += 1
            if self._dry_run:
                return OperationResult(success=True, message=f"Dry run queued {file_path.name}", output_path=file_path)

            assert self._writer is not None
            reader = PdfReader(str(file_path))
            for page in reader.pages:
                self._writer.add_page(page)
            return OperationResult(success=True, message=f"Queued {file_path.name}", output_path=file_path)
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def finalize(self) -> OperationResult:
        if self._output_path is None:
            return OperationResult(success=False, error="Merge not initialized")
        if self._consumed == 0:
            return OperationResult(success=False, error="No PDFs were provided for merge")

        if self._dry_run:
            return OperationResult(success=True, message=f"Dry run merge would produce {self._output_path.name}", output_path=self._output_path)

        try:
            assert self._writer is not None
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            with exclusive_output(self._output_path) as output_file:
                self._writer.write(output_file)
            return OperationResult(success=True, message=f"Merged {self._consumed} files", output_path=self._output_path)
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        try:
            PdfReader(str(file_path))
            return True
        except Exception:
            return False
