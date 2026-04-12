#!/usr/bin/env python3
"""
download_external_features.py — Download and preprocess external features for Task 4.

Fetches four datasets and saves ready-to-join Parquet files at the study grid resolution
(320m, EPSG:5070, 1520x2048 pixels).

Outputs (all in data/processed/task4/):
    soil_features.parquet           -- gSSURGO soil properties (static)
    terrain_features.parquet        -- 3DEP elevation + slope (static)
    daymet_features_{year}.parquet  -- gridMET climate aggregates (per year; filenames kept for Task 4 joins)
    csb_features.parquet            -- CSB field boundaries (optional)

Usage:
    python scripts/download_external_features.py --all
    python scripts/download_external_features.py --all --skip-soil
    python scripts/download_external_features.py --soil --terrain
    python scripts/download_external_features.py --daymet --years 2020 2021 2022

Dependencies (see requirements.txt): xarray, scipy, rioxarray, rasterio, netCDF4 (OPeNDAP),
requests, numpy, pandas, pyproj, shapely, geopandas (optional for CSB).

  - Climate: gridMET via xarray + netCDF4 OPeNDAP — no pydaymet, no Earthdata auth
  - Terrain: USGS 3DEP ImageServer exportImage + rasterio — no py3dep, no aiohttp
"""

from __future__ import annotations

import argparse
import json
import logging
import zipfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import pyproj
import rasterio
import rasterio.warp
import requests
import shapely.geometry
from rasterio.enums import Resampling
from rasterio.transform import Affine

try:
    import geopandas as gpd

    HAS_GPD = True
except ImportError:
    HAS_GPD = False

REPO_ROOT = Path(__file__).resolve().parent.parent
META_PATH = REPO_ROOT / "data" / "processed" / "cdl" / "cdl_stack_spatial_metadata.json"
OUT_DIR = REPO_ROOT / "data" / "processed" / "task4"

DAYMET_YEARS = list(range(2013, 2024))

# gSSURGO drainage class -> ordinal (1=best drained, 7=worst)
DRAINAGE_ORDER = {
    "Excessively drained": 1,
    "Somewhat excessively drained": 2,
    "Well drained": 3,
    "Moderately well drained": 4,
    "Somewhat poorly drained": 5,
    "Poorly drained": 6,
    "Very poorly drained": 7,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------


def load_grid_meta():
    """
    Load spatial metadata from cdl_stack_spatial_metadata.json.

    Returns
    -------
    transform  : list[float]   9-element GDAL-style geotransform
    height     : int
    width      : int
    bbox_5070  : tuple (west, south, east, north) in EPSG:5070 metres
    bbox_wgs84 : tuple (west_lon, south_lat, east_lon, north_lat)
    geom_wgs84 : shapely.geometry.Polygon
    affine     : rasterio.transform.Affine
    """
    with open(META_PATH) as f:
        meta = json.load(f)

    transform = meta["transform"]
    height = meta["height"]
    width = meta["width"]

    ox, sx = transform[2], transform[0]  # origin X, pixel width (m)
    oy, sy = transform[5], transform[4]  # origin Y, pixel height (negative)

    west = ox
    north = oy
    east = ox + width * sx
    south = oy + height * sy
    bbox_5070 = (west, south, east, north)

    tr = pyproj.Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)
    w_lon, s_lat = tr.transform(west, south)
    e_lon, n_lat = tr.transform(east, north)
    bbox_wgs84 = (w_lon, s_lat, e_lon, n_lat)
    geom_wgs84 = shapely.geometry.box(*bbox_wgs84)

    affine = Affine(sx, transform[1], ox, transform[3], sy, oy)

    log.info(f"Grid: {height}x{width}, EPSG:5070 bbox {tuple(round(v) for v in bbox_5070)}")
    return transform, height, width, bbox_5070, bbox_wgs84, geom_wgs84, affine


