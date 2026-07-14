# Epson ET-8550 Pigmera ETX calibration

This branch contains an experimental Gutenprint pipeline for the Epson ET-8550,
developed for 106 × 152 mm die-cut glossy labels.

## Physically validated pipeline

The following combination has been tested on an ET-8550 converted to Farbenwerk
Pigmera ETX pigment ink:

- 106 × 152 mm logical page
- square source pixels
- `GlossyPhoto`
- `HighPhoto`
- direct `Resolution=1440x1440dpi`
- `StpPrintingDirection=Bidirectional`
- `StpDitherAlgorithm=EvenTone`
- `StpColorCorrection=Accurate`
- `StpGCRLower=0`
- `StpGCRUpper=0`
- `StpBlackTrans=1000`
- `StpiShrinkOutput=crop`
- `print-scaling=none`
- `fit-to-page=Off`

The generated PPD does not expose `1440x1440dpi` in its visible resolution list,
but Gutenprint accepts and uses the token directly. Filter logs confirmed
`HWResolution = [ 1440 1440 ]`.

## Ink architecture

Raw diagnostic output established this physical channel order:

| Raw index | Physical ink |
|---:|---|
| 0 | BK |
| 1 | C |
| 2 | M |
| 3 | Y |
| 4 | GY |
| 5 | PB |

For the glossy RGB path, PB + GY are used as the photo-black/gray pair. BK remains
available in the physical raw inkset, but is not forced into the glossy photo path.

## Color-engine correction

The original ET-8550 CMYKk inkset was bound to fixed CMY hue curves. Removing
those three fixed `HueCurve` references restored a much more useful traditional
RGB separation: orange appeared correctly, red moved out of the pink failure
region, and neutral output remained usable.

A physical red pinpoint test then established:

```text
source RGB(255, 0, 36) → visually correct printed red
```

The calibrated controller therefore applies a local 65³ `Color3DLUT` around the
saturated red sector:

- center correction: approximately −8.47° toward magenta
- smooth cosine fade to zero at ±30°
- neutral colors unaffected
- orange preserved
- magenta preserved

This is a global printer calibration step, not per-label artwork compensation.

## Included tools

- `ET8550-standard-hue-engine-v1.sh`
  Applies/restores the CMYKk hue-engine change.

- `ET8550-color-test-v4-red-sector-lut.py`
  Full physical validation chart using the calibrated local red-sector LUT.

## Scope and warning

This work is experimental and currently validated only for the tested combination:

- Epson ET-8550
- Farbenwerk Pigmera ETX pigment conversion
- glossy inkjet label media
- the settings documented above

Stock Epson ink, other pigment conversions, and other media will require their
own physical calibration.
