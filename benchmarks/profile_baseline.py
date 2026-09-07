"""Collect bounded, reproducible cProfile evidence for V12-PERF workloads."""

from __future__ import annotations

import argparse
import json
import math
import pstats
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.fixtures import (
    generate_fixtures,
    sha256_file,
    sha256_json_file,
    verify_fixture_files,
    verify_manifest,
)
from benchmarks.run_baseline import (
    BenchmarkConfigurationError,
    REPOSITORY_ROOT,
    _git_output,
    run_command_with_timeout,
    write_new_json,
)
from benchmarks.workloads import BenchmarkExecutionError, WORKLOAD_DEFINITIONS


PROFILE_SCHEMA_VERSION = "batchstudio-bounded-profiling-summary/v1"
FIXTURE_MANIFEST_PATH = Path(__file__).with_name("fixture_manifest_v1.json")

COMPONENT_CONTRACT = {
    "B1": (
        ("BatchProcessor.process_batch", "core/processor.py", "process_batch"),
        ("BatchProcessor.process_single_file", "core/processor.py", "process_single_file"),
        ("FileRenameOperation._execute", "core/operations/file_ops.py", "_execute"),
        ("shutil.copyfileobj", "/shutil.py", "copyfileobj"),
    ),
    "B2": (
        ("BatchProcessor.process_batch", "core/processor.py", "process_batch"),
        ("ImageResizeOperation._execute", "core/operations/image_ops.py", "_execute"),
        ("PIL.Image.resize", "PIL/Image.py", "resize"),
        ("PIL.Image.save", "PIL/Image.py", "save"),
    ),
    "B3": (
        ("BatchProcessor.process_batch", "core/processor.py", "process_batch"),
        ("PDFWatermarkOperation._execute", "core/operations/pdf_ops.py", "_execute"),
        (
            "PDFWatermarkOperation._create_watermark_page",
            "core/operations/pdf_ops.py",
            "_create_watermark_page",
        ),
        ("pypdf.PdfReader.get_object", "pypdf/_reader.py", "get_object"),
        ("pypdf.PdfWriter.add_page", "pypdf/_writer.py", "add_page"),
    ),
    "B4": (
        ("BatchProcessor.process_batch", "core/processor.py", "process_batch"),
        ("PDFAggregateMergeOperation.consume", "core/operations/pdf_ops.py", "consume"),
        ("pypdf.PdfReader.get_object", "pypdf/_reader.py", "get_object"),
        ("pypdf.PdfWriter.add_page", "pypdf/_writer.py", "add_page"),
        ("PDFAggregateMergeOperation.finalize", "core/operations/pdf_ops.py", "finalize"),
    ),
    "B5": (
        ("BatchProcessor.process_batch", "core/processor.py", "process_batch"),
        ("ImageResizeOperation._execute", "core/operations/image_ops.py", "_execute"),
        ("PIL.Image.save", "PIL/Image.py", "save"),
        ("PIL.Image.resize", "PIL/Image.py", "resize"),
    ),
}

INTERPRETATIONS = {
    "B1": (
        "Time is distributed across per-file orchestration, path/ownership checks, "
        "and file copying; no isolated actionable component is established."
    ),
    "B2": (
        "The image-operation and Pillow resampling path is the largest identified "
        "component, but one perturbed sample does not establish an optimization target."
    ),
    "B3": (
        "Per-page watermark construction and PDF object parsing account for most "
        "identified operation time; no correctness-safe improvement requirement exists."
    ),
    "B4": (
        "PDF parsing and page addition dominate the identified aggregate-operation work; "
        "the evidence establishes a workload class, not an actionable optimization."
    ),
    "B5": (
        "Concurrent cumulative time identifies image transformation and output activity, "
        "but the values are non-additive and cannot establish a wall-time contribution."
    ),
}


def _normalized_profile_path(path: str) -> str:
    return path.replace("\\", "/")


def extract_component_rows(
    raw_stats: dict[tuple[str, int, str], tuple[Any, ...]],
    component_contract: tuple[tuple[str, str, str], ...],
) -> list[dict[str, Any]]:
    """Extract declared cumulative-time rows without heuristic name matching."""
    rows = []
    for component, file_suffix, function_name in component_contract:
        matches = [
            (key, values)
            for key, values in raw_stats.items()
            if _normalized_profile_path(key[0]).endswith(file_suffix)
            and key[2] == function_name
        ]
        if len(matches) != 1:
            raise BenchmarkExecutionError(
                f"{component} expected one pstats match, found {len(matches)}"
            )
        (filename, line_number, _), values = matches[0]
        primitive_calls, total_calls, total_seconds, cumulative_seconds = values[:4]
        if not all(
            math.isfinite(float(value))
            for value in (total_seconds, cumulative_seconds)
        ):
            raise BenchmarkExecutionError(f"{component} contains non-finite profiler data")
        rows.append(
            {
                "component": component,
                "source": f"{_normalized_profile_path(filename)}:{line_number}",
                "primitive_calls": int(primitive_calls),
                "total_calls": int(total_calls),
                "total_seconds": float(total_seconds),
                "cumulative_seconds": float(cumulative_seconds),
            }
        )
    return rows


