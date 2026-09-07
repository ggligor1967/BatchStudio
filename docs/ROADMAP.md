# Roadmap

This is the only canonical location for unimplemented work. Items are candidates, not promises, dates, or assignments. A candidate becomes release scope only through an approved issue and must satisfy tests, documentation, packaging, and release evidence.

## Canonical post-v1.1 execution order

```text
No implementation unit is currently admitted.
```

The completed `BACKLOG-H0` governance gate, V11-08 behavioral Tkinter coverage, V12-01 final-name collision protection (issue #25), V12-02 aggregate semantic hardening (issue #27), V11-06 controlled real-OCR qualification (issue #10), V12-03 format-capability decision (issue #33), V12-04 page-aware PDF watermark placement (issue #35), and V12-PERF reproducible performance baseline (issue #37) are no longer active or schedulable roadmap items. A new candidate requires evidence, an approved tracking issue, and explicit admission; completion of V12-PERF is not authorization to optimize production code.

## Completed post-v1.1 units

These units were explicitly **not** part of the 1.1.0 release gate. The published 1.1.0 release does not depend on them.

V11-06 (issue #10) established the dedicated fail-closed `real-ocr-qualification` job, checksum-pinned Tesseract/Poppler/English data, reproducible hashed fixtures, real image and image-only PDF OCR, and a distinct native-text PDF case. No OCR production behavior or aggregate semantics changed. The qualification is limited to the exact successful job SHA and controlled English environment; it is not cross-platform, multilingual, arbitrary-document, or accuracy-benchmark certification. The deterministic mocked V11-05 coverage remains the only OCR qualification shipped in 1.1.0; see [OCR](OCR.md).

V12-03 (issue #33) selected `RESTRICT_TO_GENERIC_COMPATIBILITY` for XLS, XLSX, TXT, JSON, and XML. All five remain classified and core-valid for byte-preserving generic rename, but none is product-admitted or has a format-aware input operation or template. Workflow/settings JSON and OCR-generated TXT remain control/output formats, not input-processing capabilities. The decision added no parser, format feature, dependency, or future support unit; see [Operations](OPERATIONS.md#capability-levels-and-v12-03-decisions).

V12-04 (issue #35) replaced the fixed Letter watermark overlay with a per-page CropBox and rotation contract. Its byte-deterministic F1-F11 fixtures cover A4, Letter, small and large custom pages, mixed page sizes, rotations 90/180/270, and non-default CropBoxes. Structural tests assert exact visible-coordinate placement, shrink-only containment, page geometry, source content, style, page count, and output ownership without raster comparison or dependency changes; see [Operations](OPERATIONS.md#pdf-watermark-geometry-contract).

V12-PERF (issue #37) established deterministic F1-F5 fixtures and hashes, frozen B1-B5 workloads, exact environment and dependency identity, warm measurement and variance policies, fail-closed correctness guardrails, retained raw samples, two-session repeatability evidence, and noise-derived regression budgets. Both sessions passed at source commit `1bfae7b091f9ce8dca64219792c3438604ea2ad5`; bounded profiling established no actionable bottleneck, so no optimization unit is admitted. The unit changed no production runtime behavior; see [Reproducible performance baseline](PERFORMANCE_BASELINE.md).
