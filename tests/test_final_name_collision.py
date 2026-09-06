"""V12-01: deterministic final-name collision regressions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.operations import file_ops
from core import processor as processor_module
from core.processor import BatchProcessor, ProcessingStats, process_single_file
from core.security import OutputPathAllocator, exclusive_output
from core.workflow import Workflow
from ui import logs_panel
from ui.logs_panel import LogsPanel


SENTINEL = b"unrelated output: preserve these bytes\x00\xff"


def make_report_stats(label: str) -> ProcessingStats:
    stats = ProcessingStats()
    stats.total_files = 1
    stats.add_result(f"{label}.txt", {"output": f"{label}.txt", "message": label})
    return stats


@pytest.mark.parametrize("report_format", ["html", "csv"])
def test_existing_report_destination_is_not_overwritten(tmp_path, report_format):
    target = tmp_path / f"report.{report_format}"
    target.write_bytes(SENTINEL)
    stats = make_report_stats("new-report")

    generated = BatchProcessor().generate_report(stats, str(target), report_format)

    assert generated is False
    assert target.read_bytes() == SENTINEL
    assert stats.generated_report_paths == {}


@pytest.mark.parametrize("report_format", ["html", "csv"])
def test_report_collision_at_exclusive_open_preserves_new_owner(
    tmp_path, monkeypatch, report_format
):
    target = tmp_path / f"report.{report_format}"
    collided = []

    @contextmanager
    def occupy_before_create(path, **options):
        Path(path).write_bytes(SENTINEL)
        collided.append(Path(path))
        with exclusive_output(Path(path), **options) as stream:
            yield stream

    monkeypatch.setattr(processor_module, "exclusive_output", occupy_before_create)

    generated = BatchProcessor().generate_report(
        make_report_stats("late-collision"), str(target), report_format
    )

    assert generated is False
    assert collided == [target]
    assert target.read_bytes() == SENTINEL


@pytest.mark.parametrize("report_format", ["html", "csv"])
def test_concurrent_reports_have_one_explicit_owner(tmp_path, monkeypatch, report_format):
    target = tmp_path / f"report.{report_format}"
    ready_to_create = threading.Barrier(2)

    @contextmanager
    def synchronize_before_create(path, **options):
        ready_to_create.wait(timeout=5)
        with exclusive_output(Path(path), **options) as stream:
            yield stream

    monkeypatch.setattr(processor_module, "exclusive_output", synchronize_before_create)
    processor = BatchProcessor()
    labels = ("first-owner", "second-owner")

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda label: processor.generate_report(
                    make_report_stats(label), str(target), report_format
                ),
                labels,
            )
        )

    report = target.read_text(encoding="utf-8")
    assert sorted(outcomes) == [False, True]
    assert sum(label in report for label in labels) == 1


def test_html_view_does_not_open_unowned_stale_report(tmp_path, monkeypatch):
    target = tmp_path / "report.html"
    target.write_bytes(SENTINEL)
    browser = Mock()
    monkeypatch.setattr(logs_panel.webbrowser, "open", browser)
    panel = LogsPanel.__new__(LogsPanel)
    panel.current_stats = make_report_stats("current-run")
    panel.main_window = SimpleNamespace(
        processor=BatchProcessor(),
        run_panel=SimpleNamespace(output_dir=SimpleNamespace(get=lambda: str(tmp_path))),
        set_status=Mock(),
    )

    panel._view_html_report()

    browser.assert_not_called()
    assert target.read_bytes() == SENTINEL
    panel.main_window.set_status.assert_called_once_with(
        "HTML report unavailable; the destination is occupied or could not be written.",
        "danger",
    )


def test_html_view_opens_only_report_recorded_for_current_stats(tmp_path, monkeypatch):
    target = tmp_path / "report.html"
    processor = BatchProcessor()
    stats = make_report_stats("current-run")
    assert processor.generate_report(stats, str(target), "html")
    processor.generate_report = Mock(wraps=processor.generate_report)
    browser = Mock()
    monkeypatch.setattr(logs_panel.webbrowser, "open", browser)
    panel = LogsPanel.__new__(LogsPanel)
    panel.current_stats = stats
    panel.main_window = SimpleNamespace(
        processor=processor,
        run_panel=SimpleNamespace(output_dir=SimpleNamespace(get=lambda: str(tmp_path))),
        set_status=Mock(),
    )

    panel._view_html_report()

    processor.generate_report.assert_not_called()
    browser.assert_called_once_with(f"file://{target.resolve()}")


def test_independent_workers_converging_on_final_path_have_one_owner(tmp_path, monkeypatch):
    sources = []
    for name, contents in (("alpha.txt", b"alpha"), ("beta.txt", b"beta")):
        source = tmp_path / name
        source.write_bytes(contents)
        sources.append(source)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    workflow = Workflow("concurrent final owner")
    workflow.add_step("file_rename", {"pattern": "final"})
    workflow_payload = workflow.to_dict()
    ready_to_create = threading.Barrier(2)

    @contextmanager
    def synchronize_before_create(path, **options):
        ready_to_create.wait(timeout=5)
        with exclusive_output(Path(path), **options) as stream:
            yield stream

    monkeypatch.setattr(file_ops, "exclusive_output", synchronize_before_create)

    def process(source):
        return process_single_file(str(source), workflow_payload, str(output_dir), "{original}")

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(process, sources))

    successes = [outcome for outcome in outcomes if outcome["success"]]
    failures = [outcome for outcome in outcomes if not outcome["success"]]
    assert len(successes) == len(failures) == 1
    assert failures[0]["error"]
    owned_output = Path(successes[0]["output"])
    assert owned_output == output_dir / "final.txt"
    assert owned_output.read_bytes() == Path(successes[0]["file"]).read_bytes()
    assert set(output_dir.iterdir()) == {owned_output}


def test_different_initial_names_converge_to_distinct_final_outputs(tmp_path):
    sources = []
    for name, contents in (("alpha.txt", b"alpha"), ("beta.txt", b"beta")):
        source = tmp_path / name
        source.write_bytes(contents)
        sources.append(source)
    workflow = Workflow("convergent final names")
    workflow.add_step("file_rename", {"pattern": "same"})

    stats = BatchProcessor(max_workers=2).process_batch(
        [str(source) for source in sources],
        workflow,
        str(tmp_path / "out"),
        naming_pattern="{original}",
    )

    outputs = {
        Path(record["output"]).name: Path(record["output"]).read_bytes() for record in stats.results
    }
    assert stats.failed_files == 0
    assert set(outputs) == {"same.txt", "same_001.txt"}
    assert set(outputs.values()) == {b"alpha", b"beta"}


def test_sanitized_name_aliases_reserve_distinct_paths(tmp_path):
    allocator = OutputPathAllocator(tmp_path)

    outputs = [
        allocator.allocate("same", ".txt"),
        allocator.allocate(" same ", ".txt"),
        allocator.allocate("same.", ".txt"),
    ]

    assert [path.name for path in outputs] == [
        "same.txt",
        "same_001.txt",
        "same_002.txt",
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows case-insensitive path contract")
def test_windows_case_aliases_reserve_distinct_paths(tmp_path):
    allocator = OutputPathAllocator(tmp_path)

    first = allocator.allocate("CaseName", ".TXT")
    second = allocator.allocate("casename", ".txt")

    assert first.name == "CaseName.TXT"
    assert second.name == "casename_001.txt"
    assert first != second
