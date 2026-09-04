# User guide

BatchStudio presents one window with four tabs. The ordinary path is to select inputs, assemble a workflow, configure a run, and inspect results.

## Input Files

Use **Add Files** for individual files or **Add Folder** for a recursive scan. The panel accepts image extensions (`jpg`, `jpeg`, `png`, `gif`, `bmp`, `webp`, `tiff`, `tif`), PDF, CSV, Excel extensions, and text/data extensions (`txt`, `json`, `xml`). Acceptance by the picker does not imply that a transformation exists for every type; consult [Operations](OPERATIONS.md).

The panel can preview images, PDF metadata, CSV rows, and text. It caches at most 50 image previews. File and folder dialogs are the verified input path. The source contains an optional `tkinterdnd2` hook, but input drag-and-drop is not a verified release capability.

## Workflow

Select an available operation, add it, then use **Move Up**, **Move Down**, and **Remove** to manage order. Select a step to edit the fields derived from its configuration schema. Steps can be enabled or disabled.

Workflows can be saved to and loaded from JSON files. Built-in templates are editable presets, not guarantees about file size, appearance, OCR accuracy, or fitness for a particular service. Review their steps and configuration before running them.

Workflow steps are not reordered by drag-and-drop. Compilation checks registered IDs, configuration value types and choices, file-operation type transitions, required capabilities, and the aggregate-last rule. See [Workflows](WORKFLOWS.md).

## Run

Choose an output directory, a naming pattern, a worker count from 1 to 16, dry-run mode, and report generation. Naming patterns recognize `{original}`, `{timestamp}`, and `{counter}`. Unsafe path characters and traversal fragments are sanitized, and duplicate initial allocations receive a numeric suffix. Operation-specific suffix or name changes have the collision limitation described in [Limitations](LIMITATIONS.md).

Use **Dry Run** first. It suppresses operation output files and the automatic report. Output-directory validation still resolves and checks the directory and can create a missing directory plus a transient `.write_test` probe.

**Pause** stops new work from being scheduled; it does not suspend a task already executing. **Stop** cancels work that has not started and prevents new submissions; a running library call cannot be forcibly terminated.

## Logs

The Logs tab displays successful items, failures, and a summary. It can export a CSV report or create/open an HTML report. Report generation escapes HTML fields and neutralizes leading spreadsheet formula characters in CSV cells.

## Output behavior

Non-aggregate workflows process each valid input through the enabled step chain. Intermediate generated files are removed after a later step succeeds, leaving the final output. The file rename operation copies to a new name; it does not rename or delete the source.

PDF merge is different: all selected PDFs are consumed in selection order and one PDF is finalized. Invalid inputs are reported individually. An empty successful input set cannot produce a merge.

## Settings

Settings are stored in `~/.batchstudio/settings.json`. The window remembers geometry and selected preferences. A basic dark-theme toggle exists, but operating-system and Tk theme differences limit visual consistency.
