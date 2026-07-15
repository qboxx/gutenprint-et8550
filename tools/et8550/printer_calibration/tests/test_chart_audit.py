import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile

MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from chart_spec import build_chart_spec, build_patches
from render_chart import render_chart
from chart_audit import audit_chart_artifact


class ChartAuditTests(unittest.TestCase):
    def setUp(self):
        self.spec = build_chart_spec()
        self.patches = build_patches(self.spec)

    def _render(self, directory: str):
        return render_chart(Path(directory), self.spec, self.patches)

    def test_audit_accepts_the_exact_rendered_a4_cmyk_chart(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self._render(directory)
            report = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["patches_checked"], 224)
        self.assertEqual(report["outside_active_target_nonzero_pixels"], 0)
        self.assertEqual(report["source_plane_order"], ["C", "M", "Y", "K"])
        self.assertEqual(report["samples_per_pixel"], 4)

    def test_audit_rejects_changed_plane_order_and_nonzero_uv_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self._render(directory)
            manifest = json.loads(artifacts.manifest_path.read_text())
            manifest["source_plane_order"] = ["K", "C", "M", "Y"]
            manifest["reserved_spot_channels"]["UV_A"] = 1
            artifacts.manifest_path.write_text(json.dumps(manifest))
            report = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)

        self.assertFalse(report["passed"])
        self.assertTrue(any("source_plane_order" in error for error in report["errors"]))
        self.assertTrue(any("reserved_spot_channels" in error for error in report["errors"]))

    def test_audit_rejects_nonzero_uv_coverage_in_any_patch_manifest_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self._render(directory)
            manifest = json.loads(artifacts.manifest_path.read_text())
            manifest["patches"][20]["reserved_spot_coverage"]["UV_B"] = 255
            artifacts.manifest_path.write_text(json.dumps(manifest))
            report = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)

        self.assertFalse(report["passed"])
        self.assertTrue(any("UV policy" in error for error in report["errors"]))

    def test_audit_rejects_tampering_of_measurement_geometry_and_release_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self._render(directory)
            manifest = json.loads(artifacts.manifest_path.read_text())
            manifest["patches"][0]["rect_mm"]["x"] += 0.1
            manifest["patches"][1]["grid"]["row"] = 99
            manifest["artifacts"]["tiff"] = "wrong.tiff"
            manifest["fiducials"][0]["x_px"] += 1
            artifacts.manifest_path.write_text(json.dumps(manifest))
            report = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)

        self.assertFalse(report["passed"])
        self.assertTrue(any("millimetre rectangle" in error for error in report["errors"]))
        self.assertTrue(any("grid" in error for error in report["errors"]))
        self.assertTrue(any("artifacts" in error for error in report["errors"]))
        self.assertTrue(any("fiducials" in error for error in report["errors"]))

    def test_audit_rejects_a_correct_centre_with_a_corrupted_patch_edge(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self._render(directory)
            manifest = json.loads(artifacts.manifest_path.read_text())
            rect = manifest["patches"][5]["rect_px"]
            raster = tifffile.memmap(artifacts.tiff_path, mode="r+")
            raster[rect["top"], rect["left"]] = [255, 255, 255, 255]
            raster.flush()
            report = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)

        self.assertFalse(report["passed"])
        self.assertTrue(any("patch pixels" in error for error in report["errors"]))

    def test_audit_rejects_boolean_values_in_integer_manifest_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self._render(directory)
            manifest = json.loads(artifacts.manifest_path.read_text())
            # In Python, bool is a subclass of int. These values compare equal
            # to 1/0 unless the audit explicitly rejects their JSON types.
            manifest["schema_version"] = True
            manifest["reserved_spot_channels"]["UV_A"] = False
            manifest["patches"][0]["cmyk"]["C"] = False
            manifest["patches"][0]["reserved_spot_coverage"]["UV_B"] = False
            manifest["patches"][0]["grid"]["row"] = False
            artifacts.manifest_path.write_text(json.dumps(manifest))
            report = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)

        self.assertFalse(report["passed"])
        self.assertTrue(any("type" in error for error in report["errors"]))

    def test_audit_returns_a_structured_failure_for_malformed_manifest_and_tiff(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self._render(directory)
            artifacts.manifest_path.write_text("{}")
            malformed_manifest = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)
            tifffile.imwrite(artifacts.tiff_path, np.zeros((10, 10), dtype=np.uint8), photometric="minisblack")
            malformed_tiff = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)

        self.assertFalse(malformed_manifest["passed"])
        self.assertTrue(malformed_manifest["errors"])
        self.assertFalse(malformed_tiff["passed"])
        self.assertTrue(malformed_tiff["errors"])


if __name__ == "__main__":
    unittest.main()
