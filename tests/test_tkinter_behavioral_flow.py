"""Behavioral V11-08 coverage at the real Tk widget/controller boundary."""

from pathlib import Path
import sys
import threading

import pytest
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from core.processor import BatchProcessor
from core.settings import Settings
from ui import main_window as main_window_module
from ui import run_panel as run_panel_module
from ui import workflow_panel as workflow_panel_module
from ui.main_window import MainWindow


TK_WAIT_TIMEOUT_SECONDS = 5.0
TK_PUMP_INTERVAL_MILLISECONDS = 5


def pump_tk_events_until(root, condition, description):
    """Run Tk callbacks until a condition succeeds or the bounded deadline expires."""
    outcome = {"completed": False}

    def poll_condition():
        if condition():
            outcome["completed"] = True
            root.quit()
            return
        root.after(TK_PUMP_INTERVAL_MILLISECONDS, poll_condition)

    poll_condition()
    timeout_id = root.after(round(TK_WAIT_TIMEOUT_SECONDS * 1000), root.quit)
    root.mainloop()
    root.after_cancel(timeout_id)
    if not outcome["completed"]:
        pytest.fail(f"Timed out after {TK_WAIT_TIMEOUT_SECONDS:.1f}s waiting for {description}")


def create_supported_png(path):
    from PIL import Image

    Image.new("RGB", (1, 1), color="white").save(path)


def fail_if_interactive_dialog_opens(name):
    def fail_dialog(*args, **kwargs):
        pytest.fail(f"Unexpected interactive dialog: {name}")

    return fail_dialog


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        if sys.platform == "win32":
            pytest.fail(f"Tk graphical session is required on Windows: {exc}")
        pytest.skip(f"Tk graphical session unavailable: {exc}")

    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def tkinter_application(tmp_path, monkeypatch, tk_root):
    dialog_calls = {"info": [], "warning": [], "error": []}
    created_threads = []
    real_thread_class = threading.Thread
    isolated_settings = Settings(str(tmp_path / "settings"))

    monkeypatch.setattr(main_window_module, "get_settings", lambda: isolated_settings)
    monkeypatch.setattr(
        workflow_panel_module.WorkflowPanel,
        "_load_capability_status",
        lambda self, operation_id, config, display_status: display_status(
            "availability isolated for behavioral test"
        ),
    )

    monkeypatch.setattr(
        messagebox,
        "showinfo",
        lambda title, text, **kwargs: dialog_calls["info"].append((title, text)),
    )
    monkeypatch.setattr(
        messagebox,
        "showwarning",
        lambda title, text, **kwargs: dialog_calls["warning"].append((title, text)),
    )
    monkeypatch.setattr(
        messagebox,
        "showerror",
        lambda title, text, **kwargs: dialog_calls["error"].append((title, text)),
    )
    monkeypatch.setattr(messagebox, "askyesno", fail_if_interactive_dialog_opens("askyesno"))
    monkeypatch.setattr(
        filedialog, "askopenfilenames", fail_if_interactive_dialog_opens("askopenfilenames")
    )
    monkeypatch.setattr(
        filedialog, "askopenfilename", fail_if_interactive_dialog_opens("askopenfilename")
    )
    monkeypatch.setattr(
        filedialog, "asksaveasfilename", fail_if_interactive_dialog_opens("asksaveasfilename")
    )
    monkeypatch.setattr(
        filedialog, "askdirectory", fail_if_interactive_dialog_opens("askdirectory")
    )
    monkeypatch.setattr(simpledialog, "askstring", fail_if_interactive_dialog_opens("askstring"))

    def create_tracked_thread(*args, **kwargs):
        worker = real_thread_class(*args, **kwargs)
        created_threads.append(worker)
        return worker

    monkeypatch.setattr(threading, "Thread", create_tracked_thread)

    root = tk_root
    application = MainWindow(root)
    root.update()

    harness = {
        "app": application,
        "root": root,
        "dialogs": dialog_calls,
        "threads": created_threads,
        "settings": isolated_settings,
    }
    yield harness

    for worker in created_threads:
        if worker.ident is not None and worker is not threading.current_thread():
            worker.join(timeout=TK_WAIT_TIMEOUT_SECONDS)
    leaked_threads = [worker.name for worker in created_threads if worker.is_alive()]

    pending_callbacks = root.tk.call("after", "info")
    for callback_id in root.tk.splitlist(pending_callbacks):
        root.after_cancel(callback_id)
    root.configure(menu="")
    for child in root.winfo_children():
        child.destroy()

    assert not leaked_threads, f"Tk behavioral workers still alive: {leaked_threads}"
    assert not isolated_settings.config_file.exists(), "Behavioral test wrote real settings"


