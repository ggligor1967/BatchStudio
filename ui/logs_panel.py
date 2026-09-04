"""
BatchStudio - Logs Panel
Logs and reports viewing interface.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import webbrowser
import subprocess
import sys

from core import ProcessingStats


class LogsPanel:
    """Logs and reports panel."""
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)
        self.current_stats = None
        self.output_files = {}  # Map tree item id to output file path
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create panel widgets."""
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title = ttk.Label(header_frame, text="Processing Logs & Reports",
                         style='Heading.TLabel')
        title.pack(side=tk.LEFT)
        
        # Stats cards frame
        stats_frame = ttk.Frame(self.frame)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Create stat cards
        self.total_card = self._create_stat_card(stats_frame, "Total Files", "0", "#3498db")
        self.total_card.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        self.success_card = self._create_stat_card(stats_frame, "Processed", "0", "#27ae60")
        self.success_card.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        self.failed_card = self._create_stat_card(stats_frame, "Failed", "0", "#e74c3c")
        self.failed_card.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        self.duration_card = self._create_stat_card(stats_frame, "Duration", "0s", "#f39c12")
        self.duration_card.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # Tabs for different views
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Results tab
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="✅ Successful")
        
        results_scroll = ttk.Scrollbar(results_frame)
        results_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.results_tree = ttk.Treeview(results_frame,
                                        columns=('File', 'Status', 'Details'),
                                        show='headings',
                                        yscrollcommand=results_scroll.set)
        self.results_tree.heading('File', text='File')
        self.results_tree.heading('Status', text='Status')
        self.results_tree.heading('Details', text='Details')
        
        self.results_tree.column('File', width=300)
        self.results_tree.column('Status', width=100)
        self.results_tree.column('Details', width=400)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scroll.config(command=self.results_tree.yview)
        
        # Bind double-click to open file
        self.results_tree.bind('<Double-1>', self._on_result_double_click)
        # Bind right-click for context menu
        self.results_tree.bind('<Button-3>', self._show_context_menu)
        
        # Create context menu
        self.context_menu = tk.Menu(self.frame, tearoff=0)
        self.context_menu.add_command(label="📂 Open File", command=self._open_selected_file)
        self.context_menu.add_command(label="📁 Open Containing Folder", command=self._open_containing_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📋 Copy Path", command=self._copy_file_path)
        
        # Errors tab
        errors_frame = ttk.Frame(self.notebook)
        self.notebook.add(errors_frame, text="❌ Errors")
        
        errors_scroll = ttk.Scrollbar(errors_frame)
        errors_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.errors_tree = ttk.Treeview(errors_frame,
                                       columns=('File', 'Error'),
                                       show='headings',
                                       yscrollcommand=errors_scroll.set)
        self.errors_tree.heading('File', text='File')
        self.errors_tree.heading('Error', text='Error Message')
        
        self.errors_tree.column('File', width=300)
        self.errors_tree.column('Error', width=500)
        
        self.errors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        errors_scroll.config(command=self.errors_tree.yview)
        
        # Summary tab
        summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(summary_frame, text="📊 Summary")
        
        summary_scroll = ttk.Scrollbar(summary_frame)
        summary_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.summary_text = tk.Text(summary_frame, wrap=tk.WORD,
                                   font=('Segoe UI', 10),
                                   yscrollcommand=summary_scroll.set)
        self.summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        summary_scroll.config(command=self.summary_text.yview)
        
        # Configure text tags
        self.summary_text.tag_config('title', font=('Segoe UI', 16, 'bold'),
                                    foreground='#667eea')
        self.summary_text.tag_config('heading', font=('Segoe UI', 12, 'bold'))
        self.summary_text.tag_config('success', foreground='#27ae60')
        self.summary_text.tag_config('error', foreground='#e74c3c')
        
        # Action buttons
        action_frame = ttk.Frame(self.frame)
        action_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(action_frame, text="💾 Export to CSV",
                  command=self._export_csv).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="📄 View HTML Report",
                  command=self._view_html_report).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="📂 Open Output Folder",
                  command=self._open_output_folder).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="🗑️ Clear Logs",
                  command=self._clear_logs).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="🔄 New Batch",
                  command=self._new_batch).pack(side=tk.RIGHT, padx=5)
    
    def _create_stat_card(self, parent, label, value, color):
        """Create a statistics card."""
        card = ttk.Frame(parent, relief=tk.RAISED, borderwidth=2)
        
        value_label = ttk.Label(card, text=value,
                               font=('Segoe UI', 24, 'bold'),
                               foreground=color)
        value_label.pack(pady=10)
        value_label.value = value  # Store reference for updates
        
        label_label = ttk.Label(card, text=label,
                               font=('Segoe UI', 10))
        label_label.pack(pady=5)
        
        return card
    
    def show_stats(self, stats: ProcessingStats):
        """Display processing statistics."""
        self.current_stats = stats
        self.output_files = {}  # Reset output files map
        
        # Update stat cards
        self._update_stat_card(self.total_card, str(stats.total_files))
        self._update_stat_card(self.success_card, str(stats.processed_files))
        self._update_stat_card(self.failed_card, str(stats.failed_files))
        self._update_stat_card(self.duration_card, f"{stats.get_duration():.1f}s")
        
        # Clear previous data
        self.results_tree.delete(*self.results_tree.get_children())
        self.errors_tree.delete(*self.errors_tree.get_children())
        self.summary_text.delete(1.0, tk.END)
        
        # Populate results
        for result in stats.results:
            filename = os.path.basename(result.get('output', result['file']))
            status = "✅ Success"
            details = result['result'].get('message', 'Processed successfully')
            item_id = self.results_tree.insert('', tk.END, values=(filename, status, details))
            
            # Store output path for this item
            output_path = result.get('output', '')
            if output_path:
                self.output_files[item_id] = output_path
        
        # Populate errors
        for error in stats.errors:
            filename = os.path.basename(error['file'])
            error_msg = error['error']
            self.errors_tree.insert('', tk.END, values=(filename, error_msg))
        
        # Generate summary
        self._generate_summary(stats)
    
    def _update_stat_card(self, card, value):
        """Update a stat card value."""
        for child in card.winfo_children():
            if isinstance(child, ttk.Label) and hasattr(child, 'value'):
                child.config(text=value)
                break
    
    def _generate_summary(self, stats: ProcessingStats):
        """Generate summary report."""
        self.summary_text.insert(tk.END, "📊 Batch Processing Summary\n\n", 'title')
        
        self.summary_text.insert(tk.END, "Overview\n", 'heading')
        self.summary_text.insert(tk.END, f"Total files: {stats.total_files}\n")
        self.summary_text.insert(tk.END, f"Successfully processed: {stats.processed_files}\n", 'success')
        self.summary_text.insert(tk.END, f"Failed: {stats.failed_files}\n", 'error')
        self.summary_text.insert(tk.END, f"Duration: {stats.get_duration():.2f} seconds\n\n")
        
        if stats.processed_files > 0:
            avg_time = stats.get_duration() / stats.total_files
            self.summary_text.insert(tk.END, f"Average time per file: {avg_time:.3f} seconds\n\n")
        
        # Success rate
        if stats.total_files > 0:
            success_rate = (stats.processed_files / stats.total_files) * 100
            self.summary_text.insert(tk.END, f"Success rate: {success_rate:.1f}%\n\n")
        
        # Detailed results
        if stats.results:
            self.summary_text.insert(tk.END, "\nSuccessful Files\n", 'heading')
            for i, result in enumerate(stats.results[:10], 1):  # Show first 10
                filename = os.path.basename(result['file'])
                self.summary_text.insert(tk.END, f"{i}. {filename}\n", 'success')
            
            if len(stats.results) > 10:
                self.summary_text.insert(tk.END,
                                       f"... and {len(stats.results) - 10} more\n\n")
        
        # Errors
        if stats.errors:
            self.summary_text.insert(tk.END, "\nFailed Files\n", 'heading')
            for i, error in enumerate(stats.errors[:10], 1):  # Show first 10
                filename = os.path.basename(error['file'])
                error_msg = error['error']
                self.summary_text.insert(tk.END,
                                       f"{i}. {filename}\n   Error: {error_msg}\n",
                                       'error')
            
            if len(stats.errors) > 10:
                self.summary_text.insert(tk.END,
                                       f"... and {len(stats.errors) - 10} more\n")
    
    def _export_csv(self):
        """Export logs to CSV."""
        if not self.current_stats:
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Export Logs to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filepath:
            processor = self.main_window.processor
            if processor.generate_report(self.current_stats, filepath, format='csv'):
                self.main_window.set_status(f"Exported logs to {filepath}")
            else:
                self.main_window.set_status("Failed to export logs", 'danger')
    
    def _view_html_report(self):
        """Open HTML report in browser."""
        if not self.current_stats:
            return
        
        output_dir = self.main_window.run_panel.output_dir.get()
        report_path = os.path.join(output_dir, 'report.html')
        
        if os.path.exists(report_path):
            webbrowser.open(f'file://{os.path.abspath(report_path)}')
        else:
            # Generate report on the fly
            processor = self.main_window.processor
            if processor.generate_report(self.current_stats, report_path, format='html'):
                webbrowser.open(f'file://{os.path.abspath(report_path)}')
    
    def _open_output_folder(self):
        """Open the output folder in file explorer."""
        output_dir = self.main_window.run_panel.output_dir.get()
        if output_dir and os.path.exists(output_dir):
            self._open_folder(output_dir)
        else:
            messagebox.showwarning("Output Folder", "Output folder does not exist or is not set.")
    
    def _clear_logs(self):
        """Clear all logs."""
        self.results_tree.delete(*self.results_tree.get_children())
        self.errors_tree.delete(*self.errors_tree.get_children())
        self.summary_text.delete(1.0, tk.END)
        
        self._update_stat_card(self.total_card, "0")
        self._update_stat_card(self.success_card, "0")
        self._update_stat_card(self.failed_card, "0")
        self._update_stat_card(self.duration_card, "0s")
        
        self.current_stats = None
        self.main_window.set_status("Logs cleared")
    
    def _new_batch(self):
        """Start a new batch."""
        self.main_window.notebook.select(0)  # Go to input tab
        self.main_window.set_status("Ready for new batch")
    
    def _on_result_double_click(self, event):
        """Handle double-click on result to open file."""
        self._open_selected_file()
    
    def _show_context_menu(self, event):
        """Show context menu on right-click."""
        # Select the item under cursor
        item = self.results_tree.identify_row(event.y)
        if item:
            self.results_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def _get_selected_output_path(self):
        """Get the output path of the selected item."""
        selection = self.results_tree.selection()
        if not selection:
            return None
        
        item_id = selection[0]
        return self.output_files.get(item_id)
    
    def _open_selected_file(self):
        """Open the selected output file."""
        output_path = self._get_selected_output_path()
        
        if not output_path:
            # Try to get from output directory
            selection = self.results_tree.selection()
            if selection:
                values = self.results_tree.item(selection[0], 'values')
                if values:
                    filename = values[0]
                    output_dir = self.main_window.run_panel.output_dir.get()
                    output_path = os.path.join(output_dir, filename)
        
        if output_path and os.path.exists(output_path):
            self._open_file(output_path)
            self.main_window.set_status(f"Opened: {os.path.basename(output_path)}")
        else:
            self.main_window.set_status("File not found", 'warning')
    
    def _open_containing_folder(self):
        """Open the folder containing the selected file."""
        output_path = self._get_selected_output_path()
        
        if not output_path:
            # Use output directory
            output_path = self.main_window.run_panel.output_dir.get()
        
        if output_path:
            folder = os.path.dirname(output_path) if os.path.isfile(output_path) else output_path
            if os.path.exists(folder):
                self._open_folder(folder)
                self.main_window.set_status(f"Opened folder: {folder}")
            else:
                self.main_window.set_status("Folder not found", 'warning')
    
    def _copy_file_path(self):
        """Copy the file path to clipboard."""
        output_path = self._get_selected_output_path()
        
        if output_path:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(output_path)
            self.main_window.set_status(f"Copied: {output_path}")
    
    def _open_file(self, filepath):
        """Open a file with the default application."""
        try:
            if sys.platform == 'win32':
                os.startfile(filepath)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filepath])
            else:
                subprocess.run(['xdg-open', filepath])
        except Exception as e:
            self.main_window.set_status(f"Error opening file: {e}", 'danger')
    
    def _open_folder(self, folder):
        """Open a folder in file explorer."""
        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.run(['open', folder])
            else:
                subprocess.run(['xdg-open', folder])
        except Exception as e:
            self.main_window.set_status(f"Error opening folder: {e}", 'danger')
