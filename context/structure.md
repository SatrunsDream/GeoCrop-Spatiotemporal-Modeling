# structure.md

Single source of truth for:
1. Repository structure (what each file/folder is for)
2. Results and artifacts produced by each notebook
3. References to exported figures and datasets
4. Key findings and what they mean

All referenced paths are relative to repo root.

---

## PROJECT MAP

### Root-level files

| File | Purpose |
|------|---------|
| `README.md` | Entry point: setup instructions, repo overview |
| `development_rules.md` | Operational contract for structure + workflow |
| `structure.md` | This file — single source of truth |
| `DECISIONS.md` | Design choices and rationale |
| `ASSUMPTIONS.md` | Modeling and data assumptions |
| `CHANGELOG.md` | Milestone log |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Ignored files (raw data, caches, secrets) |

### configs/

Task-specific YAML configuration files. All hyperparameters, thresholds, and paths are
defined here — no magic numbers in notebooks or scripts.

| File | Purpose |
|------|---------|
| `task1_ndvi_analysis.yaml` | CDL year, study area bounds, purity threshold, smoothing params |
| `task2_crop_rotation.yaml` | CDL year range, rotation metrics, classification thresholds |
| `task3_soil_moisture.yaml` | SMAP baseline period, event window, anomaly method |
| `task4_crop_mapping.yaml` | Feature set, model family, train/val split, CV strategy |

### context/

Long-running memory for humans and agents.

| File | Purpose |
|------|---------|
| `PROJECT_BRIEF.md` | Goals, success criteria, constraints |
| `GLOSSARY.md` | Domain terms, acronyms, CDL class codes |
| `DATASETS.md` | Data sources, schemas, licensing, download paths |
| `INTERFACES.md` | I/O contracts, expected array shapes, file formats |
| `STATUS.md` | Current state, completed work, blockers |
| `RISKS.md` | Known failure modes and mitigations |
| `TASK2_RESULTS.md` | Task 2 rotation outputs: numbers, interpretation, improvement ideas |

### data/

| Tier | Path | Contents |
|------|------|---------|
| Raw | `data/raw/cdl/` | CDL GeoTIFFs per year (`cdl_{year}_iowa_nebraska_5070.tif`) — typically gitignored |
| Raw | `data/raw/ndvi/` | NDVI GeoTIFFs per week (`NDVI-WEEKLY_{year}_…`) — typically gitignored |
| Raw | `data/raw/smap/` | SMAP GeoTIFFs per week (`SMAP-WEEKLY_{year}_…`) — typically gitignored |
| Interim | `data/interim/cdl/` | `cdl_stack_{y0}_{y1}.nc` — multi-year NetCDF stack |
| Interim | `data/interim/ndvi/` | `ndvi_weekly_{year}.nc` — per-year growing-season stack |
| Interim | `data/interim/smap/` | `smap_weekly_{year}.nc` — per-year weekly stack |
| Processed | `data/processed/cdl/` | `cdl_stack_wide.parquet` + `cdl_stack_spatial_metadata.json` |
| Processed | `data/processed/ndvi/` | `ndvi_weekly_{year}_wide.parquet` + `ndvi_weekly_{year}_metadata.json` |
| Processed | `data/processed/smap/` | `smap_weekly_{year}_wide.parquet` + `smap_weekly_{year}_metadata.json` |
| External | `data/external/` | Saved GetCapabilities / WMS map metadata; optional legends, boundaries |

### notebooks/

Each task has its own subfolder. Notebooks run top-to-bottom in numbered order.

```
notebooks/
├── task1_ndvi_timeseries/     Task 1 — NDVI phenology corn vs. soybean
├── task2_crop_rotation/       Task 2 — Rotation pattern identification
├── task3_soil_moisture/       Task 3 — SMAP anomaly detection
└── task4_crop_mapping/        Task 4 — Crop-type prediction model
```

### src/

Reusable Python package. All heavy logic lives here; notebooks import from `src`.

