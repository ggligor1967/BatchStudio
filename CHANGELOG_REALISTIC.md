# Changelog

All notable changes to BatchStudio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2024-02-24

### Fixed
- **CRITICAL**: PDF Merge operation thread-safety issue (BUG-001)
  - Refactored PDFMergeOperation to use session-based accumulation
  - Implemented class-level session management with thread locking
  - Added automatic cleanup of temporary files
  - Now works correctly in batch processing with multiple workers
  - Files changed: `core/operations.py`, `core/processor.py`
- Fixed missing imports in `core/operations.py` (`tempfile`, `time`)
- Fixed syntax error in PDFMergeOperation class

### Added
- Session management methods for PDF merge operations
- Test scripts for PDF merge functionality (`test_pdf_merge_simple.py`)
- Detailed error reporting for PDF merge failures
- Project tracking documentation (`PROJECT_TRACKING.md`)
- Realistic architecture documentation (`ARCHITECTURE_REALISTIC.md`)

### Changed
- Updated PDF merge to provide detailed statistics (file count, total size)
- Improved error messages for missing OCR dependencies

### Known Issues
- PDF merge still requires two-step process (planned fix for v1.2.0)
- No automatic cleanup if batch processing fails mid-way

---

## [1.0.0] - 2024-11-25

### Added
- Initial beta release of BatchStudio
- Core batch processing engine with ThreadPoolExecutor
- Multi-format file support:
  - Images: PNG, JPG, JPEG, WEBP, BMP, TIFF, GIF
  - PDFs: PDF format with watermark support
  - Data: CSV, XLSX (Excel)
- **10 implemented operations:**
  - Image Resize (with aspect ratio preservation)
  - Image Convert (PNG, JPEG, WEBP, BMP, TIFF)
  - Image Filter (blur, sharpen, grayscale, emboss, etc.)
  - PDF Merge (with known limitations)
  - PDF Watermark (text-based)
  - CSV Filter (row filtering with conditions)
  - File Rename (pattern-based, thread-safe)
  - OCR Image to Text (requires Tesseract)
  - PDF to Text (native or OCR)
  - Batch OCR (multiple files with combined output)
- **20+ workflow templates** across categories:
  - Images: Resizer, Converter, Photo Optimizer
  - Social Media: Instagram, Facebook, YouTube thumbnails
  - E-commerce: Product photos
  - OCR: Document Scanner, Invoice Extractor, Book Digitizer
- Basic UI with 4 tabs (Input, Workflow, Run, Logs)
- Dark mode toggle
- HTML and CSV report generation
- Dry run mode for testing
- Workflow save/load (JSON format)
- Multi-threaded processing (1-16 workers)
- Progress tracking with status messages
- Keyboard shortcuts (Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Q)
- Security features:
  - Path traversal detection
  - File size limits (500MB)
  - Extension whitelist
  - Output directory validation
- Easter eggs (confetti animation, motivational quotes)

### Technical Details
- Python 3.10+ required
- Tkinter-based GUI
- ThreadPoolExecutor for parallel processing
- JSON-based workflow storage
- PIL/Pillow for image processing
- PyPDF2 for PDF manipulation
- ReportLab for PDF generation
- Pandas for CSV processing
- Optional: Tesseract OCR integration

### Known Issues (at release)
- PDF merge fails in batch processing (FIXED in v1.0.1)
- No drag-and-drop support (planned for v1.2.0)
- No file preview/thumbnails (planned for v1.2.0)
- Plugin system exists only at API level (no UI)
- No batch resume capability (planned for v1.2.0)
- Memory usage scales linearly with file count
- Test coverage ~40% (partial coverage of core functions)

### Removed from Original Scope
- Video processing operations (planned for v1.3.0)
- Audio file operations (planned for v1.3.0)
- Cloud storage integration (planned for v1.3.0)
- Scheduled batch processing (planned for v1.3.0)
- Email notifications (planned for v1.3.0)

---

## [Unreleased] - Roadmap

### v1.1.0 (Planned - March 2026)
#### Added
- Drag-and-drop file support in Input tab
- File preview with thumbnails
- Plugin manager UI
- Configuration file support (JSON/TOML)
- Improved error messages with suggestions

#### Fixed
- Workflow validation at load time
- OCR operations hidden when dependencies missing
- Memory cleanup for failed operations

#### Changed
- Settings moved from code to config file
- Enhanced UI feedback for long operations

### v1.2.0 (Planned - Q2 2026)
#### Added
- Batch chunking for large file sets (>1000 files)
- Resume capability for interrupted processing
- Real progress bars (replace text messages)
- Memory usage optimization
- Multiprocessing option for CPU-bound operations

#### Fixed
- PDF merge single-step process (eliminate finalize flag)
- Memory leaks in OCR operations

#### Changed
- Default workers adjusted based on operation type
- Improved error recovery mechanisms

### v1.3.0 (Planned - Q3 2026)
#### Added
- Video processing operations (resize, convert, extract frames)
- Audio file operations (convert, extract metadata)
- Cloud storage integration (Google Drive, Dropbox, S3)
- Scheduled batch processing (cron-like)
- Email notifications on completion
- Database operations (SQLite integration)

#### Fixed
- Scaling issues with 10,000+ files
- UI responsiveness during processing

---

## Release Notes Format

### Version Numbering
- **MAJOR.MINOR.PATCH** (e.g., 1.0.1)
- MAJOR: Breaking changes, major features
- MINOR: New features, improvements
- PATCH: Bug fixes, documentation

### Categories
- **Added**: New features
- **Changed**: Changes to existing features
- **Deprecated**: Features to be removed
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements

---

[1.0.1]: https://github.com/batchstudio/batchstudio/releases/tag/v1.0.1
[1.0.0]: https://github.com/batchstudio/batchstudio/releases/tag/v1.0.0
