# Afla_books four-channel RGB/JPEG print-to-qbox calibration — PRD

> **Status:** Current active implementation scope. It supersedes any suggestion that the present ET-2856 work must use raw CMYK or six channels.
>
> **Goal:** Rapidly and reproducibly calibrate normal four-colour prints by repeatedly comparing the intended sRGB chart colours with the colours and print-quality metrics measured by qbox10, then making safe RGB input corrections for the next chart.

## 1. What we are doing now

The printer currently available is the four-reservoir Epson ET-2856:

```text
Cyan, Magenta, Yellow, Black
```

The immediate job is **regular colour printing**. We print a large, deliberate set of RGB colours, place the sheet in qbox10, measure what was actually produced, and adjust the next RGB image. This repeats until the output is acceptably close and clean.

```text
known sRGB/JPEG patch values
→ frozen Windows Epson print route
→ qbox10 capture
→ compare expected versus observed patch values and risk metrics
→ calculate adjusted RGB patch values
→ next JPEG chart
```

This is an end-to-end calibration of the **image → Windows driver → printer → paper → qbox10** system. It is valid and useful even though Windows chooses the underlying CMYK, black generation and dot pattern.

We control where and how strongly the printer is asked to print by changing the RGB value of each image region. We do not claim separate physical K/C/M/Y droplet control in this current route.

## 2. Current print contract

The print input is an audited, high-quality **sRGB JPEG** rather than a raw TIFF:

| Property | Locked current value |
|---|---|
| Page | A4, portrait, actual size — no fit/crop/rescale |
| Input | RGB JPEG, embedded sRGB ICC, 720 DPI metadata |
| JPEG encoding | Quality 95 or greater, 4:4:4/no chroma subsampling, deterministic encoder settings |
| Windows queue | `EPSONAACAF2 (ET-2850 Series)` |
| Driver | Microsoft IPP Class Driver on the existing WSD queue |
| Measurement | qbox10 White-light RAW/DNG capture with fixed exposure, gain and lens setting |
| Next active target | centred **160 × 160 mm** on A4 |

JPEG is appropriate here because every chart patch is a large, uniform colour field. The JPEG source must still be hashed, tagged, sized, and sampled after encoding. A source-pixel audit must prove that the interior of every rendered patch equals its declared RGB input before it is submitted.

Raw TIFF/LPR is **not required** for this four-channel loop and must not be used. A raw file sent to LPR is not a supported printer language on the ET-2856.

## 3. What qbox10 measures

After fiducial registration and bounded local paper normalisation, every patch gets:

```text
input_rgb                       exact JPEG colour in the patch interior
observed_normalised_rgb         qbox10 result under the locked White-light setup
colour error                    input/target versus observed colour in defined colour space
saturation residual             chroma mismatch
hue residual                    hue mismatch, excluding near-neutral patches
absolute gutter contamination   visible ink displacement into the nominally blank gutter
relative bleed                  gutter contamination relative to interior contrast
opacity/density proxy           interior contrast relative to local paper
interior uniformity             patch mottle, streaks, or unevenness
```

The present 224-patch physical sheet supplies a valid RGB baseline: the JPEG interior pixels were verified to match all **224/224** declared `target_rgb` values. Its qbox report contains the measured output for every patch. It is therefore the right evidence for an RGB feedback model; it is not evidence for a raw-CMYK/separation model.

## 4. Model and correction algorithm

Let `s = [R, G, B]` be the RGB value placed in a patch of the JPEG. Let the qbox result be:

```text
m(s) = [observed_colour, saturation, hue, gutter, bleed, opacity, uniformity]
```

### Forward model

Fit a regularised RGB response model from physical patch data:

```text
m_hat(s) = B × [1, R, G, B, R², G², B², R×G, R×B, G×B]
```

A coarse 3D lookup table stores measured RGB → qbox colour/risk observations. The regularised response surface fills gaps between measured samples without inventing large changes outside the sampled region. Repeated controls estimate measurement variation.

This is practical for the current 224-patch chart and is much faster than an exhaustive RGB cube.

### Inverse candidate

For each desired target colour `t`, select the next JPEG source RGB value by solving:

```text
s_next = argmin over s:
  colour_distance(colour_hat(s), t)
  + w_sat × saturation_error_hat(s)
  + w_hue × hue_error_hat(s)
  + w_gutter × gutter_hat(s)
  + w_uniformity × uniformity_hat(s)
```

subject to:

```text
0 ≤ R,G,B ≤ 255
small local step from the measured input colour
no predicted regression in bleed, opacity, or uniformity
no candidate outside measured/supportable RGB space
```

The first version uses deterministic local RGB candidates rather than an expensive global search. It is fast, inspectable, and fail-closed.

### Dark/black behaviour

We do **not** assume that “reduce black” is automatically the right correction. In the Windows RGB route we cannot independently lower the printer’s K channel. Instead, the measured model will reveal whether a dark target is too dark, too light, too warm/cool, or bleeding. It may choose a lighter RGB source or a small hue/chroma adjustment only when that reduces the measured error **without worsening bleed or uniformity**.

## 5. Iteration and release procedure

1. Build a hash-pinned 160 × 160 mm JPEG chart with colour patches, white gutters, and four fiducials.
2. Audit every patch RGB interior, all non-patch pixels, ICC, JPEG parameters, A4 size and hash.
3. Print once using the frozen Windows queue and settings.
4. Place the sheet in qbox10; capture with the locked camera/lighting setup.
5. Register, measure, and publish the per-patch report.
6. Fit the RGB forward/risk model from the new and prior captures.
7. Produce an **offline candidate JPEG and report only**.
8. Authorise the next physical chart only if held-out patches show predicted improvement with no protected quality regression.

Every run preserves the JPEG, print configuration, capture files, registration overlay, report, fitted model, candidate, hashes, and explicit decision.

## 6. Research basis

The approach combines standard printer-characterisation ideas with an empirical feedback loop:

- Iterative printer characterisation: *An Iterative Cellular YNSN Method for Color Printer Characterization* (1998), DOI [`10.2352/cic.1998.6.1.art00042`](https://doi.org/10.2352/cic.1998.6.1.art00042).
- Six-colour characterisation background for the later ET-8550 work: Chen, Berns and Taplin (2004), DOI [`10.2352/j.imagingsci.technol.2004.48.6.art00009`](https://doi.org/10.2352/j.imagingsci.technol.2004.48.6.art00009).
- Spatial non-uniformity as a separately corrected printer-calibration dimension: DOI [`10.1117/12.767275`](https://doi.org/10.1117/12.767275).

## 7. Future ET-8550 scope — not active now

The future six-reservoir printer normally expects physical `BK, C, M, Y, GY, PB` reservoirs. A later, separate project may replace two reservoirs with UV cyan and UV yellow. The exact reservoir-to-UV mapping, flushing process, compatibility, raw-channel transport and UV measurement model are deliberately **out of scope** for this four-channel RGB/JPEG calibration loop.

The reusable parts that will transfer later are the chart audit, qbox registration, paper normalisation, per-patch quality metrics, feedback model, held-out validation, and immutable run records. The numerical RGB or ink coefficients will not transfer.