```
src/
├── io/             Data loaders (CDL, NDVI, SMAP)
├── preprocessing/  Spatial alignment, purity filtering, smoothing, feature engineering
├── modeling/       Model definitions, rotation classifier, phenology fitting
├── evaluation/     Metrics: classification, phenology, anomaly, spatial validation
├── viz/            Plotting helpers for phenology curves, maps, anomaly layers
└── utils/          Paths, seeds, logging, geo helpers; `nafsi_catalog.py` (CDL/NDVI/SMAP year lists, brief §3)
```

### scripts/

CLI entry-points. Accept `--config` argument pointing to a YAML in `configs/`.

| Script | Purpose |
|--------|---------|
| `run_task1_ndvi.py` | End-to-end Task 1 pipeline |
| `run_task2_rotation.py` | End-to-end Task 2 pipeline |
| `run_task3_smap.py` | End-to-end Task 3 pipeline |
| `run_task4_crop_mapping.py` | End-to-end Task 4 pipeline |
| `download_data.py` | WMS download → `data/raw/{cdl,ndvi,smap}/` |
| `build_interim_data.py` | Raw GeoTIFF → NetCDF in `data/interim/{cdl,ndvi,smap}/` |
| `process_interim_to_parquet.py` | Interim NetCDF → wide Parquet under `data/processed/…` |
| `build_report.py` | Assembles artifacts into a report draft |

### tests/

| File | Purpose |
|------|---------|
| `test_cdl_loader.py` | Unit tests for CDL data loading |
| `test_spatial_alignment.py` | Unit tests for CDL→NDVI alignment |
| `test_rotation_metrics.py` | Unit tests for rotation regularity scoring |
| `test_classification_metrics.py` | Unit tests for eval metrics (F1, OA, confusion matrix) |
| `smoke_test.py` | Tiny end-to-end subset run for all four tasks |

### artifacts/

All generated outputs. Never hand-edited.

```
artifacts/
├── figures/          Exported plots (PNG, dpi=200–300)
├── tables/           Exported summary tables (CSV or HTML)
├── models/           Serialized trained models
├── reports/          Auto-generated markdown/HTML/PDF reports
└── logs/
    ├── runs/         Per-run metadata bundles (meta.json, config.yaml, metrics.json, …)
    ├── prompts/      LLM prompt + response snapshots (selective)
    └── provenance/   Input/output manifests and hashes
```

---

## ARTIFACT INDEX

*(Populated as artifacts are produced)*

### Figures

| Path | Description |
|------|-------------|
| `artifacts/figures/task2/task2__cornsoy_fractions_by_year__20260411.png` | CDL corn vs soy fraction by year (processed stack) |
| `artifacts/figures/task2/task2__ncornsoy_histogram.png` | Ever-pool `n_cornsoy_years` with eligibility cutoff |
| `artifacts/figures/task2/task2__markov_corn_soy_other.png` | Markov P(to|from) heatmap (corn/soy/other) |
| `artifacts/figures/task2/task2__metric_histograms.png` | Task 2 rotation metric distributions (eligible pixels) |
| `artifacts/figures/task2/task2__alt_vs_distance.png` | Alternation vs pattern-distance scatter |
| `artifacts/figures/task2/task2__threshold_sensitivity_regular_pct.png` | Sensitivity: % regular vs `alternation_min` by `dist_max` |
| `artifacts/figures/task2/task2__transition_asymmetry.png` | Four-bar P(C→C), P(C→S), P(S→C), P(S→S) (Markov) |
| `artifacts/figures/task2/task2__runlength_distribution.png` | Discrete max run length (monoculture zone ≥7) |
| `artifacts/figures/task2/task2__rotation_map__raw__20260411.png` | Rotation class map (raw) |
| `artifacts/figures/task2/task2__rotation_map__smoothed__20260411.png` | Rotation class map (3×3 smoothed + annotations) |
| `artifacts/figures/task2/task2__rotation_map__core_belt__*.png` | IA/IL/IN/NE zoom (notebook 04 `focus_state_names`) |
| `artifacts/figures/task2/task2__rotation_dm_p_regular__*.png` | Posterior **P(regular)** map (Dirichlet–Multinomial; notebook 04) |
| `artifacts/figures/task2/task2__rotation_dm_alt_posterior_std__*.png` | Posterior std of alternation proxy (notebook 04) |
| `artifacts/figures/task2/task2__rotation_class_by_county__*.png` | County choropleth of % regular — 13-state Belt (Notebook 04 + TIGER) |
| `artifacts/figures/task2/task2__rotation_class_by_county_core4__*.png` | County choropleth — IL / IN / IA / NE only (Notebook 04) |

