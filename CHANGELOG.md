# Changelog

All notable project changes are recorded here. Dates and release facts are included only when supported by repository and release evidence.

## [Unreleased]

### Documentation

- Replaced duplicated, generated, and obsolete documentation with one canonical suite.
- Documented current operations, workflows, architecture, security controls, limitations, testing, packaging, and release procedure from source and test evidence.
- Added contributor, support, security, agent-governance, ADR, and v1.0.0 verification documents.

## [1.0.0] - 2026-09-04

- Published the initial verified BatchStudio release from commit `bed4c76e0928f2aa7c4982b961b2c6564c696821`.
- Published a wheel and source distribution whose sizes and SHA-256 digests are recorded in [the release verification record](docs/releases/v1.0.0-verification.md).
- Verified the full automated suite, critical end-to-end cases, PDF merge regressions, package build, isolated installation, entrypoint loading, artifact contents, and Git provenance.
- Verified the OCR missing-capability path; a real OCR success path was not verified on the release machine.

[Unreleased]: https://github.com/ggligor1967/BatchStudio/compare/v1.0.0...main
[1.0.0]: https://github.com/ggligor1967/BatchStudio/releases/tag/v1.0.0
