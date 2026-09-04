# CLAUDE.md — BatchStudio (Batch Processing Studio)

> Audience: AI coding agents (Claude / Gemini / Codex) and human maintainers.
> Goal: provide an accurate, high-signal technical brief + constraints to implement changes safely.

## 1) Project Snapshot

**BatchStudio** is a **desktop GUI** application for **batch file processing** using **configurable workflows**. It supports images, PDFs, CSV/Excel, and optional OCR. The UI is **Tkinter** with **4 tabs** (Input / Workflow / Run / Logs). Processing is executed via **ThreadPoolExecutor** with progress callbacks and reporting (HTML + CSV). Current release line is **v1.0.1 (beta)**.

### Primary goals
- Batch processing of many files via reusable **workflow templates** and custom workflows.
- Safe execution: input validation, extension whitelist, size limits, output permission checks.
- Useful feedback: progress, per-file results, error isolation, reports.

### Explicit non-goals (for current versions)
- “Modern” GUI overhaul (Tkinter → PyQt/PySide is *future*).
- Plugin marketplace / full plugin UI (API exists; UI is planned).
- True parallel CPU-bound scaling (GIL limits; multiprocessing is planned).
- Cloud/scheduled/email features (planned later; not in v1.x baseline).

---

## 2) Tech Stack & Runtime

- **Language:** Python **3.10+**
- **GUI:** Tkinter
- **Concurrency:** `concurrent.futures.ThreadPoolExecutor` (1–16 workers)
- **Image processing:** Pillow (PIL)
- **PDF:** pypdf (manipulation), ReportLab (PDF generation for watermark/reporting)
- **Data:** pandas (CSV/XLSX)
- **Reports:** HTML + CSV output
- **Optional OCR:** `pytesseract`, `pdf2image`, and system **Tesseract OCR** installation

### Platforms
- Works on Windows/macOS/Linux (Tkinter-based). Windows is a primary target.

---

## 3) Repository Layout (expected / canonical)

- `main.py` — entry point, Tkinter root window
- `ui/`
  - `main_window.py` — app shell + 4 tabs
  - `input_panel.py` — file selection (no drag-drop yet)
  - `workflow_panel.py` — template selection + step configuration
  - `run_panel.py` — execution controls, workers, progress
  - `logs_panel.py` — results table, error list, report export
- `core/`
  - `processor.py` — `BatchProcessor` (ThreadPool), progress callbacks, stats
  - `workflow.py` — `Workflow`, `WorkflowManager`, templates (20+)
  - `operations/` — `OperationRegistry`, typed operation contracts, and operation implementations
  - `settings.py` — UI settings (window geometry, theme)
- `workflows/*.json` — saved workflows (generated at runtime)
- `tests/*.py` — partial unit tests (~40% coverage baseline)

If adding new modules, keep them under `core/` (logic) or `ui/` (Tkinter views). Avoid circular imports.

---

## 4) Architecture (How the app actually runs)

### UI layer (Tkinter, 4 tabs)
- Input Tab: add files/folders, list view, counters
- Workflow Tab: pick template, configure steps, save/load workflow JSON
- Run Tab: output folder, naming pattern, worker count, start/stop, progress
- Logs Tab: per-file results, errors, export report (HTML/CSV)

### Core layer
1. **Validation** (paths, size limits, extension whitelist, output permissions)
2. **Workflow load** (`WorkflowManager`) — template or JSON
3. **Operation resolution** (`OperationRegistry`) — map step → operation class
4. **Processing** (`BatchProcessor`) — ThreadPool workers, per-file execution, progress callbacks
5. **Reporting** — structured results → HTML + CSV

### Threading model
- Tkinter runs on the main thread.
- Work is executed in a ThreadPool (1–16 workers).
- UI updates must be scheduled safely (Tkinter is not thread-safe).
- GIL note: CPU-heavy operations won’t scale linearly with more threads.

---

## 5) Workflows: Data Model & Constraints

Workflows are stored as JSON and represent a list of steps:
- Each step references an **operation id** registered in `OperationRegistry`.
- Each step includes configuration for that operation (schema varies per op).

**Agent rule:** any changes to workflow format must be backward compatible or explicitly versioned with a migration strategy.

### Templates
- 20+ templates exist across categories: Images, Social Media formats, E-commerce, PDF, OCR, Data cleaning/anonymization.

---

## 6) Operations (Current Baseline)

### Implemented operation families
**Images**
- Resize (with aspect-ratio option)
- Convert (PNG/JPEG/WEBP/BMP/TIFF)
- Filter (blur, sharpen, grayscale, emboss, etc.)

**PDF**
- Merge (explicit **aggregate/batch** workflow step; see §7)
- Watermark (text-based)

**Data**
- CSV filter (condition-based row filtering)

**File**
- Rename (pattern-based, thread-safe counter)

**OCR (Optional; depends on Tesseract + deps)**
- Image → Text (OCR)
- PDF → Text (native or OCR)
- Batch OCR (multiple files, optional combined output)

---

