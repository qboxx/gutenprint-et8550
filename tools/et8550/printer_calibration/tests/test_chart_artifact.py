import sys
import unittest
from pathlib import Path

import numpy as np

MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from chart_spec import build_chart_spec, build_patches
from chart_artifact import (
    build_manifest,
    cmyk_patch_pixel_bounds,
    assert_reserved_spot_planes_zero,
)


class ChartArtifactTests(unittest.TestCase):
    def setUp(self):
        self.spec = build_chart_spec()
        self.patches = build_patches(self.spec)

    def test_manifest_declares_a4_scale_cmyk_source_order_and_hard_zero_uv_policy(self):
        manifest = build_manifest(self.spec, self.patches)
        self.assertEqual(manifest["source_plane_order"], ["C", "M", "Y", "K"])
        self.assertEqual(manifest["printer_stream_order"], ["K", "C", "M", "Y"])
        self.assertEqual(manifest["page"], {
            "width_mm": 210,
            "height_mm": 297,
            "width_px": 5953,
            "height_px": 8419,
            "dpi": 720,
            "scale": "100%",
        })
        self.assertEqual(manifest["reserved_spot_channels"], {"UV_A": 0, "UV_B": 0})
        self.assertEqual(len(manifest["patches"]), 224)

    def test_patch_pixel_bounds_are_within_the_a4_raster(self):
        for patch in self.patches:
            left, top, right, bottom = cmyk_patch_pixel_bounds(self.spec, patch)
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(right, self.spec.page_width_px)
            self.assertLessEqual(bottom, self.spec.page_height_px)
            self.assertGreater(right, left)
            self.assertGreater(bottom, top)

    def test_reserved_spot_plane_guard_accepts_zero_and_rejects_any_nonzero_pixel(self):
        planes = np.zeros((4, 5, 6), dtype=np.uint8)
        assert_reserved_spot_planes_zero(planes, {"UV_A": 4, "UV_B": 5})
        planes[2, 3, 5] = 1
        with self.assertRaisesRegex(ValueError, "UV_B"):
            assert_reserved_spot_planes_zero(planes, {"UV_A": 4, "UV_B": 5})


if __name__ == "__main__":
    unittest.main()
