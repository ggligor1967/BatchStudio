"""V11-07 UI consumption tests; environmental readiness is always mocked."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import threading

import pytest

from core import BatchProcessor, OperationRegistry, ProcessingStats, Workflow
from core.operations import ocr_ops, registry as registry_module
from core.operations.ocr_ops import OCRReadiness
from core.processor import validate_file_path
from ui import input_panel, run_panel
from ui.input_panel import InputPanel
from ui.input_support import get_input_error, get_picker_filetypes
from ui.run_panel import RunPanel
from ui.workflow_panel import WorkflowPanel


@pytest.fixture
def readiness(monkeypatch):
    states = {key: OCRReadiness() for key in ("image", "native_pdf", "pdf_ocr")}
    for key, function in [
        ("image", "get_image_ocr_readiness"),
        ("native_pdf", "get_pdf_native_readiness"),
        ("pdf_ocr", "get_pdf_ocr_readiness"),
    ]:
        probe = Mock(side_effect=lambda *args, key=key: states[key])
        monkeypatch.setattr(ocr_ops, function, probe)
        monkeypatch.setattr(registry_module, function, probe)
    return states


def workflow_for(operation_id, config=None):
    workflow = Workflow("eligibility")
    workflow.add_step(operation_id, config or {})
    return workflow


def patterns(workflow):
    filetypes, errors = get_picker_filetypes(workflow)
    return set(filetypes[0][1]) if filetypes else set()


V11_07_SELECTABLE_EXTENSIONS = (
    ".bmp",
    ".csv",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
)
V11_07_COMPATIBILITY_ONLY_EXTENSIONS = (
    ".json",
    ".txt",
    ".xls",
    ".xlsx",
    ".xml",
)


def test_run_panel_naming_hint_lists_every_supported_placeholder(monkeypatch):
    def widget_factory(*args, **kwargs):
        return Mock()

    label_factory = Mock(side_effect=widget_factory)
    for widget_name in (
        "Button",
        "Checkbutton",
        "Entry",
        "Frame",
        "LabelFrame",
        "Progressbar",
        "Scrollbar",
        "Spinbox",
    ):
        monkeypatch.setattr(run_panel.ttk, widget_name, widget_factory)
    monkeypatch.setattr(run_panel.ttk, "Label", label_factory)
    monkeypatch.setattr(run_panel.tk, "Text", widget_factory)
    for variable_name in ("BooleanVar", "IntVar", "StringVar"):
        monkeypatch.setattr(run_panel.tk, variable_name, widget_factory)

    RunPanel(Mock(), SimpleNamespace())

    hint = next(
        call.kwargs["text"]
        for call in label_factory.call_args_list
        if call.kwargs.get("text", "").startswith("Use:")
    )
    assert hint == "Use: {original}, {timestamp}, {counter}"


@pytest.mark.parametrize(
    "total,processed,failed,dry_run,celebrates",
    [
        (2, 2, 0, False, True),
        (2, 1, 1, False, False),
        (0, 0, 0, False, False),
        (2, 2, 0, True, False),
        (2, 1, 0, False, False),
    ],
    ids=("successful-real", "failed", "empty", "dry-run", "stopped-partial"),
)
def test_processing_completion_celebrates_only_fully_successful_real_runs(
    monkeypatch, total, processed, failed, dry_run, celebrates
):
    stats = ProcessingStats(dry_run=dry_run)
    stats.total_files = total
    stats.processed_files = processed
    stats.failed_files = failed
    panel = RunPanel.__new__(RunPanel)
    panel.processor = Mock()
    panel._log = Mock()
    panel._show_confetti = Mock()
    for widget_name in ("start_button", "pause_button", "stop_button", "status_label"):
        setattr(panel, widget_name, Mock())
    monkeypatch.setattr(run_panel.messagebox, "showinfo", Mock())

    panel._processing_complete(stats, "unused", generate_report=False)

    assert panel._show_confetti.called is celebrates


@pytest.mark.parametrize(
    "image,native,pdf_ocr,operation,config,extension,eligible",
    [
        (True, True, True, "ocr_image", {}, ".tif", True),
        (False, True, False, "ocr_image", {}, ".png", False),
        (True, True, False, "ocr_image", {}, ".png", True),
        (False, True, False, "ocr_pdf", {"mode": "native"}, ".pdf", True),
        (False, True, False, "ocr_pdf", {"mode": "auto"}, ".pdf", True),
        (True, True, False, "ocr_pdf", {"mode": "ocr"}, ".pdf", False),
        (True, True, True, "ocr_pdf", {"mode": "ocr"}, ".pdf", True),
        (True, False, False, "ocr_pdf", {"mode": "native"}, ".pdf", False),
        (False, True, False, "ocr_batch", {}, ".png", False),
        (False, True, False, "ocr_batch", {}, ".pdf", True),
        (True, True, False, "ocr_batch", {}, ".png", True),
        (True, True, False, "ocr_batch", {"mode": "ocr"}, ".pdf", False),
        (True, True, False, "ocr_batch", {"mode": "ocr"}, ".png", True),
        (False, True, False, "image_resize", {}, ".png", True),
        (False, True, False, "pdf_merge", {}, ".pdf", True),
    ],
)
def test_picker_and_selection_follow_backend(
    tmp_path, readiness, image, native, pdf_ocr, operation, config, extension, eligible
):
    for key, available in [("image", image), ("native_pdf", native), ("pdf_ocr", pdf_ocr)]:
        readiness[key] = OCRReadiness(None if available else key + " prerequisite unavailable")
    workflow = workflow_for(operation, config)
    source = tmp_path / ("input" + extension.upper())
    source.write_bytes(b"input")
    assert ("*" + extension in patterns(workflow)) is eligible
    error = get_input_error(source, workflow)
    assert (error is None) is eligible
    if not eligible:
        assert "prerequisite unavailable" in error


@pytest.mark.parametrize("extension", V11_07_SELECTABLE_EXTENSIONS)
def test_ui_admission_keeps_every_v11_07_input_format(tmp_path, readiness, extension):
    for key in readiness:
        readiness[key] = OCRReadiness("unavailable")
    source = tmp_path / ("input" + extension)
    source.write_bytes(b"input")
    assert "*" + extension in patterns(None)
    assert get_input_error(source, None) is None
    assert get_input_error(source, workflow_for("file_rename")) is None
    ocr_ops.get_image_ocr_readiness.assert_not_called()
    ocr_ops.get_pdf_ocr_readiness.assert_not_called()


@pytest.mark.parametrize("extension", V11_07_COMPATIBILITY_ONLY_EXTENSIONS)
def test_ui_admission_excludes_core_compatibility_only_formats(
    tmp_path, readiness, extension
):
    source = tmp_path / ("input" + extension)
    source.write_bytes(b"input")
    assert "*" + extension not in patterns(None)
    assert "not selectable" in get_input_error(source, None)
    assert "not selectable" in get_input_error(source, workflow_for("file_rename"))
    assert validate_file_path(str(source)) == (True, "")
    stats = BatchProcessor(max_workers=1).process_batch(
        [str(source)], workflow_for("file_rename"), str(tmp_path / "out")
    )
    assert stats.processed_files == 1
    assert stats.failed_files == 0
    assert Path(stats.results[0]["output"]).is_file()
    ocr_ops.get_image_ocr_readiness.assert_not_called()
    ocr_ops.get_pdf_ocr_readiness.assert_not_called()


@pytest.mark.parametrize(
    "operation,extension",
    [
        ("ocr_image", ".pdf"),
        ("ocr_pdf", ".png"),
        ("ocr_batch", ".txt"),
        ("ocr_batch", ".csv"),
        ("ocr_batch", ".xlsx"),
        ("ocr_image", ".exe"),
    ],
)
def test_unsupported_inputs_precede_ocr_checks(tmp_path, readiness, operation, extension):
    source = tmp_path / ("input" + extension)
    source.write_bytes(b"input")
    error = get_input_error(source, workflow_for(operation))
    assert any(
        reason in error for reason in ("Unsupported input", "not allowed", "not selectable")
    )
    ocr_ops.get_image_ocr_readiness.assert_not_called()
    ocr_ops.get_pdf_ocr_readiness.assert_not_called()


def test_pipeline_uses_transformed_type_and_applied_language(tmp_path, readiness):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    workflow = workflow_for("image_convert", {"format": "JPEG"})
    workflow.add_step("ocr_batch", {"language": "ron"})
    assert get_input_error(source, workflow) is None
    ocr_ops.get_image_ocr_readiness.assert_called_with("ron")
    ocr_ops.get_pdf_ocr_readiness.assert_not_called()
    readiness["image"] = OCRReadiness("Tesseract language 'ron' is not available")
    assert "language 'ron'" in get_input_error(source, workflow)
    assert patterns(workflow) == set()


def test_disabled_step_and_invalid_config(tmp_path, readiness):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    workflow = workflow_for("file_rename")
    step = workflow.add_step("ocr_image", {"grayscale": True})
    step.enabled = False
    assert get_input_error(source, workflow) is None
    step.enabled = True
    assert "unsupported OCR configuration" in get_input_error(source, workflow)
    ocr_ops.get_image_ocr_readiness.assert_not_called()


@pytest.fixture
def panel(monkeypatch):
    panel = InputPanel.__new__(InputPanel)
    panel.selected_files = []
    panel.main_window = SimpleNamespace(
        get_workflow=lambda: None, set_status=Mock(), set_files=Mock()
    )
    panel.frame = Mock()
    panel.file_listbox = Mock()
    panel._update_stats = Mock()
    panel._update_drop_zone_visibility = Mock()
    panel._load_input_support = lambda check, complete: complete(check())
    monkeypatch.setattr(input_panel.messagebox, "showwarning", Mock())
    return panel


@pytest.mark.parametrize("rejected_extension", V11_07_COMPATIBILITY_ONLY_EXTENSIONS)
@pytest.mark.parametrize("route", ["picker", "folder", "drop"])
def test_every_selection_route_rejects_unsupported_files(
    tmp_path, monkeypatch, panel, readiness, route, rejected_extension
):
    accepted = tmp_path / "input.tif"
    rejected = tmp_path / ("input" + rejected_extension)
    for source in (accepted, rejected):
        source.write_bytes(b"input")
    if route == "picker":
        dialog = Mock(return_value=[str(accepted), str(rejected)])
        monkeypatch.setattr(input_panel.filedialog, "askopenfilenames", dialog)
        panel._add_files()
        assert "*.tif" in dialog.call_args.kwargs["filetypes"][0][1]
        assert "*.*" not in dialog.call_args.kwargs["filetypes"][0][1]
    elif route == "folder":
        monkeypatch.setattr(input_panel.filedialog, "askdirectory", lambda **kwargs: str(tmp_path))
        panel._add_folder()
    else:
        panel._parse_drop_data = lambda data: [str(tmp_path)]
        assert panel._on_drop(SimpleNamespace(data="", action="copy")) == "copy"
    assert panel.selected_files == [str(accepted)]
    assert "not selectable" in input_panel.messagebox.showwarning.call_args.args[1]
    ocr_ops.get_image_ocr_readiness.assert_not_called()


def test_unavailable_picker_and_direct_selection_are_rejected(
    tmp_path, monkeypatch, panel, readiness
):
    panel.main_window.get_workflow = Mock(return_value=workflow_for("ocr_image"))
    readiness["image"] = OCRReadiness("Tesseract executable is not available")
    dialog = Mock()
    monkeypatch.setattr(input_panel.filedialog, "askopenfilenames", dialog)
    panel._add_files()
    dialog.assert_not_called()
    assert "Tesseract executable" in input_panel.messagebox.showwarning.call_args.args[1]
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    panel._accept_files([str(source)])
    assert panel.selected_files == []
    assert "Tesseract executable" in input_panel.messagebox.showwarning.call_args.args[1]


def test_selection_rechecks_capability_after_dialog(tmp_path, monkeypatch, panel, readiness):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    panel.main_window.get_workflow = Mock(return_value=workflow_for("ocr_image"))

    def select(**kwargs):
        readiness["image"] = OCRReadiness("Tesseract executable is not available")
        return [str(source)]

    monkeypatch.setattr(input_panel.filedialog, "askopenfilenames", select)
    panel._add_files()
    assert panel.selected_files == []
    assert "Tesseract executable" in input_panel.messagebox.showwarning.call_args.args[1]


def test_selection_success_and_missing_path(tmp_path, panel, readiness):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    panel.main_window.get_workflow = Mock(return_value=workflow_for("ocr_image"))
    panel._accept_files([str(source)])
    assert panel.selected_files == [str(source)]
    input_panel.messagebox.showwarning.assert_not_called()
    panel._accept_files([str(tmp_path / "missing.png")])
    assert "File does not exist" in input_panel.messagebox.showwarning.call_args.args[1]


def test_changed_workflow_does_not_accept_stale_selection(tmp_path, panel, readiness):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    workflow = workflow_for("ocr_image")
    panel.main_window.get_workflow = lambda: workflow

    def defer(check, complete):
        result = check()
        workflow.steps[0].config["language"] = "ron"
        complete(result)

    panel._load_input_support = defer
    panel._accept_files([str(source)])
    assert not panel.selected_files
    assert "Workflow changed" in input_panel.messagebox.showwarning.call_args.args[1]


@pytest.mark.parametrize(
    "failure,stale,destroyed",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
    ],
)
def test_selection_worker_keeps_probes_off_tk(monkeypatch, panel, failure, stale, destroyed):
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    main_thread = threading.current_thread()
    callbacks = []
    panel.frame.after.side_effect = lambda delay, callback: callbacks.append(callback)
    panel.frame.winfo_exists.return_value = True
    complete = Mock()
    workers = []
    real_thread = threading.Thread

    def start_worker(**kwargs):
        worker = real_thread(**kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(input_panel.threading, "Thread", start_worker)

    def check():
        assert threading.current_thread() is not main_thread
        entered.set()
        try:
            assert release.wait(5)
            if failure:
                raise RuntimeError("probe failed")
            return "ready"
        finally:
            done.set()

    InputPanel._load_input_support(panel, check, complete)
    try:
        assert entered.wait(5)
        callbacks.pop(0)()
        complete.assert_not_called()
    finally:
        release.set()
    assert done.wait(5)
    workers[0].join(timeout=5)
    assert not workers[0].is_alive()
    if stale:
        panel._selection_token = object()
    if destroyed:
        panel.frame.winfo_exists.return_value = False
    callbacks.pop(0)()
    if stale or destroyed:
        complete.assert_not_called()
        input_panel.messagebox.showwarning.assert_not_called()
    elif failure:
        complete.assert_not_called()
        assert "check failed" in input_panel.messagebox.showwarning.call_args.args[1]
    else:
        complete.assert_called_once_with("ready")


@pytest.mark.parametrize(
    "operation,extension,config,available",
    [
        ("ocr_image", ".png", {}, True),
        ("ocr_image", ".png", {}, False),
        ("ocr_batch", ".png", {}, False),
        ("ocr_batch", ".csv", {}, False),
        ("ocr_pdf", ".pdf", {"mode": "native"}, False),
        ("ocr_pdf", ".pdf", {"mode": "auto"}, False),
        ("ocr_pdf", ".pdf", {"mode": "ocr"}, False),
        ("ocr_pdf", ".pdf", {"mode": "ocr"}, True),
    ],
)
def test_run_boundary_never_enters_unavailable_processing(
    tmp_path, monkeypatch, readiness, operation, extension, config, available
):
    source = tmp_path / ("input" + extension)
    source.write_bytes(b"input")
    readiness["image"] = readiness["pdf_ocr"] = OCRReadiness(
        None if available else "runtime prerequisite unavailable"
    )
    panel = RunPanel.__new__(RunPanel)
    panel.processor = Mock()
    panel.frame = Mock()
    panel._processing_error = Mock()
    panel._processing_started = Mock()
    panel._processing_complete = Mock()
    panel._run_batch(
        [str(source)],
        workflow_for(operation, config),
        str(tmp_path / "out"),
        "{original}",
        False,
        False,
    )
    for call in panel.frame.after.call_args_list:
        _, callback, *args = call.args
        callback(*args)
    eligible = available or (operation == "ocr_pdf" and config["mode"] in {"native", "auto"})
    assert panel.processor.process_batch.called is eligible
    assert panel._processing_started.called is eligible
    assert panel._processing_error.called is not eligible
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("extension", V11_07_COMPATIBILITY_ONLY_EXTENSIONS)
def test_run_preflight_rejects_core_compatibility_only_inputs(tmp_path, extension):
    source = tmp_path / ("input" + extension)
    source.write_bytes(b"input")
    panel = RunPanel.__new__(RunPanel)
    panel.processor = Mock()
    panel.frame = Mock()
    panel._processing_error = Mock()
    panel._processing_started = Mock()
    panel._processing_complete = Mock()

    panel._run_batch(
        [str(source)],
        workflow_for("file_rename"),
        str(tmp_path / "out"),
        "{original}",
        False,
        False,
    )
    for call in panel.frame.after.call_args_list:
        _, callback, *args = call.args
        callback(*args)

    panel.processor.process_batch.assert_not_called()
    panel._processing_started.assert_not_called()
    assert "not selectable" in panel._processing_error.call_args.args[0]
    assert not (tmp_path / "out").exists()


def test_visible_pdf_status_preserves_native_and_fallback_distinction(readiness):
    readiness["pdf_ocr"] = OCRReadiness("Poppler PDF rasterizer is not available")
    panel = WorkflowPanel.__new__(WorkflowPanel)
    panel.operation_registry = OperationRegistry()
    panel.templates_listbox = Mock()
    panel.operations_listbox = Mock()
    panel.operations_listbox.curselection.return_value = ()
    panel._load_capability_status = lambda op, config, display: display(
        panel.operation_registry.get_capability_status(op, config)
    )
    panel._load_operations()
    rows = [call.args[1] for call in panel.operations_listbox.insert.call_args_list]
    assert any(
        "Native PDF: ready" in row and "PDF OCR fallback (eng): Poppler" in row for row in rows
    )
    assert any("Image OCR (eng): ready" in row for row in rows)


def test_run_controls_show_checking_then_processing_or_refusal(tmp_path, monkeypatch, readiness):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    workflow = workflow_for("ocr_image")
    panel = RunPanel.__new__(RunPanel)
    panel.main_window = SimpleNamespace(
        get_files=lambda: [str(source)], get_workflow=lambda: workflow
    )
    for name, value in [
        ("output_dir", str(tmp_path / "out")),
        ("naming_pattern", "{original}"),
        ("workers_var", 1),
        ("dry_run_var", False),
        ("generate_report_var", False),
    ]:
        setattr(panel, name, SimpleNamespace(get=lambda value=value: value))
    for name in ("log_text", "start_button", "pause_button", "stop_button", "status_label"):
        setattr(panel, name, Mock())
    panel._log = Mock()
    panel._update_progress = Mock()
    worker = Mock()
    monkeypatch.setattr(threading, "Thread", worker)
    monkeypatch.setattr(input_panel.messagebox, "showerror", Mock())
    panel._start_processing()
    worker.return_value.start.assert_called_once()
    for button in (panel.start_button, panel.pause_button, panel.stop_button):
        button.config.assert_called_with(state="disabled")
    assert "Checking" in panel.status_label.config.call_args.kwargs["text"]
    panel._processing_started()
    for button in (panel.pause_button, panel.stop_button):
        button.config.assert_called_with(state="normal")
    panel._processing_error("Tesseract executable is not available")
    panel.start_button.config.assert_called_with(state="normal")
    for button in (panel.pause_button, panel.stop_button):
        button.config.assert_called_with(state="disabled")
    assert "Tesseract executable" in input_panel.messagebox.showerror.call_args.args[1]


@pytest.mark.parametrize("route", ["files", "folder", "drop"])
def test_selection_enumeration_and_validation_only_run_in_worker(
    tmp_path, monkeypatch, panel, readiness, route
):
    from ui import input_support

    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    ui_thread = threading.current_thread()
    callbacks, workers = [], []
    real_thread = threading.Thread
    original_validate = input_support.validate_file_path
    original_walk = input_panel.os.walk
    validations = []
    enumerations = []

    def validate(path):
        assert threading.current_thread() is not ui_thread
        validations.append(path)
        return original_validate(path)

    def walk(folder):
        assert threading.current_thread() is not ui_thread
        enumerations.append(folder)
        yield from original_walk(folder)

    def files():
        assert threading.current_thread() is not ui_thread
        enumerations.append("files")
        yield str(source)
        yield str(source)

    def worker(**kwargs):
        thread = real_thread(**kwargs)
        workers.append(thread)
        return thread

    monkeypatch.setattr(input_support, "validate_file_path", validate)
    monkeypatch.setattr(input_panel.os, "walk", walk)
    monkeypatch.setattr(threading, "Thread", worker)
    panel._load_input_support = lambda check, complete: InputPanel._load_input_support(
        panel, check, complete
    )
    panel.frame.after.side_effect = lambda delay, callback: callbacks.append(callback)
    panel.frame.winfo_exists.return_value = True
    if route == "files":
        panel._accept_files(files())
    elif route == "folder":
        monkeypatch.setattr(input_panel.filedialog, "askdirectory", lambda **kwargs: str(tmp_path))
        panel._add_folder()
    else:
        panel._parse_drop_data = lambda data: [str(tmp_path)]
        panel._on_drop(SimpleNamespace(data="", action="copy"))
    workers[0].join(timeout=5)
    assert not workers[0].is_alive()
    assert not panel.selected_files
    callbacks.pop(0)()
    assert len(enumerations) == 1
    assert validations == [str(source)] * (2 if route == "files" else 1)
    assert panel.selected_files == [str(source)]
    panel.file_listbox.insert.assert_called_once_with("end", source.name)
    input_panel.messagebox.showwarning.assert_not_called()


@pytest.mark.parametrize("invalid", ["blank_name", "empty", "operation_id", "config"])
def test_invalid_workflow_preflight_never_prepares_output(
    tmp_path, monkeypatch, readiness, invalid
):
    from core import BatchProcessor
    from core import processor

    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    workflow = workflow_for("ocr_image")
    if invalid == "blank_name":
        workflow.name = "   "
    elif invalid == "empty":
        workflow.steps.clear()
    elif invalid == "operation_id":
        workflow.steps[0].operation_id = ""
    else:
        workflow.steps[0].config = []
    valid, error = workflow.validate()
    assert not valid
    panel = RunPanel.__new__(RunPanel)
    panel.processor = BatchProcessor()
    panel.processor.process_batch = Mock(wraps=panel.processor.process_batch)
    panel.frame = Mock()
    panel._processing_error = Mock()
    prepare = Mock(side_effect=AssertionError("Output preparation reached"))
    monkeypatch.setattr(processor, "validate_output_directory", prepare)
    panel._run_batch([str(source)], workflow, str(tmp_path / "out"), "{original}", False, False)
    panel.processor.process_batch.assert_not_called()
    prepare.assert_not_called()
    for call in panel.frame.after.call_args_list:
        _, callback, *args = call.args
        callback(*args)
    panel._processing_error.assert_called_once_with(f"Invalid workflow: {error}")
    assert not (tmp_path / "out").exists()
    ocr_ops.get_image_ocr_readiness.assert_not_called()


@pytest.mark.parametrize(
    "operation,extensions,config,probe,key",
    [
        ("ocr_image", [".png", ".jpg", ".tif"], {}, "get_image_ocr_readiness", "image"),
        ("ocr_pdf", [".pdf", ".PDF", ".pdf"], {"mode": "ocr"}, "get_pdf_ocr_readiness", "pdf_ocr"),
        ("ocr_batch", [".png", ".jpg", ".tif"], {}, "get_image_ocr_readiness", "image"),
        (
            "ocr_batch",
            [".pdf", ".PDF", ".pdf"],
            {"mode": "ocr"},
            "get_pdf_ocr_readiness",
            "pdf_ocr",
        ),
    ],
)
@pytest.mark.parametrize("route", ["selection", "start"])
def test_equivalent_inputs_reuse_readiness_only_within_one_pass(
    tmp_path, panel, readiness, operation, extensions, config, probe, key, route
):
    files = []
    for index, extension in enumerate(extensions):
        source = tmp_path / (str(index) + extension)
        source.write_bytes(b"input")
        files.append(str(source))
    workflow = workflow_for(operation, config)
    if route == "selection":
        panel.main_window.get_workflow = lambda: workflow
        run = lambda: panel._accept_files(files)
    else:
        panel = RunPanel.__new__(RunPanel)
        panel.processor = Mock()
        panel.frame = Mock()
        run = lambda: panel._run_batch(
            files, workflow, str(tmp_path / "out"), "{original}", False, False
        )
    run()
    getattr(ocr_ops, probe).assert_called_once()
    readiness[key] = OCRReadiness("prerequisite removed between passes")
    run()
    assert getattr(ocr_ops, probe).call_count == 2
    if route == "selection":
        assert "prerequisite removed" in input_panel.messagebox.showwarning.call_args.args[1]
        assert panel.selected_files == files
    else:
        panel.processor.process_batch.assert_called_once()
        assert "prerequisite removed" in panel.frame.after.call_args.args[-1]


def test_pass_cache_keeps_concrete_delegate_and_configuration_distinct(readiness):
    from pathlib import Path
    from ui.input_support import InputCapabilityRegistry

    registry = InputCapabilityRegistry()
    for language in ("eng", "ron"):
        batch = registry.get_operation("ocr_batch", {"mode": "ocr", "language": language})
        assert batch.get_capability_error(Path("image.png")) is None
        assert batch.get_capability_error(Path("image.tif")) is None
        assert batch.get_capability_error(Path("scan.pdf")) is None
        assert batch.get_capability_error(Path("scan.PDF")) is None
    assert ocr_ops.get_image_ocr_readiness.call_count == 2
    assert ocr_ops.get_pdf_ocr_readiness.call_count == 2
    native = registry.get_operation("ocr_pdf", {"mode": "native", "language": "eng"})
    assert native.get_capability_error() is None
    ocr_ops.get_pdf_native_readiness.assert_called_once()
    direct = registry.get_operation("ocr_image", {"mode": "ocr", "language": "eng"})
    assert direct.get_capability_error() is None
    assert ocr_ops.get_image_ocr_readiness.call_count == 2
