from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from core.contracts import OperationResult
from core.operations.base import AggregateOperation, Operation
from core.security import sanitize_filename


class PDFWatermarkOperation(Operation):
    id = "pdf_watermark"
    name = "PDF Watermark"
    description = "Add text watermark to PDF documents"
    accepted_types = {"pdf"}
    output_type = "pdf"

    def execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        if dry_run:
            return OperationResult(success=True, output_path=output_path, message="Dry run watermark")

        try:
            reader = PdfReader(str(file_path))
            writer = PdfWriter()
            text = self.config.get("text", "CONFIDENTIAL")

            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont("Helvetica", 60)
            can.setFillGray(0.5, alpha=0.3)
            can.saveState()
            can.translate(300, 400)
            can.rotate(45)
            can.drawCentredString(0, 0, str(text))
            can.restoreState()
            can.save()

            packet.seek(0)
            watermark = PdfReader(packet)

            for page in reader.pages:
                page.merge_page(watermark.pages[0])
                writer.add_page(page)

            with output_path.open("wb") as output_file:
                writer.write(output_file)

            return OperationResult(success=True, output_path=output_path, message=f"Watermarked {len(reader.pages)} pages")
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
        self._output_path = output_path.with_name(sanitize_filename(output_path.name))
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
            with self._output_path.open("wb") as output_file:
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
