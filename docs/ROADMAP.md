# Roadmap

This is the only canonical location for unimplemented work. Items are candidates, not promises, dates, or assignments. A candidate becomes release scope only through an approved issue and must satisfy tests, documentation, packaging, and release evidence.

## Canonical post-v1.1 execution order

```text
V12-02
→ V11-06
→ V12-03
→ V12-04
→ V12-PERF
```

This sequence constrains admission precedence only; it is not a release promise, assignment, or authorization to start work. The completed `BACKLOG-H0` governance gate, V11-08 behavioral Tkinter coverage, and V12-01 final-name collision protection (issue #25) establish the remaining order but are no longer active or schedulable roadmap items. **V12-02 is the next admissible implementation unit**; no later unit starts automatically. V12-02 settles core workflow semantics after V12-01 settled final-output data safety. V11-06 can then qualify real OCR in a controlled environment. V12-03 resolves product capability ambiguity before any new format work, V12-04 addresses page-aware rendering only after its contract and fixtures exist, and V12-PERF remains benchmark-gated. This order changes only when repository evidence proves a concrete dependency that requires it.

## Active deferred v1.1 unit

This unit carries an open issue and was explicitly **not** part of the 1.1.0 release gate. The published 1.1.0 release does not depend on it.

- **V11-06 — controlled real-OCR qualification** (issue #10, priority P1 conditional). Provision a reproducible Tesseract/Poppler/`eng` environment, freeze high-contrast image and image-only PDF fixtures with known text and hashes, assert normalized real tokens, and retain a native-text PDF case. This unit does not change OCR production behavior or claim cross-platform, multilingual, or accuracy-benchmark certification. The deterministic mocked V11-05 coverage remains the only OCR qualification shipped in 1.1.0; see [OCR](OCR.md).

## V12 backlog units

### V12-02 — Aggregate workflow semantic hardening

- **Problem:** Workflow compilation must describe behavior the aggregate runtime actually performs, including the disposition of preceding enabled steps and compatibility between aggregate input types and supplied inputs.
- **Existing evidence:** `compile_workflow` currently requires an aggregate to be the only enabled step, while `BatchProcessor` has a dedicated `pdf_merge` path that consumes the original input list. Focused workflow and aggregate-lifecycle tests cover predecessor rejection, multiple aggregates, empty input, stop/finalize boundaries, and invalid PDFs. The compiler does not itself derive concrete input types because it receives a workflow rather than an input set.
- **Risk:** P1 correctness. A compiler/runtime mismatch can accept a workflow whose preceding transformations never run or whose inputs are incompatible, producing misleading success or late failures.
- **Priority:** P1 correctness.
- **Scope:** Define the supported aggregate composition contract, then make compiler, preflight, and runtime agree. Either preserve aggregate-only execution with explicit input admissibility at the correct boundary, or separately authorize composed predecessors and implement their outputs as aggregate inputs.
- **Explicit non-goals:** New aggregate operation types, implicit conversion, silent skipping of steps, broad workflow-engine redesign, or UI redesign unrelated to expressing the chosen contract.
- **Dependencies:** The V11-02 aggregate lifecycle and V12-01 final-output ownership. It precedes V11-06 so later qualification runs use settled workflow semantics.
- **Acceptance criteria:** Every workflow accepted by compilation has one unambiguous runtime meaning. Enabled predecessors are either rejected with actionable errors or demonstrably executed in order. Aggregate input incompatibility is rejected before finalization, disabled steps remain inert, and empty/stop/failure result accounting remains truthful.
- **Test strategy:** Extend the compile matrix across disabled/enabled predecessors, compatible/incompatible types, multiple aggregates, and aggregate position. Pair each accepted shape with processor integration tests and preserve event-controlled lifecycle regressions without sleeps.
- **Documentation impact:** Update [Workflows](WORKFLOWS.md), [Operations](OPERATIONS.md), [Security model](SECURITY_MODEL.md), and [Limitations](LIMITATIONS.md) to state only the selected, tested semantic contract.

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
