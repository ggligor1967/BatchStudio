"""
BatchStudio - Main Window
Creates the main application window with tabbed interface.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os

from ui.input_panel import InputPanel
from ui.workflow_panel import WorkflowPanel
from ui.run_panel import RunPanel
from ui.logs_panel import LogsPanel
from core import __version__, BatchProcessor, get_settings


class MainWindow:
    """Main application window."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BatchStudio - Batch Processing Studio")
        
        # Load settings
        self.settings = get_settings()
        
        # Apply saved window geometry
        width, height, x, y = self.settings.get_window_geometry()
        if x is not None and y is not None:
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        else:
            self.root.geometry(f"{width}x{height}")
        
        # Set theme colors
        self.colors = {
            'primary': '#667eea',
            'secondary': '#764ba2',
            'success': '#27ae60',
            'danger': '#e74c3c',
            'warning': '#f39c12',
            'dark': '#2c3e50',
            'light': '#ecf0f1',
            'bg': '#ffffff'
        }
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()
        
        # Initialize core components
        self.processor = BatchProcessor(max_workers=self.settings.get('default_workers', 4))
        
        # State
        self.current_files = []
        self.current_workflow = None
        self.dark_mode = self.settings.get('dark_mode', False)
        
        # Build UI
        self._create_menu()
        self._create_main_interface()
        self._create_statusbar()
        
        # Keyboard shortcuts
        self._setup_shortcuts()
        
        # Center window (if no saved position)
        if x is None or y is None:
            self._center_window()
        
        # Apply theme
        if self.dark_mode:
            self._apply_dark_theme()
        
        # Save window position on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Show welcome message
        self.root.after(100, self._show_welcome)
    
    def _on_close(self):
        """Handle window close - save settings."""
        # Save window geometry
        geo = self.root.geometry()
        # Parse geometry string (WxH+X+Y)
        try:
            size, pos = geo.split('+', 1)
            w, h = size.split('x')
            x, y = pos.split('+')
            self.settings.save_window_geometry(int(w), int(h), int(x), int(y))
        except:
            pass
        
        # Save dark mode preference
        self.settings.set('dark_mode', self.dark_mode)
        
        self.root.destroy()
    
    def _configure_styles(self):
        """Configure ttk styles."""
        self.style.configure('Title.TLabel',
                           font=('Segoe UI', 24, 'bold'),
                           foreground=self.colors['primary'])
        
        self.style.configure('Heading.TLabel',
                           font=('Segoe UI', 14, 'bold'),
                           foreground=self.colors['dark'])
        
        self.style.configure('Primary.TButton',
                           font=('Segoe UI', 10, 'bold'),
                           foreground='white',
                           background=self.colors['primary'])
        
        self.style.configure('TNotebook',
                           background=self.colors['light'])
        
        self.style.configure('TNotebook.Tab',
                           font=('Segoe UI', 11),
                           padding=[20, 10])
    
    def _create_menu(self):
        """Create menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Workflow", command=self._new_workflow, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Workflow...", command=self._open_workflow, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Workflow", command=self._save_workflow, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Preferences", command=self._show_preferences)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_checkbutton(label="Dark Mode", command=self._toggle_theme)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self._show_documentation)
        help_menu.add_command(label="About", command=self._show_about)
    
    def _create_main_interface(self):
        """Create main tabbed interface."""
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create panels
        self.input_panel = InputPanel(self.notebook, self)
        self.workflow_panel = WorkflowPanel(self.notebook, self)
        self.run_panel = RunPanel(self.notebook, self)
        self.logs_panel = LogsPanel(self.notebook, self)
        
        # Add tabs
        self.notebook.add(self.input_panel.frame, text="📁 Input Files")
        self.notebook.add(self.workflow_panel.frame, text="🔧 Workflow")
        self.notebook.add(self.run_panel.frame, text="▶️ Run")
        self.notebook.add(self.logs_panel.frame, text="📊 Logs")
    
    def _create_statusbar(self):
        """Create status bar."""
        self.statusbar = ttk.Frame(self.root)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        self.status_label = ttk.Label(self.statusbar, text="Ready", foreground=self.colors['success'])
        self.status_label.pack(side=tk.LEFT)
        
        self.version_label = ttk.Label(self.statusbar, text=f"v{__version__}", foreground='gray')
        self.version_label.pack(side=tk.RIGHT)
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        self.root.bind('<Control-n>', lambda e: self._new_workflow())
        self.root.bind('<Control-o>', lambda e: self._open_workflow())
        self.root.bind('<Control-s>', lambda e: self._save_workflow())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<Control-Shift-D>', lambda e: self._show_dev_console())
    
    def _center_window(self):
        """Center window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _show_welcome(self):
        """Show welcome message."""
        self.set_status("Welcome to BatchStudio! 🎉 Ready to process some files?")
    
    def _new_workflow(self):
        """Create new workflow."""
        self.workflow_panel.create_new_workflow()
        self.notebook.select(1)  # Switch to workflow tab
    
    def _open_workflow(self):
        """Open existing workflow."""
        self.workflow_panel.load_workflow()
    
    def _save_workflow(self):
        """Save current workflow."""
        self.workflow_panel.save_workflow()
    
    def _show_preferences(self):
        """Show preferences dialog."""
        messagebox.showinfo(
            "Preferences",
            "A preferences editor is not available in this release.\n\n"
            "Settings are stored in ~/.batchstudio/settings.json.",
        )
    
    def _toggle_theme(self):
        """Toggle between light and dark mode."""
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()
    
    def _apply_dark_theme(self):
        """Apply dark theme."""
        self.colors['bg'] = '#1e1e1e'
        self.colors['dark'] = '#ffffff'
        self.colors['light'] = '#2d2d2d'
        self.root.configure(bg=self.colors['bg'])
        # Reconfigure styles
        self._configure_styles()
    
    def _apply_light_theme(self):
        """Apply light theme."""
        self.colors['bg'] = '#ffffff'
        self.colors['dark'] = '#2c3e50'
        self.colors['light'] = '#ecf0f1'
        self.root.configure(bg=self.colors['bg'])
        # Reconfigure styles
        self._configure_styles()
    
    def _show_documentation(self):
        """Show documentation."""
        messagebox.showinfo("Documentation",
                          "📚 BatchStudio Documentation\n\n"
                          "1. Add files in the Input tab\n"
                          "2. Build your workflow in the Workflow tab\n"
                          "3. Run the batch in the Run tab\n"
                          "4. View results in the Logs tab\n\n"
                          "For more help, check README.md")
    
    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo("About BatchStudio",
                          f"🎨 BatchStudio v{__version__}\n\n"
                          "A Tkinter desktop application for\n"
                          "registry-backed file workflows.\n\n"
                          "Built with Python & Tkinter")
    
    def _show_dev_console(self):
        """Show hidden developer console (Easter egg)."""
        messagebox.showinfo("🎮 Developer Console",
                          "Easter egg found! 🎉\n\n"
                          "You've unlocked the developer console!\n"
                          "An interactive console is not implemented in this release.")
    
    def set_status(self, message: str, color: str = 'success'):
        """Update status bar message."""
        self.status_label.config(text=message, foreground=self.colors.get(color, 'gray'))
        self.root.update_idletasks()
    
    def get_files(self):
        """Get current file list."""
        return self.current_files
    
    def set_files(self, files):
        """Set current file list."""
        self.current_files = files
    
    def get_workflow(self):
        """Get current workflow."""
        return self.current_workflow
    
    def set_workflow(self, workflow):
        """Set current workflow."""
        self.current_workflow = workflow
