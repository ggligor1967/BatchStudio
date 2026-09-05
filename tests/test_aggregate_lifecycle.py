"""V11-02: real aggregate lifecycle with deterministic termination boundaries."""

import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter

import core.processor as processor_module
from core.operations.pdf_ops import PDFAggregateMergeOperation
from core.processor import BatchProcessor
from core.workflow import Workflow
from tests.pdf_merge_cases import make_pdf_inputs


def assert_no_completed_output(stats):
    assert all(not record["output"] for record in stats.results)
    assert all(not record["result"].get("output") for record in stats.results)


def assert_settled(processor, stats):
    assert processor.stats is stats
    assert processor.is_running is False
    assert processor.is_paused is False
    assert stats.start_time is not None and stats.end_time is not None
    assert stats.end_time >= stats.start_time


@pytest.fixture
def merge_case(tmp_path, monkeypatch):
    case = SimpleNamespace(
        processor=BatchProcessor(max_workers=1),
        workflow=Workflow("aggregate-lifecycle"),
        files=make_pdf_inputs(tmp_path, 3),
        out=tmp_path / "out",
        begun=[], consumed=[], finalized=[],
    )
    case.workflow.add_step("pdf_merge", {"output_filename": "merged.pdf"})
    begin = PDFAggregateMergeOperation.begin
    consume = PDFAggregateMergeOperation.consume
    finalize = PDFAggregateMergeOperation.finalize

    def observe_begin(operation, output_path, dry_run=False):
        assert operation._writer is None
        assert operation._output_path is None
        assert operation._consumed == 0
        case.begun.append(operation)
        begin(operation, output_path, dry_run)

    def observe_consume(operation, file_path):
        assert_no_completed_output(case.processor.stats)
        case.consumed.append(file_path)
        return consume(operation, file_path)

    def observe_finalize(operation):
        assert_no_completed_output(case.processor.stats)
        case.finalized.append(operation)
        result = finalize(operation)
        # Publication must wait for finalize to return.
        assert_no_completed_output(case.processor.stats)
        return result

    monkeypatch.setattr(PDFAggregateMergeOperation, "begin", observe_begin)
    monkeypatch.setattr(PDFAggregateMergeOperation, "consume", observe_consume)
    monkeypatch.setattr(PDFAggregateMergeOperation, "finalize", observe_finalize)
    return case


@pytest.mark.parametrize("config", [{}, {"output_filename": "explicit.pdf"}])
@pytest.mark.parametrize("dry_run", [False, True])
def test_empty_aggregate_is_controlled_before_output_preparation(merge_case, monkeypatch, config, dry_run):
    case = merge_case
    case.workflow.steps[0].config = config
    preparations = []
    validate_output_directory = processor_module.validate_output_directory

    def observe_preparation(output_dir):
        preparations.append(output_dir)
        return validate_output_directory(output_dir)

    monkeypatch.setattr(processor_module, "validate_output_directory", observe_preparation)
    stats = case.processor.process_batch([], case.workflow, str(case.out), dry_run=dry_run)

    assert preparations == []
    assert case.begun == case.consumed == case.finalized == []
    assert not case.out.exists()
    assert stats.total_files == stats.processed_files == stats.skipped_files == 0
    assert stats.failed_files == 1 and len(stats.errors) == 1
    assert "no input files" in stats.errors[0]["error"].lower()
    assert stats.errors[0]["file"] == "pdf_merge"
    assert stats.results == []
    assert_settled(case.processor, stats)


