"""V11-04: intercept attempted application writes, including UI report routes."""

import builtins
import io
import os
from pathlib import Path
import shutil
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from pypdf import PdfWriter

from core.operations import OperationRegistry
from core.operations import data_ops, file_ops, image_ops, ocr_ops, pdf_ops
from core.operations.base import Operation
from core.processor import BatchProcessor, ProcessingStats, process_single_file, validate_output_directory
from core import security
from core.workflow import Workflow
from ui.logs_panel import LogsPanel
from ui.run_panel import RunPanel
from ui import logs_panel, run_panel


WRITERS = [
    ("file_rename", {}, ".txt"),
    ("image_resize", {}, ".png"),
    ("image_convert", {"format": "JPEG"}, ".png"),
    ("image_filter", {}, ".png"),
    ("csv_filter", {"column": "status", "value": "active"}, ".csv"),
    ("pdf_watermark", {}, ".pdf"),
    ("ocr_image", {}, ".png"),
    ("ocr_pdf", {"mode": "ocr"}, ".pdf"),
    ("ocr_batch", {}, ".png"),
    ("ocr_batch", {}, ".pdf"),
    ("pdf_merge", {}, ".pdf"),
]


def make_source(path):
    if path.suffix == ".png":
        Image.new("RGB", (16, 16), "blue").save(path)
    elif path.suffix == ".pdf":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with path.open("wb") as stream:
            writer.write(stream)
    elif path.suffix == ".csv":
        path.write_text("status,value\nactive,1\ninactive,2\n", encoding="utf-8")
    else:
        path.write_text("original", encoding="utf-8")
    return path


def filesystem_snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
            for path in root.rglob("*")}


@pytest.fixture
def forbid_output_writes(monkeypatch):
    def install(root):
        root = root.resolve()
        attempts = []

        def in_output(path):
            return isinstance(path, (str, bytes, os.PathLike)) and Path(os.fsdecode(path)).resolve().is_relative_to(root)

        def reject(name):
            attempts.append(name)
            raise AssertionError(f"Attempted application write: {name}")

        def intercept_path(function, name, position=0):
            def guarded(*args, **kwargs):
                if in_output(args[position]):
                    reject(name)
                return function(*args, **kwargs)
            return guarded

        for owner, name in [(Path, "mkdir"), (os, "mkdir"), (Path, "unlink"), (os, "unlink"),
                            (os, "remove"), (Path, "write_text"), (Path, "write_bytes")]:
            monkeypatch.setattr(owner, name, intercept_path(getattr(owner, name), name))

        for owner, name in [(builtins, "open"), (io, "open"), (Path, "open")]:
            original = getattr(owner, name)

            def guarded_open(file, mode="r", *args, _original=original, **kwargs):
                if any(flag in mode for flag in "wxa+") and in_output(file):
                    reject("open:" + mode)
                return _original(file, mode, *args, **kwargs)

            monkeypatch.setattr(owner, name, guarded_open)

        original_os_open = os.open

        def guarded_os_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) and in_output(path):
                reject("os.open")
            return original_os_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(os, "open", guarded_os_open)
        for name in ("NamedTemporaryFile", "TemporaryFile", "mkstemp", "mkdtemp"):
            original = getattr(tempfile, name)

            def guarded_temp(*args, _original=original, **kwargs):
                # BatchStudio supplies dir by keyword; os.open/mkdir also cover positional destinations.
                if kwargs.get("dir") is not None and in_output(kwargs["dir"]):
                    reject("tempfile")
                return _original(*args, **kwargs)

            monkeypatch.setattr(tempfile, name, guarded_temp)

        for module in (security, data_ops, file_ops, image_ops, ocr_ops, pdf_ops):
            monkeypatch.setattr(module, "exclusive_output", intercept_path(module.exclusive_output, "exclusive_output"))
        for owner, name in [(os, "rename"), (os, "replace"), (Path, "rename"), (Path, "replace"),
                            (shutil, "copy"), (shutil, "copy2"), (shutil, "copyfile"),
                            (shutil, "copystat"), (shutil, "move")]:
            original = getattr(owner, name)

            def guarded_move(source, destination, *args, _original=original, _name=name, **kwargs):
                if in_output(source) or in_output(destination):
                    reject(_name)
                return _original(source, destination, *args, **kwargs)

            monkeypatch.setattr(owner, name, guarded_move)

        original_copyfileobj = shutil.copyfileobj

        def guarded_copyfileobj(source, destination, *args, **kwargs):
            if in_output(getattr(destination, "name", None)):
                reject("copyfileobj")
            return original_copyfileobj(source, destination, *args, **kwargs)

        monkeypatch.setattr(shutil, "copyfileobj", guarded_copyfileobj)
        for name in ("_generate_html_report", "_generate_csv_report"):
            original = getattr(BatchProcessor, name)

            def guarded_report(self, stats, output_path, _original=original):
                if in_output(output_path):
                    reject("report writer")
                return _original(self, stats, output_path)

            monkeypatch.setattr(BatchProcessor, name, guarded_report)
        original_pdf_write = PdfWriter.write

        def guarded_pdf_write(self, stream):
            if in_output(getattr(stream, "name", stream)):
                reject("aggregate/PDF final write")
            return original_pdf_write(self, stream)

        monkeypatch.setattr(PdfWriter, "write", guarded_pdf_write)
        return attempts

    return install


