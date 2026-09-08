"""
BatchStudio - Input Panel
File selection and preview interface with optional native file drag-and-drop.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from PIL import Image, ImageTk
import csv
from copy import deepcopy
from queue import Empty, SimpleQueue
import threading

from core.operations.registry import OperationRegistry
from ui.dnd_support import COPY, DND_FILES, REFUSE_DROP
from ui.input_support import InputCapabilityRegistry, get_input_error, get_picker_filetypes

# Try to import pypdf for PDF preview
try:
    from pypdf import PdfReader
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


class InputPanel:
    """Input panel for file selection with drag & drop support."""
    
    # Maximum number of previews to cache (prevent memory leak)
    MAX_PREVIEW_CACHE = 50
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)
        self.selected_files = []
        self._selected_file_identities = set()
        self._displayed_files = []
        self._selection_token = None
        self.file_previews = {}
        self._preview_cache_order = []  # Track order for LRU cache
        
        self._create_widgets()
        self._setup_drag_drop()
    
    def _create_widgets(self):
        """Create panel widgets."""
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title = ttk.Label(header_frame, text="Select Files to Process",
                         style='Heading.TLabel')
        title.pack(side=tk.LEFT)
        
        # Button frame
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="➕ Add Files",
                  command=self._add_files).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="📁 Add Folder",
                  command=self._add_folder).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="➖ Remove Selected",
                  command=self._remove_selected).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="🗑️ Clear All",
                  command=self._clear_all).pack(side=tk.LEFT, padx=5)
        
        # Main content area with two columns
        content_frame = ttk.Frame(self.frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left: File list with drag & drop zone
        self.file_list_frame = ttk.LabelFrame(
            content_frame, text="Selected Files", padding=10
        )
        self.file_list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Search/filter entry
        filter_frame = ttk.Frame(self.file_list_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(filter_frame, text="🔍").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', self._filter_files)
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=30)
        self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(filter_frame, text="✕", width=3,
                  command=lambda: self.filter_var.set('')).pack(side=tk.RIGHT)
        
        # Scrollbar for file list
        list_scroll = ttk.Scrollbar(self.file_list_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(self.file_list_frame, yscrollcommand=list_scroll.set,
                                       font=('Segoe UI', 10), selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.config(command=self.file_listbox.yview)
        
        # Bind selection event and keyboard shortcuts
        self.file_listbox.bind('<<ListboxSelect>>', self._on_file_select)
        self.file_listbox.bind('<Delete>', lambda e: self._remove_selected())
        self.file_listbox.bind('<Control-a>', self._select_all)
        
        # Drop zone indicator (shown when empty)
        self.drop_label = ttk.Label(self.file_list_frame,
                                   text="📂 Use buttons above to add files",
                                   font=('Segoe UI', 12),
                                   foreground='gray')
        self._default_drop_background = self.file_listbox.cget("background")
        self._default_drop_foreground = self.drop_label.cget("foreground")
        
        # Right: Preview and info
        preview_frame = ttk.LabelFrame(content_frame, text="Preview", padding=10)
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Preview canvas for images
        self.preview_canvas = tk.Canvas(preview_frame, width=400, height=300,
                                       bg='#f0f0f0', relief=tk.SUNKEN, borderwidth=2)
        self.preview_canvas.pack(pady=10)
        
        # File info with scrollbar
        info_frame = ttk.Frame(preview_frame)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        info_scroll = ttk.Scrollbar(info_frame)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.info_text = tk.Text(info_frame, height=8, wrap=tk.WORD,
                                font=('Segoe UI', 9), yscrollcommand=info_scroll.set)
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scroll.config(command=self.info_text.yview)
        
        # Configure text tags for colored output
        self.info_text.tag_config('header', font=('Segoe UI', 10, 'bold'), foreground='#667eea')
        self.info_text.tag_config('label', font=('Segoe UI', 9, 'bold'))
        self.info_text.tag_config('value', foreground='#333')
        
        # Stats frame at bottom
        stats_frame = ttk.Frame(self.frame)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.stats_label = ttk.Label(stats_frame,
                                     text="No files selected",
                                     font=('Segoe UI', 10, 'bold'))
        self.stats_label.pack(side=tk.LEFT)
        
        # Next button
        ttk.Button(stats_frame, text="Next: Build Workflow ➡️",
                  command=self._go_to_workflow,
                  style='Primary.TButton').pack(side=tk.RIGHT)
        
        # Show drop zone initially
        self._update_drop_zone_visibility()
    
    def _setup_drag_drop(self):
        """Setup drag and drop functionality."""
        status = getattr(self.main_window, "dnd_status", None)
        if status is None or not status.tkdnd_loaded:
            return

        targets = (self.file_listbox, self.drop_label)
        registered_targets = []
        try:
            for target in targets:
                target.drop_target_register(DND_FILES)
                registered_targets.append(target)
                target.dnd_bind("<<DropEnter>>", self._on_drop_enter)
                target.dnd_bind("<<DropPosition>>", self._on_drop_position)
                target.dnd_bind("<<DropLeave>>", self._on_drop_leave)
                target.dnd_bind("<<Drop>>", self._on_drop)
        except Exception as error:
            for target in registered_targets:
                try:
                    target.drop_target_unregister()
                except Exception:
                    pass
            status.targets_registered = False
            status.error = f"{type(error).__name__}: {error}"
            self._reset_drop_feedback()
            return

        status.targets_registered = True
        status.error = None
        self.file_list_frame.config(text="Selected Files (native file drop available)")
        self.drop_label.config(text="📂 Drop files here\nor use buttons above")
    
    def _on_drop(self, event):
        """Handle file drop event."""
        action = self._negotiate_drop_action(event)
        if action == REFUSE_DROP:
            self._reset_drop_feedback()
            self.main_window.set_status("Drop refused; the source must allow copying.", "warning")
            return REFUSE_DROP

        try:
            files = self._parse_drop_data(event.data)
        except ValueError as error:
            self._reset_drop_feedback()
            self.main_window.set_status(str(error), "warning")
            messagebox.showwarning("Drop refused", str(error))
            return REFUSE_DROP

        def candidates():
            for filepath in files:
                if os.path.isdir(filepath):
                    yield from self._folder_files(filepath)
                else:
                    yield filepath

        started = self._accept_files(candidates())
        self._reset_drop_feedback()
        return COPY if started else REFUSE_DROP
    
    def _parse_drop_data(self, data):
        """Parse the native payload as the Tcl list emitted by tkdnd."""
        if not isinstance(data, str) or not data:
            raise ValueError("Drop refused: empty Tcl file list.")
        try:
            files = self.frame.tk.splitlist(data)
        except (tk.TclError, ValueError) as error:
            raise ValueError("Drop refused: malformed Tcl file list.") from error
        if not files or any(not isinstance(path, str) or not path for path in files):
            raise ValueError("Drop refused: empty Tcl file list.")
        return list(files)

    def _negotiate_drop_action(self, event):
        actions = getattr(event, "actions", ())
        if isinstance(actions, str):
            try:
                actions = self.frame.tk.splitlist(actions)
            except (tk.TclError, ValueError):
                actions = ()
        if COPY in actions or (not actions and getattr(event, "action", None) == COPY):
            return COPY
        return REFUSE_DROP

    def _on_drop_enter(self, event):
        """Negotiate a non-destructive action and show target feedback."""
        action = self._negotiate_drop_action(event)
        if action == COPY:
            self._show_drop_feedback()
        else:
            self._reset_drop_feedback()
        return action

    def _on_drop_position(self, event):
        """Maintain COPY-only negotiation while the pointer moves."""
        return self._on_drop_enter(event)

    def _on_drop_leave(self, event):
        """Reset target feedback when the pointer leaves."""
        self._reset_drop_feedback()

    def _show_drop_feedback(self):
        self.file_listbox.config(background="#e8f4fc")
        self.drop_label.config(foreground="#667eea")

    def _reset_drop_feedback(self):
        background = getattr(self, "_default_drop_background", "white")
        foreground = getattr(self, "_default_drop_foreground", "gray")
        self.file_listbox.config(background=background)
        self.drop_label.config(foreground=foreground)
    
    def _select_all(self, event):
        """Select all files in listbox."""
        self.file_listbox.select_set(0, tk.END)
        return 'break'
    
    def _add_single_file(self, filepath):
        """Insert a worker-validated file once; this method only updates UI state."""
        filepath = os.fspath(filepath)
        identity = self._selection_identity(filepath)
        identities = getattr(self, "_selected_file_identities", None)
        if identities is None:
            identities = {self._selection_identity(path) for path in self.selected_files}
            self._selected_file_identities = identities
        if identity in identities:
            return False

        identities.add(identity)
        self.selected_files.append(filepath)
        filter_var = getattr(self, "filter_var", None)
        filter_text = filter_var.get().lower() if filter_var is not None else ""
        if filter_text in os.path.basename(filepath).lower():
            self.file_listbox.insert(tk.END, os.path.basename(filepath))
            displayed_files = getattr(self, "_displayed_files", None)
            if displayed_files is None:
                displayed_files = []
                self._displayed_files = displayed_files
            displayed_files.append(filepath)
        self._update_drop_zone_visibility()
        return True

    @staticmethod
    def _selection_identity(filepath):
        normalized = os.path.abspath(os.path.normpath(os.fspath(filepath)))
        return os.path.normcase(normalized)

    def _folder_files(self, folder):
        for root, dirs, files in os.walk(folder):
            for filename in files:
                yield os.path.join(root, filename)

    def _load_input_support(self, check, complete):
        """Run one input probe at a time and publish its result only on Tk."""
        if getattr(self, "_selection_token", None) is not None:
            message = "An input availability check is already in progress; try again when it finishes."
            self.main_window.set_status(message, "warning")
            messagebox.showwarning("Input check in progress", message)
            return False

        token = object()
        self._selection_token = token
        results = SimpleQueue()
        self.main_window.set_status("Checking input availability...")

        def probe():
            try:
                results.put((check(), None))
            except Exception:
                results.put((None, "Input availability check failed; please try again."))

        def poll():
            if not self.frame.winfo_exists() or getattr(self, "_selection_token", None) is not token:
                return
            try:
                result, error = results.get_nowait()
            except Empty:
                self.frame.after(50, poll)
                return
            self._selection_token = None
            if error:
                self.main_window.set_status(error, 'warning')
                messagebox.showwarning("Input unavailable", error)
            else:
                complete(result)

        worker = threading.Thread(target=probe, daemon=True)
        try:
            worker.start()
        except Exception:
            self._selection_token = None
            raise
        self.frame.after(0, poll)
        return True

    def _accept_files(self, files):
        workflow = deepcopy(self.main_window.get_workflow())

        def check():
            registry = InputCapabilityRegistry()
            return [(path, get_input_error(path, workflow, registry)) for path in files]

        def complete(results):
            current = self.main_window.get_workflow()
            if (current.to_dict() if current else None) != (workflow.to_dict() if workflow else None):
                messagebox.showwarning("Selection changed", "Workflow changed; select inputs again.")
                self.main_window.set_status("Workflow changed; select inputs again.", "warning")
                return
            added = 0
            rejected = []
            for path, error in results:
                if error:
                    rejected.append(f"{os.path.basename(path)}: {error}")
                elif self._add_single_file(path):
                    added += 1
            self._update_stats()
            self.main_window.set_files(self.selected_files)
            self.main_window.set_status(f"Added {added} file(s); rejected {len(rejected)}")
            if rejected:
                message = "\n".join(rejected[:10])
                if len(rejected) > 10:
                    message += f"\n... and {len(rejected) - 10} more rejected inputs."
                messagebox.showwarning("Inputs rejected", message)

        return self._load_input_support(check, complete)

    def _update_drop_zone_visibility(self):
        """Show/hide drop zone based on file count."""
        if len(self.selected_files) == 0:
            self.drop_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        else:
            self.drop_label.place_forget()
    
    def _filter_files(self, *args):
        """Filter displayed files based on search text."""
        filter_text = self.filter_var.get().lower()
        
        self.file_listbox.delete(0, tk.END)
        self._displayed_files = []
        for filepath in self.selected_files:
            filename = os.path.basename(filepath).lower()
            if filter_text in filename:
                self.file_listbox.insert(tk.END, os.path.basename(filepath))
                self._displayed_files.append(filepath)
    
    def _remove_selected(self):
        """Remove selected files from list."""
        selection = list(self.file_listbox.curselection())
        if not selection:
            return
        
        displayed_files = getattr(self, "_displayed_files", self.selected_files)
        files_to_remove = [
            displayed_files[index] for index in selection if index < len(displayed_files)
        ]
        
        # Remove files
        for filepath in files_to_remove:
            if filepath in self.selected_files:
                self.selected_files.remove(filepath)
            # Clean up preview cache
            if filepath in self.file_previews:
                del self.file_previews[filepath]
                if filepath in self._preview_cache_order:
                    self._preview_cache_order.remove(filepath)
        self._selected_file_identities = {
            self._selection_identity(path) for path in self.selected_files
        }
        
        # Refresh display
        self._filter_files()
        self._update_stats()
        self._update_drop_zone_visibility()
        self.main_window.set_files(self.selected_files)
        self.main_window.set_status(f"Removed {len(files_to_remove)} file(s)")
    
    def _add_files(self):
        """Refresh workflow eligibility before opening the native picker."""
        workflow = deepcopy(self.main_window.get_workflow())

        def check():
            return get_picker_filetypes(workflow)

        def open_picker(result):
            filetypes, errors = result
            if not filetypes:
                message = "No eligible inputs for this workflow.\n" + "\n".join(errors)
                self.main_window.set_status("No eligible inputs for this workflow.", 'warning')
                messagebox.showwarning("Input unavailable", message)
                return
            self.main_window.set_status("Select inputs; availability is checked after selection.")
            files = filedialog.askopenfilenames(
                title="Select Files to Process", filetypes=filetypes)
            self._accept_files(files)

        self._load_input_support(check, open_picker)

    def _add_folder(self):
        """Apply the same selection boundary to folder inputs."""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            self._accept_files(self._folder_files(folder))

    def _clear_all(self):
        """Clear all selected files."""
        validation_pending = getattr(self, "_selection_token", None) is not None
        if not self.selected_files and not validation_pending:
            return
        prompt = "Remove all files from the list?"
        if validation_pending:
            prompt = "Remove all files and cancel the pending input check?"
        if messagebox.askyesno("Clear All", prompt):
            self._selection_token = None
            self.selected_files = []
            self._selected_file_identities = set()
            self._displayed_files = []
            self.file_listbox.delete(0, tk.END)
            self.preview_canvas.delete('all')
            self.info_text.delete(1.0, tk.END)
            self._clear_preview_cache()
            self._update_stats()
            self._update_drop_zone_visibility()
            self.main_window.set_files([])
            self.main_window.set_status("Cleared all files")
    
    def _clear_preview_cache(self):
        """Clear preview cache to free memory."""
        self.file_previews.clear()
        self._preview_cache_order.clear()
    
    def _manage_preview_cache(self, filepath):
        """Manage preview cache size (LRU eviction)."""
        if filepath in self._preview_cache_order:
            self._preview_cache_order.remove(filepath)
        self._preview_cache_order.append(filepath)
        
        # Evict oldest entries if cache is full
        while len(self._preview_cache_order) > self.MAX_PREVIEW_CACHE:
            oldest = self._preview_cache_order.pop(0)
            if oldest in self.file_previews:
                del self.file_previews[oldest]
    
    def _on_file_select(self, event):
        """Handle file selection in listbox."""
        selection = self.file_listbox.curselection()
        if not selection:
            return
        
        displayed_files = getattr(self, "_displayed_files", self.selected_files)
        filepath = displayed_files[selection[0]] if selection[0] < len(displayed_files) else None
        
        if filepath:
            self._show_preview(filepath)
    
    def _show_preview(self, filepath):
        """Show preview of selected file."""
        # Clear previous preview
        self.preview_canvas.delete('all')
        self.info_text.delete(1.0, tk.END)
        
        if not os.path.exists(filepath):
            self.info_text.insert(tk.END, "File not found!", 'header')
            return
        
        # Show file info
        file_size = os.path.getsize(filepath)
        size_str = self._format_size(file_size)
        ext = os.path.splitext(filepath)[1].lower()
        
        self.info_text.insert(tk.END, "📄 File Information\n\n", 'header')
        self.info_text.insert(tk.END, "Name: ", 'label')
        self.info_text.insert(tk.END, f"{os.path.basename(filepath)}\n", 'value')
        self.info_text.insert(tk.END, "Path: ", 'label')
        self.info_text.insert(tk.END, f"{filepath}\n", 'value')
        self.info_text.insert(tk.END, "Size: ", 'label')
        self.info_text.insert(tk.END, f"{size_str}\n", 'value')
        self.info_text.insert(tk.END, "Type: ", 'label')
        self.info_text.insert(tk.END, f"{ext}\n\n", 'value')
        
        # Show preview based on file type
        if OperationRegistry().classify_extension(ext) == 'image':
            self._show_image_preview(filepath)
        elif ext == '.pdf':
            self._show_pdf_preview(filepath)
        elif ext == '.csv':
            self._show_csv_preview(filepath)
        elif ext in ('.txt', '.json', '.xml'):
            self._show_text_preview(filepath)
        else:
            self.preview_canvas.create_text(200, 150,
                                          text=f"No preview for {ext} files",
                                          font=('Segoe UI', 12), fill='gray')
    
    def _show_image_preview(self, filepath):
        """Show image preview."""
        try:
            img = Image.open(filepath)
            self.info_text.insert(tk.END, "📐 Dimensions\n", 'header')
            self.info_text.insert(tk.END, "Width: ", 'label')
            self.info_text.insert(tk.END, f"{img.size[0]}px\n", 'value')
            self.info_text.insert(tk.END, "Height: ", 'label')
            self.info_text.insert(tk.END, f"{img.size[1]}px\n", 'value')
            self.info_text.insert(tk.END, "Format: ", 'label')
            self.info_text.insert(tk.END, f"{img.format}\n", 'value')
            self.info_text.insert(tk.END, "Mode: ", 'label')
            self.info_text.insert(tk.END, f"{img.mode}\n", 'value')
            
            # Resize for preview
            img.thumbnail((380, 280), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            # Manage cache
            self._manage_preview_cache(filepath)
            self.file_previews[filepath] = photo
            
            # Center image on canvas
            x = (400 - img.size[0]) // 2
            y = (300 - img.size[1]) // 2
            self.preview_canvas.create_image(x, y, anchor=tk.NW, image=photo)
            
        except Exception as e:
            self.preview_canvas.create_text(200, 150, text=f"Cannot preview: {e}",
                                          font=('Segoe UI', 10), fill='red')
    
    def _show_pdf_preview(self, filepath):
        """Show PDF preview with metadata."""
        if not HAS_PDF:
            self.preview_canvas.create_text(200, 150, 
                                          text="PDF preview requires pypdf",
                                          font=('Segoe UI', 12), fill='gray')
            return
        
        try:
            reader = PdfReader(filepath)
            num_pages = len(reader.pages)
            
            self.info_text.insert(tk.END, "📑 PDF Information\n", 'header')
            self.info_text.insert(tk.END, "Pages: ", 'label')
            self.info_text.insert(tk.END, f"{num_pages}\n", 'value')
            
            # Get metadata if available
            if reader.metadata:
                if reader.metadata.title:
                    self.info_text.insert(tk.END, "Title: ", 'label')
                    self.info_text.insert(tk.END, f"{reader.metadata.title}\n", 'value')
                if reader.metadata.author:
                    self.info_text.insert(tk.END, "Author: ", 'label')
                    self.info_text.insert(tk.END, f"{reader.metadata.author}\n", 'value')
            
            # Get first page dimensions
            if num_pages > 0:
                page = reader.pages[0]
                if page.mediabox:
                    width = float(page.mediabox.width)
                    height = float(page.mediabox.height)
                    self.info_text.insert(tk.END, "Page size: ", 'label')
                    self.info_text.insert(tk.END, f"{width:.0f} x {height:.0f} pts\n", 'value')
            
            # Show PDF icon
            self.preview_canvas.create_text(200, 120, text="📄",
                                          font=('Segoe UI', 72), fill='#e74c3c')
            self.preview_canvas.create_text(200, 200, text=f"PDF Document",
                                          font=('Segoe UI', 14, 'bold'), fill='#333')
            self.preview_canvas.create_text(200, 230, text=f"{num_pages} page(s)",
                                          font=('Segoe UI', 11), fill='#666')
            
        except Exception as e:
            self.preview_canvas.create_text(200, 150, text=f"Cannot read PDF: {e}",
                                          font=('Segoe UI', 10), fill='red')
    
    def _show_csv_preview(self, filepath):
        """Show CSV preview with sample data."""
        try:
            rows = []
            columns = []
            
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0:
                        columns = row
                    if i < 6:  # First 5 rows + header
                        rows.append(row)
                    else:
                        break
            
            # Count total rows
            with open(filepath, 'r', encoding='utf-8') as f:
                total_rows = sum(1 for _ in f) - 1  # Exclude header
            
            self.info_text.insert(tk.END, "📊 CSV Information\n", 'header')
            self.info_text.insert(tk.END, "Columns: ", 'label')
            self.info_text.insert(tk.END, f"{len(columns)}\n", 'value')
            self.info_text.insert(tk.END, "Rows: ", 'label')
            self.info_text.insert(tk.END, f"{total_rows}\n", 'value')
            self.info_text.insert(tk.END, "\nColumn names:\n", 'label')
            for col in columns[:10]:  # Show first 10 columns
                self.info_text.insert(tk.END, f"  • {col}\n", 'value')
            if len(columns) > 10:
                self.info_text.insert(tk.END, f"  ... and {len(columns) - 10} more\n", 'value')
            
            # Show CSV icon
            self.preview_canvas.create_text(200, 120, text="📊",
                                          font=('Segoe UI', 72), fill='#27ae60')
            self.preview_canvas.create_text(200, 200, text=f"CSV File",
                                          font=('Segoe UI', 14, 'bold'), fill='#333')
            self.preview_canvas.create_text(200, 230, text=f"{len(columns)} columns × {total_rows} rows",
                                          font=('Segoe UI', 11), fill='#666')
            
        except Exception as e:
            self.preview_canvas.create_text(200, 150, text=f"Cannot read CSV: {e}",
                                          font=('Segoe UI', 10), fill='red')
    
    def _show_text_preview(self, filepath):
        """Show text file preview."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # First 2000 chars
                total_size = os.path.getsize(filepath)
            
            lines = content.count('\n')
            
            self.info_text.insert(tk.END, "📝 Text Information\n", 'header')
            self.info_text.insert(tk.END, "Lines (preview): ", 'label')
            self.info_text.insert(tk.END, f"~{lines}\n", 'value')
            self.info_text.insert(tk.END, "\nPreview:\n", 'label')
            self.info_text.insert(tk.END, content[:500] + "...\n" if len(content) > 500 else content, 'value')
            
            # Show text icon
            self.preview_canvas.create_text(200, 120, text="📝",
                                          font=('Segoe UI', 72), fill='#3498db')
            self.preview_canvas.create_text(200, 200, text=f"Text File",
                                          font=('Segoe UI', 14, 'bold'), fill='#333')
            self.preview_canvas.create_text(200, 230, text=f"~{lines} lines",
                                          font=('Segoe UI', 11), fill='#666')
            
        except Exception as e:
            self.preview_canvas.create_text(200, 150, text=f"Cannot read file: {e}",
                                          font=('Segoe UI', 10), fill='red')
    
    def _format_size(self, size):
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def _update_stats(self):
        """Update statistics display."""
        count = len(self.selected_files)
        if count == 0:
            self.stats_label.config(text="No files selected")
        else:
            total_size = sum(os.path.getsize(f) for f in self.selected_files if os.path.exists(f))
            size_str = self._format_size(total_size)
            
            # Count by type
            types = {}
            for f in self.selected_files:
                ext = os.path.splitext(f)[1].lower()
                types[ext] = types.get(ext, 0) + 1
            
            type_str = ", ".join(f"{v} {k}" for k, v in sorted(types.items(), key=lambda x: -x[1])[:3])
            
            self.stats_label.config(text=f"📊 {count} file(s) • {size_str} • {type_str}")
    
    def _go_to_workflow(self):
        """Navigate to workflow tab."""
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please select some files first!")
            return
        
        self.main_window.notebook.select(1)  # Switch to workflow tab
        self.main_window.set_status("Now build your workflow →")
