"""V11-01: deterministic final-path ownership regressions, using only temp files."""

from copy import deepcopy
import builtins
import io
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from core.operations import OperationRegistry
from core.operations.file_ops import FileRenameOperation
from core.operations.pdf_ops import PDFAggregateMergeOperation
from core.operations import ocr_ops
from core.processor import BatchProcessor, process_single_file, validate_output_directory
from core.security import (
    OutputPathAllocator,
    exclusive_output,
    output_identity,
    remove_owned_output,
    resolve_safe_output,
)
from core.workflow import Workflow


SENTINEL = b"unrelated output: preserve these bytes\x00\xff"
WRITERS = [
    ("image_resize", {"width": 8, "height": 8}, ".png", "planned.png"),
    ("image_filter", {}, ".png", "planned.png"),
    ("image_convert", {"format": "JPEG"}, ".png", "planned.jpeg"),
    ("file_rename", {"pattern": "renamed"}, ".txt", "renamed.txt"),
    ("ocr_image", {}, ".png", "planned.txt"),
    ("ocr_pdf", {"mode": "native"}, ".pdf", "planned.txt"),
    ("ocr_batch", {}, ".png", "planned.txt"),
    ("pdf_watermark", {}, ".pdf", "planned.pdf"),
    ("csv_filter", {"column": "status", "value": "active"}, ".csv", "planned.csv"),
]


