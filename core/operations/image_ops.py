from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

from core.contracts import OperationResult
from core.operations.base import Operation


class ImageResizeOperation(Operation):
    id = "image_resize"
    name = "Image Resize"
    description = "Resize images to specified width and height"
    accepted_types = {"image"}
    output_type = "image"

    def execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        width = int(self.config.get("width", 800))
        height = int(self.config.get("height", 600))
        maintain_aspect = bool(self.config.get("maintain_aspect", True))

        if dry_run:
            return OperationResult(success=True, message=f"Dry run resize to {width}x{height}", output_path=output_path)

        try:
            img = Image.open(file_path)
            original_size = img.size
            if maintain_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            else:
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            img.save(output_path, quality=int(self.config.get("quality", 95)))
            return OperationResult(
                success=True,
                output_path=output_path,
                message=f"Resized from {original_size} to {img.size}",
                metadata={"original_size": original_size, "new_size": img.size},
            )
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        try:
            Image.open(file_path)
            return True
        except Exception:
            return False

    def get_config_schema(self):
        return {
            "width": {"type": "int", "default": 800},
            "height": {"type": "int", "default": 600},
            "maintain_aspect": {"type": "bool", "default": True},
            "quality": {"type": "int", "default": 95},
        }


class ImageConvertOperation(Operation):
    id = "image_convert"
    name = "Image Convert"
    description = "Convert images to different formats"
    accepted_types = {"image"}
    output_type = "image"

    def execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        format_to = str(self.config.get("format", "PNG")).upper()
        converted_path = output_path.with_suffix("." + format_to.lower())

        if dry_run:
            return OperationResult(success=True, message=f"Dry run convert to {format_to}", output_path=converted_path)

        try:
            img = Image.open(file_path)
            if format_to == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            img.save(converted_path, format=format_to)
            return OperationResult(
                success=True,
                output_path=converted_path,
                message=f"Converted to {format_to}",
                metadata={"format": format_to},
            )
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        try:
            Image.open(file_path)
            return True
        except Exception:
            return False

    def get_config_schema(self):
        return {"format": {"type": "choice", "default": "PNG", "choices": ["PNG", "JPEG", "WEBP", "BMP", "TIFF"]}}


class ImageFilterOperation(Operation):
    id = "image_filter"
    name = "Image Filter"
    description = "Apply various filters to images"
    accepted_types = {"image"}
    output_type = "image"

    def execute(self, file_path: Path, output_path: Path, dry_run: bool = False) -> OperationResult:
        filter_type = str(self.config.get("filter", "SHARPEN"))
        if dry_run:
            return OperationResult(success=True, message=f"Dry run filter {filter_type}", output_path=output_path)

        try:
            img = Image.open(file_path)
            filters = {
                "BLUR": ImageFilter.BLUR,
                "SHARPEN": ImageFilter.SHARPEN,
                "SMOOTH": ImageFilter.SMOOTH,
                "EDGE_ENHANCE": ImageFilter.EDGE_ENHANCE,
                "EMBOSS": ImageFilter.EMBOSS,
                "CONTOUR": ImageFilter.CONTOUR,
                "GRAYSCALE": None,
            }
            if filter_type == "GRAYSCALE":
                img = img.convert("L")
            elif filter_type in filters:
                img = img.filter(filters[filter_type])

            if "brightness" in self.config:
                img = ImageEnhance.Brightness(img).enhance(float(self.config["brightness"]))
            if "contrast" in self.config:
                img = ImageEnhance.Contrast(img).enhance(float(self.config["contrast"]))

            img.save(output_path)
            return OperationResult(success=True, output_path=output_path, message=f"Applied {filter_type} filter")
        except Exception as exc:
            return OperationResult(success=False, error=str(exc))

    def validate(self, file_path: Path) -> bool:
        try:
            Image.open(file_path)
            return True
        except Exception:
            return False

    def get_config_schema(self):
        return {
            "filter": {
                "type": "choice",
                "default": "SHARPEN",
                "choices": ["BLUR", "SHARPEN", "SMOOTH", "EDGE_ENHANCE", "EMBOSS", "CONTOUR", "GRAYSCALE"],
            },
            "brightness": {"type": "float", "default": 1.0, "optional": True},
            "contrast": {"type": "float", "default": 1.0, "optional": True},
        }
