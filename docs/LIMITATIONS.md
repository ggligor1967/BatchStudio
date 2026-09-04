# Limitations

This document records observed boundaries of the current 1.0.0 implementation. It is not a future-feature promise.

## OCR

- OCR-backed paths require a working external Tesseract executable in addition to Python packages.
- PDF rasterization requires `pdf2image` and Poppler utilities.
- Requested Tesseract language packs must be installed separately.
- The release machine verified dependency-absence behavior, not a real OCR success path.
- Image OCR exposes page segmentation, grayscale, and threshold configuration but currently applies only `language`.
- Batch OCR exposes combined-output fields but currently writes one text result per input.

## Execution and cancellation

- `ThreadPoolExecutor` does not bypass the GIL for CPU-bound Python work.
- Pause prevents new scheduling; it does not suspend a running operation.
- Stop cannot hard-terminate work already inside Python or a third-party library.
- PDF merge consumes inputs sequentially and retains accumulated PDF pages in its writer until finalization.

## User interface

- The desktop UI is Tkinter-based and requires an interactive graphical session.
- Workflow ordering uses buttons; workflow-step drag-and-drop is not implemented.
- The optional input drag-and-drop hook was not verified as part of v1.0.0.
- The current `main.py` startup banner and `ui/workflow_panel.py` module description still use the inaccurate phrase "drag-and-drop workflow builder"; the actual workflow controls are the add/remove/move buttons described here.
- Dark styling is basic and can vary with the operating system/Tk theme.
- There is no command-line batch-processing interface; installed console and GUI entrypoints both launch the desktop application.
- The Preferences command displays an informational placeholder rather than an editable settings dialog.
- The hidden developer-console command is an informational dialog, not an interactive console.
- The About dialog and startup banner retain promotional wording that is not a scale guarantee; this documentation makes no corresponding performance claim.

## Formats and operations

- Excel files can be selected, but no registered operation transforms `.xlsx` or `.xls` content.
- TXT, JSON, and XML have no dedicated transformation.
- `file_rename` copies the file to a new name; it does not move or delete the source.
- CSV filtering silently leaves rows unchanged when the configured column is empty or absent.
- PDF watermark rendering uses a fixed letter-sized watermark canvas and fixed placement; page-specific layout is not calculated.
- A workflow containing PDF merge takes the aggregate path; preceding per-file transformations are not applied before the merge.

## Dry run and output safety

- Dry run creates no operation output or automatic report, but output validation can create a missing output directory and a transient `.write_test` file.
- Unique allocation applies to the initially planned name/suffix. A later operation-specific suffix or name change can still target an existing path.
- Intermediate outputs may be removed after a later workflow step succeeds; inputs are not deleted.

## Scale and coverage

- No maximum batch size, throughput, memory ceiling, or performance percentage is guaranteed.
- Individual inputs above 500 MiB are rejected, but total memory and decompressed document/image size are not bounded.
- On 2026-09-04 at the documentation baseline, `python -m coverage run --source=core,ui,main -m pytest -q` followed by `python -m coverage report --skip-covered` reported 31% production-code coverage across 2,470 statements. All 24 discovered tests passed, while UI modules were at 0% and `main` was not imported. This is a measurement of that exact command and environment, not a quality guarantee.

## Distribution metadata

The 1.0.0 package metadata retains legacy `github.com/batchstudio/batchstudio` project URLs. The canonical repository is `https://github.com/ggligor1967/BatchStudio`; correcting package metadata requires a later non-documentation release change.