## 7) PDF Merge: Critical Implementation Notes (v1.0.1)

A prior bug made implicit session-based PDF merge fail under multithreaded batch processing.

**Current design (v1.0.1): explicit aggregate lifecycle**
- `begin(output_path)` initializes one batch merge target
- `consume(file_path)` appends validated input PDFs to the aggregate writer
- `finalize()` emits the merged output exactly once

**Constraints**
- Aggregate operations must be the last workflow step
- Merge output filename is validated through the safe output resolver
- Dry-run must not write temporary or final PDF files

**Agent rule:** treat PDF merge code paths as high-risk; keep regression coverage for aggregate behavior.

---

## 8) Security & Validation (Must Not Regress)

Validation layer requirements:
- Block path traversal (`..` / suspicious paths).
- Enforce file size limit: **500MB max**.
- Enforce extension whitelist (images, pdf, csv, xlsx, etc.).
- Validate file existence.
- Validate output directory is writable and paths are sanitized.
- Error isolation: one file failing must not stop the entire batch unless explicitly configured.

**Agent rule:** any new operation must declare:
- what extensions it supports,
- size/memory concerns,
- safe temp-file handling,
- deterministic output naming.

---

## 9) Performance Constraints & Guidance

Empirical guidance (baseline target behavior):
- Recommended batch size: **≤ 1000 files** for stability (memory scales with file count metadata).
- Typical worker counts:
  - Most operations: **4–8** workers
  - OCR: **2–4** workers (memory heavy)
  - PDF merge: effectively sequential at finalize stage

**Agent rule:** do not increase default workers or memory usage without measuring and documenting impact.

---

## 10) Known Issues / Technical Debt (High Signal)

High priority:
1. PDF merge session cleanup can leak session data on failure.
2. Workflow validation is too late (invalid operation ids may be detected only at runtime).
3. OCR operations appear in UI even when OCR deps are missing (should hide/disable).

Medium:
4. OCR memory usage management (buffering / periodic cleanup).
5. Logging uses `print()` in places instead of `logging` module.

Low:
6. Missing docstrings / type hints in multiple modules.
7. Test coverage incomplete; needs integration tests (core + workflow + operations).

---

## 11) Roadmap Alignment (Do not implement out-of-scope)

Planned milestones:
- **v1.1.0 (March 2026):** drag-and-drop input, thumbnails/preview, plugin manager UI, config file support, better error messages.
- **v1.2.0 (Q2 2026):** batch chunking (>1000), resume capability, real progress bars, memory optimization, optional multiprocessing for CPU-bound tasks, single-step PDF merge.
- **v1.3.0 (Q3 2026):** video/audio ops, cloud storage, scheduling, email notifications, SQLite integration.

**Agent rule:** changes must target the current milestone unless explicitly authorized.

---

## 12) Developer Setup (Local)

### Install
```bash
pip install -r requirements.txt Agent rule: if you cannot run tests in your environment, state so explicitly and provide a minimal reproducible test plan.

13) Coding Standards (Required)
General

Prefer small, reviewable diffs.

Keep UI and core logic separated.

Add type hints for new/modified public APIs where reasonable.

Use logging for new logging; do not add new print() calls.

Ensure operations are deterministic and thread-safe.

Error handling

Return structured result objects/dicts consistently (success flag, message, metadata).

Never crash the UI thread on per-file failures.

Always clean up temp files on success and best-effort on failure.

Security

Never allow arbitrary file writes outside user-selected output directory.

Treat filenames and user-provided patterns as untrusted input.

Do not introduce shell execution features.

14) Contribution / GitHub Hygiene

Use Semantic Versioning and Keep a Changelog conventions.

Update CHANGELOG.md for user-visible changes.

Add/adjust tests for bug fixes and risky refactors (PDF/OCR/registry/worker logic).

PRs should include:

summary,

screenshots if UI changes,

test results (or explicit statement if not executed),

risk assessment.

15) AI Agent Operating Rules (Truth & Quality)

You must follow these operating rules for any task on this repo:

No false claims. Do not claim commands/tests passed unless you actually executed them.

Be explicit about verification. Tag any verification as:

Executed

Not Executed (reason)

Unverified

No fabricated artifacts. Do not invent files, links, outputs, or APIs.

Plan before refactor. For concurrency-sensitive code (PDF merge, workers, UI callbacks), propose a safe sequence:

add tests → implement minimal change → validate behavior → expand.

Respect scope. Do not add roadmap features unless requested.

16) Quick Pointers for New Work

When adding a new operation:

Implement operation class in core/operations.py (or a dedicated module imported there).

Register it in OperationRegistry.

Provide a config schema + validation rules.

Add at least:

unit tests for success/failure paths,

one sample workflow template if broadly useful,

documentation in README/CHANGELOG if user-facing.

When touching ThreadPool / UI responsiveness:

Ensure Tkinter updates are marshaled to the main thread.

Avoid long blocking operations in UI callbacks.

Keep per-file work isolated and exception-safe.

End of CLAUDE.md