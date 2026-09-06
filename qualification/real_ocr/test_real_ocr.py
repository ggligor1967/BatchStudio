"""Real external-tool integration tests for the pinned V11-06 environment."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import pytest
from pypdf import PdfReader

from core.operations import ocr_ops
from core.processor import BatchProcessor
from core.workflow import Workflow
from qualification.real_ocr.verify_environment import (
    QualificationError,
    verify_environment,
    verify_external_toolchain,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_name("contract.json")
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def fixture_path(name: str) -> Path:
    return REPOSITORY_ROOT / CONTRACT["fixtures"][name]["path"]


def expected_text(name: str) -> str:
    return CONTRACT["fixtures"][name]["expected_text"]


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def assert_successful_text_output(result, expected: str) -> None:
    assert result.success, result.error
    assert result.output_path is not None
    encoded = result.output_path.read_bytes()
    decoded = encoded.decode("utf-8")
    assert normalize_text(decoded) == expected


@pytest.fixture(scope="session", autouse=True)
def controlled_qualification_environment() -> dict[str, str]:
    artifact_directory = Path(os.environ["QUALIFICATION_ARTIFACT_DIR"])
    return verify_environment(REPOSITORY_ROOT, CONTRACT_PATH, artifact_directory)


def test_real_image_ocr_uses_batchstudio_path(tmp_path: Path) -> None:
    assert ocr_ops.pytesseract.image_to_string.__module__.startswith("pytesseract")
    operation = ocr_ops.OCRImageOperation({"language": "eng"})

    result = operation.execute(fixture_path("image"), tmp_path / "recognized.pending")

    assert result.metadata["word_count"] == 3
    assert_successful_text_output(result, expected_text("image"))


@pytest.mark.parametrize("mode", ["ocr", "auto"])
def test_real_scanned_pdf_ocr_requires_rasterization(tmp_path: Path, mode: str) -> None:
    scanned_pdf = fixture_path("scanned_pdf")
    native_text = "\n\n".join((page.extract_text() or "") for page in PdfReader(scanned_pdf).pages)
    assert normalize_text(native_text) == ""
    operation = ocr_ops.OCRPDFOperation({"mode": mode, "language": "eng", "dpi": 200})

    result = operation.execute(scanned_pdf, tmp_path / f"scanned-{mode}.pending")

    assert result.message == "Extracted text using ocr"
    assert_successful_text_output(result, expected_text("scanned_pdf"))


def test_native_pdf_text_does_not_use_ocr_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "no-executables"))
    operation = ocr_ops.OCRPDFOperation({"mode": "native", "language": "eng"})

    result = operation.execute(fixture_path("native_pdf"), tmp_path / "native.pending")

    assert result.message == "Extracted text using native"
    assert_successful_text_output(result, expected_text("native_pdf"))


@pytest.mark.parametrize(
    "fixture_name,config",
    [
        ("image", {"language": "eng"}),
        ("scanned_pdf", {"mode": "ocr", "language": "eng", "dpi": 200}),
    ],
)
def test_real_batch_ocr_delegates_to_concrete_path(
    tmp_path: Path, fixture_name: str, config: dict[str, object]
) -> None:
    operation = ocr_ops.OCRBatchOperation(config)

    result = operation.execute(
        fixture_path(fixture_name), tmp_path / f"batch-{fixture_name}.pending"
    )

    assert_successful_text_output(result, expected_text(fixture_name))


@pytest.mark.parametrize(
    "operation,fixture_name",
    [
        (ocr_ops.OCRImageOperation({"language": "eng"}), "image"),
        (ocr_ops.OCRPDFOperation({"mode": "ocr", "language": "eng", "dpi": 200}), "scanned_pdf"),
        (ocr_ops.OCRBatchOperation({"language": "eng"}), "image"),
        (ocr_ops.OCRBatchOperation({"mode": "ocr", "language": "eng", "dpi": 200}), "scanned_pdf"),
    ],
    ids=["image", "pdf", "batch-image", "batch-pdf"],
)
def test_real_ocr_dry_run_is_write_free(
    tmp_path: Path, operation: ocr_ops.OCROperation, fixture_name: str
) -> None:
    output = tmp_path / f"dry-{fixture_name}.pending"

    result = operation.execute(fixture_path(fixture_name), output, dry_run=True)

    assert result.success, result.error
    assert result.output_path is not None
    assert result.output_path.suffix == ".txt"
    assert not result.output_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_real_ocr_outputs_are_collision_safe(tmp_path: Path) -> None:
    input_roots = [tmp_path / "first", tmp_path / "second"]
    for input_root in input_roots:
        input_root.mkdir()
        shutil.copyfile(fixture_path("image"), input_root / "same-name.png")
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    workflow = Workflow("real-ocr-collision")
    workflow.add_step("ocr_image", {"language": "eng"})

    stats = BatchProcessor(max_workers=2).process_batch(
        [str(input_root / "same-name.png") for input_root in input_roots],
        workflow,
        str(output_directory),
        "{original}",
    )

    outputs = sorted(output_directory.glob("*.txt"))
    assert stats.processed_files == 2
    assert stats.failed_files == 0
    assert [path.name for path in outputs] == ["same-name.txt", "same-name_001.txt"]
    assert all(
        normalize_text(path.read_text(encoding="utf-8")) == expected_text("image")
        for path in outputs
    )


def test_invalid_image_input_fails_without_output(tmp_path: Path) -> None:
    invalid_input = tmp_path / "invalid.png"
    invalid_input.write_bytes(b"not an image")
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    workflow = Workflow("invalid-real-ocr-input")
    workflow.add_step("ocr_image", {"language": "eng"})

    stats = BatchProcessor(max_workers=1).process_batch(
        [str(invalid_input)], workflow, str(output_directory), "{original}"
    )

    assert stats.processed_files == 0
    assert stats.failed_files == 1
    assert list(output_directory.iterdir()) == []
    assert "cannot process this file" in str(stats.errors)


def test_missing_controlled_tool_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "no-executables"))

    with pytest.raises(QualificationError, match="Controlled executable is missing"):
        verify_external_toolchain(CONTRACT, Path(os.environ["TESSDATA_PREFIX"]))
