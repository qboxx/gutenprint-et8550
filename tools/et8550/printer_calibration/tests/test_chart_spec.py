import sys
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from chart_spec import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    CMYK_CHANNELS,
    RESERVED_UV_CHANNELS,
    build_chart_spec,
    build_patches,
    validate_chart,
)


class ChartSpecTests(unittest.TestCase):
    def setUp(self):
        self.spec = build_chart_spec()
        self.patches = build_patches(self.spec)

    def test_active_target_is_centered_on_a4_at_exact_requested_size(self):
        self.assertEqual((A4_WIDTH_MM, A4_HEIGHT_MM), (210, 297))
        self.assertEqual((self.spec.target_width_mm, self.spec.target_height_mm), (177, 170))
        self.assertEqual(self.spec.target_x_mm, 16.5)
        self.assertEqual(self.spec.target_y_mm, 63.5)
        self.assertEqual((self.spec.page_width_px, self.spec.page_height_px), (5953, 8419))
        self.assertEqual((self.spec.target_width_px, self.spec.target_height_px), (5017, 4819))

    def test_patch_plan_fills_exact_14_by_16_grid_with_unique_ids(self):
        self.assertEqual((self.spec.grid_columns, self.spec.grid_rows), (14, 16))
        self.assertEqual(len(self.patches), 224)
        self.assertEqual(len({patch.patch_id for patch in self.patches}), 224)
        self.assertEqual({patch.family for patch in self.patches}, {
            "neugebauer", "ramp", "pairwise", "neutral_gcr", "space_filling", "control"
        })

    def test_every_patch_is_printable_cmyk_and_reserved_uv_channels_are_zero(self):
        for patch in self.patches:
            self.assertEqual(set(patch.coverage), set(CMYK_CHANNELS))
            self.assertTrue(all(0 <= value <= 255 for value in patch.coverage.values()))
            self.assertEqual(patch.reserved_spot_coverage, RESERVED_UV_CHANNELS)

    def test_patch_boxes_are_inside_target_and_do_not_overlap(self):
        for patch in self.patches:
            self.assertGreaterEqual(patch.x_mm, self.spec.target_x_mm)
            self.assertGreaterEqual(patch.y_mm, self.spec.target_y_mm)
            self.assertLessEqual(patch.x_mm + patch.width_mm, self.spec.target_x_mm + self.spec.target_width_mm)
            self.assertLessEqual(patch.y_mm + patch.height_mm, self.spec.target_y_mm + self.spec.target_height_mm)
        validate_chart(self.spec, self.patches)


if __name__ == "__main__":
    unittest.main()
