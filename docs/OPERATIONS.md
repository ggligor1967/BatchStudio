# Operations reference

`core/operations/registry.py` is authoritative. It registers nine per-file operations and one aggregate operation. Extension classification maps images to `image`, PDF to `pdf`, CSV to `csv`, Excel extensions to `spreadsheet`, and TXT/JSON/XML to `text`.

| Operation ID | Class | Accepted input | Output | Configuration | Mode | Dry-run behavior | Dependencies | Principal failure modes |
|---|---|---|---|---|---|---|---|---|
| `image_resize` | `ImageResizeOperation` | `image`: jpg, jpeg, png, gif, bmp, webp, tiff, tif | Image, input suffix | `width:int=800`, `height:int=600`, `maintain_aspect:bool=true`, `quality:int=95` | File | Returns planned path; does not open or write the image | Pillow | Unreadable image, unsupported encoder/mode, write error |
| `image_convert` | `ImageConvertOperation` | `image` | PNG, JPEG, WEBP, BMP, or TIFF | `format` choice, default `PNG` | File | Returns the path with target-format suffix; no write | Pillow | Unreadable image, unsupported conversion/encoder, write error |
| `image_filter` | `ImageFilterOperation` | `image` | Image, input suffix | `filter` choice; optional `brightness:float`, `contrast:float` | File | Returns planned path; no image write | Pillow | Unreadable image, invalid numeric value, unsupported save mode, write error |
| `pdf_watermark` | `PDFWatermarkOperation` | `pdf` | PDF | `text:str=CONFIDENTIAL` | File | Returns planned path; no PDF write | pypdf, reportlab | Invalid/encrypted PDF, page merge failure, write error |
| `csv_filter` | `CSVFilterOperation` | `csv` | CSV | `column:str` required/non-empty, `operator` in `==`, `!=`, `>`, `<`, `contains`; `value:str` | File | Reads and filters the CSV, returns counts, but does not write | pandas | Invalid column configuration, missing concrete column, CSV parse/encoding error, nonnumeric comparison value, write error |
| `file_rename` | `FileRenameOperation` | `any` registry-classified input | Same suffix | `pattern:str={original}_{counter}` | File | Returns sanitized target path; no copy | Standard library | Missing source, invalid counter, copy/permission error |
| `ocr_image` | `OCRImageOperation` | `image` | UTF-8 TXT | `language:str=eng` | File | Refreshes image readiness, then returns TXT path without extraction/write | Pillow, pytesseract, Tesseract executable, requested language data; no PDF tools | Legacy config, missing executable/package/language, unreadable image, OCR or write error |
| `ocr_pdf` | `OCRPDFOperation` | `pdf` | UTF-8 TXT | `mode` in `auto`, `native`, `ocr`; `language:str=eng`, `dpi:int=200` | File | Checks unconditional mode readiness; returns TXT path without extraction/write or fallback prediction | pypdf; OCR branch also pytesseract, Tesseract, requested language, pdf2image, Poppler | Legacy config, invalid/encrypted PDF, missing OCR tool, rasterization/OCR/language/write error |
| `ocr_batch` | `OCRBatchOperation` | Declared `any`; runtime delegates PDF or image | One UTF-8 TXT per input | `language:str=eng` | File | Delegates to concrete image/PDF dry run; no text output | Concrete branch dependencies; native PDF needs no OCR tools | Legacy config, non-image/non-PDF input, missing OCR tool, delegated extraction failure |
| `pdf_merge` | `PDFAggregateMergeOperation` | `pdf` | One PDF | `output_filename:str=merged_output.pdf` | Aggregate | Initializes no writer, validates/queues inputs, and reports `result.planned_output` without a completed output | pypdf | Invalid/encrypted PDF, no valid PDFs, not initialized, final write error |

## Image filter choices

The registered values are `BLUR`, `SHARPEN`, `SMOOTH`, `EDGE_ENHANCE`, `EMBOSS`, `CONTOUR`, and `GRAYSCALE`. Brightness and contrast are applied only when the keys are present in the operation configuration.