@pytest.mark.parametrize("operation_id,config,suffix", WRITERS)
@pytest.mark.parametrize("existing_output", [False, True])
def test_registered_dry_run_paths_attempt_no_writes(
    tmp_path, monkeypatch, forbid_output_writes, operation_id, config, suffix, existing_output
):
    source = make_source(tmp_path / ("input" + suffix))
    out = tmp_path / "out"
    if existing_output:
        out.mkdir()
        (out / "prior.txt").write_bytes(b"preserve")
    monkeypatch.setattr(ocr_ops, "HAS_TESSERACT_BINARY", True)
    monkeypatch.setattr(ocr_ops, "HAS_PDF2IMAGE", True)
    # Optional imports may be absent in minimal installations.
    monkeypatch.delattr(ocr_ops, "pytesseract", raising=False)
    monkeypatch.delattr(ocr_ops, "convert_from_path", raising=False)
    monkeypatch.setattr(
        ocr_ops, "pytesseract",
        SimpleNamespace(image_to_string=Mock(side_effect=AssertionError("real OCR"))),
        raising=False,
    )
    monkeypatch.setattr(
        ocr_ops, "convert_from_path", Mock(side_effect=AssertionError("rasterization")), raising=False,
    )
    workflow = Workflow("registered dry run")
    workflow.add_step(operation_id, config)
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(out)
    messages = []
    processor = BatchProcessor(1)
    processor.set_progress_callback(lambda current, total, message: messages.append(message))

    stats = processor.process_batch([str(source)], workflow, str(out), dry_run=True)

    assert attempts == []
    assert filesystem_snapshot(tmp_path) == before
    assert out.exists() is existing_output
    assert stats.failed_files == 0 and stats.processed_files == 1
    assert stats.dry_run is True and stats.to_dict()["dry_run"] is True
    assert any("writ" in message.lower() and "not" in message.lower() for message in messages)
    if operation_id == "pdf_merge":
        assert not stats.results[0]["output"]
        assert stats.results[0]["result"]["planned_output"].endswith(".pdf")


@pytest.mark.parametrize("operation_id", ["file_rename", "pdf_merge"])
def test_empty_dry_run_creates_no_directory(tmp_path, forbid_output_writes, operation_id):
    out = tmp_path / "missing" / "out"
    workflow = Workflow("empty")
    workflow.add_step(operation_id)
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(tmp_path / "missing")
    stats = BatchProcessor(1).process_batch([], workflow, str(out), dry_run=True)
    assert attempts == [] and filesystem_snapshot(tmp_path) == before
    assert not out.exists() and stats.dry_run
    assert stats.failed_files == (1 if operation_id == "pdf_merge" else 0)


