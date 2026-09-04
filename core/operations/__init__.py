from core.operations.base import AggregateOperation, Operation
from core.operations.data_ops import CSVFilterOperation
from core.operations.file_ops import FileRenameOperation
from core.operations.image_ops import ImageConvertOperation, ImageFilterOperation, ImageResizeOperation
from core.operations.ocr_ops import (
    HAS_PDF2IMAGE,
    HAS_TESSERACT,
    HAS_TESSERACT_BINARY,
    OCRBatchOperation,
    OCRImageOperation,
    OCRPDFOperation,
)
from core.operations.pdf_ops import PDFAggregateMergeOperation, PDFWatermarkOperation
from core.operations.registry import FILE_TYPE_BY_EXTENSION, OperationRegistry

__all__ = [
    "AggregateOperation",
    "Operation",
    "OperationRegistry",
    "FILE_TYPE_BY_EXTENSION",
    "ImageResizeOperation",
    "ImageConvertOperation",
    "ImageFilterOperation",
    "PDFWatermarkOperation",
    "PDFAggregateMergeOperation",
    "CSVFilterOperation",
    "FileRenameOperation",
    "OCRImageOperation",
    "OCRPDFOperation",
    "OCRBatchOperation",
    "HAS_TESSERACT",
    "HAS_TESSERACT_BINARY",
    "HAS_PDF2IMAGE",
]
