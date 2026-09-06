# OCR

OCR recognition is optional. Readiness is checked separately for image recognition, native PDF extraction, and rasterized PDF OCR. Runtime readiness describes prerequisites, not recognition accuracy. Real OCR is qualified only by the controlled V11-06 environment and fixtures below.

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

V11-05 verification uses deterministic mocked executables, languages, rasterization, and recognition. It establishes capability and contract behavior, not real recognition. Those fast mocked tests remain in ordinary CI.

V11-06 (issue #10) established a separate fail-closed real-OCR qualification path after being deferred at the 1.1.0 release boundary. A successful `real-ocr-qualification` job proves BatchStudio behavior only for the exact commit, runner, toolchain, language data, fixtures, and assertions verified by that job. It does not change OCR production behavior or retroactively make real OCR part of the published 1.1.0 release evidence.

### Controlled environment

The authoritative machine-readable contract is `qualification/real_ocr/contract.json`. The dedicated workflow uses Ubuntu 24.04 amd64, Python 3.12.11, `pytesseract==0.3.13`, `pdf2image==1.17.0`, Pillow 12.3.0, pypdf 6.17.0, and reportlab 4.4.3. Remaining Python qualification packages are exactly resolved in `qualification/real_ocr/requirements.txt`.

| Component | Controlled identity | Artifact SHA256 | Runtime location |
|---|---|---|---|
| Tesseract | Ubuntu `tesseract-ocr` `5.3.4-1build5` | `2dfac382d77215aee0c3de4a2a2205505d5f2195e72e79b54ad32154fc08da77` | `/usr/bin/tesseract` |
| Poppler | Ubuntu `poppler-utils` `24.02.0-1ubuntu9.9` | `fb936375b183a9d8ecb5b1fc5665a44110ca130c445946fb575c0b800b1dc0f4` | `/usr/bin/pdfinfo`, `/usr/bin/pdftoppm` |
| English data | official `tessdata_fast` tag 4.1.0, commit `65727574dfcd264acbb0c3e07860e4e9e9b22185` | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` | isolated directory selected by `TESSDATA_PREFIX` |

Tesseract and Poppler are acquired from exact [Ubuntu package artifacts](https://packages.ubuntu.com/noble/tesseract-ocr) and [Ubuntu Poppler package metadata](https://packages.ubuntu.com/noble-updates/poppler-utils). The language model and its Apache-2.0 provenance come from the official [Tesseract `tessdata_fast` 4.1.0 tag](https://github.com/tesseract-ocr/tessdata_fast/tree/4.1.0). Tesseract is Apache-2.0; Poppler licensing is recorded in the [upstream tagged COPYING file](https://gitlab.freedesktop.org/poppler/poppler/-/blob/poppler-24.02.0/COPYING). No external binary or traineddata file is stored in this repository.

### Controlled fixtures and assertions

All fixtures are synthetic and generated by `qualification/real_ocr/generate_fixtures.py` without host font discovery. The PNG uses Pillow's embedded font. The PDFs use reportlab's invariant output mode and PDF core Helvetica only for the native-text case.

| Fixture | SHA256 | Expected normalized text | Evidence role |
|---|---|---|---|
| `known_text.png` (1600 by 400) | `921405601cf234e16204ee5bb08492b5844ad0a66779a9e029aa4f1e7fda6c8a` | `BATCHSTUDIO OCR 7319` | Real image OCR |
| `scanned_text.pdf` (one image-only page) | `4aa016a90a43188d6213eb5dbeab6b4eb3f0f8d3d61d4e98647e47980023bbdd` | `SCANNED PDF OCR 4827` | Real Poppler rasterization plus Tesseract in forced and auto modes |
| `native_text.pdf` (one native-text page) | `bab971c93a289c7b4c090f0f62c943957b6640249fdac3c1670ed69c0fc5347a` | `NATIVE PDF TEXT 5631` | Native pypdf extraction without OCR; never counted as OCR evidence |

Assertions normalize CRLF/CR to LF, collapse whitespace runs, and trim outer whitespace. The resulting string must equal the complete expected string exactly. Case, punctuation, words, and numeric identifiers are not normalized or matched fuzzily. The scanned PDF must have an empty normalized pypdf text layer before its OCR result is accepted.

### Reproduction and failure policy

The authoritative command is the `real-ocr-qualification` job in `.github/workflows/real-ocr-qualification.yml`. On an Ubuntu 24.04 amd64 host already running Python 3.12.11, its local sequence is:

```bash
export QUALIFICATION_ARTIFACT_DIR="$RUNNER_TEMP/batchstudio-real-ocr"
export TESSDATA_PREFIX="$QUALIFICATION_ARTIFACT_DIR/tessdata"
python qualification/real_ocr/download_toolchain.py --destination "$QUALIFICATION_ARTIFACT_DIR"
sudo apt-get install --yes --no-install-recommends \
  "$QUALIFICATION_ARTIFACT_DIR/tesseract-ocr_5.3.4-1build5_amd64.deb" \
  "$QUALIFICATION_ARTIFACT_DIR/poppler-utils_24.02.0-1ubuntu9.9_amd64.deb"
python -m pip install -r qualification/real_ocr/requirements.txt
python qualification/real_ocr/verify_environment.py \
  --artifact-directory "$QUALIFICATION_ARTIFACT_DIR"
python qualification/real_ocr/generate_fixtures.py --check
python -m pytest -q qualification/real_ocr/test_real_ocr.py -ra
```

The verifier checks the checked-out SHA, OS, architecture, Python and wrapper versions, exact Ubuntu package versions and artifacts, executable paths and hashes, Poppler/Tesseract version output, isolated traineddata hash, and fixture hashes. Missing tools, wrong versions, missing data, or any hash mismatch exits nonzero; there is no skip, xfail, mock fallback, or PATH-based acceptance of an uncontrolled tool.

### Qualification limits

`REAL_OCR_QUALIFIED=YES` means only that the dedicated job passed for its exact commit in this pinned English environment. It is not certification for Windows, other Linux images, arbitrary dependency versions, other languages, arbitrary PDF/scanner quality, other OCR engines, handwriting, accuracy benchmarks, or all documents. Native PDF extraction remains a separate pypdf capability. See [Testing](TESTING.md#controlled-real-ocr-qualification) for test topology and evidence requirements.
