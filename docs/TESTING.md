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

V11-06 additionally requires the separately readable `real-ocr-qualification` job for candidate and final-main OCR evidence. It runs on pull requests and pushes to `main`. It is an issue-level release gate in addition to the seven ruleset-required checks; it is not silently folded into the general CI matrix.

## Test topology

`pyproject.toml` sets `testpaths = ["tests"]`, so normal discovery runs fifteen test modules under `tests/`. V11-01 increased discovery from 24 to 77 tests, V11-02 to 107, V11-03/V11-04 to 203, V11-05 to 289, V11-07 to 365, V11-R to 379, V11-07R to 401, V11-07R2 to 417, V11-08 to 422, V12-01 to 434, V12-02 to 462, and V12-03 to 506 on a supported graphical Windows session:

- `tests/test_operations.py`: result contract, resize output, and aggregate registration.
- `tests/test_processor.py`: path validation, operation chains, dry run, duplicate allocation, traversal-shaped naming, report encoding, and preservation of empty non-merge validation.
- `tests/test_workflow.py`: workflow/compiler rejection cases, aggregate-only acceptance, disabled-step handling, and enabled-predecessor/multiple-aggregate rejection.
- `tests/test_aggregate_lifecycle.py`: empty input, output publication, event-controlled stop/pause boundaries, dry-run plans, partial-invalid-input policy, and success/failure/stop/success isolation.
- `tests/test_aggregate_semantics.py`: complete registry classification, explicit compiled plans, every aggregate composition shape, original-input flow, core/UI type preflight parity, defensive per-file rejection, and lifecycle exception boundaries.
- `tests/test_e2e_release_blockers.py`: resize/convert chains, PDF merge and containment, dry run, malformed configuration, OCR dependency absence, pause, and cancellation.
- `tests/test_output_ownership.py`: 53 focused V11-01 cases for all registered per-file writers, direct entrypoints, final-path collisions, deterministic counter interleaving, canonical reservation aliases, exclusive creation, aggregate ownership, intermediate cleanup, and normal probe ownership. Symlink cases skip explicitly if the OS does not permit link creation.
- `tests/test_final_name_collision.py`: 12 V12-01 cases for occupied and collision-at-open reports, barrier-controlled concurrent report and independent-worker ownership, different initial names converging on one final class, sanitizer aliases, Windows case aliases, and current-run report provenance that prevents stale report viewing after a collision.

- `tests/test_csv_contracts.py`: 43 V11-03 cases for generic required/non-empty and float parity, numeric boolean rejection, compiler/direct CSV rejection, missing concrete columns, normal matching/zero-row output, dry-run counts, and both numeric operators.
- `tests/test_dry_run_contracts.py`: 53 V11-04 cases for registered writers, read-only validation, empty input, unsupported operations, provenance/UI option mutation, automatic/manual/direct reports, normal report/probe preservation, and write-interceptor calibration.
- `tests/test_ocr_contracts.py`: 86 deterministic V11-05 cases covering schema/legacy-key parity, all four OCR templates, separate dependency failures, live readiness refresh, PDF modes and forwarding, batch delegates, and schema/status UI routes.

- `tests/test_input_capabilities.py`: 110 V11-07/V11-07R/V11-07R2 cases for naming-hint placeholders, outcome-accurate completion and success-only celebration, aggregate stop/finalization states, truthful DnD labels, launch filesystem behavior, About metadata, the images/PDF/CSV UI policy, retained core and OCR-to-rename compatibility, independent image/native PDF/PDF OCR states, unsupported and unavailable selection boundaries, picker/folder/drop routes, stale/failed worker probes, and run preflight. Runtime readiness is mocked; OCR qualification is not repeated. Run independently with `python -m pytest -q tests/test_input_capabilities.py`.
- `tests/test_format_capability_decisions.py`: 44 V12-03 cases for XLS, XLSX, TXT, JSON, and XML classification, core validation, picker and preflight restriction, byte-preserving generic rename, picker/folder/drop rejection, Run-boundary refusal, operation/template exclusion, and canonical decision documentation. CSV, PNG, and PDF are preserved admitted controls across every UI route. Run independently with `python -m pytest -q tests/test_format_capability_decisions.py`.

