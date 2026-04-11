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
| `artifacts/figures/` | *(empty — to be populated)* |

### Tables

| Path | Description |
|------|-------------|
| `artifacts/tables/` | *(empty — to be populated)* |

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
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task2_crop_rotation/02_rotation_metrics_computation.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task2_crop_rotation/03_rotation_classification.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task2_crop_rotation/04_spatial_mapping_rotation.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task2_crop_rotation/05_areal_statistics_export.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

---

### Task 3 — Soil Moisture Anomaly

#### notebooks/task3_soil_moisture/01_smap_data_loading.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task3_soil_moisture/02_baseline_climatology.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task3_soil_moisture/03_anomaly_computation.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task3_soil_moisture/04_spatial_anomaly_maps.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

#### notebooks/task3_soil_moisture/05_agricultural_impact_analysis.ipynb
- **Purpose:**
- **Inputs:**
- **Outputs:**
- **Key findings:**
- **Next steps:**

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