### Tables

| Path | Description |
|------|-------------|
| `artifacts/tables/task2/task2__markov_transition_{counts,probs}.csv` | Markov transition tables (NB02) |
| `artifacts/tables/task4/task2__areal_stats_by_class__*.csv` | Areal summary by rotation class (grid ha); Task 2 notebook 04 |
| `artifacts/tables/task4/task2__areal_stats_by_class__*__metadata.json` | `pixel_area_ha`, grid resolution, CRS, disclaimer vs 30 m CDL |
| `artifacts/tables/task4/task2__areal_stats_by_region__*.csv` | Class % by state (13-state join) |
| `artifacts/tables/task4/task2__areal_stats_by_county__*.csv` | Class % by county (TIGER join; smoothed label; 13-state) |
| `artifacts/tables/task4/task2__areal_stats_by_county_core4__*.csv` | Same; IL / IN / IA / NE counties only |
| `artifacts/tables/task2/task2__threshold_sensitivity_grid.csv` | Full `alternation_min` × `pattern_dist_max` class shares |

### Figures — Task 3

| Path | Description |
|------|-------------|
| `artifacts/figures/task3/task3__smap_week_histogram_subset_{2019,2022}.png` | SMAP sanity histograms on rotation-eligible pixels (NB01) |
| `artifacts/figures/task3/task3__midwest_flood_2019__anomaly_map_4panel__20260412.png` | Z-score raster maps at 4 spread ISO weeks (2019 flood) |
| `artifacts/figures/task3/task3__midwest_flood_2019__anomaly_timeseries_cropland__20260412.png` | Belt-wide mean z ± 1σ time series (2019 flood) |
| `artifacts/figures/task3/task3__midwest_flood_2019__duration_fraction__20260412.png` | Persistence map: fraction of weeks with z > 1.5 (2019 flood) |
| `artifacts/figures/task3/task3__midwest_flood_2019__nig_p_drought_4panel__20260412.png` | NIG posterior P(drought) 4-panel (RdYlBu; 2019 flood) |
| `artifacts/figures/task3/task3__midwest_flood_2019__nig_uncertainty__20260412.png` | NIG posterior predictive scale / epistemic uncertainty (2019 flood) |
| `artifacts/figures/task3/task3__midwest_flood_2019__zscore_vs_nig_scatter__20260412.png` | Z-score vs −log₁₀(NIG p-value) scatter (2019 flood) |
| `artifacts/figures/task3/task3__plains_drought_2022__anomaly_map_4panel__20260412.png` | Z-score raster maps at 4 spread ISO weeks (2022 drought) |
| `artifacts/figures/task3/task3__plains_drought_2022__anomaly_timeseries_cropland__20260412.png` | Belt-wide mean z ± 1σ time series (2022 drought) |
| `artifacts/figures/task3/task3__plains_drought_2022__duration_fraction__20260412.png` | Persistence map: fraction of weeks with z < −1.5 (2022 drought) |
| `artifacts/figures/task3/task3__plains_drought_2022__nig_p_drought_4panel__20260412.png` | NIG posterior P(drought) 4-panel (RdYlBu; 2022 drought) |
| `artifacts/figures/task3/task3__plains_drought_2022__nig_uncertainty__20260412.png` | NIG posterior predictive scale / epistemic uncertainty (2022 drought) |
| `artifacts/figures/task3/task3__plains_drought_2022__zscore_vs_nig_scatter__20260412.png` | Z-score vs −log₁₀(NIG p-value) scatter (2022 drought) |

