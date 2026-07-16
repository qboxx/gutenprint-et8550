# Afla_books RGB/JPEG print-to-qbox feedback loop — Implementation Plan

> **For Hermes:** Execute task-by-task using TDD. The active goal is four-channel normal-colour calibration through the existing Windows JPEG print route; do not add raw-CMYK or UV behaviour to this implementation.

**Goal:** Build a fast, reproducible RGB input → qbox10 output feedback model and a 160 × 160 mm sRGB JPEG chart builder that can create a safe next candidate from physical measurements.

**Architecture:** Treat the current Windows IPP printer route as a fixed black box. Model declared JPEG patch RGB values to qbox-normalised RGB plus print-quality risks using regularised polynomial features. Choose only small local RGB corrections that improve predicted colour while not worsening bleed or interior texture, then render a hash-pinned JPEG chart and manifest. The physical qbox report remains the authority.

**Tech stack:** Python 3.10+, NumPy, Pillow, unittest; existing qbox registration/measurement report as input.

---

### Task 1: Correct durable scope records

**Files:**
- Create: `docs/AFLABOOKS-FOUR-CHANNEL-RGB-JPEG-CALIBRATION-PRD.md`
- Modify: `docs/AFLABOOKS-SIX-CHANNEL-CALIBRATION-PRD.md`

**Objective:** Make the four-channel RGB/JPEG loop the active record and classify six-channel/UV work as a later extension.

**Verification:**

```bash
git diff --check
git diff -- docs/AFLABOOKS-FOUR-CHANNEL-RGB-JPEG-CALIBRATION-PRD.md docs/AFLABOOKS-SIX-CHANNEL-CALIBRATION-PRD.md
```

### Task 2: Implement an auditable RGB forward/risk model

**Files:**
- Create: `tools/et8550/printer_calibration/rgb_feedback.py`
- Create: `tools/et8550/printer_calibration/tests/test_rgb_feedback.py`

**Objective:** Load a qbox per-patch quality report whose `target_rgb` is verified to be the printed JPEG patch input; fit RGB → observed colour/risk prediction with deterministic regularised polynomial features.

**Step 1 — RED:** Write failing tests for:

```python
def test_polynomial_features_preserve_rgb_interactions(): ...
def test_fit_predicts_a_known_affine_rgb_response(): ...
def test_report_loader_rejects_missing_or_nonfinite_measurements(): ...
```

Run:

```bash
python3 -m unittest tools/et8550/printer_calibration/tests/test_rgb_feedback.py -v
```

Expected: import failure because `rgb_feedback` does not exist.

**Step 2 — GREEN:** Implement only:

```python
polynomial_rgb_features(rgb)
RegularizedRGBFeedback.fit(...)
RegularizedRGBFeedback.predict(...)
load_feedback_samples(report)
```

The model must use `target_rgb`/verified rendered input as the source RGB, `observed_normalised_rgb` as measured colour, and report gutter/bleed/interior-variance as separate risks. It must not interpret source RGB as direct physical CMYK.

**Step 3 — GREEN verification:** Run the focused tests, then the full calibration suite.

### Task 3: Implement conservative candidate selection

**Files:**
- Modify: `tools/et8550/printer_calibration/rgb_feedback.py`
- Modify: `tools/et8550/printer_calibration/tests/test_rgb_feedback.py`

**Objective:** Choose fast local RGB corrections without an exhaustive global search.

**Step 1 — RED:** Add failing tests proving that selection:

```python
def test_candidate_increases_source_brightness_when_measured_model_is_too_dark(): ...
def test_candidate_reverts_when_bleed_would_regress(): ...
def test_candidate_never_leaves_the_local_rgb_trust_region(): ...
```

**Step 2 — GREEN:** Implement `choose_safe_rgb_candidate(...)` with deterministic candidates around the current RGB value. A candidate is selected only when predicted colour improves by the required margin and predicted gutter/bleed/uniformity do not regress. Otherwise return the current RGB value and record a rejection reason.

**Step 3 — Verification:** Run focused and full tests. Apply the model to the existing 224-patch qbox10 Windows-rendered report, producing an offline JSON candidate report only; never spool or print.

### Task 4: Build and audit the 160 × 160 mm JPEG chart

**Files:**
- Create: `tools/et8550/printer_calibration/render_rgb_jpeg_chart.py`
- Create: `tools/et8550/printer_calibration/tests/test_render_rgb_jpeg_chart.py`

**Objective:** Build a centred A4 RGB JPEG with a 14×16 patch grid, gutters, fiducials, sRGB ICC, 720-DPI metadata, deterministic quality/subsampling, source audit and SHA-256 manifest.

**Step 1 — RED:** Add failing tests proving that the chart:

```python
def test_jpeg_chart_is_a4_720dpi_and_has_embedded_srgb(): ...
def test_active_target_is_centered_160_by_160_mm(): ...
def test_every_patch_central_interior_decodes_to_declared_rgb_within_tolerance(): ...
def test_nonpatch_sample_regions_remain_white_and_fiducials_are_present(): ...
```

**Step 2 — GREEN:** Implement the smallest renderer/auditor that passes. JPEG audit uses a declared central sample region and bounded tolerance; it must never falsely claim byte-for-byte preservation of a lossy format.

**Step 3 — Verification:** Build a non-printing chart from the offline candidate report, inspect the manifest/hash/preview and run all tests.

### Task 5: Review and publish

**Files:** all above.

1. Run all calibration tests and `git diff --check`.
2. Run a static scan for accidental secrets, shell execution, or unsafe paths.
3. Obtain an independent spec-compliance review, then a code-quality review.
4. Commit and push only the reviewed documentation and code to the existing calibration PR. Do not merge and do not print.
