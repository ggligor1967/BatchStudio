#!/usr/bin/env python3
"""Simple manual test for aggregate PDF merge."""

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter

from core import BatchProcessor, Workflow


def mkpdf(path: Path):
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=400)
    with path.open("wb") as fh:
        writer.write(fh)


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = root / "out"
        out.mkdir()

        sources = []
        for i in range(3):
            p = root / f"in_{i}.pdf"
            mkpdf(p)
            sources.append(str(p))

        wf = Workflow("simple-merge")
        wf.add_step("pdf_merge", {"output_filename": "merged.pdf"})

        stats = BatchProcessor(max_workers=1).process_batch(sources, wf, str(out), "{original}")
        merged = out / "merged.pdf"

        print("failed", stats.failed_files)
        print("exists", merged.exists())
        if merged.exists():
            print("pages", len(PdfReader(str(merged)).pages))
