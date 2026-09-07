"""Write-free per-file planning; generated paths are never opened as inputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.contracts import (
    ArtifactDescriptor, CheckOutcome, PlanDiagnostic, PlanFact, PlanResult, PlanningContext,
)
from core.operations import OperationRegistry
from core.security import OutputPathAllocator, render_filename, resolve_safe_output
from core.workflow import Workflow


@dataclass
class PlanningSession:
    context: PlanningContext
    allocator: OutputPathAllocator | None = None
    observations: list[tuple] = field(default_factory=list)

    def __post_init__(self):
        if self.allocator is None:
            self.allocator = OutputPathAllocator(Path(self.context.output_root))


def planning_preflight(context, registry):
    from core.processor import compile_workflow, validate_output_directory
    workflow = Workflow.from_dict(context.workflow_dict())
    valid, error = workflow.validate()
    if not valid:
        return (PlanDiagnostic(0, "workflow", "structure", "structure", CheckOutcome.FAILED, error),)
    compilation = compile_workflow(workflow, registry, check_capabilities=False)
    diagnostics = list(compilation.diagnostics)
    if compilation.aggregate_operation_id:
        diagnostics.append(PlanDiagnostic(0, "pdf_merge", "aggregate_boundary", "structure",
                                          CheckOutcome.FAILED, "Aggregate operation requires batch execution"))
    valid, error = validate_output_directory(context.output_root, dry_run=True)
    if not valid:
        diagnostics.append(PlanDiagnostic(0, "output_dir", "destination", "naming", CheckOutcome.FAILED, error))
    else:
        diagnostics.append(PlanDiagnostic(0, "output_dir", "destination", "naming", CheckOutcome.CHECKED, error))
    return tuple(diagnostics)


def _verdict(checks, complete):
    outcomes = {check.outcome for check in checks}
    if CheckOutcome.FAILED in outcomes:
        return "REJECTED"
    if CheckOutcome.UNSUPPORTED in outcomes:
        return "UNSUPPORTED"
    if not complete:
        return "UNASSESSED"
    return "CONDITIONAL" if CheckOutcome.DEFERRED in outcomes else "CHECKED"


def plan_file(session, file_path, counter, registry, *, preflight=(), continue_assessment=lambda: True):
    from core.processor import validate_file_path
    context = session.context
    try:
        origin = (counter, str(Path(file_path).resolve(strict=False)))
    except (OSError, ValueError):
        origin = (counter, str(file_path))
    workflow = Workflow.from_dict(context.workflow_dict())
    disabled = tuple(index for index, step in enumerate(workflow.steps, 1) if not step.enabled)
    enabled = [(index, step) for index, step in enumerate(workflow.steps, 1) if step.enabled]
    checks, artifacts = list(preflight), []
    blocked = any(check.outcome == CheckOutcome.FAILED for check in checks)
    complete, interrupted, started = True, False, False
    current = None
    step_index = 0
    try:
        if not continue_assessment():
            complete = False
        elif not blocked:
            started = True
            valid, error = validate_file_path(file_path)
            if not valid:
                checks.append(PlanDiagnostic(0, "source", "source_path", "source", CheckOutcome.FAILED, error))
                blocked = True
            else:
                source = Path(origin[1])
                try:
                    before = source.stat()
                    with source.open("rb") as stream:
                        stream.read(1)
                    after = source.stat()
                    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                        raise OSError("Source changed during read-only inspection")
                    session.observations.append(("source_identity", origin, identity))
                    current = ArtifactDescriptor(
                        origin, None, "MATERIALIZED_SOURCE", registry.classify_extension(source.suffix),
                        None, source.suffix,
                        facts=(PlanFact("source_identity", identity, "OBSERVED_SOURCE"),),
                        unknown_properties=("full_content_integrity",),
                    )
                    artifacts.append(current)
                    checks.append(PlanDiagnostic(0, "source", "source_readability", "source", CheckOutcome.CHECKED,
                                                  "Actual source path, size and bounded read checked"))
                except OSError as exc:
                    checks.append(PlanDiagnostic(0, "source", "source_readability", "source", CheckOutcome.FAILED, str(exc)))
                    blocked = True
        for step_index, step in enabled:
            if complete and not continue_assessment():
                complete = False
            if blocked or not complete:
                checks.append(PlanDiagnostic(step_index, step.operation_id, "upstream", "generated_content",
                                              CheckOutcome.BLOCKED, "Upstream failed or assessment did not complete"))
                continue
            started = True
            operation = registry.get_operation(step.operation_id, step.config)
            if operation is None:
                checks.append(PlanDiagnostic(step_index, step.operation_id, "operation", "structure",
                                              CheckOutcome.FAILED, f"Unknown operation: {step.operation_id}"))
                blocked = True
                continue
            if not operation.supports_dry_run or not operation.supports_planning:
                checks.append(PlanDiagnostic(step_index, step.operation_id, "planning_support", "structure",
                                              CheckOutcome.UNSUPPORTED,
                                              f"Operation {operation.name} does not support dry run/planning"))
                blocked = True
                continue
            config_valid, config_error = operation.validate_config()
            checks.append(PlanDiagnostic(step_index, step.operation_id, "configuration", "structure",
                                          CheckOutcome.CHECKED if config_valid else CheckOutcome.FAILED,
                                          config_error or "Configuration schema checked"))
            if not config_valid:
                blocked = True
                continue
            plan = operation.plan(current, step_index)
            checks.extend(plan.diagnostics)
            blocked = any(check.outcome in {CheckOutcome.FAILED, CheckOutcome.UNSUPPORTED}
                          for check in plan.diagnostics)
            if blocked:
                continue
            if not continue_assessment():
                complete = False
                continue
            base = render_filename(context.naming_pattern, Path(origin[1]).stem, counter, context.timestamp)
            candidate = Path(context.output_root) / (base + plan.suffix)
            try:
                intended = operation.plan_output_path(current, candidate, context, counter)
                destination = resolve_safe_output(Path(context.output_root), intended.name)
                destination = session.allocator.allocate(destination.stem, destination.suffix)
                session.observations.append(("allocated_destination", step_index, str(destination)))
            except (OSError, ValueError) as exc:
                checks.append(PlanDiagnostic(step_index, step.operation_id, "destination", "naming",
                                              CheckOutcome.FAILED, str(exc)))
                blocked = True
                continue
            checks.append(PlanDiagnostic(step_index, step.operation_id, "destination", "naming",
                                          CheckOutcome.CHECKED, f"Proposed destination: {destination}"))
            current = ArtifactDescriptor(origin, (step_index, step.operation_id), "PLANNED",
                                         plan.logical_type, plan.logical_format, destination.suffix,
                                         str(destination), plan.facts, plan.unknown_properties)
            artifacts.append(current)
    except Exception as exc:
        complete, interrupted = False, True
        checks.append(PlanDiagnostic(0, "planner", "assessment_exception", "assessment", CheckOutcome.BLOCKED,
                                      f"Assessment interrupted: {type(exc).__name__}: {exc}"))
        for remaining_index, remaining_step in enabled:
            if remaining_index >= step_index:
                checks.append(PlanDiagnostic(remaining_index, remaining_step.operation_id,
                                              "upstream", "assessment", CheckOutcome.BLOCKED,
                                              "Assessment interrupted before this step completed"))
    state = "COMPLETE" if complete else ("PARTIAL" if started else "NOT_STARTED")
    verdict = _verdict(checks, complete)
    final = current.destination if current and complete and verdict in {"CHECKED", "CONDITIONAL"} else None
    return PlanResult(origin, state, verdict, tuple(checks), tuple(artifacts), disabled, final, interrupted)


def _adapt_aggregate(stats, context):
    """Add planning evidence without changing aggregate consumption/error counters."""
    stats._planning_context = context
    stats.execution_state = "CANCELLED" if stats.stopped else "COMPLETED"
    successful = list(stats.results)
    errors = list(stats.errors)
    assigned_errors = set()
    for index, source in enumerate(context.inputs, 1):
        record = next((record for record in successful if record["file"] == source), None)
        if record is not None:
            successful.remove(record)
            final = record["result"].get("planned_output")
            checks = (
                PlanDiagnostic(1, "pdf_merge", "source_content", "source", CheckOutcome.CHECKED,
                               "Original PDF consumed by the standalone dry-run lifecycle"),
                PlanDiagnostic(1, "pdf_merge", "execution", "execution", CheckOutcome.DEFERRED,
                               "Physical merge, generated PDF validity and ownership require execution"),
            )
            plan = PlanResult((index, source), "COMPLETE" if final else "PARTIAL",
                              "CONDITIONAL" if final else "UNASSESSED", checks, planned_output=final)
            data = plan.to_dict()
            record["result"].update(data)
            stats.plan_results.append(data)
        else:
            error_index = next((i for i, error in enumerate(errors)
                                if i not in assigned_errors and error["file"] == source), None)
            if error_index is not None:
                assigned_errors.add(error_index)
                diagnostic = PlanDiagnostic(1, "pdf_merge", "source_content", "source", CheckOutcome.FAILED,
                                            errors[error_index]["error"])
                plan = PlanResult((index, source), "COMPLETE", "REJECTED", (diagnostic,))
            else:
                plan = PlanResult((index, source), "NOT_STARTED", "UNASSESSED", (
                    PlanDiagnostic(1, "pdf_merge", "upstream", "assessment", CheckOutcome.BLOCKED,
                                   "Aggregate input was not assessed"),))
            stats.plan_results.append(plan.to_dict())
    stats.planning_errors = [error for i, error in enumerate(errors) if i not in assigned_errors]
    if any(result["assessment_state"] != "COMPLETE" for result in stats.plan_results) and not stats.stopped:
        stats.execution_state = "INCOMPLETE"
    return stats


def run_planning_batch(processor, file_list, workflow, output_dir, naming_pattern, context=None):
    from core.processor import ProcessingStats
    context = context or PlanningContext.capture(file_list, workflow.to_dict(), naming_pattern, output_dir)
    workflow = Workflow.from_dict(context.workflow_dict())
    if any(isinstance(step.operation_id, str) and step.operation_id in processor.operation_registry.aggregate_operations
           for step in workflow.get_enabled_steps()):
        stats = processor._process_batch(list(context.inputs), workflow, context.output_root,
                                         context.naming_pattern.replace("{timestamp}", context.timestamp), dry_run=True)
        return _adapt_aggregate(stats, context)
    stats = ProcessingStats(dry_run=True)
    stats._planning_context = context
    processor.stats = stats
    processor.dry_run = True
    processor.is_running, processor.is_paused = True, False
    processor._aggregate_finalization_pending = False
    stats.total_files, stats.start_time = len(context.inputs), datetime.now()
    session = PlanningSession(context)
    try:
        preflight = planning_preflight(context, processor.operation_registry)
        failed = [check for check in preflight if check.outcome == CheckOutcome.FAILED]
        if failed:
            for check in failed:
                stats.add_error(check.operation_id, check.reason)
                stats.planning_errors.append(check.to_dict())
            for index, source in enumerate(context.inputs, 1):
                stats.add_plan(PlanResult((index, source), "NOT_STARTED", "UNASSESSED", tuple(
                    PlanDiagnostic(step_index, step.operation_id, "upstream", "structure", CheckOutcome.BLOCKED,
                                   "Workflow/output preflight failed")
                    for step_index, step in enumerate(workflow.steps, 1) if step.enabled)))
            return stats
        processor._update_progress(0, stats.total_files,
                                   "DRY RUN: no execution or report writes. Future write permission is not physically verified.")

        def continue_assessment():
            processor._wait_if_paused()
            return processor.is_running

        for index, source in enumerate(context.inputs, 1):
            result = plan_file(session, source, index, processor.operation_registry,
                               preflight=preflight, continue_assessment=continue_assessment)
            stats.add_plan(result)
            if result.interrupted:
                stats.execution_state = "INCOMPLETE"
                processor.is_running = False
            processor._update_progress(index, stats.total_files, result.to_dict()["message"])
    except Exception as exc:
        stats.execution_state = "INCOMPLETE"
        stats.planning_errors.append({"error": f"Planning interrupted: {exc}"})
        stats.add_error("planner", f"Planning interrupted: {exc}")
        for index in range(len(stats.plan_results) + 1, stats.total_files + 1):
            stats.add_plan(PlanResult((index, context.inputs[index - 1]), "NOT_STARTED", "UNASSESSED", ()))
    finally:
        if stats.execution_state != "INCOMPLETE":
            stats.execution_state = "CANCELLED" if stats.stopped else "COMPLETED"
        stats.end_time = datetime.now()
        processor.is_running = False
        processor.is_paused = False
    return stats
