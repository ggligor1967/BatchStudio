# 🎨 BatchStudio - Batch Processing Studio

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

**A powerful, user-friendly desktop application for batch file processing**

Process thousands of files with ease through customizable workflows!

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Examples](#examples) • [Extending](#extending)

</div>

---

## ✨ Features

- 📁 **Multi-Format Support**: Images (PNG, JPG, WEBP), PDFs, CSVs, Excel files, and more
- 🔧 **Workflow Builder**: Drag-and-drop interface to chain operations
- ⚡ **Multi-threaded Processing**: Utilize all CPU cores for maximum speed
- 📊 **Progress Tracking**: Real-time progress bars and detailed logging
- 🎯 **Pre-built Templates**: Quick start with common workflows
- 📈 **Comprehensive Reports**: HTML and CSV reports with statistics
- 🔍 **Dry Run Mode**: Preview changes before executing
- 🎨 **Modern UI**: Clean, intuitive interface with light/dark modes
- 💾 **Save & Share Workflows**: Export workflows as JSON files
- 🔌 **Extensible**: Easy plugin system for custom operations

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Quick Install

```bash
# Clone or download the repository
cd BatchStudio

# Install dependencies
pip install -r requirements.txt

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

## 🚀 Quick Start

1. **Add Files**: 
   - Go to the "Input Files" tab
   - Click "Add Files" or "Add Folder" to select your files
   - Preview files and check statistics

2. **Build Workflow**:
   - Switch to the "Workflow" tab
   - Select operations from the left panel
   - Add them to your workflow
   - Configure each operation
   - Save your workflow for future use

3. **Run Processing**:
   - Go to the "Run" tab
   - Set output directory and naming pattern
   - Choose number of parallel workers
   - Click "Start Processing"
   - Watch the magic happen! ✨

4. **View Results**:
   - Check the "Logs" tab for detailed results
   - Export reports in HTML or CSV format
   - Review any errors and statistics

## 📖 Usage Examples

### Example 1: Bulk Image Resizing

```
1. Add 100 photos from vacation folder
2. Use "Image Resizer" template
3. Configure: 1920x1080, maintain aspect ratio
4. Set output to "resized_photos" folder
5. Run batch → Get resized photos in seconds!
```

### Example 2: Photo Optimization for Web

```
Workflow:
1. Resize to 1200x800 (web-friendly)
2. Apply sharpening filter
3. Convert to WEBP format
4. Result: Optimized images, 70% smaller!
```

### Example 3: PDF Watermarking

```
1. Select all company PDFs
2. Use "PDF Watermarker" template
3. Set watermark text: "CONFIDENTIAL"
4. Batch process → All PDFs watermarked!
```

### Example 4: CSV Data Cleaning

```
Workflow:
1. Load CSV file with customer data
2. Filter: Status == "Active"
3. Result: Clean dataset ready for analysis
```

## 🔧 Available Operations

### Image Operations

- **Image Resize**: Scale images to specific dimensions
- **Image Convert**: Change format (PNG, JPEG, WEBP, BMP, TIFF)
- **Image Filter**: Apply filters (blur, sharpen, grayscale, etc.)

### PDF Operations

- **PDF Merge**: Combine multiple PDFs into one
- **PDF Watermark**: Add text watermarks

### CSV Operations

- **CSV Filter**: Filter rows based on conditions

### General Operations

- **File Rename**: Batch rename with patterns ({original}, {counter}, {timestamp})

## 🎯 Pre-built Templates

BatchStudio comes with these ready-to-use templates:

1. **Image Resizer**: Resize images to 1920x1080
2. **Image Format Converter**: Convert images to PNG
3. **PDF Watermarker**: Add "CONFIDENTIAL" watermark
4. **CSV Data Cleaner**: Filter CSV data
5. **Batch File Renamer**: Rename files with patterns
6. **Photo Optimizer**: Resize + sharpen + convert to WEBP

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

## ⚙️ Configuration

### Naming Patterns

Use these placeholders in the naming pattern:

- `{original}`: Original filename (without extension)
- `{timestamp}`: Unix timestamp
- `{counter}`: Sequential number (001, 002, ...)

Examples:
- `{original}_processed` → `photo_processed.jpg`
- `IMG_{counter}` → `IMG_001.jpg`, `IMG_002.jpg`
- `{original}_{timestamp}` → `photo_1234567890.jpg`

### Parallel Workers

- **1-2 workers**: For I/O intensive operations
- **4-8 workers**: Optimal for most tasks
- **8-16 workers**: For CPU-intensive operations on powerful machines

## 🐛 Troubleshooting

### Common Issues

**Issue**: "Module not found" error
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**Issue**: Slow processing
```bash
# Solution: Increase parallel workers in Run tab
# Or reduce file batch size
```

**Issue**: Out of memory
```bash
# Solution: Process files in smaller batches
# Or reduce parallel workers
```

**Issue**: Permission denied
```bash
# Solution: Run with appropriate permissions
# Windows: Run as Administrator
# Linux/Mac: chmod +x main.py
```

## 📊 Performance Tips

1. **Use appropriate workers**: Start with 4, adjust based on results
2. **Batch processing**: Process 100-1000 files at a time for optimal memory usage
3. **Dry run first**: Test with small batch before processing thousands
4. **SSD vs HDD**: SSD significantly faster for I/O operations
5. **Close other apps**: Free up system resources for better performance

## 🎨 Easter Eggs

- **Ctrl+Shift+D**: Open developer console
- **Confetti animation**: Appears on successful batch completion
- **Motivational quotes**: Random quotes during processing

## 📝 Project Structure

```
BatchStudio/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── ARCHITECTURE.txt       # Architecture diagram
├── core/                  # Core processing logic
│   ├── __init__.py
│   ├── operations.py      # Operation registry & base classes
│   ├── workflow.py        # Workflow management
│   └── processor.py       # Batch processing engine
├── ui/                    # User interface
│   ├── __init__.py
│   ├── main_window.py     # Main window
│   ├── input_panel.py     # File selection
│   ├── workflow_panel.py  # Workflow builder
│   ├── run_panel.py       # Execution controls
│   └── logs_panel.py      # Logs & reports
├── workflows/             # Saved workflows (created at runtime)
└── tests/                 # Unit tests (future)
```

## 🧪 Testing

Run the application with test files:

```bash
# Create test directory with sample files
mkdir test_files
# Add some images, PDFs, CSVs
python main.py
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

## 📧 Support

- Report bugs: Create an issue on GitHub
- Feature requests: Open a discussion
- Questions: Check the documentation first

## 🌟 Credits

Built with:
- Python 3.10+
- Tkinter (GUI)
- Pillow (Image processing)
- Pandas (Data processing)
- ReportLab (PDF generation)
- pypdf (PDF manipulation)

## 🔮 Roadmap

Future features planned:

- [ ] Video processing operations
- [ ] Audio file operations
- [ ] Cloud storage integration (Google Drive, Dropbox)
- [ ] Scheduled batch processing
- [ ] Email notifications on completion
- [ ] More pre-built templates
- [ ] Plugin marketplace
- [ ] Mobile companion app
- [ ] AI-powered file organization
- [ ] Batch preview thumbnails

## 📈 Version History

### v1.0.0 (Initial Release)
- ✅ Multi-format file support
- ✅ Drag-and-drop workflow builder
- ✅ Multi-threaded processing
- ✅ Progress tracking & logging
- ✅ HTML/CSV reports
- ✅ Pre-built templates
- ✅ Dry run mode
- ✅ Modern UI with dark mode

---

<div align="center">

**Made with ❤️ by the BatchStudio team**

[⬆ Back to top](#-batchstudio---batch-processing-studio)

</div>