def pixels_to_df(height, width):
    """
    Build a DataFrame with (iy, ix) for all H*W pixels.
    All fetchers use this to flatten raster arrays into joinable rows.
    """
    iy, ix = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")
    return pd.DataFrame(
        {
            "iy": iy.ravel().astype("int32"),
            "ix": ix.ravel().astype("int32"),
        }
    )


# ---------------------------------------------------------------------------
# Section 1: gSSURGO soil
# ---------------------------------------------------------------------------


def _wcs_mukey_request(bbox_5070, width_px, height_px):
    """Single WCS GetCoverage request. Returns raw GeoTIFF bytes."""
    west, south, east, north = bbox_5070
    url = (
        "https://SDMDataAccess.nrcs.usda.gov/Spatial/SDM.wcs"
        "?SERVICE=WCS&VERSION=1.0.0&REQUEST=GetCoverage"
        "&COVERAGE=MapunitRaster_30m"
        "&CRS=EPSG:5070"
        f"&BBOX={west},{south},{east},{north}"
        f"&WIDTH={width_px}&HEIGHT={height_px}"
        "&FORMAT=GeoTIFF"
    )
    log.info(f"WCS request: {width_px}x{height_px} px")
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content


def _fetch_mukey_tiled(bbox_5070, raw_tif_path):
    """Download MUKEY raster in 2x2 tiles and stitch into one GeoTIFF."""
    west, south, east, north = bbox_5070
    mid_x = (west + east) / 2
    mid_y = (south + north) / 2

    quadrants = [
        (west, mid_y, mid_x, north),  # NW
        (mid_x, mid_y, east, north),  # NE
        (west, south, mid_x, mid_y),  # SW
        (mid_x, south, east, mid_y),  # SE
    ]

    w30_full = int(round((east - west) / 30))
    h30_full = int(round((north - south) / 30))
    full_arr = np.zeros((h30_full, w30_full), dtype="int32")
    tf_full = rasterio.transform.from_bounds(west, south, east, north, w30_full, h30_full)

    for q_bbox in quadrants:
        q_w, q_s, q_e, q_n = q_bbox
        tw = int(round((q_e - q_w) / 30))
        th = int(round((q_n - q_s) / 30))
        content = _wcs_mukey_request(q_bbox, tw, th)
        with rasterio.open(BytesIO(content)) as src:
            tile = src.read(1)
            col_off = int(round((q_w - west) / 30))
            row_off = int(round((north - q_n) / 30))
            full_arr[row_off : row_off + th, col_off : col_off + tw] = tile

    profile = {
        "driver": "GTiff",
        "dtype": "int32",
        "width": w30_full,
        "height": h30_full,
        "count": 1,
        "crs": "EPSG:5070",
        "transform": tf_full,
        "compress": "lzw",
    }
    raw_tif_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(raw_tif_path, "w", **profile) as dst:
        dst.write(full_arr, 1)


def _fetch_mukey_raster(bbox_5070, affine, height, width, raw_tif_path):
    """
    Download 30m MUKEY raster (tiles if needed), resample to study grid via majority.
    Returns int32 array of shape (height, width).
    """
    if not raw_tif_path.exists():
        west, south, east, north = bbox_5070
        w30 = int(round((east - west) / 30))
        h30 = int(round((north - south) / 30))
        try:
            content = _wcs_mukey_request(bbox_5070, w30, h30)
            raw_tif_path.parent.mkdir(parents=True, exist_ok=True)
            raw_tif_path.write_bytes(content)
        except Exception as e:
            log.warning(f"Single WCS request failed ({e}), falling back to 2x2 tiling")
            _fetch_mukey_tiled(bbox_5070, raw_tif_path)
    else:
        log.info(f"Raw MUKEY raster found at {raw_tif_path}, skipping download")

    dst_array = np.zeros((height, width), dtype="int32")
    with rasterio.open(raw_tif_path) as src:
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=dst_array,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=affine,
            dst_crs="EPSG:5070",
            resampling=Resampling.mode,
        )
    return dst_array


