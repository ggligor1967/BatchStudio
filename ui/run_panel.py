"""
BatchStudio - Run Panel
Batch execution interface with progress tracking.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
from copy import deepcopy
from datetime import datetime

from core import BatchProcessor
from core.processor import compile_workflow
from ui.input_support import InputCapabilityRegistry, get_input_error


class RunPanel:
    """Run panel for batch execution."""
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)
        self.processor = BatchProcessor()
        self.is_running = False
        self.current_stats = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create panel widgets."""
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title = ttk.Label(header_frame, text="Run Batch Processing",
                         style='Heading.TLabel')
        title.pack(side=tk.LEFT)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.frame, text="Processing Settings", padding=15)
        settings_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Output directory
        output_dir_frame = ttk.Frame(settings_frame)
        output_dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(output_dir_frame, text="Output Directory:",
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        
        self.output_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "BatchStudio_Output"))
        ttk.Entry(output_dir_frame, textvariable=self.output_dir,
                 width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(output_dir_frame, text="Browse...",
                  command=self._browse_output).pack(side=tk.LEFT, padx=5)
        
        # Naming pattern
        naming_frame = ttk.Frame(settings_frame)
        naming_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(naming_frame, text="Naming Pattern:",
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        
        self.naming_pattern = tk.StringVar(value="{original}_processed")
        ttk.Entry(naming_frame, textvariable=self.naming_pattern,
                 width=30).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(naming_frame,
                 text="Use: {original}, {timestamp}, {counter}",
                 foreground='gray').pack(side=tk.LEFT, padx=5)
        
        # Options
        options_frame = ttk.Frame(settings_frame)
        options_frame.pack(fill=tk.X, pady=10)
        
        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="🔍 Dry Run (preview only)",
                       variable=self.dry_run_var).pack(side=tk.LEFT, padx=10)
        
        self.generate_report_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="📊 Generate Report",
                       variable=self.generate_report_var).pack(side=tk.LEFT, padx=10)
        
        # Worker threads
        threads_frame = ttk.Frame(settings_frame)
        threads_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(threads_frame, text="Parallel Workers:",
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        
        self.workers_var = tk.IntVar(value=4)
        ttk.Spinbox(threads_frame, from_=1, to=16, textvariable=self.workers_var,
                   width=10).pack(side=tk.LEFT, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(self.frame, text="Processing Progress", padding=15)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Status
        self.status_label = ttk.Label(progress_frame,
                                     text="Ready to process",
                                     font=('Segoe UI', 11, 'bold'))
        self.status_label.pack(pady=10)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate',
                                           length=600)
        self.progress_bar.pack(pady=10, fill=tk.X)
        
        # Progress text
        self.progress_label = ttk.Label(progress_frame, text="0 / 0 files")
        self.progress_label.pack()
        
        # Log display
        log_frame = ttk.Frame(progress_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=15, wrap=tk.WORD,
                               font=('Consolas', 9), yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.config(command=self.log_text.yview)
        
        # Configure text tags for colored output
        self.log_text.tag_config('success', foreground='#27ae60')
        self.log_text.tag_config('error', foreground='#e74c3c')
        self.log_text.tag_config('info', foreground='#3498db')
        self.log_text.tag_config('warning', foreground='#f39c12')
        
        # Control buttons
        control_frame = ttk.Frame(self.frame)
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.start_button = ttk.Button(control_frame, text="▶️ Start Processing",
                                      command=self._start_processing,
                                      style='Primary.TButton')
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(control_frame, text="⏸️ Pause",
                                      command=self._pause_processing,
                                      state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="⏹️ Stop",
                                     command=self._stop_processing,
                                     state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="📊 View Results ➡️",
                  command=self._view_results).pack(side=tk.RIGHT, padx=5)
    
    def _browse_output(self):
        """Browse for output directory."""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir.set(directory)
    
    def _log(self, message: str, tag: str = None):
        """Add message to log."""
        if threading.current_thread() is not threading.main_thread():
            self.frame.after(0, self._log, message, tag)
            return

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_message, tag)
        self.log_text.see(tk.END)
        self.log_text.update_idletasks()
    
    def _update_progress(self, current: int, total: int, message: str = ""):
        """Update progress display."""
        if threading.current_thread() is not threading.main_thread():
            self.frame.after(0, self._update_progress, current, total, message)
            return

        if total > 0:
            percentage = (current / total) * 100
            self.progress_bar['value'] = percentage
            self.progress_label.config(text=f"{current} / {total} files ({percentage:.1f}%)")
        
        if message:
            # Determine tag based on emoji/content
            tag = None
            if '✅' in message:
                tag = 'success'
            elif '❌' in message:
                tag = 'error'
            elif '🔍' in message or '🚀' in message:
                tag = 'info'
            
            self._log(message, tag)
    
    def _start_processing(self):
        """Start batch processing."""
        files = self.main_window.get_files()
        workflow = self.main_window.get_workflow()
        
        if not files:
            messagebox.showwarning("No Files", "Please select files in the Input tab first!")
            self.main_window.notebook.select(0)
            return
        
        if not workflow or not workflow.steps:
            messagebox.showwarning("No Workflow", "Please create a workflow in the Workflow tab first!")
            self.main_window.notebook.select(1)
            return
        
        output_dir = self.output_dir.get()
        if not output_dir:
            messagebox.showwarning("No Output", "Please select an output directory!")
            return
        
        dry_run = self.dry_run_var.get()
        naming_pattern = self.naming_pattern.get()
        workers = self.workers_var.get()
        generate_report = self.generate_report_var.get()
        files = list(files)
        workflow = deepcopy(workflow)

        # Clear log
        self.log_text.delete(1.0, tk.END)
        
        # Update UI state
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        
        # Configure processor
        self.processor = BatchProcessor(max_workers=workers)
        self.main_window.processor = self.processor
        self.processor.set_progress_callback(self._update_progress)
        
        # Log start
        self._log("="*60, 'info')
        self._log(f"Checking batch availability: {workflow.name}", 'info')
        self._log(f"Files: {len(files)}", 'info')
        self._log(f"Steps: {len(workflow.steps)}", 'info')
        self._log(f"Output: {output_dir}", 'info')
        if dry_run:
            self._log("Mode: DRY RUN (no files will be modified)", 'warning')
        self._log("="*60, 'info')
        
        self.status_label.config(text="Checking input and workflow availability...")
        
        # Start processing in separate thread
        thread = threading.Thread(target=self._run_batch,
                                 args=(files, workflow, output_dir, naming_pattern, dry_run, generate_report))
        thread.daemon = True
        thread.start()
    
    def _run_batch(self, files, workflow, output_dir, naming_pattern, dry_run, generate_report):
        """Run batch processing (in separate thread)."""
        try:
            valid, error = workflow.validate()
            if not valid:
                self.frame.after(0, self._processing_error, f"Invalid workflow: {error}")
                return
            registry = InputCapabilityRegistry()
            for file_path in files:
                error = get_input_error(file_path, workflow, registry)
                if error:
                    self.frame.after(
                        0, self._processing_error, f"{os.path.basename(file_path)}: {error}"
                    )
                    return
            compilation = compile_workflow(workflow, registry)
            if not compilation.valid:
                self.frame.after(0, self._processing_error, "\n".join(compilation.errors))
                return
            self.frame.after(0, self._processing_started)
            stats = self.processor.process_batch(
                files, workflow, output_dir, naming_pattern=naming_pattern, dry_run=dry_run
            )

            # Update UI from main thread
            self.frame.after(0, self._processing_complete, stats, output_dir, generate_report)

        except Exception as e:
            self.frame.after(0, self._processing_error, str(e))
    
    def _processing_started(self):
        self.status_label.config(text="🚀 Processing in progress...")
        self.pause_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)

    def _processing_complete(self, stats, output_dir, generate_report):
        """Handle processing completion."""
        self.current_stats = stats
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        
        # Log summary
        self._log("="*60, 'info')
        self._log("Processing complete!", 'success')
        self._log(f"✅ Processed: {stats.processed_files}", 'success')
        if stats.failed_files > 0:
            self._log(f"❌ Failed: {stats.failed_files}", 'error')
        self._log(f"⏱️ Duration: {stats.get_duration():.1f} seconds", 'info')
        self._log("="*60, 'info')
        
        if (
            not stats.dry_run
            and stats.total_files > 0
            and stats.failed_files == 0
            and stats.processed_files == stats.total_files
        ):
            self._show_confetti()
        
        # Generate report
        if generate_report and not stats.dry_run:
            report_path = os.path.join(output_dir, 'report.html')
            if self.processor.generate_report(stats, report_path, format='html'):
                self._log(f"📊 Report generated: {report_path}", 'info')
        
        self.status_label.config(text="✅ Processing complete!")
        
        messagebox.showinfo("Complete",
                          f"Batch processing complete!\n\n"
                          f"Processed: {stats.processed_files}\n"
                          f"Failed: {stats.failed_files}\n"
                          f"Duration: {stats.get_duration():.1f}s")
    
    def _processing_error(self, error):
        """Handle processing error."""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        
        self._log(f"❌ Error: {error}", 'error')
        self.status_label.config(text="❌ Processing failed!")
        
        messagebox.showerror("Error", f"Processing failed:\n\n{error}")
    
    def _pause_processing(self):
        """Pause processing."""
        if self.processor.is_paused:
            self.processor.resume()
            self.pause_button.config(text="⏸️ Pause")
            self._log("▶️ Resumed processing", 'info')
        else:
            self.processor.pause()
            self.pause_button.config(text="▶️ Resume")
            self._log("⏸️ Paused processing", 'warning')
    
    def _stop_processing(self):
        """Stop processing."""
        if messagebox.askyesno("Stop Processing",
                              "Are you sure you want to stop processing?"):
            self.processor.stop()
            self._log("⏹️ Processing stopped by user", 'warning')
    
    def _show_confetti(self):
        """Show confetti animation (Easter egg!)."""
        confetti_window = tk.Toplevel(self.main_window.root)
        confetti_window.title("Success!")
        confetti_window.geometry("400x300")
        confetti_window.resizable(False, False)
        
        canvas = tk.Canvas(confetti_window, bg='white')
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Draw confetti
        import random
        colors = ['#667eea', '#764ba2', '#27ae60', '#f39c12', '#e74c3c']
        
        for _ in range(50):
            x = random.randint(0, 400)
            y = random.randint(0, 300)
            color = random.choice(colors)
            size = random.randint(5, 15)
            canvas.create_oval(x, y, x+size, y+size, fill=color, outline='')
        
        # Success message
        canvas.create_text(200, 150, text="🎉 Success! 🎉",
                          font=('Segoe UI', 24, 'bold'),
                          fill='#667eea')
        
        # Close button
        ttk.Button(confetti_window, text="Close",
                  command=confetti_window.destroy).pack(pady=20)
        
        # Auto-close after 3 seconds
        confetti_window.after(3000, confetti_window.destroy)
    
    def _view_results(self):
        """View results in logs tab."""
        self.main_window.notebook.select(3)  # Switch to logs tab
        if self.current_stats:
            self.main_window.logs_panel.show_stats(self.current_stats)
