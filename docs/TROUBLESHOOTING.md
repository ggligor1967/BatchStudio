# Troubleshooting

## The application does not open

Run `python test_installation.py` from a source checkout to verify imports and entrypoint loading. Confirm Python is 3.10 or newer and that Tkinter is available in the active interpreter. A headless session cannot display the GUI.

## An input is rejected

The processor requires an existing regular file, an allow-listed extension, and a size no greater than 500 MiB. Selection support is broader than operation support: Excel and text/data files have no dedicated transformation in 1.0.1. Match the input to [Operations](OPERATIONS.md).

## Workflow compilation fails

- **Unknown operation**: the JSON references an ID not present in the registry.
- **Invalid config**: a value has the wrong basic type, is outside a declared choice list, or violates a required/non-empty constraint. CSV `column` must be a non-empty string; a column missing from the actual CSV fails at runtime.
- **Type incompatibility**: the output type of one per-file step is not accepted by the next.
- **Aggregate operations must be last**: move PDF merge to the final enabled position.
- **Missing capability**: install and verify the external OCR stack or select PDF `native` mode.

## No output appears in dry run

That is expected. Dry run creates no directory, probe, operation output, or automatic/manual report. Read-only path feasibility does not verify future write permission. A later step may fail if it needs an intermediate file that dry run does not create; see [Limitations](LIMITATIONS.md#dry-run-and-output-safety).

## Output has an unexpected suffix or name

Image conversion selects a suffix from its target format. OCR selects `.txt`. Run naming and file-rename patterns substitute `{original}`, `{timestamp}`, and `{counter}`, then sanitize unsafe characters. Duplicate initial allocations add numeric suffixes.

## Pause or stop seems delayed

Pause and stop act between submissions and completed futures. They cannot interrupt an image/PDF/OCR library call already executing. Wait for the running call to return; do not terminate the process if output integrity matters.

## OCR is reported unavailable

Importing `pytesseract` alone is insufficient. Verify the Tesseract executable, requested language data, and, for rasterized PDFs, `pdf2image` plus Poppler. Restart BatchStudio after installing tools because capability detection happens at import. Follow [OCR](OCR.md).

## PDF merge reports no output

Use readable PDF inputs and place `pdf_merge` last. The operation writes only after at least one PDF is consumed and finalization succeeds. Encrypted or malformed PDFs can be rejected individually.

## Reports are missing

Reports are unavailable for dry-run results, including manual CSV export and HTML viewing. Changing the checkbox afterward does not change the completed run. Normal automatic reports use the report option and output directory captured at start; the Logs tab can create HTML or CSV reports for normal-run statistics when the destination is writable.

## Getting support

Collect the exact operation ID, configuration, Python/OS versions, error text, and a minimal non-sensitive reproduction, then follow [SUPPORT.md](../SUPPORT.md).
