"""V12-04: structural page-aware PDF watermark placement regressions."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, radians, sin
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from core.operations.pdf_ops import PDFWatermarkOperation
from tests.pdf_watermark_fixtures import (
    PDF_WATERMARK_FIXTURES,
    PageFixture,
    PdfFixture,
    fixture_sha256,
    write_pdf_fixture,
)


WATERMARK_TEXT = "CONFIDENTIAL"
WATERMARK_FONT = "Helvetica"
MAX_FONT_SIZE = 60.0
WATERMARK_ANGLE = 45.0
GEOMETRY_TOLERANCE = 0.0001


@dataclass(frozen=True, slots=True)
class ExpectedPlacement:
    visible_width: float
    visible_height: float
    x: float
    y: float
    width: float
    height: float
    font_size: float


@dataclass(frozen=True, slots=True)
class ObservedWatermark:
    bounding_box: tuple[float, float, float, float]
    font_size: float
    visible_angle: float


@pytest.mark.parametrize(
    "fixture",
    PDF_WATERMARK_FIXTURES,
    ids=lambda fixture: fixture.fixture_id,
)
def test_generated_fixture_has_declared_hash_and_geometry(tmp_path: Path, fixture: PdfFixture):
    source = write_pdf_fixture(tmp_path, fixture)

    assert fixture_sha256(fixture) == fixture.expected_sha256
    reader = PdfReader(source)
    assert len(reader.pages) == len(fixture.pages)
    for page, expected_page in zip(reader.pages, fixture.pages):
        assert tuple(float(value) for value in page.mediabox) == tuple(
            float(value) for value in expected_page.media_box
        )
        assert tuple(float(value) for value in page.cropbox) == tuple(
            float(value) for value in expected_page.crop_box or expected_page.media_box
        )
        assert page.rotation == expected_page.rotation


@pytest.mark.parametrize(
    "fixture",
    PDF_WATERMARK_FIXTURES,
    ids=lambda fixture: fixture.fixture_id,
)
def test_watermark_placement_matches_page_geometry(tmp_path: Path, fixture: PdfFixture):
    source = write_pdf_fixture(tmp_path, fixture)
    output = tmp_path / f"watermarked-{fixture.filename}"
    source_reader = PdfReader(source)

    result = PDFWatermarkOperation({"text": WATERMARK_TEXT}).execute(source, output)

    assert result.success, result.error
    assert result.output_path == output.resolve(strict=False)
    assert output.exists()
    output_reader = PdfReader(output)
    assert len(output_reader.pages) == len(source_reader.pages)

    for page_index, (source_page, output_page, page_fixture) in enumerate(
        zip(source_reader.pages, output_reader.pages, fixture.pages),
        start=1,
    ):
        _assert_source_geometry_preserved(source_page, output_page)
        source_marker = f"SOURCE_{fixture.fixture_id}_P{page_index}"
        assert source_marker in (source_page.extract_text() or "")
        assert source_marker in (output_page.extract_text() or "")
        assert any(
            operator == b"re" and tuple(float(value) for value in operands[2:]) == (40.0, 30.0)
            for operands, operator in output_page.get_contents().operations
        )

        expected = _expected_placement(page_fixture)
        observed = _observe_watermark(output_page, page_fixture)
        expected_box = (
            expected.x,
            expected.y,
            expected.x + expected.width,
            expected.y + expected.height,
        )
        assert observed.bounding_box == pytest.approx(
            expected_box,
            abs=GEOMETRY_TOLERANCE,
        )
        assert observed.font_size == pytest.approx(
            expected.font_size,
            abs=GEOMETRY_TOLERANCE,
        )
        assert observed.visible_angle == pytest.approx(
            WATERMARK_ANGLE,
            abs=GEOMETRY_TOLERANCE,
        )
        left, bottom, right, top = observed.bounding_box
        assert left >= -GEOMETRY_TOLERANCE
        assert bottom >= -GEOMETRY_TOLERANCE
        assert right <= expected.visible_width + GEOMETRY_TOLERANCE
        assert top <= expected.visible_height + GEOMETRY_TOLERANCE
        _assert_watermark_style_preserved(output_page)

    PdfReader(output)


def test_empty_watermark_text_remains_compatible(tmp_path: Path):
    fixture = PDF_WATERMARK_FIXTURES[2]
    source = write_pdf_fixture(tmp_path, fixture)
    output = tmp_path / "empty-text.pdf"

    result = PDFWatermarkOperation({"text": ""}).execute(source, output)

    assert result.success, result.error
    assert result.output_path == output.resolve(strict=False)
    assert len(PdfReader(output).pages) == 1


def test_long_watermark_text_is_reduced_to_the_small_page(tmp_path: Path):
    fixture = PDF_WATERMARK_FIXTURES[3]
    source = write_pdf_fixture(tmp_path, fixture)
    output = tmp_path / "long-text.pdf"
    text = "CONFIDENTIAL " * 20

    result = PDFWatermarkOperation({"text": text}).execute(source, output)

    assert result.success, result.error
    page_fixture = fixture.pages[0]
    expected = _expected_placement(page_fixture, text)
    observed = _observe_watermark(PdfReader(output).pages[0], page_fixture, text)
    assert observed.bounding_box == pytest.approx(
        (expected.x, expected.y, expected.x + expected.width, expected.y + expected.height),
        abs=GEOMETRY_TOLERANCE,
    )
    assert observed.font_size < MAX_FONT_SIZE


def test_watermark_failure_does_not_replace_existing_destination(tmp_path: Path):
    fixture = PDF_WATERMARK_FIXTURES[2]
    source = write_pdf_fixture(tmp_path, fixture)
    output = tmp_path / "occupied.pdf"
    sentinel = b"existing destination must survive"
    output.write_bytes(sentinel)

    result = PDFWatermarkOperation({"text": WATERMARK_TEXT}).execute(source, output)

    assert not result.success
    assert result.output_path is None
    assert output.read_bytes() == sentinel


@pytest.mark.parametrize(
    "page_fixture,expected_error",
    [
        (PageFixture(("0", "0", "0", "100")), "positive width and height"),
        (PageFixture(("0", "0", "612", "792"), rotation=45), "multiple of 90"),
    ],
    ids=("zero-width-crop-box", "non-cardinal-rotation"),
)
def test_invalid_page_geometry_fails_before_output_creation(
    tmp_path: Path,
    page_fixture: PageFixture,
    expected_error: str,
):
    fixture = PdfFixture("INVALID", "invalid.pdf", (page_fixture,), "")
    source = write_pdf_fixture(tmp_path, fixture)
    output = tmp_path / "must-not-exist.pdf"

    result = PDFWatermarkOperation({"text": WATERMARK_TEXT}).execute(source, output)

    assert not result.success
    assert result.error is not None
    assert expected_error in result.error
    assert result.output_path is None
    assert not output.exists()


def _expected_placement(
    page: PageFixture,
    text: str = WATERMARK_TEXT,
) -> ExpectedPlacement:
    crop_box = page.crop_box or page.media_box
    left, bottom, right, top = (float(value) for value in crop_box)
    crop_width = right - left
    crop_height = top - bottom
    if page.rotation in (90, 270):
        visible_width, visible_height = crop_height, crop_width
    else:
        visible_width, visible_height = crop_width, crop_height

    text_width = pdfmetrics.stringWidth(text, WATERMARK_FONT, MAX_FONT_SIZE)
    ascent, descent = pdfmetrics.getAscentDescent(WATERMARK_FONT, MAX_FONT_SIZE)
    text_height = ascent - descent
    angle = radians(WATERMARK_ANGLE)
    rotated_width = abs(cos(angle)) * text_width + abs(sin(angle)) * text_height
    rotated_height = abs(sin(angle)) * text_width + abs(cos(angle)) * text_height
    scale = min(1.0, visible_width / rotated_width, visible_height / rotated_height)
    width = rotated_width * scale
    height = rotated_height * scale
    return ExpectedPlacement(
        visible_width=visible_width,
        visible_height=visible_height,
        x=(visible_width - width) / 2,
        y=(visible_height - height) / 2,
        width=width,
        height=height,
        font_size=MAX_FONT_SIZE * scale,
    )


def _observe_watermark(
    page,
    page_fixture: PageFixture,
    text: str = WATERMARK_TEXT,
) -> ObservedWatermark:
    observations = []

    def capture_watermark(text, current_matrix, text_matrix, font, font_size):
        if text.strip() == expected_text.strip():
            observations.append((tuple(current_matrix), tuple(text_matrix), float(font_size)))

    expected_text = text
    page.extract_text(visitor_text=capture_watermark)
    assert len(observations) == 1
    current_matrix, text_matrix, font_size = observations[0]
    text_width = pdfmetrics.stringWidth(text, WATERMARK_FONT, font_size)
    ascent, descent = pdfmetrics.getAscentDescent(WATERMARK_FONT, font_size)
    text_left = float(text_matrix[4])
    baseline = float(text_matrix[5])
    local_corners = (
        (text_left, baseline + descent),
        (text_left + text_width, baseline + descent),
        (text_left + text_width, baseline + ascent),
        (text_left, baseline + ascent),
    )
    visible_corners = [
        _page_to_visible(
            _transform_point(current_matrix, point),
            page_fixture,
        )
        for point in local_corners
    ]
    xs = [point[0] for point in visible_corners]
    ys = [point[1] for point in visible_corners]

    baseline_start = _page_to_visible(
        _transform_point(current_matrix, (text_left, baseline)),
        page_fixture,
    )
    baseline_end = _page_to_visible(
        _transform_point(current_matrix, (text_left + 1, baseline)),
        page_fixture,
    )
    angle = (
        degrees(
            atan2(
                baseline_end[1] - baseline_start[1],
                baseline_end[0] - baseline_start[0],
            )
        )
        % 360
    )
    return ObservedWatermark(
        bounding_box=(min(xs), min(ys), max(xs), max(ys)),
        font_size=font_size,
        visible_angle=angle,
    )


def _transform_point(matrix, point: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, e, f = (float(value) for value in matrix)
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def _page_to_visible(
    point: tuple[float, float],
    page_fixture: PageFixture,
) -> tuple[float, float]:
    crop_box = page_fixture.crop_box or page_fixture.media_box
    left, bottom, right, top = (float(value) for value in crop_box)
    crop_width = right - left
    crop_height = top - bottom
    x = point[0] - left
    y = point[1] - bottom
    if page_fixture.rotation == 0:
        return x, y
    if page_fixture.rotation == 90:
        return y, crop_width - x
    if page_fixture.rotation == 180:
        return crop_width - x, crop_height - y
    if page_fixture.rotation == 270:
        return crop_height - y, x
    raise AssertionError(f"Unsupported fixture rotation: {page_fixture.rotation}")


def _assert_source_geometry_preserved(source_page, output_page) -> None:
    assert tuple(output_page.mediabox) == tuple(source_page.mediabox)
    assert tuple(output_page.cropbox) == tuple(source_page.cropbox)
    assert output_page.rotation == source_page.rotation


def _assert_watermark_style_preserved(page) -> None:
    resources = page["/Resources"]
    fonts = resources["/Font"]
    assert any(font.get_object()["/BaseFont"] == "/Helvetica" for font in fonts.values())
    graphics_states = resources["/ExtGState"]
    assert any(
        float(state.get_object().get("/ca", -1)) == pytest.approx(0.3, abs=1e-6)
        for state in graphics_states.values()
    )
    assert any(
        operator == b"g" and float(operands[0]) == pytest.approx(0.5, abs=1e-6)
        for operands, operator in page.get_contents().operations
    )
