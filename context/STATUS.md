# STATUS.md

Current state of the project. Updated after each meaningful work session.

---

## Current Status

**Date:** 2026-04-10
**Phase:** Repository scaffold — data folder layout and pipeline scripts documented; task notebooks still mostly stubs

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
- [x] `context/` — PROJECT_BRIEF, GLOSSARY, DATASETS, INTERFACES, STATUS, RISKS
- [x] `notebooks/` — task subfolders with 5 stub notebooks each
- [x] `src/` — full package skeleton (io, preprocessing, modeling, evaluation, viz, utils)
- [x] `scripts/` — CLI entry-points per task plus `download_data.py`, `build_interim_data.py`, `process_interim_to_parquet.py`
- [x] `tests/` — unit test stubs + smoke test
- [x] `artifacts/` — directory hierarchy with .gitkeep files

## In Progress

- [ ] Task 1: NDVI data ingestion and purity filtering

## Pending

- [ ] Task 1: Smoothing + phenometrics extraction
- [ ] Task 1: Phenological curve visualization and report export
- [ ] Task 2: Rotation metrics computation and classification
- [ ] Task 2: Spatial mapping and areal statistics
- [ ] Task 3: SMAP baseline climatology and anomaly maps
- [ ] Task 3: Agricultural impact interpretation
- [ ] Task 4: Feature engineering and model training
- [ ] Task 4: Spatial prediction map and feature importance ablation
- [ ] PDF report (human-written)
- [ ] Final repository freeze (deadline: April 13, 2026 — 4:00 PM CT)

## Blockers

*(none currently)*
