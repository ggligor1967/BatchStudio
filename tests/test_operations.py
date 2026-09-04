from pathlib import Path

from PIL import Image

from core.contracts import OperationResult
from core.operations import ImageResizeOperation, OperationRegistry


def test_operation_result_contract():
    result = OperationResult(success=True, message="ok")
    payload = result.to_dict()
    assert payload["success"] is True
    assert payload["message"] == "ok"


def test_resize_returns_actual_output_path(tmp_path: Path):
    src = tmp_path / "input.png"
    Image.new("RGB", (30, 30), color="red").save(src)

    dst = tmp_path / "out.png"
    op = ImageResizeOperation({"width": 10, "height": 10, "maintain_aspect": False})
    result = op.execute(src, dst, dry_run=False)

    assert result.success is True
    assert result.output_path == dst
    assert dst.exists()


def test_registry_includes_aggregate_pdf_merge():
    registry = OperationRegistry()
    merge = registry.get_aggregate_operation("pdf_merge", {})
    assert merge is not None