- `tests/test_version_identity.py`: 14 V11-R cases for the canonical `core._version.__version__` source, the `pyproject.toml` dynamic-version contract, the runtime banner and UI version surfaces, installed distribution metadata, the repository and package version verifiers (including divergence detection), and release-documentation invariants (CHANGELOG candidate section, protected release-process integration path, OCR-qualification reconciliation, and ROADMAP completed-unit/next-admission/deferred markers). Run independently with `python -m pytest -q tests/test_version_identity.py`.
- `tests/test_tkinter_behavioral_flow.py`: five V11-08 cases using a withdrawn real `tk.Tk` root and the real `MainWindow` panels. They cover input admission, workflow construction/configuration, four-tab navigation, a synthetic file-rename run, repeated execution, progress/results, deterministic failure, no-input behavior, worker-to-Tk callback dispatch, dialog/settings isolation, bounded waits including a forced timeout, and clean teardown.

Run the discovered suite:

```powershell
pytest -q
```

## V11-08 Tkinter behavioral flow

Run the focused behavioral suite from an interactive graphical Windows session with Tk 8.6 available:

```powershell
python -m pytest -q tests/test_tkinter_behavioral_flow.py
```

The module creates and withdraws one real Tk root; each behavioral flow test instantiates `MainWindow` and drives panel callbacks directly. Worker completion is event-loop pumped until an observable widget/application condition succeeds, with a five-second maximum for every production-flow wait and worker join. A focused regression forces the timeout path with a 0.01-second bound and confirms that it fails deterministically without leaving a Tk callback queued. The required Windows CI jobs must create a Tk root or fail. A headless non-Windows job skips these five cases with an explicit `Tk graphical session unavailable` reason; this does not claim interactive Linux qualification.

All inputs, outputs, and settings paths are synthetic and confined to pytest temporary directories. Message boxes, file choosers, the placeholder preferences dialog, and the success animation are isolated so the suite never waits for user input. The successful flow uses the real processor and registered file-rename operation; the failure case replaces only the per-file operation boundary with a deterministic failure. Runtime assertions prove that processing occurs off the Tk thread and the resulting status-widget mutation occurs on it.

Coverage is behavioral state/callback verification, not screenshot, pixel, accessibility-tree, or OS-wide automation. It does not certify drag-and-drop, native dialog rendering, window-manager behavior, theming, visual layout, real OCR, performance, or cross-platform interactive display behavior. Stop/cancel remains covered at the processor and V11-07 completion-contract boundaries; issue #12 does not require a new interactive cancellation scenario.

Run the critical end-to-end suite independently:

```powershell
pytest -q tests/test_e2e_release_blockers.py
```

Run V11-01 independently:

```powershell
pytest -q tests/test_output_ownership.py
```

The initial 37-case pre-fix matrix produced 36 failures and one pass on the admitted source; the deterministic counter test re-enters worker B while worker A is paused at its operation call, without sleeps or probabilistic assertions. Collision tests use temporary sentinel files, including collisions injected immediately before the actual open. OCR text extraction is mocked; these are path-contract tests and require neither Tesseract nor Poppler. Additional cases verify successful outputs, partial-write cleanup, replaced intermediates, and exclusive probe creation. These tests do not qualify aggregate lifecycle changes or strict write-free dry runs.

Run V12-01 independently:

```powershell
pytest -q tests/test_final_name_collision.py tests/test_output_ownership.py
```

The V12-01 cases use `threading.Barrier` at the exclusive-creation boundary rather than sleeps. Repetition is a regression-exposure check, not an automatic retry: every iteration must pass. Existing report destinations retain their exact bytes, concurrent contenders produce one success and one explicit failure, successful operation results identify the actual winner, and the HTML viewer opens only a report recorded as generated for the current run.

## V11-02 aggregate regressions

Run the focused 31-case selection independently:

```powershell
pytest -q tests/test_aggregate_lifecycle.py tests/test_workflow.py tests/test_e2e_release_blockers.py -k 'aggregate or pdf_merge'
```

Before production changes, the original 27-case selection produced 12 failures and 15 passes on the admitted V11-01 source. Four additional review regressions failed before the empty-input validation-order correction, then passed: blank workflow name, invalid aggregate configuration, enabled predecessor, and multiple aggregates. Stop tests use events, including after the last consumption has completed; pause tests exercise the existing pause loop with its timed wait replaced by events. They do not use sleeps or claim cancellation after finalization begins. Final-write failure is injected through the real PDF writer, checking owned-partial cleanup, preservation of an earlier output, and fresh state on subsequent runs.

The canonical `test_e2e_pdf_merge` cases cover two, three, and five inputs through `tests/pdf_merge_cases.py`, with asserted page counts, non-lexical input order, one actual final output, and zero failures. The root diagnostics reuse this helper.

