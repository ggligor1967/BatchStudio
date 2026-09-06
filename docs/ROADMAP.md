# Roadmap

This is the only canonical location for unimplemented work. Items are candidates, not promises, dates, or assignments. A candidate becomes release scope only through an approved issue and must satisfy tests, documentation, packaging, and release evidence.

## Canonical post-v1.1 execution order

```text
V12-04
→ V12-PERF
```

This sequence constrains admission precedence only; it is not a release promise, assignment, or authorization to start work. The completed `BACKLOG-H0` governance gate, V11-08 behavioral Tkinter coverage, V12-01 final-name collision protection (issue #25), V12-02 aggregate semantic hardening (issue #27), V11-06 controlled real-OCR qualification (issue #10), and V12-03 format-capability decision (issue #33) establish the remaining order but are no longer active or schedulable roadmap items. **V12-04 is the next admissible implementation unit**; it does not start automatically. V12-04 addresses page-aware rendering only after its contract and fixtures exist, and V12-PERF remains benchmark-gated. This order changes only when repository evidence proves a concrete dependency that requires it.

## Completed post-v1.1 units

These units were explicitly **not** part of the 1.1.0 release gate. The published 1.1.0 release does not depend on them.

V11-06 (issue #10) established the dedicated fail-closed `real-ocr-qualification` job, checksum-pinned Tesseract/Poppler/English data, reproducible hashed fixtures, real image and image-only PDF OCR, and a distinct native-text PDF case. No OCR production behavior or aggregate semantics changed. The qualification is limited to the exact successful job SHA and controlled English environment; it is not cross-platform, multilingual, arbitrary-document, or accuracy-benchmark certification. The deterministic mocked V11-05 coverage remains the only OCR qualification shipped in 1.1.0; see [OCR](OCR.md).

V12-03 (issue #33) selected `RESTRICT_TO_GENERIC_COMPATIBILITY` for XLS, XLSX, TXT, JSON, and XML. All five remain classified and core-valid for byte-preserving generic rename, but none is product-admitted or has a format-aware input operation or template. Workflow/settings JSON and OCR-generated TXT remain control/output formats, not input-processing capabilities. The decision added no parser, format feature, dependency, or future support unit; see [Operations](OPERATIONS.md#capability-levels-and-v12-03-decisions).

## V12 backlog units

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
