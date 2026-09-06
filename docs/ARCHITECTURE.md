# Architecture

## Components

- `main.py` creates the Tk root, constructs `ui.MainWindow`, and enters `mainloop`.
- `ui/main_window.py` owns shared `Settings`, `Workflow`, selected files, and `BatchProcessor`, and assembles the four tabs.
- `ui/input_panel.py` selects, filters, and previews inputs.
- `ui/workflow_panel.py` builds ordered workflow steps from the registry and edits schema-backed configuration.
- `ui/run_panel.py` validates run settings, starts batch work on a background thread, and marshals progress/completion callbacks to Tk with `after`.
- `ui/logs_panel.py` presents `ProcessingStats`, exports reports, and opens outputs.
- `core/contracts.py` defines the typed `OperationResult` boundary.
- `core/security.py` sanitizes names, contains paths, neutralizes spreadsheet formulas, and allocates unique destinations.
- `core/workflow.py` defines workflow/step persistence and built-in templates.
- `core/processor.py` validates, compiles, schedules, executes, cleans intermediate outputs, records statistics, and renders reports.
- `core/operations/registry.py` is the operation catalog and extension classifier.
- `core/operations/ocr_ops.py` owns OCR-specific legacy-key validation and independent image/native-PDF/PDF-OCR readiness. The registry exposes these reasons to the workflow UI; compiler and runtime use the same readiness functions. Executable/language/rasterizer state is refreshed, not cached at import. Batch delegates checks by concrete input; auto PDF checks OCR fallback only when needed. The generic operation validator remains compatible with unrelated unknown keys.
- `core/operations/base.py` defines per-file and aggregate interfaces.
- `core/operations/image_ops.py`, `pdf_ops.py`, `data_ops.py`, `file_ops.py`, and `ocr_ops.py` implement registered behavior.

## Processing flow

```text
Tkinter UI
  -> Workflow and selected paths
  -> WorkflowCompilation with one execution mode and ordered enabled IDs
  -> Concrete input preflight against the compiled plan
  -> OperationRegistry resolves IDs to operation instances
  -> ThreadPoolExecutor runs one per-file chain for each input
     OR the processor runs one aggregate lifecycle
  -> OutputPathAllocator / resolved output-root boundary
  -> OperationResult values
  -> ProcessingStats
  -> Logs tab and optional HTML/CSV report
```

The UI owns user interaction; the core has no dependency on Tkinter. The workflow is serialized before worker submission, and each per-file worker reconstructs it and creates its own registry instances.

## Operation contract

`OperationResult` is a slotted dataclass with `success`, `message`, optional `output_path`, optional `error`, and `metadata`. Operations catch expected library/runtime errors and return failures through this contract. The processor converts unexpected future and aggregate lifecycle exceptions into failed result records. A successful per-file step must supply an output path.

`Operation` handles one current input and one planned output. Its public `execute` resolves the final destination through `resolve_output_path`, applies containment and the optional batch allocator, then calls the writer's `_execute` with the protected final name. Writers use the shared `exclusive_output` stream helper and do not transform that destination again. OCR batch delegates its already resolved TXT destination to the image/PDF operation. `AggregateOperation` has an explicit `begin` / `consume` / `finalize` lifecycle. Both expose accepted types, output type, configuration schema, shared validation, and `supports_dry_run`; per-file operations also expose optional capability checks. The processor rejects unsupported dry-run operations before per-file execution or aggregate initialization.

## Per-file execution

The compiler validates the enabled chain, then `BatchProcessor` uses `ThreadPoolExecutor`. The default core worker count is `min(8, os.cpu_count() or 4)`; the UI defaults to four and restricts selection to 1-16. Each input proceeds through every enabled non-aggregate step. Calling the per-file worker with an aggregate step fails explicitly; it never skips the declaration or reports the source as an output. Operation instances copy the flat configuration mapping, so worker rename counters never mutate the caller's workflow dictionary. Serialization remains unchanged; nested values are not modified.

A later successful step replaces the current input. After a successful chain, earlier exclusively created outputs are removed only if their recorded filesystem identities still match. Unrelated occupied destinations are never recorded as owned intermediates. A failed chain can retain prior owned intermediates; the exclusive-write helper attempts to remove its own partial output on a write failure.

Threads keep the Tk event loop responsive and suit file and library calls that release the GIL or wait on I/O. They do not guarantee parallel speedup for CPU-bound Python code. See [ADR-0001](adr/0001-threadpool-execution.md).