def admit_input(harness, source):
    application = harness["app"]
    application.input_panel._accept_files([str(source)])
    pump_tk_events_until(
        harness["root"],
        lambda: application.get_files() == [str(source)],
        "input admission",
    )


def build_rename_workflow(harness, pattern="{original}_ui"):
    application = harness["app"]
    panel = application.workflow_panel
    operations = panel.operation_registry.list_operations()
    rename_index = next(
        index for index, operation in enumerate(operations) if operation["id"] == "file_rename"
    )

    panel.operations_listbox.selection_clear(0, tk.END)
    panel.operations_listbox.selection_set(rename_index)
    panel._add_operation()
    panel.steps_listbox.selection_set(0)
    panel._on_step_select(None)
    panel.config_widgets["pattern"][1].set(pattern)
    panel._apply_config(panel.current_workflow.steps[0])
    panel.workflow_name.delete(0, tk.END)
    panel.workflow_name.insert(0, "V11-08 behavioral workflow")
    panel._go_to_run()

    assert application.get_workflow() is panel.current_workflow
    assert application.get_workflow().to_dict()["steps"] == [
        {
            "operation_id": "file_rename",
            "config": {"pattern": pattern},
            "enabled": True,
        }
    ]


def start_processing_and_wait(harness, previous_stats=None):
    panel = harness["app"].run_panel
    panel._start_processing()
    pump_tk_events_until(
        harness["root"],
        lambda: not panel.is_running
        and panel.current_stats is not None
        and panel.current_stats is not previous_stats,
        "processing completion callback",
    )
    return panel.current_stats


def record_processor_and_ui_threads(monkeypatch, panel):
    thread_ids = {}
    main_thread_id = threading.get_ident()

    class ThreadRecordingBatchProcessor(BatchProcessor):
        def process_batch(self, *args, **kwargs):
            thread_ids["worker"] = threading.get_ident()
            return super().process_batch(*args, **kwargs)

    original_status_config = panel.status_label.config

    def record_status_mutation(*args, **kwargs):
        text = kwargs.get("text", "")
        if text.startswith(("✅", "❌", "ℹ️", "⏹️", "⚠️")):
            thread_ids["ui_mutation"] = threading.get_ident()
        return original_status_config(*args, **kwargs)

    monkeypatch.setattr(run_panel_module, "BatchProcessor", ThreadRecordingBatchProcessor)
    monkeypatch.setattr(panel.status_label, "config", record_status_mutation)
    return thread_ids, main_thread_id


def test_successful_input_workflow_run_results_flow(tmp_path, monkeypatch, tkinter_application):
    harness = tkinter_application
    application = harness["app"]
    root = harness["root"]
    source = tmp_path / "input.png"
    output_dir = tmp_path / "output"
    create_supported_png(source)
    output_dir.mkdir()
    confetti_threads = []
    monkeypatch.setattr(
        application.run_panel,
        "_show_confetti",
        lambda: confetti_threads.append(threading.get_ident()),
    )
    thread_ids, main_thread_id = record_processor_and_ui_threads(monkeypatch, application.run_panel)

    assert application.notebook.index("current") == 0
    admit_input(harness, source)
    assert application.input_panel.file_listbox.get(0) == source.name
    application.input_panel._go_to_workflow()
    assert application.notebook.index("current") == 1

    build_rename_workflow(harness)
    assert application.notebook.index("current") == 2
    application.run_panel.output_dir.set(str(output_dir))
    application.run_panel.workers_var.set(1)
    application.run_panel.generate_report_var.set(False)

    stats = start_processing_and_wait(harness)
    assert stats.total_files == stats.processed_files == 1
    assert stats.failed_files == 0
    assert len(stats.results) == 1
    result = stats.results[0]
    output_path = Path(result["output"])
    assert result["file"] == str(source)
    assert output_path == output_dir / "input_ui.png"
    assert output_path.read_bytes() == source.read_bytes()
    assert application.run_panel.status_label.cget("text") == "✅ Processing completed successfully."
    assert "1 / 1 files" in application.run_panel.progress_label.cget("text")

    application.run_panel._view_results()
    assert application.notebook.index("current") == 3
    assert application.logs_panel.current_stats is stats
    result_items = application.logs_panel.results_tree.get_children()
    assert len(result_items) == 1
    assert application.logs_panel.results_tree.item(result_items[0], "values")[:2] == (
        output_path.name,
        "✅ Success",
    )

    responsive = threading.Event()
    root.after(0, responsive.set)
    pump_tk_events_until(root, responsive.is_set, "post-success responsiveness callback")

    assert thread_ids["worker"] != main_thread_id
    assert thread_ids["ui_mutation"] == main_thread_id
    assert confetti_threads == [main_thread_id]
    assert harness["dialogs"]["error"] == []


