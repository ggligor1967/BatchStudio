# Changelog

All notable project changes are recorded here. Dates and release facts are included only when supported by repository and release evidence.

## [1.0.1] - 2026-09-04

### Documentation

- Replaced obsolete and contradictory documentation with the canonical verified documentation suite.
- Added architecture, security, testing, packaging, release, OCR, workflow, operations, development, and governance documentation.
- Added ADRs and v1.0.0 release-verification evidence.

### Changed

- Corrected stale package/repository metadata and user-facing version text where applicable.

### Removed

- Removed obsolete duplicate documentation, generated transcripts/status dumps, and stale project-tracking artifacts.

### Runtime

- No functional processing behavior changes.

## [1.0.0] - 2026-09-04

- Published the initial verified BatchStudio release from commit `bed4c76e0928f2aa7c4982b961b2c6564c696821`.
- Published a wheel and source distribution whose sizes and SHA-256 digests are recorded in [the release verification record](docs/releases/v1.0.0-verification.md).
- Verified the full automated suite, critical end-to-end cases, PDF merge regressions, package build, isolated installation, entrypoint loading, artifact contents, and Git provenance.
- Verified the OCR missing-capability path; a real OCR success path was not verified on the release machine.

[1.0.1]: https://github.com/ggligor1967/BatchStudio/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/ggligor1967/BatchStudio/releases/tag/v1.0.0
