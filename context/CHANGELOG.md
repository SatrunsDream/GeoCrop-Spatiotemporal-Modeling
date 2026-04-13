# CHANGELOG.md

Milestone and version log for the GeoCrop NAFSI Track 1 submission.

---

## [Unreleased]

### Added
- **Task 3 Bayesian NIG anomaly layer**: `src/modeling/task3_nig_anomaly.py` — conjugate Normal-Inverse-Gamma posterior predictive anomaly detection for SMAP soil moisture (Student-t, no MCMC, pure NumPy/SciPy).
- `context/TASK3_RESULTS.md` — full results and interpretation doc mirroring `TASK2_RESULTS.md` structure.
- NB02 (Task 3): NIG posterior params (`nig_mu_n`, `nig_lam_n`, `nig_alpha_n`, `nig_beta_n`) added to `smap_climatology.parquet`; `nig_p_anomaly`, `nig_p_drought`, `nig_posterior_scale`, `nig_df` added to each event anomaly Parquet.
- NB03 (Task 3): 3 new figures per event — NIG P(drought) 4-panel (RdYlBu), posterior uncertainty map (magma), z-score vs NIG scatter. State×crop CSV now includes `mean_nig_p_drought` and `frac_pdrought_lt_0p1`.
- `context/TASK2_NAFSI_DATA_CONTRACT.md` — processed CDL/NDVI naming, Task 2 artifact layout, NAFSI rigor checklist (mirrors Task 1 `03_ndvi_phenology_hsgp_bayesian.ipynb` patterns).

### Changed
- `context/TASK2_RESULTS.md`, `TASK2_NAFSI_DATA_CONTRACT.md`, `RISKS.md` (RISK-009): document **2026-04-12** re-run artifacts, **posterior P(regular)** map interpretation (§2.7), merged notebook **04**, class-map legend **upper right**, and DM GeoTIFF paths.
- Task 2: **Dirichlet–Multinomial** Bayesian rotation layer (`src/modeling/rotation_bayesian_dm.py`, YAML `bayesian_dm`) → `dm_*` columns in `rotation_metrics.parquet`, float GeoTIFFs in NB03, maps in merged notebook **04**; former NB04/NB05 merged into `04_spatial_maps_and_areal_export.ipynb` (sources under `_deprecated/`).
- Task 1: renamed `notebooks/task1_ndvi_timeseries/model.ipynb` to `03_ndvi_phenology_hsgp_bayesian.ipynb` (HSGP / NumPyro Bayesian phenology); cross-references updated in `context/` and Task 2 notebook 01.
- Task 2 CDL analysis window set to **2015–2024** (10 years) in `configs/task2_crop_rotation.yaml`; Task 2 notebooks, `rotation_maps` default title, and context docs updated.
- Task 2 notebooks: valid **nbformat** (`execution_count`, cell `id`) for `jupyter nbconvert --execute`; Markov plot uses **matplotlib** only (no **seaborn** import in NB02).
- `context/TASK2_RESULTS.md` rewritten from **current** parquet / CSV / sensitivity outputs (rotation-eligible denominator, geography caveat, strength assessment).
- NB02: Markov **volume-by-origin** printout, **asymmetry** four-bar figure (`task2__transition_asymmetry.png`), **run-length** discrete bars (`task2__runlength_distribution.png`). NB03 markdown: **monoculture % invariant** across sensitivity grid. `TASK2_RESULTS.md` §**2.7** documents Findings A–F.

### Added
- `context/TASK2_RESULTS.md` — Task 2 rotation run statistics, interpretation, and improvement notes
- Task 2 implementation: `src/io/cdl_parquet.py`, `rotation_classifier`, `rotation_maps`, processed-CDL notebooks 01–05, `data/processed/task2/` outputs
- Documentation: `README.md` and `context/` (`structure.md`, `DATASETS.md` §5, `INTERFACES.md`, `PROJECT_BRIEF.md`) describe `data/raw|interim|processed` subfolders (`cdl`, `ndvi`, `smap`) and the download → interim → Parquet scripts
- Initial repository scaffold with full folder hierarchy
- Root-level documentation: development_rules.md, structure.md, DECISIONS.md, ASSUMPTIONS.md
- Context system files: PROJECT_BRIEF.md, GLOSSARY.md, DATASETS.md, INTERFACES.md, STATUS.md, RISKS.md
- Notebook stubs for all four tasks (5 notebooks per task)
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
| Task 2 — Rotation mapping complete | TBD | ⬜ Pending |
| Task 3 — SMAP anomaly complete (freq + NIG Bayesian) | 2026-04-12 | ✅ Done |
| Task 4 — Crop prediction model complete | TBD | ⬜ Pending |
| PDF report draft | TBD | ⬜ Pending |
| Final review + freeze | 2026-04-13 16:00 CT | ⬜ Pending |