### Tables — Task 3

| Path | Description |
|------|-------------|
| `artifacts/tables/task3/task3__midwest_flood_2019__anomaly_stats_by_state_crop__20260412.csv` | State × crop anomaly summary with NIG columns (2019 flood) |
| `artifacts/tables/task3/task3__plains_drought_2022__anomaly_stats_by_state_crop__20260412.csv` | State × crop anomaly summary with NIG columns (2022 drought) |

### Models

| Path | Description |
|------|-------------|
| `artifacts/models/` | *(empty — to be populated)* |

---

## RESULTS LOG BY NOTEBOOK

### Task 1 — NDVI Time Series

#### notebooks/task1_ndvi_timeseries/01_data_ingestion_cdl_ndvi.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task1_ndvi_timeseries/02_purity_filtering_alignment.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task1_ndvi_timeseries/03_ndvi_smoothing_phenometrics.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task1_ndvi_timeseries/04_phenological_curve_visualization.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task1_ndvi_timeseries/05_task1_report_export.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

---

### Task 2 — Crop Rotation

#### notebooks/task2_crop_rotation/01_cdl_timeseries_loading.ipynb
- **Purpose:** Load **processed** CDL wide Parquet for 2015–2024; sanity-check grid and corn/soy prevalence by year.
- **Inputs:** `data/processed/cdl/cdl_stack_wide.parquet`, `cdl_stack_spatial_metadata.json`, `configs/task2_crop_rotation.yaml`
- **Outputs:** `artifacts/figures/task2/task2__cornsoy_fractions_by_year__*.png`
- **Key findings:** See `context/TASK2_RESULTS.md` §2–3. Corn/soy fractions vary by year; grid ~1520×2048, EPSG:5070, ~10.2 ha/cell.
- **Next steps:** Optional five-state vector mask; document study extent in report.

#### notebooks/task2_crop_rotation/02_rotation_metrics_computation.ipynb
- **Purpose:** Metrics on **ever** corn/soy stack; **eligibility** (≥5 corn/soy years); save **eligible-only** `rotation_metrics.parquet`; Markov 3×3; transition-volume printout; asymmetry bar chart; run-length discrete bars; metric plots; **Bayesian Dirichlet–Multinomial** columns `dm_p_regular`, `dm_alt_posterior_std`, `dm_n_trans_origin_corn_soy` (`src.modeling.rotation_bayesian_dm`, YAML `bayesian_dm`).
- **Inputs:** Same CDL Parquet slice; `src.modeling.rotation_classifier`
- **Outputs:** `rotation_metrics.parquet`; Markov CSVs under `artifacts/tables/task2/`; figures `task2__ncornsoy_histogram.png`, `task2__transition_asymmetry.png`, `task2__runlength_distribution.png`, metric plots
- **Key findings:** ~530k ever → **~301k eligible**; median alternation **0.5** on eligible pool; Markov shows sticky corn and soy→corn (`context/TASK2_RESULTS.md`).
- **Next steps:** Align grid with Iowa+Nebraska if regional narrative is required.

#### notebooks/task2_crop_rotation/03_rotation_classification.ipynb
- **Purpose:** **Threshold sensitivity grid** + **primary** YAML classification; GeoTIFFs; optional **DM float rasters** (`rotation_dm_p_regular.tif`, `rotation_dm_alt_posterior_std.tif`) when NB02 wrote `dm_*` columns.
- **Inputs:** `rotation_metrics.parquet`, YAML thresholds, spatial metadata JSON
- **Outputs:** `task2__threshold_sensitivity_grid.csv`, sensitivity figure, `rotation_class_map*.tif`, `rotation_metrics_classified.parquet`, DM GeoTIFFs (see above)
- **Key findings:** Strict primary **~16–17% regular**, **~27% mono**, **~55–57% irregular** on eligible pixels; relaxed (0.5, 5–6) reaches **~42–44% regular** (see sensitivity CSV).
- **Next steps:** Report = strict primary + sensitivity figure; cite USDA definitions when comparing.

