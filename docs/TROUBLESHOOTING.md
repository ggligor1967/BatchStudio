# Troubleshooting

## The application does not open

Run `python test_installation.py` from a source checkout to verify imports and entrypoint loading. Confirm Python is 3.10 or newer and that Tkinter is available in the active interpreter. A headless session cannot display the GUI.

## An input is rejected

The processor requires an existing regular file, an allow-listed extension, and a size no greater than 500 MiB. Selection support is broader than operation support: Excel and text/data files have no dedicated transformation in 1.0.0. Match the input to [Operations](OPERATIONS.md).

## Workflow compilation fails

- **Unknown operation**: the JSON references an ID not present in the registry.
- **Invalid config**: a value has the wrong basic type or is outside a declared choice list.
- **Type incompatibility**: the output type of one per-file step is not accepted by the next.
- **Aggregate operations must be last**: move PDF merge to the final enabled position.
- **Missing capability**: install and verify the external OCR stack or select PDF `native` mode.

## No output appears in dry run

That is expected. Dry run records planned paths but does not write operation results or the automatic report. The output directory may still be created and write-tested during validation.

## Output has an unexpected suffix or name

Image conversion selects a suffix from its target format. OCR selects `.txt`. Run naming and file-rename patterns substitute `{original}`, `{timestamp}`, and `{counter}`, then sanitize unsafe characters. Duplicate initial allocations add numeric suffixes.

## Pause or stop seems delayed

Pause and stop act between submissions and completed futures. They cannot interrupt an image/PDF/OCR library call already executing. Wait for the running call to return; do not terminate the process if output integrity matters.

## OCR is reported unavailable

Importing `pytesseract` alone is insufficient. Verify the Tesseract executable, requested language data, and, for rasterized PDFs, `pdf2image` plus Poppler. Restart BatchStudio after installing tools because capability detection happens at import. Follow [OCR](OCR.md).

## PDF merge reports no output

Use readable PDF inputs and place `pdf_merge` last. The operation writes only after at least one PDF is consumed and finalization succeeds. Encrypted or malformed PDFs can be rejected individually.

## Reports are missing

Automatic report generation is skipped in dry run and can be disabled in the Run tab. Report generation also requires a writable destination. The Logs tab can create an HTML report or export CSV from the current statistics.

## Getting support

Collect the exact operation ID, configuration, Python/OS versions, error text, and a minimal non-sensitive reproduction, then follow [SUPPORT.md](../SUPPORT.md).