def make_source(path, color="blue"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".png":
        Image.new("RGB", (16, 16), color).save(path)
    elif path.suffix == ".pdf":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with path.open("wb") as stream:
            writer.write(stream)
    elif path.suffix == ".csv":
        path.write_text("status,value\nactive,1\n", encoding="utf-8")
    else:
        path.write_bytes(b"source contents")
    return path


@pytest.fixture(autouse=True)
def deterministic_ocr(monkeypatch):
    monkeypatch.setattr(ocr_ops, "HAS_TESSERACT_BINARY", True)
    monkeypatch.setattr(
        ocr_ops,
        "pytesseract",
        SimpleNamespace(image_to_string=lambda *args, **kwargs: "extracted\ntext"),
        raising=False,
    )


@pytest.mark.parametrize("operation_id,config,suffix,final_name", WRITERS)
def test_direct_writers_preserve_occupied_final_target(
    tmp_path, operation_id, config, suffix, final_name
):
    source = make_source(tmp_path / "source" / ("input" + suffix))
    original = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    target = out / final_name
    target.write_bytes(SENTINEL)
    operation = OperationRegistry().get_operation(operation_id, config)

    result = operation.execute(source, out / ("planned" + suffix))

    assert target.read_bytes() == SENTINEL
    assert not result.success
    assert result.error
    assert result.output_path is None
    assert source.read_bytes() == original


@pytest.mark.parametrize("operation_id,config,suffix,final_name", WRITERS)
def test_direct_writer_success_reports_actual_owned_output(
    tmp_path, operation_id, config, suffix, final_name
):
    source = make_source(tmp_path / "source" / ("input" + suffix))
    if operation_id == "file_rename":
        os.utime(source, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    source_mtime = source.stat().st_mtime_ns
    original = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()

    result = (
        OperationRegistry()
        .get_operation(operation_id, config)
        .execute(source, out / ("planned" + suffix))
    )

    assert result.success, result.error
    assert result.output_path == out / final_name
    assert set(out.iterdir()) == {result.output_path}
    assert source.read_bytes() == original
    if operation_id in {"ocr_image", "ocr_batch"}:
        assert result.output_path.read_bytes() == f"extracted{os.linesep}text".encode("utf-8")
    elif operation_id == "csv_filter":
        assert (
            result.output_path.read_bytes()
            == f"status,value{os.linesep}active,1{os.linesep}".encode("utf-8")
        )
    elif operation_id == "file_rename":
        assert result.output_path.read_bytes() == original
        assert result.output_path.stat().st_mtime_ns == source_mtime
    elif operation_id == "pdf_watermark":
        assert len(PdfReader(result.output_path).pages) == 1


@pytest.mark.parametrize("operation_id,config,suffix,final_name", WRITERS)
def test_public_worker_protects_final_target_without_batch_allocator(
    tmp_path, operation_id, config, suffix, final_name
):
    source = make_source(tmp_path / "source" / ("input" + suffix))
    original = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    target = out / final_name
    target.write_bytes(SENTINEL)
    workflow = Workflow("occupied")
    workflow.add_step(operation_id, config)

    result = process_single_file(str(source), workflow.to_dict(), str(out), "planned")

    assert target.read_bytes() == SENTINEL
    assert source.read_bytes() == original
    if result["success"]:
        assert Path(result["output"]) != target
        assert Path(result["output"]).is_file()
    else:
        assert result["error"]


def test_rename_counter_interleaving_is_execution_local(tmp_path, monkeypatch):
    source_a = make_source(tmp_path / "a.txt")
    source_b = make_source(tmp_path / "b.txt")
    out = tmp_path / "out"
    out.mkdir()
    workflow = Workflow("counters")
    workflow.add_step("file_rename", {"pattern": "owned_{counter}"})
    payload = workflow.to_dict()
    original_payload = deepcopy(payload)
    execute = FileRenameOperation.execute
    observed = {}
    results = {}

    def interleaved(self, file_path, output_path, dry_run=False):
        if file_path == source_a:
            observed["a_before"] = self.config["counter"]
            results["b"] = process_single_file(str(source_b), payload, str(out), "b", index=2)
            observed["a_after"] = self.config["counter"]
        else:
            observed["b"] = self.config["counter"]
        return execute(self, file_path, output_path, dry_run)

    monkeypatch.setattr(FileRenameOperation, "execute", interleaved)
    results["a"] = process_single_file(str(source_a), payload, str(out), "a", index=1)

    assert observed == {"a_before": 1, "b": 2, "a_after": 1}
    assert payload == original_payload
    assert workflow.to_dict() == original_payload
    assert all(result["success"] for result in results.values())
    assert Path(results["a"]["output"]).name == "owned_001.txt"
    assert Path(results["b"]["output"]).name == "owned_002.txt"
    assert results["a"]["output"] != results["b"]["output"]


def test_reservation_aliases_are_canonical_and_unique(tmp_path):
    allocator = OutputPathAllocator(tmp_path)
    outputs = [allocator.allocate(name, ".png") for name in ("same", "same", "same_001")]
    assert len({path.resolve() for path in outputs}) == 3


@pytest.mark.parametrize("operation_id,config,suffix,final_name", WRITERS)
def test_direct_writer_collision_at_open_is_exclusive(
    tmp_path, monkeypatch, operation_id, config, suffix, final_name
):
    source = make_source(tmp_path / "source" / ("input" + suffix))
    out = tmp_path / "out"
    out.mkdir()
    target = out / final_name
    original_open = builtins.open
    original_io_open = io.open
    original_path_open = Path.open
    collided = []

    def intercept(opener):
        def open_after_collision(file, mode="r", *args, **kwargs):
            if (
                not isinstance(file, int)
                and Path(file) == target
                and any(flag in mode for flag in "wxa")
                and not collided
            ):
                with original_open(target, "xb") as stream:
                    stream.write(SENTINEL)
                collided.append(target)
            return opener(file, mode, *args, **kwargs)

        return open_after_collision

    monkeypatch.setattr(builtins, "open", intercept(original_open))
    monkeypatch.setattr(io, "open", intercept(original_io_open))
    monkeypatch.setattr(Path, "open", intercept(original_path_open))
    result = (
        OperationRegistry()
        .get_operation(operation_id, config)
        .execute(source, out / ("planned" + suffix))
    )

    assert collided == [target]
    assert target.read_bytes() == SENTINEL
    assert not result.success
    assert result.error and result.output_path is None


def test_two_basename_inputs_keep_distinct_final_contents(tmp_path):
    sources = [
        make_source(tmp_path / folder / "same.png", color)
        for folder, color in (("one", "red"), ("two", "blue"))
    ]
    workflow = Workflow("convert")
    workflow.add_step("image_convert", {"format": "BMP"})
    stats = BatchProcessor(max_workers=2).process_batch(
        [str(path) for path in sources], workflow, str(tmp_path / "out"), "same"
    )
    assert stats.failed_files == 0
    assert len({result["output"] for result in stats.results}) == 2
    for result in stats.results:
        with Image.open(result["file"]) as source, Image.open(result["output"]) as output:
            assert output.getpixel((0, 0)) == source.getpixel((0, 0))


def test_direct_worker_allocates_distinct_same_suffix_intermediates(tmp_path):
    source = make_source(tmp_path / "input.png")
    original = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    workflow = Workflow("direct chain")
    workflow.add_step("image_resize", {"width": 8, "height": 8, "maintain_aspect": False})
    workflow.add_step("image_filter", {"filter": "GRAYSCALE"})

    result = process_single_file(str(source), workflow.to_dict(), str(out), "planned")

    assert result["success"], result.get("error")
    output = Path(result["output"])
    with Image.open(output) as image:
        assert image.size == (8, 8)
        assert image.mode == "L"
    assert set(out.iterdir()) == {output}
    assert source.read_bytes() == original


def test_collision_created_after_reservation_is_not_overwritten(tmp_path, monkeypatch):
    source = make_source(tmp_path / "input.png")
    out = tmp_path / "out"
    out.mkdir()
    allocator = OutputPathAllocator(out)
    allocate = allocator.allocate
    occupied = []

    def reserve_then_collide(name, suffix):
        path = allocate(name, suffix)
        path.write_bytes(SENTINEL)
        occupied.append(path)
        return path

    monkeypatch.setattr(allocator, "allocate", reserve_then_collide)
    workflow = Workflow("race")
    workflow.add_step("image_resize", {"width": 8, "height": 8})
    result = process_single_file(
        str(source), workflow.to_dict(), str(out), "planned", allocator=allocator
    )

    assert occupied and all(path.read_bytes() == SENTINEL for path in occupied)
    assert not result["success"]
    assert result["error"]


def test_aggregate_direct_finalization_preserves_occupied_target(tmp_path):
    source = make_source(tmp_path / "input.pdf")
    target = tmp_path / "merged.pdf"
    merge = PDFAggregateMergeOperation()
    merge.begin(target)
    assert merge.consume(source).success
    target.write_bytes(SENTINEL)

    result = merge.finalize()

    assert target.read_bytes() == SENTINEL
    assert not result.success
    assert result.error and result.output_path is None


def test_aggregate_batch_allocates_final_destination(tmp_path):
    source = make_source(tmp_path / "input.pdf")
    out = tmp_path / "out"
    out.mkdir()
    target = out / "merged.pdf"
    target.write_bytes(SENTINEL)
    workflow = Workflow("merge")
    workflow.add_step("pdf_merge", {"output_filename": "merged.pdf"})

    stats = BatchProcessor().process_batch([str(source)], workflow, str(out))

    assert target.read_bytes() == SENTINEL
    assert stats.failed_files == 0
    produced = Path(stats.results[0]["output"])
    assert produced != target
    assert len(PdfReader(produced).pages) == 1


def test_failed_aggregate_does_not_advertise_occupied_path(tmp_path, monkeypatch):
    source = make_source(tmp_path / "input.pdf")
    workflow = Workflow("merge race")
    workflow.add_step("pdf_merge", {"output_filename": "merged.pdf"})
    begin = PDFAggregateMergeOperation.begin
    occupied = []

    def collide(self, output_path, dry_run=False):
        begin(self, output_path, dry_run)
        output_path.write_bytes(SENTINEL)
        occupied.append(output_path)

    monkeypatch.setattr(PDFAggregateMergeOperation, "begin", collide)
    stats = BatchProcessor().process_batch([str(source)], workflow, str(tmp_path / "out"))

    assert all(path.read_bytes() == SENTINEL for path in occupied)
    assert stats.failed_files == 1
    assert all(
        not result["output"] and not result["result"].get("output") for result in stats.results
    )


def test_intermediate_cleanup_preserves_unrelated_final_target(tmp_path):
    source = make_source(tmp_path / "input.png")
    original = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    target = out / "finished.jpeg"
    target.write_bytes(SENTINEL)
    workflow = Workflow("chain")
    workflow.add_step("image_convert", {"format": "JPEG"})
    workflow.add_step("file_rename", {"pattern": "finished"})
    stats = BatchProcessor().process_batch([str(source)], workflow, str(out), "intermediate")

    assert target.read_bytes() == SENTINEL
    assert source.read_bytes() == original
    assert stats.failed_files == 0
    produced = Path(stats.results[0]["output"])
    assert produced != target and produced.is_file()
    assert set(out.iterdir()) == {target, produced}


def test_normal_probe_preserves_existing_write_test(tmp_path):
    target = tmp_path / ".write_test"
    target.write_bytes(SENTINEL)
    assert validate_output_directory(str(tmp_path)) == (True, "")
    assert target.read_bytes() == SENTINEL
    assert set(tmp_path.iterdir()) == {target}


def test_normal_probe_uses_exclusive_creation_and_skips_collision(tmp_path, monkeypatch):
    occupied = tmp_path / ".batchstudio-probe-occupied"
    occupied.write_bytes(SENTINEL)
    monkeypatch.setattr(tempfile, "_get_candidate_names", lambda: iter(("occupied", "available")))
    original_open = os.open
    attempts = []

    def record_open(path, flags, *args, **kwargs):
        if Path(path).parent == tmp_path:
            attempts.append((Path(path), flags))
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", record_open)
    assert validate_output_directory(str(tmp_path)) == (True, "")
    assert len(attempts) == 2
    assert all(flags & os.O_EXCL and flags & os.O_CREAT for _, flags in attempts)
    assert occupied.read_bytes() == SENTINEL
    assert set(tmp_path.iterdir()) == {occupied}


def test_failed_write_removes_only_its_partial_output(tmp_path):
    target = tmp_path / "partial.txt"
    with pytest.raises(OSError, match="simulated write failure"):
        with exclusive_output(target) as stream:
            stream.write(b"partial")
            raise OSError("simulated write failure")
    assert not target.exists()


def test_cleanup_keeps_a_replaced_intermediate(tmp_path, monkeypatch):
    source = make_source(tmp_path / "input.png")
    out = tmp_path / "out"
    out.mkdir()
    workflow = Workflow("replacement")
    workflow.add_step("image_convert", {"format": "JPEG"})
    workflow.add_step("file_rename", {"pattern": "finished"})
    execute = FileRenameOperation._execute
    replaced = []

    def replace_intermediate_after_read(self, file_path, output_path, dry_run=False):
        result = execute(self, file_path, output_path, dry_run)
        assert result.success
        file_path.rename(tmp_path / "actor-retained-original.jpeg")
        file_path.write_bytes(SENTINEL)
        replaced.append(file_path)
        return result

    monkeypatch.setattr(FileRenameOperation, "_execute", replace_intermediate_after_read)
    stats = BatchProcessor().process_batch([str(source)], workflow, str(out), "intermediate")

    assert stats.failed_files == 0
    assert replaced and all(path.read_bytes() == SENTINEL for path in replaced)
    assert Path(stats.results[0]["output"]).is_file()


def test_cleanup_tolerates_already_removed_owned_file(tmp_path):
    target = tmp_path / "owned.txt"
    target.write_bytes(b"owned")
    identity = output_identity(target)
    target.unlink()
    remove_owned_output(target, identity)
    assert not target.exists()


@pytest.mark.parametrize("dangling", [False, True])
def test_direct_writer_rejects_final_symlink(tmp_path, dangling):
    source = make_source(tmp_path / "input.txt")
    target = tmp_path / "other.txt"
    if not dangling:
        target.write_bytes(SENTINEL)
    link = tmp_path / "renamed.txt"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"Symlink creation unavailable: {exc}")
    result = FileRenameOperation({"pattern": "renamed"}).execute(source, tmp_path / "planned.txt")
    assert not result.success and result.error
    assert link.is_symlink()
    if dangling:
        assert not target.exists()
    else:
        assert target.read_bytes() == SENTINEL


def test_final_suffix_cannot_escape_through_existing_link(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    target = tmp_path / "outside.txt"
    target.write_bytes(SENTINEL)
    try:
        (out / "planned.txt").symlink_to(target)
    except OSError as exc:
        pytest.skip(f"Symlink creation unavailable: {exc}")
    with pytest.raises(ValueError, match="escapes"):
        resolve_safe_output(out, "planned.pdf", required_suffix=".txt")
    assert target.read_bytes() == SENTINEL
