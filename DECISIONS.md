# DECISIONS.md

Records every meaningful design or methodological choice made in this project.
Format: decision → alternatives considered → rationale → consequences → date.

If this file conflicts with `development_rules.md`, `development_rules.md` wins.

---

## Template

### DEC-000 — Title
- **Decision:**
- **Alternatives considered:**
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**
- **Run ID (if applicable):**

---

## Decisions

### DEC-001 — Spatial alignment strategy for CDL → NDVI (Task 1)
- **Decision:**
- **Alternatives considered:**
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-002 — NDVI smoothing method choice (Task 1)
- **Decision:**
- **Alternatives considered:** Savitzky–Golay, TIMESAT double-logistic, Whittaker, harmonic regression
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-003 — Rotation regularity criterion definition (Task 2)
- **Decision:**
- **Alternatives considered:** Edit-distance (RECRUIT-style), transition frequency, run-length penalty, entropy
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-004 — SMAP anomaly baseline method (Task 3)
- **Decision:**
- **Alternatives considered:** DOY climatology (z-score), week-of-year percentile rank
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-005 — Crop-type prediction model family (Task 4)
- **Decision:**
- **Alternatives considered:** Markov baseline, Random Forest, LightGBM/XGBoost, deep SITS (CNN/RNN/Transformer)
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-006 — Validation strategy for Task 4
- **Decision:**
- **Alternatives considered:** Random CV, temporal holdout, spatial block CV
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-007 — Task 4 rolling panel (not single-label-per-pixel)
- **Decision:** Train on a **panel** of rows `(iy, ix, year)` for years 2013–2022: features = CDL history **before** `year` plus same-year NDVI/SMAP (crop-mapping signal, not forecasting). Labels = CDL at `year` mapped to {0=other cropland, 1=corn, 2=soy, 3=wheat}. Temporal split: train `year<=2021`, val `2022`, test frame `2023`.
- **Alternatives considered:** One row per pixel with label=test year only (~3M rows); random spatial CV.
- **Rationale:** Matches agronomic interpretation (phenology/soil in year *t* explain crop in year *t*); multiplies effective training size; strict year-based split reduces temporal leakage.
- **Consequences / follow-ups:** Report spatial autocorrelation caveat; ~6M training rows — use `float32`, year-at-a-time assembly; winter wheat CDL code **24** (not 26) per AOI diagnostics.
- **Date:** 2026-04-11
