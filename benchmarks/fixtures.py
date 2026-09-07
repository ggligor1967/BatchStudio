"""Generate and verify deterministic V12-PERF benchmark fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import RectangleObject


FIXTURE_SCHEMA_VERSION = "batchstudio-benchmark-fixtures/v1"
GENERATION_COMMAND = (
    "python -m benchmarks.fixtures --output-dir .benchmarks/fixtures-v1 --verify"
)
MANIFEST_PATH = Path(__file__).with_name("fixture_manifest_v1.json")


class FixtureVerificationError(RuntimeError):
    """Raised when generated fixture bytes do not match the canonical manifest."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json_payload(payload: Any) -> str:
    canonical_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def sha256_json_file(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sha256_json_payload(payload)


def sha256_normalized_text_file(path: Path) -> str:
    normalized = "\n".join(path.read_text(encoding="utf-8").splitlines()) + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _write_small_text(path: Path) -> None:
    pattern = b"BatchStudio V12-PERF deterministic fixture v1\r\n"
    size = 64 * 1024
    path.write_bytes((pattern * ((size // len(pattern)) + 1))[:size])


def _bmp_row(width: int, logical_y: int, seed: int, row_stride: int) -> bytes:
    row = bytearray(row_stride)
    for x in range(width):
        offset = x * 3
        row[offset] = (x * 3 + logical_y * 5 + seed * 11) & 0xFF
        row[offset + 1] = (x * 7 + logical_y * 13 + seed * 17) & 0xFF
        row[offset + 2] = (x * 19 + logical_y * 23 + seed * 29) & 0xFF
    return bytes(row)


def _write_bmp(path: Path, width: int, height: int, seed: int) -> None:
    row_stride = (width * 3 + 3) & ~3
    image_size = row_stride * height
    file_size = 14 + 40 + image_size
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 54)
    dib_header = struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height,
        1,
        24,
        0,
        image_size,
        2835,
        2835,
        0,
        0,
    )
    cached_rows = {
        logical_y: _bmp_row(width, logical_y, seed, row_stride)
        for logical_y in range(256)
    }
    with path.open("wb") as handle:
        handle.write(file_header)
        handle.write(dib_header)
        for y in range(height - 1, -1, -1):
            handle.write(cached_rows[y & 0xFF])


def _write_pdf(path: Path, page_specs: list[dict[str, Any]], title: str) -> None:
    writer = PdfWriter()
    writer.add_metadata(
        {
            "/Producer": "BatchStudio V12-PERF fixture generator v1",
            "/Title": title,
        }
    )
    for spec in page_specs:
        page = writer.add_blank_page(width=spec["width"], height=spec["height"])
        cropbox = spec.get("cropbox")
        if cropbox is not None:
            page.cropbox = RectangleObject(cropbox)
        rotation = int(spec.get("rotation", 0))
        if rotation:
            page.rotate(rotation)
    with path.open("wb") as handle:
        writer.write(handle)


def _watermark_page_specs() -> list[dict[str, Any]]:
    return [
        {"width": 595, "height": 842, "rotation": 0},
        {"width": 612, "height": 792, "rotation": 90},
        {"width": 792, "height": 612, "rotation": 180},
        {"width": 420, "height": 420, "rotation": 270},
        {"width": 1000, "height": 500, "cropbox": [40, 25, 960, 475], "rotation": 0},
        {"width": 500, "height": 1000, "cropbox": [25, 40, 475, 960], "rotation": 90},
        {"width": 360, "height": 240, "cropbox": [12, 18, 348, 222], "rotation": 180},
        {"width": 240, "height": 360, "cropbox": [18, 12, 222, 348], "rotation": 270},
    ]


def _merge_page_specs(file_index: int) -> list[dict[str, Any]]:
    return [
        {
            "width": 500 + file_index * 3 + page_index,
            "height": 700 + page_index * 5,
            "rotation": 0,
        }
        for page_index in range(6)
    ]


def merge_page_dimensions() -> list[list[int]]:
    return [
        [spec["width"], spec["height"]]
        for file_index in range(16)
        for spec in _merge_page_specs(file_index)
    ]


def _file_record(path: Path, fixture_root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(fixture_root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def generate_fixtures(output_directory: Path) -> dict[str, Any]:
    output_directory = output_directory.resolve()
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FixtureVerificationError(
            f"Fixture output directory must be absent or empty: {output_directory}"
        )
    output_directory.mkdir(parents=True, exist_ok=True)

    small_text = output_directory / "f1" / "small.txt"
    small_text.parent.mkdir()
    _write_small_text(small_text)

    single_image = output_directory / "f2" / "single.bmp"
    single_image.parent.mkdir()
    _write_bmp(single_image, width=4096, height=3072, seed=11)

    watermark_pdf = output_directory / "f3" / "mixed_geometry.pdf"
    watermark_pdf.parent.mkdir()
    watermark_specs = _watermark_page_specs() * 8
    _write_pdf(watermark_pdf, watermark_specs, "V12-PERF F3")

    merge_directory = output_directory / "f4"
    merge_directory.mkdir()
    merge_files: list[Path] = []
    for file_index in range(16):
        merge_file = merge_directory / f"merge_{file_index:02d}.pdf"
        _write_pdf(
            merge_file,
            _merge_page_specs(file_index),
            f"V12-PERF F4 input {file_index:02d}",
        )
        merge_files.append(merge_file)

    batch_directory = output_directory / "f5"
    batch_directory.mkdir()
    batch_files: list[Path] = []
    for file_index in range(8):
        batch_file = batch_directory / f"batch_{file_index:02d}.bmp"
        _write_bmp(batch_file, width=2048, height=1536, seed=21 + file_index)
        batch_files.append(batch_file)

    return {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "generation_command": GENERATION_COMMAND,
        "fixtures": [
            {
                "fixture_id": "F1",
                "generator": "deterministic repeated ASCII bytes",
                "input_type": "text",
                "file_count": 1,
                "dimensions_or_pages": {"bytes": 65536},
                "expected_output_class": "byte-identical TXT copy",
                "files": [_file_record(small_text, output_directory)],
            },
            {
                "fixture_id": "F2",
                "generator": "standard-library 24-bit BMP arithmetic pixel pattern",
                "input_type": "image/bmp",
                "file_count": 1,
                "dimensions_or_pages": {"width": 4096, "height": 3072, "mode": "RGB"},
                "expected_output_class": "2048x1536 RGB BMP",
                "files": [_file_record(single_image, output_directory)],
            },
            {
                "fixture_id": "F3",
                "generator": "pypdf blank pages with fixed boxes and rotations",
                "input_type": "application/pdf",
                "file_count": 1,
                "dimensions_or_pages": {
                    "base_pages": _watermark_page_specs(),
                    "repetitions": 8,
                    "total_pages": 64,
                },
                "expected_output_class": (
                    "readable 64-page watermarked PDF preserving repeated geometry"
                ),
                "files": [_file_record(watermark_pdf, output_directory)],
            },
            {
                "fixture_id": "F4",
                "generator": "pypdf blank pages with index-encoded fixed dimensions",
                "input_type": "application/pdf",
                "file_count": len(merge_files),
                "dimensions_or_pages": {
                    "pages_per_file": 6,
                    "total_pages": 96,
                    "dimension_formula": (
                        "width=500+3*file_index+page_index; height=700+5*page_index"
                    ),
                },
                "expected_output_class": (
                    "ordered 96-page source sequence; B4 repeats it to 384 pages"
                ),
                "files": [_file_record(path, output_directory) for path in merge_files],
            },
            {
                "fixture_id": "F5",
                "generator": "standard-library 24-bit BMP arithmetic pixel patterns",
                "input_type": "image/bmp",
                "file_count": len(batch_files),
                "dimensions_or_pages": {"width": 2048, "height": 1536, "mode": "RGB"},
                "expected_output_class": "eight 1024x768 RGB BMP files",
                "files": [_file_record(path, output_directory) for path in batch_files],
            },
        ],
    }


def load_expected_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FixtureVerificationError(f"Fixture manifest is missing: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def verify_manifest(actual_manifest: dict[str, Any]) -> None:
    expected_manifest = load_expected_manifest()
    if actual_manifest != expected_manifest:
        raise FixtureVerificationError(
            "Generated fixture manifest does not match benchmarks/fixture_manifest_v1.json"
        )


def verify_fixture_files(fixture_root: Path, manifest: dict[str, Any]) -> None:
    for fixture in manifest.get("fixtures", []):
        for record in fixture.get("files", []):
            fixture_path = fixture_root / record["path"]
            if not fixture_path.is_file():
                raise FixtureVerificationError(f"Fixture file is missing: {record['path']}")
            if fixture_path.stat().st_size != record["size_bytes"]:
                raise FixtureVerificationError(f"Fixture size differs: {record['path']}")
            if sha256_file(fixture_path) != record["sha256"]:
                raise FixtureVerificationError(f"Fixture SHA-256 differs: {record['path']}")


def fixture_by_id(manifest: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    for fixture in manifest.get("fixtures", []):
        if fixture.get("fixture_id") == fixture_id:
            return fixture
    raise FixtureVerificationError(f"Unknown fixture ID: {fixture_id}")


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--print-manifest", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    manifest = generate_fixtures(arguments.output_dir)
    if arguments.verify:
        verify_manifest(manifest)
        verify_fixture_files(arguments.output_dir, manifest)
        print(f"Verified {len(manifest['fixtures'])} deterministic fixture groups.")
    else:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, FixtureVerificationError, ValueError) as error:
        print(f"Fixture generation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