def test_multistep_dry_run_never_creates_intermediates(tmp_path, forbid_output_writes):
    source = make_source(tmp_path / "input.png")
    workflow = Workflow("chain")
    workflow.add_step("image_convert", {"format": "JPEG"})
    workflow.add_step("file_rename")
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(tmp_path / "out")
    stats = BatchProcessor(1).process_batch([str(source)], workflow, str(tmp_path / "out"), dry_run=True)
    assert attempts == [] and filesystem_snapshot(tmp_path) == before
    # No fabricated intermediate exists for the next validator to read.
    assert stats.failed_files == 1 and "cannot process" in stats.errors[0]["error"]


@pytest.mark.parametrize("suffix", ["", "/child"])
def test_readonly_validation_rejects_file_as_directory(tmp_path, forbid_output_writes, suffix):
    occupied = tmp_path / "occupied"
    occupied.write_bytes(b"preserve")
    attempts = forbid_output_writes(occupied)
    valid, error = validate_output_directory(str(occupied) + suffix, dry_run=True)
    assert not valid and error
    assert attempts == [] and occupied.read_bytes() == b"preserve"


def test_normal_validation_still_creates_and_removes_owned_probe(tmp_path, monkeypatch):
    out = tmp_path / "new"
    original = tempfile.NamedTemporaryFile
    probes = []

    def observe_probe(*args, **kwargs):
        probe = original(*args, **kwargs)
        probes.append(Path(probe.name))
        assert probes[-1].is_file()
        return probe

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", observe_probe)
    assert validate_output_directory(str(out)) == (True, "")
    assert len(probes) == 1 and out.is_dir() and not list(out.iterdir())


def test_unsupported_per_file_dry_run_never_calls_execute(tmp_path, monkeypatch, forbid_output_writes):
    calls = []

    class Unsupported(Operation):
        supports_dry_run = False

        def validate(self, file_path):
            return True

        def execute(self, *args, **kwargs):
            calls.append("execute")
            raise AssertionError("Unsupported execute reached")

        def _execute(self, *args, **kwargs):
            raise AssertionError("Unsupported writer reached")

    source = make_source(tmp_path / "input.txt")
    registry = OperationRegistry()
    registry.operations["unsupported"] = Unsupported
    monkeypatch.setattr("core.processor.OperationRegistry", lambda: registry)
    workflow = Workflow("unsupported")
    workflow.add_step("unsupported")
    attempts = forbid_output_writes(tmp_path / "out")
    result = process_single_file(str(source), workflow.to_dict(), str(tmp_path / "out"), "planned", dry_run=True)
    assert calls == [] and attempts == []
    assert not result["success"] and "dry run" in result["error"].lower()


def test_unsupported_aggregate_dry_run_never_begins(tmp_path, monkeypatch, forbid_output_writes):
    source = make_source(tmp_path / "input.pdf")
    begin = Mock(side_effect=AssertionError("Unsupported begin reached"))
    monkeypatch.setattr(pdf_ops.PDFAggregateMergeOperation, "supports_dry_run", False, raising=False)
    monkeypatch.setattr(pdf_ops.PDFAggregateMergeOperation, "begin", begin)
    workflow = Workflow("unsupported merge")
    workflow.add_step("pdf_merge")
    attempts = forbid_output_writes(tmp_path / "out")
    stats = BatchProcessor(1).process_batch([str(source)], workflow, str(tmp_path / "out"), dry_run=True)
    begin.assert_not_called()
    assert attempts == [] and stats.failed_files == 1
    assert "dry run" in stats.errors[0]["error"].lower()


