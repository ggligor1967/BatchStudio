#!/usr/bin/env python3
"""Ad-hoc validation for aggregate PDF merge workflow."""

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter

from core import BatchProcessor, Workflow


def create_pdf(path: Path):
    writer = PdfWriter()
    writer.add_blank_page(width=500, height=500)
    with path.open("wb") as handle:
        writer.write(handle)


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = root / "out"
        out.mkdir()

        files = []
        for idx in range(5):
            pdf = root / f"doc_{idx}.pdf"
            create_pdf(pdf)
            files.append(str(pdf))

        workflow = Workflow("pdf-merge")
        workflow.add_step("pdf_merge", {"output_filename": "merged.pdf"})

        stats = BatchProcessor(max_workers=2).process_batch(files, workflow, str(out), "{original}")
        merged = out / "merged.pdf"

        print("processed", stats.processed_files)
        print("failed", stats.failed_files)
        print("merged_exists", merged.exists())
        if merged.exists():
            print("merged_pages", len(PdfReader(str(merged)).pages))
