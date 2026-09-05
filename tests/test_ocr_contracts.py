"""V11-05 capability/configuration truth; all recognition and tools are mocked."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from core.operations import OperationRegistry, ocr_ops
from core.processor import compile_workflow, process_single_file
from core.workflow import Workflow, WorkflowTemplates


LEGACY = {
    "ocr_image": {"page_segmentation_mode": 3, "grayscale": True,
                  "threshold": False, "threshold_value": 140},
    "ocr_pdf": {"page_segmentation_mode": 3, "grayscale": True,
                "threshold": False, "threshold_value": 140},
    "ocr_batch": {"combine_output": False, "combined_filename": "all.txt"},
}


@pytest.fixture
def tools_ready(monkeypatch):
    adapter = SimpleNamespace(
        get_tesseract_version=Mock(return_value="5.0"),
        get_languages=Mock(return_value=["eng", "ron"]),
        image_to_string=Mock(return_value="mock recognition"),
    )
    monkeypatch.setattr(ocr_ops, "HAS_TESSERACT", True)
    monkeypatch.setattr(ocr_ops, "HAS_PDF2IMAGE", True)
    monkeypatch.setattr(ocr_ops, "pytesseract", adapter, raising=False)
    monkeypatch.setattr(ocr_ops, "convert_from_path", Mock(return_value=[object()]), raising=False)
    # Patch stdlib boundaries so tests also run against the admitted implementation.
    monkeypatch.setattr("shutil.which", lambda name: str(Path("tools") / name))
    monkeypatch.setattr("subprocess.run", Mock(return_value=SimpleNamespace(returncode=0)))
    return adapter


def compile_operation(operation_id, config):
    workflow = Workflow("OCR contract")
    workflow.add_step(operation_id, config)
    return compile_workflow(workflow, OperationRegistry())


def native_reader(monkeypatch, text):
    extract = Mock(return_value=text)
    reader = Mock(return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=extract)]))
    monkeypatch.setattr(ocr_ops, "PdfReader", reader)
    return reader, extract


def absent_ocr(monkeypatch, adapter):
    monkeypatch.setattr(ocr_ops, "HAS_TESSERACT", False)
    monkeypatch.setattr(ocr_ops, "HAS_PDF2IMAGE", False)
    adapter.get_tesseract_version.side_effect = AssertionError("Tesseract called")
    adapter.get_languages.side_effect = AssertionError("languages called")
    adapter.image_to_string.side_effect = AssertionError("recognition called")
    ocr_ops.convert_from_path.side_effect = AssertionError("rasterization called")


@pytest.mark.parametrize("operation_id,key,value", [
    (operation_id, key, value)
    for operation_id, fields in LEGACY.items() for key, value in fields.items()
])
def test_legacy_keys_rejected_at_compile_and_direct_execution(
    tmp_path, tools_ready, operation_id, key, value
):
    config = {key: value}
    operation = OperationRegistry().get_operation(operation_id, config)
    valid, error = operation.validate_config()
    assert not valid
    assert f"unsupported OCR configuration '{key}'" in error
    compilation = compile_operation(operation_id, config)
    assert not compilation.valid and any(error in item for item in compilation.errors)
    for dry_run in (False, True):
        result = operation.execute(tmp_path / "input.png", tmp_path / "out.txt", dry_run)
        assert not result.success and result.error == error
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("operation_id,config,keys", [
    ("ocr_image", {"language": "ron"}, {"language"}),
    ("ocr_batch", {"language": "ron"}, {"language"}),
    ("ocr_pdf", {"mode": "native", "language": "ron", "dpi": 300}, {"mode", "language", "dpi"}),
    ("ocr_pdf", {"mode": "ocr", "language": "ron", "dpi": 300}, {"mode", "language", "dpi"}),
    ("ocr_pdf", {"mode": "auto", "language": "ron", "dpi": 300}, {"mode", "language", "dpi"}),
])
def test_functional_schema_retained(tools_ready, operation_id, config, keys):
    operation = OperationRegistry().get_operation(operation_id, config)
    assert set(operation.get_config_schema()) == keys
    assert operation.validate_config() == (True, "")
    assert compile_operation(operation_id, config).valid


@pytest.mark.parametrize("template", [
    entry for entry in WorkflowTemplates.list_templates() if entry["category"] == "OCR"
], ids=lambda entry: entry["id"])
def test_every_ocr_template_is_truthful_and_compiles(tools_ready, template):
    workflow = WorkflowTemplates.get_template(template["id"])
    for step in workflow.steps:
        assert not set(step.config).intersection(LEGACY.get(step.operation_id, {}))
    description = (workflow.description + " " + template["description"]).lower()
    for claim in ("grayscale", "threshold", "preprocessing", "optimized", "high quality"):
        assert claim not in description
    compilation = compile_workflow(workflow, OperationRegistry())
    assert compilation.valid, compilation.errors


@pytest.mark.parametrize("operation_id,missing,expected", [
    (operation_id, missing, expected)
    for operation_id in ("ocr_image", "ocr_pdf")
    for missing, expected in [
        ("adapter", "pytesseract package is not installed"),
        ("binary", "Tesseract executable is not available"),
        ("language", "Tesseract language 'ron' is not available"),
    ]
] + [
    ("ocr_pdf", "pdf2image", "pdf2image package is not installed"),
    ("ocr_pdf", "poppler", "Poppler PDF rasterizer is not available"),
])
def test_missing_capability_causes_agree(tmp_path, monkeypatch, tools_ready, operation_id, missing, expected):
    if missing == "adapter":
        monkeypatch.setattr(ocr_ops, "HAS_TESSERACT", False)
    elif missing == "binary":
        tools_ready.get_tesseract_version.side_effect = FileNotFoundError()
    elif missing == "language":
        tools_ready.get_languages.return_value = ["eng"]
    elif missing == "pdf2image":
        monkeypatch.setattr(ocr_ops, "HAS_PDF2IMAGE", False)
    else:
        monkeypatch.setattr("shutil.which", lambda name: None)
    config = {"language": "ron", "mode": "ocr"}
    operation = OperationRegistry().get_operation(operation_id, config)
    assert operation.get_capability_error() == expected
    compilation = compile_operation(operation_id, config)
    assert not compilation.valid and any(expected in error for error in compilation.errors)
    for dry_run in (False, True):
        result = operation.execute(tmp_path / "input.pdf", tmp_path / "out.txt", dry_run)
        assert not result.success and result.error == expected
    assert not (tmp_path / "out.txt").exists()


@pytest.mark.parametrize("operation_id", ["ocr_image", "ocr_batch"])
def test_image_branch_needs_no_pdf_tools(tmp_path, monkeypatch, tools_ready, operation_id):
    monkeypatch.setattr(ocr_ops, "HAS_PDF2IMAGE", False)
    poppler = Mock(side_effect=AssertionError("image must not check Poppler"))
    monkeypatch.setattr("shutil.which", poppler)
    source = tmp_path / "input.png"
    Image.new("RGB", (4, 4)).save(source)
    operation = OperationRegistry().get_operation(operation_id, {"language": "ron"})
    assert operation.get_capability_error(source) is None
    assert compile_operation(operation_id, {"language": "ron"}).valid
    result = operation.execute(source, tmp_path / "out.txt")
    assert result.success, result.error
    assert result.output_path.read_text() == "mock recognition"
    assert tools_ready.image_to_string.call_args.kwargs == {"lang": "ron"}
    poppler.assert_not_called()


@pytest.mark.parametrize("operation_id", ["ocr_pdf", "ocr_batch"])
@pytest.mark.parametrize("mode", ["native", "auto"])
def test_native_success_without_any_ocr_tools(tmp_path, monkeypatch, tools_ready, operation_id, mode):
    absent_ocr(monkeypatch, tools_ready)
    rasterizer = Mock(side_effect=AssertionError("Poppler checked"))
    monkeypatch.setattr("shutil.which", rasterizer)
    text = "native text " * 8
    reader, extract = native_reader(monkeypatch, text)
    config = {"mode": mode, "language": "missing"}
    operation = OperationRegistry().get_operation(operation_id, config)
    assert operation.validate_config()[0]
    assert compile_operation(operation_id, config).valid
    assert operation.get_capability_error(tmp_path / "input.pdf") is None
    result = operation.execute(tmp_path / "input.pdf", tmp_path / "out.txt")
    assert result.success, result.error
    assert result.output_path.read_text() == text
    extract.assert_called_once_with()
    tools_ready.get_tesseract_version.assert_not_called()
    tools_ready.get_languages.assert_not_called()
    ocr_ops.convert_from_path.assert_not_called()
    rasterizer.assert_not_called()


@pytest.mark.parametrize("operation_id", ["ocr_pdf", "ocr_batch"])
@pytest.mark.parametrize("mode", ["auto", "ocr"])
def test_pdf_branch_missing_fallback_is_controlled(tmp_path, monkeypatch, tools_ready, operation_id, mode):
    native_reader(monkeypatch, "short")
    monkeypatch.setattr(ocr_ops, "HAS_PDF2IMAGE", False)
    operation = OperationRegistry().get_operation(operation_id, {"mode": mode})
    expected_preflight = "pdf2image package is not installed" if mode == "ocr" else None
    assert operation.get_capability_error(tmp_path / "input.pdf") == expected_preflight
    result = operation.execute(tmp_path / "input.pdf", tmp_path / "out.txt")
    assert not result.success and result.error == "pdf2image package is not installed"
    assert not (tmp_path / "out.txt").exists()
    ocr_ops.convert_from_path.assert_not_called()


@pytest.mark.parametrize("operation_id", ["ocr_pdf", "ocr_batch"])
@pytest.mark.parametrize("mode,native_length,uses_ocr", [
    ("native", 0, False), ("ocr", 100, True),
    ("auto", 49, True), ("auto", 50, False),
])
def test_pdf_modes_preserve_threshold_and_forward_language_dpi(
    tmp_path, monkeypatch, tools_ready, operation_id, mode, native_length, uses_ocr
):
    native_reader(monkeypatch, " " + "x" * native_length + " ")
    operation = OperationRegistry().get_operation(operation_id, {"mode": mode, "language": "ron", "dpi": 300})
    result = operation.execute(tmp_path / "input.pdf", tmp_path / "out.txt")
    assert result.success, result.error
    assert ("using ocr" in result.message) is uses_ocr
    if uses_ocr:
        ocr_ops.convert_from_path.assert_called_once_with(str(tmp_path / "input.pdf"), dpi=300)
        assert tools_ready.image_to_string.call_args.kwargs == {"lang": "ron"}
    else:
        ocr_ops.convert_from_path.assert_not_called()


@pytest.mark.parametrize("component", ["binary", "language", "poppler"])
@pytest.mark.parametrize("initially_ready", [False, True])
def test_live_readiness_refreshes_both_directions(monkeypatch, tools_ready, component, initially_ready):
    operation = ocr_ops.OCRPDFOperation({"mode": "ocr", "language": "ron"})
    for ready in (initially_ready, not initially_ready):
        if component == "binary":
            tools_ready.get_tesseract_version.side_effect = None if ready else FileNotFoundError()
        elif component == "language":
            tools_ready.get_languages.return_value = ["ron"] if ready else []
        else:
            monkeypatch.setattr("shutil.which", lambda name: name if ready else None)
        assert (operation.get_capability_error() is None) is ready
        assert compile_operation("ocr_pdf", operation.config).valid is ready
    tools_ready.get_tesseract_version.assert_called_with(cached=False)
    if component != "binary" or initially_ready is False:
        tools_ready.get_languages.assert_called_with(cached=False)


@pytest.mark.parametrize("language,available,success", [
    ("eng+ron", ["eng", "ron"], True), ("eng+ron", ["eng"], False),
    ("", ["eng"], False), ("eng", [], False),
])
def test_every_requested_language_is_checked(tools_ready, language, available, success):
    tools_ready.get_languages.return_value = available
    error = ocr_ops.OCRImageOperation({"language": language}).get_capability_error()
    assert (error is None) is success


@pytest.mark.parametrize("mode", ["auto", "ocr"])
def test_fallback_language_is_checked(tmp_path, monkeypatch, tools_ready, mode):
    native_reader(monkeypatch, "")
    tools_ready.get_languages.return_value = ["eng"]
    result = ocr_ops.OCRPDFOperation({"mode": mode, "language": "ron"}).execute(
        tmp_path / "input.pdf", tmp_path / "out.txt"
    )
    assert not result.success and "language 'ron'" in result.error
    tools_ready.image_to_string.assert_not_called()


def test_worker_reports_live_image_failure_instead_of_invalid_file(tmp_path, tools_ready):
    source = tmp_path / "input.png"
    Image.new("RGB", (4, 4)).save(source)
    tools_ready.get_tesseract_version.side_effect = FileNotFoundError()
    workflow = Workflow("live missing binary")
    workflow.add_step("ocr_batch")
    result = process_single_file(str(source), workflow.to_dict(), str(tmp_path), "out")
    assert not result["success"]
    assert result["error"] == "Tesseract executable is not available"


@pytest.mark.parametrize("mode", ["native", "auto", "ocr"])
def test_pdf_dry_run_checks_only_unconditional_capability(tmp_path, monkeypatch, tools_ready, mode):
    absent_ocr(monkeypatch, tools_ready)
    reader = Mock(side_effect=AssertionError("dry-run extraction"))
    monkeypatch.setattr(ocr_ops, "PdfReader", reader)
    result = ocr_ops.OCRPDFOperation({"mode": mode}).execute(
        tmp_path / "input.pdf", tmp_path / "out.txt", dry_run=True
    )
    assert result.success is (mode != "ocr")
    if mode == "ocr":
        assert result.error == "pytesseract package is not installed"
    reader.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_unknown_nonlegacy_keys_still_compatible(tools_ready):
    registry = OperationRegistry()
    for operation_id in ("ocr_image", "file_rename", "image_resize"):
        assert registry.get_operation(operation_id, {"future_metadata": 42}).validate_config()[0]


def test_registry_exposes_independent_capability_reasons(monkeypatch, tools_ready):
    monkeypatch.setattr(ocr_ops, "HAS_PDF2IMAGE", False)
    registry = OperationRegistry()
    readiness = registry.get_ocr_readiness("ron")
    assert readiness["image"].ready and readiness["native_pdf"].ready
    assert not readiness["pdf_ocr"].ready
    assert readiness["pdf_ocr"].error == "pdf2image package is not installed"
    status = registry.get_capability_status("ocr_pdf", {"language": "ron"})
    assert "Native PDF: ready" in status and "pdf2image package is not installed" in status


def test_ui_lists_capability_reason_without_hiding_native_pdf(monkeypatch, tools_ready):
    from ui.workflow_panel import WorkflowPanel

    absent_ocr(monkeypatch, tools_ready)
    panel = WorkflowPanel.__new__(WorkflowPanel)
    panel.operation_registry = OperationRegistry()
    panel.templates_listbox = Mock()
    panel.operations_listbox = Mock()
    panel._load_operations()
    rows = [call.args[1] for call in panel.operations_listbox.insert.call_args_list]
    assert any("OCR Image" in row and "pytesseract package is not installed" in row for row in rows)
    assert any("PDF to Text" in row and "Native PDF: ready" in row for row in rows)


@pytest.mark.parametrize("missing", ["pdfinfo", "pdftoppm"])
def test_both_poppler_executables_are_required(monkeypatch, tools_ready, missing):
    monkeypatch.setattr("shutil.which", lambda name: None if name == missing else name)
    assert ocr_ops.get_pdf_ocr_readiness().error == "Poppler PDF rasterizer is not available"


@pytest.mark.parametrize("failure", ["nonzero", "oserror", "timeout"])
def test_poppler_probe_failure_is_controlled(monkeypatch, tools_ready, failure):
    import subprocess

    probe = Mock(return_value=SimpleNamespace(returncode=1))
    if failure == "oserror":
        probe.side_effect = OSError("cannot launch")
    elif failure == "timeout":
        probe.side_effect = subprocess.TimeoutExpired(["pdfinfo", "-v"], 5)
    monkeypatch.setattr(subprocess, "run", probe)
    assert ocr_ops.get_pdf_ocr_readiness().error == "Poppler PDF rasterizer is not available"


def test_poppler_preflight_uses_bounded_argument_vectors(tools_ready):
    assert ocr_ops.get_pdf_ocr_readiness().ready
    calls = ocr_ops.subprocess.run.call_args_list
    assert [Path(call.args[0][0]).name for call in calls] == ["pdfinfo", "pdftoppm"]
    for call in calls:
        assert call.args[0][1:] == ["-v"]
        assert call.kwargs["timeout"] == 5
        assert not call.kwargs.get("shell", False)
    ocr_ops.convert_from_path.assert_not_called()


def test_language_probe_error_is_controlled(tools_ready):
    tools_ready.get_languages.side_effect = OSError("data unreadable")
    assert ocr_ops.get_image_ocr_readiness().error == "Tesseract language data could not be checked"


@pytest.mark.parametrize("operation_id,config,expected_keys", [
    ("ocr_image", {"language": "ron"}, {"language"}),
    ("ocr_batch", {"language": "ron"}, {"language"}),
    ("ocr_pdf", {"mode": "native", "language": "ron", "dpi": 300}, {"mode", "language", "dpi"}),
])
def test_ui_config_controls_and_refresh_use_current_config(
    monkeypatch, tools_ready, operation_id, config, expected_keys
):
    from ui import workflow_panel

    labels = []
    buttons = []

    def label_factory(*args, **kwargs):
        widget = Mock()
        labels.append(widget)
        return widget

    def button_factory(*args, **kwargs):
        buttons.append(kwargs)
        return Mock()

    monkeypatch.setattr(workflow_panel.ttk, "Label", label_factory)
    monkeypatch.setattr(workflow_panel.ttk, "Button", button_factory)
    for name in ("Frame", "Entry", "Combobox", "Spinbox"):
        monkeypatch.setattr(workflow_panel.ttk, name, Mock())
    for name in ("StringVar", "IntVar"):
        monkeypatch.setattr(workflow_panel.tk, name, lambda value: SimpleNamespace(get=lambda: value))
    panel = workflow_panel.WorkflowPanel.__new__(workflow_panel.WorkflowPanel)
    panel.config_container = Mock()
    panel.config_container.winfo_children.return_value = []
    panel.operation_registry = OperationRegistry()
    workflow = Workflow("UI config")
    step = workflow.add_step(operation_id, config)
    panel._show_step_config(step)
    assert set(panel.config_widgets) == expected_keys
    status = labels[1]
    initial = status.config.call_args.kwargs["text"]
    if operation_id == "ocr_pdf":
        assert initial == "Native PDF: ready"
        tools_ready.get_tesseract_version.assert_not_called()
        step.config["mode"] = "ocr"
    else:
        assert "ron" in initial and "ready" in initial
    tools_ready.get_languages.return_value = ["eng"]
    refresh = next(button["command"] for button in buttons if button["text"] == "Refresh OCR availability")
    refresh()
    assert "language 'ron' is not available" in status.config.call_args.kwargs["text"]


def test_batch_image_language_missing_fails_before_recognition(tmp_path, tools_ready):
    tools_ready.get_languages.return_value = ["eng"]
    source = tmp_path / "input.png"
    operation = ocr_ops.OCRBatchOperation({"language": "ron"})
    assert operation.get_capability_error(source) == "Tesseract language 'ron' is not available"
    result = operation.execute(source, tmp_path / "out.txt")
    assert not result.success and "language 'ron'" in result.error
    tools_ready.image_to_string.assert_not_called()
