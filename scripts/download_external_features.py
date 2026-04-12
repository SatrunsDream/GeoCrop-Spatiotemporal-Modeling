#!/usr/bin/env python3
"""
download_external_features.py — Download and preprocess external features for Task 4.

Fetches four datasets and saves ready-to-join Parquet files at the study grid resolution
(320m, EPSG:5070, 1520×2048 pixels).

Outputs (all in data/processed/task4/):
    soil_features.parquet           -- gSSURGO soil properties (static)
    terrain_features.parquet        -- 3DEP elevation + slope (static)
    daymet_features_{year}.parquet  -- Daymet V4 climate (per year 2013–2023)
    csb_features.parquet            -- CSB field boundaries (optional; national ZIP is multi-GB)

Usage:
    python scripts/download_external_features.py --all
    python scripts/download_external_features.py --all --skip-soil
    python scripts/download_external_features.py --soil --soil-mukey-geotiff /path/to/MapunitRaster.tif
    python scripts/download_external_features.py --daymet --years 2020 2021 2022

gSSURGO MUKEY raster:
 USDA ``MapunitRaster_30m`` WCS (``.../Spatial/SDM.wcs``) returns404 as of 2026 on both
    ``nrcs.usda.gov`` and ``sc.egov.usda.gov`` hosts. To build ``soil_features.parquet`` you can:
    (1) download state/county gSSURGO GeoDatabase rasters from NRCS and pass
    ``--soil-mukey-geotiff`` (any CRS; the script reprojects to the study grid), or
    (2) skip soil with ``--skip-soil`` and join soil features later.

New dependencies:
    pip install pydaymet>=0.16 py3dep>=0.16
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
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
    import pydaymet  # noqa: F401

    HAS_PYDAYMET = True
except ImportError:
    HAS_PYDAYMET = False

try:
    import py3dep  # noqa: F401

    HAS_PY3DEP = True
except ImportError:
    HAS_PY3DEP = False

try:
    import geopandas as gpd  # noqa: F401

    HAS_GPD = True
except ImportError:
    HAS_GPD = False

REPO_ROOT = Path(__file__).resolve().parent.parent
META_PATH = REPO_ROOT / "data" / "processed" / "cdl" / "cdl_stack_spatial_metadata.json"
OUT_DIR = REPO_ROOT / "data" / "processed" / "task4"

# Tabular API: use ``/Tabular/post.rest`` with ``format=JSON`` (no column header row).
# Valu1-style summaries are not exposed on public SDA; we join muaggatt + dominant component + chorizon.
SDA_POST_URL = "https://SDMDataAccess.nrcs.usda.gov/Tabular/post.rest"

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
    geom_wgs84 : shapely.geometry.Polygon  (for pydaymet)
    affine     : rasterio.transform.Affine
    """
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    transform = meta["transform"]
    height = int(meta["height"])
    width = int(meta["width"])

    ox, sx = transform[2], transform[0]
    oy, sy = transform[5], transform[4]

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

    log.info("Grid: %sx%s, EPSG:5070 bbox %s", height, width, tuple(round(v) for v in bbox_5070))
    return transform, height, width, bbox_5070, bbox_wgs84, geom_wgs84, affine


def pixels_to_df(height: int, width: int) -> pd.DataFrame:
    """Build a DataFrame with (iy, ix) for all H×W pixels."""
    iy, ix = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")
    return pd.DataFrame({"iy": iy.ravel().astype("int32"), "ix": ix.ravel().astype("int32")})


# ---------------------------------------------------------------------------
# Section 1: gSSURGO soil
# ---------------------------------------------------------------------------


