# Workflows

## Data model

`Workflow` contains a name, description, ordered `WorkflowStep` objects, creation/modification timestamps, and a metadata mapping. Each step contains an `operation_id`, configuration mapping, and `enabled` flag. Only enabled steps execute.

The model supports adding, removing, and moving steps. Workflow-level validation requires a nonblank name, at least one stored step, a nonblank string operation ID for every step, and dictionary configuration.

## Compilation

Before processing, `compile_workflow` examines enabled steps against `OperationRegistry`.

It rejects:

- no enabled steps;
- unknown operation IDs;
- configuration values whose types or choices do not match an operation schema, booleans supplied for numeric fields, missing required keys, or strings violating a declared non-empty constraint;
- a missing capability reported by a per-file operation;
- incompatible type transitions between per-file operations;
- an aggregate operation alongside any other enabled step, including another aggregate;
- an aggregate operation that is not the final enabled step.

CSV filters require a non-empty string `column`, including for direct execution. Compilation rejects missing, empty, whitespace-only, and non-string columns. Whether that column exists in a concrete CSV is checked only after parsing at execution; absence fails without output. A valid zero-match result succeeds. See [CSV behavior](OPERATIONS.md#csv-behavior).

The compiler starts with type `any`. A per-file operation that returns a concrete `output_type` advances the current type; `same` preserves it. Aggregate configuration and position are checked, but aggregate input acceptance is enforced while inputs are consumed rather than by the compiler.

Only one aggregate operation is registered: `pdf_merge`. Contract A requires it to be the **only enabled step**. Disabled predecessors or successors do not participate in compilation or execution. Enabled per-file predecessors are rejected with an instruction to disable or remove the other steps; transformed intermediates are not composed into aggregate execution.

## PDF merge lifecycle

After workflow validation and compilation, an empty aggregate batch records one batch-level `No input files` error before output-directory preparation, path allocation, or `begin`; timing and running state settle normally. This also applies to aggregate dry run.

For nonempty input, the processor creates a fresh `PDFAggregateMergeOperation`, resolves and reserves one contained `.pdf` destination, calls `begin`, then calls `consume` in selection order. Each readable PDF contributes all pages in their original order to one writer. Invalid inputs are recorded as failures; readable inputs can still be merged.

`finalize` is the physical write boundary and creates the output exclusively. Successfully consumed inputs count as processed, but their common output path is published only after successful finalization. Stop or finalize failure leaves those consumption records without a completed output. Dry run creates no writer or final PDF and records the destination under `result.planned_output`, leaving `output` empty.

Pause delays consumption and finalization. Stop is checked after pause handling and immediately before `finalize`; a stop observed there prevents the final write. Cancellation is cooperative: once finalization begins, hard cancellation and atomic rollback are not promised. Each independent run uses a fresh aggregate instance.

## Dry-run execution identity

Run options are captured on the Tk thread before worker startup. `ProcessingStats.dry_run` records that invocation and is read-only through its public property; `to_dict()` includes it. Later checkbox changes cannot alter the run or its report eligibility. Unsupported dry-run operations are rejected before execution. All dry-run execution and report paths follow the [write-free boundary](SECURITY_MODEL.md#dry-run-output-suppression).

## JSON persistence

`Workflow.to_dict()` and `Workflow.from_dict()` define the serialized shape:

```json
{
  "name": "Resize images",
  "description": "Create bounded copies",
  "steps": [
    {
      "operation_id": "image_resize",
      "config": {
        "width": 800,
        "height": 600,
        "maintain_aspect": true,
        "quality": 95
      },
      "enabled": true
    }
  ],
  "created_at": "ISO-8601 timestamp",
  "modified_at": "ISO-8601 timestamp",
  "metadata": {}
}
```

Saving uses UTF-8 JSON with indentation. Loading malformed JSON or an incompatible shape returns no workflow and prints an error. JSON is data, not a plugin or executable extension mechanism.

## Naming

The run naming pattern supports `{original}`, `{timestamp}`, and `{counter}`. The processor sanitizes the rendered stem and allocates a unique destination inside the resolved output root. `file_rename` applies the same tokens to its own `pattern`; despite its display name, it copies the current file to the destination and leaves the source intact.

## Templates

The UI exposes built-in JSON-equivalent presets for image, PDF watermark, CSV, rename, and OCR workflows. Templates are starting configurations. Their descriptive names do not establish file-size, quality, visual, compatibility, or OCR-accuracy guarantees.
