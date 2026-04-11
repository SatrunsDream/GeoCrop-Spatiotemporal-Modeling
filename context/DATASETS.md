# DATASETS.md

Data sources, schemas, licensing, and download instructions for all datasets used in this project.

---

## 1. Cropland Data Layer (CDL)

| Attribute | Value |
|-----------|-------|
| Producer | USDA NASS |
| Resolution | 30 m (annual raster) |
| Period | 2008–2025 |
| Format | GeoTIFF |
| Projection | Albers Equal Area (EPSG:5070 — CONUS Albers) |
| License | Public domain (U.S. government data) |

**Direct download:**
- https://croplandcros.scinet.usda.gov
- https://nassgeodata.gmu.edu/CropScape

**Local path:** `data/raw/cdl/`

**Schema:** Single-band integer raster. Each pixel value is a CDL class code (see `GLOSSARY.md`).

**Notes:**
- Legend changes slightly across years — always load the year-specific legend CSV
- Accuracy varies by crop and geography; see USDA accuracy assessment metadata

---

## 2. MODIS NDVI (via CropSmart)

| Attribute | Value |
|-----------|-------|
| Producer | NASA / CSISS GMU (CropSmart composite) |
| Resolution | 250 m |
| Temporal | Daily and weekly composites |
| Period | 2000–2026 |
| Format | GeoTIFF / NetCDF (confirm on CropSmart portal) |
| License | Public (NASA open data) |

**Access:** https://cloud.csiss.gmu.edu/CropSmart/

**Local path:** `data/raw/ndvi/`

**Schema:** Float raster, NDVI values in range [−1, 1] or scaled integer (confirm scale factor on download).

**Notes:**
- Quality/QA flags available — filter clouds and view-angle artifacts before smoothing
- Purity filtering against CDL reduces mixed-pixel bias (see `configs/task1_ndvi_analysis.yaml`)

---

## 3. SMAP L4 Soil Moisture

| Attribute | Value |
|-----------|-------|
| Producer | NASA JPL |
| Resolution | ~9 km (EASE-Grid 2.0) |
| Temporal | Daily and weekly |
| Period | 2015–2025 |
| Format | HDF5 (.h5) |
| License | Public (NASA open data) |

**Access:** https://cloud.csiss.gmu.edu/CropSmart/

**Local path:** `data/raw/smap/`

**Schema:** Gridded soil moisture (m³/m³); variable `sm_surface` for surface layer. EASE-Grid 2.0 projection.

**Notes:**
- SMAP L4 is a model-assimilation product, not a direct retrieval — anomalies reflect model-consistent soil moisture
- Baseline record begins 2015; short record may make percentile-based baselines preferable over z-scores

---

## 4. External / Supplementary Datasets

| Dataset | Source | Use | Path |
|---------|--------|-----|------|
| State boundaries (TIGER) | U.S. Census Bureau | Study area masking | `data/external/states/` |
| CDL class legend CSV | USDA NASS | Code→name lookup | `data/external/cdl_legends/` |
| ERA5 climate reanalysis | ECMWF (via CDS) | Optional supplementary features | `data/external/era5/` |
| USDA CSB field polygons | USDA NASS | Optional field-level rotation units | `data/external/csb/` |

---

## 5. Local pipeline layout (raw → interim → processed)

After download, stacks and tabular exports use fixed subfolders (see `README.md` and `structure.md`).

| Stage | CDL | NDVI | SMAP |
|-------|-----|------|------|
| **Raw** | `data/raw/cdl/` | `data/raw/ndvi/` | `data/raw/smap/` |
| **Interim** | `data/interim/cdl/cdl_stack_{y0}_{y1}.nc` | `data/interim/ndvi/ndvi_weekly_{year}.nc` | `data/interim/smap/smap_weekly_{year}.nc` |
| **Processed** | `data/processed/cdl/cdl_stack_wide.parquet` + spatial JSON | `data/processed/ndvi/ndvi_weekly_{year}_wide.parquet` + JSON per year | `data/processed/smap/smap_weekly_{year}_wide.parquet` + JSON per year |

**Scripts:** `scripts/download_data.py` → `scripts/build_interim_data.py` → `scripts/process_interim_to_parquet.py` (`--dataset cdl|ndvi|smap`). Default year lists live in `src/utils/nafsi_catalog.py` (aligned with NAFSI brief §3).

**Wide Parquet convention:** rows indexed by `iy`, `ix`; time-varying bands as columns `w000`, `w001`, … in chronological order; CDL adds `cdl_{year}` columns. Each `*_metadata.json` records CRS, transform, dimensions, and (for NDVI/SMAP) `time_start_day` per week column.

---

## Data Loading Notes

- All loaders live in `src/io/`
- Projection standardization: reproject all data to EPSG:5070 (CONUS Albers) for area-correct summaries
- SMAP → 9 km; NDVI → 250 m; CDL → 30 m. Alignment strategy documented in `DECISIONS.md`
