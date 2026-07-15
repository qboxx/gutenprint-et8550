"""Fail-closed read-back audit for the fixed A4 raw-CMYK V1 chart."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import tifffile

from chart_artifact import cmyk_patch_pixel_bounds
from chart_spec import (
    CMYK_CHANNELS,
    RESERVED_UV_CHANNELS,
    ChartSpec,
    build_chart_spec,
    build_patches,
)

PRINTER_STREAM_ORDER = ["K", "C", "M", "Y"]
ARTIFACT_NAMES = {
    "tiff": "aflabox-printer-characterisation-v1-a4-720dpi.tiff",
    "preview": "aflabox-printer-characterisation-v1-a4-preview.png",
}


def _report(
    errors: list[str],
    *,
    patches_checked: int = 0,
    outside_count: int = 0,
    samples_per_pixel: int | None = None,
    spec: ChartSpec | None = None,
) -> dict[str, Any]:
    spec = spec or build_chart_spec()
    return {
        "passed": not errors,
        "errors": errors,
        "patches_checked": patches_checked,
        "outside_active_target_nonzero_pixels": outside_count,
        "source_plane_order": list(CMYK_CHANNELS),
        "samples_per_pixel": samples_per_pixel,
        "page_px": {"width": spec.page_width_px, "height": spec.page_height_px},
        "active_target_px": {
            "x": spec.target_x_px,
            "y": spec.target_y_px,
            "width": spec.target_width_px,
            "height": spec.target_height_px,
        },
    }


def _expected_page(spec: ChartSpec) -> dict[str, object]:
    return {
        "width_mm": spec.page_width_mm,
        "height_mm": spec.page_height_mm,
        "width_px": spec.page_width_px,
        "height_px": spec.page_height_px,
        "dpi": spec.dpi,
        "scale": "100%",
    }


def _expected_target(spec: ChartSpec) -> dict[str, object]:
    return {
        "width_mm": spec.target_width_mm,
        "height_mm": spec.target_height_mm,
        "x_mm": spec.target_x_mm,
        "y_mm": spec.target_y_mm,
        "x_px": spec.target_x_px,
        "y_px": spec.target_y_px,
        "width_px": spec.target_width_px,
        "height_px": spec.target_height_px,
    }


def _fiducial_centers_px(spec: ChartSpec) -> list[tuple[int, int]]:
    offset_mm = 3
    positions_mm = (
        (spec.target_x_mm + offset_mm, spec.target_y_mm + offset_mm),
        (spec.target_x_mm + spec.target_width_mm - offset_mm, spec.target_y_mm + offset_mm),
        (spec.target_x_mm + offset_mm, spec.target_y_mm + spec.target_height_mm - offset_mm),
        (spec.target_x_mm + spec.target_width_mm - offset_mm, spec.target_y_mm + spec.target_height_mm - offset_mm),
    )
    scale = spec.dpi / 25.4
    return [(round(x * scale), round(y * scale)) for x, y in positions_mm]


def _expected_fiducials(spec: ChartSpec) -> list[dict[str, object]]:
    return [{"x_px": x, "y_px": y, "kind": "K-only bullseye"} for x, y in _fiducial_centers_px(spec)]


def _nonzero_pixels(view: np.ndarray) -> int:
    if view.size == 0:
        return 0
    return int(np.count_nonzero(np.any(view != 0, axis=2)))


def _expected_patch_manifest(spec: ChartSpec, patch: object) -> dict[str, object]:
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


def _require_mapping_types(actual: object, expected: dict[str, object], label: str, errors: list[str]) -> None:
    """Reject JSON bools and other type-coercible values before equality checks."""
    if not isinstance(actual, dict):
        errors.append(f"{label} is not an object")
        return
    for key, expected_value in expected.items():
        if type(actual.get(key)) is not type(expected_value):
            errors.append(
                f"{label}.{key} type is {type(actual.get(key)).__name__}, "
                f"expected {type(expected_value).__name__}"
            )


def _validate_manifest(manifest: object, spec: ChartSpec, errors: list[str]) -> None:
    if not isinstance(manifest, dict):
        errors.append("Manifest root is not an object")
        return
    expected_keys = {
        "schema_version",
        "kind",
        "source_plane_order",
        "printer_stream_order",
        "reserved_spot_channels",
        "page",
        "active_target",
        "patches",
        "artifacts",
        "fiducials",
    }
    if set(manifest) != expected_keys:
        errors.append("Manifest top-level schema differs from fixed contract")
    if type(manifest.get("schema_version")) is not int:
        errors.append("schema_version type is not int")
    if manifest.get("schema_version") != 1:
        errors.append("schema_version is not 1")
    if manifest.get("kind") != "aflabox-printer-characterisation-chart":
        errors.append("kind is not aflabox-printer-characterisation-chart")
    if manifest.get("source_plane_order") != list(CMYK_CHANNELS):
        errors.append("source_plane_order violates fixed CMYK contract")
    if manifest.get("printer_stream_order") != PRINTER_STREAM_ORDER:
        errors.append("printer_stream_order violates fixed KCMY contract")
    _require_mapping_types(manifest.get("reserved_spot_channels"), RESERVED_UV_CHANNELS, "reserved_spot_channels", errors)
    _require_mapping_types(manifest.get("page"), _expected_page(spec), "page", errors)
    _require_mapping_types(manifest.get("active_target"), _expected_target(spec), "active_target", errors)
    if manifest.get("reserved_spot_channels") != RESERVED_UV_CHANNELS:
        errors.append("reserved_spot_channels violates hard-zero UV policy")
    if manifest.get("page") != _expected_page(spec):
        errors.append("page violates fixed A4/720-DPI/100%-scale contract")
    if manifest.get("active_target") != _expected_target(spec):
        errors.append("active_target violates fixed 177x170-mm placement contract")
    expected_artifacts = {
        "tiff": ARTIFACT_NAMES["tiff"],
        "preview": ARTIFACT_NAMES["preview"],
        "source_tiff_photometric": "separated",
        "source_tiff_samples_per_pixel": 4,
    }
    _require_mapping_types(manifest.get("artifacts"), expected_artifacts, "artifacts", errors)
    if manifest.get("artifacts") != expected_artifacts:
        errors.append("artifacts differs from fixed release metadata")
    expected_fiducials = _expected_fiducials(spec)
    manifest_fiducials = manifest.get("fiducials")
    if isinstance(manifest_fiducials, list) and len(manifest_fiducials) == len(expected_fiducials):
        for index, (actual, expected) in enumerate(zip(manifest_fiducials, expected_fiducials)):
            _require_mapping_types(actual, expected, f"fiducials[{index}]", errors)
    if manifest_fiducials != expected_fiducials:
        errors.append("fiducials differ from fixed target geometry")

    manifest_patches = manifest.get("patches")
    expected_patches = build_patches(spec)
    if not isinstance(manifest_patches, list) or len(manifest_patches) != len(expected_patches):
        errors.append("patch manifest does not contain exactly 224 patches")
        return
    expected_patch_keys = {"id", "family", "cmyk", "reserved_spot_coverage", "rect_mm", "rect_px", "grid"}
    for expected, actual in zip(expected_patches, manifest_patches):
        if not isinstance(actual, dict):
            errors.append(f"{expected.patch_id} manifest entry is not an object")
            continue
        if set(actual) != expected_patch_keys:
            errors.append(f"{expected.patch_id} manifest schema differs from fixed chart plan")
            continue
        planned = _expected_patch_manifest(spec, expected)
        _require_mapping_types(actual.get("cmyk"), planned["cmyk"], f"{expected.patch_id}.cmyk", errors)
        _require_mapping_types(
            actual.get("reserved_spot_coverage"),
            RESERVED_UV_CHANNELS,
            f"{expected.patch_id}.reserved_spot_coverage",
            errors,
        )
        _require_mapping_types(actual.get("rect_mm"), planned["rect_mm"], f"{expected.patch_id}.rect_mm", errors)
        _require_mapping_types(actual.get("rect_px"), planned["rect_px"], f"{expected.patch_id}.rect_px", errors)
        _require_mapping_types(actual.get("grid"), planned["grid"], f"{expected.patch_id}.grid", errors)
        if actual.get("id") != planned["id"] or actual.get("family") != planned["family"]:
            errors.append(f"{expected.patch_id} manifest identity differs from fixed chart plan")
        if actual.get("cmyk") != planned["cmyk"]:
            errors.append(f"{expected.patch_id} CMYK differs from fixed chart plan")
        if actual.get("reserved_spot_coverage") != RESERVED_UV_CHANNELS:
            errors.append(f"{expected.patch_id} violates hard-zero UV policy")
        if actual.get("rect_mm") != planned["rect_mm"]:
            errors.append(f"{expected.patch_id} millimetre rectangle differs from fixed chart plan")
        if actual.get("rect_px") != planned["rect_px"]:
            errors.append(f"{expected.patch_id} pixel rectangle differs from fixed chart plan")
        if actual.get("grid") != planned["grid"]:
            errors.append(f"{expected.patch_id} grid differs from fixed chart plan")


def _audit_fiducials_and_target_background(raster: np.ndarray, spec: ChartSpec, errors: list[str]) -> int:
    x, y = spec.target_x_px, spec.target_y_px
    target_right, target_bottom = x + spec.target_width_px, y + spec.target_height_px
    target = raster[y:target_bottom, x:target_right]
    allowed = np.zeros(target.shape[:2], dtype=bool)

    for patch in build_patches(spec):
        left, top, patch_right, patch_bottom = cmyk_patch_pixel_bounds(spec, patch)
        actual = raster[top:patch_bottom, left:patch_right]
        expected = np.array([patch.coverage[channel] for channel in CMYK_CHANNELS], dtype=np.uint8)
        if not np.all(actual == expected):
            errors.append(f"{patch.patch_id} patch pixels differ from declared CMYK coverage")
        allowed[top - y : patch_bottom - y, left - x : patch_right - x] = True

    radius = round(2.5 * spec.dpi / 25.4)
    white_radius = round(0.9 * spec.dpi / 25.4)
    for center_x, center_y in _fiducial_centers_px(spec):
        ftop = center_y - radius
        fbottom = center_y + radius + 1
        fleft = center_x - radius
        fright = center_x + radius + 1
        yy, xx = np.ogrid[ftop:fbottom, fleft:fright]
        distance_squared = (xx - center_x) ** 2 + (yy - center_y) ** 2
        expected = np.zeros((fbottom - ftop, fright - fleft, 4), dtype=np.uint8)
        expected[:, :, 3][distance_squared <= radius**2] = 255
        expected[:, :, 3][distance_squared <= white_radius**2] = 0
        actual = raster[ftop:fbottom, fleft:fright]
        if not np.array_equal(actual, expected):
            errors.append(f"Fiducial at {center_x},{center_y} is not the approved K-only bullseye")
        allowed[ftop - y : fbottom - y, fleft - x : fright - x] = True

    unexpected_target_pixels = _nonzero_pixels(target[~allowed].reshape(-1, 1, 4))
    if unexpected_target_pixels:
        errors.append(f"Found {unexpected_target_pixels} unexpected nonzero pixel(s) inside active target")

    return (
        _nonzero_pixels(raster[:y, :, :])
        + _nonzero_pixels(raster[target_bottom:, :, :])
        + _nonzero_pixels(raster[y:target_bottom, :x, :])
        + _nonzero_pixels(raster[y:target_bottom, target_right:, :])
    )


def audit_chart_artifact(tiff_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Validate immutable layout, TIFF encoding, manifest and every rendered pixel."""
    spec = build_chart_spec()
    errors: list[str] = []
    samples_per_pixel: int | None = None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _report([f"Cannot parse manifest: {type(exc).__name__}: {exc}"], spec=spec)
    _validate_manifest(manifest, spec, errors)
    if errors:
        return _report(errors, spec=spec)

    try:
        with tifffile.TiffFile(tiff_path) as document:
            if len(document.pages) != 1:
                return _report([f"Expected one TIFF page, got {len(document.pages)}"], spec=spec)
            page = document.pages[0]
            samples_per_pixel = int(page.samplesperpixel)
            if page.shape != (spec.page_height_px, spec.page_width_px, 4):
                errors.append(f"Shape is {page.shape}, expected {(spec.page_height_px, spec.page_width_px, 4)}")
            if page.samplesperpixel != 4:
                errors.append(f"Expected 4 CMYK samples, got {page.samplesperpixel}")
            if page.photometric.name != "SEPARATED":
                errors.append(f"Photometric is {page.photometric.name}, expected SEPARATED")
            if page.planarconfig.name != "CONTIG":
                errors.append(f"Planar configuration is {page.planarconfig.name}, expected CONTIG")
            if page.bitspersample != 8 or page.dtype != np.dtype(np.uint8):
                errors.append(f"Samples are {page.bitspersample}-bit {page.dtype}, expected 8-bit uint8")
            if page.resolutionunit.name != "INCH":
                errors.append(f"Resolution unit is {page.resolutionunit.name}, expected INCH")
            x_resolution, y_resolution = page.resolution
            if abs(x_resolution - spec.dpi) > 1e-6 or abs(y_resolution - spec.dpi) > 1e-6:
                errors.append(f"Resolution is {page.resolution}, expected {spec.dpi} DPI")
            inkset = page.tags.get(332)
            if inkset is None or inkset.value != 1:
                errors.append("InkSet is not explicit CMYK (1)")
            number_of_inks = page.tags.get(334)
            if number_of_inks is None or number_of_inks.value != 4:
                errors.append("NumberOfInks is not explicit 4")
    except Exception as exc:
        return _report([f"Cannot read TIFF: {type(exc).__name__}: {exc}"], samples_per_pixel=samples_per_pixel, spec=spec)

    if errors:
        return _report(errors, samples_per_pixel=samples_per_pixel, spec=spec)
    try:
        raster = tifffile.memmap(tiff_path)
        outside_count = _audit_fiducials_and_target_background(raster, spec, errors)
    except Exception as exc:
        return _report(
            [f"Cannot raster-audit TIFF: {type(exc).__name__}: {exc}"],
            samples_per_pixel=samples_per_pixel,
            spec=spec,
        )

    if outside_count:
        errors.append(f"Found {outside_count} nonzero pixel(s) outside active target")
    return _report(
        errors,
        patches_checked=len(build_patches(spec)),
        outside_count=outside_count,
        samples_per_pixel=samples_per_pixel,
        spec=spec,
    )
