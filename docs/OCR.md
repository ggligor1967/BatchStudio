# OCR

OCR is optional. Availability is a stack of separate capabilities; importing one Python module is not sufficient.

## Capability layers

| Layer | Purpose | How BatchStudio observes it |
|---|---|---|
| `pytesseract` Python package | Python adapter for Tesseract | Import attempted when `core.operations.ocr_ops` loads |
| Tesseract executable | Performs image recognition | `pytesseract.get_tesseract_version()` must succeed at module load |
| Tesseract language packs | Supply recognition data such as `eng` | Used when extraction runs; not preflighted separately |
| `pdf2image` Python package | Calls Poppler to rasterize PDF pages | Import attempted when the OCR module loads |
| Poppler utilities | Perform PDF rasterization for `pdf2image` | Required at conversion time; executable readiness is not preflighted |
| pypdf | Extracts native PDF text | Required package dependency used in every PDF text path |

Because capability flags are computed when the module imports, installing or reconfiguring an executable while BatchStudio is running requires an application restart before detection is refreshed.

## Operation requirements

### Image OCR (`ocr_image`)

Requires Pillow, `pytesseract`, a discoverable Tesseract executable, and the requested language data. Workflow compilation fails closed when the executable check failed. Current extraction applies `language`; exposed page-segmentation and preprocessing options are not applied in 1.0.0.

### PDF text (`ocr_pdf`)

- `mode=native` uses pypdf text extraction and does not require Tesseract or `pdf2image`.
- `mode=ocr` rasterizes every page and runs Tesseract.
- `mode=auto` first extracts native text and switches to OCR when fewer than 50 non-whitespace characters are found.

Compilation requires Tesseract and `pdf2image` for `auto` and `ocr`. Poppler and language data can still fail later because their readiness is not separately probed.

### Batch OCR (`ocr_batch`)

This per-file operation delegates PDFs to `ocr_pdf` and other inputs to `ocr_image`. In practice, inputs must be valid PDFs or images even though the registry declares `any`. It creates one output per input; combined-output configuration is not implemented.

## Installation approach

1. Install `pytesseract` for image OCR and `pdf2image` for rasterized PDF OCR. The source `requirements.txt` lists both.
2. Install Tesseract through the operating system and ensure its executable is discoverable by the process.
3. Install every language pack referenced by a workflow's `language` value.
4. For PDF OCR, install Poppler and ensure `pdf2image` can find its utilities.
5. Restart BatchStudio and test with a non-sensitive sample whose expected text is known.

Platform package names and executable locations vary, so BatchStudio does not prescribe an unverified installer command.

## Failure behavior and verification status

Missing declared capabilities are returned as workflow compilation errors rather than silently skipped. Runtime parser, rasterizer, recognizer, language, or write failures become failed `OperationResult` values and appear in batch errors.

For the canonical v1.0.0 release:

- OCR failure path verified: **YES**
- OCR success path verified: **NO**
- OCR optional capability: **YES**

See [the release verification record](releases/v1.0.0-verification.md).