## CSV behavior

`column` is required and must be a non-empty string; absent, `None`, non-string, empty, and whitespace-only values fail configuration validation and workflow compilation. Direct execution validates configuration too. A configured column missing from the parsed CSV is an explicit runtime failure with no output, rather than an unapplied filter reported as success. A valid filter matching zero rows succeeds with `filtered_rows=0` and writes a header-only CSV during normal execution. Numeric `>` and `<` comparisons convert the configured value to `float`; data-column comparison rules are then pandas rules. `contains` uses string conversion and treats missing values as nonmatches.

## OCR behavior

`native` PDF mode uses pypdf without any OCR tools. `auto` switches to OCR when stripped native text is shorter than 50 characters. Compilation allows native extraction without OCR tooling; an actual auto fallback checks full PDF OCR readiness and fails explicitly if unavailable. Explicit `ocr` mode checks that stack at compilation and runtime. Image OCR never requires PDF tooling. Batch preflight follows the concrete input branch.

Image and batch expose only `language`. Image/PDF reject legacy `page_segmentation_mode`, `grayscale`, `threshold`, and `threshold_value`; batch also rejects `combine_output` and `combined_filename`. Compilation and direct execution reject these keys explicitly rather than silently ignoring them. Executable, language, and Poppler readiness refresh on each check. See [OCR](OCR.md) for the dependency matrix, configuration migration, displayed status, and dry-run behavior. Real OCR success remains unverified; controlled real-OCR qualification (V11-06, issue #10) is deferred and is not part of the 1.1.0 release scope.

## Aggregate workflow and termination

`pdf_merge` must be the only enabled workflow step. Disabled predecessors do not participate; enabled transformations and multiple aggregates are rejected. After workflow validation and compilation, an empty input list returns one controlled batch-level error before output preparation or `begin`, including during dry run.

Consumption preserves input and page order. `processed_files` counts successfully consumed inputs, not merged files. The common output path is reported only after `finalize` succeeds; a failed finalization or a stop before it leaves no completed output advertisement. The existing partial-invalid-input policy remains: readable inputs may still produce a merge while invalid inputs are reported separately.

`finalize` is the exclusive physical write boundary. Stop is checked after pause handling and immediately before finalization. Cancellation is cooperative; once finalization has begun, hard cancellation or atomic rollback is not promised. Each processor run creates fresh aggregate state.

## Result contract

Every operation lifecycle method returns `OperationResult`: `success`, `message`, optional `output_path`, optional `error`, and a metadata mapping. The processor treats a successful per-file operation without an output path as a failed contract.

## Final destinations and collisions

Conversion resolves the target-format suffix, rename resolves its pattern, and image/PDF/batch OCR resolves `.txt` before allocation. Rename's batch counter is local to the operation instance and leaves caller workflow/config dictionaries unchanged. Other per-file writers retain the planned suffix. PDF merge resolves `.pdf` before reservation.

Batch allocation selects distinct canonical final paths, including when separate input directories contain the same basename. Every registered writer uses exclusive creation through `core/security.py`; if another actor occupies the destination before creation, the operation fails without modifying that file. Direct operation calls fail explicitly on occupied targets. Direct `process_single_file` calls without a batch allocator are also protected. Successful paths identify actual outputs; failed aggregate finalization does not advertise a produced path.

After a successful multi-step chain, cleanup removes only recorded intermediate outputs whose filesystem identities still match. Normal directory validation creates and removes an exclusively owned temporary probe. Dry-run validation uses read-only path feasibility checks and creates no directory, probe, temporary file, operation output, or report. It does not physically verify future write permission. Both operation bases declare `supports_dry_run`; the processor rejects unsupported operations before invoking per-file execution or aggregate `begin`. OCR extraction semantics are unchanged. See [Security model](SECURITY_MODEL.md) and [output-ownership regressions](../tests/test_output_ownership.py).
