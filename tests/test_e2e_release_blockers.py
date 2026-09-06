from concurrent.futures import ALL_COMPLETED, wait as wait_for_futures
from pathlib import Path
import threading
import time

import pytest
from PIL import Image
from pypdf import PdfWriter

from core.operations.image_ops import ImageResizeOperation
from core.operations import ocr_ops
from core import processor as processor_module
from core.processor import BatchProcessor
from core.workflow import Workflow
from tests.pdf_merge_cases import assert_merge_case


def _img(path: Path, color: str = "blue"):
    Image.new("RGB", (80, 80), color=color).save(path)


def _pdf(path: Path):
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=400)
    with path.open("wb") as fh:
        writer.write(fh)


def test_e2e_resize_then_rename(tmp_path: Path):
    src = tmp_path / "in.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _img(src)

    wf = Workflow("resize-rename")
    wf.add_step("image_resize", {"width": 20, "height": 20, "maintain_aspect": False})
    wf.add_step("file_rename", {"pattern": "{original}_r_{counter}"})

    stats = BatchProcessor(max_workers=1).process_batch([str(src)], wf, str(out_dir), "{original}")
    assert stats.failed_files == 0
    assert stats.processed_files == 1


def test_e2e_convert_then_rename(tmp_path: Path):
    src = tmp_path / "in.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _img(src)

    wf = Workflow("convert-rename")
    wf.add_step("image_convert", {"format": "JPEG"})
    wf.add_step("file_rename", {"pattern": "{original}_j_{counter}"})

    stats = BatchProcessor(max_workers=1).process_batch([str(src)], wf, str(out_dir), "{original}")
    assert stats.failed_files == 0
    assert stats.processed_files == 1
    assert any(Path(r["output"]).suffix.lower() in {".jpg", ".jpeg"} for r in stats.results)


@pytest.mark.parametrize("input_count", [2, 3, 5])
def test_e2e_pdf_merge(tmp_path: Path, input_count):
    assert_merge_case(tmp_path, input_count)


