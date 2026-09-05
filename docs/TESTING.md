# Testing

## Required GitHub checks

The active `main-protection` ruleset requires a pull request branch to be up to date and requires these exact GitHub Actions check names:

- `ci-windows-py310`
- `ci-windows-py312`
- `ci-ubuntu-py312`
- `release-regressions`
- `repository-truth`
- `package-build-install`
- `dependency-review`

The first six run for pull requests and pushes to `main`; `dependency-review` is intentionally pull-request-only. The Windows and Ubuntu jobs validate non-interactive compatibility and do not prove interactive Linux GUI behavior. `repository-truth` enforces version/document/link hygiene, artifact exclusions, stable job names, changed-line whitespace, and full-SHA action pins. `package-build-install` audits one wheel and one source distribution, then installs and imports the wheel from outside the repository in a fresh virtual environment.

## Test topology

`pyproject.toml` sets `testpaths = ["tests"]`, so normal discovery runs the five modules under `tests/`. V11-01 increases discovery from 24 to 76 tests:

- `tests/test_operations.py`: result contract, resize output, and aggregate registration.
- `tests/test_processor.py`: path validation, operation chains, dry run, duplicate allocation, traversal-shaped naming, and report encoding.
- `tests/test_workflow.py`: workflow and compiler rejection cases.
- `tests/test_e2e_release_blockers.py`: resize/convert chains, PDF merge and containment, dry run, malformed configuration, OCR dependency absence, pause, and cancellation.
- `tests/test_output_ownership.py`: 52 focused V11-01 cases for all registered per-file writers, direct entrypoints, final-path collisions, deterministic counter interleaving, canonical reservation aliases, exclusive creation, aggregate ownership, intermediate cleanup, and normal probe ownership. Symlink cases skip explicitly if the OS does not permit link creation.

Run the discovered suite:

```powershell
pytest -q
```

Run the critical end-to-end suite independently:

```powershell
pytest -q tests/test_e2e_release_blockers.py
```

Run V11-01 independently:

```powershell
pytest -q tests/test_output_ownership.py
```

The initial 37-case pre-fix matrix produced 36 failures and one pass on the admitted source; the deterministic counter test re-enters worker B while worker A is paused at its operation call, without sleeps or probabilistic assertions. Collision tests use temporary sentinel files, including collisions injected immediately before the actual open. OCR text extraction is mocked; these are path-contract tests and require neither Tesseract nor Poppler. Additional cases verify successful outputs, partial-write cleanup, replaced intermediates, and exclusive probe creation. These tests do not qualify aggregate lifecycle changes or strict write-free dry runs.

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

On 2026-09-05, V11-01 validation on Windows/Python 3.13 passed 76 tests and reported 37% across 2,541 production statements. `core/security.py` reached 99%; the writer modules ranged from 73% to 97%, and `core/processor.py` reached 81%. UI modules remained unexecuted and `main` was not imported. Local pytest runs disabled unrelated globally installed plugin autoload via `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; no repository dependencies or pytest configuration changed. CI separately verifies the required Python 3.10/3.12 environments.

## OCR tests

The release suite verifies fail-closed workflow compilation when the Tesseract binary is unavailable. A real success test needs controlled Tesseract, Poppler for PDF OCR, installed language data, and fixtures with expected text. The v1.0.1 release preparation does not provide that success-path evidence.

## Release-critical sequence

Run the commands above from a clean committed tree. Every command must return exit code zero, and `git status --short` must remain empty. The publication and artifact gates are in [Release process](RELEASE_PROCESS.md).
