# PROJECT_BRIEF.md

## What We Are Building

A reproducible, end-to-end geospatial analysis and machine learning pipeline
for the CropSmart NAFSI Track 1 challenge. The pipeline integrates three
operational datasets — CDL, MODIS NDVI, and SMAP — to characterize crop
phenology, detect rotation patterns, quantify soil moisture anomalies, and
predict crop types across the Contiguous United States.

## Four Tasks

| Task | Goal | Primary Dataset |
|------|------|----------------|
| 1 | NDVI phenological comparison: corn vs. soybean (Corn Belt) | MODIS NDVI + CDL |
| 2 | Crop rotation pattern identification over 10-year CDL series | CDL (2013–2022) |
| 3 | Soil moisture anomaly maps relative to multi-year baseline | SMAP L4 + CDL |
| 4 | Spatially generalizable crop-type classification model | CDL + NDVI + SMAP |

## Success Criteria

- All four tasks complete and fully reproducible (notebooks run top-to-bottom)
- Evaluation metrics reported: F1, OA, confusion matrix (Task 4)
- All six report questions answered clearly
- Artifact index fully populated in `structure.md`
- GitHub repository frozen before April 13, 2026 — 4:00 PM CT

## Constraints

- No AI-generated prose in the PDF report
- All supplementary datasets must be publicly accessible and documented
- Repository must include: notebooks, requirements.txt, README.md, PDF report
- Evaluation rubric: Analytical Accuracy 35%, Methodology/Reproducibility 30%, Innovation 20%, Communication 15%

## Where data lives in this repo

Large rasters are usually gitignored. The working layout is: **raw GeoTIFFs** under `data/raw/{cdl,ndvi,smap}/`, **interim NetCDF stacks** under `data/interim/{cdl,ndvi,smap}/`, and **ML-oriented wide Parquet** (plus JSON sidecars) under `data/processed/{cdl,ndvi,smap}/`. Scripts `download_data.py`, `build_interim_data.py`, and `process_interim_to_parquet.py` implement that flow; details are in `README.md`, `context/structure.md`, and `context/DATASETS.md` §5.
