# Afla_books printer-calibration handoff for Fable

**Date:** 2026-07-16  
**Status:** Current, four-channel normal-colour calibration only. This is a handoff record, not permission to print.

## 1. The actual goal

Brandon’s immediate goal is to make the **currently available Epson ET-2856** produce regular, accurate colour prints through an iterative physical loop:

```text
known colour chart image
→ print on the ET-2856
→ put sheet in qbox10
→ measure what was actually printed
→ compare expected vs observed colour and print quality
→ adjust the next chart image
→ repeat until it is acceptably accurate and clean
```

The current printer has only four ordinary ink channels:

```text
Cyan, Magenta, Yellow, Black/K
```

The important outcome is a **fast, repeatable image-to-physical-print calibration process**. It must measure and improve:

- visible colour accuracy;
- saturation and hue accuracy;
- dark/black behaviour;
- gutter contamination and bleed;
- opacity/density;
- interior uniformity/mottle.

The next chart’s active target must be a centred **160 × 160 mm** square on A4 so that qbox10 always has safe margins around the fiducials and printed target.

### What is explicitly *not* active now

Do **not** work on a six-channel or UV model now.

A future ET-8550 normally expects physical reservoirs `BK, C, M, Y, GY, PB`. Brandon may later convert two reservoirs to **UV cyan and UV yellow**, but the reservoir mapping, ink compatibility, flushing, UV modelling and raw transport are separate future work. Do not assume that `GY` or `PB` currently means a UV ink.

## 2. Correct current control strategy

For the present printer, use a normal **sRGB image input** and a frozen, known Windows printer route. The Windows driver chooses its internal CMYK/K separation and dot pattern.

That means:

- we **do** control where and how strongly the printer is asked to print by setting the RGB value of every chart cell or image region;
- we **do not** claim direct physical control of independent C/M/Y/K droplet coverage through the current route;
- we learn the end-to-end mapping:

```text
source RGB in the submitted image
→ Windows driver / Epson print behaviour / paper
→ qbox10 measured colour and print-quality metrics
```

This is exactly sufficient for the present aim: compare many intended colours to many printed colours, update the RGB source values, print again, and repeat.

## 3. Raw is not the current path

**Do not use raw LPR/TIFF/PNG/PDF passthrough.** It was tested and failed: the ET-2856 produced blank pages and literal garbage characters because TIFF bytes were sent to a queue expecting printer-language data.

The present safe route is the **Windows-rendered Epson queue**, not a raw print stream.

| Item | Last verified information |
|---|---|
| Windows printer host | `smallboi` (Windows), Tailscale IP `100.119.2.59` at the last check |
| Windows account | `smallboi\brand` / SSH username `brand` |
| Printer LAN address | `192.168.0.136` |
| Windows queue | `EPSONAACAF2 (ET-2850 Series)` |
| Driver | `Microsoft IPP Class Driver` |
| Port | WSD/IPPS (not raw LPR) |
| Last safe output | one-page Windows spooler smoke test, then an sRGB-tagged PNG validation chart |
| LPR port 515 | reachable from `smallboi`, but **not a valid route for raw TIFF bytes** |

### JPEG decision

Brandon explicitly wants the next chart delivered as a normal compressed JPEG rather than raw data. That is reasonable for large, uniform colour patches and is faster/smaller.

The JPEG route is **requested but not yet physically smoke-tested**. Its first use must be controlled:

- RGB JPEG, embedded sRGB profile;
- high quality (at least 95) and 4:4:4/no chroma subsampling;
- fixed A4 raster dimensions and 720-DPI metadata;
- no Windows fit-to-page, crop, auto-enhance or rescale;
- hash the submitted JPEG and record Windows queue/driver settings;
- decode the generated JPEG and audit a central interior sample of every patch before printing;
- make a single small print only after the above audit.

The prior safe output was **PNG**, not JPEG. Do not falsely report that JPEG printing has already been validated.

## 4. Access from devbox

All Aflabox work belongs on **devbox**, not Hermes local scratch storage.

```bash
# From the Hermes environment, use the host-network helper:
/opt/data/remote-dev-ssh.sh devbox 'hostname; whoami; pwd'

# On devbox, repository and captures:
REPO=/home/brandonc/repos/afla_repo/gutenprint-et8550
CAPTURES=/home/brandonc/captures/qbox10
```

The active GitHub repository and review branch are:

```text
repo:   qboxx/gutenprint-et8550
branch: aflabox-et2856-proof
PR:     https://github.com/qboxx/gutenprint-et8550/pull/1
```

### Current smallboi access state — re-verify before use

