╔══════════════════════════════════════════════════════════════════════════════╗
║                  BATCHSTUDIO ARCHITECTURE - REALISTIC VIEW                    ║
║                         (Updated: 24 February 2026)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE LAYER                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    Tkinter-based GUI (4 Tabs)                         │  │
│  │                                                                      │  │
│  │  📁 Input Tab         🔧 Workflow Tab     ▶️ Run Tab     📊 Logs Tab │  │
│  │  - File selection     - Template list     - Execution     - Results  │  │
│  │  - Basic list view    - Step config       - Workers       - Errors   │  │
│  │  - File counter       - Save/Load         - Progress      - Export   │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                            ↓ (Direct calls)                                │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────────────┐
│                         CORE LOGIC LAYER                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                   BatchProcessor (ThreadPool)                        │  │
│  │  - ThreadPoolExecutor (1-16 workers)                                │  │
│  │  - Progress callbacks                                               │  │
│  │  - Statistics tracking                                              │  │
│  │  - Session management pentru PDF merge                              │  │
│  │  - Error handling & recovery                                        │  │
│  └──────────────────────────┬──────────────────────────────────────────┘  │
│                             │                                              │
│  ┌──────────────────────────▼──────────────────────────────────────────┐  │
│  │                   WorkflowManager (JSON)                             │  │
│  │  - Load/Save workflows                                              │  │
│  │  - Template system (20+ templates)                                  │  │
│  │  - Step validation                                                  │  │
│  │  - Export/Import                                                    │  │
│  └──────────────────────────┬──────────────────────────────────────────┘  │
│                             │                                              │
│  ┌──────────────────────────▼──────────────────────────────────────────┐  │
│  │                  OperationRegistry                                   │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │  │
│  │  │  Image Ops   │  │   PDF Ops    │  │   CSV Ops    │            │  │
│  │  │  - Resize    │  │  - Merge*    │  │  - Filter    │            │  │
│  │  │  - Convert   │  │  - Watermark │  │              │            │  │
│  │  │  - Filter    │  │              │  │              │            │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │  │
│  │  ┌─────────────────────────────────────────────────────────┐      │  │
│  │  │           OCR Operations (Optional)                     │      │  │
│  │  │  - OCR Image, OCR PDF, Batch OCR                        │      │  │
│  │  │  (Requires pytesseract, pdf2image, Tesseract)           │      │  │
│  │  └─────────────────────────────────────────────────────────┘      │  │
│  │  ┌─────────────────────────────────────────────────────────┐      │  │
│  │  │         File Operations                                 │      │  │
│  │  │  - File Rename (Thread-safe counter)                    │      │  │
│  │  └─────────────────────────────────────────────────────────┘      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────────────┐
│                         SECURITY & VALIDATION                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │              Input Validation Layer                                  │  │
│  │  - Path traversal detection (.. detection)                          │  │
│  │  - File size limits (500MB max)                                     │  │
│  │  - Extension whitelist (.jpg, .png, .pdf, .csv, etc.)               │  │
│  │  - Output directory write permissions                               │  │
│  │  - File existence validation                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────────────┐
│                         OUTPUT & REPORTING LAYER                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  Processed Files │  │  HTML Reports    │  │  CSV Reports     │        │
│  │  - Temp files    │  │  - Stats cards   │  │  - Raw data      │        │
│  │  - Final output  │  │  - File list     │  │  - Timestamps    │        │
│  │  - Cleanup       │  │  - Error log     │  │  - Status        │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
└────────────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════════════════════╗
║                          DATA FLOW (Realistic)                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Input Files → Validation → Workflow Load → Operation Registry → Process   ║
║       ↓              ↓            ↓                ↓              ↓          ║
║  File List    Security Check   Steps        Operation Init     ThreadPool  ║
║                                                                              ║
║  Results ← Stats Tracking ← Error Handling ← Temp Cleanup ← Output Gen     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                         KEY COMPONENTS (Actual)                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  main.py              → Entry point, Tkinter root window                    ║
║  core/processor.py    → BatchProcessor with ThreadPoolExecutor              ║
║  core/workflow.py     → Workflow, WorkflowManager, WorkflowTemplates        ║
║  core/operations.py   → OperationRegistry + 10 operation classes            ║
║  core/settings.py     → Settings management (window geometry, theme)        ║
║  ui/main_window.py    → MainWindow with 4 tabs                              ║
║  ui/input_panel.py    → File selection panel                                ║
║  ui/workflow_panel.py → Workflow configuration panel                        ║
║  ui/run_panel.py      → Execution controls and progress                     ║
║  ui/logs_panel.py     → Results and reports panel                           ║
║  workflows/*.json     → Saved workflows (generated at runtime)              ║
║  tests/*.py           → Unit tests (partial coverage)                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                        THREADING MODEL (Current)                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Main Thread (UI)                                                          ║
║       │                                                                      ║
║       ├──→ Worker Thread 1 → Process File 1                               ║
║       ├──→ Worker Thread 2 → Process File 2                               ║
║       ├──→ Worker Thread 3 → Process File 3                               ║
║       └──→ Worker Thread 4 → Process File 4                               ║
║                                                                              ║
║  Note: ThreadPoolExecutor with max_workers (1-16)                          ║
║  Limitation: GIL restricts true parallelism for CPU-bound ops              ║
║  Future: Consider ProcessPoolExecutor for v1.2.0                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                    PDF MERGE FIX (v1.0.1) - Technical Details                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Problemă Inițială:                                                          ║
║  - Instance-level state: self.accumulated_pdfs = []                         ║
║  - Nu funcționa în ThreadPoolExecutor (fiecare thread are instanță proprie) ║
║  - Nu era thread-safe                                                       ║
║                                                                              ║
║  Soluție Implementată:                                                       ║
║  - Class-level session management                                           ║
║  - _merge_sessions = {session_id: {'files': [...]}}                         ║
║  - _session_lock = threading.Lock() pentru thread-safety                    ║
║  - Fiecare batch are session_id unic                                        ║
║  - Two-step process: accumulation + finalize                                ║
║                                                                              ║
║  Flow:                                                                       ║
║  1. Initialize session: PDFMergeOperation.initialize_batch()                ║
║  2. For each file: operation.execute(file, temp_output)                     ║
║     → Copy to temp dir, track in session                                    ║
║  3. Final step: operation.execute(..., finalize=True)                       ║
║     → Merge all tracked files, cleanup                                      ║
║                                                                              ║
║  Benefits:                                                                   ║
║  ✅ Thread-safe accumulation                                                ║
║  ✅ Suport pentru multiple sesiuni simultane                                ║
║  ✅ Cleanup automat al fișierelor temporare                                 ║
║  ✅ Raportare detaliată (număr fișiere, dimensiune)                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                        SECURITY ARCHITECTURE                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Input Layer                                                                 ║
║       │                                                                      ║
║       ├─→ Path Traversal Detection (block "../")                           ║
║       ├─→ File Size Limit (500MB max)                                      ║
║       ├─→ Extension Whitelist (.jpg, .png, .pdf, .csv, .xlsx, etc.)        ║
║       └─→ File Existence Check                                             ║
║                                                                              ║
║  Processing Layer                                                            ║
║       │                                                                      ║
║       ├─→ Operation Validation (can this op handle this file?)             ║
║       ├─→ Temp File Isolation (unique names per thread)                    ║
║       └─→ Error Isolation (one file fails, others continue)                ║
║                                                                              ║
║  Output Layer                                                                ║
║       │                                                                      ║
║       ├─→ Directory Write Permission Check                                 ║
║       ├─→ Output Path Sanitization                                         ║
║       └─→ Cleanup on Error (remove temp files)                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                    PERFORMANCE CHARACTERISTICS                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Benchmarks (Windows 11, Python 3.10, i7-10700K, 32GB RAM):                ║
║                                                                              ║
║  Operation          │ File Size │ Duration  │ Memory    │ Workers          ║
║  ───────────────────┼───────────┼───────────┼───────────┼───────────────── ║
║  Image Resize       │ 5MB JPG   │ 0.1-0.3s  │ ~50MB     │ 4                ║
║  Image Convert      │ 5MB PNG   │ 0.2-0.4s  │ ~50MB     │ 4                ║
║  PDF Watermark      │ 2MB PDF   │ 0.3-0.6s  │ ~30MB     │ 4                ║
║  PDF Merge (5 files)│ 10MB total│ 1.2s      │ ~100MB    │ 1 (sequential)   ║
║  CSV Filter         │ 1MB CSV   │ 0.05-0.1s │ ~20MB     │ 4                ║
║  OCR (1 page)       │ 300 DPI   │ 2-5s      │ ~100MB    │ 2                ║
║                                                                              ║
║  Scaling:                                                                    ║
║  - 100 files:  ~10-30s processing time                                      ║
║  - 1000 files: ~2-5 minutes processing time                                 ║
║  - Memory usage scales linearly with file count                            ║
║                                                                              ║
║  Recommendations:                                                            ║
║  - Max 1000 files per batch for stability                                  ║
║  - Use 4-8 workers for optimal performance                                 ║
║  - For OCR: max 2-4 workers (memory intensive)                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                          TECHNICAL DEBT & LIMITATIONS                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  HIGH PRIORITY:                                                              ║
║  1. PDF Merge Session Cleanup                                              ║
║     - Session data poate rămâne dacă procesarea eșuează                    ║
║     - Soluție: Implementare timeout și cleanup on error                    ║
║                                                                              ║
║  2. Workflow Validation la Runtime                                          ║
║     - Operații inexistente nu sunt detectate până la procesare             ║
║     - Soluție: Validare workflow la încărcare                              ║
║                                                                              ║
║  3. OCR Dependencies Detection                                              ║
║     - Operațiile OCR apar în UI chiar dacă dependencies lipsesc            ║
║     - Soluție: Disable operații dacă dependencies nu sunt disponibile      ║
║                                                                              ║
║  MEDIUM PRIORITY:                                                           ║
║  4. Memory Management pentru OCR                                            ║
║     - OCRBatchOperation poate consuma multă memorie                        ║
║     - Soluție: Limită buffer size și clear periodic                        ║
║                                                                              ║
║  5. Logging Framework                                                       ║
║     - Folosește print() în loc de logging module                           ║
║     - Soluție: Implementare logging cu levels                              ║
║                                                                              ║
║  LOW PRIORITY:                                                              ║
║  6. Code Documentation                                                      ║
║     - Lipsesc docstrings în multe funcții                                  ║
║     - Soluție: Adăugare docstrings și type hints                           ║
║                                                                              ║
║  7. Test Coverage                                                           ║
║     - Doar 40% coverage, lipsesc teste de integrare                        ║
║     - Soluție: Adăugare teste pentru operații și UI                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                         FUTURE ARCHITECTURE (v2.0)                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Considerații pentru v2.0:                                                   ║
║                                                                              ║
║  1. GUI Framework: Tkinter → PyQt/PySide                                   ║
║     - Motivație: UI modern, drag-and-drop nativ, mai multe widgets         ║
║     - Cost: Creștere dependencies, learning curve                          ║
║                                                                              ║
║  2. Processing Engine: Threading → Multiprocessing                         ║
║     - Motivație: Evitare GIL, utilizare multi-core reală                   ║
║     - Cost: Complexitate IPC, shared memory management                     ║
║                                                                              ║
║  3. Storage: JSON → SQLite                                                 ║
║     - Motivație: Query capabilities, performance la scale                  ║
║     - Cost: Database management, migrations                                ║
║                                                                              ║
║  4. Plugin System: Manual → Dynamic Loading                                ║
║     - Motivație: Ușurință extensibilitate, plugin marketplace              ║
║     - Cost: Security considerations, API stability                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

---

Document întreținut de: BatchStudio Team
Ultima actualizare: 24 Februarie 2026
Vezi PROJECT_TRACKING.md pentru detalii complete
