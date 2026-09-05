# Installation

## Requirements

- Python 3.10 or newer.
- A desktop environment with Tk support.
- Platform-specific external programs only if OCR-backed operations are used.

The canonical package metadata is in `pyproject.toml`. Its required Python dependencies are Pillow, pandas, reportlab, openpyxl, and pypdf.

## Install a published wheel

Download `batchstudio-<version>-py3-none-any.whl` for the latest published version from the [releases page](https://github.com/ggligor1967/BatchStudio/releases), then install it in an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .\batchstudio-<version>-py3-none-any.whl
batchstudio-gui
```

Each release's notes record the canonical wheel and source-distribution filenames, byte sizes, and digests. Historical v1.0.0 identities remain in [v1.0.0 release verification](releases/v1.0.0-verification.md).

## Install from a source checkout

```powershell
git clone https://github.com/ggligor1967/BatchStudio.git
Set-Location BatchStudio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
batchstudio-gui
```

For development tools, install the `dev` extra:

```powershell
python -m pip install ".[dev]"
```

`requirements.txt` represents the source-development environment and additionally lists `pytesseract` and `pdf2image`. Those two packages do not by themselves provide the Tesseract executable, Poppler utilities, or OCR language packs. See [OCR](OCR.md).

## Entrypoints

An installed package exposes both `batchstudio` and `batchstudio-gui`; both call `main:main`. From a checkout, use `python main.py`.

## Verify installation

From a source checkout:

```powershell
python test_installation.py
pytest -q test_installation.py
```

The standalone script checks required imports, operation registration, workflow construction, settings, and main-module loading. It does not prove that a Tk window can be displayed on a headless system or that external OCR programs are installed.
