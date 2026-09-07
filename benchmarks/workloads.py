"""Frozen V12-PERF workload definitions and correctness guardrails."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from pypdf import PdfReader

from benchmarks.fixtures import fixture_by_id, merge_page_dimensions, sha256_file
from core import BatchProcessor, Workflow


SENTINEL_BYTES = b"V12-PERF collision sentinel: preserve exactly\n"


class BenchmarkExecutionError(RuntimeError):
    """Raised when a workload cannot produce valid performance evidence."""


@dataclass(frozen=True, slots=True)
class WorkloadDefinition:
    workload_id: str
    operation_id: str
    fixture_id: str
    input_repetitions: int
    input_count: int
    worker_count: int
    naming_pattern: str
    operation_config: dict[str, Any]
    expected_output_count: int
    deterministic_output: bool
    profile: str


WORKLOAD_DEFINITIONS = {
    "B1": WorkloadDefinition(
        workload_id="B1",
        operation_id="file_rename",
        fixture_id="F1",
        input_repetitions=256,
        input_count=256,
        worker_count=1,
        naming_pattern="ignored_by_file_rename",
        operation_config={"pattern": "{original}_{counter}"},
        expected_output_count=256,
        deterministic_output=True,
        profile="small-file/fixed processor overhead",
    ),
    "B2": WorkloadDefinition(
        workload_id="B2",
        operation_id="image_resize",
        fixture_id="F2",
        input_repetitions=1,
        input_count=1,
        worker_count=1,
        naming_pattern="benchmark_owned",
        operation_config={
            "width": 2048,
            "height": 1536,
            "maintain_aspect": False,
            "quality": 95,
        },
        expected_output_count=1,
        deterministic_output=True,
        profile="single-file image decode/resample/encode",
    ),
    "B3": WorkloadDefinition(
        workload_id="B3",
        operation_id="pdf_watermark",
        fixture_id="F3",
        input_repetitions=1,
        input_count=1,
        worker_count=1,
        naming_pattern="benchmark_owned",
        operation_config={"text": "BATCHSTUDIO V12-PERF"},
        expected_output_count=1,
        deterministic_output=False,
        profile="page-aware PDF transform",
    ),
    "B4": WorkloadDefinition(
        workload_id="B4",
        operation_id="pdf_merge",
        fixture_id="F4",
        input_repetitions=4,
        input_count=64,
        worker_count=1,
        naming_pattern="ignored_by_pdf_merge",
        operation_config={"output_filename": "benchmark_owned.pdf"},
        expected_output_count=1,
        deterministic_output=True,
        profile="ordered aggregate PDF parse/write",
    ),
    "B5": WorkloadDefinition(
        workload_id="B5",
        operation_id="image_resize",
        fixture_id="F5",
        input_repetitions=4,
        input_count=32,
        worker_count=4,
        naming_pattern="{original}_benchmark",
        operation_config={
            "width": 1024,
            "height": 768,
            "maintain_aspect": False,
            "quality": 95,
        },
        expected_output_count=32,
        deterministic_output=True,
        profile="four-worker image batch throughput",
    ),
}


def get_workload_definition(workload_id: str) -> WorkloadDefinition:
    try:
        return WORKLOAD_DEFINITIONS[workload_id]
    except KeyError as error:
        raise BenchmarkExecutionError(f"Unknown workload: {workload_id}") from error


def _fixture_files(
    definition: WorkloadDefinition,
    fixture_manifest: dict[str, Any],
    fixture_root: Path,
) -> tuple[list[Path], dict[str, str]]:
    fixture = fixture_by_id(fixture_manifest, definition.fixture_id)
    base_files = [fixture_root / record["path"] for record in fixture["files"]]
    files = base_files * definition.input_repetitions
    expected_hashes = {record["path"]: record["sha256"] for record in fixture["files"]}
    if len(files) != definition.input_count:
        raise BenchmarkExecutionError(
            f"{definition.workload_id} expected {definition.input_count} inputs, got {len(files)}"
        )
    return files, expected_hashes


def _create_workflow(definition: WorkloadDefinition) -> Workflow:
    workflow = Workflow(f"V12-PERF {definition.workload_id}")
    workflow.add_step(definition.operation_id, definition.operation_config)
    return workflow


def _sentinel_path(
    definition: WorkloadDefinition,
    input_files: list[Path],
    output_root: Path,
) -> Path:
    if definition.workload_id in {"B1", "B5"}:
        if definition.workload_id == "B1":
            return output_root / f"{input_files[0].stem}_001{input_files[0].suffix}"
        return output_root / f"{input_files[0].stem}_benchmark{input_files[0].suffix}"
    suffix = input_files[0].suffix
    if definition.workload_id == "B4":
        suffix = ".pdf"
    return output_root / f"benchmark_owned{suffix}"


def _assert_path_beneath(path: Path, root: Path) -> None:
    if not path.resolve().is_relative_to(root.resolve()):
        raise BenchmarkExecutionError(f"Output escaped iteration root: {path}")


def _box_values(box: Any) -> tuple[float, float, float, float]:
    return tuple(float(value) for value in box)  # type: ignore[return-value]


def _validate_image(path: Path, expected_size: tuple[int, int]) -> None:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        if image.format != "BMP" or image.mode != "RGB" or image.size != expected_size:
            details = f"format={image.format} mode={image.mode} size={image.size}"
            raise BenchmarkExecutionError(f"Invalid image output {path.name}: {details}")


def _validate_watermarked_pdf(source: Path, output: Path) -> None:
    source_reader = PdfReader(str(source))
    output_reader = PdfReader(str(output))
    if len(source_reader.pages) != 64 or len(output_reader.pages) != 64:
        raise BenchmarkExecutionError("B3 must preserve exactly 64 PDF pages")
    for index, (source_page, output_page) in enumerate(
        zip(source_reader.pages, output_reader.pages, strict=True)
    ):
        if _box_values(source_page.mediabox) != _box_values(output_page.mediabox):
            raise BenchmarkExecutionError(f"B3 MediaBox changed on page {index}")
        if _box_values(source_page.cropbox) != _box_values(output_page.cropbox):
            raise BenchmarkExecutionError(f"B3 CropBox changed on page {index}")
        if int(source_page.rotation) != int(output_page.rotation):
            raise BenchmarkExecutionError(f"B3 rotation changed on page {index}")
        if output_page.get_contents() is None:
            raise BenchmarkExecutionError(f"B3 watermark content missing on page {index}")


def _validate_merged_pdf(
    output: Path,
    fixture_manifest: dict[str, Any],
) -> None:
    fixture_by_id(fixture_manifest, "F4")
    expected_dimensions = merge_page_dimensions() * 4
    reader = PdfReader(str(output))
    if len(reader.pages) != len(expected_dimensions):
        raise BenchmarkExecutionError(
            f"B4 expected {len(expected_dimensions)} pages, got {len(reader.pages)}"
        )
    actual_dimensions = [
        [float(page.mediabox.width), float(page.mediabox.height)] for page in reader.pages
    ]
    if actual_dimensions != expected_dimensions:
        raise BenchmarkExecutionError("B4 merged PDF page order or dimensions changed")


def _validate_output_class(
    definition: WorkloadDefinition,
    input_files: list[Path],
    output_files: list[Path],
    fixture_manifest: dict[str, Any],
) -> None:
    if definition.workload_id == "B1":
        source_hash = sha256_file(input_files[0])
        if any(sha256_file(output_file) != source_hash for output_file in output_files):
            raise BenchmarkExecutionError("B1 output bytes differ from the input fixture")
    elif definition.workload_id == "B2":
        _validate_image(output_files[0], (2048, 1536))
    elif definition.workload_id == "B3":
        _validate_watermarked_pdf(input_files[0], output_files[0])
    elif definition.workload_id == "B4":
        _validate_merged_pdf(output_files[0], fixture_manifest)
    elif definition.workload_id == "B5":
        for output_file in output_files:
            _validate_image(output_file, (1024, 768))


def _validate_inputs_unchanged(
    fixture_root: Path,
    expected_hashes: dict[str, str],
) -> None:
    for relative_path, expected_hash in expected_hashes.items():
        actual_hash = sha256_file(fixture_root / relative_path)
        if actual_hash != expected_hash:
            raise BenchmarkExecutionError(f"Input fixture changed: {relative_path}")


def execute_iteration(
    definition: WorkloadDefinition,
    fixture_manifest: dict[str, Any],
    fixture_root: Path,
    iteration_root: Path,
    iteration_number: int,
) -> dict[str, Any]:
    input_files, expected_hashes = _fixture_files(definition, fixture_manifest, fixture_root)
    output_root = iteration_root / "output"
    output_root.mkdir(parents=True)
    sentinel = _sentinel_path(definition, input_files, output_root)
    sentinel.write_bytes(SENTINEL_BYTES)

    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    processor = BatchProcessor(max_workers=definition.worker_count)
    workflow = _create_workflow(definition)
    stats = processor.process_batch(
        [str(path) for path in input_files],
        workflow,
        str(output_root),
        naming_pattern=definition.naming_pattern,
        dry_run=False,
    )
    cpu_end = time.process_time_ns()
    wall_end = time.perf_counter_ns()

    if (
        stats.total_files != definition.input_count
        or stats.processed_files != definition.input_count
        or stats.failed_files != 0
        or stats.skipped_files != 0
        or stats.stopped
        or len(stats.results) != definition.input_count
        or stats.errors
    ):
        raise BenchmarkExecutionError(
            f"{definition.workload_id} returned invalid processing stats: {stats.to_dict()}"
        )

    result_paths = [Path(record["output"]).resolve() for record in stats.results]
    for result_path in result_paths:
        _assert_path_beneath(result_path, output_root)
        if not result_path.is_file():
            raise BenchmarkExecutionError(f"Expected output does not exist: {result_path}")
    unique_outputs = sorted(set(result_paths), key=lambda path: path.as_posix())
    if len(unique_outputs) != definition.expected_output_count:
        raise BenchmarkExecutionError(
            f"{definition.workload_id} expected {definition.expected_output_count} unique outputs, "
            f"got {len(unique_outputs)}"
        )
    if sentinel.read_bytes() != SENTINEL_BYTES:
        raise BenchmarkExecutionError(f"{definition.workload_id} changed the collision sentinel")
    if sentinel.resolve() in unique_outputs:
        raise BenchmarkExecutionError(
            f"{definition.workload_id} claimed the occupied sentinel path"
        )

    _validate_inputs_unchanged(fixture_root, expected_hashes)
    _validate_output_class(
        definition,
        input_files,
        unique_outputs,
        fixture_manifest,
    )

    output_hashes = {
        path.relative_to(output_root).as_posix(): sha256_file(path) for path in unique_outputs
    }
    output_hash_manifest = json.dumps(
        output_hashes,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "iteration": iteration_number,
        "wall_clock_seconds": (wall_end - wall_start) / 1_000_000_000,
        "cpu_time_seconds": (cpu_end - cpu_start) / 1_000_000_000,
        "files_processed": definition.input_count,
        "output_bytes": sum(path.stat().st_size for path in unique_outputs),
        "output_sha256": {
            "file_count": len(output_hashes),
            "manifest_sha256": hashlib.sha256(output_hash_manifest).hexdigest(),
            "unique_content_sha256": sorted(set(output_hashes.values())),
        },
        "correctness": "PASS",
    }


def _remove_completed_iteration(iteration_root: Path, work_root: Path) -> None:
    resolved_iteration = iteration_root.resolve()
    resolved_work_root = work_root.resolve()
    if resolved_iteration.parent != resolved_work_root or not resolved_iteration.name.startswith(
        ("warmup-", "measured-")
    ):
        raise BenchmarkExecutionError(f"Refusing unsafe iteration cleanup: {iteration_root}")
    shutil.rmtree(resolved_iteration)


def run_workload(
    definition: WorkloadDefinition,
    fixture_manifest: dict[str, Any],
    fixture_root: Path,
    work_root: Path,
    warmups: int,
    repetitions: int,
) -> list[dict[str, Any]]:
    if warmups < 0 or repetitions < 1:
        raise BenchmarkExecutionError("warmups must be >= 0 and repetitions must be >= 1")
    work_root.mkdir(parents=True, exist_ok=False)

    for warmup_index in range(1, warmups + 1):
        iteration_root = work_root / f"warmup-{warmup_index:03d}"
        execute_iteration(
            definition,
            fixture_manifest,
            fixture_root,
            iteration_root,
            warmup_index,
        )
        _remove_completed_iteration(iteration_root, work_root)

    samples = []
    for repetition_index in range(1, repetitions + 1):
        iteration_root = work_root / f"measured-{repetition_index:03d}"
        sample = execute_iteration(
            definition,
            fixture_manifest,
            fixture_root,
            iteration_root,
            repetition_index,
        )
        samples.append(sample)
        _remove_completed_iteration(iteration_root, work_root)

    if definition.deterministic_output:
        fingerprints = [sample["output_sha256"] for sample in samples]
        if any(fingerprint != fingerprints[0] for fingerprint in fingerprints[1:]):
            raise BenchmarkExecutionError(
                f"{definition.workload_id} produced nondeterministic output bytes"
            )
    return samples
