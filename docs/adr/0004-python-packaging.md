# ADR-0004: Standard Python packaging

## Status

Accepted

## Context

The project needs reproducible source and binary-Python distributions, declared dependencies, importable packages, and installable entrypoints without maintaining parallel package definitions.

## Decision

Use `pyproject.toml` with the setuptools build backend as the canonical package configuration. Build standard wheel and source-distribution artifacts with `python -m build`, then verify them through isolated installation, content audit, byte size, and SHA-256.

## Consequences

Standard Python tools can build and install BatchStudio, and artifact identity can be recorded independently of a development checkout. Build tools and dependency resolution remain external inputs. Rebuilt archives are not assumed byte-identical, so published canonical artifacts are retained and verified rather than silently regenerated.

## Update — 2026-09-05 (V11-R)

The project version is declared once in `core/_version.py` and consumed as packaging metadata through the `[tool.setuptools.dynamic]` `version = {attr = "core._version.__version__"}` declaration in `pyproject.toml`. The runtime banner and the desktop UI version displays import the same attribute. `scripts/verify_repository.py` validates this single-source relationship, and `scripts/verify_package.py` fails on any divergence between built distribution metadata and the canonical value. This removes the earlier need to keep duplicated literal version strings synchronized across source and documentation.