def _fetch_soil_attributes(mukeys):
    """
    POST SQL to USDA SDA REST in chunks of 1000 MUKEYs.
    Returns DataFrame: mukey, drclassdcd, aws0150wta, claytotal_r, hydgrpdcd, soc0_150.
    """
    mukey_list = [int(k) for k in mukeys if k > 0]
    results = []
    chunk_size = 1000
    for i in range(0, len(mukey_list), chunk_size):
        chunk = mukey_list[i : i + chunk_size]
        sql = (
            "SELECT mukey, drclassdcd, aws0150wta, claytotal_r, hydgrpdcd, soc0_150 "
            "FROM Valu1 "
            f"WHERE mukey IN ({','.join(str(k) for k in chunk)})"
        )
        r = requests.post(
            "https://SDMDataAccess.nrcs.usda.gov/Tabular/SDMTabularService/post.rest",
            data={"format": "JSON+COLUMNNAME", "query": sql},
            timeout=120,
        )
        r.raise_for_status()
        table = r.json().get("Table", [])
        if len(table) >= 2:
            results.append(pd.DataFrame(table[1:], columns=table[0]))
        log.info(f"  SDA chunk {i // chunk_size + 1}/{-(-len(mukey_list) // chunk_size)}: {len(table)-1} rows")

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def fetch_ssurgo_soil(bbox_5070, affine, height, width, out_dir):
    """Download gSSURGO MUKEY raster, resample to study grid, join tabular attributes, save parquet."""
    out_path = out_dir / "soil_features.parquet"
    if out_path.exists():
        log.info("soil_features.parquet already exists, skipping")
        return

    log.info("=== gSSURGO soil features ===")
    raw_tif = out_dir / "_cache" / "ssurgo_mukey_30m.tif"
    mukey_arr = _fetch_mukey_raster(bbox_5070, affine, height, width, raw_tif)

    unique_mukeys = np.unique(mukey_arr)
    log.info(f"Unique MUKEYs: {len(unique_mukeys)}")
    attr_df = _fetch_soil_attributes(unique_mukeys)

    if attr_df.empty:
        log.warning("No soil attributes returned from SDA")
        attr_df = pd.DataFrame(
            columns=["mukey", "drclassdcd", "aws0150wta", "claytotal_r", "hydgrpdcd", "soc0_150"]
        )

    attr_df["mukey"] = attr_df["mukey"].astype("int32")

    attr_df["soil_drainage_class"] = attr_df["drclassdcd"].map(DRAINAGE_ORDER).astype("float32")

    attr_df["_hg"] = attr_df["hydgrpdcd"].str[0].fillna("")
    for code in ["A", "B", "C", "D"]:
        attr_df[f"soil_hydgrp_{code}"] = (attr_df["_hg"] == code).astype("float32")

    for col, new_col in [
        ("aws0150wta", "soil_awc_150cm"),
        ("claytotal_r", "soil_clay_pct"),
        ("soc0_150", "soil_soc_150"),
    ]:
        attr_df[new_col] = pd.to_numeric(attr_df[col], errors="coerce").astype("float32")

    keep = [
        "mukey",
        "soil_drainage_class",
        "soil_awc_150cm",
        "soil_clay_pct",
        "soil_hydgrp_A",
        "soil_hydgrp_B",
        "soil_hydgrp_C",
        "soil_hydgrp_D",
        "soil_soc_150",
    ]
    attr_df = attr_df[keep].drop_duplicates("mukey")

    pixels = pixels_to_df(height, width)
    pixels["mukey"] = mukey_arr.ravel()
    result = pixels.merge(attr_df, on="mukey", how="left").drop(columns=["mukey"])

    result.to_parquet(out_path, engine="pyarrow", compression="zstd", index=False)
    log.info(f"Saved: {out_path}  shape={result.shape}")


# ---------------------------------------------------------------------------
# Section 2: gridMET climate (Daymet-compatible column names)
# ---------------------------------------------------------------------------


