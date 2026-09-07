"""Run the bounded, fail-closed V12-PERF baseline suite."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.fixtures import (
    generate_fixtures,
    sha256_json_file,
    sha256_normalized_text_file,
    verify_fixture_files,
    verify_manifest,
)
from benchmarks.workloads import (
    WORKLOAD_DEFINITIONS,
    BenchmarkExecutionError,
    get_workload_definition,
    run_workload,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SESSION_SCHEMA_VERSION = "batchstudio-performance-baseline/v1"
THRESHOLD_SCHEMA_VERSION = "batchstudio-repeatability-thresholds/v1"
THRESHOLD_PATH = Path(__file__).with_name("repeatability_thresholds_v1.json")
FIXTURE_MANIFEST_PATH = Path(__file__).with_name("fixture_manifest_v1.json")
CONSTRAINTS_PATH = Path(__file__).with_name("constraints.txt")
DEFAULT_TIMEOUT_SECONDS = 120.0
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

PROFILE_CONFIGURATIONS = {
    "pilot": {
        "B1": {"warmups": 5, "repetitions": 15},
        "B2": {"warmups": 8, "repetitions": 15},
        "B3": {"warmups": 5, "repetitions": 15},
        "B4": {"warmups": 5, "repetitions": 15},
        "B5": {"warmups": 8, "repetitions": 15},
    },
    "canonical": {
        "B1": {"warmups": 5, "repetitions": 15},
        "B2": {"warmups": 8, "repetitions": 15},
        "B3": {"warmups": 5, "repetitions": 15},
        "B4": {"warmups": 5, "repetitions": 15},
        "B5": {"warmups": 8, "repetitions": 15},
    },
}


class BenchmarkConfigurationError(RuntimeError):
    """Raised when configuration or environment identity is invalid."""


def validate_run_counts(warmups: int, repetitions: int) -> None:
    if warmups < 0:
        raise BenchmarkConfigurationError("warmups must be >= 0")
    if repetitions < 1:
        raise BenchmarkConfigurationError("repetitions must be >= 1")


def calculate_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        raise BenchmarkConfigurationError("Cannot summarize an empty sample set")
    wall_times = [float(sample["wall_clock_seconds"]) for sample in samples]
    cpu_times = [float(sample["cpu_time_seconds"]) for sample in samples]
    if any(value <= 0 or not math.isfinite(value) for value in wall_times):
        raise BenchmarkConfigurationError("Wall-clock samples must be finite and positive")
    if any(value < 0 or not math.isfinite(value) for value in cpu_times):
        raise BenchmarkConfigurationError("CPU-time samples must be finite and non-negative")
    file_counts = {int(sample["files_processed"]) for sample in samples}
    if len(file_counts) != 1 or next(iter(file_counts)) < 1:
        raise BenchmarkConfigurationError("Samples must have one positive files_processed identity")

    ordered_wall_times = sorted(wall_times)
    count = len(wall_times)
    median_seconds = statistics.median(wall_times)
    files_per_run = next(iter(file_counts))
    p95_seconds = ordered_wall_times[math.ceil(0.95 * count) - 1] if count >= 10 else None
    return {
        "n": count,
        "minimum_seconds": min(wall_times),
        "maximum_seconds": max(wall_times),
        "median_seconds": median_seconds,
        "mean_seconds": statistics.fmean(wall_times),
        "standard_deviation_seconds": statistics.stdev(wall_times) if count > 1 else 0.0,
        "p95_seconds": p95_seconds,
        "p95_unavailable_reason": None if p95_seconds is not None else "N < 10",
        "cpu_time_median_seconds": statistics.median(cpu_times),
        "throughput_files_per_second": files_per_run / median_seconds,
        "latency_per_file_seconds": median_seconds / files_per_run,
        "peak_memory_mb": None,
        "peak_memory_unavailable_reason": (
            "No dependency-free per-workload process peak with a trustworthy "
            "cross-platform boundary"
        ),
    }


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    resolved = path.resolve()
    if resolved.exists():
        raise BenchmarkConfigurationError(f"Refusing to overwrite existing evidence: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(resolved.name + ".tmp")
    temporary_created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            temporary_created = True
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, resolved)
    except Exception:
        if temporary_created:
            temporary.unlink(missing_ok=True)
        raise


def run_command_with_timeout(
    command: list[str], timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    if timeout_seconds <= 0 or not math.isfinite(timeout_seconds):
        raise BenchmarkConfigurationError("timeout_seconds must be finite and positive")
    try:
        return subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise BenchmarkExecutionError(
            f"Workload process exceeded {timeout_seconds:g} seconds"
        ) from error


def _git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _windows_cpu_name() -> str:
    if sys.platform != "win32":
        return platform.processor() or "UNAVAILABLE"
    import winreg

    key_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
    return str(value).strip()


def _total_ram_bytes() -> int | None:
    if sys.platform == "win32":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total_physical)
        return None
    page_size = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else None
    page_count = os.sysconf("SC_PHYS_PAGES") if hasattr(os, "sysconf") else None
    return int(page_size * page_count) if page_size and page_count else None


def _dependency_identity() -> dict[str, Any]:
    distributions = [
        "batchstudio",
        "Pillow",
        "pandas",
        "reportlab",
        "openpyxl",
        "pypdf",
        "numpy",
        "python-dateutil",
        "pytz",
        "tzdata",
        "six",
        "et_xmlfile",
        "charset-normalizer",
    ]
    versions = {}
    for distribution in distributions:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "UNAVAILABLE"
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "constraints_path": "benchmarks/constraints.txt",
        "constraints_sha256": sha256_normalized_text_file(CONSTRAINTS_PATH),
        "versions": versions,
        "pip_freeze_all": freeze.stdout.splitlines(),
    }


def collect_environment(
    environment_id: str,
    storage_type: str,
    power_mode: str,
) -> dict[str, Any]:
    perf_counter = time.get_clock_info("perf_counter")
    process_time = time.get_clock_info("process_time")
    return {
        "environment_id": environment_id,
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu": _windows_cpu_name(),
        "logical_processors": os.cpu_count(),
        "ram_bytes": _total_ram_bytes(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": str(Path(sys.executable).resolve()),
        "dependency_identity": _dependency_identity(),
        "storage_type": storage_type,
        "power_mode": power_mode,
        "external_toolchain": "none; OCR excluded from canonical B1-B5",
        "clock": {
            "wall": "time.perf_counter_ns",
            "wall_monotonic": perf_counter.monotonic,
            "wall_adjustable": perf_counter.adjustable,
            "wall_resolution_seconds": perf_counter.resolution,
            "cpu": "time.process_time_ns",
            "cpu_monotonic": process_time.monotonic,
            "cpu_adjustable": process_time.adjustable,
            "cpu_resolution_seconds": process_time.resolution,
        },
    }


def _load_thresholds() -> dict[str, Any]:
    if not THRESHOLD_PATH.is_file():
        raise BenchmarkConfigurationError(
            "Canonical profile requires benchmarks/repeatability_thresholds_v1.json"
        )
    thresholds = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
    if thresholds.get("schema_version") != THRESHOLD_SCHEMA_VERSION:
        raise BenchmarkConfigurationError("Repeatability threshold schema is invalid")
    if set(thresholds.get("workloads", {})) != set(WORKLOAD_DEFINITIONS):
        raise BenchmarkConfigurationError("Repeatability thresholds do not cover B1-B5 exactly")
    current_fixture_hash = sha256_json_file(FIXTURE_MANIFEST_PATH)
    if thresholds.get("source_fixture_manifest_sha256") != current_fixture_hash:
        raise BenchmarkConfigurationError(
            "Repeatability thresholds were calibrated against another fixture manifest"
        )
    return thresholds


def validate_session_record(record: dict[str, Any]) -> None:
    required_top_level = {
        "schema_version",
        "status",
        "profile",
        "session_id",
        "captured_at_utc",
        "repository_sha",
        "repository_tree",
        "working_tree_clean",
        "environment",
        "fixture_manifest",
        "fixture_manifest_sha256",
        "configuration",
        "workload_results",
    }
    missing = required_top_level - set(record)
    if missing:
        raise BenchmarkConfigurationError(
            f"Session record is missing metadata: {', '.join(sorted(missing))}"
        )
    environment_fields = {
        "environment_id",
        "os",
        "os_version",
        "architecture",
        "cpu",
        "logical_processors",
        "ram_bytes",
        "python_version",
        "dependency_identity",
        "storage_type",
        "power_mode",
        "external_toolchain",
        "clock",
    }
    missing_environment = environment_fields - set(record["environment"])
    if missing_environment:
        raise BenchmarkConfigurationError(
            "Session environment is missing: " + ", ".join(sorted(missing_environment))
        )
    if record["schema_version"] != SESSION_SCHEMA_VERSION or record["status"] != "PASS":
        raise BenchmarkConfigurationError("Session record is not valid PASS evidence")
    for result in record["workload_results"]:
        if result.get("correctness") != "PASS" or not result.get("raw_samples"):
            raise BenchmarkConfigurationError("Workload result lacks passing raw evidence")
        if result["summary"]["n"] != len(result["raw_samples"]):
            raise BenchmarkConfigurationError("Summary N differs from raw sample count")
        if result["summary"] != calculate_summary(result["raw_samples"]):
            raise BenchmarkConfigurationError(
                f"{result.get('workload_id', 'unknown')} summary differs from raw samples"
            )


def _run_worker(
    workload_id: str,
    fixture_manifest_path: Path,
    fixture_root: Path,
    work_root: Path,
    result_path: Path,
    warmups: int,
    repetitions: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    command = [
        sys.executable,
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
        str(work_root),
        "--output",
        str(result_path),
        "--warmups",
        str(warmups),
        "--repetitions",
        str(repetitions),
    ]
    completed = run_command_with_timeout(command, timeout_seconds)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic output"
        raise BenchmarkExecutionError(
            f"{workload_id} worker failed with exit {completed.returncode}: {detail}"
        )
    if not result_path.is_file():
        raise BenchmarkExecutionError(f"{workload_id} worker produced no result file")
    return json.loads(result_path.read_text(encoding="utf-8"))


def _selected_workloads(arguments: argparse.Namespace) -> list[str]:
    selected = arguments.workload or sorted(WORKLOAD_DEFINITIONS)
    if len(selected) != len(set(selected)):
        raise BenchmarkConfigurationError("Workload IDs must not be repeated")
    if arguments.profile == "canonical" and set(selected) != set(WORKLOAD_DEFINITIONS):
        raise BenchmarkConfigurationError(
            "Canonical sessions must execute the complete B1-B5 suite"
        )
    return selected


def run_session(arguments: argparse.Namespace) -> dict[str, Any]:
    if not SESSION_ID_PATTERN.fullmatch(arguments.session_id):
        raise BenchmarkConfigurationError("session_id contains unsupported characters")
    if arguments.output.exists():
        raise BenchmarkConfigurationError(f"Output already exists: {arguments.output}")
    if arguments.timeout_seconds <= 0 or not math.isfinite(arguments.timeout_seconds):
        raise BenchmarkConfigurationError("timeout_seconds must be finite and positive")

    selected = _selected_workloads(arguments)
    repository_sha = _git_output("rev-parse", "HEAD")
    repository_tree = _git_output("rev-parse", "HEAD^{tree}")
    working_tree_clean = not bool(_git_output("status", "--porcelain"))
    if arguments.profile == "canonical":
        if not working_tree_clean:
            raise BenchmarkConfigurationError("Canonical sessions require a clean working tree")
        if not arguments.expected_repository_sha:
            raise BenchmarkConfigurationError(
                "Canonical sessions require --expected-repository-sha"
            )
        if repository_sha != arguments.expected_repository_sha:
            raise BenchmarkConfigurationError(
                f"Expected repository SHA {arguments.expected_repository_sha}, got {repository_sha}"
            )
        thresholds = _load_thresholds()
    else:
        thresholds = None

    workspace_root = arguments.workspace_root.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    order_seed = int.from_bytes(
        hashlib.sha256(f"v1:{arguments.session_id}".encode("utf-8")).digest()[:8],
        "big",
    )
    workload_order = list(selected)
    random.Random(order_seed).shuffle(workload_order)

    with tempfile.TemporaryDirectory(
        prefix=f"{arguments.session_id}-",
        dir=workspace_root,
    ) as temporary_directory:
        session_root = Path(temporary_directory)
        fixture_root = session_root / "fixtures"
        fixture_manifest = generate_fixtures(fixture_root)
        verify_manifest(fixture_manifest)
        verify_fixture_files(fixture_root, fixture_manifest)
        fixture_manifest_path = session_root / "fixture-manifest.json"
        fixture_manifest_path.write_text(
            json.dumps(fixture_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        workload_results = []
        for workload_id in workload_order:
            run_config = PROFILE_CONFIGURATIONS[arguments.profile][workload_id]
            validate_run_counts(run_config["warmups"], run_config["repetitions"])
            definition = get_workload_definition(workload_id)
            worker_result = _run_worker(
                workload_id=workload_id,
                fixture_manifest_path=fixture_manifest_path,
                fixture_root=fixture_root,
                work_root=session_root / f"work-{workload_id}",
                result_path=session_root / f"result-{workload_id}.json",
                warmups=run_config["warmups"],
                repetitions=run_config["repetitions"],
                timeout_seconds=arguments.timeout_seconds,
            )
            samples = worker_result["raw_samples"]
            workload_results.append(
                {
                    "workload_id": workload_id,
                    "operation": definition.operation_id,
                    "profile": definition.profile,
                    "fixture_id": definition.fixture_id,
                    "worker_count": definition.worker_count,
                    "cold_warm_mode": "warm in-process; fresh subprocess per workload",
                    "warmups": run_config["warmups"],
                    "measured_runs": run_config["repetitions"],
                    "raw_samples": samples,
                    "summary": calculate_summary(samples),
                    "correctness": "PASS",
                }
            )

    record = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "status": "PASS",
        "profile": arguments.profile,
        "session_id": arguments.session_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "working_tree_clean": working_tree_clean,
        "environment": collect_environment(
            arguments.environment_id,
            arguments.storage_type,
            arguments.power_mode,
        ),
        "fixture_manifest": fixture_manifest,
        "fixture_manifest_sha256": sha256_json_file(FIXTURE_MANIFEST_PATH),
        "configuration": {
            "workload_order": workload_order,
            "order_seed": order_seed,
            "workloads": {
                workload_id: {
                    **PROFILE_CONFIGURATIONS[arguments.profile][workload_id],
                    "worker_count": WORKLOAD_DEFINITIONS[workload_id].worker_count,
                }
                for workload_id in selected
            },
            "timeout_seconds_per_workload": arguments.timeout_seconds,
            "outlier_rule": "retain every completed measured sample",
            "validation_boundary": "immediately after each timed operation, outside timed region",
            "primary_statistic": "median wall_clock_seconds",
            "threshold_manifest": thresholds,
        },
        "workload_results": workload_results,
    }
    validate_session_record(record)
    write_new_json(arguments.output, record)
    return record


def run_worker_process(arguments: argparse.Namespace) -> dict[str, Any]:
    validate_run_counts(arguments.warmups, arguments.repetitions)
    definition = get_workload_definition(arguments.workload)
    fixture_manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    samples = run_workload(
        definition=definition,
        fixture_manifest=fixture_manifest,
        fixture_root=arguments.fixture_root,
        work_root=arguments.work_root,
        warmups=arguments.warmups,
        repetitions=arguments.repetitions,
    )
    payload = {
        "workload_id": definition.workload_id,
        "worker_count": definition.worker_count,
        "raw_samples": samples,
        "correctness": "PASS",
    }
    write_new_json(arguments.output, payload)
    return payload


def _print_summary(record: dict[str, Any]) -> None:
    print(
        f"{record['profile'].upper()} {record['session_id']} PASS at {record['repository_sha']}"
    )
    for result in sorted(record["workload_results"], key=lambda item: item["workload_id"]):
        summary = result["summary"]
        print(
            f"{result['workload_id']}: N={summary['n']} "
            f"median={summary['median_seconds']:.6f}s "
            f"mean={summary['mean_seconds']:.6f}s "
            f"stdev={summary['standard_deviation_seconds']:.6f}s correctness=PASS"
        )


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a pilot or canonical session")
    run_parser.add_argument("--profile", choices=sorted(PROFILE_CONFIGURATIONS), required=True)
    run_parser.add_argument("--session-id", required=True)
    run_parser.add_argument("--environment-id", required=True)
    run_parser.add_argument("--storage-type", required=True)
    run_parser.add_argument("--power-mode", required=True)
    run_parser.add_argument("--workspace-root", required=True, type=Path)
    run_parser.add_argument("--output", required=True, type=Path)
    run_parser.add_argument("--expected-repository-sha")
    run_parser.add_argument(
        "--workload",
        action="append",
        choices=sorted(WORKLOAD_DEFINITIONS),
        help="Pilot-only subset; omit to run B1-B5",
    )
    run_parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)

    worker_parser = subparsers.add_parser("worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("--workload", required=True)
    worker_parser.add_argument("--manifest", required=True, type=Path)
    worker_parser.add_argument("--fixture-root", required=True, type=Path)
    worker_parser.add_argument("--work-root", required=True, type=Path)
    worker_parser.add_argument("--output", required=True, type=Path)
    worker_parser.add_argument("--warmups", required=True, type=int)
    worker_parser.add_argument("--repetitions", required=True, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    if arguments.command == "worker":
        run_worker_process(arguments)
        return 0
    record = run_session(arguments)
    _print_summary(record)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BenchmarkConfigurationError,
        BenchmarkExecutionError,
        json.JSONDecodeError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