At the latest read-only test, `smallboi` was online on Tailscale at `100.119.2.59`, but this connection from devbox failed:

```bash
ssh -4 -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes \
  brand@100.119.2.59 'hostname; whoami'
# Result: Permission denied (publickey,password,keyboard-interactive)
```

A direct host-network attempt timed out. Therefore **do not assume remote Windows access currently works**. Before any printing work, Brandon/Fable must either:

1. use the SSH identity that is already authorised on `smallboi`; or
2. add the current devbox public key to `C:\Users\brand\.ssh\authorized_keys` (and, if needed for administrative access, `C:\ProgramData\ssh\administrators_authorized_keys`), restart OpenSSH, then verify the connection; or
3. use an interactive local Windows session on smallboi.

Use only a read-only queue check first:

```powershell
Get-Printer -Name 'EPSONAACAF2 (ET-2850 Series)' |
  Select-Object Name,DriverName,PortName,PrinterStatus | Format-List
```

Do not change drivers, ports, colour-management settings, ink settings or queue defaults while building the model. Those settings are part of the calibrated black box and must stay fixed for a run.

## 5. qbox10 access and locked capture conditions

qbox10 is accessed through the Aflabox Headscale/cluster route from devbox. Its current Headscale address is:

```text
qbox10: 100.64.0.3
```

**Every remote qbox command must first check:**

```bash
[ "$(hostname)" = qbox10 ] || exit 9
```

Existing devbox reference scripts (temporary paths; inspect before reusing) are:

```text
/tmp/qbox10_capture_validation.sh
/tmp/qbox10_download_validation_capture.sh
```

They retrieve an ephemeral authorised key through the existing Aflabox cluster, tunnel via the Headscale SSH gateway, and refuse to proceed if the target hostname is not `qbox10`. Do not copy keys or credentials into Git or documentation.

### Locked camera conditions used for the usable validation recapture

```text
illumination: White (GPIO 18 on; other capture LEDs off)
exposure:     8 ms / 8000 µs
gain:         1.0
lens:         manual position 8.75
capture:      4624 × 3472, JPEG + RAW/DNG
```

The reference capture command used `rpicam-still --raw --nopreview` with those settings. The capture script additionally requires `aflabox.service` to be inactive before taking control of the camera/LEDs and turns LEDs off on exit. Preserve those protections.

The DNG file is the quantitative source. JPEG is a convenience/visual derivative only.

## 6. Physical evidence already available

The latest useful physical sheet is the independently printed Windows-rendered validation chart. Important paths on devbox:

```text
# Source chart/manifest
/home/brandonc/captures/qbox10/iteration-03/independent-validation-master/
  qbox10-independent-validation.manifest.json
  qbox10-independent-validation-a4-720dpi.tiff
  qbox10-independent-validation-preview.png

# Image actually submitted through the Windows-rendered route
/home/brandonc/captures/qbox10/iteration-03/independent-validation-windows-rendered/
  qbox10-independent-validation-windows-srgb-720dpi.png

# Usable replacement qbox10 capture and analysis
/home/brandonc/captures/qbox10/iteration-03/recapture-20260716T145953Z/
  qbox10_validation_8000us.dng
  qbox10_validation_8000us.jpg
  analysis/validation-quality-report.json
```

### Why this capture is usable

- Three real fiducials were detected: top-left, top-right, bottom-right.
- The bottom-left was inferred as the valid parallelogram corner, per Brandon’s accepted rule.
- All **224/224** patch centres were inside the captured frame.
- The printed source PNG was audited against its manifest: all **224/224** patch-interior sample pixels exactly matched their declared `target_rgb` values.
- Local paper normalisation used **bounded inverse-distance interpolation** from paper controls. An earlier global affine field was rejected because it extrapolated implausibly.

The replacement is therefore a valid baseline for an **RGB image-input → qbox-output** model. It is *not* a reason to claim direct CMYK/ink separation knowledge.

### Baseline report summary

From `analysis/validation-quality-report.json`:

```text
patches:                         224
mean deltaE76:                   24.4648
mean saturation residual:        0.1686
mean hue error:                  18.5621 degrees
mean gutter contamination:       61.0753
95th percentile gutter:          120.9900
mean bleed fraction:             1.1612
mean interior luminance std.dev: 4.1709
```

These values show that the present result has substantial room for improvement. They do **not** by themselves prove that black/K alone is the cause. The next model must use per-patch evidence: some dark cells may need a lighter RGB input, but that must be decided by measured response and non-regression gates rather than guessing “reduce black.”

## 7. Metrics Fable should retain

For each patch, retain the declared input RGB and measure/report:

