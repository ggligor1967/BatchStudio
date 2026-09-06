# BatchStudio

BatchStudio is a Python/Tkinter desktop application for applying configured operations to groups of local files. It provides file selection and preview, ordered workflows, bounded thread-pool execution, progress controls, and HTML or CSV result reports.

## Supported operations

- Images: resize, convert, and filter.
- PDF: text watermark and aggregate merge.
- CSV: row filtering.
- Files: copy to a name produced from a naming pattern.
- OCR: image, PDF, and per-file batch text extraction when the required external tools are available.

The registry-backed operation details, accepted inputs, configuration, dependencies, and known failure modes are in [Operations](docs/OPERATIONS.md).

## User interface

The application has four tabs: **Input Files**, **Workflow**, **Run**, and **Logs**. Files are selected with file/folder dialogs. The source includes an optional `tkinterdnd2` input hook, but drag-and-drop is not a verified capability. Workflow steps are added, removed, and reordered with buttons; workflow-step drag-and-drop is not implemented.

## Installation

Python 3.10 or newer is required. From a source checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
batchstudio-gui
```

Alternatively, download the wheel for the latest published version from the [releases page](https://github.com/ggligor1967/BatchStudio/releases) and install it with `python -m pip install .\batchstudio-<version>-py3-none-any.whl`.

OCR is optional. Image OCR and OCR-backed PDF modes require the Python integration and a discoverable Tesseract executable. PDF rasterization also requires `pdf2image` and a working Poppler installation. See [OCR](docs/OCR.md) before enabling OCR steps.

## First workflow

1. Start `batchstudio-gui` or run `python main.py` from a source checkout.
2. In **Input Files**, add one or more supported images.
3. In **Workflow**, add **Resize Image** and set the dimensions.
4. In **Run**, choose an output directory and keep **Dry Run** enabled for a preview.
5. Run once, inspect the planned results, disable **Dry Run**, and run again to create the outputs.

See the [Quick start](QUICKSTART.md) for a reproducible example and the [User guide](docs/USER_GUIDE.md) for the complete UI flow.

## Limitations

- OCR availability depends on external executables and language data; release validation verifies the missing-capability path, not a real OCR success path.
- Pause and stop prevent further scheduling but cannot forcibly terminate an operation already running.
- Thread-based execution does not bypass Python's GIL for CPU-bound Python code.
- UI selection is limited to images, PDF, and CSV. Excel, TXT, JSON, and XML remain core-classified compatibility inputs but are not selectable in the UI.
- Text and structured-text inputs have no dedicated transformation; the generic file-copy rename operation remains available through the core compatibility path and for generated OCR TXT.
- Dry run suppresses operation outputs and reports, but output-directory validation can create a missing directory and a transient write-test file.
- No throughput or maximum-batch guarantee is made. See [Limitations](docs/LIMITATIONS.md).

## Documentation

- [Installation](docs/INSTALLATION.md)
- [User guide](docs/USER_GUIDE.md)
- [Operations](docs/OPERATIONS.md)
- [Workflows](docs/WORKFLOWS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Development and testing](docs/DEVELOPMENT.md)
- [Release evidence](docs/releases/v1.0.0-verification.md)

## License

BatchStudio is distributed under the [MIT License](LICENSE).