## V12-02 aggregate semantic regressions

Run the focused compiler/preflight/runtime contract independently:

```powershell
pytest -q tests/test_aggregate_semantics.py
```

The 28 cases account for all nine per-file and one aggregate registry entries. They assert explicit valid plan metadata, no executable plan on rejection, every mixed workflow shape under Contract A, disabled-step behavior, original input order/content, missing-path and homogeneous/mixed wrong-type rejection before output preparation, UI/core preflight agreement, direct per-file aggregate refusal before any predecessor executes, and begin/consume/finalize exception reporting. The initial test-first run produced 23 failures and two passes before production changes; UI wrong-type, missing-path, and direct-worker ordering regressions were added during implementation/audit, bringing the final focused set to 28. V11-02 partial-invalid-PDF, event-controlled cancellation, and V12-01 ownership remain separate preserved suites.

## V11-03 and V11-04 regressions

Run the two contracts independently:

```powershell
pytest -q tests/test_csv_contracts.py
pytest -q tests/test_dry_run_contracts.py
```

Before production changes, the initial CSV matrix produced 21 failures and 16 passes; the initial dry-run matrix produced 43 failures and one pass. Additional cases check dry-run CSV counts, normal manual reports, and interceptor calibration. The existing V11-01 CSV writer fixture now supplies valid required configuration so ownership assertions still reach the writer. The V11-02 dry-run assertion now requires the missing output directory to remain absent; lifecycle assertions are preserved.