@pytest.mark.parametrize("dry_run", [False, True])
def test_run_provenance_is_readonly_and_survives_processor_reuse(tmp_path, dry_run):
    workflow = Workflow("identity")
    workflow.add_step("file_rename")
    processor = BatchProcessor(1)
    stats = processor.process_batch([], workflow, str(tmp_path / "out"), dry_run=dry_run)
    processor.process_batch([], workflow, str(tmp_path / "other"), dry_run=not dry_run)
    assert stats.dry_run is dry_run and stats.to_dict()["dry_run"] is dry_run
    with pytest.raises(AttributeError):
        stats.dry_run = not dry_run


@pytest.mark.parametrize("format", ["csv", "html"])
@pytest.mark.parametrize("existing", [False, True])
def test_direct_report_rejects_dry_run_without_touching_destination(tmp_path, forbid_output_writes, format, existing):
    target = tmp_path / ("report." + format)
    if existing:
        target.write_bytes(b"prior report")
    stats = ProcessingStats(dry_run=True)
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(tmp_path)
    assert BatchProcessor().generate_report(stats, str(target), format) is False
    assert attempts == [] and filesystem_snapshot(tmp_path) == before


@pytest.mark.parametrize("route", ["_export_csv", "_view_html_report"])
@pytest.mark.parametrize("existing", [False, True])
def test_manual_dry_run_reports_do_not_write_or_open_stale_html(tmp_path, monkeypatch, forbid_output_writes, route, existing):
    if existing:
        (tmp_path / "report.html").write_bytes(b"old HTML")
    panel = LogsPanel.__new__(LogsPanel)
    panel.current_stats = ProcessingStats(dry_run=True)
    panel.main_window = SimpleNamespace(
        processor=Mock(), set_status=Mock(),
        run_panel=SimpleNamespace(output_dir=SimpleNamespace(get=lambda: str(tmp_path))),
    )
    dialog = Mock(return_value=str(tmp_path / "report.csv"))
    browser = Mock()
    monkeypatch.setattr(logs_panel.filedialog, "asksaveasfilename", dialog)
    monkeypatch.setattr(logs_panel.webbrowser, "open", browser)
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(tmp_path)
    getattr(panel, route)()
    panel.main_window.processor.generate_report.assert_not_called()
    browser.assert_not_called()
    dialog.assert_not_called()
    panel.main_window.set_status.assert_called_once_with("Reports are unavailable for dry-run results.")
    assert attempts == [] and filesystem_snapshot(tmp_path) == before


