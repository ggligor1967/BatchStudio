# Roadmap

This is the only canonical location for unimplemented work. Items are candidates, not promises, dates, or assignments. A candidate becomes release scope only through an approved issue and must satisfy tests, documentation, packaging, and release evidence.

## Canonical post-v1.1 execution order

```text
V12-03
→ V12-04
→ V12-PERF
```

This sequence constrains admission precedence only; it is not a release promise, assignment, or authorization to start work. The completed `BACKLOG-H0` governance gate, V11-08 behavioral Tkinter coverage, V12-01 final-name collision protection (issue #25), V12-02 aggregate semantic hardening (issue #27), and V11-06 controlled real-OCR qualification (issue #10) establish the remaining order but are no longer active or schedulable roadmap items. **V12-03 is the next admissible implementation unit**; it does not start automatically. V12-03 resolves product capability ambiguity before any new format work, V12-04 addresses page-aware rendering only after its contract and fixtures exist, and V12-PERF remains benchmark-gated. This order changes only when repository evidence proves a concrete dependency that requires it.

## Completed post-v1.1 unit

This unit was explicitly **not** part of the 1.1.0 release gate. The published 1.1.0 release does not depend on it.

V11-06 (issue #10) established the dedicated fail-closed `real-ocr-qualification` job, checksum-pinned Tesseract/Poppler/English data, reproducible hashed fixtures, real image and image-only PDF OCR, and a distinct native-text PDF case. No OCR production behavior or aggregate semantics changed. The qualification is limited to the exact successful job SHA and controlled English environment; it is not cross-platform, multilingual, arbitrary-document, or accuracy-benchmark certification. The deterministic mocked V11-05 coverage remains the only OCR qualification shipped in 1.1.0; see [OCR](OCR.md).

## V12 backlog units

### V12-03 — Excel / structured-text capability decision

- **Problem:** `.xls`/`.xlsx` and non-CSV structured-text extensions are core-classified, while UI admission excludes them and no dedicated registered operation transforms their content. The product needs an explicit support or restriction decision before capability claims expand.
- **Existing evidence:** `core/operations/registry.py` classifies Excel as `spreadsheet` and TXT/JSON/XML as `text`; `ui/input_support.py` admits only images, PDF, and CSV. Current documentation limits Excel and structured text to compatibility paths such as generic rename and generated OCR TXT. CSV already has a real, separately documented transformation.
- **Risk:** P2 product correctness. Ambiguous classification can imply unsupported processing, while premature support can introduce parser, dependency, data-loss, and format-fidelity risks.
- **Priority:** P2.
- **Scope:** Produce a per-format decision for `.xls`, `.xlsx`, `.txt`, `.json`, and `.xml`: implement supported operations in a separately approved unit, retain an explicitly restricted compatibility role, or remove the classification/claim. Define the user-visible and runtime consequences of each disposition.
- **Explicit non-goals:** Automatic feature implementation, adding spreadsheet/parser dependencies, treating generic rename as content support, changing CSV behavior, or claiming format fidelity without fixtures and tests.
- **Dependencies:** Completed V11-07 capability-truth work, V11-08 behavioral coverage, and settled V12-02 workflow semantics. If support is selected, a new approved implementation unit and dependency decision are required.
- **Acceptance criteria:** Every listed extension has one documented disposition, and registry classification, processor allow-list, picker/folder/drop admission, operation compatibility, templates, and user-facing claims are consistent with it. A support decision includes concrete operations, dependency review, fixtures, failure policy, and follow-on acceptance criteria; it does not itself imply implementation.
- **Test strategy:** Use the existing capability-route matrix to lock the selected restriction/removal behavior. Any later support unit must add synthetic format fixtures and compiler, direct-operation, batch, dry-run, malformed-input, and UI-route tests before claims change.
- **Documentation impact:** Reconcile [Operations](OPERATIONS.md), [User guide](USER_GUIDE.md), [Workflows](WORKFLOWS.md), and [Limitations](LIMITATIONS.md) with the selected disposition.

### V12-04 — Page-aware PDF watermark placement

- **Problem:** The watermark uses one fixed letter-sized canvas and fixed coordinates for every page, so placement is not derived from actual page geometry.
- **Existing evidence:** `PDFWatermarkOperation` creates a reportlab `letter` canvas, translates to fixed coordinates, and merges that same page onto every source page. Existing ownership coverage verifies successful output and page count, not placement across page sizes, crop boxes, or rotation. [Limitations](LIMITATIONS.md) records the fixed-layout boundary.
- **Risk:** P2 rendering correctness. Watermarks can be clipped, displaced, scaled unexpectedly, or absent from the visible area on non-letter or rotated pages.
- **Priority:** P2.
- **Scope:** First define placement coordinates, scaling, rotation, crop/media-box handling, supported page geometries, and deterministic fixtures. Only then implement per-page watermark construction and merge behavior against that contract.
- **Explicit non-goals:** OCR, arbitrary graphic overlays, typography/layout engines, pixel-identical rendering across unspecified PDF renderers, or dependency additions without approval.
- **Dependencies:** Stable output/workflow contracts from V12-01/V12-02. Contract and fixtures precede implementation; existing pypdf/reportlab behavior remains authoritative until then.
- **Acceptance criteria:** The approved contract covers portrait, landscape, mixed-size, rotated, and non-default-box fixtures. Watermark placement remains within the defined visible region on every supported page, preserves page count and source geometry, reports controlled failures, and keeps output ownership guarantees.
- **Test strategy:** Commit synthetic PDFs with documented geometry and hashes. Assert page boxes/rotation and watermark transform semantics; use a pinned, documented renderer for any raster placement assertion, with tolerances fixed before implementation. Preserve ownership, malformed/encrypted-PDF, and dry-run regressions.
- **Documentation impact:** Update [Operations](OPERATIONS.md) and [Limitations](LIMITATIONS.md), document the rendering contract and fixture identities, and add no visual guarantee beyond the tested geometries.

### V12-PERF — Reproducible performance baseline

- **Problem:** No optimization or numeric performance claim is admissible until a reproducible baseline separates workload, environment, measurement method, and result variance.
- **Existing evidence:** DOC-07 in the maintainer contract requires a reproducible benchmark definition. Existing test-count and coverage records are correctness evidence, not performance benchmarks; the historical ROADMAP candidate was benchmark-gated.
- **Risk:** Evidence integrity. Uncontrolled timings can drive regressions, misleading claims, or optimizations that change semantics without measurable benefit.
- **Priority:** Evidence-driven / later.
- **Scope:** Define versioned synthetic workloads and fixture hashes; operation mix and input sizes; cold/warm policy; worker counts; machine, OS, Python, tool, and dependency identity; exact command; warm-up and repetition counts; elapsed-time and resource metrics; aggregation statistics; raw-result retention; and variance reporting.
- **Explicit non-goals:** Performance optimization, target numbers chosen after measurement, marketing claims, cross-machine equivalence, or replacing correctness/release gates with benchmark results.
- **Dependencies:** Stable semantics from all preceding units. External OCR or PDF tools are benchmark inputs only when their exact versions and data are fixed.
- **Acceptance criteria:** A fresh documented environment can execute the same command against identical fixture hashes and produce machine-readable raw samples plus a declared summary and variance. Optimization work is admitted only after the baseline, bottleneck, target metric, guardrails, and acceptable regression budget are approved prospectively.
- **Test strategy:** Validate fixture identity, benchmark configuration, result schema, repeat count, and failure propagation. Run calibration trials to expose warm-up and variance, but do not convert calibration data into a product claim.
- **Documentation impact:** Add the benchmark definition and evidence location to [Testing](TESTING.md) when implemented; publish no number in canonical documentation without the reproducible command, environment identity, raw evidence, and limitations.
