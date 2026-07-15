import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tifffile

MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from chart_spec import build_chart_spec, build_patches
from chart_artifact import cmyk_patch_pixel_bounds
from render_chart import render_chart


class RenderChartTests(unittest.TestCase):
    def setUp(self):
        self.spec = build_chart_spec()
        self.patches = build_patches(self.spec)

    def test_renderer_writes_a4_720dpi_separated_cmyk_tiff_and_preview(self):
        cyan_patch = next(
            patch for patch in self.patches
            if patch.coverage == {"C": 255, "M": 0, "Y": 0, "K": 0}
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            artifacts = render_chart(output, self.spec, self.patches)
            self.assertTrue(artifacts.tiff_path.is_file())
            self.assertTrue(artifacts.preview_path.is_file())
            self.assertTrue(artifacts.manifest_path.is_file())
            current = json.loads((output / "current.json").read_text())
            self.assertEqual(current["release"], artifacts.tiff_path.parent.name)

            with tifffile.TiffFile(artifacts.tiff_path) as document:
                page = document.pages[0]
                self.assertEqual(page.shape, (8419, 5953, 4))
                self.assertEqual(page.samplesperpixel, 4)
                self.assertEqual(page.photometric.name, "SEPARATED")
                self.assertEqual(page.planarconfig.name, "CONTIG")
                self.assertEqual(page.tags[332].value, 1)  # InkSet: CMYK
                self.assertEqual(page.tags[334].value, 4)  # NumberOfInks
                x_resolution, y_resolution = page.resolution
                self.assertAlmostEqual(x_resolution, 720, places=6)
                self.assertAlmostEqual(y_resolution, 720, places=6)

            raster = tifffile.memmap(artifacts.tiff_path)
            left, top, right, bottom = cmyk_patch_pixel_bounds(self.spec, cyan_patch)
            sample = raster[(top + bottom) // 2, (left + right) // 2].tolist()
            self.assertEqual(sample, [255, 0, 0, 0])
            self.assertEqual(raster[0, 0].tolist(), [0, 0, 0, 0])

    def test_renderer_does_not_publish_a_release_or_current_pointer_when_audit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch(
                "chart_audit.audit_chart_artifact",
                return_value={"passed": False, "errors": ["synthetic test rejection"]},
            ):
                with self.assertRaisesRegex(RuntimeError, "staged artifact audit failed"):
                    render_chart(output, self.spec, self.patches)
            self.assertFalse((output / "current.json").exists())
            releases = output / "releases"
            self.assertTrue(not releases.exists() or not any(releases.iterdir()))


if __name__ == "__main__":
    unittest.main()