def fetch_gridmet_climate(bbox_wgs84, affine, height, width, years, out_dir):
    """
    Download gridMET daily climate via public OPeNDAP (no Earthdata auth).

    Source: Northwest Knowledge Network THREDDS
    Vars: tmax/tmin in Kelvin; pr = mm/day. CRS WGS84, ~4 km.

    Output columns use daymet_* names for downstream compatibility.
    """
    import rioxarray  # noqa: F401
    import xarray as xr

    # NKN catalogs use tmmx / tmmn / pr (not tmax / tmin). See reacch_climate_MET_catalog.html.
    GRIDMET_BASE = "http://thredds.northwestknowledge.net:8080/thredds/dodsC/MET"
    GRIDMET_FILES = {
        "tmax": ("tmmx", "air_temperature"),
        "tmin": ("tmmn", "air_temperature"),
        "pr": ("pr", "precipitation_amount"),
    }
    KELVIN = 273.15
    w_lon, s_lat, e_lon, n_lat = bbox_wgs84

    log.info("=== gridMET climate features (OPeNDAP, no Earthdata) ===")

    def _clip(ds):
        lat_mask = (ds.lat >= s_lat - 0.5) & (ds.lat <= n_lat + 0.5)
        lon_mask = (ds.lon >= w_lon - 0.5) & (ds.lon <= e_lon + 0.5)
        return ds.isel(lat=lat_mask, lon=lon_mask)

    def _reproject_da(da):
        da = da.rio.write_crs("EPSG:4326")
        da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
        return (
            da.rio.reproject(
                "EPSG:5070",
                shape=(height, width),
                transform=affine,
                resampling=Resampling.bilinear,
                nodata=np.nan,
            )
            .values.ravel()
            .astype("float32")
        )

    def _open_gridmet(kind: str, year: int):
        folder, vname = GRIDMET_FILES[kind]
        url = f"{GRIDMET_BASE}/{folder}/{folder}_{year}.nc"
        ds = xr.open_dataset(url, engine="netcdf4")
        if vname not in ds.data_vars:
            vname = next(iter(ds.data_vars))
        return _clip(ds)[vname].load()

    for year in years:
        out_path = out_dir / f"daymet_features_{year}.parquet"
        if out_path.exists():
            log.info(f"  {year}: already exists, skipping")
            continue

        log.info(f"  Downloading gridMET {year} ...")
        try:
            tmax_k = _open_gridmet("tmax", year)
            tmin_k = _open_gridmet("tmin", year)
            pr = _open_gridmet("pr", year)

            tmax = tmax_k - KELVIN
            tmin = tmin_k - KELVIN

        except Exception as e:
            log.error(f"  gridMET {year} failed: {e}")
            continue

        t_dim = "day" if "day" in tmax.dims else "time"
        times = pd.to_datetime(tmax[t_dim].values)
        doy = times.dayofyear

        gs = (doy >= 100) & (doy <= 280)
        tmean = (tmax.isel({t_dim: gs}) + tmin.isel({t_dim: gs})) / 2
        gdd_da = (tmean - 10).clip(min=0).sum(t_dim)

        spr_da = pr.isel({t_dim: (doy >= 60) & (doy <= 151)}).sum(t_dim)
        gs_p_da = pr.isel({t_dim: (doy >= 91) & (doy <= 273)}).sum(t_dim)
        jul_da = tmax.isel({t_dim: (doy >= 182) & (doy <= 212)}).mean(t_dim)

        pixels = pixels_to_df(height, width)
        pixels["daymet_gdd"] = _reproject_da(gdd_da)
        pixels["daymet_prcp_spring"] = _reproject_da(spr_da)
        pixels["daymet_prcp_gs"] = _reproject_da(gs_p_da)
        pixels["daymet_tmax_july"] = _reproject_da(jul_da)

        pixels.to_parquet(out_path, engine="pyarrow", compression="zstd", index=False)
        log.info(f"  Saved: {out_path}")
        del tmax_k, tmin_k, pr, tmax, tmin, gdd_da, spr_da, gs_p_da, jul_da