#### notebooks/task2_crop_rotation/04_spatial_maps_and_areal_export.ipynb
- **Purpose:** **Merged** former NB04+NB05: publication-style **class** maps (raw + smoothed) + **core-belt zoom**; **Bayesian P(regular)** and **posterior std** maps from DM GeoTIFFs; **areal** CSV + metadata JSON + **per-state** shares + **per-county** (TIGER) choropleths; **`run_bundle.json`** (includes DM GeoTIFF paths).
- **Inputs:** Classified GeoTIFFs; DM float GeoTIFFs from NB03; `rotation_metrics_classified.parquet`; spatial metadata; `load_cornbelt_state_boundaries_5070`; `src.io.tiger_counties.load_cornbelt_counties_5070` (cached under `data/external/tiger/`)
- **Outputs:** `artifacts/figures/task2/task2__rotation_map__*__*.png`, `task2__rotation_map__core_belt__*.png`, `task2__rotation_dm_*.png`, `artifacts/tables/task4/task2__areal_stats_by_class__*.csv`, `*__metadata.json`, `task2__areal_stats_by_region__*.csv`, `task2__areal_stats_by_county__*.csv`, `task2__areal_stats_by_county_core4__*.csv`, `task2__per_state_rotation_classes.png`, `task2__rotation_class_by_county__*.png`, `task2__rotation_class_by_county_core4__*.png`, `artifacts/logs/runs/*/run_bundle.json`
- **Key findings:** By-region rows are **state names** from spatial join (plus `outside_configured_states` / `full_raster_extent` fallback if boundaries unavailable) — not an Iowa–Nebraska longitude proxy.
- **Next steps:** Re-run after stack changes; interpret empty rare states as extent, not pipeline failure. (Legacy NB04/NB05 sources live under `notebooks/task2_crop_rotation/_deprecated/` for the merge rebuild script.)

---

### Task 3 — Soil Moisture Anomaly (frequentist z-score + NIG Bayesian)

Three notebooks: **data prep → climatology + NIG Bayesian anomalies → maps/tables/bundle**. Full results and interpretation in `context/TASK3_RESULTS.md`.

#### notebooks/task3_soil_moisture/01_pixel_panel_smap_cdl.ipynb
- **Purpose:** Build the spatial subset: **rotation-eligible** `iy, ix` from Task 2 (~2.08M pixels), attach **per-event-year CDL label** (`cdl_2019`, `cdl_2022`); sanity histograms of one SMAP week per event year on that subset.
- **Inputs:** `data/processed/task2/rotation_metrics.parquet`, `data/processed/cdl/cdl_stack_wide.parquet`, `data/processed/smap/smap_weekly_{2019,2022}_wide.parquet`
- **Outputs:** `data/processed/task3/task3_pixel_panel.parquet` (2,084,112 rows), `artifacts/figures/task3/task3__smap_week_histogram_subset_{2019,2022}.png`
- **Key findings:** Confirms SMAP Parquet path works **without** interim NetCDF; per-event CDL year attachment ensures crop labels match actual planted cover during each event.
- **Next steps:** Run notebook 02.

