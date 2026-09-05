"""V11-03: generic schema constraints and fail-closed CSV filtering."""

import pandas as pd
import pytest

from core.operations.base import AggregateOperation, Operation
from core.operations.data_ops import CSVFilterOperation
from core.operations import OperationRegistry
from core.processor import BatchProcessor, compile_workflow
from core.workflow import Workflow


INVALID_COLUMNS = [{}, {"column": None}, {"column": ""}, {"column": " \t\n"}, {"column": 12}]


class SyntheticOperation(Operation):
    def get_config_schema(self):
        return {
            "label": {"type": "str", "required": True, "non_empty": True},
            "ratio": {"type": "float"},
        }

    def validate(self, file_path):
        return True

    def _execute(self, file_path, output_path, dry_run=False):
        raise AssertionError("Schema-only operation must not execute")


class SyntheticAggregate(AggregateOperation):
    get_config_schema = SyntheticOperation.get_config_schema

    def begin(self, output_path, dry_run=False):
        raise AssertionError("Schema-only aggregate must not begin")

    def consume(self, file_path):
        raise AssertionError("Schema-only aggregate must not consume")

    def finalize(self):
        raise AssertionError("Schema-only aggregate must not finalize")


@pytest.mark.parametrize("config,valid", [
    ({}, False), ({"label": None}, False), ({"label": 7}, False),
    ({"label": ""}, False), ({"label": " \t\n"}, False),
    ({"label": "name"}, True), ({"label": " name "}, True),
])
def test_generic_required_nonempty_validator_parity(config, valid):
    file_result = SyntheticOperation(config).validate_config()
    aggregate_result = SyntheticAggregate(config).validate_config()
    assert file_result == aggregate_result
    assert file_result[0] is valid
    if not valid:
        assert "label" in file_result[1]


@pytest.mark.parametrize("value,valid", [(1, True), (1.5, True), ("1.5", False), (None, False), ([], False)])
def test_generic_float_validator_parity(value, valid):
    config = {"label": "valid", "ratio": value}
    file_result = SyntheticOperation(config).validate_config()
    assert file_result == SyntheticAggregate(config).validate_config()
    assert file_result[0] is valid
    if not valid:
        assert "ratio" in file_result[1] and "float" in file_result[1]


@pytest.fixture
def csv_source(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("status,amount\nactive,1\ninactive,3\nactive,5\n", encoding="utf-8")
    return source


@pytest.mark.parametrize("config", INVALID_COLUMNS)
def test_csv_invalid_column_fails_compilation(config):
    workflow = Workflow("invalid CSV configuration")
    workflow.add_step("csv_filter", config)
    compilation = compile_workflow(workflow, OperationRegistry())
    assert not compilation.valid
    assert any("Invalid config" in error and "column" in error for error in compilation.errors)


@pytest.mark.parametrize("config", INVALID_COLUMNS)
@pytest.mark.parametrize("dry_run", [False, True])
def test_direct_csv_invalid_config_creates_no_output(csv_source, tmp_path, config, dry_run):
    output = tmp_path / "output.csv"
    result = CSVFilterOperation(config).execute(csv_source, output, dry_run=dry_run)
    assert not result.success
    assert "column" in result.error
    assert result.output_path is None
    assert "Filtered" not in result.message
    assert not output.exists()


@pytest.mark.parametrize("dry_run", [False, True])
def test_csv_missing_concrete_column_fails(csv_source, tmp_path, dry_run):
    config = {"column": "missing", "operator": "==", "value": "active"}
    workflow = Workflow("runtime columns")
    workflow.add_step("csv_filter", config)
    assert compile_workflow(workflow, OperationRegistry()).valid
    output = tmp_path / "output.csv"
    result = CSVFilterOperation(config).execute(csv_source, output, dry_run=dry_run)
    assert not result.success
    assert "missing" in result.error and "column" in result.error.lower()
    assert result.output_path is None and "Filtered" not in result.message
    assert not output.exists()
    stats = BatchProcessor(1).process_batch([str(csv_source)], workflow, str(tmp_path / "out"), dry_run=dry_run)
    assert stats.failed_files == 1 and stats.processed_files == 0
    assert not list((tmp_path / "out").glob("*.csv"))


@pytest.mark.parametrize("column,operator,value,amounts", [
    ("status", "==", "active", [1, 5]),
    ("status", "==", "no matches", []),
    ("amount", ">", "2", [3, 5]),
    ("amount", "<", "4", [1, 3]),
])
def test_csv_valid_filters_write_correct_rows(csv_source, tmp_path, column, operator, value, amounts):
    config = {"column": column, "operator": operator, "value": value}
    output = tmp_path / "output.csv"
    result = CSVFilterOperation(config).execute(csv_source, output)
    assert result.success, result.error
    assert result.metadata == {"original_rows": 3, "filtered_rows": len(amounts)}
    actual = pd.read_csv(output)
    assert list(actual.columns) == ["status", "amount"]
    assert actual["amount"].tolist() == amounts
    workflow = Workflow("normal CSV")
    workflow.add_step("csv_filter", config)
    stats = BatchProcessor(1).process_batch([str(csv_source)], workflow, str(tmp_path / "batch"))
    assert stats.failed_files == 0 and stats.processed_files == 1
    assert pd.read_csv(stats.results[0]["output"])["amount"].tolist() == amounts


@pytest.mark.parametrize("operator", [">", "<"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_csv_malformed_numeric_operand_fails(csv_source, tmp_path, operator, dry_run):
    output = tmp_path / "output.csv"
    result = CSVFilterOperation({"column": "amount", "operator": operator, "value": "not numeric"}).execute(
        csv_source, output, dry_run=dry_run
    )
    assert not result.success and result.error
    assert result.output_path is None and not output.exists()


@pytest.mark.parametrize("operator,value,rows", [("==", "active", 2), ("==", "absent", 0)])
def test_csv_dry_run_evaluates_counts_without_output(csv_source, tmp_path, operator, value, rows):
    output = tmp_path / "output.csv"
    result = CSVFilterOperation({"column": "status", "operator": operator, "value": value}).execute(
        csv_source, output, dry_run=True
    )
    assert result.success and result.metadata == {"original_rows": 3, "filtered_rows": rows}
    assert not output.exists()
