#!/usr/bin/env python3
"""
BatchStudio - Batch Processing Studio

A powerful cross-platform desktop application for batch file processing.
Process images, PDFs, CSVs, and more through customizable workflows!

Author: BatchStudio Team
Version: 1.0.0
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import MainWindow


def main():
    """Main application entry point."""
    # Create root window
    root = tk.Tk()
    
    # Set application icon (if available)
    try:
        # icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')
        # if os.path.exists(icon_path):
        #     root.iconbitmap(icon_path)
        pass
    except:
        pass
    
    # Create main window
    app = MainWindow(root)
    
    # Start the application
    root.mainloop()


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                      BATCHSTUDIO v1.0.0                       ║
    ║          Your Friendly Batch Processing Companion            ║
    ╚══════════════════════════════════════════════════════════════╝
    
    🚀 Starting BatchStudio...
    
    Features:
    • Batch process images, PDFs, CSVs, and more
    • Drag-and-drop workflow builder
    • Multi-threaded processing
    • Beautiful progress tracking
    • Comprehensive reports
    
    Ready to transform your files! ✨
    """)
    
    main()
