# CHANGELOG.md

Milestone and version log for the GeoCrop NAFSI Track 1 submission.

---

## [Unreleased]

### Added
- **Task 3 Bayesian NIG anomaly layer**: `src/modeling/task3_nig_anomaly.py` — conjugate Normal-Inverse-Gamma posterior predictive anomaly detection for SMAP soil moisture (Student-t, no MCMC, pure NumPy/SciPy).
- **Task 3 multi-event analysis**: two contrasting events — 2019 Midwest flood (wet, 18 weeks) and 2022 Great Plains flash drought (dry, 13 weeks) — from a single 2015–2021 baseline climatology.
- **Task 3 six figures per event**: z-score 4-panel maps, cropland mean z time series, duration/persistence fraction, NIG P(drought) 4-panel (RdYlBu), NIG posterior uncertainty (magma), z-score vs NIG scatter.
- **Task 3 state × crop CSV with NIG columns**: `mean_nig_p_drought` and `frac_pdrought_lt_0p1` alongside frequentist z-score summaries for each state × crop stratum.
- `context/TASK3_RESULTS.md` — full results and interpretation doc with numeric tables from actual artifacts, key NAFSI questions answered, limitations section.
- NB02 (Task 3): NIG posterior params (`nig_mu_n`, `nig_lam_n`, `nig_alpha_n`, `nig_beta_n`) added to `smap_climatology.parquet`; `nig_p_anomaly`, `nig_p_drought`, `nig_posterior_scale`, `nig_df` added to each event anomaly Parquet.
- NB03 (Task 3): 3 new figures per event — NIG P(drought) 4-panel (RdYlBu), posterior uncertainty map (magma), z-score vs NIG scatter. State × crop CSV now includes `mean_nig_p_drought` and `frac_pdrought_lt_0p1`.
- `context/TASK2_NAFSI_DATA_CONTRACT.md` — processed CDL/NDVI naming, Task 2 artifact layout, NAFSI rigor checklist.

### Changed
- `context/TASK3_RESULTS.md` rewritten from **actual** 2026-04-12 artifact outputs — CSV numbers, NB02 printouts, parquet row counts — with clean interpretations answering six NAFSI-style key questions.
- `context/STATUS.md` updated to reflect Task 3 complete status with all artifact details.
- `context/structure.md` updated: Task 3 per-notebook results log populated with actual inputs, outputs, key findings, and next steps.
- `context/TASK2_RESULTS.md`, `TASK2_NAFSI_DATA_CONTRACT.md`, `RISKS.md` (RISK-009): document **2026-04-12** re-run artifacts, **posterior P(regular)** map interpretation (§2.7), merged notebook **04**, class-map legend **upper right**, and DM GeoTIFF paths.
- Task 2: **Dirichlet–Multinomial** Bayesian rotation layer (`src/modeling/rotation_bayesian_dm.py`, YAML `bayesian_dm`) → `dm_*` columns in `rotation_metrics.parquet`, float GeoTIFFs in NB03, maps in merged notebook **04**; former NB04/NB05 merged into `04_spatial_maps_and_areal_export.ipynb`.
- Task 1: renamed `notebooks/task1_ndvi_timeseries/model.ipynb` to `03_ndvi_phenology_hsgp_bayesian.ipynb` (HSGP / NumPyro Bayesian phenology).
- Task 2 CDL analysis window set to **2015–2024** (10 years) in `configs/task2_crop_rotation.yaml`.

### Added (initial scaffold)
- `context/TASK2_RESULTS.md` — Task 2 rotation run statistics, interpretation, and improvement notes
- Task 2 implementation: `src/io/cdl_parquet.py`, `rotation_classifier`, `rotation_maps`, processed-CDL notebooks 01–05, `data/processed/task2/` outputs
- Documentation: `README.md` and `context/` describe `data/raw|interim|processed` subfolders and the download → interim → Parquet scripts
- Initial repository scaffold with full folder hierarchy
- Root-level documentation: development_rules.md, structure.md, DECISIONS.md, ASSUMPTIONS.md
- Context system files: PROJECT_BRIEF.md, GLOSSARY.md, DATASETS.md, INTERFACES.md, STATUS.md, RISKS.md
- Notebook stubs for all four tasks
- src/ package skeleton: io, preprocessing, modeling, evaluation, viz, utils
- scripts/ CLI entry-points for each task
- tests/ unit test stubs and smoke test
- artifacts/ directory hierarchy

---

## Milestones

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Repo scaffold + structure | 2026-04-10 | ✅ Done |
| Task 1 — NDVI analysis complete | TBD | ⬜ Pending |
| Task 2 — Rotation mapping complete | 2026-04-12 | ✅ Done |
| Task 3 — SMAP anomaly complete (freq + NIG Bayesian) | 2026-04-12 | ✅ Done |
| Task 4 — Crop prediction model complete | TBD | ⬜ Pending |
| PDF report draft | TBD | ⬜ Pending |
| Final review + freeze | 2026-04-13 16:00 CT | ⬜ Pending |
