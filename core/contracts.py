from __future__ import annotations

from enum import Enum
import json
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(slots=True)
class OperationResult:
    success: bool
    message: str = ""
    output_path: Optional[Path] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "success": self.success,
            "message": self.message,
            "metadata": self.metadata,
        }
        if self.output_path is not None:
            data["output_path"] = str(self.output_path)
        if self.error:
            data["error"] = self.error
        return data


class CheckOutcome(str, Enum):
    CHECKED = "CHECKED"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class PlanningContext:
    run_id: str
    timestamp: str
    inputs: tuple[str, ...]
    workflow_json: str
    naming_pattern: str
    output_root: str

    @classmethod
    def capture(cls, inputs, workflow_dict, naming_pattern, output_dir):
        return cls(
            uuid4().hex, datetime.now().strftime("%Y%m%d_%H%M%S"),
            tuple(str(path) for path in inputs), json.dumps(workflow_dict),
            str(naming_pattern), (str(Path(output_dir).resolve(strict=False))
                                  if str(output_dir).strip() and "\x00" not in str(output_dir) else str(output_dir)),
        )

    def workflow_dict(self):
        return json.loads(self.workflow_json)

    def to_dict(self):
        return {
            "run_id": self.run_id, "timestamp": self.timestamp,
            "inputs": list(self.inputs), "workflow": self.workflow_dict(),
            "naming_pattern": self.naming_pattern, "output_root": self.output_root,
        }


@dataclass(frozen=True, slots=True)
class PlanFact:
    name: str
    value: str | int | float | bool | tuple
    provenance: str
    dependencies: tuple[str, ...] = ()

    def to_dict(self):
        return {"name": self.name, "value": self.value, "provenance": self.provenance,
                "dependencies": list(self.dependencies)}


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    origin_id: tuple[int, str]
    producer_step: tuple[int, str] | None
    state: str
    logical_type: str
    logical_format: str | None
    suffix: str
    destination: str | None = None
    facts: tuple[PlanFact, ...] = ()
    unknown_properties: tuple[str, ...] = ()

    @property
    def name(self):
        return Path(self.destination or self.origin_id[1]).name

    def fact(self, name):
        return next((fact for fact in self.facts if fact.name == name), None)

    def to_dict(self):
        return {
            "origin_id": list(self.origin_id), "producer_step": self.producer_step,
            "state": self.state, "logical_type": self.logical_type,
            "logical_format": self.logical_format, "suffix": self.suffix,
            "destination": self.destination, "facts": [fact.to_dict() for fact in self.facts],
            "unknown_properties": list(self.unknown_properties),
        }


@dataclass(frozen=True, slots=True)
class PlanDiagnostic:
    step_index: int
    operation_id: str
    check_id: str
    stage: str
    outcome: CheckOutcome
    reason: str
    dependencies: tuple[str, ...] = ()

    def to_dict(self):
        return {
            "step_index": self.step_index, "operation_id": self.operation_id,
            "check_id": self.check_id, "stage": self.stage, "outcome": self.outcome.value,
            "reason": self.reason, "dependencies": list(self.dependencies),
        }


@dataclass(frozen=True, slots=True)
class OperationPlan:
    diagnostics: tuple[PlanDiagnostic, ...]
    logical_type: str = "UNKNOWN"
    logical_format: str | None = None
    suffix: str = ""
    facts: tuple[PlanFact, ...] = ()
    unknown_properties: tuple[str, ...] = ("generated_bytes", "size", "parseability")


@dataclass(frozen=True, slots=True)
class PlanResult:
    origin_id: tuple[int, str]
    assessment_state: str
    verdict: str
    diagnostics: tuple[PlanDiagnostic, ...]
    artifacts: tuple[ArtifactDescriptor, ...] = ()
    disabled_steps: tuple[int, ...] = ()
    planned_output: str | None = None
    interrupted: bool = False

    def to_dict(self):
        success = self.assessment_state == "COMPLETE" and self.verdict in {"CHECKED", "CONDITIONAL"}
        diagnostics = [item.to_dict() for item in self.diagnostics]
        data = {
            "success": success, "success_scope": "planning", "output": "",
            "file": self.origin_id[1], "origin_id": list(self.origin_id),
            "assessment_state": self.assessment_state, "planning_verdict": self.verdict,
            "diagnostics": diagnostics, "artifacts": [item.to_dict() for item in self.artifacts],
            "disabled_steps": list(self.disabled_steps), "interrupted": self.interrupted,
            "deferred_checks": [item for item in diagnostics if item["outcome"] == "DEFERRED"],
            "message": f"{self.verdict.title()} plan; no files were generated.",
        }
        if self.planned_output is not None:
            data["planned_output"] = self.planned_output
        errors = [item.reason for item in self.diagnostics
                  if item.outcome in {CheckOutcome.FAILED, CheckOutcome.UNSUPPORTED}]
        if errors:
            data["error"] = "; ".join(errors)
        return data
