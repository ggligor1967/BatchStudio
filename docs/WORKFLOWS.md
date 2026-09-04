# Workflows

## Data model

`Workflow` contains a name, description, ordered `WorkflowStep` objects, creation/modification timestamps, and a metadata mapping. Each step contains an `operation_id`, configuration mapping, and `enabled` flag. Only enabled steps execute.

The model supports adding, removing, and moving steps. Workflow-level validation requires a nonblank name, at least one stored step, a nonblank string operation ID for every step, and dictionary configuration.

## Compilation

Before processing, `compile_workflow` examines enabled steps against `OperationRegistry`.

It rejects:

- no enabled steps;
- unknown operation IDs;
- configuration values whose types or choices do not match an operation schema;
- a missing capability reported by a per-file operation;
- incompatible type transitions between per-file operations;
- an aggregate operation that is not the final enabled step.

The compiler starts with type `any`. A per-file operation that returns a concrete `output_type` advances the current type; `same` preserves it. Aggregate configuration and position are checked, but aggregate input acceptance is enforced while inputs are consumed rather than by the compiler.

Only one aggregate operation is registered: `pdf_merge`. If it is present as the last enabled step, batch execution uses the aggregate path. Earlier per-file steps are not applied before the aggregate merge in that path; a workflow intended to merge PDFs should therefore use PDF merge as its effective operation.

## PDF merge lifecycle

The processor creates a `PDFAggregateMergeOperation`, resolves one contained `.pdf` destination, calls `begin`, then calls `consume` once for each input in selection order. Each readable PDF contributes all pages to one writer. `finalize` writes the output once. This explicit lifecycle has no hidden cross-run session state.

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