def _wcs_mukey_request(bbox_5070, width_px, height_px):
    """Single WCS GetCoverage request. Returns raw GeoTIFF bytes.

    Note: As of 2026 this endpoint often returns HTTP 404 (WCS retired). Prefer
    ``--soil-mukey-geotiff`` with a local MapunitRaster, or ``--skip-soil``.
    """
    west, south, east, north = bbox_5070
    url = (
        "https://sdmdataaccess.sc.egov.usda.gov/Spatial/SDM.wcs"
        "?SERVICE=WCS&VERSION=1.0.0&REQUEST=GetCoverage"
        "&COVERAGE=MapunitRaster_30m"
        "&CRS=EPSG:5070"
        f"&BBOX={west},{south},{east},{north}"
        f"&WIDTH={width_px}&HEIGHT={height_px}"
        "&FORMAT=GeoTIFF_Float"
    )
    log.info("WCS request: %sx%s px", width_px, height_px)
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content


def _fetch_mukey_tiled(bbox_5070, raw_tif_path: Path):
    """Download MUKEY raster in 2×2 tiles and stitch into one GeoTIFF."""
    west, south, east, north = bbox_5070
    mid_x = (west + east) / 2
    mid_y = (south + north) / 2

    quadrants = [
        (west, mid_y, mid_x, north),
        (mid_x, mid_y, east, north),
        (west, south, mid_x, mid_y),
        (mid_x, south, east, mid_y),
    ]

    w30_full = int(round((east - west) / 30))
    h30_full = int(round((north - south) / 30))
    full_arr = np.zeros((h30_full, w30_full), dtype="float32")
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
        "dtype": "float32",
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