#### notebooks/task3_soil_moisture/02_climatology_and_anomalies.ipynb
- **Purpose:** **ISO week-of-year** μ and σ from **2015–2021** baseline (7 years) + **NIG conjugate Bayesian** posterior params per (pixel, week); **multi-event** z-scores **and** NIG posterior predictive anomaly scores.
- **Inputs:** `task3_pixel_panel.parquet`, SMAP wide Parquets + metadata JSONs for years 2015–2022, `configs/task3_soil_moisture.yaml`
- **Outputs:** `data/processed/task3/smap_climatology.parquet` (~45.8M rows; includes `nig_mu_n`, `nig_lam_n`, `nig_alpha_n`, `nig_beta_n`), `data/processed/task3/smap_anomaly_midwest_flood_2019.parquet` (37.5M rows), `smap_anomaly_plains_drought_2022.parquet` (27.1M rows) — each with `z_score`, `nig_p_anomaly`, `nig_p_drought`, `nig_posterior_scale`, `nig_df`.
- **Key findings:** Median posterior df = 11.0, median predictive scale = 0.0454 m³/m³. 2019 flood: median NIG P(drought) = 0.817 (wet-shifted), 0.2% pixel-weeks significant at p < 0.05. 2022 drought: median NIG P(drought) = 0.292 (dry-shifted), 4.9% pixel-weeks significant. Student-t posterior predictive provides conservative anomaly calls appropriate for a 7-year baseline.
- **Next steps:** Run notebook 03.

#### notebooks/task3_soil_moisture/03_maps_timeseries_tables.ipynb
- **Purpose:** For each `event_id`: **4-panel** z-score maps, **cropland mean z** time series, **duration/persistence** map, **NIG P(drought) 4-panel**, **NIG uncertainty** map, **z-score vs NIG scatter**, **state × crop** CSV (with NIG columns), and `run_bundle.json`.
- **Inputs:** `smap_anomaly_{event_id}.parquet`, `cdl_stack_spatial_metadata.json`, Corn Belt state boundaries
- **Outputs:** 6 PNGs per event (12 total) + 2 state × crop CSVs + `run_bundle.json`
- **Key findings:** 2019 flood — Iowa corn mean z = 0.91, 18% of pixel-weeks z > 1.5; South Dakota strongest wet anomaly (mean z ≈ 1.16). 2022 drought — Kentucky winter wheat hardest hit (mean z = −1.57, 42% pixel-weeks with NIG P(drought) < 0.10); Kansas and Nebraska corn 35–37% severe drought probability. North Dakota anomalously wet during 2022, confirming the drought was Central/Southern Plains–centered. NIG uncertainty map exposes baseline-sparse regions where z-scores should be interpreted cautiously.

#### Source modules
- `src/modeling/task3_nig_anomaly.py` — NIG posterior params + Student-t predictive scores (~113 lines, pure NumPy/SciPy)
- `src/modeling/task3_smap_anomalies.py` — frequentist climatology + z-score + event anomaly computation
- `src/modeling/task3_aggregate.py` — state × crop summary with NIG columns, chunked point-in-polygon state join
- `src/viz/task3_maps.py` — raster fill, z-map plotting, pixel coordinate utilities
- `src/io/smap_weekly_parquet.py` — SMAP wide Parquet loader, metadata reader, ISO week column resolver

---

### Task 4 — Crop Mapping Prediction

#### notebooks/task4_crop_mapping/01_feature_engineering_cdl.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task4_crop_mapping/02_ndvi_smap_feature_augmentation.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task4_crop_mapping/03_model_training_evaluation.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task4_crop_mapping/04_spatial_prediction_map.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task4_crop_mapping/05_feature_importance_ablation.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

---

## CURRENT STATUS + NEXT STEPS

**Status (2026-04-12):** Task 2 (crop rotation) and Task 3 (soil moisture anomaly) are **complete** with full notebook pipelines, Bayesian upgrades, artifact exports, and interpretation docs. Task 1 (NDVI phenology) notebooks exist but final figures are pending. Task 4 (crop-type ML) is not started. Raw → interim → processed pipeline scripts are functional.

**Next steps:**
1. Task 1: Finalise phenology figures and report export
2. Task 4: Feature engineering, model training, evaluation, ablation (if time permits before deadline)
3. PDF report (human-written): integrate figures and tables from Tasks 1–3 (and Task 4 if completed)
4. Final repository freeze: **2026-04-13 4:00 PM CT**
