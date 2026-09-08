"""PRODUCT-D2-I1 unit and real Tk/tkdnd integration contracts."""

from types import SimpleNamespace
from unittest.mock import Mock
import sys
import threading
import tkinter as tk

import pytest

import main
from core import Workflow
from core.settings import Settings
from ui import dnd_support, input_panel, main_window as main_window_module
from ui.dnd_support import COPY, REFUSE_DROP, enable_native_file_drop
from ui.input_panel import InputPanel
from ui.main_window import MainWindow
from ui.run_panel import RunPanel


def make_synchronous_input_panel():
    panel = InputPanel.__new__(InputPanel)
    panel.selected_files = []
    panel._selected_file_identities = set()
    panel._displayed_files = []
    panel.main_window = SimpleNamespace(
        dnd_status=SimpleNamespace(targets_registered=True),
        get_workflow=lambda: None,
        set_status=Mock(),
        set_files=Mock(),
    )
    panel.frame = SimpleNamespace(tk=Mock())
    panel.file_listbox = Mock()
    panel.drop_label = Mock()
    panel._update_stats = Mock()
    panel._update_drop_zone_visibility = Mock()
    panel._load_input_support = lambda check, complete: (complete(check()), True)[1]
    return panel


def workflow_for(operation_id):
    workflow = Workflow("PRODUCT-D2-I1")
    workflow.add_step(operation_id)
    return workflow


def test_missing_python_package_keeps_existing_root_usable(monkeypatch):
    root = SimpleNamespace(tk=Mock())
    monkeypatch.setattr(dnd_support, "TkinterDnD", None)

    status = enable_native_file_drop(root)

    assert status.python_package_importable is False
    assert status.tkdnd_loaded is False
    assert status.targets_registered is False
    assert status.error is None
    root.tk.call.assert_not_called()


def test_native_load_failure_keeps_the_existing_root_for_picker_fallback():
    root = SimpleNamespace(tk=Mock())
    failing_module = SimpleNamespace(
        require=Mock(side_effect=RuntimeError("injected load failure"))
    )

    status = enable_native_file_drop(root, dnd_module=failing_module)

    assert status.python_package_importable is True
    assert status.tkdnd_loaded is False
    assert status.targets_registered is False
    assert status.error == "RuntimeError: injected load failure"
    assert root is root


def test_loader_success_without_tcl_package_identity_fails_closed():
    root = SimpleNamespace(tk=Mock())
    root.tk.call.return_value = ""
    module = SimpleNamespace(require=Mock(return_value="injected"))

    status = enable_native_file_drop(root, dnd_module=module)

    assert status.python_package_importable is True
    assert status.tkdnd_loaded is False
    assert status.targets_registered is False
    assert "did not report" in status.error


def test_tk_startup_failure_is_not_relabelled_as_optional_dnd_absence(monkeypatch):
    failure = tk.TclError("injected Tk startup failure")
    monkeypatch.setattr(main.tk, "Tk", Mock(side_effect=failure))

    with pytest.raises(tk.TclError, match="injected Tk startup failure"):
        main.create_application_root()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows tkdnd integration qualification")
def test_normal_bootstrap_loads_real_tkdnd_and_registers_both_targets(tmp_path, monkeypatch):
    assert dnd_support.TkinterDnD is not None, "Windows tests must install the declared dnd extra"
    settings = Settings(str(tmp_path / "settings"))
    monkeypatch.setattr(main_window_module, "get_settings", lambda: settings)

    root, status = main.create_application_root()
    try:
        application = MainWindow(root, dnd_status=status)
        root.update()

        assert status.python_package_importable is True
        assert status.python_package_version
        assert status.tkdnd_loaded is True
        assert status.tkdnd_version == root.tk.call("package", "provide", "tkdnd")
        assert status.targets_registered is True
        assert "native file drop available" in application.input_panel.file_list_frame.cget("text")
        for target in (
            application.input_panel.file_listbox,
            application.input_panel.drop_label,
        ):
            for event_name in (
                "<<DropEnter>>",
                "<<DropPosition>>",
                "<<DropLeave>>",
                "<<Drop>>",
            ):
                assert target.dnd_bind(event_name)
    finally:
        root.destroy()

    assert not settings.config_file.exists()


@pytest.mark.parametrize("payload", ("", r"{C:\synthetic input\unfinished.png"))
def test_empty_or_malformed_drop_resets_feedback_without_starting_admission(monkeypatch, payload):
    panel = InputPanel.__new__(InputPanel)
    tcl_interpreter = Mock()
    if payload:
        tcl_interpreter.splitlist.side_effect = tk.TclError("injected malformed Tcl list")
    panel.frame = SimpleNamespace(tk=tcl_interpreter)
    panel.main_window = SimpleNamespace(set_status=Mock())
    panel.file_listbox = Mock()
    panel.drop_label = Mock()
    panel._accept_files = Mock()
    warning = Mock()
    monkeypatch.setattr(input_panel.messagebox, "showwarning", warning)

    result = panel._on_drop(SimpleNamespace(data=payload, actions=(COPY, "move"), action="move"))

    assert result == REFUSE_DROP
    panel._accept_files.assert_not_called()
    panel.file_listbox.config.assert_called_with(background="white")
    panel.drop_label.config.assert_called_with(foreground="gray")
    warning.assert_called_once()


