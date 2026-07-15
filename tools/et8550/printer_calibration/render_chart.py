"""Render the approved printer-characterisation plan into raw CMYK artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence
from uuid import uuid4

import numpy as np
from PIL import Image, ImageDraw
import tifffile

from chart_artifact import build_manifest, cmyk_patch_pixel_bounds
from chart_spec import ChartSpec, Patch, validate_chart


@dataclass(frozen=True)
class RenderedArtifacts:
    tiff_path: Path
    preview_path: Path
    manifest_path: Path


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


def _draw_fiducials(raster: np.ndarray, spec: ChartSpec) -> None:
    """Draw small K-only bullseyes in the otherwise unused target inset."""
    radius = round(2.5 * spec.dpi / 25.4)
    white_radius = round(0.9 * spec.dpi / 25.4)
    for center_x, center_y in _fiducial_centers_px(spec):
        top = max(0, center_y - radius)
        bottom = min(raster.shape[0], center_y + radius + 1)
        left = max(0, center_x - radius)
        right = min(raster.shape[1], center_x + radius + 1)
        yy, xx = np.ogrid[top:bottom, left:right]
        distance_squared = (xx - center_x) ** 2 + (yy - center_y) ** 2
        black_mask = distance_squared <= radius**2
        white_mask = distance_squared <= white_radius**2
        channel = raster[top:bottom, left:right, 3]
        channel[black_mask] = 255
        channel[white_mask] = 0


def _render_cmyk_raster(spec: ChartSpec, patches: Sequence[Patch]) -> np.ndarray:
    raster = np.zeros((spec.page_height_px, spec.page_width_px, 4), dtype=np.uint8)
    for patch in patches:
        left, top, right, bottom = cmyk_patch_pixel_bounds(spec, patch)
        raster[top:bottom, left:right, 0] = patch.coverage["C"]
        raster[top:bottom, left:right, 1] = patch.coverage["M"]
        raster[top:bottom, left:right, 2] = patch.coverage["Y"]
        raster[top:bottom, left:right, 3] = patch.coverage["K"]
    _draw_fiducials(raster, spec)
    return raster


def _nominal_preview_rgb(coverage: dict[str, int]) -> tuple[int, int, int]:
    """Provide a clearly nominal CMYK preview; it is not a colour prediction."""
    c, m, y, k = (coverage[channel] / 255 for channel in ("C", "M", "Y", "K"))
    return (
        round(255 * (1 - c) * (1 - k)),
        round(255 * (1 - m) * (1 - k)),
        round(255 * (1 - y) * (1 - k)),
    )


def _write_preview(path: Path, spec: ChartSpec, patches: Sequence[Patch]) -> None:
    preview_width = 1200
    scale = preview_width / spec.page_width_px
    preview_height = round(spec.page_height_px * scale)
    image = Image.new("RGB", (preview_width, preview_height), "white")
    draw = ImageDraw.Draw(image)
    for patch in patches:
        left, top, right, bottom = cmyk_patch_pixel_bounds(spec, patch)
        draw.rectangle(
            (round(left * scale), round(top * scale), round(right * scale), round(bottom * scale)),
            fill=_nominal_preview_rgb(dict(patch.coverage)),
        )
    radius = max(2, round(2.5 * spec.dpi / 25.4 * scale))
    inner_radius = max(1, round(0.9 * spec.dpi / 25.4 * scale))
    for center_x, center_y in _fiducial_centers_px(spec):
        x, y = round(center_x * scale), round(center_y * scale)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="black")
        draw.ellipse((x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius), fill="white")
    image.save(path, format="PNG", optimize=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def render_chart(output_dir: Path, spec: ChartSpec, patches: Sequence[Patch]) -> RenderedArtifacts:
    """Stage, built-in audit, then atomically publish a coherent artifact release."""
    validate_chart(spec, patches)
    output_dir.mkdir(parents=True, exist_ok=True)
    releases_dir = output_dir / "releases"
    releases_dir.mkdir(exist_ok=True)
    names = {
        "tiff": "aflabox-printer-characterisation-v1-a4-720dpi.tiff",
        "preview": "aflabox-printer-characterisation-v1-a4-preview.png",
        "manifest": "aflabox-printer-characterisation-v1.manifest.json",
    }

    # Import only here to avoid the chart renderer/auditor import cycle. This
    # mandatory built-in check has no production injection or bypass path.
    from chart_audit import audit_chart_artifact

    with TemporaryDirectory(prefix=".chart-stage-", dir=releases_dir) as staging_directory:
        staging = Path(staging_directory)
        tiff_path = staging / names["tiff"]
        preview_path = staging / names["preview"]
        manifest_path = staging / names["manifest"]

        raster = _render_cmyk_raster(spec, patches)
        tifffile.imwrite(
            tiff_path,
            raster,
            photometric="separated",
            planarconfig="contig",
            resolution=(spec.dpi, spec.dpi),
            resolutionunit="INCH",
            # TIFF InkSet=1 (CMYK) and NumberOfInks=4 make the physical
            # source-plane contract explicit rather than inferred.
            extratags=[(332, "H", 1, 1, False), (334, "H", 1, 4, False)],
            metadata=None,
        )
        del raster

        _write_preview(preview_path, spec, patches)
        manifest = build_manifest(spec, patches)
        manifest["artifacts"] = {
            "tiff": names["tiff"],
            "preview": names["preview"],
            "source_tiff_photometric": "separated",
            "source_tiff_samples_per_pixel": 4,
        }
        manifest["fiducials"] = [
            {"x_px": x, "y_px": y, "kind": "K-only bullseye"}
            for x, y in _fiducial_centers_px(spec)
        ]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        audit_report = audit_chart_artifact(tiff_path, manifest_path)
        if not audit_report.get("passed", False):
            raise RuntimeError(f"staged artifact audit failed: {audit_report.get('errors', [])}")

        release_name = f"release-{uuid4().hex}"
        release_dir = releases_dir / release_name
        staging.replace(release_dir)

    current = {
        "schema_version": 1,
        "release": release_name,
        "artifacts": {name: f"releases/{release_name}/{filename}" for name, filename in names.items()},
        "sha256": {
            "tiff": _sha256(release_dir / names["tiff"]),
            "preview": _sha256(release_dir / names["preview"]),
            "manifest": _sha256(release_dir / names["manifest"]),
        },
    }
    current_temporary = output_dir / f".current-{uuid4().hex}.json"
    current_temporary.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(current_temporary, output_dir / "current.json")

    return RenderedArtifacts(
        tiff_path=release_dir / names["tiff"],
        preview_path=release_dir / names["preview"],
        manifest_path=release_dir / names["manifest"],
    )
