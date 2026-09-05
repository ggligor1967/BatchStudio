"""
BatchStudio - Workflow Module
Manages workflow creation, saving, loading, and execution.
"""

import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime


class WorkflowStep:
    """Represents a single step in a workflow."""
    
    def __init__(self, operation_id: str, config: Optional[Dict[str, Any]] = None):
        self.operation_id = operation_id
        self.config = config or {}
        self.enabled = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'operation_id': self.operation_id,
            'config': self.config,
            'enabled': self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowStep':
        step = cls(data['operation_id'], data.get('config'))
        step.enabled = data.get('enabled', True)
        return step


class Workflow:
    """Represents a complete workflow with multiple steps."""
    
    def __init__(self, name: str = "Untitled Workflow", description: str = ""):
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self.created_at = datetime.now().isoformat()
        self.modified_at = self.created_at
        self.metadata = {}
    
    def add_step(self, operation_id: str, config: Optional[Dict[str, Any]] = None) -> WorkflowStep:
        """Add a new step to the workflow."""
        step = WorkflowStep(operation_id, config)
        self.steps.append(step)
        self.modified_at = datetime.now().isoformat()
        return step
    
    def remove_step(self, index: int) -> bool:
        """Remove a step from the workflow."""
        if 0 <= index < len(self.steps):
            self.steps.pop(index)
            self.modified_at = datetime.now().isoformat()
            return True
        return False
    
    def move_step(self, from_index: int, to_index: int) -> bool:
        """Move a step to a different position."""
        if 0 <= from_index < len(self.steps) and 0 <= to_index < len(self.steps):
            step = self.steps.pop(from_index)
            self.steps.insert(to_index, step)
            self.modified_at = datetime.now().isoformat()
            return True
        return False
    
    def get_enabled_steps(self) -> List[WorkflowStep]:
        """Get only enabled steps."""
        return [step for step in self.steps if step.enabled]
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate the workflow."""
        if not self.steps:
            return False, "Workflow must contain at least one step"
        
        if not self.name.strip():
            return False, "Workflow must have a name"

        for index, step in enumerate(self.steps, start=1):
            if not isinstance(step.operation_id, str) or not step.operation_id.strip():
                return False, f"Step {index} has invalid operation_id"
            if not isinstance(step.config, dict):
                return False, f"Step {index} has invalid config type"
        
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'steps': [step.to_dict() for step in self.steps],
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """Create workflow from dictionary."""
        workflow = cls(data['name'], data.get('description', ''))
        workflow.steps = [WorkflowStep.from_dict(step_data) for step_data in data['steps']]
        workflow.created_at = data.get('created_at', datetime.now().isoformat())
        workflow.modified_at = data.get('modified_at', workflow.created_at)
        workflow.metadata = data.get('metadata', {})
        return workflow
    
    def save_to_file(self, filepath: str) -> bool:
        """Save workflow to JSON file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving workflow: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: str) -> Optional['Workflow']:
        """Load workflow from JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"Error loading workflow: {e}")
            return None


class WorkflowTemplates:
    """Pre-built workflow templates."""
    
    @staticmethod
    def get_template(template_id: str) -> Optional[Workflow]:
        """Get a workflow template by ID."""
        templates = {
            'image_resizer': WorkflowTemplates._image_resizer_template(),
            'image_converter': WorkflowTemplates._image_converter_template(),
            'pdf_watermarker': WorkflowTemplates._pdf_watermarker_template(),
            'csv_cleaner': WorkflowTemplates._csv_cleaner_template(),
            'batch_renamer': WorkflowTemplates._batch_renamer_template(),
            'photo_optimizer': WorkflowTemplates._photo_optimizer_template(),
            # New templates
            'social_media_instagram': WorkflowTemplates._social_media_instagram_template(),
            'social_media_facebook': WorkflowTemplates._social_media_facebook_template(),
            'thumbnail_generator': WorkflowTemplates._thumbnail_generator_template(),
            'ecommerce_product': WorkflowTemplates._ecommerce_product_template(),
            'email_attachment': WorkflowTemplates._email_attachment_template(),
            'vintage_effect': WorkflowTemplates._vintage_effect_template(),
            'document_archive': WorkflowTemplates._document_archive_template(),
            'print_preparation': WorkflowTemplates._print_preparation_template(),
            'mobile_wallpaper': WorkflowTemplates._mobile_wallpaper_template(),
            'data_anonymizer': WorkflowTemplates._data_anonymizer_template(),
            # OCR templates
            'ocr_document_scanner': WorkflowTemplates._ocr_document_scanner_template(),
            'ocr_invoice_extractor': WorkflowTemplates._ocr_invoice_extractor_template(),
            'ocr_book_digitizer': WorkflowTemplates._ocr_book_digitizer_template(),
            'ocr_multilingual': WorkflowTemplates._ocr_multilingual_template(),
        }
        return templates.get(template_id)
    
    @staticmethod
    def list_templates() -> List[Dict[str, str]]:
        """List all available templates."""
        return [
            {
                'id': 'image_resizer',
                'name': 'Image Resizer',
                'description': 'Resize images to specific dimensions while maintaining quality',
                'category': 'Images'
            },
            {
                'id': 'image_converter',
                'name': 'Image Format Converter',
                'description': 'Convert images to different formats (PNG, JPEG, WEBP)',
                'category': 'Images'
            },
            {
                'id': 'pdf_watermarker',
                'name': 'PDF Watermarker',
                'description': 'Add watermarks to PDF documents',
                'category': 'PDF'
            },
            {
                'id': 'csv_cleaner',
                'name': 'CSV Data Cleaner',
                'description': 'Filter and clean CSV data files',
                'category': 'Data'
            },
            {
                'id': 'batch_renamer',
                'name': 'Batch File Renamer',
                'description': 'Rename multiple files with custom patterns',
                'category': 'Files'
            },
            {
                'id': 'photo_optimizer',
                'name': 'Photo Optimizer',
                'description': 'Optimize photos for web (resize + convert + compress)',
                'category': 'Images'
            },
            # New templates
            {
                'id': 'social_media_instagram',
                'name': 'Instagram Post Ready',
                'description': 'Prepare images for Instagram posts (1080x1080, enhanced colors)',
                'category': 'Social Media'
            },
            {
                'id': 'social_media_facebook',
                'name': 'Facebook Cover Photo',
                'description': 'Create Facebook cover photos (820x312) with sharpening',
                'category': 'Social Media'
            },
            {
                'id': 'thumbnail_generator',
                'name': 'YouTube Thumbnail',
                'description': 'Generate YouTube thumbnails (1280x720) with contrast boost',
                'category': 'Social Media'
            },
            {
                'id': 'ecommerce_product',
                'name': 'E-commerce Product Photos',
                'description': 'Standardize product images (800x800, white background ready)',
                'category': 'E-commerce'
            },
            {
                'id': 'email_attachment',
                'name': 'Email Attachment Optimizer',
                'description': 'Compress images for email attachments (max 1024px, JPEG 70%)',
                'category': 'Productivity'
            },
            {
                'id': 'vintage_effect',
                'name': 'Vintage Photo Effect',
                'description': 'Apply vintage/retro effect (grayscale + contrast + emboss)',
                'category': 'Creative'
            },
            {
                'id': 'document_archive',
                'name': 'Document Archival',
                'description': 'Prepare documents for archiving with DRAFT watermark',
                'category': 'PDF'
            },
            {
                'id': 'print_preparation',
                'name': 'Print-Ready Images',
                'description': 'Prepare high-quality images for printing (300 DPI, TIFF)',
                'category': 'Print'
            },
            {
                'id': 'mobile_wallpaper',
                'name': 'Mobile Wallpaper Creator',
                'description': 'Create smartphone wallpapers (1080x1920, enhanced)',
                'category': 'Mobile'
            },
            {
                'id': 'data_anonymizer',
                'name': 'CSV Data Anonymizer',
                'description': 'Filter sensitive data from CSV files (exclude PII columns)',
                'category': 'Data'
            },
            # OCR Templates
            {
                'id': 'ocr_document_scanner',
                'name': 'Document Scanner OCR',
                'description': 'Extract text from scanned documents (images)',
                'category': 'OCR'
            },
            {
                'id': 'ocr_invoice_extractor',
                'name': 'Invoice Text Extractor',
                'description': 'Extract text from invoices and receipts',
                'category': 'OCR'
            },
            {
                'id': 'ocr_book_digitizer',
                'name': 'Book Page Digitizer',
                'description': 'Digitize book pages from PDF scans',
                'category': 'OCR'
            },
            {
                'id': 'ocr_multilingual',
                'name': 'Multilingual OCR',
                'description': 'OCR for Romanian documents',
                'category': 'OCR'
            },
        ]
    
    @staticmethod
    def _image_resizer_template() -> Workflow:
        workflow = Workflow(
            name="Image Resizer",
            description="Resize images to 1920x1080 maintaining aspect ratio"
        )
        workflow.add_step('image_resize', {
            'width': 1920,
            'height': 1080,
            'maintain_aspect': True,
            'quality': 95
        })
        return workflow
    
    @staticmethod
    def _image_converter_template() -> Workflow:
        workflow = Workflow(
            name="Image Format Converter",
            description="Convert images to PNG format"
        )
        workflow.add_step('image_convert', {'format': 'PNG'})
        return workflow
    
    @staticmethod
    def _pdf_watermarker_template() -> Workflow:
        workflow = Workflow(
            name="PDF Watermarker",
            description="Add 'CONFIDENTIAL' watermark to PDFs"
        )
        workflow.add_step('pdf_watermark', {'text': 'CONFIDENTIAL'})
        return workflow
    
    @staticmethod
    def _csv_cleaner_template() -> Workflow:
        workflow = Workflow(
            name="CSV Data Cleaner",
            description="Filter CSV data based on conditions"
        )
        workflow.add_step('csv_filter', {
            'column': 'status',
            'operator': '==',
            'value': 'active'
        })
        return workflow
    
    @staticmethod
    def _batch_renamer_template() -> Workflow:
        workflow = Workflow(
            name="Batch File Renamer",
            description="Rename files with pattern"
        )
        workflow.add_step('file_rename', {'pattern': '{original}_{counter}'})
        return workflow
    
    @staticmethod
    def _photo_optimizer_template() -> Workflow:
        workflow = Workflow(
            name="Photo Optimizer",
            description="Optimize photos for web use"
        )
        workflow.add_step('image_resize', {
            'width': 1200,
            'height': 800,
            'maintain_aspect': True,
            'quality': 85
        })
        workflow.add_step('image_filter', {
            'filter': 'SHARPEN'
        })
        workflow.add_step('image_convert', {'format': 'WEBP'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - Social Media
    # ============================================
    
    @staticmethod
    def _social_media_instagram_template() -> Workflow:
        """Instagram-optimized square images (1080x1080)."""
        workflow = Workflow(
            name="Instagram Post Ready",
            description="Prepare images for Instagram posts - 1080x1080 square format with enhanced colors"
        )
        workflow.add_step('image_resize', {
            'width': 1080,
            'height': 1080,
            'maintain_aspect': False,
            'quality': 95
        })
        workflow.add_step('image_filter', {
            'filter': 'SHARPEN',
            'contrast': 1.1,
            'brightness': 1.05
        })
        workflow.add_step('image_convert', {'format': 'JPEG'})
        workflow.add_step('file_rename', {'pattern': '{original}_instagram'})
        return workflow
    
    @staticmethod
    def _social_media_facebook_template() -> Workflow:
        """Facebook cover photo dimensions (820x312)."""
        workflow = Workflow(
            name="Facebook Cover Photo",
            description="Create Facebook cover photos - 820x312 with optimal sharpness"
        )
        workflow.add_step('image_resize', {
            'width': 820,
            'height': 312,
            'maintain_aspect': False,
            'quality': 90
        })
        workflow.add_step('image_filter', {
            'filter': 'SHARPEN'
        })
        workflow.add_step('image_convert', {'format': 'JPEG'})
        workflow.add_step('file_rename', {'pattern': '{original}_fb_cover'})
        return workflow
    
    @staticmethod
    def _thumbnail_generator_template() -> Workflow:
        """YouTube thumbnail generator (1280x720)."""
        workflow = Workflow(
            name="YouTube Thumbnail",
            description="Generate eye-catching YouTube thumbnails - 1280x720 with contrast boost"
        )
        workflow.add_step('image_resize', {
            'width': 1280,
            'height': 720,
            'maintain_aspect': False,
            'quality': 95
        })
        workflow.add_step('image_filter', {
            'filter': 'SHARPEN',
            'contrast': 1.2,
            'brightness': 1.05
        })
        workflow.add_step('image_convert', {'format': 'JPEG'})
        workflow.add_step('file_rename', {'pattern': '{original}_thumbnail'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - E-commerce
    # ============================================
    
    @staticmethod
    def _ecommerce_product_template() -> Workflow:
        """Standardized e-commerce product images."""
        workflow = Workflow(
            name="E-commerce Product Photos",
            description="Standardize product images for online stores - 800x800 square format"
        )
        workflow.add_step('image_resize', {
            'width': 800,
            'height': 800,
            'maintain_aspect': True,
            'quality': 95
        })
        workflow.add_step('image_filter', {
            'filter': 'SHARPEN',
            'brightness': 1.05
        })
        workflow.add_step('image_convert', {'format': 'PNG'})
        workflow.add_step('file_rename', {'pattern': 'product_{counter}'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - Productivity
    # ============================================
    
    @staticmethod
    def _email_attachment_template() -> Workflow:
        """Compress images for email attachments."""
        workflow = Workflow(
            name="Email Attachment Optimizer",
            description="Compress images for email - max 1024px, JPEG 70% quality (under 500KB)"
        )
        workflow.add_step('image_resize', {
            'width': 1024,
            'height': 1024,
            'maintain_aspect': True,
            'quality': 70
        })
        workflow.add_step('image_convert', {'format': 'JPEG'})
        workflow.add_step('file_rename', {'pattern': '{original}_email'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - Creative
    # ============================================
    
    @staticmethod
    def _vintage_effect_template() -> Workflow:
        """Apply vintage/retro photo effect."""
        workflow = Workflow(
            name="Vintage Photo Effect",
            description="Transform photos with a classic vintage look - grayscale with artistic effects"
        )
        workflow.add_step('image_filter', {
            'filter': 'GRAYSCALE'
        })
        workflow.add_step('image_filter', {
            'contrast': 1.3,
            'brightness': 0.95,
            'filter': 'SMOOTH'
        })
        workflow.add_step('image_convert', {'format': 'JPEG'})
        workflow.add_step('file_rename', {'pattern': '{original}_vintage'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - PDF & Documents
    # ============================================
    
    @staticmethod
    def _document_archive_template() -> Workflow:
        """Prepare documents for archival with watermark."""
        workflow = Workflow(
            name="Document Archival",
            description="Prepare PDFs for archiving - adds ARCHIVED watermark"
        )
        workflow.add_step('pdf_watermark', {'text': 'ARCHIVED'})
        workflow.add_step('file_rename', {'pattern': '{original}_archived_{timestamp}'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - Print
    # ============================================
    
    @staticmethod
    def _print_preparation_template() -> Workflow:
        """Prepare high-quality images for professional printing."""
        workflow = Workflow(
            name="Print-Ready Images",
            description="Prepare images for high-quality printing - large dimensions, TIFF format"
        )
        workflow.add_step('image_resize', {
            'width': 3000,
            'height': 2000,
            'maintain_aspect': True,
            'quality': 100
        })
        workflow.add_step('image_filter', {
            'filter': 'SHARPEN'
        })
        workflow.add_step('image_convert', {'format': 'TIFF'})
        workflow.add_step('file_rename', {'pattern': '{original}_print'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - Mobile
    # ============================================
    
    @staticmethod
    def _mobile_wallpaper_template() -> Workflow:
        """Create smartphone wallpapers."""
        workflow = Workflow(
            name="Mobile Wallpaper Creator",
            description="Create beautiful smartphone wallpapers - 1080x1920 (Full HD portrait)"
        )
        workflow.add_step('image_resize', {
            'width': 1080,
            'height': 1920,
            'maintain_aspect': False,
            'quality': 95
        })
        workflow.add_step('image_filter', {
            'filter': 'SHARPEN',
            'contrast': 1.1
        })
        workflow.add_step('image_convert', {'format': 'PNG'})
        workflow.add_step('file_rename', {'pattern': 'wallpaper_{counter}'})
        return workflow
    
    # ============================================
    # NEW TEMPLATES - Data Processing
    # ============================================
    
    @staticmethod
    def _data_anonymizer_template() -> Workflow:
        """Filter out sensitive data from CSV files."""
        workflow = Workflow(
            name="CSV Data Anonymizer",
            description="Remove or filter sensitive data - excludes rows with 'private' status"
        )
        workflow.add_step('csv_filter', {
            'column': 'status',
            'operator': '!=',
            'value': 'private'
        })
        workflow.add_step('file_rename', {'pattern': '{original}_anonymized'})
        return workflow
    
    # ============================================
    # OCR TEMPLATES
    # ============================================
    
    @staticmethod
    def _ocr_document_scanner_template() -> Workflow:
        """OCR for scanned documents (images)."""
        workflow = Workflow(
            name="Document Scanner OCR",
            description="Extract English text from scanned document images"
        )
        workflow.add_step('ocr_image', {
            'language': 'eng'
        })
        workflow.add_step('file_rename', {'pattern': '{original}_text'})
        return workflow
    
    @staticmethod
    def _ocr_invoice_extractor_template() -> Workflow:
        """Extract text from invoice and receipt images."""
        workflow = Workflow(
            name="Invoice Text Extractor",
            description="Extract English text from invoice and receipt images"
        )
        workflow.add_step('ocr_image', {
            'language': 'eng'
        })
        workflow.add_step('file_rename', {'pattern': '{original}_invoice_text'})
        return workflow
    
    @staticmethod
    def _ocr_book_digitizer_template() -> Workflow:
        """OCR for digitizing book pages from PDF."""
        workflow = Workflow(
            name="Book Page Digitizer",
            description="Extract text from PDF book pages, with OCR fallback at 300 DPI"
        )
        workflow.add_step('ocr_pdf', {
            'mode': 'auto',
            'language': 'eng',
            'dpi': 300
        })
        workflow.add_step('file_rename', {'pattern': '{original}_digitized'})
        return workflow
    
    @staticmethod
    def _ocr_multilingual_template() -> Workflow:
        """OCR for Romanian documents."""
        workflow = Workflow(
            name="Multilingual OCR (Romanian)",
            description="Extract text from Romanian documents"
        )
        workflow.add_step('ocr_image', {
            'language': 'ron'
        })
        workflow.add_step('file_rename', {'pattern': '{original}_ro_text'})
        return workflow


class WorkflowManager:
    """Manages workflow storage and retrieval."""
    
    def __init__(self, workflows_dir: str = "workflows"):
        self.workflows_dir = workflows_dir
        os.makedirs(workflows_dir, exist_ok=True)
    
    def save_workflow(self, workflow: Workflow, filename: Optional[str] = None) -> str:
        """Save a workflow to the workflows directory."""
        if filename is None:
            # Generate filename from workflow name
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' 
                               for c in workflow.name)
            filename = f"{safe_name}.json"
        
        filepath = os.path.join(self.workflows_dir, filename)
        workflow.save_to_file(filepath)
        return filepath
    
    def load_workflow(self, filename: str) -> Optional[Workflow]:
        """Load a workflow from the workflows directory."""
        filepath = os.path.join(self.workflows_dir, filename)
        return Workflow.load_from_file(filepath)
    
    def list_workflows(self) -> List[Dict[str, str]]:
        """List all saved workflows."""
        workflows = []
        for filename in os.listdir(self.workflows_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.workflows_dir, filename)
                workflow = Workflow.load_from_file(filepath)
                if workflow:
                    workflows.append({
                        'filename': filename,
                        'name': workflow.name,
                        'description': workflow.description,
                        'steps': len(workflow.steps),
                        'modified': workflow.modified_at
                    })
        return workflows
    
    def delete_workflow(self, filename: str) -> bool:
        """Delete a workflow file."""
        try:
            filepath = os.path.join(self.workflows_dir, filename)
            os.remove(filepath)
            return True
        except Exception as e:
            print(f"Error deleting workflow: {e}")
            return False
    
    def export_workflow(self, workflow: Workflow, export_path: str) -> bool:
        """Export workflow to a specific location."""
        return workflow.save_to_file(export_path)
    
    def import_workflow(self, import_path: str) -> Optional[Workflow]:
        """Import workflow from external file."""
        workflow = Workflow.load_from_file(import_path)
        if workflow:
            self.save_workflow(workflow)
        return workflow
