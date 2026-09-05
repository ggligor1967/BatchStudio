from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from core.contracts import OperationResult
from core.operations.base import Operation
from core.security import exclusive_output

try:
    import pytesseract

    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


def _tesseract_binary_available() -> bool:
    if not HAS_TESSERACT:
        return False
    try:
        _ = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


HAS_TESSERACT_BINARY = _tesseract_binary_available()

try:
    from pdf2image import convert_from_path

    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False


class OCRImageOperation(Operation):
    id = "ocr_image"
    name = "OCR Image to Text"
    description = "Extract text from images using Tesseract OCR"
    accepted_types = {"image"}
    output_type = "text"
    requires_ocr = True

    def resolve_output_path(self, file_path: Path, output_path: Path) -> Path:
        return output_path.with_suffix(".txt")

    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        if not HAS_TESSERACT_BINARY:
            return OperationResult(success=False, error="pytesseract not installed")
        txt_path = output_path
        if dry_run:
            return OperationResult(success=True, output_path=txt_path, message="Dry run OCR image")

        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang=self.config.get("language", "eng"))
            with exclusive_output(txt_path, text=True) as stream:
                stream.write(text)
            return OperationResult(success=True, output_path=txt_path, message="OCR extraction complete", metadata={"word_count": len(text.split())})
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        if not HAS_TESSERACT_BINARY:
            return False
        try:
            Image.open(file_path)
            return True
        except Exception:
            return False

    def get_capability_error(self):
        if not HAS_TESSERACT_BINARY:
            return "OCR image requires an installed Tesseract binary"
        return None

    def get_config_schema(self):
        return {
            "language": {"type": "str", "default": "eng"},
            "page_segmentation_mode": {"type": "int", "default": 3},
            "grayscale": {"type": "bool", "default": False},
            "threshold": {"type": "bool", "default": False},
        }


class OCRPDFOperation(Operation):
    id = "ocr_pdf"
    name = "PDF to Text"
    description = "Extract text from PDFs (native/OCR)"
    accepted_types = {"pdf"}
    output_type = "text"

    def resolve_output_path(self, file_path: Path, output_path: Path) -> Path:
        return output_path.with_suffix(".txt")

    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        txt_path = output_path
        if dry_run:
            return OperationResult(success=True, output_path=txt_path, message="Dry run OCR PDF")

        try:
            mode = self.config.get("mode", "auto")
            reader = PdfReader(str(file_path))
            native_text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            text = native_text
            extraction = "native"

            if mode == "ocr" or (mode == "auto" and len(native_text.strip()) < 50):
                if not HAS_TESSERACT or not HAS_PDF2IMAGE:
                    return OperationResult(success=False, error="OCR dependencies missing for scanned PDF")
                images = convert_from_path(str(file_path), dpi=int(self.config.get("dpi", 200)))
                text = "\n\n".join(pytesseract.image_to_string(img, lang=self.config.get("language", "eng")) for img in images)
                extraction = "ocr"

            with exclusive_output(txt_path, text=True) as stream:
                stream.write(text)
            return OperationResult(success=True, output_path=txt_path, message=f"Extracted text using {extraction}")
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        try:
            PdfReader(str(file_path))
            return True
        except Exception:
            return False

    def get_capability_error(self):
        mode = self.config.get("mode", "auto")
        if mode in {"ocr", "auto"} and not HAS_TESSERACT_BINARY:
            return "OCR PDF mode requires an installed Tesseract binary"
        if mode in {"ocr", "auto"} and not HAS_PDF2IMAGE:
            return "OCR PDF mode requires pdf2image"
        return None

    def get_config_schema(self):
        return {
            "mode": {"type": "choice", "default": "auto", "choices": ["auto", "native", "ocr"]},
            "language": {"type": "str", "default": "eng"},
            "dpi": {"type": "int", "default": 200},
        }


class OCRBatchOperation(Operation):
    id = "ocr_batch"
    name = "Batch OCR"
    description = "Extract text from multiple files"
    accepted_types = {"any"}
    output_type = "text"
    requires_ocr = True

    def resolve_output_path(self, file_path: Path, output_path: Path) -> Path:
        return output_path.with_suffix(".txt")

    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        base_op = OCRImageOperation(config=self.config)
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return OCRPDFOperation(config=self.config).execute(file_path, output_path, dry_run=dry_run)
        return base_op.execute(file_path, output_path, dry_run=dry_run)

    def validate(self, file_path: Path) -> bool:
        if file_path.suffix.lower() == ".pdf":
            return OCRPDFOperation(config=self.config).validate(file_path)
        return OCRImageOperation(config=self.config).validate(file_path)

    def get_capability_error(self):
        if not HAS_TESSERACT_BINARY:
            return "Batch OCR requires an installed Tesseract binary"
        return None

    def get_config_schema(self):
        return {
            "language": {"type": "str", "default": "eng"},
            "combine_output": {"type": "bool", "default": False},
            "combined_filename": {"type": "str", "default": "combined_ocr_output.txt"},
        }
