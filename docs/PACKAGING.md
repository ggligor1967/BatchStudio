# Packaging

## Canonical configuration

`pyproject.toml` is the canonical build and package definition. It uses `setuptools.build_meta`, declares distribution name `batchstudio`, a dynamic `version` resolved from the single canonical source `core._version.__version__`, Python 3.10+, runtime dependencies, the `core*` and `ui*` packages, the `main` module, and two entrypoints to `main:main`. The same `core._version.__version__` value backs the runtime banner and the desktop UI version displays, and `scripts/verify_repository.py` fails the build if any of these diverge.

`MANIFEST.in` excludes Git, virtual environments, Python caches, pytest cache, and compiled Python files from the source distribution. `.gitignore` excludes local build, distribution, cache, coverage, report, and virtual-environment output.

The package metadata identifies the canonical `ggligor1967/BatchStudio` repository.

## Build

Build only from the exact clean commit selected for release:

```powershell
git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}
python -m build
```

The build must return zero and produce a wheel and source distribution under `dist/`. Recheck Git status to prove the build did not mutate tracked source.

## Isolated installation

Create a new temporary virtual environment, install the newly built wheel, and verify:

- distribution metadata name and version;
- imports for `core`, `core.processor`, `core.workflow`, and `core.operations`;
- resolution and loading of `batchstudio-gui`.

Do not reuse the development environment as release installation evidence.

## Artifact content audit

List wheel ZIP members and source-distribution TAR members. Reject an artifact containing `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.coverage`, or `build/`. Also inspect the exact asset set so unrelated local files are not published.

## Artifact identity

For every artifact record the filename, exact byte size, and SHA-256 digest. On PowerShell, `Get-Item` provides length and `Get-FileHash -Algorithm SHA256` provides the digest. The canonical 1.0.0 values are in [v1.0.0 release verification](releases/v1.0.0-verification.md).

Rebuilding can legitimately change archive bytes even when source is unchanged. Never substitute a rebuild for a required canonical artifact whose identity is already fixed.

See [ADR-0004](adr/0004-python-packaging.md) for the packaging decision.
