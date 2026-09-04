from __future__ import annotations

from typing import Dict, List, Optional, Type

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


FILE_TYPE_BY_EXTENSION = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".bmp": "image",
    ".webp": "image",
    ".tiff": "image",
    ".tif": "image",
    ".pdf": "pdf",
    ".csv": "csv",
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".txt": "text",
    ".json": "text",
    ".xml": "text",
}


class OperationRegistry:
    def __init__(self):
        self.operations: Dict[str, Type[Operation]] = {
            ImageResizeOperation.id: ImageResizeOperation,
            ImageConvertOperation.id: ImageConvertOperation,
            ImageFilterOperation.id: ImageFilterOperation,
            PDFWatermarkOperation.id: PDFWatermarkOperation,
            CSVFilterOperation.id: CSVFilterOperation,
            FileRenameOperation.id: FileRenameOperation,
            OCRImageOperation.id: OCRImageOperation,
            OCRPDFOperation.id: OCRPDFOperation,
            OCRBatchOperation.id: OCRBatchOperation,
        }
        self.aggregate_operations: Dict[str, Type[AggregateOperation]] = {
            PDFAggregateMergeOperation.id: PDFAggregateMergeOperation,
        }

    def get_operation(self, operation_id: str, config: Optional[dict] = None) -> Optional[Operation]:
        op_class = self.operations.get(operation_id)
        return op_class(config) if op_class else None

    def get_operation_class(self, operation_id: str):
        return self.operations.get(operation_id)

    def get_aggregate_operation(self, operation_id: str, config: Optional[dict] = None) -> Optional[AggregateOperation]:
        op_class = self.aggregate_operations.get(operation_id)
        return op_class(config) if op_class else None

    def list_operations(self) -> List[dict]:
        result: List[dict] = []
        for op_id, op_class in self.operations.items():
            op = op_class()
            result.append({"id": op_id, "name": op.name, "description": op.description})
        for op_id, op_class in self.aggregate_operations.items():
            op = op_class()
            result.append({"id": op_id, "name": op.name, "description": op.description})
        return result

    def classify_extension(self, extension: str) -> str:
        return FILE_TYPE_BY_EXTENSION.get(extension.lower(), "unknown")

    def has_ocr_capability(self) -> bool:
        return HAS_TESSERACT and HAS_TESSERACT_BINARY and HAS_PDF2IMAGE
