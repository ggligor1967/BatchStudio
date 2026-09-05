"""Asserted PDF scenarios shared by pytest and standalone diagnostics."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter

from core.processor import BatchProcessor
from core.workflow import Workflow


def make_pdf_inputs(root: Path, count: int) -> list[str]:
    sources = []
    for index in range(count):
        path = root / f"input_{index}.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=400 + index, height=500)
        with path.open("wb") as stream:
            writer.write(stream)
        sources.append(str(path))
    return sources[::-1]


def assert_merge_case(root: Path, input_count: int):
    sources = make_pdf_inputs(root, input_count)
    output_dir = root / "out"
    workflow = Workflow("ordered-pdf-merge")
    workflow.add_step("pdf_merge", {"output_filename": "merged.pdf"})
    stats = BatchProcessor(max_workers=2).process_batch(sources, workflow, str(output_dir))

    merged = output_dir / "merged.pdf"
    assert stats.total_files == stats.processed_files == input_count
    assert stats.failed_files == 0 and stats.errors == []
    assert [record["file"] for record in stats.results] == sources
    assert {record["output"] for record in stats.results} == {str(merged)}
    assert {record["result"]["output"] for record in stats.results} == {str(merged)}
    assert list(output_dir.iterdir()) == [merged]
    pages = PdfReader(merged).pages
    assert len(pages) == input_count
    assert [float(page.mediabox.width) for page in pages] == list(
        reversed(range(400, 400 + input_count))
    )
    return stats
