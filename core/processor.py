"""
BatchStudio - Processor Module
Secure batch processor with typed operation results and aggregate workflow support.
"""

from __future__ import annotations

import csv
import html
import os
import shutil
import tempfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import FIRST_COMPLETED, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.operations import AggregateOperation, OperationRegistry
from core.security import (
    OutputPathAllocator,
    output_identity,
    remove_owned_output,
    resolve_safe_output,
    sanitize_filename,
    sanitize_for_spreadsheet,
)
from core.workflow import Workflow

MAX_FILE_SIZE = 500 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tiff",
    ".tif",
    ".pdf",
    ".csv",
    ".xlsx",
    ".xls",
    ".txt",
    ".json",
    ".xml",
}


@dataclass(slots=True)
class WorkflowCompilation:
    valid: bool
    errors: List[str]
    aggregate_operation_id: Optional[str] = None


def validate_file_path(file_path: str, base_dir: Optional[str] = None) -> tuple[bool, str]:
    try:
        path = Path(file_path)
        resolved = path.resolve(strict=False)

        if ".." in str(path):
            return False, "Path traversal detected"

        if base_dir:
            base_resolved = Path(base_dir).resolve(strict=False)
            if not resolved.is_relative_to(base_resolved):
                return False, "File outside allowed directory"

        if not resolved.exists() or not resolved.is_file():
            return False, "File does not exist"

        if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
            return False, f"File type '{resolved.suffix.lower()}' not allowed"

        if resolved.stat().st_size > MAX_FILE_SIZE:
            return False, "File too large"

        return True, ""
    except Exception as exc:
        return False, str(exc)


def validate_output_directory(output_dir: str) -> tuple[bool, str]:
    try:
        out = Path(output_dir).resolve(strict=False)
        out.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(dir=out, prefix=".batchstudio-probe-", mode="wb") as probe:
            probe.write(b"ok")
            probe.flush()
        return True, ""
    except PermissionError:
        return False, "No write permission for output directory"
    except Exception as exc:
        return False, str(exc)


def compile_workflow(workflow: Workflow, registry: OperationRegistry) -> WorkflowCompilation:
    errors: List[str] = []
    enabled_steps = workflow.get_enabled_steps()
    if not enabled_steps:
        errors.append("Workflow must contain at least one enabled step")
        return WorkflowCompilation(valid=False, errors=errors)

    current_type = "any"
    aggregate_id: Optional[str] = None

    for index, step in enumerate(enabled_steps):
        op = registry.get_operation(step.operation_id, step.config)
        agg = registry.get_aggregate_operation(step.operation_id, step.config)

        if op is None and agg is None:
            errors.append(f"Unknown operation at step {index + 1}: {step.operation_id}")
            continue

        if agg is not None:
            config_ok, config_error = agg.validate_config()
            if not config_ok:
                errors.append(f"Invalid config at step {index + 1} ({step.operation_id}): {config_error}")
            if index != len(enabled_steps) - 1:
                errors.append("Aggregate operations must be the last workflow step")
            aggregate_id = step.operation_id
            continue

        assert op is not None
        config_ok, config_error = op.validate_config()
        if not config_ok:
            errors.append(f"Invalid config at step {index + 1} ({step.operation_id}): {config_error}")

        capability_error = op.get_capability_error()
        if capability_error:
            errors.append(f"Missing capability at step {index + 1} ({step.operation_id}): {capability_error}")

        accepted = getattr(op, "accepted_types", {"any"})
        if "any" not in accepted and current_type not in accepted and current_type != "any":
            errors.append(
                f"Type incompatibility at step {index + 1}: expected {accepted}, got {current_type}"
            )

        if getattr(op, "output_type", "any") != "same":
            current_type = getattr(op, "output_type", current_type)

    return WorkflowCompilation(valid=len(errors) == 0, errors=errors, aggregate_operation_id=aggregate_id)


def _render_name(pattern: str, file_path: Path, index: int) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = (
        pattern.replace("{original}", file_path.stem)
        .replace("{timestamp}", timestamp)
        .replace("{counter}", f"{index:03d}")
    )
    return sanitize_filename(stem)


