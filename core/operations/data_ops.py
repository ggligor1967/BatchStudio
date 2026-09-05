from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.contracts import OperationResult
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
            df = pd.read_csv(file_path)
            original_rows = len(df)
            column = self.config.get("column")
            operator = self.config.get("operator", "==")
            value = self.config.get("value")

            if column and column in df.columns:
                if operator == "==":
                    df = df[df[column] == value]
                elif operator == "!=":
                    df = df[df[column] != value]
                elif operator == ">":
                    df = df[df[column] > float(value)]
                elif operator == "<":
                    df = df[df[column] < float(value)]
                elif operator == "contains":
                    df = df[df[column].astype(str).str.contains(str(value), na=False)]

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

    def validate(self, file_path: Path) -> bool:
        try:
            pd.read_csv(file_path)
            return True
        except Exception:
            return False

    def get_config_schema(self):
        return {
            "column": {"type": "str", "default": ""},
            "operator": {"type": "choice", "default": "==", "choices": ["==", "!=", ">", "<", "contains"]},
            "value": {"type": "str", "default": ""},
        }
