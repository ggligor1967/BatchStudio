from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

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


try:
    from pdf2image import convert_from_path

    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False


@dataclass(frozen=True)
class OCRReadiness:
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.error is None


def get_image_ocr_readiness(language: str = "eng") -> OCRReadiness:
    if not HAS_TESSERACT:
        return OCRReadiness("pytesseract package is not installed")
    try:
        pytesseract.get_tesseract_version(cached=False)
    except (Exception, SystemExit):
        return OCRReadiness("Tesseract executable is not available")
    try:
        available_languages = pytesseract.get_languages(cached=False)
    except Exception:
        return OCRReadiness("Tesseract language data could not be checked")
    if not isinstance(language, str) or not language:
        return OCRReadiness("Tesseract language must be a non-empty string")
    for requested in language.split("+"):
        if requested not in available_languages:
            return OCRReadiness(f"Tesseract language '{requested}' is not available")
    return OCRReadiness()


def get_pdf_native_readiness() -> OCRReadiness:
    # pypdf is a required application import, independent of optional OCR tools.
    return OCRReadiness()


def get_pdf_ocr_readiness(language: str = "eng") -> OCRReadiness:
    image = get_image_ocr_readiness(language)
    if not image.ready:
        return image
    if not HAS_PDF2IMAGE:
        return OCRReadiness("pdf2image package is not installed")
    # These are pdf2image's default page-info and rasterization executables.
    for name in ("pdfinfo", "pdftoppm"):
        executable = shutil.which(name)
        if executable is None:
            return OCRReadiness("Poppler PDF rasterizer is not available")
        try:
            probe = subprocess.run(
                [executable, "-v"], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if probe.returncode != 0:
                return OCRReadiness("Poppler PDF rasterizer is not available")
        except (OSError, subprocess.TimeoutExpired):
            return OCRReadiness("Poppler PDF rasterizer is not available")
    return OCRReadiness()


class OCROperation(Operation):
    unsupported_config_keys = frozenset({
        "page_segmentation_mode", "grayscale", "threshold", "threshold_value",
    })

    def validate_config(self) -> tuple[bool, str]:
        for key in sorted(self.unsupported_config_keys):
            if key in self.config:
                return False, f"unsupported OCR configuration '{key}'"
        return super().validate_config()

    def execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        valid, error = self.validate_config()
        if not valid:
            return OperationResult(success=False, error=error)
        error = self.get_capability_error(file_path)
        if error:
            return OperationResult(success=False, error=error)
        return super().execute(file_path, output_path, dry_run)


class OCRImageOperation(OCROperation):
    id = "ocr_image"
    name = "OCR Image to Text"
    description = "Extract text from images using Tesseract OCR"
    accepted_types = {"image"}
    output_type = "text"
    requires_ocr = True

    def resolve_output_path(self, file_path: Path, output_path: Path) -> Path:
        return output_path.with_suffix(".txt")

    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        txt_path = output_path
        if dry_run:
            return OperationResult(success=True, output_path=txt_path, message="Dry run OCR image")

        try:
            with Image.open(file_path) as img:
                text = pytesseract.image_to_string(img, lang=self.config.get("language", "eng"))
            with exclusive_output(txt_path, text=True) as stream:
                stream.write(text)
            return OperationResult(success=True, output_path=txt_path, message="OCR extraction complete", metadata={"word_count": len(text.split())})
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        try:
            with Image.open(file_path):
                pass
            return True
        except Exception:
            return False

    def get_capability_error(self, file_path: Path | None = None):
        return get_image_ocr_readiness(self.config.get("language", "eng")).error

    def get_config_schema(self):
        return {
            "language": {"type": "str", "default": "eng"},
        }


class OCRPDFOperation(OCROperation):
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
                readiness = get_pdf_ocr_readiness(self.config.get("language", "eng"))
                if not readiness.ready:
                    return OperationResult(success=False, error=readiness.error)
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

    def get_capability_error(self, file_path: Path | None = None):
        mode = self.config.get("mode", "auto")
        if mode == "ocr":
            return get_pdf_ocr_readiness(self.config.get("language", "eng")).error
        return get_pdf_native_readiness().error

    def get_config_schema(self):
        return {
            "mode": {"type": "choice", "default": "auto", "choices": ["auto", "native", "ocr"]},
            "language": {"type": "str", "default": "eng"},
            "dpi": {"type": "int", "default": 200},
        }


class OCRBatchOperation(OCROperation):
    unsupported_config_keys = OCROperation.unsupported_config_keys | {
        "combine_output", "combined_filename",
    }
    id = "ocr_batch"
    name = "Batch OCR"
    description = "Extract text from multiple files"
    accepted_types = {"any"}
    output_type = "text"

    def resolve_output_path(self, file_path: Path, output_path: Path) -> Path:
        return output_path.with_suffix(".txt")

    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        return self._operation_for_input(file_path).execute(file_path, output_path, dry_run=dry_run)

    def _operation_for_input(self, file_path: Path) -> OCROperation:
        operation_class = OCRPDFOperation if file_path.suffix.lower() == ".pdf" else OCRImageOperation
        return operation_class(config=self.config)

    def validate(self, file_path: Path) -> bool:
        return self._operation_for_input(file_path).validate(file_path)

    def get_capability_error(self, file_path: Path | None = None):
        if file_path is None:
            # The compiler has no concrete input; a native PDF may need no OCR.
            return None
        return self._operation_for_input(file_path).get_capability_error(file_path)

    def get_config_schema(self):
        return {
            "language": {"type": "str", "default": "eng"},
        }
