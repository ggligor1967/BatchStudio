from __future__ import annotations

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
