from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

import pandas as pd

from core.contracts import OperationResult, PlanFact, PlanDiagnostic, CheckOutcome
from core.operations.base import Operation
from core.security import exclusive_output


class CSVFilterOperation(Operation):
    id = "csv_filter"
    name = "CSV Filter"
    description = "Filter CSV rows based on column conditions"
    accepted_types = {"csv"}
    output_type = "csv"

    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        try:
            valid, error = self.validate_config()
            if not valid:
                return OperationResult(success=False, error=f"Invalid CSV filter configuration: {error}")
            df = pd.read_csv(file_path)
            original_rows = len(df)

            df = self._filter_rows(df)

            if not dry_run:
                with exclusive_output(output_path, text=True, newline="") as stream:
                    df.to_csv(stream, index=False)

            return OperationResult(
                success=True,
                output_path=output_path,
                message=f"Filtered from {original_rows} to {len(df)} rows",
                metadata={"original_rows": original_rows, "filtered_rows": len(df)},
            )
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    supports_planning = True

    def _filter_rows(self, df):
        column = self.config.get("column")
        operator = self.config.get("operator", "==")
        value = self.config.get("value")
        if column not in df.columns:
            raise ValueError(f"CSV column {column!r} is missing from the input file")
        if operator == "==":
            return df[df[column] == value]
        if operator == "!=":
            return df[df[column] != value]
        if operator == ">":
            return df[df[column] > float(value)]
        if operator == "<":
            return df[df[column] < float(value)]
        if operator == "contains":
            return df[df[column].astype(str).str.contains(str(value), na=False)]
        return df

    def plan(self, artifact, step_index):
        plan = self._plan_standard(artifact, step_index, logical_format="CSV",
                                   unknown_properties=("values", "dtypes", "intermediate_row_count"))
        if any(check.outcome == CheckOutcome.FAILED for check in plan.diagnostics):
            return plan
        checks, facts = list(plan.diagnostics), []
        dependency = (f"step:{step_index}:success", f"step:{step_index}:row_filter_preserves_headers")
        try:
            if artifact.state == "MATERIALIZED_SOURCE":
                df = pd.read_csv(artifact.origin_id[1])
                filtered_rows = len(self._filter_rows(df))
                columns = tuple(df.columns)
                # Only simple unique header names have a supported serialization proof.
                stable = (all(isinstance(name, str) and name and name.strip() == name
                              and not any(char in name for char in '\r\n,\"')
                              and not name.startswith("Unnamed:") for name in columns)
                          and len(set(columns)) == len(columns))
                if stable:
                    facts.append(PlanFact("csv_columns", columns, "DERIVED_CONTRACT",
                                          ("source:parsed_headers",) + dependency))
                facts.extend((
                    PlanFact("original_rows", len(df), "OBSERVED_SOURCE", ("source:predicate_evaluation",)),
                    PlanFact("filtered_rows", filtered_rows, "OBSERVED_SOURCE", ("source:predicate_evaluation",)),
                ))
                checks.append(PlanDiagnostic(step_index, self.id, "csv_predicate", "source",
                                             CheckOutcome.CHECKED,
                                             f"Real-source predicate evaluated: {len(df)} to {filtered_rows} rows"))
                if not stable:
                    checks.append(PlanDiagnostic(step_index, self.id, "csv_headers", "metadata",
                                                 CheckOutcome.DEFERRED, "Header round-trip is not established"))
            else:
                column_fact = artifact.fact("csv_columns")
                if column_fact is not None:
                    if self.config["column"] not in column_fact.value:
                        raise ValueError(f"CSV column {self.config['column']!r} is missing from the planned schema")
                    facts.append(PlanFact("csv_columns", column_fact.value, "DERIVED_CONTRACT",
                                          column_fact.dependencies + dependency))
                checks.append(PlanDiagnostic(
                    step_index, self.id, "csv_column", "metadata",
                    CheckOutcome.CHECKED if column_fact else CheckOutcome.DEFERRED,
                    "Column belongs to the preserved schema" if column_fact else "Generated CSV schema is unknown",
                    column_fact.dependencies if column_fact else (),
                ))
                if self.config.get("operator", "==") in {">", "<"}:
                    float(self.config.get("value"))
                checks.append(PlanDiagnostic(step_index, self.id, "csv_predicate", "generated_content",
                                             CheckOutcome.DEFERRED,
                                             "Generated CSV parsing, values, dtypes and predicate count require execution"))
        except (ValueError, TypeError, KeyError, OSError, re.error) as exc:
            checks.append(PlanDiagnostic(step_index, self.id, "csv_predicate", "source" if artifact.state == "MATERIALIZED_SOURCE" else "metadata",
                                         CheckOutcome.FAILED, str(exc)))
        return replace(plan, diagnostics=tuple(checks), facts=tuple(facts))

    def validate(self, file_path: Path) -> bool:
        try:
            pd.read_csv(file_path)
            return True
        except Exception:
            return False

    def get_config_schema(self):
        return {
            "column": {"type": "str", "default": "", "required": True, "non_empty": True},
            "operator": {"type": "choice", "default": "==", "choices": ["==", "!=", ">", "<", "contains"]},
            "value": {"type": "str", "default": ""},
        }
