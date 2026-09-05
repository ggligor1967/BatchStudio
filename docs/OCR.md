# OCR

OCR recognition is optional. Readiness is checked separately for image recognition, native PDF extraction, and rasterized PDF OCR. These checks describe prerequisites, not recognition accuracy or real OCR qualification.

## Capability layers

| Layer | Purpose | How BatchStudio observes it |
|---|---|---|
| `pytesseract` Python package | Python adapter for Tesseract | Import attempted when `core.operations.ocr_ops` loads |
| Tesseract executable | Performs image recognition | Fresh `get_tesseract_version(cached=False)` at preflight and execution |
| Tesseract language data | Supplies recognition data such as `eng` or `ron` | Fresh `get_languages(cached=False)`; every requested language must be listed |
| `pdf2image` Python package | Calls Poppler to rasterize PDF pages | Import attempted when the OCR module loads |
| Poppler utilities | Inspect and rasterize PDFs | `pdfinfo` and `pdftoppm` resolved on PATH and probed with `-v`, each with a five-second timeout |
| pypdf | Extracts native PDF text | Required application dependency, independent of OCR imports |

Executable, language, and rasterizer changes are reflected on subsequent checks without reloading the module. Python package imports remain startup facts. Poppler probes use argument lists without a shell and do not convert documents. A successful probe cannot guarantee that a later document conversion will succeed.

## Operation requirements

### Image OCR (`ocr_image`)

Requires Pillow, `pytesseract`, a working Tesseract executable, and the requested language data. It does not require `pdf2image` or Poppler. `language` defaults to `eng`; values such as `eng+ron` require all named languages. Image parsing is validated separately so capability failures retain their specific reasons.

### PDF text (`ocr_pdf`)

- `mode=native` uses pypdf text extraction without `pytesseract`, Tesseract, OCR language data, `pdf2image`, or Poppler.
- `mode=ocr` requires the image OCR stack plus `pdf2image` and both Poppler utilities. It rasterizes and recognizes every page.
- `mode=auto` first extracts native text and falls back to OCR when `len(native_text.strip()) < 50`. This threshold and extraction sequence are unchanged. Compilation permits native extraction without the fallback stack. An actual fallback checks full PDF OCR readiness and returns an explicit failure if a prerequisite is missing, without publishing a text output.

The functional fields remain `mode` (default `auto`), `language` (default `eng`), and `dpi` (default 200). `language` and `dpi` are forwarded to recognition and rasterization respectively.

### Batch OCR (`ocr_batch`)

This per-file operation delegates PDFs to `ocr_pdf` and other inputs to `ocr_image`. Inputs must be valid PDFs or images even though the registry declares `any`. It creates one text output per input and exposes only `language`.

Compilation has no concrete input type and does not impose a global OCR gate. Concrete preflight and execution use the delegate's capability checks: image inputs require no PDF tools; PDFs default to `auto`. Existing configurations that pass PDF `mode`/`dpi` through to the PDF delegate retain that behavior; these optional keys are validated against the PDF schema at compilation and direct execution, but are not additional exposed batch controls. A native PDF branch needs no OCR stack. The batch wrapper validates, checks readiness, and resolves the destination once before calling the concrete writer; PDF OCR checks readiness again at the actual rasterization boundary.

## Configuration migration

Image and PDF OCR explicitly reject `page_segmentation_mode`, `grayscale`, `threshold`, and `threshold_value`. Batch OCR rejects these delegated preprocessing keys plus `combine_output` and `combined_filename`. Remove them from legacy workflow JSON; even false/default values fail with an actionable error such as `unsupported OCR configuration 'grayscale'`.

These checks run during compilation and direct execution, including dry run. They do not globally reject unknown keys in unrelated operations. No preprocessing or combined-output implementation was added. All four shipped OCR templates use supported configuration and make no preprocessing or optimization claim.

## Display and dry run

The workflow operation list shows readiness for default English configuration, with separate native PDF and PDF OCR fallback status. The step configuration panel shows current applied language/mode readiness or a legacy configuration error. **Refresh OCR availability** refreshes the displayed snapshot; applying configuration also refreshes the step status. Probes run in daemon workers using configuration snapshots; Tk polls their result queues and updates widgets. The UI shows `checking` while pending and discards stale refresh results. Unavailable operations remain configurable, and native PDF extraction is not hidden by absent OCR tools.

Dry run retains capability preflight for unconditional requirements: image OCR checks the image stack; explicit PDF `ocr` checks the PDF OCR stack; batch checks its concrete branch. Native and `auto` PDF dry runs require only native extraction capability. They do not extract text, rasterize, recognize, predict whether fallback will be needed, or create output. Thus a successful `auto` dry run does not qualify its fallback. Processor input parsing and read-only output feasibility checks still apply. See [the write-free boundary](SECURITY_MODEL.md#dry-run-output-suppression).

## External tools and verification status

External executables and requested language data must be provisioned separately by the operator. BatchStudio has no installation action. Only PDF OCR needs Poppler. After external executable or language changes, refresh readiness; restart after Python package changes.

Missing package, executable, requested language, `pdf2image`, and Poppler failures have distinct messages. An unreadable language list is reported as a failed language-data check. Runtime parser, rasterizer, recognizer, and write failures remain controlled `OperationResult` failures.

V11-05 verification uses deterministic mocked executables, languages, rasterization, and recognition. **Real OCR success is not verified; V11-06 qualification remains outstanding.** No binaries or language data were installed for this change. See [Testing](TESTING.md#ocr-tests) and the historical [v1.0.0 verification record](releases/v1.0.0-verification.md).