def test_second_input_request_is_explicitly_refused_while_probe_is_active(monkeypatch):
    panel = InputPanel.__new__(InputPanel)
    panel._selection_token = None
    panel.main_window = SimpleNamespace(set_status=Mock())
    panel.frame = Mock()
    panel.frame.winfo_exists.return_value = True
    callbacks = []
    panel.frame.after.side_effect = lambda delay, callback: callbacks.append(callback)
    warning = Mock()
    monkeypatch.setattr(input_panel.messagebox, "showwarning", warning)
    entered = threading.Event()
    release = threading.Event()
    workers = []
    real_thread = threading.Thread

    def tracked_thread(*args, **kwargs):
        worker = real_thread(*args, **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(input_panel.threading, "Thread", tracked_thread)

    def first_check():
        entered.set()
        assert release.wait(5)
        return "first"

    first_complete = Mock()
    second_complete = Mock()
    assert panel._load_input_support(first_check, first_complete) is True
    assert entered.wait(5)

    assert panel._load_input_support(lambda: "second", second_complete) is False
    warning.assert_called_once()
    second_complete.assert_not_called()

    release.set()
    workers[0].join(timeout=5)
    assert not workers[0].is_alive()
    while callbacks and not first_complete.called:
        callbacks.pop(0)()
    first_complete.assert_called_once_with("first")


def test_clear_all_cancels_pending_validation_only_after_confirmation(monkeypatch):
    panel = InputPanel.__new__(InputPanel)
    panel._selection_token = object()
    panel.selected_files = ["C:\\synthetic\\input.png"]
    panel._selected_file_identities = {"identity"}
    panel._displayed_files = list(panel.selected_files)
    panel.file_listbox = Mock()
    panel.preview_canvas = Mock()
    panel.info_text = Mock()
    panel._clear_preview_cache = Mock()
    panel._update_stats = Mock()
    panel._update_drop_zone_visibility = Mock()
    panel.main_window = SimpleNamespace(set_files=Mock(), set_status=Mock())
    monkeypatch.setattr(input_panel.messagebox, "askyesno", Mock(return_value=True))

    panel._clear_all()

    assert panel._selection_token is None
    assert panel.selected_files == []
    assert panel._selected_file_identities == set()
    panel.main_window.set_files.assert_called_once_with([])


def test_filtered_selection_removes_the_selected_path_not_same_basename_peer():
    first = r"C:\synthetic\first\input.png"
    second = r"C:\synthetic\second\input.png"
    panel = InputPanel.__new__(InputPanel)
    panel.selected_files = [first, second]
    panel._displayed_files = [first, second]
    panel.file_previews = {}
    panel._preview_cache_order = []
    panel.file_listbox = Mock()
    panel.file_listbox.curselection.return_value = (1,)
    panel._filter_files = Mock()
    panel._update_stats = Mock()
    panel._update_drop_zone_visibility = Mock()
    panel.main_window = SimpleNamespace(set_files=Mock(), set_status=Mock())

    panel._remove_selected()

    assert panel.selected_files == [first]
    panel.main_window.set_files.assert_called_once_with([first])


@pytest.mark.parametrize(
    "route_order",
    (("picker", "drop"), ("drop", "picker"), ("drop", "drop")),
)
def test_picker_and_drop_share_windows_equivalent_path_deduplication(
    tmp_path, monkeypatch, route_order
):
    source = tmp_path / "input.png"
    source.write_bytes(b"input")
    alternate_spelling = str(source).replace("\\", "/")
    panel = make_synchronous_input_panel()
    monkeypatch.setattr(input_panel.messagebox, "showwarning", Mock())

    def picker():
        monkeypatch.setattr(
            input_panel.filedialog,
            "askopenfilenames",
            Mock(return_value=[str(source)]),
        )
        panel._add_files()

    def drop():
        panel._parse_drop_data = lambda data: [alternate_spelling]
        assert panel._on_drop(SimpleNamespace(data="ignored", actions=(COPY,), action=COPY)) == COPY

    routes = {"picker": picker, "drop": drop}
    for route in route_order:
        routes[route]()

    assert (
        panel.selected_files == [str(source)]
        if route_order[0] == "picker"
        else [alternate_spelling]
    )
    panel.file_listbox.insert.assert_called_once()
    assert "Added 0 file(s)" in panel.main_window.set_status.call_args.args[0]


def test_mixed_drop_admits_only_workflow_eligible_files(tmp_path, monkeypatch):
    image = tmp_path / "eligible.png"
    pdf = tmp_path / "workflow-incompatible.pdf"
    text = tmp_path / "not-product-admitted.txt"
    for path in (image, pdf, text):
        path.write_bytes(b"synthetic")
    panel = make_synchronous_input_panel()
    workflow = workflow_for("image_resize")
    panel.main_window.get_workflow = lambda: workflow
    warning = Mock()
    monkeypatch.setattr(input_panel.messagebox, "showwarning", warning)
    panel._parse_drop_data = lambda data: [str(image), str(pdf), str(text)]

    assert (
        panel._on_drop(SimpleNamespace(data="ignored", actions=(COPY, "move"), action="move"))
        == COPY
    )

    assert panel.selected_files == [str(image)]
    warning_text = warning.call_args.args[1]
    assert "workflow-incompatible.pdf: Unsupported input" in warning_text
    assert "not-product-admitted.txt" in warning_text
    assert "not selectable" in warning_text


def test_run_revalidates_a_source_removed_after_selection(tmp_path):
    source = tmp_path / "selected.png"
    source.write_bytes(b"synthetic")
    source.unlink()
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
    assert "File does not exist" in panel._processing_error.call_args.args[0]
    assert not (tmp_path / "output").exists()