# ---------------------------------------------------------------------------
# Section 3: 3DEP terrain — USGS ImageServer REST
# ---------------------------------------------------------------------------

_3DEP_URL = (
    "https://elevation.nationalmap.gov/arcgis/rest/services"
    "/3DEPElevation/ImageServer/exportImage"
)


def _request_dem_tile(west, south, east, north, w_px, h_px, timeout=300):
    """Request one DEM tile from USGS 3DEP ImageServer. Returns float32 array (h_px, w_px)."""
    params = {
        "bbox": f"{west},{south},{east},{north}",
        "bboxSR": 5070,
        "size": f"{w_px},{h_px}",
        "imageSR": 5070,
        "format": "tiff",
        "pixelType": "F32",
        "noDataInterpretation": "esriNoDataMatchAny",
        "f": "image",
    }
    r = requests.get(_3DEP_URL, params=params, timeout=timeout)
    r.raise_for_status()
    with rasterio.open(BytesIO(r.content)) as src:
        return src.read(1).astype("float32")


def fetch_3dep_terrain(bbox_5070, affine, height, width, out_dir):
    """
    DEM from USGS 3DEP ImageServer; slope / northness / flat flag via numpy.gradient.
    """
    out_path = out_dir / "terrain_features.parquet"
    if out_path.exists():
        log.info("terrain_features.parquet already exists, skipping")
        return

    log.info("=== 3DEP terrain (USGS REST) ===")
    west, south, east, north = bbox_5070

    dem = None
    try:
        log.info(f"Requesting DEM at {width}x{height} px (single tile) ...")
        dem = _request_dem_tile(west, south, east, north, width, height, timeout=300)
    except Exception as e:
        log.warning(f"Single-tile DEM request failed ({e}), trying 2x2 tiles ...")

    if dem is None:
        mid_x = (west + east) / 2
        mid_y = (south + north) / 2
        hw, hh = width // 2, height // 2
        quads = [
            (west, mid_y, mid_x, north, hw, hh, 0, 0),
            (mid_x, mid_y, east, north, width - hw, hh, hw, 0),
            (west, south, mid_x, mid_y, hw, height - hh, 0, hh),
            (mid_x, south, east, mid_y, width - hw, height - hh, hw, hh),
        ]
        dem = np.zeros((height, width), dtype="float32")
        for w, s, e, n, tw, th, col, row in quads:
            log.info(f"  Tile ({col},{row}) {tw}x{th} px ...")
            tile = _request_dem_tile(w, s, e, n, tw, th, timeout=300)
            dem[row : row + th, col : col + tw] = tile

    px = abs(float(affine.a))
    py = abs(float(affine.e))

    dz_dy, dz_dx = np.gradient(dem, py, px)
    slope_deg = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))).astype("float32")
    aspect_rad = np.arctan2(-dz_dy, dz_dx)
    northness = np.cos(aspect_rad).astype("float32")
    flat_flag = (slope_deg < 1.0).astype("float32")

    pixels = pixels_to_df(height, width)
    pixels["terrain_elevation"] = dem.ravel()
    pixels["terrain_slope"] = slope_deg.ravel()
    pixels["terrain_northness"] = northness.ravel()
    pixels["terrain_flat"] = flat_flag.ravel()

    pixels.to_parquet(out_path, engine="pyarrow", compression="zstd", index=False)
    log.info(f"Saved: {out_path}  shape={pixels.shape}")


# ---------------------------------------------------------------------------
# Section 4: CSB field boundaries (optional)
# ---------------------------------------------------------------------------

CSB_URL = (
    "https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/"
    "docs/CSB_2016_2022.zip"
)


