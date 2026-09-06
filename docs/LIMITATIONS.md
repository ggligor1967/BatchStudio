# Limitations

This document records observed boundaries of the current implementation, including the output-ownership, aggregate-contract, CSV-validation, dry-run, and OCR-truth fixes prepared for the 1.1.0 release candidate. It is not a future-feature promise or a restatement of the immutable release tag.

## OCR

- OCR-backed paths require a working external Tesseract executable in addition to Python packages.
- PDF rasterization requires `pdf2image` and Poppler utilities.
- Requested Tesseract language packs must be installed separately.
- V11-05 tests mock recognition and external tools; real OCR success remains unverified. Controlled real-OCR qualification (V11-06, issue #10) was not admitted to the 1.1.0 release scope and is deferred as future work in [Roadmap](ROADMAP.md).
- Image OCR exposes only `language` and does not implement preprocessing. Image/PDF reject legacy page segmentation, grayscale, threshold, and threshold-value keys explicitly at compilation and direct execution.
- Batch OCR exposes only `language` and writes one text result per input. Legacy combined-output fields and delegated preprocessing fields fail explicitly.
- Image readiness does not require PDF tooling. Native PDF extraction needs no OCR stack. Auto mode can complete natively without it, but fails explicitly when fallback is needed and unavailable.
- Executable, language, and Poppler checks refresh without reload; Python package availability remains an import-time fact. Readiness probes do not qualify recognition accuracy or guarantee a later conversion. See [OCR](OCR.md).
- Auto PDF dry run does not extract native text or predict fallback, so its success does not establish that PDF OCR is ready.

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

- Excel files remain core-classified compatibility inputs, but `.xlsx` and `.xls` are not selectable through UI admission routes and no registered operation transforms their content.
- TXT, JSON, and XML remain core-classified compatibility inputs for generic rename and generated OCR TXT, but they are not selectable through UI admission routes and have no dedicated transformation.
- `file_rename` copies the file to a new name; it does not move or delete the source.
- CSV filtering requires a non-empty string column configuration. A column missing from the concrete CSV is a runtime failure; a valid zero-row result is success. Numeric comparisons retain pandas behavior.
- PDF watermark rendering uses a fixed letter-sized watermark canvas and fixed placement; page-specific layout is not calculated.
- PDF merge must be the only enabled step. Disabled predecessors do not participate; enabled transformations before a merge are rejected rather than composed into the aggregate.
- For a valid compiled workflow, empty aggregate input produces one controlled batch-level error before output preparation or `begin`. Successfully consumed inputs remain counted as processed on stop or finalization failure, but no completed common output is advertised.

## Dry run and output safety

- Dry run performs no BatchStudio-controlled execution or report writes: no directory, probe, temporary file, operation output, or automatic/manual report, including with empty input. The run retains its dry-run identity independently of checkbox changes. Read-only feasibility does not prove future normal-run writability and is not a filesystem sandbox; OS-managed metadata and unrelated settings persistence are outside the guarantee. See [Security model](SECURITY_MODEL.md#dry-run-output-suppression).
- Dry run does not fabricate intermediate files. A multi-step chain can fail when a later validator requires a planned intermediate to exist. Unsupported dry-run operations are not invoked. Aggregate-only dry run validates inputs and records a planned destination without writing a PDF.
- Final names/suffixes are reserved before writing; occupied destinations cause alternate batch allocation or explicit exclusive-creation failure. Direct calls are protected too. This applies to registered processing operations, not report export or settings/workflow persistence.
- Intermediate outputs are removed after a successful chain only while their recorded filesystem identities match; inputs and unrelated occupied outputs are not deleted. A failed chain can leave prior owned intermediates.
- Output ownership is not a filesystem sandbox or a promise of atomic recovery from every OS error. Arbitrary hostile directory/link replacement and replacement during cleanup's identity-check/unlink interval are outside the guarantee.

## Scale and coverage

- No maximum batch size, throughput, memory ceiling, or performance percentage is guaranteed.
- Individual inputs above 500 MiB are rejected, but total memory and decompressed document/image size are not bounded.
- On 2026-09-04 at the documentation baseline, `python -m coverage run --source=core,ui,main -m pytest -q` followed by `python -m coverage report --skip-covered` reported 31% production-code coverage across 2,470 statements. All 24 discovered tests passed, while UI modules were at 0% and `main` was not imported. This is a measurement of that exact command and environment, not a quality guarantee.
