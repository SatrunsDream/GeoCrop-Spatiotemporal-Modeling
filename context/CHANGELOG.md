# CHANGELOG.md

Milestone and version log for the GeoCrop NAFSI Track 1 submission.

---

## [Unreleased]

### Added
- `context/TASK2_NAFSI_DATA_CONTRACT.md` — processed CDL/NDVI naming, Task 2 artifact layout, NAFSI rigor checklist (mirrors `model.ipynb` patterns).

### Changed
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
| Task 3 — SMAP anomaly complete | TBD | ⬜ Pending |
| Task 4 — Crop prediction model complete | TBD | ⬜ Pending |
| PDF report draft | TBD | ⬜ Pending |
| Final review + freeze | 2026-04-13 16:00 CT | ⬜ Pending |