def process_single_file(
    file_path: str,
    workflow_dict: Dict[str, Any],
    output_dir: str,
    naming_pattern: str,
    dry_run: bool = False,
    index: int = 1,
    allocator: Optional[OutputPathAllocator] = None,
) -> Dict[str, Any]:
    registry = OperationRegistry()

    try:
        valid, error = validate_file_path(file_path)
        if not valid:
            return {"success": False, "file": file_path, "error": error}

        workflow = Workflow.from_dict(workflow_dict)
        output_root = Path(output_dir).resolve(strict=False)
        source = Path(file_path).resolve(strict=False)

        current_input = source
        generated_files: List[tuple[Path, tuple[int, int]]] = []

        for step in workflow.get_enabled_steps():
            if registry.get_aggregate_operation(step.operation_id, step.config) is not None:
                continue

            operation = registry.get_operation(step.operation_id, step.config)
            if operation is None:
                return {"success": False, "file": file_path, "error": f"Unknown operation: {step.operation_id}"}

            if not operation.validate(current_input):
                return {
                    "success": False,
                    "file": file_path,
                    "error": f"Operation {operation.name} cannot process this file",
                }

            name_base = _render_name(naming_pattern, source, index)
            planned_output = output_root / (name_base + current_input.suffix)
            operation.output_allocator = allocator

            if step.operation_id == "file_rename":
                operation.config["counter"] = index

            result = operation.execute(current_input, planned_output, dry_run=dry_run)
            if not result.success:
                return {
                    "success": False,
                    "file": file_path,
                    "error": result.error or "Operation failed",
                }

            if result.output_path is None:
                return {
                    "success": False,
                    "file": file_path,
                    "error": f"Operation {operation.name} did not return output_path",
                }

            current_input = result.output_path
            if not dry_run:
                generated_files.append((current_input, output_identity(current_input)))

        final_output = current_input

        if dry_run:
            return {
                "success": True,
                "file": file_path,
                "output": str(final_output),
                "message": "Dry run validated",
            }

        for candidate, identity in generated_files[:-1]:
            remove_owned_output(candidate, identity)

        return {
            "success": True,
            "file": file_path,
            "output": str(final_output),
            "message": "Processed successfully",
        }
    except Exception as exc:
        return {
            "success": False,
            "file": file_path,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


class ProcessingStats:
    def __init__(self):
        self.total_files = 0
        self.processed_files = 0
        self.failed_files = 0
        self.skipped_files = 0
        self.start_time = None
        self.end_time = None
        self.errors: List[Dict[str, str]] = []
        self.results: List[Dict[str, Any]] = []

    def add_error(self, file_path: str, error: str):
        self.errors.append({"file": file_path, "error": error, "timestamp": datetime.now().isoformat()})
        self.failed_files += 1

    def add_result(self, file_path: str, result: Dict[str, Any]):
        self.results.append(
            {
                "file": file_path,
                "output": result.get("output", ""),
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.processed_files += 1

    def get_duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "skipped_files": self.skipped_files,
            "duration_seconds": self.get_duration(),
            "errors": self.errors,
            "results": self.results,
        }


class BatchProcessor:
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)
        self.operation_registry = OperationRegistry()
        self.is_running = False
        self.is_paused = False
        self.dry_run = False
        self.progress_callback: Optional[Callable] = None
        self.stats = ProcessingStats()
        self._lock = threading.Lock()

    def set_progress_callback(self, callback: Callable):
        self.progress_callback = callback

    def _update_progress(self, current: int, total: int, message: str = ""):
        if self.progress_callback:
            self.progress_callback(current, total, message)

    def validate_files_for_workflow(self, file_list: List[str], workflow: Workflow) -> tuple[List[str], List[Dict[str, str]]]:
        valid_files = []
        errors = []

        for file_path in file_list:
            is_valid, error = validate_file_path(file_path)
            if not is_valid:
                errors.append({"file": file_path, "error": error})
                continue
            valid_files.append(file_path)

        return valid_files, errors

    def _wait_if_paused(self):
        while self.is_paused and self.is_running:
            time.sleep(0.05)

    def _process_aggregate_pdf_merge(
        self,
        file_list: List[str],
        aggregate_operation: AggregateOperation,
        output_dir: str,
        naming_pattern: str,
        dry_run: bool,
    ) -> None:
        output_root = Path(output_dir).resolve(strict=False)
        merge_name = sanitize_filename(
            aggregate_operation.config.get("output_filename", _render_name(naming_pattern, Path(file_list[0]), 1) + "_merged")
        )
        merge_path = resolve_safe_output(output_root, merge_name, required_suffix=".pdf")
        merge_path = OutputPathAllocator(output_root).allocate(merge_path.stem, merge_path.suffix)
        aggregate_operation.begin(merge_path, dry_run=dry_run)

        for index, file_path in enumerate(file_list, start=1):
            if not self.is_running:
                return
            self._wait_if_paused()
            result = aggregate_operation.consume(Path(file_path))
            if result.success:
                self.stats.add_result(file_path, {"message": result.message})
            else:
                self.stats.add_error(file_path, result.error or "Failed to consume PDF")
            self._update_progress(index, len(file_list), result.message or result.error or "")

        finalize = aggregate_operation.finalize()
        if not finalize.success:
            self.stats.add_error("pdf_merge_finalize", finalize.error or "Finalize failed")
        else:
            for record in self.stats.results:
                record["output"] = str(finalize.output_path)
                record["result"]["output"] = str(finalize.output_path)
            self._update_progress(len(file_list), len(file_list), finalize.message)

    def process_batch(
        self,
        file_list: List[str],
        workflow: Workflow,
        output_dir: str,
        naming_pattern: str = "{original}_processed",
        dry_run: bool = False,
    ) -> ProcessingStats:
        self.is_running = True
        self.is_paused = False
        self.dry_run = dry_run
        self.stats = ProcessingStats()
        self.stats.total_files = len(file_list)
        self.stats.start_time = datetime.now()

        is_valid, error = validate_output_directory(output_dir)
        if not is_valid:
            self.stats.add_error("output_dir", f"Invalid output directory: {error}")
            self.stats.end_time = datetime.now()
            self.is_running = False
            return self.stats

        workflow_valid, workflow_error = workflow.validate()
        if not workflow_valid:
            self.stats.add_error("workflow", f"Invalid workflow: {workflow_error}")
            self.stats.end_time = datetime.now()
            self.is_running = False
            return self.stats

        compilation = compile_workflow(workflow, self.operation_registry)
        if not compilation.valid:
            for comp_error in compilation.errors:
                self.stats.add_error("workflow", comp_error)
            self.stats.end_time = datetime.now()
            self.is_running = False
            return self.stats

        if dry_run:
            self._update_progress(0, len(file_list), "DRY RUN MODE - no files will be modified")
        else:
            self._update_progress(0, len(file_list), "Starting batch processing")

        if compilation.aggregate_operation_id == "pdf_merge":
            aggregate = self.operation_registry.get_aggregate_operation("pdf_merge", workflow.get_enabled_steps()[-1].config)
            if aggregate is None:
                self.stats.add_error("workflow", "Aggregate PDF merge operation could not be created")
            else:
                self._process_aggregate_pdf_merge(file_list, aggregate, output_dir, naming_pattern, dry_run)

            self.stats.end_time = datetime.now()
            self.is_running = False
            return self.stats

        workflow_dict = workflow.to_dict()
        allocator = OutputPathAllocator(Path(output_dir))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            pending_inputs = list(enumerate(file_list, start=1))
            futures: Dict[Any, str] = {}

            def submit_next_available() -> None:
                while self.is_running and not self.is_paused and pending_inputs and len(futures) < self.max_workers:
                    index, next_file = pending_inputs.pop(0)
                    future = executor.submit(
                        process_single_file,
                        next_file,
                        workflow_dict,
                        output_dir,
                        naming_pattern,
                        dry_run,
                        index,
                        allocator,
                    )
                    futures[future] = next_file

            processed_count = 0
            submit_next_available()

            while futures:
                if not self.is_running:
                    for future in list(futures):
                        future.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                if self.is_paused:
                    time.sleep(0.05)
                    continue

                done, _ = wait(list(futures.keys()), timeout=0.1, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                for future in done:
                    file_path = futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {"success": False, "file": file_path, "error": str(exc)}

                    processed_count += 1
                    if result["success"]:
                        self.stats.add_result(result["file"], result)
                        self._update_progress(processed_count, len(file_list), f"Processed {Path(result['file']).name}")
                    else:
                        self.stats.add_error(result["file"], result.get("error", "Unknown error"))
                        self._update_progress(processed_count, len(file_list), f"Failed {Path(result['file']).name}")

                submit_next_available()

        self.stats.end_time = datetime.now()
        self.is_running = False
        return self.stats

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_running = False
        self.is_paused = False

    def generate_report(self, stats: ProcessingStats, output_path: str, format: str = "html") -> bool:
        try:
            if format == "html":
                return self._generate_html_report(stats, output_path)
            if format == "csv":
                return self._generate_csv_report(stats, output_path)
            return False
        except Exception:
            return False

    def _generate_html_report(self, stats: ProcessingStats, output_path: str) -> bool:
        lines = [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'><title>BatchStudio Processing Report</title></head><body>",
            f"<h1>BatchStudio Processing Report</h1><p>Generated: {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</p>",
            f"<p>Total: {stats.total_files} Processed: {stats.processed_files} Failed: {stats.failed_files} Duration: {stats.get_duration():.1f}s</p>",
            "<table border='1' cellpadding='4'><thead><tr><th>File</th><th>Status</th><th>Details</th></tr></thead><tbody>",
        ]

        for result in stats.results:
            file_value = html.escape(Path(result["file"]).name)
            details = html.escape(str(result["result"].get("message", "Processed")))
            lines.append(f"<tr><td>{file_value}</td><td>Success</td><td>{details}</td></tr>")

        for error in stats.errors:
            file_value = html.escape(Path(error["file"]).name)
            details = html.escape(str(error["error"]))
            lines.append(f"<tr><td>{file_value}</td><td>Failed</td><td>{details}</td></tr>")

        lines.append("</tbody></table></body></html>")
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
        return True

    def _generate_csv_report(self, stats: ProcessingStats, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["File", "Status", "Details", "Timestamp"])
            for result in stats.results:
                writer.writerow(
                    [
                        sanitize_for_spreadsheet(result["file"]),
                        "Success",
                        sanitize_for_spreadsheet(result["result"].get("message", "Processed")),
                        sanitize_for_spreadsheet(result["timestamp"]),
                    ]
                )
            for error in stats.errors:
                writer.writerow(
                    [
                        sanitize_for_spreadsheet(error["file"]),
                        "Failed",
                        sanitize_for_spreadsheet(error["error"]),
                        sanitize_for_spreadsheet(error["timestamp"]),
                    ]
                )
        return True