def test_successful_run_repeats_in_the_same_application(tmp_path, monkeypatch, tkinter_application):
    harness = tkinter_application
    application = harness["app"]
    first_source = tmp_path / "first.png"
    second_source = tmp_path / "second.png"
    create_supported_png(first_source)
    create_supported_png(second_source)
    monkeypatch.setattr(application.run_panel, "_show_confetti", lambda: None)

    admit_input(harness, first_source)
    application.input_panel._go_to_workflow()
    build_rename_workflow(harness, pattern="{original}_repeat")
    application.run_panel.workers_var.set(1)
    application.run_panel.generate_report_var.set(False)

    first_output_dir = tmp_path / "first-output"
    first_output_dir.mkdir()
    application.run_panel.output_dir.set(str(first_output_dir))
    first_stats = start_processing_and_wait(harness)
    assert first_stats.processed_files == 1

    application.notebook.select(0)
    application.input_panel._accept_files([str(second_source)])
    pump_tk_events_until(
        harness["root"],
        lambda: application.get_files() == [str(first_source), str(second_source)],
        "second input admission",
    )
    second_output_dir = tmp_path / "second-output"
    second_output_dir.mkdir()
    application.run_panel.output_dir.set(str(second_output_dir))
    application.notebook.select(2)
    second_stats = start_processing_and_wait(harness, previous_stats=first_stats)

    assert second_stats.total_files == second_stats.processed_files == 2
    assert second_stats.failed_files == 0
    assert {Path(result["output"]).name for result in second_stats.results} == {
        "first_repeat.png",
        "second_repeat.png",
    }


def test_processor_failure_reaches_results_on_the_tk_thread(
    tmp_path, monkeypatch, tkinter_application
):
    from core import processor as processor_module

    harness = tkinter_application
    application = harness["app"]
    root = harness["root"]
    source = tmp_path / "failure.png"
    output_dir = tmp_path / "failure-output"
    create_supported_png(source)
    output_dir.mkdir()
    confetti_calls = []
    operation_thread_ids = []
    monkeypatch.setattr(
        application.run_panel,
        "_show_confetti",
        lambda: confetti_calls.append(threading.get_ident()),
    )
    thread_ids, main_thread_id = record_processor_and_ui_threads(monkeypatch, application.run_panel)

    def fail_processing(file_path, *args, **kwargs):
        operation_thread_ids.append(threading.get_ident())
        return {"success": False, "file": file_path, "error": "synthetic processor failure"}

    monkeypatch.setattr(processor_module, "process_single_file", fail_processing)
    admit_input(harness, source)
    application.input_panel._go_to_workflow()
    build_rename_workflow(harness)
    application.run_panel.output_dir.set(str(output_dir))
    application.run_panel.workers_var.set(1)
    application.run_panel.generate_report_var.set(False)

    stats = start_processing_and_wait(harness)
    assert stats.processed_files == 0
    assert stats.failed_files == 1
    assert stats.errors[0]["error"] == "synthetic processor failure"
    assert application.run_panel.status_label.cget("text") == "❌ Processing failed."
    assert confetti_calls == []
    assert harness["dialogs"]["info"][-1][0] == "Processing Failed"
    assert "success" not in harness["dialogs"]["info"][-1][1].lower()

    application.run_panel._view_results()
    error_items = application.logs_panel.errors_tree.get_children()
    assert len(error_items) == 1
    assert application.logs_panel.errors_tree.item(error_items[0], "values") == (
        source.name,
        "synthetic processor failure",
    )

    responsive = threading.Event()
    root.after(0, responsive.set)
    pump_tk_events_until(root, responsive.is_set, "post-failure responsiveness callback")

    assert thread_ids["worker"] != main_thread_id
    assert operation_thread_ids and operation_thread_ids[0] != main_thread_id
    assert thread_ids["ui_mutation"] == main_thread_id


def test_no_input_is_a_stable_non_success_boundary(
    monkeypatch, tkinter_application
):
    harness = tkinter_application
    application = harness["app"]
    root = harness["root"]
    confetti_calls = []
    monkeypatch.setattr(
        application.run_panel,
        "_show_confetti",
        lambda: confetti_calls.append(threading.get_ident()),
    )

    application.notebook.select(2)
    application.run_panel._start_processing()

    assert application.notebook.index("current") == 0
    assert application.run_panel.is_running is False
    assert application.run_panel.current_stats is None
    assert application.run_panel.status_label.cget("text") == "Ready to process"
    assert confetti_calls == []
    assert harness["dialogs"]["warning"] == [
        ("No Files", "Please select files in the Input tab first!")
    ]
    assert all(
        "success" not in title.lower() and "success" not in text.lower()
        for title, text in harness["dialogs"]["warning"]
    )

    responsive = threading.Event()
    root.after(0, responsive.set)
    pump_tk_events_until(root, responsive.is_set, "post-no-input responsiveness callback")
