"""Picker and selection adapters for the existing backend contracts."""

from pathlib import Path

from core.operations.base import AggregateOperation
from core.operations.ocr_ops import OCRBatchOperation, OCROperation
from core.operations.registry import FILE_TYPE_BY_EXTENSION, OperationRegistry
from core.processor import ALLOWED_EXTENSIONS, validate_file_path


def get_input_error(file_path, workflow, registry=None, *, check_path=True):
    """Check input eligibility without executing, recognizing, or rasterizing it."""
    registry = registry or OperationRegistry()
    path = Path(file_path)
    if check_path:
        valid, error = validate_file_path(str(path))
        if not valid:
            return error
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return f"File type '{path.suffix.lower()}' not allowed"
    if workflow is None:
        return None

    requirements = []
    for step in workflow.get_enabled_steps():
        operation = registry.get_operation(step.operation_id, step.config)
        if operation is None:
            operation = registry.get_aggregate_operation(step.operation_id, step.config)
        if operation is None:
            return f"Unknown operation: {step.operation_id}"
        valid, error = operation.validate_config()
        if not valid:
            return f"{operation.name}: {error}"
        # Batch OCR declares 'any'; its backend delegate defines concrete support.
        concrete = (
            operation._operation_for_input(path)
            if isinstance(operation, OCRBatchOperation)
            else operation
        )
        input_type = registry.classify_extension(path.suffix)
        if "any" not in concrete.accepted_types and input_type not in concrete.accepted_types:
            return f"Unsupported input for {operation.name}: {input_type}"
        requirements.append((operation, path))
        if operation.output_type != "same":
            extension = next(
                (
                    ext
                    for ext, kind in FILE_TYPE_BY_EXTENSION.items()
                    if kind == operation.output_type
                ),
                None,
            )
            if extension is not None:
                path = path.with_suffix(extension)

    # Type/configuration refusal takes priority over unrelated OCR prerequisites.
    for operation, input_path in requirements:
        if isinstance(operation, AggregateOperation):
            continue
        error = (
            operation.get_capability_error(input_path)
            if isinstance(operation, OCROperation)
            else operation.get_capability_error()
        )
        if error:
            return f"{operation.name}: {error}"
    return None


def get_picker_filetypes(workflow, registry=None):
    """Derive Tk patterns from backend formats and current workflow requirements."""
    registry = registry or OperationRegistry()
    groups = {}
    # Readiness is identical within a backend input type for the current operations.
    eligibility = {}
    for extension in sorted(ALLOWED_EXTENSIONS):
        input_type = registry.classify_extension(extension)
        if input_type not in eligibility:
            eligibility[input_type] = get_input_error(
                "input" + extension, workflow, registry, check_path=False
            )
        if eligibility[input_type] is None:
            groups.setdefault(input_type, []).append("*" + extension)
    errors = sorted({error for error in eligibility.values() if error})
    if not groups:
        return [], errors
    patterns = tuple(pattern for group in groups.values() for pattern in group)
    return [("Eligible inputs", patterns)] + [
        (input_type.title(), tuple(group)) for input_type, group in groups.items()
    ], errors
