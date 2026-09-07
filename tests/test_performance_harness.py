from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from benchmarks.compare_sessions import compare_sessions, derive_thresholds
from benchmarks.fixtures import (
    FixtureVerificationError,
    generate_fixtures,
    load_expected_manifest,
    sha256_file,
    sha256_json_file,
    sha256_normalized_text_file,
    verify_fixture_files,
    verify_manifest,
)
from benchmarks.profile_baseline import extract_component_rows
from benchmarks.run_baseline import (
    BenchmarkConfigurationError,
    calculate_summary,
    run_command_with_timeout,
    validate_run_counts,
    validate_session_record,
    write_new_json,
)
from benchmarks.workloads import (
    WORKLOAD_DEFINITIONS,
    BenchmarkExecutionError,
    get_workload_definition,
    run_workload,
)
from core.processor import BatchProcessor, ProcessingStats


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _single_file_manifest(root: Path, content: bytes = b"fixture") -> dict:
    source = root / "f1" / "small.txt"
    source.parent.mkdir(parents=True)
    source.write_bytes(content)
    return {
        "schema_version": "test-fixtures/v1",
        "fixtures": [
            {
                "fixture_id": "F1",
                "files": [
                    {
                        "path": "f1/small.txt",
                        "size_bytes": len(content),
                        "sha256": sha256_file(source),
                    }
                ],
            }
        ],
    }


def _valid_session_record(profile: str = "pilot") -> dict:
    raw_sample = {
        "iteration": 1,
        "wall_clock_seconds": 1.0,
        "cpu_time_seconds": 0.5,
        "files_processed": 1,
        "output_bytes": 10,
        "output_sha256": {
            "file_count": 1,
            "manifest_sha256": "0" * 64,
            "unique_content_sha256": ["0" * 64],
        },
        "correctness": "PASS",
    }
    results = []
    for workload_id in WORKLOAD_DEFINITIONS:
        results.append(
            {
                "workload_id": workload_id,
                "correctness": "PASS",
                "raw_samples": [copy.deepcopy(raw_sample), {**raw_sample, "iteration": 2}],
                "summary": calculate_summary(
                    [copy.deepcopy(raw_sample), {**raw_sample, "iteration": 2}]
                ),
            }
        )
    return {
        "schema_version": "batchstudio-performance-baseline/v1",
        "status": "PASS",
        "profile": profile,
        "session_id": "test-session",
        "captured_at_utc": "2026-09-07T00:00:00+00:00",
        "repository_sha": "a" * 40,
        "repository_tree": "b" * 40,
        "working_tree_clean": True,
        "environment": {
            "environment_id": "test-environment",
            "os": "TestOS",
            "os_version": "1",
            "architecture": "test",
            "cpu": "test",
            "logical_processors": 1,
            "ram_bytes": 1,
            "python_version": "3.13.0",
            "dependency_identity": {},
            "storage_type": "test",
            "power_mode": "test",
            "external_toolchain": "none",
            "clock": {},
        },
        "fixture_manifest": {},
        "fixture_manifest_sha256": "c" * 64,
        "configuration": {},
        "workload_results": results,
    }


def test_fixture_generation_is_deterministic_and_matches_manifest(tmp_path: Path):
    first = generate_fixtures(tmp_path / "first")
    second = generate_fixtures(tmp_path / "second")

    assert first == second == load_expected_manifest()
    verify_manifest(first)
    verify_fixture_files(tmp_path / "first", first)
    verify_fixture_files(tmp_path / "second", second)


def test_fixture_hash_verification_rejects_tampering(tmp_path: Path):
    manifest = _single_file_manifest(tmp_path)
    verify_fixture_files(tmp_path, manifest)

    (tmp_path / "f1" / "small.txt").write_bytes(b"tampered")

    with pytest.raises(FixtureVerificationError, match="size differs|SHA-256 differs"):
        verify_fixture_files(tmp_path, manifest)


def test_manifest_verification_rejects_changed_identity():
    manifest = load_expected_manifest()
    changed = copy.deepcopy(manifest)
    changed["fixtures"][0]["files"][0]["sha256"] = "0" * 64

    with pytest.raises(FixtureVerificationError, match="does not match"):
        verify_manifest(changed)


