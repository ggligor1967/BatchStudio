# Operations reference

`core/operations/registry.py` is authoritative for operation registration and extension classification. It registers nine per-file operations and one aggregate operation. Classification maps images to `image`, PDF to `pdf`, CSV to `csv`, Excel extensions to `spreadsheet`, and TXT/JSON/XML to `text`.

The UI admission policy is intentionally narrower than core classification: only images, PDF, and CSV are selectable through picker, folder, and drop routes. XLS, XLSX, TXT, JSON, and XML retain only generic core compatibility and are not initial UI inputs. OCR-generated TXT is an output of image/PDF OCR, not evidence of TXT input processing.

## Capability levels and V12-03 decisions

Capability claims use these levels:

- **Level 0 — Known extension:** the core classifies the suffix.
- **Level 1 — Generic file compatibility:** format-agnostic, file-safe operations can handle opaque bytes without understanding the format.
- **Level 2 — Product-admitted input:** picker, folder, drop, and Run preflight intentionally admit the format into normal UI workflows.
- **Level 3 — Format-specific capability:** a registered operation understands and meaningfully processes the format.
- **Level 4 — Qualified capability:** fixtures, tests, failure policy, and documentation cover the format-aware operation.

Levels are cumulative for initial product inputs. Classification or an installed parser dependency alone does not establish a higher level. Generic rename preserves file bytes and suffix but makes no workbook, sheet, cell, column, encoding, schema, namespace, validation, transformation, or round-trip-fidelity guarantee.

| Format | Core classification | Current level | Target level | Product admission | Format-aware input operation | V12-03 decision |
|---|---|---:|---:|---|---|---|
| `.xls` | `spreadsheet` | 1 | 1 | No | None | `RESTRICT_TO_GENERIC_COMPATIBILITY` |
| `.xlsx` | `spreadsheet` | 1 | 1 | No | None | `RESTRICT_TO_GENERIC_COMPATIBILITY` |
| `.txt` | `text` | 1 | 1 | No | None | `RESTRICT_TO_GENERIC_COMPATIBILITY` |
| `.json` | `text` | 1 | 1 | No | None | `RESTRICT_TO_GENERIC_COMPATIBILITY` |
| `.xml` | `text` | 1 | 1 | No | None | `RESTRICT_TO_GENERIC_COMPATIBILITY` |

These decisions preserve classification, core validation, and the programmatic `file_rename` copy path while keeping picker, folder, drop, Run preflight, and format-specific templates closed. No repository evidence selects future real support, so V12-03 creates no follow-up format implementation unit. Any future support proposal must remain unadvertised until a separately approved unit defines useful operations, dependencies, synthetic fixtures, malformed-input behavior, security limits, fidelity guarantees, UI routes, and qualification gates.

Workflow and settings files use JSON as a control-plane persistence format. They are not user data inputs and do not make JSON a Level 2 or Level 3 capability. Likewise, qualified OCR may produce UTF-8 TXT, but BatchStudio does not parse or transform a TXT input.

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

## PDF watermark geometry contract

`pdf_watermark` uses the page `CropBox` as its effective visible box; pypdf supplies the
`MediaBox` when no explicit `CropBox` exists. Box coordinates are interpreted in PDF default
user-space units. A supported page has finite box coordinates, positive crop width and height,
and a `/Rotate` value equivalent modulo 360 to `0`, `90`, `180`, or `270` degrees. Invalid
geometry fails the operation before the exclusively owned destination is created.

Placement is calculated independently for every page in a rotated visible coordinate system.
Its origin `(0, 0)` is the lower-left of the displayed CropBox. For rotations `0` and `180`,
the visible width and height are the CropBox width and height; for `90` and `270`, they are
swapped. The overlay-to-page matrices below map visible coordinates `(u, v)` back into default
page coordinates. Here `L`, `B`, `W`, and `H` are the CropBox left, bottom, width, and height.

| `/Rotate` | Overlay-to-page matrix `(a, b, c, d, e, f)` |
|---:|---|
| `0` | `(1, 0, 0, 1, L, B)` |
| `90` | `(0, 1, -1, 0, L + W, B)` |
| `180` | `(-1, 0, 0, -1, L + W, B + H)` |
| `270` | `(0, -1, 1, 0, L, B + H)` |

The only existing anchor is center. The rendered Helvetica glyph-metric box is centered at
`(visible_width / 2, visible_height / 2)`, then rotated 45 degrees counter-clockwise in visible
coordinates. There is no configurable or implicit margin. Text, Helvetica, 50% gray, and 30%
opacity retain their existing semantics. Font size is at most 60 points and is never enlarged;
it is reduced uniformly only when necessary to keep the rotated glyph-metric bounding box
inside the full effective visible box. Empty text retains the configuration contract and has no
visible bounding region.

The source MediaBox, CropBox, `/Rotate`, page count, and existing content remain unchanged.
Only the watermark content is merged, with no page expansion. Geometric regressions use
synthetic, byte-deterministic PDFs and structural assertions with a `0.0001` point tolerance;
raster or screenshot comparison is not part of the contract.