def test_aggregate_success_publishes_only_after_finalize(merge_case):
    case = merge_case
    # Multi-page inputs make within-file order observable as well.
    source = Path(case.files[0])
    writer = PdfWriter()
    writer.add_blank_page(width=602, height=500)
    writer.add_blank_page(width=702, height=500)
    with source.open("wb") as stream:
        writer.write(stream)
    progress_outputs = []
    case.processor.set_progress_callback(
        lambda *_: progress_outputs.append([record["output"] for record in case.processor.stats.results])
    )
    stats = case.processor.process_batch(case.files, case.workflow, str(case.out))

    merged = case.out / "merged.pdf"
    assert len(case.begun) == len(case.finalized) == 1
    assert case.consumed == list(map(Path, case.files))
    assert stats.total_files == stats.processed_files == 3
    assert stats.failed_files == 0 and stats.errors == []
    assert list(case.out.iterdir()) == [merged]
    assert [float(page.mediabox.width) for page in PdfReader(merged).pages] == [602, 702, 401, 400]
    assert [record["file"] for record in stats.results] == case.files
    assert {record["output"] for record in stats.results} == {str(merged)}
    assert all(not any(outputs) for outputs in progress_outputs[:-1])
    assert progress_outputs[-1] == [str(merged)] * 3
    assert_settled(case.processor, stats)


@pytest.mark.parametrize("consumed_count", [0, 1, 3], ids=["before-first", "between-inputs", "after-last"])
@pytest.mark.parametrize("paused", [False, True], ids=["stop", "pause-stop"])
def test_aggregate_stop_before_finalize(merge_case, monkeypatch, consumed_count, paused):
    case = merge_case
    boundary_reached = threading.Event()
    release_boundary = threading.Event()
    results = []
    errors = []

    def wait_for_stop(_interval):
        assert case.processor.is_paused
        boundary_reached.set()
        assert release_boundary.wait(timeout=5)

    def stop_at_boundary(current, total, message):
        if current == consumed_count:
            if paused:
                case.processor.pause()
            else:
                boundary_reached.set()
                assert release_boundary.wait(timeout=5)

    def run_batch():
        try:
            results.append(case.processor.process_batch(case.files, case.workflow, str(case.out)))
        except BaseException as exc:
            errors.append(exc)

    if paused:
        # Exercise the real pause loop, replacing only its timed wait with events.
        monkeypatch.setattr(processor_module.time, "sleep", wait_for_stop)
    case.processor.set_progress_callback(stop_at_boundary)
    worker = threading.Thread(target=run_batch, daemon=True)
    worker.start()
    try:
        assert boundary_reached.wait(timeout=5)
        assert len(case.consumed) == consumed_count
        assert case.finalized == []
        case.processor.stop()
    finally:
        release_boundary.set()
        worker.join(timeout=5)

    assert not worker.is_alive(), "Aggregate stop did not settle"
    assert errors == []
    stats = results[0]
    assert len(case.consumed) == consumed_count
    assert case.finalized == []
    assert not list(case.out.iterdir())
    assert stats.processed_files == consumed_count and stats.failed_files == 0
    assert_no_completed_output(stats)
    assert_settled(case.processor, stats)

    case.processor.set_progress_callback(None)
    next_stats = case.processor.process_batch(case.files, case.workflow, str(case.out))
    assert next_stats.processed_files == 3 and next_stats.failed_files == 0
    assert len(PdfReader(case.out / "merged.pdf").pages) == 3
    assert_no_completed_output(stats)
    assert_settled(case.processor, next_stats)


