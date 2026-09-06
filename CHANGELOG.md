# Changelog

All notable project changes are recorded here. Dates and release facts are included only when supported by repository and release evidence.

## [1.1.0] - 2026-09-05

This release establishes a single canonical application version source and reconciles the release documentation with completed, evidenced work.

### Added

- Single canonical application version source in `core/_version.py`, consumed by the runtime banner, the desktop UI status label and About dialog, and packaging metadata through `pyproject.toml` dynamic version resolution.
- Version-identity tests in `tests/test_version_identity.py`.

### Changed

- `scripts/verify_repository.py` validates the canonical version contract (one source, dynamic packaging metadata, derived runtime/UI consumers, non-diverging package workflow) instead of requiring duplicated literal version strings across documentation.
- `scripts/verify_package.py` and the package workflow verify the release version `1.1.0` and fail on divergence from `core/_version.py`.
- [Release process](docs/RELEASE_PROCESS.md) integration path is stated explicitly as branch to pull request to required checks to protected `main`; the instruction to push `main` directly was removed and immutable new-tag behavior is documented.
- OCR, limitations, operations, and testing documentation reconciled: 1.1.0 ships the deterministic mocked OCR capability and contract coverage completed in V11-05; controlled real-OCR qualification (V11-06, issue #10) is deferred and is not a 1.1.0 release gate.
- At the 1.1.0 release boundary, V11-06 was deferred/conditional and V11-08 (behavioral Tkinter flow coverage) was P2 / stretch and non-blocking; neither was a 1.1.0 release gate.

### Fixed

- Output-collision prevention and isolated per-worker rename counters (V11-01).
- Aggregate-only workflow enforcement, empty-input handling, and stop-before-finalize safety for PDF merge (V11-02).
- Fail-closed CSV filter configuration and rejection of booleans in numeric schemas (V11-03).
- Write-free dry runs across registered writers and reports (V11-04).
- OCR configuration validation and capability reporting for image, PDF, and batch OCR, including explicit rejection of legacy preprocessing keys (V11-05).
- Input picker and Run preflight aligned with actual runtime capabilities so unsupported or unavailable selections are reported accurately (V11-07).

### Runtime

- The V11-R/V11-F release-preparation work introduced no additional functional processing behavior changes. OCR production behavior is unchanged and OCR qualification was not reopened.

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

[1.1.0]: https://github.com/ggligor1967/BatchStudio/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/ggligor1967/BatchStudio/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/ggligor1967/BatchStudio/releases/tag/v1.0.0