class MainThreadVariable:
    def __init__(self, value):
        self.value = value

    def get(self):
        assert threading.current_thread() is threading.main_thread(), "Tk variable read by worker"
        return self.value


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("report_intent", [False, True])
def test_run_panel_snapshots_options_and_reports_from_provenance(
    tmp_path, monkeypatch, forbid_output_writes, dry_run, report_intent
):
    source = make_source(tmp_path / "input.txt")
    workflow = Workflow("snapshot")
    workflow.add_step("file_rename", {"pattern": "original"})
    panel = RunPanel.__new__(RunPanel)
    panel.main_window = SimpleNamespace(get_files=lambda: [str(source)], get_workflow=lambda: workflow)
    out = tmp_path / "out"
    panel.output_dir = MainThreadVariable(str(out))
    panel.naming_pattern = MainThreadVariable("initial-pattern")
    panel.dry_run_var = MainThreadVariable(dry_run)
    panel.workers_var = MainThreadVariable(1)
    panel.generate_report_var = MainThreadVariable(report_intent)
    panel.current_stats = None
    for name in ("log_text", "start_button", "pause_button", "stop_button", "status_label", "frame"):
        setattr(panel, name, Mock())
    panel._log = Mock()
    panel._update_progress = Mock()
    panel._show_confetti = Mock()
    monkeypatch.setattr(run_panel.messagebox, "showinfo", Mock())
    real_thread = threading.Thread
    pending = []

    def defer_thread(*, target, args):
        pending.append((target, args))
        return SimpleNamespace(start=lambda: None, daemon=False)

    monkeypatch.setattr(run_panel.threading, "Thread", defer_thread)
    attempts = forbid_output_writes(tmp_path) if dry_run else []
    panel._start_processing()
    monkeypatch.setattr(run_panel.threading, "Thread", real_thread)
    assert panel.processor.max_workers == 1
    panel.dry_run_var.value = not dry_run
    panel.naming_pattern.value = "changed-pattern"
    panel.output_dir.value = str(tmp_path / "changed-output")
    panel.generate_report_var.value = not report_intent
    panel.workers_var.value = 8
    workflow.steps[0].config["pattern"] = "changed-name"
    original_process = panel.processor.process_batch
    calls = []

    def record_process(*args, **kwargs):
        calls.append((args, kwargs))
        return original_process(*args, **kwargs)

    panel.processor.process_batch = record_process
    panel.processor.generate_report = Mock(wraps=panel.processor.generate_report)
    target, args = pending.pop()
    worker = real_thread(target=target, args=args)
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert calls[0][1] == {"naming_pattern": "initial-pattern", "dry_run": dry_run}
    assert calls[0][0][2] == str(out)
    assert calls[0][0][1].steps[0].config["pattern"] == "original"
    # Execute the queued completion on the Tk thread, after widget values changed.
    for call in panel.frame.after.call_args_list:
        _, callback, *callback_args = call.args
        callback(*callback_args)
    assert attempts == []
    assert panel.current_stats.dry_run is dry_run
    assert panel.current_stats.failed_files == 0
    if report_intent and not dry_run:
        panel.processor.generate_report.assert_called_once_with(panel.current_stats, str(out / "report.html"), format="html")
        assert (out / "report.html").is_file()
    else:
        panel.processor.generate_report.assert_not_called()
        assert not (out / "report.html").exists()
    assert not (tmp_path / "changed-output").exists()
    if dry_run:
        assert not out.exists()


@pytest.mark.parametrize("route", ["_export_csv", "_view_html_report"])
def test_manual_normal_reports_still_generate(tmp_path, monkeypatch, route):
    panel = LogsPanel.__new__(LogsPanel)
    panel.current_stats = ProcessingStats()
    panel.main_window = SimpleNamespace(
        processor=BatchProcessor(), set_status=Mock(),
        run_panel=SimpleNamespace(output_dir=SimpleNamespace(get=lambda: str(tmp_path))),
    )
    monkeypatch.setattr(logs_panel.filedialog, "asksaveasfilename", lambda **kwargs: str(tmp_path / "report.csv"))
    browser = Mock()
    monkeypatch.setattr(logs_panel.webbrowser, "open", browser)
    getattr(panel, route)()
    if route == "_export_csv":
        assert (tmp_path / "report.csv").read_text().startswith("File,Status,Details,Timestamp")
        browser.assert_not_called()
    else:
        assert (tmp_path / "report.html").read_text().startswith("<!DOCTYPE html>")
        browser.assert_called_once()


@pytest.mark.parametrize("primitive", ["mkdir", "open", "tempfile", "exclusive_output", "copy", "pdf", "report"])
def test_write_interceptor_detects_attempts_before_files_exist(tmp_path, forbid_output_writes, primitive):
    source = make_source(tmp_path / "input.txt")
    out = tmp_path / "out"
    out.mkdir()
    target = out / "output.txt"
    writer = PdfWriter()
    attempts = forbid_output_writes(out)
    operations = {
        "mkdir": lambda: (out / "child").mkdir(),
        "open": lambda: target.open("wb"),
        "tempfile": lambda: tempfile.NamedTemporaryFile(dir=out),
        "exclusive_output": lambda: security.exclusive_output(target),
        "copy": lambda: shutil.copyfile(source, target),
        "pdf": lambda: writer.write(str(target)),
        "report": lambda: BatchProcessor()._generate_html_report(ProcessingStats(), str(target)),
    }
    with pytest.raises(AssertionError, match="Attempted application write"):
        operations[primitive]()
    assert len(attempts) == 1
    assert not list(out.iterdir())
