"""Manifest, pixel geometry and channel safety helpers for CMYK chart artifacts."""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from chart_spec import ChartSpec, Patch, mm_to_px


def cmyk_patch_pixel_bounds(spec: ChartSpec, patch: Patch) -> tuple[int, int, int, int]:
    """Return page-relative [left, top, right, bottom) raster bounds for a patch."""
    left = mm_to_px(patch.x_mm, spec.dpi)
    top = mm_to_px(patch.y_mm, spec.dpi)
    right = mm_to_px(patch.x_mm + patch.width_mm, spec.dpi)
    bottom = mm_to_px(patch.y_mm + patch.height_mm, spec.dpi)
    return left, top, right, bottom


def _patch_manifest_entry(spec: ChartSpec, patch: Patch) -> dict[str, object]:
    left, top, right, bottom = cmyk_patch_pixel_bounds(spec, patch)
    return {
        "id": patch.patch_id,
        "family": patch.family,
        "cmyk": dict(patch.coverage),
        "reserved_spot_coverage": dict(patch.reserved_spot_coverage),
        "rect_mm": {
            "x": patch.x_mm,
            "y": patch.y_mm,
            "width": patch.width_mm,
            "height": patch.height_mm,
        },
        "rect_px": {"left": left, "top": top, "right": right, "bottom": bottom},
        "grid": {"row": patch.row, "column": patch.column},
    }


def build_manifest(spec: ChartSpec, patches: Sequence[Patch]) -> dict[str, object]:
    """Build a portable, audit-oriented manifest for the rendered chart."""
    return {
        "schema_version": 1,
        "kind": "aflabox-printer-characterisation-chart",
        "source_plane_order": ["C", "M", "Y", "K"],
        "printer_stream_order": ["K", "C", "M", "Y"],
        "reserved_spot_channels": {"UV_A": 0, "UV_B": 0},
        "page": {
            "width_mm": spec.page_width_mm,
            "height_mm": spec.page_height_mm,
            "width_px": spec.page_width_px,
            "height_px": spec.page_height_px,
            "dpi": spec.dpi,
            "scale": "100%",
        },
        "active_target": {
            "width_mm": spec.target_width_mm,
            "height_mm": spec.target_height_mm,
            "x_mm": spec.target_x_mm,
            "y_mm": spec.target_y_mm,
            "x_px": spec.target_x_px,
            "y_px": spec.target_y_px,
            "width_px": spec.target_width_px,
            "height_px": spec.target_height_px,
        },
        "patches": [_patch_manifest_entry(spec, patch) for patch in patches],
    }


def assert_reserved_spot_planes_zero(planes: np.ndarray, reserved_indices: Mapping[str, int]) -> None:
    """Fail closed if a nominally-reserved spot plane contains any nonzero pixel."""
    if planes.ndim != 3:
        raise ValueError(f"Expected H×W×channels planes, got shape {planes.shape}")
    for channel_name, channel_index in reserved_indices.items():
        if not 0 <= channel_index < planes.shape[2]:
            raise ValueError(f"{channel_name} index {channel_index} is outside {planes.shape[2]} channels")
        count = int(np.count_nonzero(planes[:, :, channel_index]))
        if count:
            raise ValueError(f"{channel_name} contains {count} nonzero pixel(s)")