The dry-run suite intercepts attempted output-scoped directory creation, writable opens, temporary files, exclusive writers, copying/renaming, cleanup, aggregate/PDF writes, and report writers; it also compares directory contents and bytes before/after. It covers all nine registered per-file operations plus aggregate merge, including both batch OCR delegates, with existing and missing output directories. OCR capability/extraction boundaries are mocked without invoking real OCR or rasterization. UI tests run real worker threads with thread-checking variable doubles and queued completion callbacks; they exercise option/checkbox mutation without requiring a graphical display. These are focused route tests, not an interactive GUI qualification. See the [precise dry-run boundary](SECURITY_MODEL.md#dry-run-output-suppression).

## Root checks

`test_installation.py` is both an importable pytest module and a standalone console check. Because it is outside configured `testpaths`, invoke it explicitly:

```powershell
pytest -q test_installation.py
python test_installation.py
```

The root PDF merge scripts remain supported standalone diagnostics and execute the same asserted three/five-input helper used by pytest:

```powershell
python test_pdf_merge_fix.py
python test_pdf_merge_simple.py
```

Assertion failures return a nonzero exit code. CI runs their cases through the critical end-to-end pytest suite; duplicate standalone invocations were removed from `release-regressions` without changing any required check name. Standalone commands remain available for local diagnosis.

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

On 2026-09-05, V11-01 validation on Windows/Python 3.13 passed 77 tests and reported 37% across 2,543 production statements. `core/security.py` reached 99%; the writer modules ranged from 73% to 97%, and `core/processor.py` reached 81%. UI modules remained unexecuted and `main` was not imported. Local pytest runs disabled unrelated globally installed plugin autoload via `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; no repository dependencies or pytest configuration changed. CI separately verifies the required Python 3.10/3.12 environments.

On 2026-09-05, V11-02 validation on Windows/Python 3.13 passed 107 tests and reported 38% across 2,559 production statements (985 executed). `core/processor.py` reached 85%, with 21 of 25 changed executable lines covered (four reindented output-directory error-handling lines were unexecuted); the PDF operations module reached 94% and output security remained at 99%. UI modules remained unexecuted and `main` was not imported. The same local plugin-autoload isolation was used. Coverage remains diagnostic, with no global threshold.

On 2026-09-05, V11-03/V11-04 validation on Windows/Python 3.13 passed 203 tests and reported 48.65% production coverage (1,259 of 2,588 statements; the console rounds to 49%). The shared operation base reached 89.41%, CSV operations 89.58%, processor 86.74%, RunPanel 34.74%, and LogsPanel 18.47%. Output security remained 98.63% and PDF operations reached 95.24%. Changed executable-line coverage was 24/26 in the shared base, 12/15 in CSV, 25/27 in the processor, and 21/21 across both UI panels. Uncovered changed lines include existing boolean/choice rejection branches, reindented CSV `!=`/`contains` handling, invalid empty/NUL destination rejection, and the no-existing-parent fallback. UI coverage exercises routes with doubles rather than rendering widgets; `main` was not imported. Local runs used the same plugin-autoload isolation. These measurements are diagnostic, with no threshold.

## OCR tests

On 2026-09-05, V11-05 validation on Windows/Python 3.13 passed 289 tests and reported 56.63% production coverage (1,541 of 2,721 statements). OCR operations reached 175/184 statements (95.11%), the registry 55/59 (93.22%), workflow definitions 208/259 (80.31%), and WorkflowPanel 113/299 (37.79%). Changed executable lines were covered 96/97 in OCR operations, 25/27 in the registry, and 55/58 in WorkflowPanel; the uncovered lines are the OCR abstract-method guard, the registry's non-OCR/invalid-config display returns, the refresh-button creation in the full widget builder, and the apply-triggered refresh route. Template literal edits have no separately attributed changed executable lines. `main` was not imported. UI evidence uses widget doubles and event-controlled real threads, and OCR output is mocked. Local runs disabled unrelated global pytest plugin autoload with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Coverage is diagnostic, with no threshold.

Run V11-05 independently:

```powershell
pytest -q tests/test_ocr_contracts.py
```

The initial 64-case regression matrix on the admitted source produced 49 failures and 15 passes before implementation. The final 86-case suite adds rasterizer launch/timeout and argument-vector checks, real UI configuration-route tests with widget doubles, and concrete batch language/preflight coverage. Review regressions first reproduced four batch PDF pass-through validation failures, synchronous Tk probing, and redundant batch image probes. Event-controlled tests verify nonblocking worker probes, Tk-only scheduling/publication, configuration snapshots, pending/error/destroyed-widget handling, and stale-response suppression. Native mode retains its ignored language semantics, including blank values; it never requires OCR language data. All external tools, language lists, rasterization, and recognition outputs are mocked. Native PDF threshold tests assert the existing 49/50-character boundary, including mode/language/DPI forwarding. Both directions of executable, language, and rasterizer state changes are tested without module reload.

The inherited ownership and complete 53-case dry-run write-interception suites use fresh version/language/rasterizer mocks; their original assertions remain intact. Dry runs check only unconditional capabilities and never recognize or rasterize. Auto dry run does not predict fallback. The critical end-to-end absence test now deterministically mocks a missing executable rather than potentially invoking real OCR when local tools happen to be installed.

UI tests exercise the actual operation-list/configuration methods with widget doubles, including refreshed status for applied language/mode and absence of inert controls; they are not interactive GUI qualification. Controlled real-OCR qualification (V11-06, issue #10) remains separate from the published 1.1.0 release evidence and from these mocked tests; see [Roadmap](ROADMAP.md). Real OCR is qualified only by a successful dedicated job for its exact SHA and pinned English environment. Ordinary tests install no external tools or language packs.

## Controlled real-OCR qualification

The dedicated suite is outside `pyproject.toml`'s default `tests/` discovery so ordinary CI remains deterministic and mock-based. The `real-ocr-qualification` job explicitly provisions and verifies the environment before invoking it:

```bash
python -m pytest -q qualification/real_ocr/test_real_ocr.py -ra
```

The suite contains 15 real-environment cases and permits zero skips. It proves real image recognition; forced and auto image-only PDF recognition; absence of a useful scanned-PDF native text layer; separate native PDF extraction with external OCR commands unavailable; both `ocr_batch` delegates; normal UTF-8 TXT output; four write-free dry-run branches; V12-01 collision-safe final names; invalid-image failure; and fail-closed missing-tool, checked-out-SHA, and unexpected-verifier-error detection.

Before pytest, CI runs the checksum-validating downloader, the environment verifier, and byte-for-byte fixture regeneration. On pull requests it checks out and verifies `pull_request.head.sha` rather than the synthetic merge ref; on `main` pushes it verifies `github.sha`. Logs identify both the event SHA and `QUALIFICATION_REPOSITORY_SHA`, runner image fields, `/etc/os-release`, `uname`, Python/package resolution, exact Debian package versions, command version output, executable hashes, traineddata identity, and all fixture hashes. A successful job is evidence only for its logged qualification SHA. The workflow has no skip or xfail path: setup, identity, regeneration, or test failure makes the job red.

The exact environment, artifact sources, hashes, expected strings, normalization policy, native/OCR distinction, reproduction sequence, and limitations are canonical in [OCR](OCR.md#controlled-environment).

## Release-critical sequence

Run the commands above from a clean committed tree. Every command must return exit code zero, and `git status --short` must remain empty. The publication and artifact gates are in [Release process](RELEASE_PROCESS.md).
