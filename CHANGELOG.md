# Changelog

All notable changes to BatchStudio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Split `core.operations` into a package with typed operation contracts and per-domain modules
- Replaced PyPDF2 with pypdf across runtime code, tests, and packaging
- Redesigned PDF merge as an explicit aggregate batch operation with begin/consume/finalize lifecycle
- Consolidated runtime dependencies in `pyproject.toml` and simplified `setup.py` to a packaging shim

### Fixed
- Required successful operations to report their actual output path
- Fixed rename integration in per-file processing workflows
- Made dry-run side-effect free for file operations and batch runs
- Added canonical safe output path resolution and duplicate-basename allocation
- Escaped HTML report content and neutralized spreadsheet formulas in CSV reports
- Moved worker-thread progress/log widget mutations onto the Tk main thread
- Added workflow compilation checks for unknown operations, invalid configs, type mismatches, and missing OCR capability
- Fixed mutable settings defaults for list-valued preferences

## [1.0.0] - 2024-11-25

### Added
- Initial release of BatchStudio
- Multi-format file support (images, PDFs, CSVs)
- Drag-and-drop workflow builder interface
- Multi-threaded batch processing with configurable workers
- Real-time progress tracking with detailed logging
- Pre-built workflow templates:
  - Image Resizer
  - Image Format Converter
  - PDF Watermarker
  - CSV Data Cleaner
  - Batch File Renamer
  - Photo Optimizer
- Image processing operations:
  - Resize with aspect ratio preservation
  - Format conversion (PNG, JPEG, WEBP, BMP, TIFF)
  - Filters (blur, sharpen, grayscale, etc.)
  - Brightness and contrast adjustment
- PDF operations:
  - Merge multiple PDFs
  - Add watermarks
- CSV operations:
  - Filter rows by conditions
- General operations:
  - Batch file renaming with patterns
- HTML and CSV report generation
- Dry run mode for preview
- Modern UI with light/dark mode support
- Workflow save/load functionality (JSON format)
- Keyboard shortcuts for common actions
- Easter eggs (confetti animation, motivational quotes, dev console)
- Comprehensive documentation (README, QUICKSTART, ARCHITECTURE)
- Installation verification script
- Cross-platform support (Windows, macOS, Linux)

### Features
- Process up to 10,000+ files efficiently
- Configurable naming patterns with placeholders
- Error recovery and detailed error logging
- Pause/resume capability during processing
- File validation before processing
- Preview thumbnails for images
- Statistics display (file count, total size)
- Extensible plugin system for custom operations

### Documentation
- Complete README.md with usage examples
- QUICKSTART.md for rapid onboarding
- ARCHITECTURE.txt with system design
- Inline code documentation
- Setup script with dependency verification

## [Unreleased]

### Planned Features
- Video file processing
- Audio file operations
- Cloud storage integration (Google Drive, Dropbox)
- Scheduled batch processing
- Email notifications
- Additional pre-built templates
- Plugin marketplace
- Mobile companion app
- AI-powered file organization
- Batch preview thumbnails
- Undo/redo functionality
- Advanced scripting support
- Database operations
- FTP/SFTP integration
- Compression/archive operations
- Metadata editing
- OCR capabilities
- More image filters and effects

---

[1.0.0]: https://github.com/yourusername/batchstudio/releases/tag/v1.0.0
