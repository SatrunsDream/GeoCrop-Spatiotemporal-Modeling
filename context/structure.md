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

### Task 3 — Soil Moisture Anomaly

Three notebooks (replaces former 01–05 stubs): **data prep → climatology + anomalies → maps/tables/bundle**.

#### notebooks/task3_soil_moisture/01_pixel_panel_smap_cdl.ipynb
- **Purpose:** Build the spatial subset: **rotation-eligible** `iy, ix` + **CDL 2019** label; sanity histogram of one SMAP week on that subset.
- **Inputs:** `data/processed/task2/rotation_metrics.parquet`, `data/processed/cdl/cdl_stack_wide.parquet`, `data/processed/smap/smap_weekly_2019_wide.parquet`
- **Outputs:** `data/processed/task3/task3_pixel_panel.parquet`, `artifacts/figures/task3/task3__smap_week_histogram_subset.png`
- **Key findings:** Confirms SMAP Parquet path works **without** interim NetCDF; subset keeps NB02 tractable.
- **Next steps:** Run notebook 02.

#### notebooks/task3_soil_moisture/02_climatology_and_anomalies.ipynb
- **Purpose:** **ISO week-of-year** μ and σ from **2015–2021**; **multi-event** z-scores vs that climatology (default: **2019** wet-season window, **2022** Jun–Aug Plains window in `event_windows`).
- **Inputs:** `task3_pixel_panel.parquet`, SMAP wide Parquets + metadata JSONs, `configs/task3_soil_moisture.yaml`
- **Outputs:** `data/processed/task3/smap_climatology.parquet` (union of weeks needed by all events), `data/processed/task3/smap_anomaly_{event_id}.parquet` per configured event (includes `event_id`, `event_label`).
- **Key findings:** One row per pixel-week in each event window with `z_score`, `sm_mean`, `sm_std`, `cdl_2019`.
- **Next steps:** Run notebook 03 (figures + CSV).

#### notebooks/task3_soil_moisture/03_maps_timeseries_tables.ipynb
- **Purpose:** For each `event_id`: **4-panel** anomaly maps at spread ISO weeks, **cropland mean z** time series with ±1σ band, **duration** map (wet: fraction of weeks with z > threshold; dry: fraction with z < threshold), **state × crop** summary CSV, and `run_bundle.json` with `outputs_by_event`.
- **Inputs:** `smap_anomaly_{event_id}.parquet`, `cdl_stack_spatial_metadata.json`, Natural Earth / external state boundaries (via `load_cornbelt_state_boundaries_5070`)
- **Outputs:** `artifacts/figures/task3/task3__{event_id}__anomaly_map_4panel__*.png`, `task3__{event_id}__anomaly_timeseries_cropland__*.png`, `task3__{event_id}__duration_fraction__*.png`, `artifacts/tables/task3/task3__{event_id}__anomaly_stats_by_state_crop__*.csv`, `artifacts/logs/runs/*/run_bundle.json`
- **Key findings:** Contrasts **2019** excess-moisture signal with **2022** dry-soil / negative-z patterns on the same rotation/CDL pixel frame; tables still use CDL **corn / soybean / winter wheat / oats** codes (`cdl_2019`).
- **Next steps:** Add prose interpretation (phenology calendar, NASS citations) in the report PDF.

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

**Status:** Repository scaffold complete; raw → interim → processed pipeline scripts exist (`download_data.py`, `build_interim_data.py`, `process_interim_to_parquet.py`). Notebooks and most `src/` modules remain stubs until analysis runs.

**Next steps:**
1. Populate `configs/` with real parameters after initial data exploration
2. Implement or wire `src/io/` loaders to interim NetCDF / processed Parquet as needed
3. Begin Task notebook execution in numbered order
4. Update this file after each notebook run (artifact index, results log)
