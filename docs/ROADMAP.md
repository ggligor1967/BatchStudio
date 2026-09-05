# Roadmap

This is the only canonical location for unimplemented work. Items are candidates, not promises, dates, or assignments. A candidate becomes release scope only through an approved issue and must satisfy tests, documentation, packaging, and release evidence.

## Deferred v1.1 units

These units carry open issues and are explicitly **not** part of the 1.1.0 release gate. 1.1.0 does not depend on either.

- **V11-06 — controlled real-OCR qualification** (issue #10, priority P1 *conditional*). A dedicated controlled workflow that provisions Tesseract, Poppler, and explicit `eng` language data, freezes a high-contrast image fixture and an image-only PDF fixture with known text and hashes, and asserts real recognized tokens plus a native-text PDF case. It was not admitted to 1.1.0 scope. 1.1.0 ships only the deterministic mocked OCR capability and contract coverage completed in V11-05. This item does not reopen or change OCR production behavior; see [OCR](OCR.md).
- **V11-08 — minimal behavioral Tkinter flow coverage** (issue #12). **P2 / STRETCH, NON-BLOCKING FOR v1.1.** One successful four-tab flow plus failure propagation and main-thread callback behavior, built on the existing pytest and Tkinter setup with isolated settings and dialogs. Deferred if it would require substantial UI redesign; it must not delay release closure.

## Other evidence-driven candidates

- Make collision protection cover operation-specific final suffix/name changes, not only the processor's initially allocated path.
- Clarify or tighten aggregate workflow compilation so preceding steps and aggregate input types cannot imply behavior the aggregate execution path does not perform.
- Decide whether Excel and structured-text selection should gain operations or be narrowed in the picker.
- Replace fixed PDF-watermark layout with page-aware placement only after defined rendering tests exist.

Performance work requires a reproducible benchmark definition under DOC-07 before any numeric claim is accepted.
