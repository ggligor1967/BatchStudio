#!/usr/bin/env python3
"""
BatchStudio - Batch Processing Studio

A Tkinter desktop application for registry-backed batch file workflows.

Author: BatchStudio Team
Version: defined by core._version.__version__
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import __version__
from ui import MainWindow
from ui.dnd_support import enable_native_file_drop


def create_application_root():
    """Create the sole Tk interpreter and initialize optional native DnD on it."""
    root = tk.Tk()
    return root, enable_native_file_drop(root)


def main():
    """Main application entry point."""
    root, dnd_status = create_application_root()
    
    # Set application icon (if available)
    try:
        # icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')
        # if os.path.exists(icon_path):
        #     root.iconbitmap(icon_path)
        pass
    except:
        pass
    
    # Create main window
    app = MainWindow(root, dnd_status=dnd_status)
    
    # Start the application
    root.mainloop()


if __name__ == "__main__":
    print(f"""
    ================================================================
                         BATCHSTUDIO v{__version__}
    ================================================================

    Starting BatchStudio...

    Registry-backed file workflows
    Thread-pool batch execution
    HTML and CSV processing reports
    """)
    
    main()
