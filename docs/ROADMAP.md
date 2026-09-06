# Roadmap

This is the only canonical location for unimplemented work. Items are candidates, not promises, dates, or assignments. A candidate becomes release scope only through an approved issue and must satisfy tests, documentation, packaging, and release evidence.

## Canonical post-v1.1 execution order

```text
V12-PERF
```

This sequence constrains admission precedence only; it is not a release promise, assignment, or authorization to start work. The completed `BACKLOG-H0` governance gate, V11-08 behavioral Tkinter coverage, V12-01 final-name collision protection (issue #25), V12-02 aggregate semantic hardening (issue #27), V11-06 controlled real-OCR qualification (issue #10), V12-03 format-capability decision (issue #33), and V12-04 page-aware PDF watermark placement (issue #35) establish the remaining order but are no longer active or schedulable roadmap items. **V12-PERF is the next admissible implementation unit**; it does not start automatically and remains benchmark-gated. This order changes only when repository evidence proves a concrete dependency that requires it.

## Completed post-v1.1 units

These units were explicitly **not** part of the 1.1.0 release gate. The published 1.1.0 release does not depend on them.

V11-06 (issue #10) established the dedicated fail-closed `real-ocr-qualification` job, checksum-pinned Tesseract/Poppler/English data, reproducible hashed fixtures, real image and image-only PDF OCR, and a distinct native-text PDF case. No OCR production behavior or aggregate semantics changed. The qualification is limited to the exact successful job SHA and controlled English environment; it is not cross-platform, multilingual, arbitrary-document, or accuracy-benchmark certification. The deterministic mocked V11-05 coverage remains the only OCR qualification shipped in 1.1.0; see [OCR](OCR.md).

V12-03 (issue #33) selected `RESTRICT_TO_GENERIC_COMPATIBILITY` for XLS, XLSX, TXT, JSON, and XML. All five remain classified and core-valid for byte-preserving generic rename, but none is product-admitted or has a format-aware input operation or template. Workflow/settings JSON and OCR-generated TXT remain control/output formats, not input-processing capabilities. The decision added no parser, format feature, dependency, or future support unit; see [Operations](OPERATIONS.md#capability-levels-and-v12-03-decisions).

V12-04 (issue #35) replaced the fixed Letter watermark overlay with a per-page CropBox and rotation contract. Its byte-deterministic F1-F11 fixtures cover A4, Letter, small and large custom pages, mixed page sizes, rotations 90/180/270, and non-default CropBoxes. Structural tests assert exact visible-coordinate placement, shrink-only containment, page geometry, source content, style, page count, and output ownership without raster comparison or dependency changes; see [Operations](OPERATIONS.md#pdf-watermark-geometry-contract).

## V12 backlog units

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
