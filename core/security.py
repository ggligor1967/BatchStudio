from __future__ import annotations

import os
import re
import threading
from contextlib import contextmanager
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
    requested = base / safe_name
    if required_suffix and requested.suffix.lower() != required_suffix.lower():
        requested = requested.with_suffix(required_suffix)
    candidate = requested.resolve(strict=False)

    if not candidate.is_relative_to(base):
        raise ValueError("Output path escapes output directory")

    if requested.is_symlink():
        raise ValueError("Output path is a symbolic link")
    return candidate


def output_identity(path: Path) -> tuple[int, int]:
    stat = path.lstat()
    return stat.st_dev, stat.st_ino


def remove_owned_output(path: Path, identity: tuple[int, int]) -> None:
    """Remove a recorded artifact only while its filesystem identity still matches."""
    try:
        if output_identity(path) == identity:
            path.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def exclusive_output(path: Path, *, text: bool = False, newline: str | None = None):
    """Create once and write through that handle; never reopen a destination for writing."""
    options = {"encoding": "utf-8", "newline": newline} if text else {}
    identity = None
    try:
        with path.open("x" if text else "xb", **options) as stream:
            stat = os.fstat(stream.fileno())
            identity = stat.st_dev, stat.st_ino
            yield stream
    except BaseException:
        if identity is not None:
            remove_owned_output(path, identity)
        raise


class OutputPathAllocator:
    """Reserve canonical final destinations across threads and preferred-name aliases."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir.resolve(strict=False)
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._reserved: set[Path] = set()

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
                if candidate not in self._reserved and not candidate.exists():
                    self._counters[key] = index + 1
                    self._reserved.add(candidate)
                    return candidate
                index += 1