```text
input_rgb                         exact colour represented by submitted image
observed_normalised_rgb           qbox output after paper normalisation
colour difference                 target/input versus observed in a defined colour space
saturation residual               chroma mismatch
hue error                         ignore/flag near-neutral hue values
absolute gutter contamination     visible ink in nominally blank gutter
relative bleed                    gutter relative to interior contrast
opacity/density proxy             interior contrast relative to local paper
interior luminance standard dev.  mottle/streak/uniformity
repeat controls                   measurement/print variation across sheet
```

Never collapse these into one optimistic score. A colour change is not accepted if it improves colour but worsens gutter bleed, opacity or uniformity.

## 8. Recommended fast algorithm direction

Use an empirical image-domain calibration, not a giant exhaustive search and not a raw CMYK model.

1. Use the 224 known RGB inputs and corresponding qbox measurements as initial training data.
2. Build a bounded local **RGB input → observed colour plus risk** lookup/interpolation model.
3. For every desired target RGB, search only a small local neighbourhood around the previous source RGB (for example ± one or two modest RGB steps), not a full global cube.
4. Select a revised RGB only if it is predicted to reduce colour/saturation/hue error and not regress gutter, bleed, opacity or uniformity.
5. Include repeated controls and held-out patches. The next physical print decides whether the candidate actually improved.
6. If the model is poorly supported or fails held-out error checks, keep the old source colour rather than inventing a large correction.

A simple expression for each candidate is:

```text
next_source_RGB = argmin(local RGB candidates)
  colour_error_predicted
  + saturation/hue penalties
  + gutter/bleed/uniformity penalties

subject to:
  small trust region around prior source RGB
  no predicted protected-metric regression
  enough nearby physical observations
```

This is deliberately iterative: it does not need to be perfect in one step. The correct output is a safe next JPEG chart plus a transparent report, then another qbox10 measurement.

Useful research directions already identified:

- Iterative cellular printer characterisation: DOI `10.2352/cic.1998.6.1.art00042`.
- Printer lookup-table modelling: DOI `10.1117/12.910357`.
- Spatial non-uniformity correction in printer calibration: DOI `10.1117/12.767275`.

These inform the design; qbox10 physical measurements are the authority for this printer/paper/driver combination.

## 9. Required next workflow

1. **Recover/verify safe smallboi access**, but do not print yet.
2. Inspect/freeze the Windows Epson queue settings and record them in the run manifest.
3. Build a 160 × 160 mm A4 sRGB JPEG chart with 224 or similar deliberately distributed RGB patches, white gutters and four fiducials.
4. Audit the encoded JPEG interior samples, page size, ICC, JPEG parameters and SHA-256.
5. Make one Windows-rendered JPEG smoke/validation print; never raw-LPR it.
6. Brandon places it in qbox10.
7. Capture with the locked White/8-ms/gain-1.0/lens-8.75 setup.
8. Analyse it, fit/validate the bounded local RGB feedback model, and release the next chart only with a clear evidence report.

## 10. Repository state and warnings

Current reviewed documentation on the open calibration PR:

```text
docs/AFLABOOKS-FOUR-CHANNEL-RGB-JPEG-CALIBRATION-PRD.md
docs/AFLABOOKS-SIX-CHANNEL-CALIBRATION-PRD.md
docs/plans/2026-07-16-aflabooks-rgb-jpeg-feedback-loop.md
```

The six-channel document is explicitly a future extension only. The four-channel RGB/JPEG PRD is the active scope.

There are currently **uncommitted, incomplete scratch files** in the devbox worktree:

```text
tools/et8550/printer_calibration/rgb_feedback.py
tools/et8550/printer_calibration/tests/test_rgb_feedback.py
```

They were started but are not complete, reviewed, committed or pushed. They must be deleted/ignored before Fable begins rather than being treated as a working implementation.

Also, the existing PR contains historical raw-CMYK chart work. It is not the current printing route and must not be used to send raw files to LPR.

## 11. Hard safety/reproducibility rules

- Never raw-send TIFF/JPEG/PDF bytes to LPR.
- Never print without a hash-pinned, audited source artifact and explicit run record.
- Never change the Windows driver/queue settings in the middle of a calibration run.
- Never claim a model is accurate without a physical qbox10 recapture.
- Never authorise a candidate because a global/offline optimizer says it looks good; require held-out and protected-metric gates.
- Always verify `hostname == qbox10` before camera or LED control.
- Do not use a clipped-fiducial capture for quantitative results; three corners plus an inferred fourth is allowed only with geometric plausibility and all patch centres in frame.
- Keep secret keys, cluster credentials, passwords and raw access tokens out of Git, logs and handoff documents.
