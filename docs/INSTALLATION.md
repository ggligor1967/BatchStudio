# Installation

## Requirements

- Python 3.10 or newer.
- A desktop environment with Tk support.
- Platform-specific external programs only if OCR-backed operations are used.

The canonical package metadata is in `pyproject.toml`. Its required Python dependencies are Pillow, pandas, reportlab, openpyxl, and pypdf.

## Install the verified 1.0.0 wheel

Download `batchstudio-1.0.0-py3-none-any.whl` from the [v1.0.0 release](https://github.com/ggligor1967/BatchStudio/releases/tag/v1.0.0), then install it in an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .\batchstudio-1.0.0-py3-none-any.whl
batchstudio-gui
```

The verified filename, byte size, and digest are recorded in [v1.0.0 release verification](releases/v1.0.0-verification.md). Verify those values before installing a downloaded artifact.

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

## Known metadata issue

The 1.0.0 `pyproject.toml` contains legacy project URLs under `github.com/batchstudio/batchstudio`. The canonical public repository and release are under `github.com/ggligor1967/BatchStudio`. Packaging metadata was intentionally left unchanged by the documentation-only remediation.
