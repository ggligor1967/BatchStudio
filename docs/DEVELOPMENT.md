# Development

## Environment

Use Python 3.10 or newer in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

OCR development additionally needs the runtime described in [OCR](OCR.md). Keep external executables outside the repository.

## Branch workflow

Start from an up-to-date `main`, create a focused topic branch, and submit changes through a pull request. Direct pushes to `main` are prohibited. The contribution boundary is canonical in [Contributing](../CONTRIBUTING.md), and required local and GitHub checks are canonical in [Testing](TESTING.md).

## Source layout

- `main.py`: application entrypoint.
- `core/`: contracts, validation/security helpers, workflows, processing, settings, and operations.
- `ui/`: Tkinter panels and window coordination.
- `tests/`: automatically discovered pytest suite.
- root `test_*.py` files: standalone installation and PDF merge checks with separate invocation rules.
- `docs/`: canonical technical and maintainer documentation.

Read [Architecture](ARCHITECTURE.md) before changing execution flow and [Operations](OPERATIONS.md) before extending the registry.

## Adding or changing an operation

1. Implement the existing `Operation` or `AggregateOperation` interface.
2. Give the operation a stable ID, accepted types, output type, validation, and configuration schema.
3. Return `OperationResult` for every success and failure path.
4. Route generated destinations through processor allocation and containment; do not construct unchecked output paths.
5. Register the class in `core/operations/registry.py`.
6. Add focused unit and end-to-end coverage, including malformed configuration, dry run, failure, and collision behavior.
7. Update `docs/OPERATIONS.md`, relevant limitations, and an ADR only if an architectural decision changed.

Do not add extension instructions to a monolithic `core/operations.py`; operations are a package under `core/operations/`.

## UI changes

Tkinter widgets belong to the main thread. Background work may communicate through callbacks, but widget changes must be scheduled with `after`. Test core behavior without requiring a display, and describe any manual GUI verification separately.

## Local artifacts

Do not commit `.venv/`, caches, coverage data, `build/`, `dist/`, reports, temporary inputs, workflow scratch files, or generated agent/status transcripts. Check `git status --short` before staging.

## Documentation changes

Follow the DOC-01 through DOC-07 rules in [AGENTS.md](../AGENTS.md). Prefer links to canonical subjects over copied explanations. Validate relative links, versions, stale terms, and runtime zero-change when the task is documentation-only.
