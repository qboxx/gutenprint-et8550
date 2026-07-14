# TODO — Epson ET-8550 Pigmera ETX driver

This document tracks the remaining public driver and color-calibration work for
the experimental Epson ET-8550 Pigmera ETX Gutenprint branch.

## High priority

### Pigmera-specific ink limits

- Determine the maximum usable total ink load on glossy inkjet label media.
- Check for coalescence, muddy dark colors, edge softening, slow drying and poor
  adhesion.
- Create conservative media-specific limits rather than one universal value.
- Keep Gutenprint's mechanical `escp2_density` values separate from actual color
  and media ink-limit calibration.

### Individual channel density

Calibrate the effective density of:

- Cyan
- Magenta
- Yellow
- Photo Black
- Gray

The goal is balanced channel strength without oversaturation or unnecessary ink
load.

### Photo Black / Gray transition

- Tune the Gray to Photo Black transition.
- Preserve smooth neutral gradients.
- Avoid visible transition bands.
- Check shadow detail and maximum black density.
- Validate neutral output at multiple gray levels.

## Color calibration

### Integrate the red correction cleanly

A physical test established that:

```text
source RGB(255, 0, 36) -> visually correct printed red
```

The current test pipeline uses a local red-sector 3D LUT. Remaining work:

- move the correction into a reusable global color-management path;
- avoid per-image manual adjustment;
- preserve orange, magenta and neutral colors;
- document the exact transform and test conditions.

### Full gamut validation

Systematically test:

- red
- orange
- yellow
- green
- cyan
- blue
- violet
- magenta
- neutral grays
- dark saturated colors
- pastel colors
- smooth gradients

The current red, orange and neutral results are promising, but the complete
gamut has not yet been fully characterized.

### ICC or equivalent color-management workflow

- Evaluate whether an ICC workflow is appropriate for Pigmera ETX and the tested
  glossy media.
- Compare ICC-based correction with Gutenprint curves and LUT-based correction.
- Keep media, ink and printer assumptions explicit.
- Avoid presenting one profile as universal across unrelated media.

## Media profiles

- Create clearly named Pigmera ETX media presets.
- Start with the physically tested glossy label stock.
- Add separate profiles only after physical validation.
- Document drying time, adhesion and visual density for each medium.
- Keep stock Epson Claria media assumptions separate from Pigmera ETX results.

## Resolution and quality mapping

- Keep the physically validated 1440 x 1440 mode documented.
- Verify the direct Gutenprint `Resolution=1440x1440dpi` token across clean
  builds.
- Confirm filter logs report square 1440 x 1440 output.
- Validate quality presets without silent fallback to 1440 x 720.
- Continue using square source pixels for geometry tests.

## Build and installation

- Write clean build instructions for Ubuntu and WSL.
- Document required dependencies.
- Add a reproducible install script.
- Document PPD generation.
- Document CUPS queue creation.
- Add uninstall and restore instructions.
- Verify a clean clone can build without relying on local experimental files.

## Regression tests

Create repeatable tests for:

- model 139 loading `pigmera_etx.xml`;
- original `claria_et.xml` remaining unchanged;
- six physical raw channels;
- PB/GY glossy architecture;
- borderless 106 x 152 mm geometry;
- crop/no-scale behavior;
- bidirectional output;
- direct 1440 x 1440 mode;
- neutral gray output;
- red-sector calibration anchors.

## Documentation

- Clearly distinguish stock Claria from Pigmera ETX.
- Mark all physically validated findings as such.
- Mark unverified values and TODO parameters explicitly.
- Document exact ink, media, resolution and quality settings used for each test.
- Avoid claiming universal compatibility before additional physical validation.

## Current validated baseline

```text
Printer: Epson ET-8550
Ink: Farbenwerk Pigmera ETX pigment conversion
Page: 106 x 152 mm
Source pixels: square
Media: glossy inkjet label stock
Quality: HighPhoto
Resolution: direct 1440 x 1440
Direction: Bidirectional
Scaling: crop / no scale
Black path: Photo Black + Gray
Neutral test: GCR lower 0, GCR upper 0
Red anchor: RGB(255, 0, 36)
```

## Out of scope

This repository tracks the public printer-driver, ink architecture, color
calibration and installation work only.
