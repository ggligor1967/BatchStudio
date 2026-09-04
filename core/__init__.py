"""
BatchStudio - Core Module
Contains the core processing logic, workflow management, and operations.
"""

from core.processor import (
    BatchProcessor,
    ProcessingStats,
    validate_file_path,
    validate_output_directory,
    process_single_file,
    compile_workflow,
    WorkflowCompilation,
    MAX_FILE_SIZE,
    ALLOWED_EXTENSIONS
)
from core.workflow import Workflow, WorkflowManager, WorkflowTemplates
from core.operations import OperationRegistry, Operation
from core.settings import Settings, get_settings

__all__ = [
    'BatchProcessor',
    'ProcessingStats',
    'validate_file_path',
    'validate_output_directory',
    'process_single_file',
    'compile_workflow',
    'WorkflowCompilation',
    'MAX_FILE_SIZE',
    'ALLOWED_EXTENSIONS',
    'Workflow',
    'WorkflowManager',
    'WorkflowTemplates',
    'OperationRegistry',
    'Operation',
    'Settings',
    'get_settings'
]
