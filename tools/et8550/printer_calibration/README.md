# Aflabox printer-characterisation chart

This directory contains the printer-only V1 characterization target for the raw
CMYK Gutenprint path. It is intentionally independent of camera colour
calibration; qbox10 is used only to measure the rendered patches after its own
calibration is available.

## Fixed V1 print contract

| Item | Value |
|---|---:|
| Paper | A4 (`210 × 297 mm`) |
| Active chart | `177 × 170 mm` |
| A4 placement | `x=16.5 mm`, `y=63.5 mm` |
| Raster | `5953 × 8419 px` at `720 DPI` |
| Active raster | `5017 × 4819 px` |
| Source TIFF | contiguous 8-bit separated `CMYK`; `InkSet=CMYK`, `NumberOfInks=4` |
| Source plane order | `C, M, Y, K` |
| Gutenprint raw stream order | `K, C, M, Y` |
| Scale | exactly `100%`; no fit, crop or driver rescale |

The chart contains 224 patches: Neugebauer primaries, single-channel ramps,
three visible-colour pair grids, neutral/GCR samples, deterministic interior
samples and repeated controls.

## UV safety policy

This V1 ET-2856 chart has only four physical source planes. Its manifest still
records two hard-zero logical UV spot channels (`UV_A`, `UV_B`) for compatibility
with the future six-channel ET-8550 pipeline.

No automatic Epson RGB separation is used. Source TIFF CMYK is explicitly
reordered by `src/testpattern/printraw.c` for the raw Epson stream. Future
six-channel jobs must be rejected unless UV spots are zero outside their
approved masks.

## Render and audit

Run from the repository root:

```bash
PYTHONPATH=tools/et8550/printer_calibration python3 - <<'PY'
from pathlib import Path
from chart_spec import build_chart_spec, build_patches
from render_chart import render_chart
from chart_audit import audit_chart_artifact

output = Path("artifacts/printer-characterisation-v1")
spec = build_chart_spec()
artifacts = render_chart(output, spec, build_patches(spec))
report = audit_chart_artifact(artifacts.tiff_path, artifacts.manifest_path)
print(report)
if not report["passed"]:
    raise SystemExit("artifact audit failed")
PY
```

Do not print until both the TIFF/manifest audit and decoded-printer-spool audit
pass. Rendering stages an entire release privately, audits it, then atomically
updates `current.json` to point at that immutable release under `releases/`.
Always resolve the TIFF and manifest through `current.json`; loose legacy files
in the artifact root are not authoritative. The spool must be produced with
`InputImageType=Raw`, `ColorCorrection=Raw`, `RawChannels=4`, A4 page size and
the native `720sw` resolution used by `printraw.c`.

## Tests

```bash
python3 -m unittest \
  tools/et8550/printer_calibration/tests/test_chart_spec.py \
  tools/et8550/printer_calibration/tests/test_chart_artifact.py \
  tools/et8550/printer_calibration/tests/test_render_chart.py \
  tools/et8550/printer_calibration/tests/test_chart_audit.py -v
```
