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
