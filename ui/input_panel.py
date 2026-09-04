"""
BatchStudio - Input Panel
File selection and preview interface with drag & drop support.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from PIL import Image, ImageTk
import csv

# Try to import tkinterdnd2 for drag & drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

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
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif',
        '.pdf', '.csv', '.xlsx', '.xls', '.txt', '.json', '.xml'
    }
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)
        self.selected_files = []
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
        list_frame = ttk.LabelFrame(content_frame, text="Selected Files (Drag & Drop supported)", padding=10)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Search/filter entry
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(filter_frame, text="🔍").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', self._filter_files)
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=30)
        self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(filter_frame, text="✕", width=3,
                  command=lambda: self.filter_var.set('')).pack(side=tk.RIGHT)
        
        # Scrollbar for file list
        list_scroll = ttk.Scrollbar(list_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(list_frame, yscrollcommand=list_scroll.set,
                                       font=('Segoe UI', 10), selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.config(command=self.file_listbox.yview)
        
        # Bind selection event and keyboard shortcuts
        self.file_listbox.bind('<<ListboxSelect>>', self._on_file_select)
        self.file_listbox.bind('<Delete>', lambda e: self._remove_selected())
        self.file_listbox.bind('<Control-a>', self._select_all)
        
        # Drop zone indicator (shown when empty)
        self.drop_label = ttk.Label(list_frame, 
                                   text="📂 Drop files here\nor use buttons above",
                                   font=('Segoe UI', 12),
                                   foreground='gray')
        
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
        if HAS_DND:
            try:
                # Register the listbox as a drop target
                self.file_listbox.drop_target_register(DND_FILES)
                self.file_listbox.dnd_bind('<<Drop>>', self._on_drop)
                self.file_listbox.dnd_bind('<<DragEnter>>', self._on_drag_enter)
                self.file_listbox.dnd_bind('<<DragLeave>>', self._on_drag_leave)
            except Exception as e:
                print(f"Drag & drop setup failed: {e}")
        
        # Also bind native tkinter events for basic drag support
        self.file_listbox.bind('<Button-1>', self._on_click)
    
    def _on_drop(self, event):
        """Handle file drop event."""
        # Parse dropped files (format varies by OS)
        files = self._parse_drop_data(event.data)
        added = 0
        
        for filepath in files:
            if os.path.isfile(filepath):
                if self._add_single_file(filepath):
                    added += 1
            elif os.path.isdir(filepath):
                added += self._add_folder_recursive(filepath)
        
        if added > 0:
            self._update_stats()
            self.main_window.set_files(self.selected_files)
            self.main_window.set_status(f"Dropped {added} file(s)")
        
        # Reset listbox appearance
        self.file_listbox.config(bg='white')
        return event.action
    
    def _parse_drop_data(self, data):
        """Parse dropped file data (handles different OS formats)."""
        files = []
        
        # Handle Windows format with curly braces for paths with spaces
        if '{' in data:
            import re
            # Match paths in curly braces or standalone paths
            pattern = r'\{([^}]+)\}|(\S+)'
            matches = re.findall(pattern, data)
            for match in matches:
                path = match[0] if match[0] else match[1]
                if path:
                    files.append(path)
        else:
            # Simple space-separated list
            files = data.split()
        
        return [f.strip() for f in files if f.strip()]
    
    def _on_drag_enter(self, event):
        """Visual feedback when dragging over."""
        self.file_listbox.config(bg='#e8f4fc')
        return event.action
    
    def _on_drag_leave(self, event):
        """Reset visual feedback."""
        self.file_listbox.config(bg='white')
        return event.action
    
    def _on_click(self, event):
        """Handle click in listbox."""
        pass  # Placeholder for future drag-to-reorder
    
    def _select_all(self, event):
        """Select all files in listbox."""
        self.file_listbox.select_set(0, tk.END)
        return 'break'
    
    def _add_single_file(self, filepath):
        """Add a single file if valid."""
        ext = os.path.splitext(filepath)[1].lower()
        
        if filepath in self.selected_files:
            return False
        
        if ext not in self.SUPPORTED_EXTENSIONS:
            return False
        
        self.selected_files.append(filepath)
        self.file_listbox.insert(tk.END, os.path.basename(filepath))
        self._update_drop_zone_visibility()
        return True
    
    def _add_folder_recursive(self, folder):
        """Add all supported files from a folder recursively."""
        count = 0
        for root, dirs, files in os.walk(folder):
            for file in files:
                filepath = os.path.join(root, file)
                if self._add_single_file(filepath):
                    count += 1
        return count
    
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
        
        for filepath in self.selected_files:
            filename = os.path.basename(filepath).lower()
            if filter_text in filename:
                self.file_listbox.insert(tk.END, os.path.basename(filepath))
    
    def _remove_selected(self):
        """Remove selected files from list."""
        selection = list(self.file_listbox.curselection())
        if not selection:
            return
        
        # Get actual filenames from listbox (may be filtered)
        files_to_remove = []
        for index in selection:
            display_name = self.file_listbox.get(index)
            # Find matching file in selected_files
            for filepath in self.selected_files:
                if os.path.basename(filepath) == display_name:
                    files_to_remove.append(filepath)
                    break
        
        # Remove files
        for filepath in files_to_remove:
            if filepath in self.selected_files:
                self.selected_files.remove(filepath)
            # Clean up preview cache
            if filepath in self.file_previews:
                del self.file_previews[filepath]
                if filepath in self._preview_cache_order:
                    self._preview_cache_order.remove(filepath)
        
        # Refresh display
        self._filter_files()
        self._update_stats()
        self._update_drop_zone_visibility()
        self.main_window.set_files(self.selected_files)
        self.main_window.set_status(f"Removed {len(files_to_remove)} file(s)")
    
    def _add_files(self):
        """Add files via file dialog."""
        files = filedialog.askopenfilenames(
            title="Select Files to Process",
            filetypes=[
                ("All Supported", "*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.webp;*.tiff;*.pdf;*.csv;*.txt;*.xlsx;*.xls;*.json;*.xml"),
                ("Images", "*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.webp;*.tiff"),
                ("PDFs", "*.pdf"),
                ("Spreadsheets", "*.csv;*.xlsx;*.xls"),
                ("Text/Data", "*.txt;*.json;*.xml"),
                ("All Files", "*.*")
            ]
        )
        
        if files:
            added = 0
            for file in files:
                if self._add_single_file(file):
                    added += 1
            
            self._update_stats()
            self.main_window.set_files(self.selected_files)
            self.main_window.set_status(f"Added {added} file(s)")
    
    def _add_folder(self):
        """Add all files from a folder."""
        folder = filedialog.askdirectory(title="Select Folder")
        
        if folder:
            count = self._add_folder_recursive(folder)
            self._update_stats()
            self.main_window.set_files(self.selected_files)
            self.main_window.set_status(f"Added {count} file(s) from folder")
    
    def _clear_all(self):
        """Clear all selected files."""
        if self.selected_files and messagebox.askyesno("Clear All",
                                                       "Remove all files from the list?"):
            self.selected_files = []
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
        
        # Get the display name and find matching filepath
        display_name = self.file_listbox.get(selection[0])
        filepath = None
        for f in self.selected_files:
            if os.path.basename(f) == display_name:
                filepath = f
                break
        
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
        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'):
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