def fetch_csb_boundaries(bbox_5070, affine, height, width, out_dir):
    """Download CSB shapefile ZIP, clip, rasterize field IDs, save parquet."""
    if not HAS_GPD:
        log.error("geopandas not installed -- skipping CSB")
        return

    from rasterio.features import rasterize as rio_rasterize

    out_path = out_dir / "csb_features.parquet"
    if out_path.exists():
        log.info("csb_features.parquet already exists, skipping")
        return

    log.info("=== CSB field boundaries ===")
    cache_dir = out_dir / "_cache" / "csb"
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "csb.zip"

    if not zip_path.exists():
        log.info(f"Downloading CSB ZIP from {CSB_URL} ...")
        r = requests.get(CSB_URL, stream=True, timeout=600)
        r.raise_for_status()
        zip_path.write_bytes(r.content)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(cache_dir)

    shp_files = list(cache_dir.glob("**/*.shp"))
    if not shp_files:
        log.error("No .shp found in CSB ZIP")
        return

    csb = gpd.read_file(shp_files[0]).to_crs("EPSG:5070")
    west, south, east, north = bbox_5070
    csb = csb.cx[west:east, south:north].reset_index(drop=True)
    log.info(f"CSB polygons in study area: {len(csb)}")

    csb["_fid"] = (csb.index + 1).astype("int32")
    csb["csb_field_area_ha"] = (csb.geometry.area / 10_000).astype("float32")

    crop_col = next(
        (c for c in ["CROPTYPE", "DomCrop", "DOMCROP", "cdl_mode", "CDL_MODE"] if c in csb.columns),
        None,
    )
    csb["csb_dominant_crop"] = csb[crop_col].astype("int16") if crop_col else np.int16(-1)

    field_id_arr = rio_rasterize(
        [(geom, fid) for geom, fid in zip(csb.geometry, csb["_fid"])],
        out_shape=(height, width),
        transform=affine,
        fill=0,
        dtype="int32",
    )

    attr = csb[["_fid", "csb_field_area_ha", "csb_dominant_crop"]].drop_duplicates("_fid")
    pixels = pixels_to_df(height, width)
    pixels["_fid"] = field_id_arr.ravel().astype("int32")
    result = pixels.merge(attr, on="_fid", how="left").drop(columns=["_fid"])

    result.to_parquet(out_path, engine="pyarrow", compression="zstd", index=False)
    log.info(f"Saved: {out_path}  shape={result.shape}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    p = argparse.ArgumentParser(description="Download and preprocess external features for Task 4 crop mapping.")
    p.add_argument("--soil", action="store_true", help="Fetch gSSURGO soil features")
    p.add_argument("--daymet", action="store_true", help="Fetch gridMET climate (daymet_* columns)")
    p.add_argument("--terrain", action="store_true", help="Fetch 3DEP terrain features")
    p.add_argument("--csb", action="store_true", help="Fetch CSB field boundaries (optional)")
    p.add_argument(
        "--all",
        action="store_true",
        help="Run soil, gridMET climate, and terrain (not CSB; use --csb separately)",
    )
    p.add_argument(
        "--skip-soil",
        action="store_true",
        help="With --all, skip gSSURGO soil (WCS can be flaky)",
    )
    p.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=DAYMET_YEARS,
        help="Years for climate download (default: 2013-2023)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _transform, height, width, bbox_5070, bbox_wgs84, _geom_wgs84, affine = load_grid_meta()

    run_all = args.all
    if (run_all or args.soil) and not (run_all and args.skip_soil):
        fetch_ssurgo_soil(bbox_5070, affine, height, width, OUT_DIR)
    if run_all or args.daymet:
        fetch_gridmet_climate(bbox_wgs84, affine, height, width, args.years, OUT_DIR)
    if run_all or args.terrain:
        fetch_3dep_terrain(bbox_5070, affine, height, width, OUT_DIR)
    if args.csb:
        fetch_csb_boundaries(bbox_5070, affine, height, width, OUT_DIR)

    log.info("Done.")


if __name__ == "__main__":
    main()
