# 🎨 BatchStudio - Batch Processing Studio

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Status](https://img.shields.io/badge/status-beta-yellow.svg)

**A functional desktop application for batch file processing with workflow automation**

Process images, PDFs, and CSV files through customizable workflows!

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Examples](#examples) • [Known Issues](#known-issues)

</div>

---

## ⚠️ Important Notice

This is a **beta release** (v1.0.1). While core functionality is operational, some features documented in the original README are not yet implemented. Please see [Known Issues](#known-issues) for details.

For detailed project tracking, see [PROJECT_TRACKING.md](PROJECT_TRACKING.md)

---

## ✨ Implemented Features

### ✅ Fully Functional
- 📁 **Multi-Format Support**: Images (PNG, JPG, WEBP, BMP, TIFF), PDFs, CSVs, Excel files
- ⚡ **Multi-threaded Processing**: Configurable parallel workers (1-16)
- 📊 **Progress Tracking**: Real-time status updates with detailed logging
- 🎯 **Pre-built Templates**: 20+ workflow templates for common tasks
- 📈 **Comprehensive Reports**: HTML and CSV reports with statistics
- 🔍 **Dry Run Mode**: Preview changes before executing
- 🎨 **Dark Mode**: Toggle between light and dark themes
- 💾 **Save & Load Workflows**: JSON-based workflow persistence
- 🔤 **OCR Support**: Text extraction from images and PDFs (requires Tesseract)

### ⚠️ Partially Implemented
- 🔧 **Workflow Builder**: List-based workflow configuration (drag-and-drop not yet implemented)
- 🔌 **Plugin System**: API exists for custom operations, but no UI for management

### ❌ Not Yet Implemented
- 🖱️ **Drag-and-drop interface**: Planned for v1.2.0
- 👁️ **File preview**: Currently shows only file list, no thumbnails
- 🔌 **Plugin manager UI**: Manual registry modification required

---

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Quick Install

```bash
# Clone or download the repository
cd BatchStudio

# Install core dependencies
pip install -r requirements.txt

# Optional: Install OCR dependencies if you need text extraction
pip install pytesseract pdf2image

# Install Tesseract OCR for your OS:
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr
# macOS: brew install tesseract

# Run the application
python main.py
```

### Platform-Specific Notes

**Windows:**
```bash
pip install -r requirements.txt
python main.py
```

**macOS/Linux:**
```bash
pip3 install -r requirements.txt
python3 main.py
```

---

## 🚀 Quick Start

1. **Add Files**:
   - Go to the "Input Files" tab
   - Click "Add Files" or "Add Folder" to select your files
   - Review the file list

2. **Build Workflow**:
   - Switch to the "Workflow" tab
   - Select a template or create a custom workflow
   - Configure each operation's parameters
   - Save your workflow for future use

3. **Run Processing**:
   - Go to the "Run" tab
   - Set output directory and naming pattern
   - Choose number of parallel workers (4-8 recommended)
   - Click "Start Processing"

4. **View Results**:
   - Check the "Logs" tab for detailed results
   - Export reports in HTML or CSV format
   - Review any errors and statistics

---

## 📖 Usage Examples

### Example 1: Bulk Image Resizing

```bash
# Using the application UI:
1. Add 100 photos from your folder
2. Select "Image Resizer" template
3. Configure: width=1920, height=1080, maintain_aspect=True
4. Set output to "resized_photos" folder
5. Run with 4-8 workers
```

### Example 2: PDF Watermarking

```bash
# Using the application UI:
1. Select multiple PDF files
2. Choose "PDF Watermarker" template
3. Set watermark text: "CONFIDENTIAL"
4. Process all files
```

### Example 3: Extract Text from Scanned Documents (OCR)

**Important:** Requires Tesseract OCR installation

```bash
# Using the application UI:
1. Add scanned images or PDFs
2. Select "Document Scanner OCR" template
3. Choose language (e.g., 'eng' for English, 'ron' for Romanian)
4. Run OCR extraction
5. Text files will be created alongside originals
```

### Example 4: Batch File Renaming

```bash
# Using the application UI:
1. Add files to rename
2. Select "Batch File Renamer" template
3. Set pattern: "IMG_{counter}_{original}"
4. Process to rename all files
```

### Example 5: Merge Multiple PDFs

**Note:** PDF merge requires a two-step process

```bash
# Using the application UI:
1. Add all PDFs to merge
2. Add PDF Merge operation (non-finalize) to workflow
3. Run processing (collects all PDFs)
4. Add final PDF Merge operation (finalize=True)
5. Run again to create merged file
```

---

## 🔧 Available Operations

### Image Operations
- **Image Resize**: Scale images to specific dimensions
- **Image Convert**: Change format (PNG, JPEG, WEBP, BMP, TIFF)
- **Image Filter**: Apply filters (blur, sharpen, grayscale, etc.)

### PDF Operations
- **PDF Merge**: Merge multiple PDFs into one (see example above)
- **PDF Watermark**: Add text watermarks

### CSV Operations
- **CSV Filter**: Filter rows based on conditions

### File Operations
- **File Rename**: Batch rename with patterns

### OCR Operations (requires Tesseract)
- **OCR Image to Text**: Extract text from images
- **PDF to Text**: Extract text from PDFs (native or OCR)
- **Batch OCR**: Process multiple files with optional combined output

---

## 🎯 Pre-built Templates

BatchStudio includes 20+ templates organized by category:

### Images
- Image Resizer, Image Format Converter, Photo Optimizer
- Social Media: Instagram Post, Facebook Cover, YouTube Thumbnail
- E-commerce: Product Photos
- Creative: Vintage Photo Effect
- Print: Print-Ready Images, Mobile Wallpaper

### PDF & Documents
- PDF Watermarker, Document Archival

### Data
- CSV Data Cleaner, CSV Data Anonymizer

### OCR
- Document Scanner OCR, Invoice Text Extractor
- Book Page Digitizer, Multilingual OCR

---

## ⚙️ Configuration

### Naming Patterns

Use these placeholders in output naming:

- `{original}`: Original filename (without extension)
- `{timestamp}`: Unix timestamp
- `{counter}`: Sequential number (1, 2, 3...)

Examples:
- `{original}_processed` → `photo_processed.jpg`
- `IMG_{counter:03d}` → `IMG_001.jpg`, `IMG_002.jpg`
- `{original}_{timestamp}` → `photo_1234567890.jpg`

### Parallel Workers

- **1-2 workers**: For I/O intensive operations (network, disk)
- **4-8 workers**: Optimal for most tasks (recommended)
- **8-16 workers**: For CPU-intensive operations on powerful machines

---

## 🔍 Known Issues and Limitations

### Current Limitations (v1.0.1)

1. **Drag-and-Drop Not Implemented**
   - Status: Planned for v1.2.0
   - Workaround: Use file/folder selection dialogs

2. **No File Preview/Thumbnails**
   - Status: Planned for v1.2.0
   - Current: Shows only file list with names

3. **PDF Merge Requires Two Steps**
   - Status: Architecture limitation
   - Workaround: See Example 5 above
   - Fix: Planned workflow engine refactor for v1.3.0

4. **No Plugin Manager UI**
   - Status: Manual registry modification required
   - Guide: See [Extending BatchStudio](#extending-batchstudio)

5. **No Batch Resume**
   - Status: If processing stops, must restart from beginning
   - Workaround: Process files in smaller batches
   - Fix: Planned for v1.2.0

6. **Memory Usage for Large Batches**
   - Status: All file metadata loaded in memory
   - Workaround: Process max 1000 files at a time
   - Fix: Batch chunking planned for v1.2.0

### Recently Fixed (v1.0.1)

1. **PDF Merge Thread-Safety**
   - Issue: PDF merge failed in batch processing
   - Fix: Implemented session-based accumulation
   - Files: `core/operations.py`, `core/processor.py`

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** "Module not found" error
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**Issue:** OCR operations fail
```bash
# Solution: Install OCR dependencies
pip install pytesseract pdf2image

# And install Tesseract for your OS:
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr
# macOS: brew install tesseract
```

**Issue:** "No PDFs to merge" error
```bash
# Solution: Ensure you're using the two-step process
# 1. Collect PDFs (finalize=False)
# 2. Merge (finalize=True)
```

**Issue:** Slow processing
```bash
# Solution: Adjust parallel workers
# Try 4-8 workers for optimal performance
# Reduce if running on older hardware
```

**Issue:** Out of memory
```bash
# Solution: Process in smaller batches
# Process 100-500 files at a time instead of thousands
```

**Issue:** Permission denied
```bash
# Solution: Check file permissions
# Windows: Run as Administrator if needed
# Linux/macOS: chmod +x main.py
```

---

## 📊 Performance Tips

1. **Use appropriate workers**: Start with 4, adjust based on results
2. **Batch processing**: Process 100-1000 files at a time for optimal memory
3. **Dry run first**: Test with 5-10 files before processing thousands
4. **SSD vs HDD**: SSD significantly faster for I/O operations
5. **Close other apps**: Free up system resources
6. **OCR optimization**: Use grayscale preprocessing for faster OCR

---

## 🔌 Extending BatchStudio

### Creating Custom Operations

Create a new file `core/custom_operations.py`:

```python
from core.operations import Operation

class CustomOperation(Operation):
    def __init__(self, config=None):
        super().__init__(
            name="My Custom Operation",
            description="Does something awesome",
            config=config
        )

    def execute(self, file_path, output_path):
        # Your processing logic here
        return {'success': True, 'message': 'Processed!'}

    def validate(self, file_path):
        # Check if operation can process this file
        return True

    def get_config_schema(self):
        return {
            'param1': {'type': 'str', 'default': 'value', 'label': 'Parameter 1'}
        }
```

Register your operation in `core/operations.py`:

```python
from core.custom_operations import CustomOperation

# In OperationRegistry.__init__():
self.operations['custom_op'] = CustomOperation
```

### Custom Workflow Templates

Add to `core/workflow.py` in the `WorkflowTemplates` class:

```python
@staticmethod
def _my_custom_template() -> Workflow:
    workflow = Workflow(
        name="My Custom Workflow",
        description="Does something specific"
    )
    workflow.add_step('operation_id', {'config': 'value'})
    return workflow
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Check [PROJECT_TRACKING.md](PROJECT_TRACKING.md) for current issues
2. Fork the repository
3. Create a feature branch (`git checkout -b feature/amazing`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing`)
6. Open a Pull Request

**Important:** Please update tests and documentation for any new features.

---

## 📧 Support

- **Report bugs:** Create an issue on GitHub with steps to reproduce
- **Feature requests:** Open a discussion on GitHub
- **Questions:** Check documentation first, then open an issue

---

## 🌟 Credits

Built with:
- Python 3.10+
- Tkinter (GUI framework)
- Pillow (Image processing)
- Pandas (Data processing)
- ReportLab (PDF generation)
- PyPDF2 (PDF manipulation)
- Tesseract OCR (Optional text extraction)

---

## 🔮 Roadmap

### v1.1.0 (Planned - March 2026)
- [ ] Drag-and-drop file support
- [ ] File preview with thumbnails
- [ ] Plugin manager UI
- [ ] Improved error messages
- [ ] Configuration file support

### v1.2.0 (Planned - Q2 2026)
- [ ] Batch chunking for large file sets
- [ ] Resume capability for interrupted processing
- [ ] Real progress bars
- [ ] Memory usage optimization

### v1.3.0 (Planned - Q3 2026)
- [ ] Video processing operations
- [ ] Audio file operations
- [ ] Cloud storage integration (Google Drive, Dropbox)
- [ ] Scheduled batch processing

See [PROJECT_TRACKING.md](PROJECT_TRACKING.md) for detailed milestone planning.

---

<div align="center">

**Made with ❤️ by the BatchStudio Team**

[⬆ Back to top](#-batchstudio---batch-processing-studio)

</div>
