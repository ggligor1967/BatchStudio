from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from core.contracts import OperationResult
from core.security import OutputPathAllocator, resolve_safe_output


class Operation(ABC):
    id = "operation"
    name = "Operation"
    description = ""
    accepted_types = {"any"}
    output_type = "any"
    supports_dry_run = True
    requires_ocr = False

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(config) if config is not None else {}
        self.output_allocator: Optional[OutputPathAllocator] = None

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
        schema = self.get_config_schema()
        for key, rules in schema.items():
            if key not in self.config:
                continue
            value = self.config[key]
            expected = rules.get("type")
            if expected == "int" and not isinstance(value, int):
                return False, f"config '{key}' must be int"
            if expected == "float" and not isinstance(value, (int, float)):
                return False, f"config '{key}' must be float"
            if expected == "bool" and not isinstance(value, bool):
                return False, f"config '{key}' must be bool"
            if expected == "str" and not isinstance(value, str):
                return False, f"config '{key}' must be str"
            if expected == "choice":
                choices = rules.get("choices", [])
                if value not in choices:
                    return False, f"config '{key}' must be one of {choices}"
        return True, ""


class AggregateOperation(ABC):
    id = "aggregate"
    name = "Aggregate"
    description = ""
    accepted_types = {"pdf"}
    output_type = "pdf"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(config) if config is not None else {}

    def get_config_schema(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def validate_config(self) -> tuple[bool, str]:
        schema = self.get_config_schema()
        for key, rules in schema.items():
            if key not in self.config:
                continue
            value = self.config[key]
            expected = rules.get("type")
            if expected == "int" and not isinstance(value, int):
                return False, f"config '{key}' must be int"
            if expected == "bool" and not isinstance(value, bool):
                return False, f"config '{key}' must be bool"
            if expected == "str" and not isinstance(value, str):
                return False, f"config '{key}' must be str"
            if expected == "choice":
                choices = rules.get("choices", [])
                if value not in choices:
                    return False, f"config '{key}' must be one of {choices}"
        return True, ""

    @abstractmethod
    def begin(self, output_path: Path, dry_run: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def consume(self, file_path: Path) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def finalize(self) -> OperationResult:
        raise NotImplementedError
