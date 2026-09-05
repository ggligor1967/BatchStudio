# Limitations

This document records observed boundaries of the current 1.0.1 implementation plus unreleased output-ownership and aggregate-contract fixes in source. It is not a future-feature promise or a restatement of the immutable release tag.

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
- Aggregate stop is checked after pause handling and immediately before finalization. A stop observed there prevents output; once the physical final write begins, hard cancellation and atomic rollback are not promised.

## User interface

- The desktop UI is Tkinter-based and requires an interactive graphical session.
- Workflow ordering uses buttons; workflow-step drag-and-drop is not implemented.
- The optional input drag-and-drop hook is not a verified release capability.
- Dark styling is basic and can vary with the operating system/Tk theme.
- There is no command-line batch-processing interface; installed console and GUI entrypoints both launch the desktop application.
- The Preferences command displays an informational placeholder rather than an editable settings dialog.
- The hidden developer-console command is an informational dialog, not an interactive console.

## Formats and operations

- Excel files can be selected, but no registered operation transforms `.xlsx` or `.xls` content.
- TXT, JSON, and XML have no dedicated transformation.
- `file_rename` copies the file to a new name; it does not move or delete the source.
- CSV filtering silently leaves rows unchanged when the configured column is empty or absent.
- PDF watermark rendering uses a fixed letter-sized watermark canvas and fixed placement; page-specific layout is not calculated.
- PDF merge must be the only enabled step. Disabled predecessors do not participate; enabled transformations before a merge are rejected rather than composed into the aggregate.
- Empty aggregate input produces one controlled batch-level error before output preparation or `begin`. Successfully consumed inputs remain counted as processed on stop or finalization failure, but no completed common output is advertised.

## Dry run and output safety

- Dry run creates no operation output or automatic report, but output validation can create a missing output directory and an exclusively owned temporary probe. Strict write-free validation (V11-04) remains outstanding. Empty aggregate batches return before preparation; nonempty aggregate dry runs still use directory validation and record only a planned destination.
- Final names/suffixes are reserved before writing; occupied destinations cause alternate batch allocation or explicit exclusive-creation failure. Direct calls are protected too. This applies to registered processing operations, not report export or settings/workflow persistence.
- Intermediate outputs are removed after a successful chain only while their recorded filesystem identities match; inputs and unrelated occupied outputs are not deleted. A failed chain can leave prior owned intermediates.
- Output ownership is not a filesystem sandbox or a promise of atomic recovery from every OS error. Arbitrary hostile directory/link replacement and replacement during cleanup's identity-check/unlink interval are outside the guarantee.

## Scale and coverage

- No maximum batch size, throughput, memory ceiling, or performance percentage is guaranteed.
- Individual inputs above 500 MiB are rejected, but total memory and decompressed document/image size are not bounded.
- On 2026-09-04 at the documentation baseline, `python -m coverage run --source=core,ui,main -m pytest -q` followed by `python -m coverage report --skip-covered` reported 31% production-code coverage across 2,470 statements. All 24 discovered tests passed, while UI modules were at 0% and `main` was not imported. This is a measurement of that exact command and environment, not a quality guarantee.