def _require_empty_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise BenchmarkConfigurationError(
            f"Profiling workspace must be absent or empty: {path}"
        )
    path.mkdir(parents=True, exist_ok=True)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _profile_workload(
    workload_id: str,
    fixture_manifest_path: Path,
    fixture_root: Path,
    workspace_root: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    profile_path = workspace_root / f"{workload_id}.pstats"
    result_path = workspace_root / f"{workload_id}-worker-result.json"
    command = [
        sys.executable,
        "-m",
        "cProfile",
        "-o",
        str(profile_path),
        "-m",
        "benchmarks.run_baseline",
        "worker",
        "--workload",
        workload_id,
        "--manifest",
        str(fixture_manifest_path),
        "--fixture-root",
        str(fixture_root),
        "--work-root",
        str(workspace_root / f"work-{workload_id}"),
        "--output",
        str(result_path),
        "--warmups",
        "0",
        "--repetitions",
        "1",
    ]
    completed = run_command_with_timeout(command, timeout_seconds)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic output"
        raise BenchmarkExecutionError(
            f"{workload_id} profile failed with exit {completed.returncode}: {detail}"
        )
    if not profile_path.is_file() or not result_path.is_file():
        raise BenchmarkExecutionError(f"{workload_id} profile omitted required artifacts")

    worker_result = json.loads(result_path.read_text(encoding="utf-8"))
    if (
        worker_result.get("workload_id") != workload_id
        or worker_result.get("correctness") != "PASS"
        or len(worker_result.get("raw_samples", [])) != 1
    ):
        raise BenchmarkExecutionError(f"{workload_id} profile lacks passing worker evidence")

    statistics = pstats.Stats(str(profile_path))
    return {
        "workload_id": workload_id,
        "correctness": "PASS",
        "worker_count": WORKLOAD_DEFINITIONS[workload_id].worker_count,
        "profile_invocation": command,
        "profile_artifact": _display_path(profile_path),
        "profile_sha256": sha256_file(profile_path),
        "raw_worker_sample": worker_result["raw_samples"][0],
        "component_rows": extract_component_rows(
            statistics.stats,
            COMPONENT_CONTRACT[workload_id],
        ),
        "confidence": "LOW" if workload_id == "B5" else "MEDIUM",
        "interpretation": INTERPRETATIONS[workload_id],
    }


def run_profile(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.output.exists():
        raise BenchmarkConfigurationError(f"Output already exists: {arguments.output}")
    if arguments.timeout_seconds <= 0 or not math.isfinite(arguments.timeout_seconds):
        raise BenchmarkConfigurationError("timeout_seconds must be finite and positive")

    repository_sha = _git_output("rev-parse", "HEAD")
    repository_tree = _git_output("rev-parse", "HEAD^{tree}")
    if _git_output("status", "--porcelain"):
        raise BenchmarkConfigurationError("Profiling requires a clean working tree")
    if repository_sha != arguments.expected_repository_sha:
        raise BenchmarkConfigurationError(
            f"Expected repository SHA {arguments.expected_repository_sha}, got {repository_sha}"
        )

    workspace_root = arguments.workspace_root.resolve()
    _require_empty_directory(workspace_root)
    fixture_root = workspace_root / "fixtures"
    fixture_manifest = generate_fixtures(fixture_root)
    verify_manifest(fixture_manifest)
    verify_fixture_files(fixture_root, fixture_manifest)
    fixture_manifest_path = workspace_root / "fixture-manifest.json"
    fixture_manifest_path.write_text(
        json.dumps(fixture_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    workloads = [
        _profile_workload(
            workload_id,
            fixture_manifest_path,
            fixture_root,
            workspace_root,
            arguments.timeout_seconds,
        )
        for workload_id in sorted(WORKLOAD_DEFINITIONS)
    ]
    command = [
        sys.executable,
        "-m",
        "benchmarks.profile_baseline",
        "--environment-id",
        arguments.environment_id,
        "--workspace-root",
        _display_path(arguments.workspace_root),
        "--expected-repository-sha",
        repository_sha,
        "--output",
        _display_path(arguments.output),
        "--timeout-seconds",
        str(arguments.timeout_seconds),
    ]
    record = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "conclusion": "NO_ACTIONABLE_BOTTLENECK_ESTABLISHED",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "environment_id": arguments.environment_id,
        "fixture_manifest_sha256": sha256_json_file(FIXTURE_MANIFEST_PATH),
        "runner_invocation": command,
        "working_directory": str(REPOSITORY_ROOT),
        "method": (
            "Python standard-library cProfile of one complete worker invocation per "
            "B1-B5 workload; component rows are deterministically extracted from pstats"
        ),
        "extraction_contract": {
            workload_id: [
                {
                    "component": component,
                    "source_file_suffix": source_file_suffix,
                    "function_name": function_name,
                }
                for component, source_file_suffix, function_name in contract
            ]
            for workload_id, contract in COMPONENT_CONTRACT.items()
        },
        "limitations": [
            "cProfile perturbs execution and these observations are not baseline timings",
            "each workload is profiled once with zero warmups",
            "cumulative time across B5 worker threads is non-additive",
            "profile artifacts remain local; their hashes and exact invocations are recorded",
        ],
        "workloads": workloads,
    }
    write_new_json(arguments.output, record)
    return record


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--expected-repository-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    record = run_profile(arguments)
    print(
        f"PROFILE PASS at {record['repository_sha']}: "
        f"{record['conclusion']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BenchmarkConfigurationError,
        BenchmarkExecutionError,
        json.JSONDecodeError,
        OSError,
    ) as error:
        print(f"Profiling failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
