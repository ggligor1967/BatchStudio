"""V12-02: compiler, preflight, and aggregate runtime semantic agreement."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from pypdf import PdfReader

import core.processor as processor_module
from core.operations import OperationRegistry
from core.operations.file_ops import FileRenameOperation
from core.operations.pdf_ops import PDFAggregateMergeOperation
from core.processor import BatchProcessor, compile_workflow, process_single_file
from core.workflow import Workflow
from tests.pdf_merge_cases import make_pdf_inputs
from ui.run_panel import RunPanel


VALID_CONFIGS = {
    "image_resize": {},
    "image_convert": {},
    "image_filter": {},
    "pdf_watermark": {},
    "csv_filter": {"column": "value"},
    "file_rename": {},
    "ocr_image": {},
    "ocr_pdf": {"mode": "native"},
    "ocr_batch": {},
}


def aggregate_workflow() -> Workflow:
    workflow = Workflow("aggregate-only")
    workflow.add_step("pdf_merge", {"output_filename": "merged.pdf"})
    return workflow


def assert_settled(processor: BatchProcessor, stats) -> None:
    assert processor.stats is stats
    assert processor.is_running is False
    assert processor.is_paused is False
    assert stats.start_time is not None and stats.end_time is not None


def test_registry_execution_classes_are_completely_accounted_for():
    registry = OperationRegistry()

    assert set(registry.operations) == set(VALID_CONFIGS)
    assert set(registry.aggregate_operations) == {"pdf_merge"}


def test_compiled_aggregate_plan_declares_original_pdf_inputs():
    compilation = compile_workflow(aggregate_workflow(), OperationRegistry())

    assert compilation.valid and compilation.errors == []
    assert compilation.execution_mode == "aggregate"
    assert compilation.enabled_operation_ids == ("pdf_merge",)
    assert compilation.aggregate_operation_id == "pdf_merge"
    assert compilation.aggregate_input_source == "original_inputs"
    assert compilation.accepted_input_types == frozenset({"pdf"})


def test_compiled_per_file_plan_declares_every_enabled_step_in_order():
    workflow = Workflow("per-file")
    workflow.add_step("image_resize")
    workflow.add_step("file_rename")

    compilation = compile_workflow(workflow, OperationRegistry())

    assert compilation.valid and compilation.errors == []
    assert compilation.execution_mode == "per_file"
    assert compilation.enabled_operation_ids == ("image_resize", "file_rename")
    assert compilation.aggregate_operation_id is None
    assert compilation.aggregate_input_source is None
    assert compilation.accepted_input_types == frozenset()


@pytest.mark.parametrize("operation_id", sorted(VALID_CONFIGS))
def test_every_per_file_operation_is_rejected_before_aggregate(operation_id):
    workflow = Workflow("unsupported-composition")
    workflow.add_step(operation_id, VALID_CONFIGS[operation_id])
    workflow.add_step("pdf_merge")

    compilation = compile_workflow(workflow, OperationRegistry())

    assert not compilation.valid
    assert any("only enabled step" in error for error in compilation.errors)
    assert compilation.execution_mode is None
    assert compilation.enabled_operation_ids == ()
    assert compilation.aggregate_operation_id is None


@pytest.mark.parametrize(
    "operation_ids, expected_fragments",
    [
        (("file_rename", "pdf_watermark", "pdf_merge"), ("only enabled step",)),
        (("pdf_merge", "file_rename"), ("only enabled step", "last enabled")),
        (("pdf_merge", "pdf_merge"), ("only enabled step",)),
        (("ocr_pdf", "pdf_merge"), ("only enabled step",)),
    ],
    ids=("two-predecessors", "aggregate-before-per-file", "two-aggregates", "type-changing-predecessor"),
)
def test_unsupported_aggregate_shapes_have_no_executable_plan(operation_ids, expected_fragments):
    workflow = Workflow("unsupported-shape")
    for operation_id in operation_ids:
        workflow.add_step(operation_id, VALID_CONFIGS.get(operation_id, {}))

    compilation = compile_workflow(workflow, OperationRegistry())

    assert not compilation.valid
    assert all(any(fragment in error for error in compilation.errors) for fragment in expected_fragments)
    assert compilation.execution_mode is None
    assert compilation.enabled_operation_ids == ()


def test_disabled_steps_are_absent_from_the_aggregate_plan():
    workflow = Workflow("disabled-steps")
    workflow.add_step("ocr_pdf", {"mode": "native"}).enabled = False
    workflow.add_step("pdf_merge")
    workflow.add_step("file_rename").enabled = False

    compilation = compile_workflow(workflow, OperationRegistry())

    assert compilation.valid
    assert compilation.enabled_operation_ids == ("pdf_merge",)
    assert compilation.aggregate_input_source == "original_inputs"


@pytest.mark.parametrize("extensions", [(".csv",), (".pdf", ".csv")], ids=("homogeneous", "mixed"))
def test_incompatible_aggregate_input_types_fail_before_output_preparation(
    tmp_path, monkeypatch, extensions
):
    sources = []
    pdf_inputs = iter(make_pdf_inputs(tmp_path, extensions.count(".pdf")))
    for index, extension in enumerate(extensions):
        if extension == ".pdf":
            sources.append(next(pdf_inputs))
        else:
            source = tmp_path / f"input-{index}{extension}"
            source.write_text("value\n1\n", encoding="utf-8")
            sources.append(str(source))

    prepare = Mock(side_effect=AssertionError("output preparation reached"))
    begin = Mock(side_effect=AssertionError("aggregate begin reached"))
    consume = Mock(side_effect=AssertionError("aggregate consume reached"))
    finalize = Mock(side_effect=AssertionError("aggregate finalize reached"))
    monkeypatch.setattr(processor_module, "validate_output_directory", prepare)
    monkeypatch.setattr(PDFAggregateMergeOperation, "begin", begin)
    monkeypatch.setattr(PDFAggregateMergeOperation, "consume", consume)
    monkeypatch.setattr(PDFAggregateMergeOperation, "finalize", finalize)
    processor = BatchProcessor(1)

    stats = processor.process_batch(sources, aggregate_workflow(), str(tmp_path / "out"))

    prepare.assert_not_called()
    begin.assert_not_called()
    consume.assert_not_called()
    finalize.assert_not_called()
    assert stats.processed_files == 0
    assert stats.results == []
    assert any("PDF Merge" in error["error"] for error in stats.errors)
    assert any("expected input type" in error["error"] and "csv" in error["error"] for error in stats.errors)
    assert not (tmp_path / "out").exists()
    assert_settled(processor, stats)


def test_missing_aggregate_input_fails_before_output_preparation(tmp_path, monkeypatch):
    source = tmp_path / "missing.pdf"
    prepare = Mock(side_effect=AssertionError("output preparation reached"))
    begin = Mock(side_effect=AssertionError("aggregate begin reached"))
    monkeypatch.setattr(processor_module, "validate_output_directory", prepare)
    monkeypatch.setattr(PDFAggregateMergeOperation, "begin", begin)
    processor = BatchProcessor(1)

    stats = processor.process_batch(
        [str(source)], aggregate_workflow(), str(tmp_path / "out")
    )

    prepare.assert_not_called()
    begin.assert_not_called()
    assert stats.processed_files == 0
    assert stats.results == []
    assert stats.errors[0]["file"] == str(source)
    assert "input preflight failed" in stats.errors[0]["error"]
    assert "does not exist" in stats.errors[0]["error"]
    assert not (tmp_path / "out").exists()
    assert_settled(processor, stats)


def test_aggregate_consumes_original_inputs_in_declared_order(tmp_path, monkeypatch):
    sources = make_pdf_inputs(tmp_path, 3)
    consumed = []
    original_consume = PDFAggregateMergeOperation.consume

    def observe_consume(operation, file_path):
        consumed.append(file_path)
        return original_consume(operation, file_path)

    monkeypatch.setattr(PDFAggregateMergeOperation, "consume", observe_consume)
    stats = BatchProcessor(1).process_batch(sources, aggregate_workflow(), str(tmp_path / "out"))

    assert consumed == list(map(Path, sources))
    assert stats.processed_files == 3 and stats.failed_files == 0
    assert len(PdfReader(stats.results[0]["output"]).pages) == 3


def test_per_file_worker_rejects_aggregate_instead_of_skipping_it(tmp_path, monkeypatch):
    source = make_pdf_inputs(tmp_path, 1)[0]
    begin = Mock(side_effect=AssertionError("aggregate begin reached"))
    monkeypatch.setattr(PDFAggregateMergeOperation, "begin", begin)

    result = process_single_file(
        source, aggregate_workflow().to_dict(), str(tmp_path / "out"), "planned"
    )

    begin.assert_not_called()
    assert not result["success"]
    assert "aggregate" in result["error"].lower()
    assert "batch" in result["error"].lower()
    assert not (tmp_path / "out").exists()


def test_per_file_worker_rejects_mixed_shape_before_predecessor_execution(
    tmp_path, monkeypatch
):
    source = make_pdf_inputs(tmp_path, 1)[0]
    execute = Mock(side_effect=AssertionError("per-file predecessor executed"))
    monkeypatch.setattr(FileRenameOperation, "execute", execute)
    workflow = Workflow("unsupported-direct-worker-shape")
    workflow.add_step("file_rename")
    workflow.add_step("pdf_merge")

    result = process_single_file(
        source, workflow.to_dict(), str(tmp_path / "out"), "planned"
    )

    execute.assert_not_called()
    assert not result["success"]
    assert "aggregate" in result["error"].lower()
    assert "batch" in result["error"].lower()
    assert not (tmp_path / "out").exists()


def test_run_preflight_reports_composition_error_before_input_interpretation(tmp_path):
    source = tmp_path / "input.png"
    source.write_bytes(b"not an image")
    workflow = Workflow("unsupported-composition")
    workflow.add_step("file_rename")
    workflow.add_step("pdf_merge")
    panel = RunPanel.__new__(RunPanel)
    panel.processor = Mock()
    panel.frame = Mock()
    panel._processing_error = Mock()
    panel._processing_started = Mock()
    panel._processing_complete = Mock()

    panel._run_batch([str(source)], workflow, str(tmp_path / "out"), "{original}", False, False)
    for call in panel.frame.after.call_args_list:
        _, callback, *args = call.args
        callback(*args)

    panel.processor.process_batch.assert_not_called()
    panel._processing_started.assert_not_called()
    assert "only enabled step" in panel._processing_error.call_args.args[0]
    assert not (tmp_path / "out").exists()


def test_run_preflight_rejects_incompatible_aggregate_input_before_processor(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    panel = RunPanel.__new__(RunPanel)
    panel.processor = Mock()
    panel.frame = Mock()
    panel._processing_error = Mock()
    panel._processing_started = Mock()
    panel._processing_complete = Mock()

    panel._run_batch(
        [str(source)], aggregate_workflow(), str(tmp_path / "out"), "{original}", False, False
    )
    for call in panel.frame.after.call_args_list:
        _, callback, *args = call.args
        callback(*args)

    panel.processor.process_batch.assert_not_called()
    panel._processing_started.assert_not_called()
    assert "Unsupported input for PDF Merge: csv" in panel._processing_error.call_args.args[0]
    assert not (tmp_path / "out").exists()


def test_aggregate_begin_exception_is_reported_and_settled(tmp_path, monkeypatch):
    source = make_pdf_inputs(tmp_path, 1)[0]
    consume = Mock(side_effect=AssertionError("consume reached"))
    finalize = Mock(side_effect=AssertionError("finalize reached"))

    def fail_begin(_operation, _output_path, dry_run=False):
        raise OSError("injected begin failure")

    monkeypatch.setattr(PDFAggregateMergeOperation, "begin", fail_begin)
    monkeypatch.setattr(PDFAggregateMergeOperation, "consume", consume)
    monkeypatch.setattr(PDFAggregateMergeOperation, "finalize", finalize)
    processor = BatchProcessor(1)

    stats = processor.process_batch([source], aggregate_workflow(), str(tmp_path / "out"))

    consume.assert_not_called()
    finalize.assert_not_called()
    assert stats.processed_files == 0 and stats.failed_files == 1
    assert stats.errors[0]["file"] == "pdf_merge_begin"
    assert "injected begin failure" in stats.errors[0]["error"]
    assert stats.results == []
    assert not list((tmp_path / "out").iterdir())
    assert_settled(processor, stats)


def test_aggregate_consume_exception_is_an_input_failure_and_other_inputs_finalize(
    tmp_path, monkeypatch
):
    sources = make_pdf_inputs(tmp_path, 3)
    original_consume = PDFAggregateMergeOperation.consume

    def fail_middle_consume(operation, file_path):
        if file_path == Path(sources[1]):
            raise OSError("injected consume failure")
        return original_consume(operation, file_path)

    monkeypatch.setattr(PDFAggregateMergeOperation, "consume", fail_middle_consume)
    processor = BatchProcessor(1)

    stats = processor.process_batch(sources, aggregate_workflow(), str(tmp_path / "out"))

    assert stats.processed_files == 2 and stats.failed_files == 1
    assert stats.errors[0]["file"] == sources[1]
    assert "injected consume failure" in stats.errors[0]["error"]
    assert len(PdfReader(stats.results[0]["output"]).pages) == 2
    assert {record["file"] for record in stats.results} == {sources[0], sources[2]}
    assert_settled(processor, stats)


def test_aggregate_finalize_exception_is_reported_without_completed_output(tmp_path, monkeypatch):
    sources = make_pdf_inputs(tmp_path, 2)

    def fail_finalize(_operation):
        raise OSError("injected finalize failure")

    monkeypatch.setattr(PDFAggregateMergeOperation, "finalize", fail_finalize)
    processor = BatchProcessor(1)

    stats = processor.process_batch(sources, aggregate_workflow(), str(tmp_path / "out"))

    assert stats.processed_files == 2 and stats.failed_files == 1
    assert stats.errors[-1]["file"] == "pdf_merge_finalize"
    assert "injected finalize failure" in stats.errors[-1]["error"]
    assert all(not record["output"] for record in stats.results)
    assert not list((tmp_path / "out").iterdir())
    assert_settled(processor, stats)
