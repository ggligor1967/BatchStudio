# Testing

## Test topology

`pyproject.toml` sets `testpaths = ["tests"]`, so normal discovery runs the four modules under `tests/`. At the documentation baseline, they contain 24 tests:

- `tests/test_operations.py`: result contract, resize output, and aggregate registration.
- `tests/test_processor.py`: path validation, operation chains, dry run, duplicate allocation, traversal-shaped naming, and report encoding.
- `tests/test_workflow.py`: workflow and compiler rejection cases.
- `tests/test_e2e_release_blockers.py`: resize/convert chains, PDF merge and containment, dry run, malformed configuration, OCR dependency absence, pause, and cancellation.

Run the discovered suite:

```powershell
pytest -q
```

Run the critical end-to-end suite independently:

```powershell
pytest -q tests/test_e2e_release_blockers.py
```

## Root checks

`test_installation.py` is both an importable pytest module and a standalone console check. Because it is outside configured `testpaths`, invoke it explicitly:

```powershell
pytest -q test_installation.py
python test_installation.py
```

The root PDF merge scripts create temporary PDFs and print processed/error, existence, and page-count evidence:

```powershell
python test_pdf_merge_fix.py
python test_pdf_merge_simple.py
```

These two scripts contain no assertions; their output values must be inspected in addition to the exit code. Asserted PDF merge behavior lives in the critical end-to-end suite.

## Syntax compilation

The release-critical compilation command is:

```powershell
python -m compileall core ui tests main.py test_installation.py test_pdf_merge_fix.py test_pdf_merge_simple.py
```

## Production-only coverage

Measure application modules without counting test files:

```powershell
python -m coverage run --source=core,ui,main -m pytest -q
python -m coverage report --skip-covered
```

On 2026-09-04 at the documentation baseline, this command passed 24 tests and reported 31% across 2,470 production statements. UI modules were unexecuted and coverage warned that `main` was not imported. Coverage is diagnostic; raising a percentage without meaningful behavioral tests is not an acceptance goal.

## OCR tests

The release suite verifies fail-closed workflow compilation when the Tesseract binary is unavailable. A real success test needs controlled Tesseract, Poppler for PDF OCR, installed language data, and fixtures with expected text. The v1.0.0 release machine did not provide that success-path evidence.

## Release-critical sequence

Run the commands above from a clean committed tree. Every command must return exit code zero, and `git status --short` must remain empty. The publication and artifact gates are in [Release process](RELEASE_PROCESS.md).
