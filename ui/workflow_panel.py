"""
BatchStudio - Workflow Panel
Workflow builder interface with button-based step ordering.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json

from core import Workflow, WorkflowTemplates, OperationRegistry


class WorkflowPanel:
    """Workflow builder panel."""
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.frame = ttk.Frame(parent)
        self.current_workflow = Workflow()
        self.operation_registry = OperationRegistry()
        
        self._create_widgets()
        self._load_operations()
    
    def _create_widgets(self):
        """Create panel widgets."""
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title = ttk.Label(header_frame, text="Build Your Workflow",
                         style='Heading.TLabel')
        title.pack(side=tk.LEFT)
        
        # Workflow name
        name_frame = ttk.Frame(header_frame)
        name_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(name_frame, text="Workflow Name:").pack(side=tk.LEFT, padx=5)
        self.workflow_name = ttk.Entry(name_frame, width=30)
        self.workflow_name.insert(0, "Untitled Workflow")
        self.workflow_name.pack(side=tk.LEFT)
        
        # Main content with three columns
        content_frame = ttk.Frame(self.frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left: Available operations
        ops_frame = ttk.LabelFrame(content_frame, text="Available Operations", padding=10)
        ops_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Templates
        ttk.Label(ops_frame, text="Templates:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W)
        
        self.templates_listbox = tk.Listbox(ops_frame, height=6, font=('Segoe UI', 9))
        self.templates_listbox.pack(fill=tk.X, pady=5)
        self.templates_listbox.bind('<Double-Button-1>', self._load_template)
        
        ttk.Separator(ops_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Operations
        ttk.Label(ops_frame, text="Operations:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W)

        ttk.Button(ops_frame, text="Refresh OCR availability",
                   command=self._load_operations).pack(fill=tk.X, pady=5)
        
        ops_scroll = ttk.Scrollbar(ops_frame)
        ops_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.operations_listbox = tk.Listbox(ops_frame, yscrollcommand=ops_scroll.set,
                                            font=('Segoe UI', 9))
        self.operations_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ops_scroll.config(command=self.operations_listbox.yview)
        
        ttk.Button(ops_frame, text="➕ Add to Workflow",
                  command=self._add_operation).pack(pady=10, fill=tk.X)
        
        # Middle: Current workflow steps
        workflow_frame = ttk.LabelFrame(content_frame, text="Workflow Steps", padding=10)
        workflow_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        steps_scroll = ttk.Scrollbar(workflow_frame)
        steps_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.steps_listbox = tk.Listbox(workflow_frame, yscrollcommand=steps_scroll.set,
                                       font=('Segoe UI', 10), selectmode=tk.SINGLE)
        self.steps_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        steps_scroll.config(command=self.steps_listbox.yview)
        self.steps_listbox.bind('<<ListboxSelect>>', self._on_step_select)
        
        # Step controls
        controls_frame = ttk.Frame(workflow_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(controls_frame, text="⬆️ Move Up",
                  command=self._move_step_up).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        
        ttk.Button(controls_frame, text="⬇️ Move Down",
                  command=self._move_step_down).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        
        ttk.Button(controls_frame, text="🗑️ Remove",
                  command=self._remove_step).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        
        # Right: Step configuration
        config_frame = ttk.LabelFrame(content_frame, text="Step Configuration", padding=10)
        config_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Scrollable config area
        config_canvas = tk.Canvas(config_frame, highlightthickness=0)
        config_scroll = ttk.Scrollbar(config_frame, orient="vertical", command=config_canvas.yview)
        self.config_container = ttk.Frame(config_canvas)
        
        config_canvas.create_window((0, 0), window=self.config_container, anchor="nw")
        config_canvas.configure(yscrollcommand=config_scroll.set)
        
        config_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        config_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.config_container.bind("<Configure>",
                                  lambda e: config_canvas.configure(scrollregion=config_canvas.bbox("all")))
        
        self.config_widgets = {}
        
        ttk.Label(self.config_container,
                 text="Select a step to configure",
                 foreground='gray').pack(pady=20)
        
        # Bottom: Action buttons
        action_frame = ttk.Frame(self.frame)
        action_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(action_frame, text="💾 Save Workflow",
                  command=self.save_workflow).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="📂 Load Workflow",
                  command=self.load_workflow).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="🆕 New Workflow",
                  command=self.create_new_workflow).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="Next: Run Batch ➡️",
                  command=self._go_to_run,
                  style='Primary.TButton').pack(side=tk.RIGHT)
    
    def _load_operations(self):
        """Load available operations and templates."""
        self.templates_listbox.delete(0, tk.END)
        self.operations_listbox.delete(0, tk.END)
        # Load templates
        templates = WorkflowTemplates.list_templates()
        for template in templates:
            self.templates_listbox.insert(tk.END, f"📋 {template['name']}")
        
        # Load operations
        operations = self.operation_registry.list_operations()
        for op in operations:
            status = self.operation_registry.get_capability_status(op['id'])
            suffix = f" — {status}" if status else ""
            self.operations_listbox.insert(tk.END, f"🔧 {op['name']}{suffix}")
    
    def _add_operation(self):
        """Add selected operation to workflow."""
        selection = self.operations_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an operation first!")
            return
        
        operations = self.operation_registry.list_operations()
        op = operations[selection[0]]
        
        step = self.current_workflow.add_step(op['id'])
        self._refresh_steps()
        self.main_window.set_status(f"Added {op['name']} to workflow")
    
    def _remove_step(self):
        """Remove selected step from workflow."""
        selection = self.steps_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        self.current_workflow.remove_step(index)
        self._refresh_steps()
        self.main_window.set_status("Removed step from workflow")
    
    def _move_step_up(self):
        """Move selected step up."""
        selection = self.steps_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        
        index = selection[0]
        self.current_workflow.move_step(index, index - 1)
        self._refresh_steps()
        self.steps_listbox.selection_clear(0, tk.END)
        self.steps_listbox.selection_set(index - 1)
    
    def _move_step_down(self):
        """Move selected step down."""
        selection = self.steps_listbox.curselection()
        if not selection or selection[0] >= len(self.current_workflow.steps) - 1:
            return
        
        index = selection[0]
        self.current_workflow.move_step(index, index + 1)
        self._refresh_steps()
        self.steps_listbox.selection_clear(0, tk.END)
        self.steps_listbox.selection_set(index + 1)
    
    def _refresh_steps(self):
        """Refresh workflow steps display."""
        self.steps_listbox.delete(0, tk.END)
        
        for i, step in enumerate(self.current_workflow.steps):
            operation = self.operation_registry.get_operation(step.operation_id)
            if operation is None:
                operation = self.operation_registry.get_aggregate_operation(step.operation_id)
            if operation is None:
                continue
            status = "✅" if step.enabled else "⏸️"
            self.steps_listbox.insert(tk.END, f"{i+1}. {status} {operation.name}")
    
    def _on_step_select(self, event):
        """Handle step selection."""
        selection = self.steps_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        step = self.current_workflow.steps[index]
        self._show_step_config(step)
    
    def _show_step_config(self, step):
        """Show configuration for selected step."""
        # Clear previous config
        for widget in self.config_container.winfo_children():
            widget.destroy()
        
        self.config_widgets = {}
        
        operation = self.operation_registry.get_operation(step.operation_id)
        if operation is None:
            operation = self.operation_registry.get_aggregate_operation(step.operation_id)
        if operation is None:
            ttk.Label(self.config_container, text="Unknown operation", foreground='red').pack(pady=10)
            return
        schema = operation.get_config_schema()
        
        ttk.Label(self.config_container,
                 text=f"Configure: {operation.name}",
                 font=('Segoe UI', 11, 'bold')).pack(pady=10, anchor=tk.W)

        if step.operation_id in {'ocr_image', 'ocr_pdf', 'ocr_batch'}:
            status = ttk.Label(self.config_container, wraplength=300, justify=tk.LEFT)
            status.pack(fill=tk.X, pady=5)

            def refresh_capability():
                status.config(text=self.operation_registry.get_capability_status(
                    step.operation_id, step.config,
                ))

            refresh_capability()
            ttk.Button(self.config_container, text="Refresh OCR availability",
                       command=refresh_capability).pack(fill=tk.X, pady=5)
        
        if not schema:
            ttk.Label(self.config_container,
                     text="No configuration needed for this operation",
                     foreground='gray').pack(pady=10)
            return
        
        # Create config widgets
        for key, config in schema.items():
            frame = ttk.Frame(self.config_container)
            frame.pack(fill=tk.X, pady=5)
            
            label_text = config.get('label', key)
            if config.get('optional'):
                label_text += " (optional)"
            
            ttk.Label(frame, text=label_text).pack(side=tk.LEFT, padx=5)
            
            widget_type = config.get('type')
            default = step.config.get(key, config.get('default'))
            
            if widget_type == 'bool':
                var = tk.BooleanVar(value=default)
                widget = ttk.Checkbutton(frame, variable=var)
                widget.pack(side=tk.RIGHT, padx=5)
                self.config_widgets[key] = ('bool', var)
            
            elif widget_type == 'choice':
                var = tk.StringVar(value=default)
                widget = ttk.Combobox(frame, textvariable=var,
                                     values=config.get('choices', []),
                                     state='readonly', width=20)
                widget.pack(side=tk.RIGHT, padx=5)
                self.config_widgets[key] = ('choice', var)
            
            elif widget_type == 'int':
                var = tk.IntVar(value=default)
                widget = ttk.Spinbox(frame, from_=0, to=10000,
                                    textvariable=var, width=15)
                widget.pack(side=tk.RIGHT, padx=5)
                self.config_widgets[key] = ('int', var)
            
            elif widget_type == 'float':
                var = tk.DoubleVar(value=default)
                widget = ttk.Entry(frame, textvariable=var, width=15)
                widget.pack(side=tk.RIGHT, padx=5)
                self.config_widgets[key] = ('float', var)
            
            else:  # str
                var = tk.StringVar(value=default)
                widget = ttk.Entry(frame, textvariable=var, width=25)
                widget.pack(side=tk.RIGHT, padx=5)
                self.config_widgets[key] = ('str', var)
        
        # Apply button
        ttk.Button(self.config_container, text="✅ Apply Configuration",
                  command=lambda: self._apply_config(step)).pack(pady=15, fill=tk.X)
    
    def _apply_config(self, step):
        """Apply configuration changes."""
        for key, (widget_type, var) in self.config_widgets.items():
            step.config[key] = var.get()

        if step.operation_id in {'ocr_image', 'ocr_pdf', 'ocr_batch'}:
            self._show_step_config(step)
        
        self.main_window.set_status("Configuration applied")
        messagebox.showinfo("Success", "Configuration updated successfully!")
    
    def _load_template(self, event):
        """Load a workflow template."""
        selection = self.templates_listbox.curselection()
        if not selection:
            return
        
        templates = WorkflowTemplates.list_templates()
        template = templates[selection[0]]
        
        if messagebox.askyesno("Load Template",
                              f"Load template '{template['name']}'?\n\n"
                              f"{template['description']}\n\n"
                              "This will replace your current workflow."):
            
            workflow = WorkflowTemplates.get_template(template['id'])
            if workflow:
                self.current_workflow = workflow
                self.workflow_name.delete(0, tk.END)
                self.workflow_name.insert(0, workflow.name)
                self._refresh_steps()
                self.main_window.set_workflow(workflow)
                self.main_window.set_status(f"Loaded template: {template['name']}")
    
    def create_new_workflow(self):
        """Create a new workflow."""
        if self.current_workflow.steps:
            if not messagebox.askyesno("New Workflow",
                                      "Create new workflow? Current workflow will be lost."):
                return
        
        self.current_workflow = Workflow()
        self.workflow_name.delete(0, tk.END)
        self.workflow_name.insert(0, "Untitled Workflow")
        self._refresh_steps()
        self.main_window.set_workflow(None)
        self.main_window.set_status("Created new workflow")
    
    def save_workflow(self):
        """Save current workflow."""
        name = self.workflow_name.get().strip()
        if not name:
            messagebox.showwarning("No Name", "Please enter a workflow name!")
            return
        
        self.current_workflow.name = name
        
        filepath = filedialog.asksaveasfilename(
            title="Save Workflow",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{name}.json"
        )
        
        if filepath:
            if self.current_workflow.save_to_file(filepath):
                self.main_window.set_status(f"Saved workflow to {filepath}")
                messagebox.showinfo("Success", "Workflow saved successfully!")
            else:
                messagebox.showerror("Error", "Failed to save workflow!")
    
    def load_workflow(self):
        """Load a workflow from file."""
        filepath = filedialog.askopenfilename(
            title="Load Workflow",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            workflow = Workflow.load_from_file(filepath)
            if workflow:
                self.current_workflow = workflow
                self.workflow_name.delete(0, tk.END)
                self.workflow_name.insert(0, workflow.name)
                self._refresh_steps()
                self.main_window.set_workflow(workflow)
                self.main_window.set_status(f"Loaded workflow: {workflow.name}")
                messagebox.showinfo("Success", "Workflow loaded successfully!")
            else:
                messagebox.showerror("Error", "Failed to load workflow!")
    
    def _go_to_run(self):
        """Navigate to run tab."""
        if not self.current_workflow.steps:
            messagebox.showwarning("Empty Workflow",
                                  "Please add some operations to your workflow first!")
            return
        
        # Update workflow name
        self.current_workflow.name = self.workflow_name.get().strip()
        self.main_window.set_workflow(self.current_workflow)
        
        self.main_window.notebook.select(2)  # Switch to run tab
        self.main_window.set_status("Ready to run batch →")