def test_unknown_workload_is_rejected():
    with pytest.raises(BenchmarkExecutionError, match="Unknown workload"):
        get_workload_definition("UNKNOWN")


@pytest.mark.parametrize("warmups,repetitions", [(-1, 1), (0, 0)])
def test_invalid_run_counts_are_rejected(warmups: int, repetitions: int):
    with pytest.raises(BenchmarkConfigurationError):
        validate_run_counts(warmups, repetitions)


def test_timeout_is_bounded_and_reported():
    command = [sys.executable, "-c", "import time; time.sleep(2)"]

    with pytest.raises(BenchmarkExecutionError, match="exceeded"):
        run_command_with_timeout(command, timeout_seconds=0.01)


def test_failed_operation_produces_no_valid_workload_record(tmp_path: Path, monkeypatch):
    fixture_root = tmp_path / "fixtures"
    manifest = _single_file_manifest(fixture_root)

    def fail_batch(self, *args, **kwargs):
        stats = ProcessingStats()
        stats.total_files = 1
        stats.add_error("small.txt", "injected failure")
        return stats

    monkeypatch.setattr(BatchProcessor, "process_batch", fail_batch)

    with pytest.raises(BenchmarkExecutionError, match="invalid processing stats"):
        run_workload(
            get_workload_definition("B1"),
            manifest,
            fixture_root,
            tmp_path / "work",
            warmups=0,
            repetitions=1,
        )


def test_b1_smoke_uses_real_processor_and_preserves_collision_sentinel(tmp_path: Path):
    fixture_root = tmp_path / "fixtures"
    manifest = _single_file_manifest(fixture_root, b"real B1 fixture")

    definition = replace(
        get_workload_definition("B1"),
        input_repetitions=1,
        input_count=1,
        expected_output_count=1,
    )
    samples = run_workload(
        definition,
        manifest,
        fixture_root,
        tmp_path / "work",
        warmups=1,
        repetitions=2,
    )

    assert [sample["iteration"] for sample in samples] == [1, 2]
    assert all(sample["correctness"] == "PASS" for sample in samples)
    assert all(sample["output_bytes"] == len(b"real B1 fixture") for sample in samples)


def test_relative_work_root_produces_valid_output_fingerprint(
    tmp_path: Path,
    monkeypatch,
):
    fixture_root = tmp_path / "fixtures"
    manifest = _single_file_manifest(fixture_root, b"relative path fixture")
    definition = replace(
        get_workload_definition("B1"),
        input_repetitions=1,
        input_count=1,
        expected_output_count=1,
    )
    monkeypatch.chdir(tmp_path)

    samples = run_workload(
        definition,
        manifest,
        fixture_root,
        Path("relative-work"),
        warmups=0,
        repetitions=1,
    )

    assert samples[0]["correctness"] == "PASS"
    assert samples[0]["output_sha256"]["file_count"] == 1
    assert len(samples[0]["output_sha256"]["manifest_sha256"]) == 64


def test_summary_uses_all_raw_timings_without_mutation():
    samples = [
        {
            "wall_clock_seconds": float(value),
            "cpu_time_seconds": float(value) / 2,
            "files_processed": 2,
        }
        for value in range(1, 11)
    ]
    original = copy.deepcopy(samples)

    summary = calculate_summary(samples)

    assert samples == original
    assert summary["n"] == 10
    assert summary["minimum_seconds"] == 1.0
    assert summary["maximum_seconds"] == 10.0
    assert summary["median_seconds"] == 5.5
    assert summary["mean_seconds"] == 5.5
    assert summary["p95_seconds"] == 10.0
    assert summary["throughput_files_per_second"] == pytest.approx(2 / 5.5)
    assert summary["latency_per_file_seconds"] == 2.75


def test_worker_counts_are_frozen_in_workload_identity():
    assert {key: value.worker_count for key, value in WORKLOAD_DEFINITIONS.items()} == {
        "B1": 1,
        "B2": 1,
        "B3": 1,
        "B4": 1,
        "B5": 4,
    }


def test_metadata_validation_is_fail_closed():
    record = _valid_session_record()
    validate_session_record(record)
    del record["environment"]["cpu"]

    with pytest.raises(BenchmarkConfigurationError, match="missing"):
        validate_session_record(record)


