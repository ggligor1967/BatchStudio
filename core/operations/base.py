from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from core.contracts import (
    OperationResult, OperationPlan, PlanDiagnostic, CheckOutcome,
)
from core.security import OutputPathAllocator, resolve_safe_output


def validate_schema_config(config: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> tuple[bool, str]:
    for key, rules in schema.items():
        if key not in config:
            if rules.get("required", False):
                return False, f"config '{key}' is required"
            continue
        value = config[key]
        expected = rules.get("type")
        if expected == "int" and (isinstance(value, bool) or not isinstance(value, int)):
            return False, f"config '{key}' must be int"
        if expected == "float" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            return False, f"config '{key}' must be float"
        if expected == "bool" and not isinstance(value, bool):
            return False, f"config '{key}' must be bool"
        if expected == "str" and not isinstance(value, str):
            return False, f"config '{key}' must be str"
        if rules.get("non_empty", False) and (not isinstance(value, str) or not value.strip()):
            return False, f"config '{key}' must be a non-empty string"
        if expected == "choice":
            choices = rules.get("choices", [])
            if value not in choices:
                return False, f"config '{key}' must be one of {choices}"
    return True, ""


class Operation(ABC):
    id = "operation"
    name = "Operation"
    description = ""
    accepted_types = {"any"}
    output_type = "any"
    supports_dry_run = True
    supports_planning = False
    requires_ocr = False

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(config) if config is not None else {}
        self.output_allocator: Optional[OutputPathAllocator] = None

    def plan(self, artifact, step_index):
        return OperationPlan((PlanDiagnostic(
            step_index, self.id, "planning_support", "structure", CheckOutcome.UNSUPPORTED,
            f"Operation {self.name} does not support planning",
        ),))

    def plan_output_path(self, artifact, candidate, context, counter):
        # Resolvers receive lexical names only, never a materialized-input claim.
        return self.resolve_output_path(Path(artifact.name), candidate)

    def _plan_standard(self, artifact, step_index, *, facts=(), logical_format=None,
                       suffix=None, accepted_types=None, unknown_properties=()):
        checks = []
        accepted = self.accepted_types if accepted_types is None else accepted_types
        if "any" in accepted or artifact.logical_type in accepted:
            outcome, reason = CheckOutcome.CHECKED, "Declared input type is compatible"
        elif artifact.logical_type == "UNKNOWN":
            outcome, reason = CheckOutcome.DEFERRED, "Concrete input type requires generated content"
        else:
            outcome, reason = CheckOutcome.FAILED, f"Expected {sorted(accepted)}, got {artifact.logical_type}"
        checks.append(PlanDiagnostic(step_index, self.id, "input_type", "structure", outcome, reason))
        if artifact.state == "MATERIALIZED_SOURCE" and outcome != CheckOutcome.FAILED:
            valid = self.validate(Path(artifact.origin_id[1]))
            checks.append(PlanDiagnostic(
                step_index, self.id, "source_content", "source",
                CheckOutcome.CHECKED if valid else CheckOutcome.FAILED,
                "Existing source validator passed" if valid else f"Operation {self.name} cannot process this file",
            ))
        elif artifact.state == "PLANNED":
            checks.append(PlanDiagnostic(
                step_index, self.id, "intermediate_content", "generated_content", CheckOutcome.DEFERRED,
                "Generated input bytes have not been materialized or validated",
                (f"step:{artifact.producer_step[0]}:success",),
            ))
        checks.append(PlanDiagnostic(
            step_index, self.id, "execution", "execution", CheckOutcome.DEFERRED,
            "Production, generated content validity, mutable inputs/capabilities, future write permission "
            "and exclusive output ownership require normal execution",
        ))
        output_type = artifact.logical_type if self.output_type == "same" else self.output_type
        return OperationPlan(
            tuple(checks), "UNKNOWN" if output_type == "any" else output_type,
            logical_format, artifact.suffix if suffix is None else suffix, tuple(facts),
            ("generated_bytes", "size", "parseability") + tuple(unknown_properties),
        )

    def resolve_output_path(self, file_path: Path, output_path: Path) -> Path:
        return output_path

    def execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        try:
            intended = self.resolve_output_path(file_path, output_path)
            destination = resolve_safe_output(output_path.parent, intended.name)
            if self.output_allocator is not None:
                destination = self.output_allocator.allocate(destination.stem, destination.suffix)
            return self._execute(file_path, destination, dry_run)
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    @abstractmethod
    def _execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def validate(self, file_path: Path) -> bool:
        raise NotImplementedError

    def get_config_schema(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def get_capability_error(self) -> Optional[str]:
        return None

    def validate_config(self) -> tuple[bool, str]:
        return validate_schema_config(self.config, self.get_config_schema())


class AggregateOperation(ABC):
    id = "aggregate"
    name = "Aggregate"
    description = ""
    accepted_types = {"pdf"}
    output_type = "pdf"
    supports_dry_run = True

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(config) if config is not None else {}

    def get_config_schema(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def validate_config(self) -> tuple[bool, str]:
        return validate_schema_config(self.config, self.get_config_schema())

    @abstractmethod
    def begin(self, output_path: Path, dry_run: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def consume(self, file_path: Path) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def finalize(self) -> OperationResult:
        raise NotImplementedError
