from __future__ import annotations

import re
import threading
from pathlib import Path


FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_filename(value: str) -> str:
    cleaned = (value or "").strip().replace("\\", "_").replace("/", "_")
    cleaned = cleaned.replace("..", "_")
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned or "output"


def sanitize_for_spreadsheet(value: str) -> str:
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def resolve_safe_output(base_dir: Path, candidate_name: str, required_suffix: str | None = None) -> Path:
    base = base_dir.resolve(strict=False)
    safe_name = sanitize_filename(candidate_name)
    candidate = (base / safe_name).resolve(strict=False)

    if not candidate.is_relative_to(base):
        raise ValueError("Output path escapes output directory")

    if required_suffix and candidate.suffix.lower() != required_suffix.lower():
        candidate = candidate.with_suffix(required_suffix)
    return candidate


class OutputPathAllocator:
    """Thread-safe allocator that avoids collisions for duplicate basenames."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir.resolve(strict=False)
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}

    def allocate(self, preferred_name: str, suffix: str) -> Path:
        safe_base = sanitize_filename(preferred_name)
        if suffix and not suffix.startswith("."):
            suffix = "." + suffix

        with self._lock:
            key = f"{safe_base}{suffix.lower()}"
            index = self._counters.get(key, 0)
            while True:
                stem = safe_base if index == 0 else f"{safe_base}_{index:03d}"
                candidate = resolve_safe_output(self.output_dir, stem + suffix)
                if not candidate.exists():
                    self._counters[key] = index + 1
                    return candidate
                index += 1