def test_metadata_validation_rejects_summary_drift_from_raw_samples():
    record = _valid_session_record()
    record["workload_results"][0]["summary"]["median_seconds"] = 0.5

    with pytest.raises(BenchmarkConfigurationError, match="differs from raw samples"):
        validate_session_record(record)


def test_profiler_component_extraction_uses_exact_source_and_function_identity():
    raw_stats = {
        (r"D:\repo\core\processor.py", 515, "process_batch"): (
            1,
            2,
            0.25,
            0.75,
            {},
        ),
        (r"D:\repo\core\other.py", 10, "process_batch"): (
            1,
            1,
            9.0,
            9.0,
            {},
        ),
    }

    rows = extract_component_rows(
        raw_stats,
        (("BatchProcessor.process_batch", "core/processor.py", "process_batch"),),
    )

    assert rows == [
        {
            "component": "BatchProcessor.process_batch",
            "source": "D:/repo/core/processor.py:515",
            "primitive_calls": 1,
            "total_calls": 2,
            "total_seconds": 0.25,
            "cumulative_seconds": 0.75,
        }
    ]


def test_profiler_component_extraction_rejects_missing_evidence():
    with pytest.raises(BenchmarkExecutionError, match="expected one pstats match"):
        extract_component_rows(
            {},
            (("BatchProcessor.process_batch", "core/processor.py", "process_batch"),),
        )


def test_pilot_thresholds_retain_raw_calibration_samples(tmp_path: Path):
    pilot_path = tmp_path / "pilot.json"
    pilot_path.write_text(json.dumps(_valid_session_record()), encoding="utf-8")

    thresholds = derive_thresholds(pilot_path)

    assert set(thresholds["workloads"]) == set(WORKLOAD_DEFINITIONS)
    assert thresholds["workloads"]["B1"]["pilot_raw_wall_clock_seconds"] == [1.0, 1.0]
    assert thresholds["workloads"]["B1"]["repeatability_threshold_percent"] == 5.0


def test_committed_threshold_manifest_matches_frozen_workloads():
    threshold_path = REPOSITORY_ROOT / "benchmarks/repeatability_thresholds_v1.json"
    thresholds = json.loads(threshold_path.read_text(encoding="utf-8"))

    assert thresholds["schema_version"] == "batchstudio-repeatability-thresholds/v1"
    assert set(thresholds["workloads"]) == set(WORKLOAD_DEFINITIONS)
    assert thresholds["source_fixture_manifest_sha256"] == sha256_json_file(
        REPOSITORY_ROOT / "benchmarks/fixture_manifest_v1.json"
    )
    assert all(
        workload["pilot_n"] == len(workload["pilot_raw_wall_clock_seconds"])
        for workload in thresholds["workloads"].values()
    )


def test_session_comparison_rejects_identity_drift_and_preserves_raw_sessions(
    tmp_path: Path,
):
    thresholds = {
        "schema_version": "batchstudio-repeatability-thresholds/v1",
        "source_fixture_manifest_sha256": "c" * 64,
        "workloads": {
            workload_id: {"repeatability_threshold_percent": 5.0}
            for workload_id in WORKLOAD_DEFINITIONS
        },
    }
    first = _valid_session_record(profile="canonical")
    second = copy.deepcopy(first)
    second["session_id"] = "test-session-2"
    controlled_configuration = {
        "workloads": {workload_id: {} for workload_id in WORKLOAD_DEFINITIONS},
        "timeout_seconds_per_workload": 120.0,
        "outlier_rule": "retain all",
        "validation_boundary": "after timed region",
        "threshold_manifest": thresholds,
    }
    first["configuration"] = copy.deepcopy(controlled_configuration)
    second["configuration"] = copy.deepcopy(controlled_configuration)
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    thresholds_path = tmp_path / "thresholds.json"
    first_path.write_text(json.dumps(first), encoding="utf-8")
    second_path.write_text(json.dumps(second), encoding="utf-8")
    thresholds_path.write_text(json.dumps(thresholds), encoding="utf-8")

    comparison = compare_sessions(first_path, second_path, thresholds_path)

    assert comparison["status"] == "PASS"
    assert all(item["repeatability"] == "PASS" for item in comparison["workloads"])
    assert json.loads(first_path.read_text(encoding="utf-8")) == first
    second["environment"]["cpu"] = "different"
    second_path.write_text(json.dumps(second), encoding="utf-8")
    with pytest.raises(BenchmarkConfigurationError, match="environment"):
        compare_sessions(first_path, second_path, thresholds_path)