The fixture generator is `tests/pdf_watermark_fixtures.py`. Hashes cover the exact generated
PDF bytes, not a library-normalized representation.

| Fixture | Pages | SHA256 |
|---|---:|---|
| F1 A4 portrait | 1 | `703639ed602f3002e240d37802a628abf12c16461128cc81f0f08510edef5069` |
| F2 A4 landscape | 1 | `83654eb49db99371a80a1cb34e6e6eb1ce3013595d1c74dccc8290bacdcd32af` |
| F3 US Letter portrait | 1 | `cb581373f39056ffa85cb7772c736217cca152a4466b1614a3b2fcaa208ac203` |
| F4 small non-standard | 1 | `a295250fe7aa0e36ef6e3c9d952282bd48300bbd44b8244e992613d9961280ed` |
| F5 large non-standard | 1 | `9fcb470c3bcc2df4ae74c98cabcc66067e1b6d67111f86af90e197b544a7e129` |
| F6 mixed-size | 3 | `1189fff829d804c51b418d1afaab4b20617d36ae3ab84eeb15cc3e0399bb8dff` |
| F7 rotated 90 | 1 | `f527a6b802df328590618a703283719a56bb0646f83dd6697acfff56819e60d6` |
| F8 rotated 180 | 1 | `a96fac93012ad3b862c7719832582b15c376f9af7820b810ceaa295acc4d0eca` |
| F9 rotated 270 | 1 | `fc7d79be67052959e6c61b33322c81a4c97b8c80cc2c26bd770e180d0cc0edc2` |
| F10 non-default CropBox | 1 | `1b1561a66083252d1ffa6c8ce4bfa08f0ab3d4be4a021752d8dbbf8fc89de793` |
| F11 mixed size and rotation | 3 | `b2c628aed0b420ad24002e1f34076fd7c1090df872a22ed399e2e42e17ff64f5` |

Expected placement uses the lower-left `(x, y)` and dimensions of the rotated glyph-metric
bounding box in visible coordinates. All rows use center anchor and `0.0001` point tolerance.

| Page | Effective CropBox | `/Rotate` | Visible size | Expected `(x, y, width, height)` | Font size |
|---|---|---:|---|---|---:|
| F1-P1 | `[0, 0, 595.275591, 841.889764]` | 0 | `595.275591 x 841.889764` | `(122.437948, 245.745035, 350.399694, 350.399694)` | 60 |
| F2-P1 | `[0, 0, 841.889764, 595.275591]` | 0 | `841.889764 x 595.275591` | `(245.745035, 122.437948, 350.399694, 350.399694)` | 60 |
| F3-P1 | `[0, 0, 612, 792]` | 0 | `612 x 792` | `(130.800153, 220.800153, 350.399694, 350.399694)` | 60 |
| F4-P1 | `[0, 0, 240, 320]` | 0 | `240 x 320` | `(0, 40, 240, 240)` | 41.095926 |
| F5-P1 | `[0, 0, 1200, 1800]` | 0 | `1200 x 1800` | `(424.800153, 724.800153, 350.399694, 350.399694)` | 60 |
| F6-P1 | `[0, 0, 595.275591, 841.889764]` | 0 | `595.275591 x 841.889764` | `(122.437948, 245.745035, 350.399694, 350.399694)` | 60 |
| F6-P2 | `[0, 0, 500, 500]` | 0 | `500 x 500` | `(74.800153, 74.800153, 350.399694, 350.399694)` | 60 |
| F6-P3 | `[0, 0, 841.889764, 595.275591]` | 0 | `841.889764 x 595.275591` | `(245.745035, 122.437948, 350.399694, 350.399694)` | 60 |
| F7-P1 | `[0, 0, 612, 792]` | 90 | `792 x 612` | `(220.800153, 130.800153, 350.399694, 350.399694)` | 60 |
| F8-P1 | `[0, 0, 612, 792]` | 180 | `612 x 792` | `(130.800153, 220.800153, 350.399694, 350.399694)` | 60 |
| F9-P1 | `[0, 0, 612, 792]` | 270 | `792 x 612` | `(220.800153, 130.800153, 350.399694, 350.399694)` | 60 |
| F10-P1 | `[36, 72, 576, 720]` | 0 | `540 x 648` | `(94.800153, 148.800153, 350.399694, 350.399694)` | 60 |
| F11-P1 | `[0, 0, 240, 320]` | 90 | `320 x 240` | `(40, 0, 240, 240)` | 41.095926 |
| F11-P2 | `[0, 0, 595.275591, 841.889764]` | 270 | `841.889764 x 595.275591` | `(245.745035, 122.437948, 350.399694, 350.399694)` | 60 |
| F11-P3 | `[100, 150, 1100, 1650]` | 180 | `1000 x 1500` | `(324.800153, 574.800153, 350.399694, 350.399694)` | 60 |

