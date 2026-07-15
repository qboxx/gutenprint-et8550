"""Deterministic geometry and patch allocation for printer-only CMYK charts.

The source TIFF order is CMYK.  The Gutenprint raw adapter deliberately
reorders those four samples to its Epson KCMY stream.  Reserved UV spots are
represented in the manifest even though this four-channel ET-2856 chart does
not emit them.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import floor
from typing import Mapping, Sequence

A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DPI = 720
MM_PER_INCH = 25.4
CMYK_CHANNELS = ("C", "M", "Y", "K")
RESERVED_UV_CHANNELS = {"UV_A": 0, "UV_B": 0}


@dataclass(frozen=True)
class ChartSpec:
    page_width_mm: float
    page_height_mm: float
    page_width_px: int
    page_height_px: int
    target_width_mm: float
    target_height_mm: float
    target_width_px: int
    target_height_px: int
    target_x_mm: float
    target_y_mm: float
    target_x_px: int
    target_y_px: int
    dpi: int
    grid_columns: int
    grid_rows: int
    grid_x_mm: float
    grid_y_mm: float
    grid_width_mm: float
    grid_height_mm: float
    gutter_mm: float


@dataclass(frozen=True)
class Patch:
    patch_id: str
    family: str
    coverage: Mapping[str, int]
    reserved_spot_coverage: Mapping[str, int]
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    row: int
    column: int


def mm_to_px(mm: float, dpi: int = DPI) -> int:
    """Round a positive physical length to the nearest raster pixel."""
    return floor((mm * dpi / MM_PER_INCH) + 0.5)


def build_chart_spec() -> ChartSpec:
    """Return the fixed A4 layout approved for the V1 printer chart."""
    target_width_mm = 177
    target_height_mm = 170
    target_x_mm = (A4_WIDTH_MM - target_width_mm) / 2
    target_y_mm = (A4_HEIGHT_MM - target_height_mm) / 2
    target_x_px = mm_to_px(target_x_mm)
    target_y_px = mm_to_px(target_y_mm)
    page_width_px = mm_to_px(A4_WIDTH_MM)
    page_height_px = mm_to_px(A4_HEIGHT_MM)
    target_width_px = mm_to_px(target_width_mm)
    target_height_px = mm_to_px(target_height_mm)

    # Six millimetres around the target hold minimal fiducials; all remaining
    # area is reserved for printer-characterisation patches.
    inset_mm = 6
    return ChartSpec(
        page_width_mm=A4_WIDTH_MM,
        page_height_mm=A4_HEIGHT_MM,
        page_width_px=page_width_px,
        page_height_px=page_height_px,
        target_width_mm=target_width_mm,
        target_height_mm=target_height_mm,
        target_width_px=target_width_px,
        target_height_px=target_height_px,
        target_x_mm=target_x_mm,
        target_y_mm=target_y_mm,
        target_x_px=target_x_px,
        target_y_px=target_y_px,
        dpi=DPI,
        grid_columns=14,
        grid_rows=16,
        grid_x_mm=target_x_mm + inset_mm,
        grid_y_mm=target_y_mm + inset_mm,
        grid_width_mm=target_width_mm - (2 * inset_mm),
        grid_height_mm=target_height_mm - (2 * inset_mm),
        gutter_mm=1,
    )


def _cmyk(c: int = 0, m: int = 0, y: int = 0, k: int = 0) -> dict[str, int]:
    return {"C": c, "M": m, "Y": y, "K": k}


def _halton(index: int, base: int) -> float:
    result = 0.0
    factor = 1.0 / base
    while index:
        index, remainder = divmod(index, base)
        result += factor * remainder
        factor /= base
    return result


def _patch_definitions() -> list[tuple[str, str, dict[str, int]]]:
    definitions: list[tuple[str, str, dict[str, int]]] = []

    # 16 full-coverage Neugebauer primaries, including paper white.
    for index, values in enumerate(product((0, 255), repeat=4)):
        definitions.append((f"N{index:03d}", "neugebauer", _cmyk(*values)))

    # 36 single-channel ramps: 4 channels × 9 nominal coverages.
    ramp_levels = (0, 32, 64, 96, 128, 160, 192, 224, 255)
    for channel in CMYK_CHANNELS:
        for level in ramp_levels:
            coverage = _cmyk()
            coverage[channel] = level
            definitions.append((f"R_{channel}_{level:03d}", "ramp", coverage))

    # 75 pairwise grids for the visible subtractive colour pairs.
    pair_levels = (0, 64, 128, 191, 255)
    for first, second in (("C", "M"), ("M", "Y"), ("C", "Y")):
        for first_level in pair_levels:
            for second_level in pair_levels:
                coverage = _cmyk()
                coverage[first] = first_level
                coverage[second] = second_level
                definitions.append(
                    (f"P_{first}{second}_{first_level:03d}_{second_level:03d}", "pairwise", coverage)
                )

    # 48 GCR samples: six darkness levels, each with eight K substitutions.
    for darkness in (32, 64, 96, 128, 160, 224):
        for k_fraction in (0, 36, 73, 109, 146, 182, 219, 255):
            k = round(darkness * k_fraction / 255)
            cmy = darkness - k
            definitions.append(
                (f"G_{darkness:03d}_{k_fraction:03d}", "neutral_gcr", _cmyk(cmy, cmy, cmy, k))
            )

    # 33 deterministic four-dimensional interior samples.
    for index in range(1, 34):
        sequence_index = index + 17
        coverage = _cmyk(
            round(_halton(sequence_index, 2) * 255),
            round(_halton(sequence_index, 3) * 255),
            round(_halton(sequence_index, 5) * 255),
            round(_halton(sequence_index, 7) * 255),
        )
        definitions.append((f"S{index:03d}", "space_filling", coverage))

    # 16 repeatability controls deliberately duplicate informative primaries.
    controls: Sequence[tuple[str, dict[str, int]]] = (
        ("paper", _cmyk()),
        ("c", _cmyk(c=255)),
        ("m", _cmyk(m=255)),
        ("y", _cmyk(y=255)),
        ("k", _cmyk(k=255)),
        ("cm", _cmyk(c=255, m=255)),
        ("my", _cmyk(m=255, y=255)),
        ("cy", _cmyk(c=255, y=255)),
        ("cmy", _cmyk(c=255, m=255, y=255)),
        ("cmyk", _cmyk(c=255, m=255, y=255, k=255)),
        ("neutral_064", _cmyk(64, 64, 64, 0)),
        ("neutral_128", _cmyk(128, 128, 128, 0)),
        ("neutral_192", _cmyk(192, 192, 192, 0)),
        ("gcr_128", _cmyk(64, 64, 64, 64)),
        ("gcr_192", _cmyk(96, 96, 96, 96)),
        ("mid_mix", _cmyk(96, 160, 64, 48)),
    )
    for name, coverage in controls:
        definitions.append((f"Q_{name}", "control", coverage))

    if len(definitions) != 224:
        raise AssertionError(f"Expected 224 patches, got {len(definitions)}")
    return definitions


def build_patches(spec: ChartSpec) -> list[Patch]:
    definitions = _patch_definitions()
    cell_width_mm = spec.grid_width_mm / spec.grid_columns
    cell_height_mm = spec.grid_height_mm / spec.grid_rows
    patch_width_mm = cell_width_mm - spec.gutter_mm
    patch_height_mm = cell_height_mm - spec.gutter_mm
    patches: list[Patch] = []

    for index, (patch_id, family, coverage) in enumerate(definitions):
        row, column = divmod(index, spec.grid_columns)
        patches.append(
            Patch(
                patch_id=patch_id,
                family=family,
                coverage=coverage,
                reserved_spot_coverage=dict(RESERVED_UV_CHANNELS),
                x_mm=spec.grid_x_mm + (column * cell_width_mm) + (spec.gutter_mm / 2),
                y_mm=spec.grid_y_mm + (row * cell_height_mm) + (spec.gutter_mm / 2),
                width_mm=patch_width_mm,
                height_mm=patch_height_mm,
                row=row,
                column=column,
            )
        )
    return patches


def validate_chart(spec: ChartSpec, patches: Sequence[Patch]) -> None:
    expected_count = spec.grid_columns * spec.grid_rows
    if len(patches) != expected_count:
        raise ValueError(f"Expected {expected_count} patches, got {len(patches)}")
    if len({patch.patch_id for patch in patches}) != len(patches):
        raise ValueError("Patch IDs must be unique")

    target_right = spec.target_x_mm + spec.target_width_mm
    target_bottom = spec.target_y_mm + spec.target_height_mm
    for patch in patches:
        if set(patch.coverage) != set(CMYK_CHANNELS):
            raise ValueError(f"{patch.patch_id} does not declare exactly CMYK")
        if any(not 0 <= value <= 255 for value in patch.coverage.values()):
            raise ValueError(f"{patch.patch_id} has an out-of-range CMYK value")
        if dict(patch.reserved_spot_coverage) != RESERVED_UV_CHANNELS:
            raise ValueError(f"{patch.patch_id} violates the hard-zero UV policy")
        if not (
            patch.x_mm >= spec.target_x_mm
            and patch.y_mm >= spec.target_y_mm
            and patch.x_mm + patch.width_mm <= target_right
            and patch.y_mm + patch.height_mm <= target_bottom
        ):
            raise ValueError(f"{patch.patch_id} falls outside the active target")

    for index, first in enumerate(patches):
        for second in patches[index + 1 :]:
            overlap_x = first.x_mm < second.x_mm + second.width_mm and second.x_mm < first.x_mm + first.width_mm
            overlap_y = first.y_mm < second.y_mm + second.height_mm and second.y_mm < first.y_mm + first.height_mm
            if overlap_x and overlap_y:
                raise ValueError(f"Patches overlap: {first.patch_id}, {second.patch_id}")
