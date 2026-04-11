# ASSUMPTIONS.md

All modeling, data, and spatial assumptions for this project.
Format: assumption → why it's reasonable → how it could fail → sensitivity test plan.

---

## Template

### ASS-000 — Title
- **Assumption:**
- **Why reasonable:**
- **How it could fail:**
- **Sensitivity / test plan:**

---

## Assumptions

### ASS-001 — CDL label accuracy is sufficient for Corn Belt pixels
- **Assumption:**
- **Why reasonable:**
- **How it could fail:**
- **Sensitivity / test plan:**

### ASS-002 — 250 m NDVI purity threshold (≥ 0.80 crop fraction) removes mixed-pixel bias
- **Assumption:**
- **Why reasonable:** Established in trusted-pixel / pure-pixel literature for MODIS VI crop mapping
- **How it could fail:**
- **Sensitivity / test plan:**

### ASS-003 — SMAP L4 gridded soil moisture adequately represents field-level moisture for anomaly detection
- **Assumption:**
- **Why reasonable:** SMAP L4 is a model-assimilation product; anomaly signals at 9 km are still meaningful for regional drought/flood characterization
- **How it could fail:**
- **Sensitivity / test plan:**

### ASS-004 — Temporal holdout (train 2013–2022, validate 2023) is a leakage-free split
- **Assumption:**
- **Why reasonable:**
- **How it could fail:**
- **Sensitivity / test plan:**

### ASS-005 — Crop rotation patterns are spatially stationary within the study area
- **Assumption:**
- **Why reasonable:**
- **How it could fail:**
- **Sensitivity / test plan:**

### ASS-006 — ERA5 / external climate reanalysis is consistent with SMAP L4 forcing
- **Assumption:**
- **Why reasonable:**
- **How it could fail:**
- **Sensitivity / test plan:**
