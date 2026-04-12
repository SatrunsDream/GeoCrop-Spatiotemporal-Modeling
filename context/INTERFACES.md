# INTERFACES.md

I/O contracts, expected array shapes, file formats, and inter-module data exchange.

---

## Interim NetCDF (local pipeline)

Produced by `scripts/build_interim_data.py` from raw GeoTIFFs.

| Dataset | Path pattern | Dims / vars |
|---------|--------------|-------------|
| CDL stack | `data/interim/cdl/cdl_stack_{y0}_{y1}.nc` | `(year, y, x)` — class codes per year |
| NDVI weekly | `data/interim/ndvi/ndvi_weekly_{year}.nc` | `(time, y, x)` — NDVI in [−1, 1] or scaled float |
| SMAP weekly | `data/interim/smap/smap_weekly_{year}.nc` | `(time, y, x)` — variable `sm_surface` (m³/m³) |

Legacy: single `.nc` files directly under `data/interim/` may still be read by `process_interim_to_parquet.py` if present.

---

## Processed Parquet (local pipeline)

Produced by `scripts/process_interim_to_parquet.py`.

| Dataset | Path pattern | Table shape |
|---------|--------------|---------------|
| CDL | `data/processed/cdl/cdl_stack_wide.parquet` | One row per `(iy, ix)`; columns `iy`, `ix`, `cdl_{year}` for each year in stack |
| NDVI | `data/processed/ndvi/ndvi_weekly_{year}_wide.parquet` | One row per `(iy, ix)`; columns `iy`, `ix`, `w000`… |
| SMAP | `data/processed/smap/smap_weekly_{year}_wide.parquet` | Same wide layout as NDVI |

**Sidecars:** `*_spatial_metadata.json` or `*_metadata.json` next to each Parquet — CRS, geotransform, `height`/`width`, and per-column `time_start_day` where applicable.

---

## src/io — Loader Outputs

### cdl_loader.load_cdl(year, bbox, crs)
- **Returns:** `xarray.DataArray` — shape (H, W), dtype int16
- **CRS:** EPSG:5070 (CONUS Albers) by default
- **Dims:** (y, x)

### ndvi_loader.load_ndvi(year, doy_range, bbox, crs)
- **Returns:** `xarray.DataArray` — shape (T, H, W), dtype float32, values in [−1, 1]
- **Dims:** (time, y, x)
- **Notes:** QA-filtered; scaled to float if raw product is integer

### smap_loader.load_smap(date_range, variable, bbox, crs)
- **Returns:** `xarray.DataArray` — shape (T, H, W), dtype float32
- **Dims:** (time, y, x) on EASE-Grid 2.0 (~9 km)

### processed_loaders (wide Parquet → xarray)
- **`load_cdl_stack_from_processed(repo_root)`** — `data/processed/cdl/cdl_stack_wide.parquet` → `DataArray` `(year, y, x)`.
- **`load_cdl_stack_wide_dataframe(repo_root)`** — same CDL data as `pandas.DataFrame` (`iy`, `ix`, `cdl_<year>`).
- **`load_ndvi_weekly_all_years_processed` / `load_smap_weekly_all_years_processed`** — all `*_weekly_{year}_wide.parquet` files → `DataArray` `(calendar_year, time, y, x)`; shorter years are NaN-padded in `time` to a common length.

---

## src/preprocessing — Transform Outputs

### purity_filtering.compute_purity(cdl_30m, ndvi_250m_grid)
- **Input:** CDL 30m DataArray + NDVI 250m grid
- **Returns:** `xarray.DataArray` of float32 — crop fraction per 250 m cell per crop class
- **Shape:** (n_classes, H_ndvi, W_ndvi)

### ndvi_smoothing.smooth(ndvi_ts, method, **kwargs)
- **Input:** (T,) or (T, H, W) float32 NDVI array
- **Returns:** same shape, smoothed float32

### feature_engineering.build_feature_matrix(cdl_stack, ndvi_phenometrics, smap_stats)
- **Returns:** `pandas.DataFrame` — rows = pixels, cols = features
- **Key columns:** `[lat, lon, crop_label, cdl_hist_*, ndvi_*, smap_*, rotation_score]`

---

## src/modeling — Model I/O

### crop_type_model.train(X_train, y_train, config)
- **Returns:** fitted model object (LightGBM / sklearn compatible)
- **Saves:** serialized model to `artifacts/models/task4/`

### crop_type_model.predict(model, X_test)
- **Returns:** `np.ndarray` of int class labels, shape (N,)

### rotation_classifier.classify(cdl_stack, config)
- **Returns:** `xarray.DataArray` — shape (H, W), values: {0=regular, 1=monoculture, 2=irregular}

---

## Artifact File Formats

| Type | Extension | Notes |
|------|-----------|-------|
| Figures | `.png` | dpi=200 (exploration) or dpi=300 (report) |
| Tables | `.csv` | UTF-8, comma-delimited |
| Raster outputs | `.tif` | GeoTIFF, EPSG:5070 |
| Models | `.joblib` | scikit-learn compatible |
| Run metadata | `.json` | UTF-8 |

---

## Config Interface

All scripts and notebooks accept:
```python
import yaml
with open("configs/taskN_xxx.yaml") as f:
    cfg = yaml.safe_load(f)
```
No magic numbers — all thresholds and paths come from the config dict.
