# ADR-0004: Standard Python packaging

## Status

Accepted

## Context

The project needs reproducible source and binary-Python distributions, declared dependencies, importable packages, and installable entrypoints without maintaining parallel package definitions.

## Decision

Use `pyproject.toml` with the setuptools build backend as the canonical package configuration. Build standard wheel and source-distribution artifacts with `python -m build`, then verify them through isolated installation, content audit, byte size, and SHA-256.

## Consequences

Standard Python tools can build and install BatchStudio, and artifact identity can be recorded independently of a development checkout. Build tools and dependency resolution remain external inputs. Rebuilt archives are not assumed byte-identical, so published canonical artifacts are retained and verified rather than silently regenerated.
