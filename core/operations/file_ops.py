from __future__ import annotations

from datetime import datetime
from pathlib import Path

import shutil

from core.contracts import OperationResult, PlanFact
from core.operations.base import Operation
from core.security import exclusive_output, render_filename


class FileRenameOperation(Operation):
    id = "file_rename"
    name = "File Rename"
    description = "Rename files using patterns"
    accepted_types = {"any"}
    output_type = "same"

    def resolve_output_path(self, file_path: Path, output_path: Path) -> Path:
        pattern = self.config.get("pattern", "{original}_{counter}")
        counter = self.config.get("counter", 1)
        original_stem = file_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_stem = render_filename(str(pattern), original_stem, int(counter), timestamp)
        return output_path.with_name(new_stem + output_path.suffix)

    supports_planning = True

    def plan(self, artifact, step_index):
        facts = tuple(PlanFact(fact.name, fact.value, "DERIVED_CONTRACT",
                               fact.dependencies + (f"step:{step_index}:success", f"step:{step_index}:byte_copy"))
                      for fact in artifact.facts if fact.name != "source_identity")
        return self._plan_standard(artifact, step_index, facts=facts,
                                   logical_format=artifact.logical_format,
                                   unknown_properties=artifact.unknown_properties)

    def plan_output_path(self, artifact, candidate, context, counter):
        stem = render_filename(self.config.get("pattern", "{original}_{counter}"),
                               Path(artifact.name).stem, counter, context.timestamp)
        return candidate.with_name(stem + candidate.suffix)

    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        target = output_path
        if dry_run:
            return OperationResult(success=True, output_path=target, message=f"Dry run rename to {target.name}")

        try:
            with exclusive_output(target) as destination:
                with file_path.open("rb") as source:
                    shutil.copyfileobj(source, destination)
                # Closing the write handle can update mtime, so copy metadata afterward.
                destination.close()
                shutil.copystat(file_path, target)
            return OperationResult(success=True, output_path=target, message=f"Renamed to {target.name}")
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        return file_path.is_file()

    def get_config_schema(self):
        return {"pattern": {"type": "str", "default": "{original}_{counter}"}}