def test_e2e_pdf_merge_output_filename_traversal_is_sanitized(tmp_path: Path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out"
    out.mkdir()
    _pdf(a)
    _pdf(b)

    wf = Workflow("pdf-merge-safe-name")
    wf.add_step("pdf_merge", {"output_filename": "..\\..\\merged.pdf"})

    stats = BatchProcessor(max_workers=1).process_batch([str(a), str(b)], wf, str(out), "{original}")
    outputs = {Path(item["output"]) for item in stats.results}

    assert stats.failed_files == 0
    assert len(outputs) == 1
    assert next(iter(outputs)).exists()
    assert next(iter(outputs)).parent == out.resolve()


def test_e2e_dry_run_no_write(tmp_path: Path):
    src = tmp_path / "a.png"
    out = tmp_path / "out"
    out.mkdir()
    _img(src)

    wf = Workflow("dry")
    wf.add_step("image_resize", {"width": 12, "height": 12, "maintain_aspect": False})

    before = list(out.iterdir())
    stats = BatchProcessor(max_workers=1).process_batch([str(src)], wf, str(out), "{original}", dry_run=True)
    after = list(out.iterdir())

    assert stats.failed_files == 0
    assert before == after


def test_e2e_output_traversal_attempt(tmp_path: Path):
    src = tmp_path / "a.png"
    out = tmp_path / "out"
    out.mkdir()
    _img(src)

    wf = Workflow("traversal")
    wf.add_step("file_rename", {"pattern": "..\\..\\escape"})

    stats = BatchProcessor(max_workers=1).process_batch([str(src)], wf, str(out), "{original}")
    assert stats.failed_files == 0
    assert all(str(tmp_path.resolve()) in r["output"] for r in stats.results)


def test_e2e_malformed_workflow_configs(tmp_path: Path):
    src = tmp_path / "a.png"
    out = tmp_path / "out"
    out.mkdir()
    _img(src)

    wf = Workflow("bad")
    wf.add_step("image_resize", {"width": "x", "height": 12})

    stats = BatchProcessor(max_workers=1).process_batch([str(src)], wf, str(out), "{original}")
    assert stats.failed_files >= 1


def test_e2e_ocr_dependency_absence(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ocr_ops, "HAS_TESSERACT", True)
    from types import SimpleNamespace
    from unittest.mock import Mock

    monkeypatch.setattr(ocr_ops, "pytesseract", SimpleNamespace(
        get_tesseract_version=Mock(side_effect=FileNotFoundError()),
        image_to_string=Mock(side_effect=AssertionError("real OCR")),
    ), raising=False)
    src = tmp_path / "a.png"
    out = tmp_path / "out"
    out.mkdir()
    _img(src)

    wf = Workflow("ocr")
    wf.add_step("ocr_image", {"language": "eng"})

    stats = BatchProcessor(max_workers=1).process_batch([str(src)], wf, str(out), "{original}")

    assert stats.failed_files >= 1
    assert "Tesseract executable is not available" in str(stats.errors)
    ocr_ops.pytesseract.image_to_string.assert_not_called()


def test_e2e_pause_blocks_new_submissions(tmp_path: Path, monkeypatch):
    files = []
    out = tmp_path / "out"
    out.mkdir()

    for i in range(12):
        path = tmp_path / f"{i}.png"
        _img(path)
        files.append(str(path))

    wf = Workflow("pause")
    wf.add_step("image_resize", {"width": 12, "height": 12, "maintain_aspect": False})

    original_execute = ImageResizeOperation.execute
    first_started = threading.Event()
    release_first = threading.Event()
    started_count = {"value": 0}

    def controlled_execute(self, file_path, output_path, dry_run=False):
        started_count["value"] += 1
        if started_count["value"] == 1:
            first_started.set()
            release_first.wait(timeout=5)
        return original_execute(self, file_path, output_path, dry_run)

    monkeypatch.setattr(ImageResizeOperation, "execute", controlled_execute)

    processor = BatchProcessor(max_workers=1)
    result = {}

    def run_batch():
        result["stats"] = processor.process_batch(files, wf, str(out), "{original}")

    worker = threading.Thread(target=run_batch)
    worker.start()

    assert first_started.wait(timeout=5)
    processor.pause()
    assert processor.is_paused is True
    release_first.set()
    time.sleep(0.3)
    assert started_count["value"] == 1

    processor.resume()
    worker.join(timeout=10)
    assert processor.is_paused is False
    assert result["stats"].failed_files == 0


def test_e2e_cancel_stops_future_submissions(tmp_path: Path, monkeypatch):
    files = []
    out = tmp_path / "out"
    out.mkdir()

    for i in range(12):
        path = tmp_path / f"{i}.png"
        _img(path)
        files.append(str(path))

    wf = Workflow("cancel")
    wf.add_step("image_resize", {"width": 12, "height": 12, "maintain_aspect": False})

    original_execute = ImageResizeOperation.execute
    first_started = threading.Event()
    release_first = threading.Event()
    started_count = {"value": 0}

    def controlled_execute(self, file_path, output_path, dry_run=False):
        started_count["value"] += 1
        if started_count["value"] == 1:
            first_started.set()
            release_first.wait(timeout=5)
        return original_execute(self, file_path, output_path, dry_run)

    monkeypatch.setattr(ImageResizeOperation, "execute", controlled_execute)

    processor = BatchProcessor(max_workers=1)
    result = {}

    def run_batch():
        result["stats"] = processor.process_batch(files, wf, str(out), "{original}")

    worker = threading.Thread(target=run_batch)
    worker.start()

    assert first_started.wait(timeout=5)
    processor.stop()
    release_first.set()
    worker.join(timeout=10)

    assert processor.is_running is False
    assert result["stats"].stopped is True
    assert started_count["value"] == 1
    assert result["stats"].processed_files < len(files)


def test_e2e_stop_after_final_output_does_not_reclassify_completed_run(tmp_path: Path):
    source = tmp_path / "source.png"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    _img(source)

    workflow = Workflow("completed-before-stop")
    workflow.add_step("image_resize", {"width": 12, "height": 12, "maintain_aspect": False})
    processor = BatchProcessor(max_workers=1)
    processor.set_progress_callback(
        lambda current, total, message: processor.stop()
        if current == total and message.startswith("Processed ")
        else None
    )

    stats = processor.process_batch([str(source)], workflow, str(output_dir), "{original}")

    assert stats.processed_files == stats.total_files == 1
    assert stats.failed_files == 0
    assert stats.stopped is False
    assert len(list(output_dir.glob("*.png"))) == 1


def test_e2e_stop_during_completed_future_set_does_not_reclassify_all_outputs(
    tmp_path: Path,
    monkeypatch,
):
    sources = [tmp_path / "first.png", tmp_path / "second.png"]
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    for source in sources:
        _img(source)

    workflow = Workflow("completed-future-set-before-stop")
    workflow.add_step("image_resize", {"width": 12, "height": 12, "maintain_aspect": False})
    processor = BatchProcessor(max_workers=2)
    processor.set_progress_callback(
        lambda current, total, message: processor.stop()
        if current == 1 and message.startswith("Processed ")
        else None
    )

    def return_all_completed(futures, **_kwargs):
        return wait_for_futures(futures, return_when=ALL_COMPLETED)

    monkeypatch.setattr(processor_module, "wait", return_all_completed)

    stats = processor.process_batch(list(map(str, sources)), workflow, str(output_dir), "{original}")

    assert stats.processed_files == stats.total_files == 2
    assert stats.failed_files == 0
    assert stats.stopped is False
    assert len(list(output_dir.glob("*.png"))) == 2