## Aggregate PDF merge

Compilation requires an aggregate to be the only enabled step (Contract A); disabled predecessors do not participate. A valid aggregate plan declares execution mode `aggregate`, the sole enabled ID, accepted input types, and `original_inputs` as its source. When the compiled aggregate ID is `pdf_merge`, the processor uses a dedicated batch lifecycle. For a valid compiled workflow, empty aggregate input returns one batch-level error with settled timing/running state before output-directory preparation or `begin`.

For nonempty input, core preflight validates every path and registry-classified type against the compiled aggregate input contract before output-directory preparation. A wrong or mixed type rejects the whole batch; it cannot produce a merge from only the compatible subset. Correctly typed but unreadable PDFs retain the V11-02 per-input failure policy. After preflight, the processor resolves and reserves one contained final PDF destination, calls `begin`, consumes the original selected inputs sequentially in their supplied order, and calls `finalize` once unless stopped. Finalization is the physical write boundary and creates the output exclusively. Consumption records increment `processed_files` and receive the common `output` only after successful finalization. Empty input, stop, and finalization failure advertise no completed output. Dry run records only `result.planned_output` after successful simulated finalization, with no writer or final PDF.

Unexpected lifecycle exceptions are contained at `begin`, each `consume`, and `finalize`. A begin failure prevents consumption and finalization; a consume exception is an input failure under the existing partial-invalid-input policy; a finalize exception advertises no completed output. Every path returns settled `ProcessingStats`.

Each independent batch creates a fresh aggregate instance, isolating its writer, input/page count, and destination across success, failure, and stop. See [ADR-0002](adr/0002-aggregate-operations.md).

## Pause and cancellation

Pause blocks new submissions and delays aggregate consumption. It does not suspend already-running work. Stop clears the running flag, cancels futures that have not started, and requests executor shutdown without waiting; Python cannot safely terminate an already-running operation or third-party library call. Results already recorded remain in `ProcessingStats`. Aggregate execution checks stop after pause handling and immediately before finalization; a stop observed before that call prevents output. Once finalization begins, cooperative cancellation does not promise hard interruption or atomic rollback.

## Tkinter threading rule

The Tk thread snapshots dry-run mode, naming pattern, worker count, report intent, output directory, selected files, and a copy of the workflow before starting the daemon background thread. The worker receives plain Python values and reads no Tk variable to determine execution identity. Completion receives the captured report intent and output directory. Progress and completion callbacks use `frame.after(0, ...)` before touching widgets. New UI code must preserve the rule that widget mutation occurs on the Tk main thread.

Workflow OCR readiness probes use daemon workers with plain configuration snapshots and result queues. Only Tk schedules polling and mutates labels/list rows; slow external probes do not block the event loop. Refresh tokens prevent stale responses from overwriting newer status, and destroyed widgets are ignored.

## Output allocation and containment

The processor resolves the output root. `_render_name` and operation-specific naming pass through `sanitize_filename`; `resolve_safe_output` validates final suffix/name containment. `OutputPathAllocator` uses a lock, canonical path reservations, and naming counters to select unique destinations across worker threads and aliases. `exclusive_output` closes the reservation-to-creation race by failing if the final entry is occupied. Direct `process_single_file` calls create a local allocator when none is supplied, keeping same-suffix intermediates distinct, and use the same exclusive writers. Normal directory validation uses an exclusively owned temporary probe. Dry-run validation only resolves the path and inspects its nearest existing parent; it does not create a directory or physically verify future write permission. See [Security model](SECURITY_MODEL.md) and [ADR-0003](adr/0003-safe-output-boundary.md) for boundaries and limitations.

## Reporting

`ProcessingStats` records total, processed, failed, skipped, start/end times, successful result dictionaries, error dictionaries, a read-only `dry_run` property initialized from the batch invocation and included in `to_dict()`, and the successfully generated report paths for the current run. Automatic/manual report routes and the processor report entrypoint reject dry-run provenance independently of current UI state. HTML reports escape file names and messages. CSV reports neutralize leading formula characters. Both writers create the caller-selected destination exclusively; an occupied or concurrently claimed report path returns `False` without changing the existing file. The HTML viewer opens only a path recorded as successfully generated for the current statistics, so a collision cannot present a stale report as current. Report generation returns a boolean and suppresses exceptions at its public boundary.

## Persistence

Workflows are UTF-8 JSON. User settings are JSON under `~/.batchstudio/settings.json`. These are local files and are not synchronized or executed as plugins.
