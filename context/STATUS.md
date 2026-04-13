# STATUS.md

Current state of the project. Updated after each meaningful work session.

---

## Current Status

**Date:** 2026-04-12  
**Phase:** Tasks 1–3 pipelines executable. Task 2 rotation complete (notebooks **01→04**, Bayesian DM). Task 3 soil moisture complete — **Normal-Inverse-Gamma (NIG) Bayesian** anomaly layer on top of frequentist z-scores, two events (2019 flood, 2022 drought), 6 figures per event, NIG columns in CSV tables. See `context/TASK3_RESULTS.md`.

## Completed

- [x] Repository scaffold created (all folders and stub files)
- [x] Data tier layout documented: `data/raw|interim|processed` with `cdl`, `ndvi`, `smap` subfolders (`README.md`, `context/structure.md`, `context/DATASETS.md` §5, `context/INTERFACES.md`)
- [x] `development_rules.md` (operational contract)
- [x] `structure.md` (artifact index + results log template)
- [x] `DECISIONS.md` (decision log template)
- [x] `ASSUMPTIONS.md` (assumptions template)
- [x] `CHANGELOG.md`
- [x] `requirements.txt`
- [x] `.gitignore`
- [x] `configs/` — YAML configs for all four tasks
- [x] `context/` — PROJECT_BRIEF, GLOSSARY, DATASETS, INTERFACES, STATUS, RISKS, **TASK2_RESULTS**, **TASK2_NAFSI_DATA_CONTRACT**
- [x] `notebooks/` — task subfolders (Task 2 notebooks wired to **processed** CDL)
- [x] `src/` — io, preprocessing, modeling (**rotation_classifier**), evaluation, viz (**rotation_maps**), utils
- [x] `scripts/` — CLI entry-points per task plus `download_data.py`, `build_interim_data.py`, `process_interim_to_parquet.py`, `build_task2_notebooks.py`
- [x] `tests/` — rotation metric unit tests (`tests/test_rotation_metrics.py`)
- [x] `artifacts/` — Task 2 figures under `artifacts/figures/task2/` (incl. **`task2__rotation_dm_*__*.png`**); notebook **04** areal CSV/JSON under `artifacts/tables/task4/`; Markov/sensitivity under `artifacts/tables/task2/`
- [x] **Task 2:** metrics Parquet (`dm_*` when enabled), classified Parquet, raw + smoothed rotation GeoTIFFs, **DM float GeoTIFFs**, under `data/processed/task2/`

## In Progress

- [ ] Task 1: NDVI purity filtering + phenometrics polish (multi-year notebook exists)

## Pending

- [ ] Task 1: Final phenology figures + report export
- [x] Task 2: Eligibility filter, threshold sensitivity sweep, Markov matrix, areal metadata JSON, regional table (see `TASK2_RESULTS.md`)
- [x] Task 3: SMAP baseline climatology and anomaly maps (frequentist z-score + **NIG Bayesian** posterior predictive)
- [x] Task 3: Agricultural impact interpretation (NIG P(drought) maps, uncertainty surfaces, state×crop CSV with `frac_pdrought_lt_0p1`)
- [ ] Task 4: Feature engineering and model training
- [ ] Task 4: Spatial prediction map and feature importance ablation  
  *(NAFSI-style crop-type metrics: OA, per-class F1, confusion matrix, NDVI/SMAP ablations — see `context/PROJECT_BRIEF.md` “NAFSI-style research expectations vs tasks”.)*
- [ ] PDF report (human-written)
- [ ] Final repository freeze (deadline: April 13, 2026 — 4:00 PM CT)

## Blockers

*(none currently)*
