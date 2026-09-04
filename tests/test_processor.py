from pathlib import Path

from PIL import Image

from core.processor import BatchProcessor, ProcessingStats, process_single_file, validate_file_path
from core.workflow import Workflow


def _make_image(path: Path, color: str = "blue"):
    Image.new("RGB", (64, 64), color=color).save(path)


def test_validate_file_path_blocks_traversal(tmp_path: Path):
    ok, error = validate_file_path("..\\..\\windows\\system32\\cmd.exe")
    assert ok is False
    assert "traversal" in error.lower()


def test_process_single_file_resize_then_rename(tmp_path: Path):
    src = tmp_path / "a.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _make_image(src)

    wf = Workflow("resize-rename")
    wf.add_step("image_resize", {"width": 32, "height": 32, "maintain_aspect": False})
    wf.add_step("file_rename", {"pattern": "{original}_done_{counter}"})

    result = process_single_file(str(src), wf.to_dict(), str(out_dir), "{original}", dry_run=False, index=7)
    assert result["success"] is True
    assert Path(result["output"]).exists()
    assert "_007" in Path(result["output"]).name


def test_dry_run_is_side_effect_free(tmp_path: Path):
    src = tmp_path / "a.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _make_image(src)

    wf = Workflow("dry-run")
    wf.add_step("image_resize", {"width": 32, "height": 32, "maintain_aspect": False})

    before = set(out_dir.iterdir())
    result = process_single_file(str(src), wf.to_dict(), str(out_dir), "{original}_x", dry_run=True, index=1)
    after = set(out_dir.iterdir())

    assert result["success"] is True
    assert before == after


def test_duplicate_basenames_are_allocated_uniquely(tmp_path: Path):
    a = tmp_path / "one" / "same.png"
    b = tmp_path / "two" / "same.png"
    a.parent.mkdir()
    b.parent.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _make_image(a, "green")
    _make_image(b, "yellow")

    wf = Workflow("resize")
    wf.add_step("image_resize", {"width": 16, "height": 16, "maintain_aspect": False})

    stats = BatchProcessor(max_workers=2).process_batch([str(a), str(b)], wf, str(out_dir), naming_pattern="same", dry_run=False)
    outputs = [Path(item["output"]).name for item in stats.results]

    assert stats.failed_files == 0
    assert len(set(outputs)) == 2


def test_naming_pattern_traversal_is_sanitized(tmp_path: Path):
    src = tmp_path / "a.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _make_image(src)

    wf = Workflow("resize")
    wf.add_step("image_resize", {"width": 16, "height": 16, "maintain_aspect": False})

    result = process_single_file(str(src), wf.to_dict(), str(out_dir), "..\\..\\escape", dry_run=False, index=1)
    assert result["success"] is True
    assert Path(result["output"]).parent == out_dir.resolve()


def test_reports_escape_html_and_csv_formulae(tmp_path: Path):
    processor = BatchProcessor(max_workers=1)
    stats = ProcessingStats()
    stats.total_files = 2
    stats.add_result("=cmd|' /C calc'!A0<script>.png", {"output": "out.png", "message": "<b>ok</b>"})
    stats.add_error("@bad.csv", "<script>alert(1)</script>")

    html_report = tmp_path / "report.html"
    csv_report = tmp_path / "report.csv"

    assert processor.generate_report(stats, str(html_report), "html") is True
    assert processor.generate_report(stats, str(csv_report), "csv") is True

    html_text = html_report.read_text(encoding="utf-8")
    csv_text = csv_report.read_text(encoding="utf-8")

    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text
    assert "'<script>alert(1)</script>" in csv_text or "'@bad.csv" in csv_text
