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
- `core/operations/base.py` defines per-file and aggregate interfaces.
- `core/operations/image_ops.py`, `pdf_ops.py`, `data_ops.py`, `file_ops.py`, and `ocr_ops.py` implement registered behavior.

## Processing flow

```text
Tkinter UI
  -> Workflow and selected paths
  -> BatchProcessor validation and workflow compilation
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

`OperationResult` is a slotted dataclass with `success`, `message`, optional `output_path`, optional `error`, and `metadata`. Operations catch expected library/runtime errors and return failures through this contract. The processor converts unexpected future exceptions into failed result records. A successful per-file step must supply an output path.

`Operation` handles one current input and one planned output. Its public `execute` resolves the final destination through `resolve_output_path`, applies containment and the optional batch allocator, then calls the writer's `_execute` with the protected final name. Writers use the shared `exclusive_output` stream helper and do not transform that destination again. OCR batch delegates its already resolved TXT destination to the image/PDF operation. `AggregateOperation` has an explicit `begin` / `consume` / `finalize` lifecycle. Both expose accepted types, output type, configuration schema and validation; per-file operations also expose dry-run support and optional capability checks.

## Per-file execution

The compiler validates the enabled chain, then `BatchProcessor` uses `ThreadPoolExecutor`. The default core worker count is `min(8, os.cpu_count() or 4)`; the UI defaults to four and restricts selection to 1-16. Each input proceeds through every enabled non-aggregate step. Operation instances copy the flat configuration mapping, so worker rename counters never mutate the caller's workflow dictionary. Serialization remains unchanged; nested values are not modified.

A later successful step replaces the current input. After a successful chain, earlier exclusively created outputs are removed only if their recorded filesystem identities still match. Unrelated occupied destinations are never recorded as owned intermediates. A failed chain can retain prior owned intermediates; the exclusive-write helper attempts to remove its own partial output on a write failure.

Threads keep the Tk event loop responsive and suit file and library calls that release the GIL or wait on I/O. They do not guarantee parallel speedup for CPU-bound Python code. See [ADR-0001](adr/0001-threadpool-execution.md).

## Aggregate PDF merge

When the compiled aggregate ID is `pdf_merge`, the processor takes the aggregate path rather than submitting per-file chains. It resolves and reserves one contained final PDF destination, calls `begin`, consumes selected inputs sequentially in their supplied order, and calls `finalize` once. Finalization creates the output exclusively. Consumption records receive the produced path only after successful finalization, so failure cannot advertise an occupied unrelated output. The operation holds a `PdfWriter` only for that instance and run. There is no global or cross-run merge session. Compilation, empty-input handling, and stop/finalize lifecycle behavior are unchanged. See [ADR-0002](adr/0002-aggregate-operations.md).

## Pause and cancellation

Pause blocks new submissions and delays aggregate consumption. It does not suspend already-running work. Stop clears the running flag, cancels futures that have not started, and requests executor shutdown without waiting; Python cannot safely terminate an already-running operation or third-party library call. Results already recorded remain in `ProcessingStats`.

## Tkinter threading rule

The run starts on a daemon background thread. Progress and completion callbacks use `frame.after(0, ...)` before touching widgets. New UI code must preserve the rule that widget mutation occurs on the Tk main thread.

## Output allocation and containment

The processor resolves the output root. `_render_name` and operation-specific naming pass through `sanitize_filename`; `resolve_safe_output` validates final suffix/name containment. `OutputPathAllocator` uses a lock, canonical path reservations, and naming counters to select unique destinations across worker threads and aliases. `exclusive_output` closes the reservation-to-creation race by failing if the final entry is occupied. Direct `process_single_file` calls without an allocator still use the same exclusive writers. Directory validation uses an exclusively owned temporary probe, including during dry-run validation. See [Security model](SECURITY_MODEL.md) and [ADR-0003](adr/0003-safe-output-boundary.md) for boundaries and limitations.

## Reporting

`ProcessingStats` records total, processed, failed, skipped, start/end times, successful result dictionaries, and error dictionaries. HTML reports escape file names and messages. CSV reports neutralize leading formula characters. Report generation returns a boolean and suppresses exceptions at its public boundary.

## Persistence

Workflows are UTF-8 JSON. User settings are JSON under `~/.batchstudio/settings.json`. These are local files and are not synchronized or executed as plugins.
