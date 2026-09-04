from __future__ import annotations

from datetime import datetime
from pathlib import Path

import shutil

from core.contracts import OperationResult
from core.operations.base import Operation
from core.security import sanitize_filename


class FileRenameOperation(Operation):
    id = "file_rename"
    name = "File Rename"
    description = "Rename files using patterns"
    accepted_types = {"any"}
    output_type = "same"

    def execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        pattern = self.config.get("pattern", "{original}_{counter}")
        counter = self.config.get("counter", 1)
        original_stem = file_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_stem = (
            str(pattern)
            .replace("{original}", original_stem)
            .replace("{counter}", f"{int(counter):03d}")
            .replace("{timestamp}", timestamp)
        )
        target = output_path.with_name(sanitize_filename(new_stem) + output_path.suffix)

        if dry_run:
            return OperationResult(success=True, output_path=target, message=f"Dry run rename to {target.name}")

        try:
            shutil.copy2(file_path, target)
            return OperationResult(success=True, output_path=target, message=f"Renamed to {target.name}")
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        return file_path.is_file()

    def get_config_schema(self):
        return {"pattern": {"type": "str", "default": "{original}_{counter}"}}
