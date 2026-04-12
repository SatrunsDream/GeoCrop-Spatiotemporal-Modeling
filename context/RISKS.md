# RISKS.md

Known risks, failure modes, and mitigations for the GeoCrop NAFSI Track 1 pipeline.

---

## Risk Register

### RISK-001 — CDL→NDVI scale mismatch (support mismatch)
- **Risk:** Sampling 30 m CDL labels at 250 m NDVI creates mixed-pixel bias, widening uncertainty bands and blurring phenological differences between corn and soybean.
- **Severity:** High
- **Mitigation:** Apply purity filtering — use only 250 m NDVI cells where the dominant crop fraction ≥ 0.80 (see `configs/task1_ndvi_analysis.yaml`).

### RISK-002 — SMAP baseline record is short (2015–present)
- **Risk:** A short record makes σ estimates unstable; z-score anomalies may be unreliable for extreme events.
- **Severity:** Medium
- **Mitigation:** Use percentile-rank anomalies alongside z-scores; acknowledge limitation in report.

### RISK-003 — Spatial autocorrelation causes leakage in Task 4 validation
- **Risk:** Random train/test splits produce overly optimistic metrics because nearby pixels share spatial context.
- **Severity:** High
- **Mitigation:** Use temporal holdout (train 2013–2022, test 2023) as primary validation; optionally add spatial block CV.

### RISK-004 — CDL label noise degrades rotation and prediction tasks
- **Risk:** CDL accuracy varies by class and geography; noisy labels introduce false rotation signals and degrade classifier training.
- **Severity:** Medium
- **Mitigation:** Use robust rotation metrics (transition frequency, edit distance) that tolerate occasional "break years"; consider confidence-weighted training in Task 4.

### RISK-005 — Data access / download failures from CropSmart or USDA portals
- **Risk:** Portal downtime or API changes could block data ingestion.
- **Severity:** Medium
- **Mitigation:** Cache raw downloads to `data/raw/` immediately; document direct download URLs in `context/DATASETS.md`.

### RISK-006 — Computational cost for full-CONUS Task 4 feature matrix
- **Risk:** Building a pixel-level feature matrix across CONUS for 10 years of CDL may exceed memory or runtime constraints in a notebook environment.
- **Severity:** Medium
- **Mitigation:** Tile or spatially sample during development; use full extent only for final prediction run via `scripts/run_task4_crop_mapping.py`.

### RISK-007 — Projection inconsistency across datasets
- **Risk:** Mixing CDL (Albers), NDVI (may be geographic or sinusoidal), and SMAP (EASE-Grid 2.0) projections leads to incorrect spatial overlays.
- **Severity:** High
- **Mitigation:** All data reprojected to EPSG:5070 at load time via `src/io/` loaders; centralized in `src/utils/geo_utils.py`.

### RISK-008 — Task 2 study footprint vs Corn Belt narrative
- **Risk:** The processed CDL stack’s geographic extent may cover only part of the **13-state** Corn Belt; **map callouts** or narrative that imply a specific subregion (e.g. only Iowa vs Nebraska) can **misread** the footprint.
- **Severity:** Medium (communication / reviewer trust)
- **Mitigation:** Report **bbox** from metadata; Notebook **05** assigns regions via **state polygons** (`load_cornbelt_state_boundaries_5070`, YAML state list), not a longitude proxy; tie claims to **actual** footprint (`context/TASK2_RESULTS.md`).
