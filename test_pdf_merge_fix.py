#!/usr/bin/env python3
"""Standalone diagnostic for the canonical asserted 5-input merge case."""

from pathlib import Path
from tempfile import TemporaryDirectory

from tests.pdf_merge_cases import assert_merge_case


if __name__ == "__main__":
    with TemporaryDirectory() as temporary_directory:
        stats = assert_merge_case(Path(temporary_directory), 5)
        print("processed", stats.processed_files)
        print("failed", stats.failed_files)
        print("5-input merge assertions passed")