def test_aggregate_success_failure_stop_success_has_fresh_state(merge_case, monkeypatch):
    case = merge_case
    first = case.processor.process_batch(case.files, case.workflow, str(case.out))
    first_output = case.out / "merged.pdf"
    original_bytes = first_output.read_bytes()
    assert first.processed_files == 3 and first.failed_files == 0
    assert_settled(case.processor, first)

    def fail_write(_writer, stream):
        stream.write(b"partial merge")
        raise OSError("injected finalize failure")

    with monkeypatch.context() as patch:
        patch.setattr(PdfWriter, "write", fail_write)
        failed = case.processor.process_batch(case.files[:2], case.workflow, str(case.out))

    assert failed.processed_files == 2 and failed.failed_files == 1
    assert failed.errors[0]["file"] == "pdf_merge_finalize"
    assert "injected finalize failure" in failed.errors[0]["error"]
    assert_no_completed_output(failed)
    assert_settled(case.processor, failed)
    assert list(case.out.iterdir()) == [first_output]
    assert first_output.read_bytes() == original_bytes

    case.processor.set_progress_callback(lambda current, *_: case.processor.stop() if current == 1 else None)
    stopped = case.processor.process_batch(case.files, case.workflow, str(case.out))
    assert stopped.processed_files == 1 and stopped.failed_files == 0
    assert_no_completed_output(stopped)
    assert_settled(case.processor, stopped)
    assert list(case.out.iterdir()) == [first_output]

    case.processor.set_progress_callback(None)
    last = case.processor.process_batch(case.files[-1:], case.workflow, str(case.out))
    last_output = case.out / "merged_001.pdf"
    assert last.processed_files == 1 and last.failed_files == 0
    assert {record["output"] for record in last.results} == {str(last_output)}
    assert set(case.out.iterdir()) == {first_output, last_output}
    assert [float(page.mediabox.width) for page in PdfReader(last_output).pages] == [400]
    assert first_output.read_bytes() == original_bytes
    assert len({id(operation) for operation in case.begun}) == 4
    assert len({id(operation._writer) for operation in case.begun}) == 4
    assert [operation._consumed for operation in case.begun] == [3, 2, 1, 1]
    assert [len(operation._writer.pages) for operation in case.begun] == [3, 2, 1, 1]
    assert case.finalized == [case.begun[0], case.begun[1], case.begun[3]]
    assert_no_completed_output(failed)
    assert_no_completed_output(stopped)
    assert_settled(case.processor, last)


def test_aggregate_dry_run_reports_plan_without_completed_output(merge_case):
    case = merge_case
    stats = case.processor.process_batch(case.files, case.workflow, str(case.out), dry_run=True)

    assert stats.processed_files == 3 and stats.failed_files == 0
    assert len(case.begun) == len(case.finalized) == 1
    assert case.begun[0]._writer is None
    assert case.consumed == list(map(Path, case.files))
    assert not list(case.out.iterdir())
    assert_no_completed_output(stats)
    assert {record["result"]["planned_output"] for record in stats.results} == {str(case.out / "merged.pdf")}
    assert_settled(case.processor, stats)


@pytest.mark.parametrize("all_invalid", [False, True])
def test_aggregate_invalid_input_policy_is_preserved(merge_case, all_invalid):
    case = merge_case
    invalid = case.out.parent / "invalid.pdf"
    invalid.write_bytes(b"invalid PDF")
    sources = [str(invalid)] if all_invalid else [case.files[0], str(invalid), case.files[-1]]

    stats = case.processor.process_batch(sources, case.workflow, str(case.out))

    assert stats.total_files == len(sources)
    assert len(case.finalized) == 1
    if all_invalid:
        assert stats.processed_files == 0 and stats.failed_files == 2
        assert not list(case.out.iterdir())
        assert_no_completed_output(stats)
    else:
        assert stats.processed_files == 2 and stats.failed_files == 1
        merged = case.out / "merged.pdf"
        assert list(case.out.iterdir()) == [merged]
        assert [float(page.mediabox.width) for page in PdfReader(merged).pages] == [402, 400]
    assert_settled(case.processor, stats)


@pytest.mark.parametrize(
    "invalid_part, expected_error",
    [
        ("name", "Workflow must have a name"),
        ("config", "config 'output_filename' must be str"),
        ("predecessor", "only enabled step"),
        ("multiple", "only enabled step"),
    ],
)
def test_empty_aggregate_still_validates_workflow(merge_case, invalid_part, expected_error):
    case = merge_case
    if invalid_part == "name":
        case.workflow.name = ""
    elif invalid_part == "config":
        case.workflow.steps[0].config["output_filename"] = 123
    elif invalid_part == "predecessor":
        case.workflow.add_step("file_rename")
        case.workflow.move_step(1, 0)
    else:
        case.workflow.add_step("pdf_merge")

    stats = case.processor.process_batch([], case.workflow, str(case.out))

    assert stats.failed_files >= 1
    assert all(error["file"] == "workflow" for error in stats.errors)
    assert any(expected_error in error["error"] for error in stats.errors)
    assert not any("No input files" in error["error"] for error in stats.errors)
    assert stats.results == []
    assert stats.processed_files == 0
    assert case.begun == case.consumed == case.finalized == []
    assert not case.out.exists()
    assert_settled(case.processor, stats)