## Image filter choices

The registered values are `BLUR`, `SHARPEN`, `SMOOTH`, `EDGE_ENHANCE`, `EMBOSS`, `CONTOUR`, and `GRAYSCALE`. Brightness and contrast are applied only when the keys are present in the operation configuration.

## CSV behavior

`column` is required and must be a non-empty string; absent, `None`, non-string, empty, and whitespace-only values fail configuration validation and workflow compilation. Direct execution validates configuration too. A configured column missing from the parsed CSV is an explicit runtime failure with no output, rather than an unapplied filter reported as success. A valid filter matching zero rows succeeds with `filtered_rows=0` and writes a header-only CSV during normal execution. Numeric `>` and `<` comparisons convert the configured value to `float`; data-column comparison rules are then pandas rules. `contains` uses string conversion and treats missing values as nonmatches.

## OCR behavior

`native` PDF mode uses pypdf without any OCR tools. `auto` switches to OCR when stripped native text is shorter than 50 characters. Compilation allows native extraction without OCR tooling; an actual auto fallback checks full PDF OCR readiness and fails explicitly if unavailable. Explicit `ocr` mode checks that stack at compilation and runtime. Image OCR never requires PDF tooling. Batch preflight follows the concrete input branch.

Image and batch expose only `language`. Image/PDF reject legacy `page_segmentation_mode`, `grayscale`, `threshold`, and `threshold_value`; batch also rejects `combine_output` and `combined_filename`. Compilation and direct execution reject these keys explicitly rather than silently ignoring them. Executable, language, and Poppler readiness refresh on each check. See [OCR](OCR.md) for the dependency matrix, configuration migration, displayed status, dry-run behavior, and V11-06 controlled real-OCR qualification. That qualification is limited to its exact successful CI SHA and pinned English environment; it is separate from the published 1.1.0 release evidence.

## Aggregate workflow and termination

`pdf_merge` must be the only enabled workflow step. Disabled predecessors do not participate; enabled transformations and multiple aggregates are rejected. Its valid compiled plan declares aggregate execution, the sole enabled operation, original batch inputs as the source, and accepted type `pdf`. After workflow validation and compilation, an empty input list returns one controlled batch-level error before output preparation or `begin`, including during dry run. A nonempty wrong-type or mixed-type batch is rejected in full before output preparation or `begin`; there is no implicit conversion or compatible-subset fallback.

Consumption receives the original input paths and preserves input and page order. `processed_files` counts successfully consumed inputs, not merged files. The common output path is reported only after `finalize` succeeds; a failed finalization or a stop before it leaves no completed output advertisement. The existing partial-invalid-input policy remains only for correctly typed PDFs: readable inputs may still produce a merge while unreadable PDFs are reported separately. Unexpected lifecycle exceptions are recorded as begin, input-consume, or finalize failures and return settled statistics.

`finalize` is the exclusive physical write boundary. Stop is checked after pause handling and immediately before finalization. Cancellation is cooperative; once finalization has begun, hard cancellation or atomic rollback is not promised. Each processor run creates fresh aggregate state.

## Result contract

Every operation lifecycle method returns `OperationResult`: `success`, `message`, optional `output_path`, optional `error`, and a metadata mapping. The processor treats a successful per-file operation without an output path as a failed contract.

## Final destinations and collisions

Conversion resolves the target-format suffix, rename resolves its pattern, and image/PDF/batch OCR resolves `.txt` before allocation. Rename's batch counter is local to the operation instance and leaves caller workflow/config dictionaries unchanged. Other per-file writers retain the planned suffix. PDF merge resolves `.pdf` before reservation.

Batch allocation selects distinct canonical final paths, including when separate input directories contain the same basename. Every registered writer uses exclusive creation through `core/security.py`; if another actor occupies the destination before creation, the operation fails without modifying that file. Direct operation calls fail explicitly on occupied targets. Direct `process_single_file` calls without a batch allocator are also protected. Successful paths identify actual outputs; failed aggregate finalization does not advertise a produced path.

Normal HTML and CSV processing reports use the same exclusive-creation boundary. Report generation returns `False` when the caller-selected path already exists or another writer claims it first; it never selects a different name because the report API returns only success/failure and could not truthfully report an alternate path. Successful generation records the canonical report path on the current `ProcessingStats`; the HTML viewer opens only that current-run path and reports an unavailable destination instead of opening an unrelated pre-existing report.

After a successful multi-step chain, cleanup removes only recorded intermediate outputs whose filesystem identities still match. Normal directory validation creates and removes an exclusively owned temporary probe. Dry-run validation uses read-only path feasibility checks and creates no directory, probe, temporary file, operation output, or report. It does not physically verify future write permission. Both operation bases declare `supports_dry_run`; the processor rejects unsupported operations before invoking per-file execution or aggregate `begin`. OCR extraction semantics are unchanged. See [Security model](SECURITY_MODEL.md) and [output-ownership regressions](../tests/test_output_ownership.py).