def test_session_comparison_rejects_thresholds_for_another_fixture(tmp_path: Path):
    thresholds = {
        "schema_version": "batchstudio-repeatability-thresholds/v1",
        "source_fixture_manifest_sha256": "d" * 64,
        "workloads": {
            workload_id: {"repeatability_threshold_percent": 5.0}
            for workload_id in WORKLOAD_DEFINITIONS
        },
    }
    first = _valid_session_record(profile="canonical")
    second = copy.deepcopy(first)
    second["session_id"] = "test-session-2"
    configuration = {
        "workloads": {workload_id: {} for workload_id in WORKLOAD_DEFINITIONS},
        "timeout_seconds_per_workload": 120.0,
        "outlier_rule": "retain all",
        "validation_boundary": "after timed region",
        "threshold_manifest": thresholds,
    }
    first["configuration"] = copy.deepcopy(configuration)
    second["configuration"] = copy.deepcopy(configuration)
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    thresholds_path = tmp_path / "thresholds.json"
    first_path.write_text(json.dumps(first), encoding="utf-8")
    second_path.write_text(json.dumps(second), encoding="utf-8")
    thresholds_path.write_text(json.dumps(thresholds), encoding="utf-8")

    with pytest.raises(BenchmarkConfigurationError, match="another session fixture"):
        compare_sessions(first_path, second_path, thresholds_path)


def test_committed_canonical_evidence_recomputes_exactly():
    evidence_root = REPOSITORY_ROOT / Path(
        "benchmarks/evidence/v1/win11-i7-1260p-refs-balanced-py313-v1"
    )
    first_path = evidence_root / "session-1.json"
    second_path = evidence_root / "session-2.json"
    comparison_path = evidence_root / "comparison.json"
    thresholds_path = REPOSITORY_ROOT / "benchmarks/repeatability_thresholds_v1.json"

    recorded = json.loads(comparison_path.read_text(encoding="utf-8"))
    recomputed = compare_sessions(first_path, second_path, thresholds_path)

    assert recomputed == recorded
    assert recorded["status"] == "PASS"
    assert recorded["repository_sha"] == "05ad00dc8f5b29e5fb6a0f1dcfe7828c5a3c59d2"
    assert all(item["repeatability"] == "PASS" for item in recorded["workloads"])


def test_evidence_writer_refuses_overwrite(tmp_path: Path):
    evidence_path = tmp_path / "evidence.json"
    write_new_json(evidence_path, {"status": "PASS"})

    with pytest.raises(BenchmarkConfigurationError, match="overwrite"):
        write_new_json(evidence_path, {"status": "PASS"})

    assert json.loads(evidence_path.read_text(encoding="utf-8")) == {"status": "PASS"}


def test_metadata_hashes_ignore_checkout_line_endings(tmp_path: Path):
    json_lf = tmp_path / "json-lf.json"
    json_crlf = tmp_path / "json-crlf.json"
    text_lf = tmp_path / "text-lf.txt"
    text_crlf = tmp_path / "text-crlf.txt"
    json_lf.write_bytes(b'{"a": 1, "b": [2, 3]}\n')
    json_crlf.write_bytes(b'{\r\n  "b": [2, 3],\r\n  "a": 1\r\n}\r\n')
    text_lf.write_bytes(b"alpha\nbeta\n")
    text_crlf.write_bytes(b"alpha\r\nbeta\r\n")

    assert sha256_json_file(json_lf) == sha256_json_file(json_crlf)
    assert sha256_normalized_text_file(text_lf) == sha256_normalized_text_file(
        text_crlf
    )


def test_evidence_writer_preserves_preexisting_temporary_path(tmp_path: Path):
    evidence_path = tmp_path / "evidence.json"
    temporary_path = tmp_path / "evidence.json.tmp"
    temporary_path.write_bytes(b"unrelated")

    with pytest.raises(FileExistsError):
        write_new_json(evidence_path, {"status": "PASS"})

    assert temporary_path.read_bytes() == b"unrelated"
    assert not evidence_path.exists()
