"""V12-03 capability-level and route-consistency contracts."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import ALLOWED_EXTENSIONS, BatchProcessor, OperationRegistry, Workflow
from core.operations.registry import FILE_TYPE_BY_EXTENSION
from core.processor import validate_file_path
from core.workflow import WorkflowTemplates
from ui import input_panel
from ui.input_panel import InputPanel
from ui.input_support import SELECTABLE_INPUT_EXTENSIONS, get_input_error, get_picker_filetypes
from ui.run_panel import RunPanel

TARGET_FORMATS = (
    (".xls", "spreadsheet"),
    (".xlsx", "spreadsheet"),
    (".txt", "text"),
    (".json", "text"),
    (".xml", "text"),
)
SUPPORTED_CONTROLS = (
    (".csv", "csv"),
    (".png", "image"),
    (".pdf", "pdf"),
)
ALL_ROUTE_EXPECTATIONS = TARGET_FORMATS + SUPPORTED_CONTROLS


def workflow_for(operation_id):
    workflow = Workflow("V12-03 route matrix")
    workflow.add_step(operation_id)
    return workflow


def picker_patterns():
    filetypes, errors = get_picker_filetypes(None)
    assert errors == []
    return set(filetypes[0][1])


def make_input_panel(monkeypatch):
    panel = InputPanel.__new__(InputPanel)
    panel.selected_files = []
    panel.main_window = SimpleNamespace(
        get_workflow=lambda: None,
        set_status=Mock(),
        set_files=Mock(),
    )
    panel.frame = Mock()
    panel.file_listbox = Mock()
    panel._update_stats = Mock()
    panel._update_drop_zone_visibility = Mock()
    panel._load_input_support = lambda check, complete: complete(check())
    monkeypatch.setattr(input_panel.messagebox, "showwarning", Mock())
    return panel


@pytest.mark.parametrize("extension,expected_type", ALL_ROUTE_EXPECTATIONS)
def test_classification_core_validation_picker_and_preflight_matrix(
    tmp_path, extension, expected_type
):
    source = tmp_path / ("input" + extension)
    source.write_bytes(b"opaque input")
    selectable = extension not in dict(TARGET_FORMATS)

    assert FILE_TYPE_BY_EXTENSION[extension] == expected_type
    assert OperationRegistry().classify_extension(extension.upper()) == expected_type
    assert extension in ALLOWED_EXTENSIONS
    assert validate_file_path(str(source)) == (True, "")
    assert (extension in SELECTABLE_INPUT_EXTENSIONS) is selectable
    assert (("*" + extension) in picker_patterns()) is selectable

    error = get_input_error(source, workflow_for("file_rename"))
    if selectable:
        assert error is None
    else:
        assert error == (
            f"File type '{extension}' has core generic-file compatibility only "
            "and is not selectable"
        )


@pytest.mark.parametrize("extension,expected_type", TARGET_FORMATS)
def test_generic_rename_preserves_target_format_opaque_bytes(tmp_path, extension, expected_type):
    source = tmp_path / ("input" + extension)
    payload = b"not parsed\x00\xff" + extension.encode("ascii")
    source.write_bytes(payload)

    stats = BatchProcessor(max_workers=1).process_batch(
        [str(source)],
        workflow_for("file_rename"),
        str(tmp_path / "output"),
        naming_pattern="{original}",
    )

    assert expected_type in {"spreadsheet", "text"}
    assert stats.processed_files == 1
    assert stats.failed_files == 0
    output = Path(stats.results[0]["output"])
    assert output.suffix == extension
    assert output.read_bytes() == payload
    assert source.read_bytes() == payload


@pytest.mark.parametrize("extension,expected_type", TARGET_FORMATS)
@pytest.mark.parametrize("route", ("picker", "folder", "drop"))
def test_every_ui_admission_route_rejects_generic_only_formats(
    tmp_path, monkeypatch, extension, expected_type, route
):
    source = tmp_path / ("input" + extension)
    source.write_bytes(expected_type.encode("ascii"))
    panel = make_input_panel(monkeypatch)

    if route == "picker":
        monkeypatch.setattr(
            input_panel.filedialog,
            "askopenfilenames",
            Mock(return_value=[str(source)]),
        )
        panel._add_files()
    elif route == "folder":
        monkeypatch.setattr(
            input_panel.filedialog,
            "askdirectory",
            Mock(return_value=str(tmp_path)),
        )
        panel._add_folder()
    else:
        panel._parse_drop_data = lambda data: [str(source)]
        assert panel._on_drop(SimpleNamespace(data="ignored", action="copy")) == "copy"

    assert panel.selected_files == []
    warning = input_panel.messagebox.showwarning.call_args.args[1]
    assert "core generic-file compatibility only" in warning
    assert "not selectable" in warning


@pytest.mark.parametrize("extension,expected_type", SUPPORTED_CONTROLS)
@pytest.mark.parametrize("route", ("picker", "folder", "drop"))
def test_supported_controls_remain_admitted_on_every_ui_route(
    tmp_path, monkeypatch, extension, expected_type, route
):
    source = tmp_path / ("input" + extension)
    source.write_bytes(expected_type.encode("ascii"))
    panel = make_input_panel(monkeypatch)

    if route == "picker":
        monkeypatch.setattr(
            input_panel.filedialog,
            "askopenfilenames",
            Mock(return_value=[str(source)]),
        )
        panel._add_files()
    elif route == "folder":
        monkeypatch.setattr(
            input_panel.filedialog,
            "askdirectory",
            Mock(return_value=str(tmp_path)),
        )
        panel._add_folder()
    else:
        panel._parse_drop_data = lambda data: [str(source)]
        assert panel._on_drop(SimpleNamespace(data="ignored", action="copy")) == "copy"

    assert panel.selected_files == [str(source)]
    input_panel.messagebox.showwarning.assert_not_called()


@pytest.mark.parametrize("extension,expected_type", TARGET_FORMATS)
def test_run_preflight_rejects_generic_only_formats_before_processor(
    tmp_path, extension, expected_type
):
    source = tmp_path / ("input" + extension)
    source.write_bytes(expected_type.encode("ascii"))
    panel = RunPanel.__new__(RunPanel)
    panel.processor = Mock()
    panel.frame = Mock()
    panel._processing_error = Mock()
    panel._processing_started = Mock()
    panel._processing_complete = Mock()

    panel._run_batch(
        [str(source)],
        workflow_for("file_rename"),
        str(tmp_path / "output"),
        "{original}",
        False,
        False,
    )
    for call in panel.frame.after.call_args_list:
        _, callback, *args = call.args
        callback(*args)

    panel.processor.process_batch.assert_not_called()
    panel._processing_started.assert_not_called()
    assert "core generic-file compatibility only" in panel._processing_error.call_args.args[0]
    assert not (tmp_path / "output").exists()


def test_registry_workflow_and_templates_expose_no_target_format_operation():
    registry = OperationRegistry()
    operations = {
        operation_id: operation_class()
        for operation_id, operation_class in {
            **registry.operations,
            **registry.aggregate_operations,
        }.items()
    }

    assert {
        operation_id
        for operation_id, operation in operations.items()
        if operation.accepted_types & {"spreadsheet", "text"}
    } == set()
    assert operations["file_rename"].accepted_types == {"any"}
    assert operations["file_rename"].output_type == "same"

    for template in WorkflowTemplates.list_templates():
        workflow = WorkflowTemplates.get_template(template["id"])
        assert workflow is not None
        for step in workflow.get_enabled_steps():
            operation = operations[step.operation_id]
            assert not (operation.accepted_types & {"spreadsheet", "text"})


def test_canonical_docs_record_every_v12_03_decision_and_boundary():
    repository_root = Path(__file__).resolve().parents[1]
    operations = (repository_root / "docs" / "OPERATIONS.md").read_text(encoding="utf-8")
    roadmap = (repository_root / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    user_guide = (repository_root / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")

    for extension, _ in TARGET_FORMATS:
        decision_row = next(
            line for line in operations.splitlines() if line.startswith(f"| `{extension}` |")
        )
        assert "| 1 | 1 | No | None | `RESTRICT_TO_GENERIC_COMPATIBILITY` |" in decision_row
    assert "control-plane persistence format" in operations
    assert "not user data inputs" in operations
    assert "does not parse or transform a TXT input" in operations
    assert "V12-03 (issue #33) selected `RESTRICT_TO_GENERIC_COMPATIBILITY`" in roadmap
    assert "**V12-PERF is the next admissible implementation unit**" in roadmap
    assert "previews admitted images, PDF metadata, and CSV rows" in user_guide
