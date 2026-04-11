# 2026 CropSmart Data Challenge

## GeoCrop Predictive Modeling — NAFSI Track 1

CropSmart NAFSI Track 1 challenge submission: predictive modeling for agricultural resilience using
CDL, MODIS NDVI, and SMAP across the Contiguous United States (CONUS).

### Project Overview

Four progressive tasks covering:
- **Task 1** — NDVI time-series phenology analysis for corn vs. soybean (Corn Belt)
- **Task 2** — Crop rotation pattern identification over a 10-year CDL time series
- **Task 3** — Soil moisture anomaly detection using SMAP L4 relative to historical baselines
- **Task 4** — Spatially generalizable crop-type prediction model (CDL + NDVI + SMAP)

### Repository Layout

```
GeoCrop-Predictive-Modeling/
├── README.md
├── development_rules.md     # single operational contract for this repo
├── structure.md             # repo map + artifact index + results log
├── DECISIONS.md             # design choices and rationale
├── ASSUMPTIONS.md           # modeling and data assumptions
├── CHANGELOG.md             # milestone log
├── requirements.txt
├── .gitignore
│
├── configs/                 # yaml configs for all experiments
├── context/                 # project memory (datasets, glossary, status)
├── data/                    # raw → interim (NetCDF) → processed (Parquet); see below
├── notebooks/
│   ├── task1_ndvi_timeseries/
│   ├── task2_crop_rotation/
│   ├── task3_soil_moisture/
│   └── task4_crop_mapping/
├── src/                     # reusable Python package
│   ├── io/
│   ├── preprocessing/
│   ├── modeling/
│   ├── evaluation/
│   ├── viz/
│   └── utils/
├── scripts/                 # CLI: tasks, download, interim build, Parquet export
├── tests/                   # unit tests + smoke test
└── artifacts/               # all generated outputs (never hand-edited)
    ├── figures/
    ├── tables/
    ├── models/
    ├── reports/
    └── logs/
```

### Environment Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd GeoCrop-Predictive-Modeling

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Register the src package (editable install)
pip install -e .
```

### Running the Notebooks

Open each task folder under `notebooks/` and run notebooks in numbered order
(01 → 02 → … → 05). Each notebook is self-contained and runs top-to-bottom.

```bash
jupyter lab
```

### Running Scripts (CLI)

**Task pipelines:**

```bash
python scripts/run_task1_ndvi.py       --config configs/task1_ndvi_analysis.yaml
python scripts/run_task2_rotation.py   --config configs/task2_crop_rotation.yaml
python scripts/run_task3_smap.py       --config configs/task3_soil_moisture.yaml
python scripts/run_task4_crop_mapping.py --config configs/task4_crop_mapping.yaml
```

**Raw → interim → processed (GeoTIFF → NetCDF → Parquet):**

```bash
python scripts/download_data.py --dataset all          # or cdl | ndvi | smap
python scripts/build_interim_data.py --dataset all     # stacks into data/interim/{cdl,ndvi,smap}/
python scripts/process_interim_to_parquet.py --dataset cdl   # once, multi-year wide table
python scripts/process_interim_to_parquet.py --dataset ndvi    # one Parquet per year
python scripts/process_interim_to_parquet.py --dataset smap  # one Parquet per year
```

### Data layout (local)

Paths are relative to the repo root. Large folders are typically gitignored.

| Tier | Path | Role |
|------|------|------|
| Raw | `data/raw/cdl/`, `data/raw/ndvi/`, `data/raw/smap/` | GeoTIFFs from WMS download (`scripts/download_data.py`) |
| Interim | `data/interim/cdl/`, `data/interim/ndvi/`, `data/interim/smap/` | NetCDF stacks (`scripts/build_interim_data.py`) |
| Processed | `data/processed/cdl/`, `data/processed/ndvi/`, `data/processed/smap/` | Wide Parquet + JSON sidecars (`scripts/process_interim_to_parquet.py`) |
| External | `data/external/` | Saved GetCapabilities / reference map metadata for CropSmart |

**Interim NetCDF (examples):**

- `data/interim/cdl/cdl_stack_{Y0}_{Y1}.nc` — multi-year CDL, dims `(year, y, x)`
- `data/interim/ndvi/ndvi_weekly_{year}.nc` — growing-season NDVI weeks, dims `(time, y, x)`
- `data/interim/smap/smap_weekly_{year}.nc` — weekly SMAP AVERAGE, dims `(time, y, x)`, variable `sm_surface`

**Processed Parquet:**

- `data/processed/cdl/cdl_stack_wide.parquet` + `cdl_stack_spatial_metadata.json`
- `data/processed/ndvi/ndvi_weekly_{year}_wide.parquet` + `ndvi_weekly_{year}_metadata.json`
- `data/processed/smap/smap_weekly_{year}_wide.parquet` + `smap_weekly_{year}_metadata.json`

Wide tables use grid indices `iy`, `ix` and weekly columns `w000`, `w001`, … (see each JSON for `time_start_day` and CRS/transform).

Catalog year ranges for download/build are defined in `src/utils/nafsi_catalog.py` (NAFSI brief §3).

### Data Access

All datasets are accessible via the National Data Platform (NDP) and CropSmart Digital Twin.
See `context/DATASETS.md` for sources, schemas, download instructions, and the same pipeline layout.

### Results

All outputs (figures, tables, models) are stored under `artifacts/`.
See `structure.md` for the full artifact index and results log.

### Submission Deadline

April 13, 2026 — 4:00 PM CT. No repository updates after the deadline.
