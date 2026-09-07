"""Derive pilot thresholds and compare complete V12-PERF baseline sessions."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

from benchmarks.fixtures import sha256_json_file
from benchmarks.run_baseline import (
    SESSION_SCHEMA_VERSION,
    THRESHOLD_SCHEMA_VERSION,
    BenchmarkConfigurationError,
    validate_session_record,
    write_new_json,
)
from benchmarks.workloads import BenchmarkExecutionError, WORKLOAD_DEFINITIONS


COMPARISON_SCHEMA_VERSION = "batchstudio-repeatability-comparison/v1"
REPEATABILITY_RULE = "ceil_to_0.5(max(5.0, 3 * pilot_relative_MAD_percent))"
REGRESSION_RULE = "ceil_to_0.5(max(repeatability_threshold, 2 * session_delta_percent))"
TARGET_RULE = "minimum targeted improvement = 2 * max_allowed_regression"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ceil_to_half(value: float) -> float:
    return math.ceil(value * 2.0) / 2.0


def _result_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {result["workload_id"]: result for result in record["workload_results"]}


def derive_thresholds(pilot_path: Path) -> dict[str, Any]:
    pilot = _load_json(pilot_path)
    validate_session_record(pilot)
    if pilot["schema_version"] != SESSION_SCHEMA_VERSION or pilot["profile"] != "pilot":
        raise BenchmarkConfigurationError("Thresholds require a valid pilot session record")
    results = _result_map(pilot)
    if set(results) != set(WORKLOAD_DEFINITIONS):
        raise BenchmarkConfigurationError("Pilot thresholds require the complete B1-B5 suite")

    workloads = {}
    for workload_id in sorted(results):
        result = results[workload_id]
        mean_seconds = float(result["summary"]["mean_seconds"])
        stdev_seconds = float(result["summary"]["standard_deviation_seconds"])
        raw_timings = [
            float(sample["wall_clock_seconds"]) for sample in result["raw_samples"]
        ]
        median_seconds = statistics.median(raw_timings)
        if mean_seconds <= 0:
            raise BenchmarkConfigurationError(f"{workload_id} pilot mean must be positive")
        rsd_percent = stdev_seconds / mean_seconds * 100.0
        mad_seconds = statistics.median(
            abs(timing - median_seconds) for timing in raw_timings
        )
        relative_mad_percent = mad_seconds / median_seconds * 100.0
        workloads[workload_id] = {
            "pilot_n": result["summary"]["n"],
            "pilot_raw_wall_clock_seconds": raw_timings,
            "pilot_mean_seconds": mean_seconds,
            "pilot_standard_deviation_seconds": stdev_seconds,
            "pilot_rsd_percent": rsd_percent,
            "pilot_median_seconds": median_seconds,
            "pilot_mad_seconds": mad_seconds,
            "pilot_relative_mad_percent": relative_mad_percent,
            "repeatability_threshold_percent": _ceil_to_half(
                max(5.0, 3.0 * relative_mad_percent)
            ),
        }
    return {
        "schema_version": THRESHOLD_SCHEMA_VERSION,
        "evidence_class": "noncanonical pilot calibration; not a product performance claim",
        "source_pilot_session_id": pilot["session_id"],
        "source_repository_sha": pilot["repository_sha"],
        "source_fixture_manifest_sha256": pilot["fixture_manifest_sha256"],
        "rule": REPEATABILITY_RULE,
        "workloads": workloads,
    }


def _assert_same_identity(first: dict[str, Any], second: dict[str, Any]) -> None:
    checks = {
        "repository_sha": (first["repository_sha"], second["repository_sha"]),
        "repository_tree": (first["repository_tree"], second["repository_tree"]),
        "environment": (first["environment"], second["environment"]),
        "fixture_manifest": (first["fixture_manifest"], second["fixture_manifest"]),
        "fixture_manifest_sha256": (
            first["fixture_manifest_sha256"],
            second["fixture_manifest_sha256"],
        ),
        "workload_configuration": (
            first["configuration"]["workloads"],
            second["configuration"]["workloads"],
        ),
        "timeout": (
            first["configuration"]["timeout_seconds_per_workload"],
            second["configuration"]["timeout_seconds_per_workload"],
        ),
        "outlier_rule": (
            first["configuration"]["outlier_rule"],
            second["configuration"]["outlier_rule"],
        ),
        "validation_boundary": (
            first["configuration"]["validation_boundary"],
            second["configuration"]["validation_boundary"],
        ),
        "threshold_manifest": (
            first["configuration"]["threshold_manifest"],
            second["configuration"]["threshold_manifest"],
        ),
    }
    mismatches = [name for name, values in checks.items() if values[0] != values[1]]
    if mismatches:
        raise BenchmarkConfigurationError(
            "Sessions have different controlled identities: " + ", ".join(mismatches)
        )


def compare_sessions(
    first_path: Path,
    second_path: Path,
    thresholds_path: Path,
) -> dict[str, Any]:
    first = _load_json(first_path)
    second = _load_json(second_path)
    thresholds = _load_json(thresholds_path)
    validate_session_record(first)
    validate_session_record(second)
    if first["profile"] != "canonical" or second["profile"] != "canonical":
        raise BenchmarkConfigurationError("Repeatability requires two canonical sessions")
    if first["session_id"] == second["session_id"]:
        raise BenchmarkConfigurationError("Repeatability sessions must have distinct IDs")
    if thresholds.get("schema_version") != THRESHOLD_SCHEMA_VERSION:
        raise BenchmarkConfigurationError("Threshold manifest schema is invalid")
    if set(thresholds.get("workloads", {})) != set(WORKLOAD_DEFINITIONS):
        raise BenchmarkConfigurationError("Threshold manifest must cover B1-B5 exactly")
    _assert_same_identity(first, second)
    if thresholds.get("source_fixture_manifest_sha256") != first["fixture_manifest_sha256"]:
        raise BenchmarkConfigurationError(
            "Threshold manifest was calibrated against another session fixture"
        )
    if first["configuration"]["threshold_manifest"] != thresholds:
        raise BenchmarkConfigurationError(
            "Session threshold identity differs from comparison input"
        )

    first_results = _result_map(first)
    second_results = _result_map(second)
    if set(first_results) != set(WORKLOAD_DEFINITIONS) or set(second_results) != set(
        WORKLOAD_DEFINITIONS
    ):
        raise BenchmarkConfigurationError("Canonical sessions must contain B1-B5 exactly")

    comparisons = []
    overall_pass = True
    for workload_id in sorted(WORKLOAD_DEFINITIONS):
        first_median = float(first_results[workload_id]["summary"]["median_seconds"])
        second_median = float(second_results[workload_id]["summary"]["median_seconds"])
        delta_percent = abs(second_median - first_median) / first_median * 100.0
        threshold_percent = float(
            thresholds["workloads"][workload_id]["repeatability_threshold_percent"]
        )
        repeatability = "PASS" if delta_percent <= threshold_percent else "FAIL"
        if repeatability == "FAIL":
            overall_pass = False
        regression_budget = _ceil_to_half(max(threshold_percent, 2.0 * delta_percent))
        comparisons.append(
            {
                "workload_id": workload_id,
                "session_1_median_seconds": first_median,
                "session_2_median_seconds": second_median,
                "delta_percent": delta_percent,
                "repeatability_threshold_percent": threshold_percent,
                "repeatability": repeatability,
                "max_allowed_regression_percent": regression_budget,
                "minimum_targeted_improvement_percent": regression_budget * 2.0,
            }
        )

    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "status": "PASS" if overall_pass else "FAIL",
        "session_1": first["session_id"],
        "session_2": second["session_id"],
        "repository_sha": first["repository_sha"],
        "repository_tree": first["repository_tree"],
        "environment_id": first["environment"]["environment_id"],
        "fixture_manifest_sha256": first["fixture_manifest_sha256"],
        "threshold_manifest_sha256": sha256_json_file(thresholds_path),
        "repeatability_rule": REPEATABILITY_RULE,
        "regression_budget_rule": REGRESSION_RULE,
        "target_improvement_rule": TARGET_RULE,
        "workloads": comparisons,
    }


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    derive_parser = subparsers.add_parser("derive-thresholds")
    derive_parser.add_argument("--pilot", required=True, type=Path)
    derive_parser.add_argument("--output", required=True, type=Path)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--session-1", required=True, type=Path)
    compare_parser.add_argument("--session-2", required=True, type=Path)
    compare_parser.add_argument("--thresholds", required=True, type=Path)
    compare_parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    if arguments.command == "derive-thresholds":
        payload = derive_thresholds(arguments.pilot)
        write_new_json(arguments.output, payload)
        print(f"Derived B1-B5 thresholds from pilot {payload['source_pilot_session_id']}.")
        return 0

    payload = compare_sessions(
        arguments.session_1,
        arguments.session_2,
        arguments.thresholds,
    )
    write_new_json(arguments.output, payload)
    for workload in payload["workloads"]:
        print(
            f"{workload['workload_id']}: delta={workload['delta_percent']:.2f}% "
            f"threshold={workload['repeatability_threshold_percent']:.2f}% "
            f"{workload['repeatability']}"
        )
    print(f"Repeatability {payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BenchmarkConfigurationError,
        BenchmarkExecutionError,
        json.JSONDecodeError,
        OSError,
    ) as error:
        print(f"Comparison failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
