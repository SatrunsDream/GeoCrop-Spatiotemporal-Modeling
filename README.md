# GeoCrop Spatiotemporal Modeling

## 2026 CropSmart Data Challenge — NAFSI Track 1

A reproducible, end-to-end geospatial analysis and machine learning pipeline for
agricultural resilience modeling across the U.S. Corn Belt (13 states). The
project integrates three operational remote-sensing datasets — **USDA Cropland
Data Layer (CDL)**, **MODIS NDVI**, and **NASA SMAP L4 Soil Moisture** — to
answer four progressive research questions about crop phenology, rotation
patterns, soil moisture anomalies, and crop-type prediction.

> **Read the report:**
> For a complete description of our methodology, results, and discussion, see
> **[`NAFSI_Predictive_Modeling_for_Agricultural_Resilience.pdf`](NAFSI_Predictive_Modeling_for_Agricultural_Resilience.pdf)**
> included at the root of this repository.

---

## Quick Start

There are **two ways** to reproduce our results:

| Path | Best for | What to do |
|------|----------|------------|
| **One-click orchestration** | Quick end-to-end recreation | Open `CropSmart_NAFSI_Track1_Template.ipynb` and run every cell top-to-bottom. It installs dependencies, downloads data, runs all four tasks, and displays key figures and tables. |
| **Granular exploration** | Deep understanding of each step | Follow the [Environment Setup](#environment-setup) below, then open each task folder under `notebooks/` and run notebooks in numbered order (01 → 02 → 03 → …). |

---

## Problem Description

The CropSmart NAFSI Track 1 challenge poses four tasks, each building on shared
geospatial data to characterise crop systems at the pixel level (~250 m–557 m
analysis grid, EPSG:5070 Albers projection):

| Task | Research Question | Primary Datasets | Methodology |
|------|-------------------|-------------------|-------------|
| **1** | How do corn and soybean NDVI phenologies differ across the Corn Belt? | MODIS NDVI + CDL | Hilbert Space Gaussian Process (HSGP) for smooth, uncertainty-aware seasonal curves |
| **2** | What spatial patterns of crop rotation exist over a 10-year CDL sequence? | CDL 2015–2024 | Four sequence metrics → hierarchical rule-based classification (regular / monoculture / irregular) + Bayesian Dirichlet–Multinomial |
| **3** | Where and when did soil moisture anomalies occur during the 2019 Midwest Flood and 2022 Plains Drought? | SMAP L4 + CDL | Frequentist z-score + Bayesian Normal-Inverse-Gamma (NIG) conjugate posterior for robust anomaly detection |
| **4** | Can we predict crop type from CDL history, NDVI phenology, and SMAP soil moisture? | CDL + NDVI + SMAP | LightGBM gradient-boosted classifier with temporal holdout, ablation study, and SHAP feature importance |

---

## Environment Setup

**Prerequisites:** Python 3.10–3.12, `pip`, and `git`.

```bash
# 1. Clone the repository
git clone <repo-url>
cd GeoCrop-Spatiotemporal-Modeling

# 2. Create and activate a virtual environment
python -m venv .venv

# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. Install all dependencies (pinned versions in requirements.txt)
pip install -r requirements.txt

# 4. Register the src/ package so notebooks can import it
pip install -e .
```

> **Windows + GDAL note:** If `rasterio` fails to install via pip, install
> `rasterio` and `GDAL` from conda-forge first, then `pip install` the rest.

> **NumPy 2 note:** On Python 3.13+, NumPy 2.x is required. The
> `requirements.txt` handles this automatically with environment markers.

After setup, verify with:

```bash
python -c "import src; import numpy; import pandas; import rasterio; print('All imports OK')"
```

---

## Dataset Access

All three datasets are publicly available through the National Data Platform
(NDP) and the CropSmart Digital Twin portal. No API keys or credentials are
required for CDL or NDVI. SMAP requires a free NASA Earthdata login.

| Dataset | Source | Resolution | Period Used |
|---------|--------|------------|-------------|
| **CDL** (Cropland Data Layer) | [USDA NASS CropScape](https://nassgeodata.gmu.edu/CropScape) | 30 m annual | 2015–2024 |
| **MODIS NDVI** | [CropSmart Portal](https://cloud.csiss.gmu.edu/CropSmart/) | 250 m weekly composites | 2015–2024 (growing season) |
| **SMAP L4** (Soil Moisture) | [CropSmart Portal](https://cloud.csiss.gmu.edu/CropSmart/) | 9 km weekly | 2015–2022 |
| **TIGER/Line** (State/County boundaries) | [US Census Bureau](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | Vector | 2023 |

**Automated download:** The data pipeline scripts handle downloading, stacking,
and converting all datasets:

```bash
# Download raw GeoTIFFs (30–90 min depending on network)
python scripts/download_data.py --dataset cdl
python scripts/download_data.py --dataset ndvi
python scripts/download_data.py --dataset smap

# Stack into interim NetCDF files (5–10 min)
python scripts/build_interim_data.py --dataset all

# Convert to analysis-ready wide Parquet + JSON metadata (5–15 min)
python scripts/process_interim_to_parquet.py --dataset all
```

For SMAP, set up NASA Earthdata credentials first:

```bash
python scripts/setup_earthdata_netrc.py
```

See `context/DATASETS.md` for full schemas, licensing, QA flags, and download
details.

---

## Running the Experiments

### Option A — Orchestration notebook (recommended for reviewers)

Open `CropSmart_NAFSI_Track1_Template.ipynb` in JupyterLab and run cells
sequentially. Each section explains what it does, runs the pipeline, and
displays key result figures and summary tables inline.

```bash
jupyter lab CropSmart_NAFSI_Track1_Template.ipynb
```

### Option B — Individual task notebooks

Each task has its own folder with numbered notebooks that run top-to-bottom:

```bash
jupyter lab
```

| Task | Notebooks | Approx. runtime |
|------|-----------|-----------------|
| **Task 1** — NDVI Phenology | `notebooks/task1_ndvi_timeseries/01_*.ipynb` → `03_*.ipynb` | 2–45 min (HSGP sampling is the bottleneck) |
| **Task 2** — Crop Rotation | `notebooks/task2_crop_rotation/01_*.ipynb` → `04_*.ipynb` | 5–15 min |
| **Task 3** — Soil Moisture | `notebooks/task3_soil_moisture/01_*.ipynb` → `03_*.ipynb` | 5–10 min |
| **Task 4** — Crop Mapping | `notebooks/task4_crop_mapping/01_*.ipynb` → `04_*.ipynb` | 10–30 min (training + SHAP) |

> **Optional — Hyperparameter Tuning (Task 4):**
> An additional notebook `notebooks/task4_crop_mapping/02b_hyperparameter_tuning.ipynb`
> uses [Optuna](https://optuna.org/) (Bayesian TPE search) to tune LightGBM hyperparameters
> over a 9-dimensional search space. This is **not required** for reproducing the reported
> results — the core NB02 ablation study uses the default hyperparameters. Running the
> tuning notebook takes ~30–60 minutes and may yield 1–3 pp accuracy improvement.
> We did not have sufficient time to fully complete this tuning pass before submission,
> so we include it as a ready-to-run extension for future work.

### Option C — CLI scripts

Task 2 and Task 4 also have standalone CLI entry-points:

```bash
python scripts/run_task2_rotation.py   --config configs/task2_crop_rotation.yaml
python scripts/run_task4_crop_mapping.py --config configs/task4_crop_mapping.yaml
```

---

## Expected Outputs

After a full run, the `artifacts/` directory is populated with all generated
results. Nothing in this folder is hand-edited.

### Figures (`artifacts/figures/`)

| Task | Key Figures | Description |
|------|-------------|-------------|
| **Task 1** | `hsgp_phenology_crops.png`, `hsgp_phenology_corn_vs_soy.png`, `phenological_features_by_year.png`, `calibration_diagnostics.png` | HSGP posterior phenology curves, per-year feature comparison, model diagnostics |
| **Task 2** | `task2__rotation_map__smoothed__*.png`, `task2__metric_histograms.png`, `task2__rotation_dm_p_regular__*.png`, `task2__rotation_class_by_county__*.png` | Rotation class maps (raw + smoothed), metric distributions, Bayesian P(regular) posterior, county choropleths |
| **Task 3** | `task3__*__anomaly_map_4panel__*.png`, `task3__*__nig_p_drought_4panel__*.png`, `task3__*__anomaly_timeseries_cropland__*.png`, `task3__*__zscore_vs_nig_scatter__*.png` | Z-score raster maps, NIG posterior P(drought), belt-wide time series, frequentist vs Bayesian scatter |
| **Task 4** | `task4_crop_maps_pred_vs_true.png`, `task4_confusion_matrices.png`, `task4_shap_importance.png`, `task4_ablation_comparison.png`, `task4_agreement_map.png` | Predicted vs true maps with state overlays, confusion matrices, SHAP bar/beeswarm, ablation study |

### Tables (`artifacts/tables/`)

| Task | Key Tables | Description |
|------|------------|-------------|
| **Task 1** | `hsgp_posterior_phenology.csv`, `model_evaluation.csv` | Posterior phenological parameters, model fit metrics |
| **Task 2** | `task2__markov_transition_{counts,probs}.csv`, `task2__threshold_sensitivity_grid.csv`, areal stats CSVs | Markov chain tables, threshold sensitivity, state/county-level rotation class shares |
| **Task 3** | `task3__*__anomaly_stats_by_state_crop__*.csv` | State × crop anomaly summaries (z-score + NIG posterior columns) for both events |
| **Task 4** | `task4_ablation_results.csv`, `task4_shap_feature_importance.csv`, `task4_regime_stratified_metrics.csv`, `task4__test_metrics__*.json` | Ablation study (4 configurations), top-20 SHAP values, rotation-regime performance, test-year metrics |

### Models (`artifacts/models/`)

| File | Description |
|------|-------------|
| `task4/crop_type_model.joblib` | Trained LightGBM classifier (4-class, ~500 trees) |
| `task4/crop_type_model_tuned.joblib` | *(Optional)* Optuna-tuned LightGBM — generated by `02b_hyperparameter_tuning.ipynb` |

---

## Key Results Summary

| Task | Headline Result |
|------|-----------------|
| **Task 1** | HSGP posterior curves clearly separate corn (later green-up, higher peak NDVI) from soybean, with calibrated uncertainty bands across years. |
| **Task 2** | 16–17% of eligible pixels follow strict annual corn–soy rotation (regular), 27% monoculture (≥7 consecutive years of one crop), and 56% irregular. Bayesian Dirichlet–Multinomial posterior P(regular) provides pixel-level uncertainty. |
| **Task 3** | 2019 Midwest Flood: mean z-score +0.91 (Iowa corn); 2022 Plains Drought: Kentucky winter wheat hardest hit (mean z = −1.57, 42% pixel-weeks with NIG P(drought) < 0.10). NIG posterior exposes data-sparse regions where z-scores alone would be misleading. |
| **Task 4** | **79.2% overall accuracy**, macro F1 = 0.791 on 2023 holdout. Ablation shows NDVI adds +1.7 pp accuracy over CDL-only; SMAP adds +0.07 pp. Monoculture pixels are easiest (95.5% accuracy); irregular rotation is hardest (70.9%). Top SHAP features: prior-year CDL code, NDVI mid-season mean, growing-season SMAP mean. |

---

## Directory Structure

```
GeoCrop-Spatiotemporal-Modeling/
│
├── README.md                          # This file
├── requirements.txt                   # Pinned Python dependencies
├── CropSmart_NAFSI_Track1_Template.ipynb  # One-click orchestration notebook
│
├── configs/                           # YAML configs (no magic numbers in code)
│   ├── task1_ndvi_analysis.yaml
│   ├── task2_crop_rotation.yaml
│   ├── task3_soil_moisture.yaml
│   ├── task4_crop_mapping.yaml
│   └── study_extent.yaml
│
├── notebooks/                         # Analysis notebooks (run in numbered order)
│   ├── task1_ndvi_timeseries/         # 3 notebooks: data → phenology → HSGP Bayesian
│   ├── task2_crop_rotation/           # 4 notebooks: load → metrics → classify → maps
│   ├── task3_soil_moisture/           # 3 notebooks: panel → climatology → maps/tables
│   └── task4_crop_mapping/            # 4 notebooks: features → train → SHAP → maps
│
├── src/                               # Reusable Python package (pip install -e .)
│   ├── io/                            #   Data loaders: CDL Parquet, SMAP weekly, TIGER
│   ├── preprocessing/                 #   Feature engineering (Task 4 panel builder)
│   ├── modeling/                      #   Classifiers, Bayesian models, anomaly modules
│   ├── viz/                           #   Plotting: rotation maps, anomaly maps, prediction maps
│   └── utils/                         #   NAFSI catalog, study extent, shared helpers
│
├── scripts/                           # CLI entry-points
│   ├── download_data.py               #   Download raw GeoTIFFs from CropSmart / NDP
│   ├── build_interim_data.py          #   Raw GeoTIFF → interim NetCDF stacks
│   ├── process_interim_to_parquet.py  #   Interim NetCDF → analysis-ready Parquet
│   ├── setup_earthdata_netrc.py       #   Configure NASA Earthdata credentials for SMAP
│   ├── run_task2_rotation.py          #   CLI: full Task 2 pipeline
│   └── run_task4_crop_mapping.py      #   CLI: full Task 4 pipeline
│
├── data/                              # Data directory (gitignored)
│   ├── raw/                           #   Downloaded GeoTIFFs (cdl/, ndvi/, smap/)
│   ├── interim/                       #   NetCDF stacks (cdl/, ndvi/, smap/)
│   ├── processed/                     #   Wide Parquet + JSON sidecars (cdl/, ndvi/, smap/, task2/, task3/)
│   └── external/                      #   TIGER boundaries, reference metadata
│
├── artifacts/                         # All generated outputs (never hand-edited)
│   ├── figures/                       #   PNG plots organized by task (task1–task4)
│   ├── tables/                        #   CSV/JSON summary tables by task
│   ├── models/                        #   Serialized trained models (task4/)
│   └── reports/                       #   Auto-generated report sections
│
└── resources/                         # Reference literature and challenge brief (PDF)
```

---

## Separation of Code, Data, and Results

The repository enforces a strict separation:

- **Code** lives in `src/` (reusable package), `scripts/` (CLI tools), and
  `notebooks/` (analysis). All hyperparameters and thresholds are externalized
  to YAML files under `configs/`.
- **Data** lives under `data/` with a three-tier pipeline (raw → interim →
  processed). All data directories are gitignored; the download scripts
  regenerate them deterministically.
- **Results** live under `artifacts/` with subdirectories for figures, tables,
  models, and reports. Each task's outputs are namespaced (`task1/`, `task2/`,
  etc.). Artifacts are generated programmatically by notebooks and scripts —
  never hand-edited.

---

## Configuration

All experiment parameters are defined in YAML config files under `configs/`.
Notebooks and scripts load these configs at the top of each run, so there are
no hardcoded thresholds or magic numbers in the analysis code.

| Config File | Controls |
|-------------|----------|
| `task1_ndvi_analysis.yaml` | CDL year, study area bounds, purity threshold, HSGP kernel parameters |
| `task2_crop_rotation.yaml` | CDL year range, rotation metric thresholds, classification rules, Bayesian DM priors |
| `task3_soil_moisture.yaml` | Baseline period, event definitions, NIG prior hyperparameters, anomaly method |
| `task4_crop_mapping.yaml` | Target classes, feature set toggles, LightGBM hyperparameters, train/val/test split, ablation configs |
| `study_extent.yaml` | 13-state Corn Belt bounding box and state list |

---

## Data Pipeline Detail

The data flows through three stages, each handled by a dedicated script:

```
  Raw GeoTIFFs              Interim NetCDF stacks         Analysis-ready Parquet
  ┌──────────┐  build_     ┌──────────────────┐  process_  ┌──────────────────┐
  │ CDL .tif │─ interim_ ─▶│ cdl_stack.nc     │─ interim_ ▶│ cdl_stack_wide   │
  │ NDVI .tif│  data.py    │ ndvi_weekly_Y.nc │  to_       │   .parquet       │
  │ SMAP .tif│             │ smap_weekly_Y.nc │  parquet.py│ + _metadata.json │
  └──────────┘             └──────────────────┘            └──────────────────┘
       ▲                                                          │
  download_data.py                                     notebooks read these
```

**Processed Parquet schema:** Wide tables indexed by pixel coordinates (`iy`,
`ix`) with weekly columns (`w000`, `w001`, …). Each Parquet file has a
companion JSON sidecar containing the affine transform, CRS (EPSG:5070), grid
dimensions, and week-to-date mapping.

---

## Evaluation Metrics

| Task | Metrics Used |
|------|-------------|
| **Task 1** | Posterior predictive checks, HSGP calibration diagnostics, phenological feature extraction (green-up week, peak NDVI, amplitude) |
| **Task 2** | Alternation score, pattern edit distance, Shannon entropy, max run length; threshold sensitivity analysis; Bayesian DM posterior P(regular) and posterior std |
| **Task 3** | Z-score anomaly maps, NIG posterior P(drought), NIG posterior predictive scale, duration fraction (% weeks exceeding threshold), state × crop summary statistics |
| **Task 4** | Overall accuracy (OA), macro F1-score, per-class F1, 4×4 confusion matrix, SHAP mean |SHAP| feature importance, ablation study (4 feature configurations), rotation-regime stratified accuracy |

---

## Experiment Tracking and Logging

- **Run bundles:** Each notebook execution writes a `run_bundle.json` to
  `artifacts/logs/runs/` containing the config snapshot, timestamp, input/output
  file paths, and summary metrics for that run.
- **Artifact naming:** All generated files embed a date stamp
  (`YYYYMMDD`) in their filename for traceability
  (e.g., `task3__midwest_flood_2019__nig_p_drought_4panel__20260412.png`).
- **Configs as records:** Because all parameters live in YAML configs, any run
  can be reproduced by re-running the notebook with the same config file.

---

## Testing and Validation

- **Evaluation metrics** are implemented directly in the analysis notebooks and
  `src/` modules (confusion matrices, F1 scores, ablation comparisons, SHAP).
- **Results are reproducible:** All outputs under `artifacts/` can be
  regenerated by re-running notebooks or the orchestration notebook. Random
  seeds are set in configs and applied consistently.
- **Sanity checks in notebooks:** Each notebook includes inline validation
  (shape assertions, distribution histograms, NaN audits) before proceeding
  to the analysis stage.
- **Ablation study (Task 4):** Systematically evaluates four feature
  configurations (CDL-only → CDL+NDVI → CDL+SMAP → full) to validate each
  data source's contribution, with metrics saved to
  `artifacts/tables/task4/task4_ablation_results.csv`.
- **Regime-stratified evaluation (Task 4):** Model performance is broken down
  by rotation regime (regular, monoculture, irregular) to assess robustness
  across different agricultural practices.

---

## Contribution History

Commit history and contributions are tracked through git. All team members have
contributed across the project timeline. See `git log --oneline --graph` for
the full history.

---

## Submission

**Deadline:** April 13, 2026 — 4:00 PM CT. No repository updates after the deadline.

**Evaluation rubric (from challenge brief):**

| Category | Weight |
|----------|--------|
| Analytical Accuracy | 35% |
| Methodology & Reproducibility | 30% |
| Innovation | 20% |
| Communication | 15% |

---

## License

All input datasets (CDL, MODIS NDVI, SMAP) are publicly available U.S.
government or NASA data products. See `context/DATASETS.md` for individual
licensing details.
