import pytest

from core.operations import OperationRegistry
from core.processor import compile_workflow
from core.workflow import Workflow


def test_workflow_rejects_missing_name_or_steps():
    wf = Workflow("")
    ok, error = wf.validate()
    assert ok is False
    assert error


def test_workflow_compile_unknown_operation():
    wf = Workflow("bad-op")
    wf.add_step("does_not_exist", {})

    report = compile_workflow(wf, OperationRegistry())
    assert report.valid is False
    assert any("Unknown operation" in e for e in report.errors)


def test_workflow_compile_invalid_config_type():
    wf = Workflow("bad-config")
    wf.add_step("image_resize", {"width": "wrong", "height": 10})

    report = compile_workflow(wf, OperationRegistry())
    assert report.valid is False
    assert any("Invalid config" in e for e in report.errors)


def test_workflow_compile_type_incompatibility():
    wf = Workflow("type-mismatch")
    wf.add_step("csv_filter", {"column": "a", "operator": "==", "value": "x"})
    wf.add_step("image_resize", {"width": 10, "height": 10, "maintain_aspect": False})

    report = compile_workflow(wf, OperationRegistry())
    assert report.valid is False
    assert any("Type incompatibility" in e for e in report.errors)


def test_workflow_compile_aggregate_must_be_last():
    wf = Workflow("merge-middle")
    wf.add_step("pdf_merge", {"output_filename": "merged.pdf"})
    wf.add_step("pdf_watermark", {"text": "X"})

    report = compile_workflow(wf, OperationRegistry())
    assert report.valid is False
    assert any("Aggregate operations" in e for e in report.errors)


@pytest.mark.parametrize("disabled_predecessor", [False, True])
def test_aggregate_only_enabled_step_compiles(disabled_predecessor):
    workflow = Workflow("aggregate-only")
    if disabled_predecessor:
        step = workflow.add_step("pdf_watermark", {"text": 123})
        step.enabled = False
    workflow.add_step("pdf_merge", {"output_filename": "merged.pdf"})

    report = compile_workflow(workflow, OperationRegistry())

    assert report.valid and report.errors == []
    assert report.aggregate_operation_id == "pdf_merge"


@pytest.mark.parametrize("predecessor", ["pdf_watermark", "file_rename"])
def test_aggregate_rejects_enabled_predecessor(predecessor):
    workflow = Workflow("unsupported-composition")
    workflow.add_step(predecessor)
    workflow.add_step("pdf_merge")

    report = compile_workflow(workflow, OperationRegistry())

    assert not report.valid
    assert any("only enabled step" in error and "Disable or remove" in error for error in report.errors)


def test_aggregate_rejects_multiple_enabled_aggregates():
    workflow = Workflow("multiple-merges")
    workflow.add_step("pdf_merge")
    workflow.add_step("pdf_merge")

    report = compile_workflow(workflow, OperationRegistry())

    assert not report.valid
    assert any("only enabled step" in error for error in report.errors)


def test_aggregate_ignores_disabled_successors():
    workflow = Workflow("disabled-successor")
    workflow.add_step("pdf_merge")
    workflow.add_step("file_rename").enabled = False

    report = compile_workflow(workflow, OperationRegistry())

    assert report.valid and report.errors == []


def test_non_aggregate_chain_compilation_is_unchanged():
    workflow = Workflow("per-file")
    workflow.add_step("image_resize", {"width": 10, "height": 10})
    workflow.add_step("file_rename", {"pattern": "{original}_done"})

    report = compile_workflow(workflow, OperationRegistry())

    assert report.valid and report.errors == []
    assert report.aggregate_operation_id is None
