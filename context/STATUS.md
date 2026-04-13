# STATUS.md

Current state of the project. Updated after each meaningful work session.

---

## Current Status

**Date:** 2026-04-12  
**Phase:** Tasks 1–3 pipelines executable. Task 2 rotation complete (notebooks **01→04**, Bayesian DM). Task 3 soil moisture **complete** — frequentist z-score + **Normal-Inverse-Gamma (NIG) Bayesian** anomaly layer, two contrasting events (2019 Midwest flood, 2022 Plains drought), 6 figures per event, state × crop CSV with NIG columns. See `context/TASK3_RESULTS.md` for full numeric results and interpretation.

## Completed

- [x] Repository scaffold created (all folders and stub files)
- [x] Data tier layout documented: `data/raw|interim|processed` with `cdl`, `ndvi`, `smap` subfolders
- [x] `development_rules.md` (operational contract)
- [x] `structure.md` (artifact index + results log template)
- [x] `DECISIONS.md` (decision log template)
- [x] `ASSUMPTIONS.md` (assumptions template)
- [x] `CHANGELOG.md`
- [x] `requirements.txt`
- [x] `.gitignore`
- [x] `configs/` — YAML configs for all four tasks
- [x] `context/` — PROJECT_BRIEF, GLOSSARY, DATASETS, INTERFACES, STATUS, RISKS, TASK2_RESULTS, TASK2_NAFSI_DATA_CONTRACT, **TASK3_RESULTS**
- [x] `notebooks/` — task subfolders (Task 2 notebooks wired to **processed** CDL; Task 3 notebooks wired to **processed** SMAP)
- [x] `src/` — io, preprocessing, modeling (**rotation_classifier**, **rotation_bayesian_dm**, **task3_nig_anomaly**, **task3_smap_anomalies**, **task3_aggregate**), evaluation, viz (**rotation_maps**, **task3_maps**), utils
- [x] `scripts/` — CLI entry-points per task plus `download_data.py`, `build_interim_data.py`, `process_interim_to_parquet.py`
- [x] `tests/` — rotation metric unit tests (`tests/test_rotation_metrics.py`)
- [x] `artifacts/` — Task 2 figures/tables; **Task 3 figures** (12 PNGs: 6 per event) + **Task 3 tables** (2 state × crop CSVs with NIG columns) + run bundles
- [x] **Task 2:** Complete pipeline — metrics, Bayesian DM, classification, maps, county choropleths, areal CSV/JSON
- [x] **Task 3:** Complete pipeline — pixel panel, ISO-week climatology, NIG Bayesian posterior, dual-event anomaly Parquets, 6 figures per event (z-maps, timeseries, duration, NIG P(drought), NIG uncertainty, z-vs-NIG scatter), state × crop CSV with NIG columns, run bundle

## In Progress

- [ ] Task 1: NDVI purity filtering + phenometrics polish (multi-year notebook exists)

## Pending

- [ ] Task 1: Final phenology figures + report export
- [ ] Task 4: Feature engineering and model training
- [ ] Task 4: Spatial prediction map and feature importance ablation  
  *(NAFSI-style crop-type metrics: OA, per-class F1, confusion matrix, NDVI/SMAP ablations — see `context/PROJECT_BRIEF.md`.)*
- [ ] PDF report (human-written)
- [ ] Final repository freeze (deadline: April 13, 2026 — 4:00 PM CT)

## Blockers

*(none currently)*