def _fetch_mukey_raster(bbox_5070, affine, height, width, raw_tif_path: Path):
    """
    Download 30m MUKEY raster (tiles if needed), resample to 320m via majority.
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
            log.warning("Single WCS request failed (%s), falling back to 2x2 tiling", e)
            _fetch_mukey_tiled(bbox_5070, raw_tif_path)
    else:
        log.info("Raw MUKEY raster found at %s, skipping download", raw_tif_path)

    dst_array = np.empty((height, width), dtype="float32")
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
    return dst_array.astype("int32")


def _reproject_mukey_geotiff(src_path: Path, affine, height: int, width: int) -> np.ndarray:
    """Read a local MUKEY GeoTIFF (any CRS) and majority-resample to the study grid."""
    dst_array = np.empty((height, width), dtype="float32")
    with rasterio.open(src_path) as src:
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=dst_array,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=affine,
            dst_crs="EPSG:5070",
            resampling=Resampling.mode,
        )
    return dst_array.astype("int32")


def _sda_query_json(sql: str) -> list:
    r = requests.post(SDA_POST_URL, data={"format": "JSON", "query": sql}, timeout=180)
    r.raise_for_status()
    if r.text.lstrip().startswith("<?xml"):
        raise RuntimeError(f"SDA returned XML (query error): {r.text[:500]}")
    return r.json().get("Table", [])


def _aggregate_chorizon_to_mukey(ch_df: pd.DataFrame) -> pd.DataFrame:
    """0–150 cm thickness-weighted clay; AWC summed as mm water (awc_r × thickness(cm) × 10)."""

    def _one_mukey(grp: pd.DataFrame) -> pd.Series:
        top, bot = 0.0, 150.0
        awc_mm = 0.0
        awc_any = False
        clay_w = 0.0
        clay_t = 0.0
        for _, r in grp.iterrows():
            d0 = float(r["hzdept_r"])
            d1 = float(r["hzdepb_r"])
            c0 = max(d0, top)
            c1 = min(d1, bot)
            if c1 <= c0:
                continue
            th = c1 - c0
            awc_r = r["awc_r"]
            clay = r["claytotal_r"]
            if pd.notna(awc_r):
                awc_mm += float(awc_r) * th * 10.0
                awc_any = True
            if pd.notna(clay):
                clay_w += float(clay) * th
                clay_t += th
        return pd.Series(
            {
                "soil_awc_150cm": np.float32(awc_mm) if awc_any else np.nan,
                "soil_clay_pct": np.float32(clay_w / clay_t) if clay_t > 0 else np.nan,
            }
        )

    if ch_df.empty:
        return pd.DataFrame(columns=["mukey", "soil_awc_150cm", "soil_clay_pct"])
    gcols = ["hzdept_r", "hzdepb_r", "claytotal_r", "awc_r"]
    out = ch_df.groupby("mukey", sort=False)[gcols].apply(_one_mukey)
    return out.reset_index()


def _fetch_soil_attributes(mukeys) -> pd.DataFrame:
    """
    Query USDA SDA for mapunit-level soil attributes (muaggatt + dominant component + chorizon).

    ``soil_soc_150`` is not computed here (would need bulk-density–weighted SOC); left NaN in output.
    """
    mukey_list = sorted({int(k) for k in mukeys if k and int(k) > 0})
    if not mukey_list:
        return pd.DataFrame()

    chunk_size = 400
    n_chunks = max(1, (len(mukey_list) + chunk_size - 1) // chunk_size)
    agg_parts: list[pd.DataFrame] = []
    meta_parts: list[pd.DataFrame] = []

    for i in range(0, len(mukey_list), chunk_size):
        chunk = mukey_list[i : i + chunk_size]
        in_list = ",".join(str(k) for k in chunk)
        log.info("  SDA soil chunk %s/%s (%s mukeys)", i // chunk_size + 1, n_chunks, len(chunk))

        sql_meta = (
            f"SELECT mukey, drclassdcd, hydgrpdcd FROM muaggatt WHERE mukey IN ({in_list})"
        )
        table_m = _sda_query_json(sql_meta)
        if table_m:
            mdf = pd.DataFrame(table_m, columns=["mukey", "drclassdcd", "hydgrpdcd"])
            mdf["mukey"] = pd.to_numeric(mdf["mukey"], errors="coerce").astype("int32")
            meta_parts.append(mdf)

        sql_ch = (
            "SELECT c.mukey, ch.hzdept_r, ch.hzdepb_r, ch.claytotal_r, ch.awc_r "
            "FROM component c INNER JOIN chorizon ch ON c.cokey = ch.cokey "
            f"WHERE c.majcompflag = 'Yes' AND c.mukey IN ({in_list})"
        )
        table_c = _sda_query_json(sql_ch)
        if table_c:
            ch_df = pd.DataFrame(
                table_c, columns=["mukey", "hzdept_r", "hzdepb_r", "claytotal_r", "awc_r"]
            )
            ch_df["mukey"] = pd.to_numeric(ch_df["mukey"], errors="coerce").astype("int32")
            for col in ["hzdept_r", "hzdepb_r", "claytotal_r", "awc_r"]:
                ch_df[col] = pd.to_numeric(ch_df[col], errors="coerce")
            agg_parts.append(_aggregate_chorizon_to_mukey(ch_df))

    meta = pd.concat(meta_parts, ignore_index=True) if meta_parts else pd.DataFrame()
    agg = pd.concat(agg_parts, ignore_index=True) if agg_parts else pd.DataFrame()

    if meta.empty and agg.empty:
        return pd.DataFrame()

    if meta.empty:
        base = agg.copy()
        base["drclassdcd"] = np.nan
        base["hydgrpdcd"] = np.nan
    elif agg.empty:
        base = meta.copy()
        base["soil_awc_150cm"] = np.nan
        base["soil_clay_pct"] = np.nan
    else:
        base = meta.merge(agg, on="mukey", how="outer")

    base["mukey"] = pd.to_numeric(base["mukey"], errors="coerce").astype("int32")
    base["soil_drainage_class"] = base["drclassdcd"].map(DRAINAGE_ORDER).astype("float32")

    hg = base["hydgrpdcd"].astype(str).str.strip().str.upper().str[0]
    base["_hg"] = hg.where(hg.isin(["A", "B", "C", "D"]), "")
    for code in ["A", "B", "C", "D"]:
        base[f"soil_hydgrp_{code}"] = (base["_hg"] == code).astype("float32")
    base.drop(columns=["_hg"], inplace=True, errors="ignore")

    if "soil_awc_150cm" not in base.columns:
        base["soil_awc_150cm"] = np.nan
    if "soil_clay_pct" not in base.columns:
        base["soil_clay_pct"] = np.nan
    base["soil_awc_150cm"] = base["soil_awc_150cm"].astype("float32")
    base["soil_clay_pct"] = base["soil_clay_pct"].astype("float32")
    base["soil_soc_150"] = np.float32(np.nan)

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
    return base[keep].drop_duplicates("mukey")


def fetch_ssurgo_soil(
    bbox_5070,
    affine,
    height,
    width,
    out_dir: Path,
    mukey_geotiff: Path | None = None,
):
    """Download gSSURGO MUKEY raster, resample to 320m, join tabular attributes, save parquet."""
    out_path = out_dir / "soil_features.parquet"
    if out_path.exists():
        log.info("soil_features.parquet already exists, skipping")
        return

    log.info("=== gSSURGO soil features ===")
    raw_tif = out_dir / "_cache" / "ssurgo_mukey_30m.tif"
    if mukey_geotiff is not None and Path(mukey_geotiff).is_file():
        log.info("Using local MUKEY GeoTIFF: %s", mukey_geotiff)
        mukey_arr = _reproject_mukey_geotiff(Path(mukey_geotiff), affine, height, width)
    else:
        mukey_arr = _fetch_mukey_raster(bbox_5070, affine, height, width, raw_tif)

    unique_mukeys = np.unique(mukey_arr)
    log.info("Unique MUKEYs: %s", len(unique_mukeys))
    attr_df = _fetch_soil_attributes(unique_mukeys)

    if attr_df.empty:
        log.warning("No soil attributes returned from SDA — soil columns will be null")
        attr_df = pd.DataFrame(
            columns=[
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
        )

    pixels = pixels_to_df(height, width)
    pixels["mukey"] = mukey_arr.ravel()
    result = pixels.merge(attr_df, on="mukey", how="left").drop(columns=["mukey"])

    result.to_parquet(out_path, engine="pyarrow", compression="zstd", index=False)
    log.info("Saved: %s shape=%s", out_path, result.shape)


# ---------------------------------------------------------------------------
# Section 2: Daymet V4 climate
# ---------------------------------------------------------------------------


def fetch_daymet_climate(bbox_wgs84, geom_wgs84, affine, height, width, years, out_dir: Path):
    """
    Download per-year Daymet V4 data, compute GDD/precip/temp features,
    reproject to EPSG:5070 at 320m, save one parquet per year.
    Skips years where output already exists (resume-safe).
    """
    if not HAS_PYDAYMET:
        log.error("pydaymet not installed -- skipping Daymet. pip install pydaymet")
        return

    try:
        import certifi

        ca = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)
    except ImportError:
        pass

    import pydaymet as daymet
    import rioxarray  # noqa: F401  # needed for .rio accessor

    log.info("=== Daymet V4 climate features ===")

    def _reproject_da(da, ds_crs):
        da = da.rio.write_crs(ds_crs)
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

    for year in years:
        out_path = out_dir / f"daymet_features_{year}.parquet"
        if out_path.exists():
            log.info("  %s: already exists, skipping", year)
            continue

        log.info("  Downloading Daymet %s...", year)
        try:
            ds = daymet.get_bygeom(
                geom_wgs84,
                (f"{year}-01-01", f"{year}-12-31"),
                variables=["tmax", "tmin", "prcp"],
                crs="EPSG:4326",
            )
        except Exception as e:
            log.error("  Daymet %s failed: %s", year, e)
            continue

        times = pd.to_datetime(ds.time.values)
        doy = times.dayofyear
        crs = ds.rio.crs or "EPSG:4326"

        gs_mask = (doy >= 100) & (doy <= 280)
        tmean = (ds["tmax"].isel(time=gs_mask) + ds["tmin"].isel(time=gs_mask)) / 2
        gdd_da = (tmean - 10).clip(min=0).sum("time")

        spr_mask = (doy >= 91) & (doy <= 151)
        prcp_spr = ds["prcp"].isel(time=spr_mask).sum("time")

        gs_p_mask = (doy >= 121) & (doy <= 273)
        prcp_gs = ds["prcp"].isel(time=gs_p_mask).sum("time")

        jul_mask = (doy >= 182) & (doy <= 212)
        tmax_july = ds["tmax"].isel(time=jul_mask).mean("time")

        pixels = pixels_to_df(height, width)
        pixels["daymet_gdd"] = _reproject_da(gdd_da, crs)
        pixels["daymet_prcp_spring"] = _reproject_da(prcp_spr, crs)
        pixels["daymet_prcp_gs"] = _reproject_da(prcp_gs, crs)
        pixels["daymet_tmax_july"] = _reproject_da(tmax_july, crs)

        pixels.to_parquet(out_path, engine="pyarrow", compression="zstd", index=False)
        log.info("  Saved: %s", out_path)
        del ds, gdd_da, prcp_spr, prcp_gs, tmax_july


# ---------------------------------------------------------------------------
# Section 3: 3DEP terrain
# ---------------------------------------------------------------------------


def fetch_3dep_terrain(bbox_5070, affine, height, width, out_dir: Path):
    """Download DEM + slope + aspect at 30m, derive terrain features, resample to 320m."""
    if not HAS_PY3DEP:
        log.error("py3dep not installed -- skipping terrain. pip install py3dep")
        return

    import py3dep
    import rioxarray  # noqa: F401

    out_path = out_dir / "terrain_features.parquet"
    if out_path.exists():
        log.info("terrain_features.parquet already exists, skipping")
        return

    log.info("=== 3DEP terrain features ===")
    west, south, east, north = bbox_5070
    bbox_tuple = (west, south, east, north)
    # BBox is already EPSG:5070; py3dep defaults geo_crs=4326, which corrupts the footprint.
    _g5070 = "EPSG:5070"

    dem = py3dep.get_map("DEM", bbox_tuple, resolution=30, geo_crs=_g5070, crs=_g5070)
    slope = py3dep.get_map("Slope Degrees", bbox_tuple, resolution=30, geo_crs=_g5070, crs=_g5070)
    aspect = py3dep.get_map("Aspect Degrees", bbox_tuple, resolution=30, geo_crs=_g5070, crs=_g5070)

    northness_da = aspect.copy(data=np.cos(np.deg2rad(aspect.values)).astype("float32"))
    flat_da = slope.copy(data=(slope.values < 1.0).astype("float32"))

    def _reproject_da(da, method=Resampling.bilinear):
        da = da.rio.write_crs("EPSG:5070")
        return (
            da.rio.reproject(
                "EPSG:5070",
                shape=(height, width),
                transform=affine,
                resampling=method,
                nodata=np.nan,
            )
            .values.ravel()
            .astype("float32")
        )

    pixels = pixels_to_df(height, width)
    pixels["terrain_elevation"] = _reproject_da(dem)
    pixels["terrain_slope"] = _reproject_da(slope)
    pixels["terrain_northness"] = _reproject_da(northness_da)
    pixels["terrain_flat"] = _reproject_da(flat_da, method=Resampling.average)

    pixels.to_parquet(out_path, engine="pyarrow", compression="zstd", index=False)
    log.info("Saved: %s  shape=%s", out_path, pixels.shape)


# ---------------------------------------------------------------------------
# Section 4: CSB field boundaries (optional Tier 2)
# ---------------------------------------------------------------------------

# National CSB is large (~3.5 GB); cached under ``data/processed/task4/_cache/csb/`` after first run.
CSB_DEFAULT_URL = (
    "https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/datasets/"
    "NationalCSB_2016-2023_rev23.zip"
)


def fetch_csb_boundaries(
    bbox_5070,
    affine,
    height,
    width,
    out_dir: Path,
    csb_zip_url: str = CSB_DEFAULT_URL,
):
    """Download CSB shapefile ZIP, clip to study area, rasterize field IDs, save parquet."""
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
        log.info("Downloading CSB ZIP (may be multi-GB; cached locally) from %s ...", csb_zip_url)
        with requests.get(csb_zip_url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(cache_dir)

    shp_files = list(cache_dir.glob("**/*.shp"))
    if not shp_files:
        log.error("No .shp found in CSB ZIP")
        return

    csb = gpd.read_file(shp_files[0]).to_crs("EPSG:5070")
    west, south, east, north = bbox_5070
    csb = csb.cx[west:east, south:north].reset_index(drop=True)
    log.info("CSB polygons in study area: %s", len(csb))

    csb["_fid"] = (csb.index + 1).astype("int32")
    csb["csb_field_area_ha"] = (csb.geometry.area / 10_000).astype("float32")

    crop_col = next(
        (c for c in ["CROPTYPE", "DomCrop", "DOMCROP", "cdl_mode", "CDL_MODE"] if c in csb.columns),
        None,
    )
    if crop_col:
        csb["csb_dominant_crop"] = pd.to_numeric(csb[crop_col], errors="coerce").fillna(-1).astype("int16")
    else:
        csb["csb_dominant_crop"] = np.int16(-1)

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
    log.info("Saved: %s  shape=%s", out_path, result.shape)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    p = argparse.ArgumentParser(description="Download and preprocess external features for Task 4 crop mapping.")
    p.add_argument("--soil", action="store_true", help="Fetch gSSURGO soil features")
    p.add_argument(
        "--skip-soil",
        action="store_true",
        help="Skip gSSURGO (WCS often unavailable; use --soil-mukey-geotiff or prep soil separately)",
    )
    p.add_argument(
        "--soil-mukey-geotiff",
        type=Path,
        default=None,
        help="Local MapunitRaster / MUKEY GeoTIFF to reproject (avoids WCS)",
    )
    p.add_argument("--daymet", action="store_true", help="Fetch Daymet V4 climate features")
    p.add_argument("--terrain", action="store_true", help="Fetch 3DEP terrain features")
    p.add_argument("--csb", action="store_true", help="Fetch CSB field boundaries (optional)")
    p.add_argument(
        "--csb-zip-url",
        type=str,
        default=CSB_DEFAULT_URL,
        help="NASS Crop Sequence Boundaries ZIP URL (default: national 2016–2023, multi-GB)",
    )
    p.add_argument("--all", action="store_true", help="Run all fetchers")
    p.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=DAYMET_YEARS,
        help="Years for Daymet download (default: 2013-2023)",
    )
    return p.parse_args()


def main():
    if not META_PATH.is_file():
        log.error("Missing %s — run CDL parquet + metadata first", META_PATH)
        sys.exit(1)
    args = parse_args()
    if args.skip_soil and args.soil:
        log.error("Use either --soil or --skip-soil, not both")
        sys.exit(1)
    if not (args.all or args.soil or args.daymet or args.terrain or args.csb):
        log.error("Specify --all or one of --soil --daymet --terrain --csb")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    transform, height, width, bbox_5070, bbox_wgs84, geom_wgs84, affine = load_grid_meta()

    run_all = args.all
    failures: list[str] = []

    def _try(step: str, fn, *a, **kw) -> None:
        try:
            fn(*a, **kw)
        except Exception:
            log.exception("%s failed", step)
            failures.append(step)
            if not run_all:
                raise

    if (run_all or args.soil) and not args.skip_soil:
        _try(
            "gSSURGO soil",
            fetch_ssurgo_soil,
            bbox_5070,
            affine,
            height,
            width,
            OUT_DIR,
            mukey_geotiff=args.soil_mukey_geotiff,
        )
    elif args.skip_soil and run_all:
        log.warning("Skipping gSSURGO soil (--skip-soil). Tabular join will not be available until soil is built.")
    if run_all or args.daymet:
        _try(
            "Daymet",
            fetch_daymet_climate,
            bbox_wgs84,
            geom_wgs84,
            affine,
            height,
            width,
            args.years,
            OUT_DIR,
        )
    if run_all or args.terrain:
        _try("3DEP terrain", fetch_3dep_terrain, bbox_5070, affine, height, width, OUT_DIR)
    if run_all or args.csb:
        _try(
            "CSB boundaries",
            fetch_csb_boundaries,
            bbox_5070,
            affine,
            height,
            width,
            OUT_DIR,
            csb_zip_url=args.csb_zip_url,
        )

    if failures:
        log.error("Finished with failures: %s", ", ".join(failures))
        sys.exit(1)
    log.info("Done.")


if __name__ == "__main__":
    main()
