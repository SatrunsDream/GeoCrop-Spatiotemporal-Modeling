# Task 2 — Data contract & NAFSI-aligned rigor

**Purpose:** After reprocessing `data/processed/cdl/` and `data/processed/ndvi/`, Task 2 notebooks must read **stable paths** and write **versioned artifacts** under `artifacts/`, consistent with the Track 1 brief (`resources/CropSmart_NAFSI_Track1_Challenge_Brief.docx.pdf`) and the same patterns used in `notebooks/task1_ndvi_timeseries/model.ipynb` (config-driven paths, JSON sidecars, explicit outputs).

---

## 1. Processed CDL layout (current naming)

**Extent lineage:** The **pixel grid** in this Parquet comes from the data pipeline (`download_data.py` uses `study_extent.yaml`; `process_interim_to_parquet.py --source wms` unions `task1_ndvi_analysis.yaml` `study_area.states`). Task 2’s **`study_area.states`** in `task2_crop_rotation.yaml` should match that Corn Belt definition for maps and per-state areal stats — see `context/DATASETS.md` §5.1.

| File | Role |
|------|------|
| `data/processed/cdl/cdl_stack_wide.parquet` | One row per grid cell: `iy`, `ix`, `cdl_2008`, …, `cdl_2025` (18 bands after a full 2008–2025 export). |
| `data/processed/cdl/cdl_stack_spatial_metadata.json` | `height`, `width`, `years`, `crs`, `transform`, `source_nc` — required for raster-shaped stacks. |

**Task 2 analysis window** is defined in `configs/task2_crop_rotation.yaml` as `cdl.year_range: [2015, 2024]` (10 inclusive years). The loader (`load_cdl_wide_years`) requests only those `cdl_{year}` columns; they must exist in the wide Parquet (present when the processed stack includes 2015–2024).

---

## 2. Processed NDVI layout (reference for Task 1 / cross-task consistency)

| Pattern | Role |
|---------|------|
| `data/processed/ndvi/ndvi_weekly_{YEAR}_wide.parquet` | Weekly columns `w000`, … keyed to `ndvi_weekly_{YEAR}_metadata.json` `time_start_day`. |

Task 2 is CDL-only; NDVI is listed here so **one** processed naming convention is documented for the repo.

---

## 3. Task 2 outputs (must match YAML `output`)

From `configs/task2_crop_rotation.yaml`:

- **Figures:** `artifacts/figures/task2/` — all `task2__*.png` maps and diagnostics.
- **Tables (NB02–03):** `artifacts/tables/task2/` — e.g. `task2__threshold_sensitivity_grid.csv`, **`task2__markov_transition_{counts,probs}.csv`**.
- **Tables (NB05 areal CSV + JSON):** `artifacts/tables/task4/` — YAML `output.task4_tables_dir` (`task2__areal_stats_by_class__*.csv`, `*__metadata.json`, `task2__areal_stats_by_region__*.csv`). GeoTIFFs are **not** written here; rasters stay under `data/processed/task2/`.
- **Geospatial / metrics cache:** `data/processed/task2/` — `rotation_metrics.parquet`, `rotation_metrics_classified.parquet`, `rotation_class_map*.tif`.

**Run bundle:** `artifacts/logs/runs/<id>/run_bundle.json` (Notebook 05) for provenance.

---

## 4. Scientific process checklist (brief + `model.ipynb` patterns)

Use the **PDF** as the rubric source; automate everything below in notebooks or scripts.

1. **Pinned configuration** — Load `configs/task2_crop_rotation.yaml` at the start of each notebook; record `year_range`, thresholds, and output dirs from YAML (no magic paths for figures/tables).
2. **Data lineage** — Parquet + `cdl_stack_spatial_metadata.json` document CRS, transform, and source NetCDF path from `process_interim_to_parquet.py`.
3. **Pre-registered rules** — Classification thresholds live in YAML; sensitivity sweep explores the neighborhood without silently changing the primary rule.
4. **Reproducibility** — Fix `run.seed` in YAML where used; save dated filenames where notebooks already use `date.today()` (e.g. areal CSV).
5. **Uncertainty / limitations** — Document CDL noise, coarse grid (~320 m), and strict vs relaxed interpretation (`context/TASK2_RESULTS.md`, `context/RISKS.md`).
6. **Deliverables** — Figures and tables under `artifacts/` for graders; processed rasters under `data/processed/task2/` for downstream maps.

**Task 1 reference:** `model.ipynb` loads YAML, reads `data/processed/ndvi/..._metadata.json` for DOY alignment, writes figures to `cfg["output"]["figures_dir"]` and tables to `cfg["output"]["tables_dir"]`. Task 2 mirrors that layout with `task2_crop_rotation.yaml`.

---

## 5. Commands to refresh processed stacks (from raw)

```text
python scripts/build_interim_data.py --dataset cdl
python scripts/process_interim_to_parquet.py --dataset cdl --source interim

python scripts/build_interim_data.py --dataset ndvi
python scripts/process_interim_to_parquet.py --dataset ndvi --source interim
```

Then re-run Task 2 notebooks **01 → 05** (order matters).

---

## 6. Cross-references

- `context/TASK2_RESULTS.md` — numeric interpretation and **§8** (how Task 2 maps to common NAFSI / judging prompts vs Task 4).  
- `context/PROJECT_BRIEF.md` — **end-to-end pipeline** mermaid diagram and **rubric-to-task** table (all four tasks).  
- `context/DATASETS.md` §5 — raw → interim → processed layout.  
- `resources/CropSmart_NAFSI_Track1_Challenge_Brief.docx.pdf` — official criteria and report questions.
