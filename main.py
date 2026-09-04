#!/usr/bin/env python3
"""
BatchStudio - Batch Processing Studio

A Tkinter desktop application for registry-backed batch file workflows.

Author: BatchStudio Team
Version: 1.0.1
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
    ================================================================
                         BATCHSTUDIO v1.0.1
    ================================================================

    Starting BatchStudio...

    Registry-backed file workflows
    Thread-pool batch execution
    HTML and CSV processing reports
    """)
    
    main()
