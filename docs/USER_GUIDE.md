# User guide

BatchStudio presents one window with four tabs. The ordinary path is to select inputs, assemble a workflow, configure a run, and inspect results.

## Input Files

Use **Add Files** for individual files or **Add Folder** for a recursive scan. The panel accepts image extensions (`jpg`, `jpeg`, `png`, `gif`, `bmp`, `webp`, `tiff`, `tif`), PDF, and CSV. Excel extensions and text/data extensions (`txt`, `json`, `xml`) remain classified by the core for compatibility but are not selectable through UI admission routes; consult [Operations](OPERATIONS.md).

Picker filters come from the V11-07 UI input policy and the current workflow's operation requirements. Without a workflow, all UI-selectable image, PDF, and CSV formats are offered: image editing and file rename do not require OCR. With a workflow, unavailable input types are omitted. Files selected through the dialog, folder scan, or drop hook are checked again before acceptance; unsupported inputs and missing prerequisites receive a specific refusal. Readiness checks run in a worker, and a changed workflow requires a fresh selection.

Native and auto PDF modes remain eligible when PDF OCR is unavailable. Auto mode does not predict whether a document will need fallback; the Workflow tab separately reports native PDF and PDF OCR fallback readiness. The backend checks fallback at execution. See [OCR](OCR.md#operation-requirements).

The panel can preview images, PDF metadata, CSV rows, and text. It caches at most 50 image previews. File and folder dialogs are the verified input path. The source contains an optional `tkinterdnd2` hook, but input drag-and-drop is not a verified release capability.

## Workflow

Select an available operation, add it, then use **Move Up**, **Move Down**, and **Remove** to manage order. Select a step to edit the fields derived from its configuration schema. Steps can be enabled or disabled.

Workflows can be saved to and loaded from JSON files. Built-in templates are editable presets, not guarantees about file size, appearance, OCR accuracy, or fitness for a particular service. Review their steps and configuration before running them.

Workflow steps are not reordered by drag-and-drop. Compilation checks registered IDs, configuration value types, choices, and required/non-empty constraints, file-operation type transitions, required capabilities, and the aggregate-last rule. See [Workflows](WORKFLOWS.md).

## Run

Choose an output directory, a naming pattern, a worker count from 1 to 16, dry-run mode, and report generation. Naming patterns recognize `{original}`, `{timestamp}`, and `{counter}`. Unsafe path characters and traversal fragments are sanitized, and duplicate initial allocations receive a numeric suffix. Operation-specific suffix or name changes have the collision limitation described in [Limitations](LIMITATIONS.md).

Use **Dry Run** first. It creates no output directory, probe, temporary file, operation output, or report. It checks path feasibility without physically verifying future write permission. Options are captured when the run starts; changing the checkbox afterward cannot change that run's identity. Dry run may read/parse inputs, and unsupported dry-run operations are rejected before execution. See the precise [application-write boundary](SECURITY_MODEL.md#dry-run-output-suppression) and [multi-step limitation](LIMITATIONS.md#dry-run-and-output-safety).

**Start Processing** first checks input eligibility and compiles the workflow in a worker. Start, Pause, and Stop remain disabled during this check. A refusal shows the backend reason before batch processing or output preparation; successful checks enable the processing controls. This recheck also covers inputs selected before a workflow or a runtime prerequisite changed.

**Pause** stops new work from being scheduled; it does not suspend a task already executing. **Stop** cancels work that has not started and prevents new submissions; a running library call cannot be forcibly terminated.

## Logs

The Logs tab displays successful items, failures, and a summary. For normal-run results it can export a CSV report or create/open an HTML report. Reports are unavailable for dry-run results, even after unchecking Dry Run; an older HTML report is not opened as their report. Report generation escapes HTML fields and neutralizes leading spreadsheet formula characters in CSV cells.

## Output behavior

Non-aggregate workflows process each valid input through the enabled step chain. Intermediate generated files are removed after a later step succeeds, leaving the final output. The file rename operation copies to a new name; it does not rename or delete the source.

PDF merge is different: all selected PDFs are consumed in selection order and one PDF is finalized. Invalid inputs are reported individually. An empty successful input set cannot produce a merge.

## Settings

Settings are stored in `~/.batchstudio/settings.json`. The window remembers geometry and selected preferences. A basic dark-theme toggle exists, but operating-system and Tk theme differences limit visual consistency.
