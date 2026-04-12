"""
Export geospatial data to Parquet under data/processed/.

Supports two sources:
  --source interim   Read pre-built NetCDF from data/interim/ (original flow).
  --source wms       Download directly from CropSmart / CropScape WMS endpoints.
                     Uses ``study_area.states`` from ``configs/task1_ndvi_analysis.yaml``
                     to union a WMS bbox in EPSG:5070 (same 13-state Corn Belt list as
                     ``study_extent.yaml`` / ``task2_crop_rotation.yaml`` — keep them aligned).
                     No local NetCDF required.

Output layout (identical for both sources):
  CDL:  data/processed/cdl/cdl_stack_wide.parquet   (iy, ix, cdl_2008, …)
  NDVI: data/processed/ndvi/ndvi_weekly_{year}_wide.parquet  (iy, ix, w000, …)
  SMAP: data/processed/smap/smap_weekly_{year}_wide.parquet

Usage — WMS (recommended, no interim data needed):
  python scripts/process_interim_to_parquet.py --dataset cdl  --source wms
  python scripts/process_interim_to_parquet.py --dataset cdl  --source wms --years 2018-2022
  python scripts/process_interim_to_parquet.py --dataset ndvi --source wms
  python scripts/process_interim_to_parquet.py --dataset ndvi --source wms --year 2022

Usage — interim NetCDF (legacy):
  python scripts/process_interim_to_parquet.py --dataset cdl
  python scripts/process_interim_to_parquet.py --dataset ndvi --year 2013
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

INTERIM = REPO_ROOT / "data" / "interim"
INTERIM_CDL = INTERIM / "cdl"
INTERIM_NDVI = INTERIM / "ndvi"
INTERIM_SMAP = INTERIM / "smap"
PROCESSED_CDL = REPO_ROOT / "data" / "processed" / "cdl"
PROCESSED_NDVI = REPO_ROOT / "data" / "processed" / "ndvi"
PROCESSED_SMAP = REPO_ROOT / "data" / "processed" / "smap"

# ── WMS endpoints (parsed from capabilities in data/external/) ────────────────
CDL_WMS_URL = "https://crop.csiss.gmu.edu/cgi-bin/wms_cdlall?"
NDVI_WMS_URL_TPL = (
    "https://nassgeo.csiss.gmu.edu/cgi-bin/mapserv?"
    "map=/DATA/SMAP_DATA/WMS/NDVI-WEEKLY_{year}.map"
)

# Approximate state bounding boxes (lon_min, lat_min, lon_max, lat_max) for
# computing the study-area extent in EPSG:5070 without needing shapefiles.
_STATE_BOUNDS_4326: dict[str, tuple[float, float, float, float]] = {
    "Iowa":         (-96.64, 40.38, -90.14, 43.50),
    "Nebraska":     (-104.05, 39.99, -95.31, 43.00),
    "Illinois":     (-91.51, 36.97, -87.02, 42.51),
    "Indiana":      (-88.10, 37.77, -84.78, 41.76),
    "Ohio":         (-84.82, 38.40, -80.52, 42.32),
    "Minnesota":    (-97.24, 43.50, -89.49, 49.38),
    "Missouri":     (-95.77, 35.99, -89.10, 40.61),
    "South Dakota": (-104.06, 42.48, -96.44, 45.95),
    "Wisconsin":    (-92.89, 42.49, -86.25, 47.08),
    "Kansas":       (-102.05, 36.99, -94.59, 40.00),
    "North Dakota": (-104.05, 45.94, -96.55, 49.00),
    "Kentucky":     (-89.57, 36.50, -81.96, 39.15),
    "Michigan":     (-90.42, 41.70, -82.12, 48.31),
}


def _default_cdl_stack_path() -> Path:
    cands = sorted(INTERIM_CDL.glob("cdl_stack_*.nc"))
    if not cands:
        # Legacy location (repo root under data/interim/)
        cands = sorted(INTERIM.glob("cdl_stack_*.nc"))
    if not cands:
        raise FileNotFoundError(
            f"No cdl_stack_*.nc under {INTERIM_CDL} (or legacy {INTERIM})"
        )
    return cands[-1]


def process_cdl(interim_nc: Path, chunk_y: int = 200) -> None:
    import rioxarray  # noqa: F401 — .rio on DataArray
    import xarray as xr

    interim_nc = Path(interim_nc).resolve()
    if not interim_nc.is_file():
        raise FileNotFoundError(interim_nc)

    PROCESSED_CDL.mkdir(parents=True, exist_ok=True)

    ds = xr.open_dataset(interim_nc, engine="netcdf4")
    if "cdl" in ds:
        da = ds["cdl"]
    else:
        names = list(ds.data_vars)
        if not names:
            raise ValueError(f"No data variables in {interim_nc}")
        da = ds[names[0]]

    for extra in ("band",):
        if extra in da.dims and da.sizes.get(extra, 0) == 1:
            da = da.squeeze(drop=True)

    if not {"year", "y", "x"} <= set(da.dims):
        raise ValueError(f"Expected dims year, y, x; got {tuple(da.dims)}")
    da = da.transpose("year", "y", "x")

    years = np.asarray(da["year"].values, dtype=int)
    ny, nx = int(da.sizes["y"]), int(da.sizes["x"])
    n_year = len(years)

    meta: dict = {
        "source_nc": str(interim_nc.relative_to(REPO_ROOT)),
        "height": ny,
        "width": nx,
        "years": years.tolist(),
    }
    try:
        meta["crs"] = str(da.rio.crs) if da.rio.crs is not None else None
        meta["transform"] = [float(x) for x in da.rio.transform()]
    except Exception:
        meta["crs"] = None
        meta["transform"] = None

    meta_path = PROCESSED_CDL / "cdl_stack_spatial_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[OK] Wrote {meta_path.relative_to(REPO_ROOT)}")

    parts: list[pd.DataFrame] = []
    for y0 in range(0, ny, chunk_y):
        y1 = min(y0 + chunk_y, ny)
        sub = da.isel(y=slice(y0, y1)).load()
        vals = np.asarray(sub.values, dtype=np.int32)
        if vals.shape != (n_year, y1 - y0, nx):
            vals = vals.reshape(n_year, y1 - y0, nx)
        hh = y1 - y0
        flat = vals.reshape(n_year, hh * nx).T
        iy = np.repeat(np.arange(y0, y1, dtype=np.int32), nx)
        ix = np.tile(np.arange(nx, dtype=np.int32), hh)
        cols: dict[str, np.ndarray] = {"iy": iy, "ix": ix}
        for i, yr in enumerate(years):
            cols[f"cdl_{int(yr)}"] = flat[:, i]
        parts.append(pd.DataFrame(cols))

    df = pd.concat(parts, ignore_index=True)
    ds.close()

    out_parquet = PROCESSED_CDL / "cdl_stack_wide.parquet"
    df.to_parquet(out_parquet, index=False, engine="pyarrow", compression="zstd")
    print(f"[OK] Wrote {out_parquet.relative_to(REPO_ROOT)}  rows={len(df):,}  cols={len(df.columns)}")


def _list_ndvi_interim_nc() -> list[Path]:
    cands = sorted(INTERIM_NDVI.glob("ndvi_weekly_*.nc"))
    if not cands:
        cands = sorted(INTERIM.glob("ndvi_weekly_*.nc"))
    return cands


def _year_from_ndvi_nc(path: Path) -> int:
    m = re.match(r"ndvi_weekly_(\d{4})\.nc$", path.name)
    if not m:
        raise ValueError(f"Unexpected NDVI interim filename: {path.name}")
    return int(m.group(1))


def process_ndvi_year(interim_nc: Path, chunk_y: int = 200) -> None:
    import rioxarray  # noqa: F401
    import xarray as xr

    interim_nc = Path(interim_nc).resolve()
    if not interim_nc.is_file():
        raise FileNotFoundError(interim_nc)

    year = _year_from_ndvi_nc(interim_nc)
    PROCESSED_NDVI.mkdir(parents=True, exist_ok=True)

    ds = xr.open_dataset(interim_nc, engine="netcdf4")
    if "ndvi" in ds:
        da = ds["ndvi"]
    else:
        names = list(ds.data_vars)
        if not names:
            raise ValueError(f"No data variables in {interim_nc}")
        da = ds[names[0]]

    for extra in ("band",):
        if extra in da.dims and da.sizes.get(extra, 0) == 1:
            da = da.squeeze(drop=True)

    if not {"time", "y", "x"} <= set(da.dims):
        raise ValueError(f"Expected dims time, y, x; got {tuple(da.dims)}")
    da = da.transpose("time", "y", "x")

    times = [str(pd.Timestamp(t).date()) for t in np.asarray(da["time"].values)]
    nt = int(da.sizes["time"])
    ny, nx = int(da.sizes["y"]), int(da.sizes["x"])

    meta: dict = {
        "source_nc": str(interim_nc.relative_to(REPO_ROOT)),
        "year": year,
        "height": ny,
        "width": nx,
        "n_time": nt,
        "time_start_day": times,
        "wide_columns": ["iy", "ix"] + [f"w{i:03d}" for i in range(nt)],
        "note": "w000.. are weekly NDVI layers in the same order as time_start_day.",
    }
    try:
        meta["crs"] = str(da.rio.crs) if da.rio.crs is not None else None
        meta["transform"] = [float(x) for x in da.rio.transform()]
    except Exception:
        meta["crs"] = None
        meta["transform"] = None

    meta_path = PROCESSED_NDVI / f"ndvi_weekly_{year}_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[OK] Wrote {meta_path.relative_to(REPO_ROOT)}")

    parts: list[pd.DataFrame] = []
    for y0 in range(0, ny, chunk_y):
        y1 = min(y0 + chunk_y, ny)
        sub = da.isel(y=slice(y0, y1)).load()
        vals = np.asarray(sub.values, dtype=np.float32)
        if vals.shape != (nt, y1 - y0, nx):
            vals = vals.reshape(nt, y1 - y0, nx)
        hh = y1 - y0
        flat = vals.reshape(nt, hh * nx).T
        iy = np.repeat(np.arange(y0, y1, dtype=np.int32), nx)
        ix = np.tile(np.arange(nx, dtype=np.int32), hh)
        cols: dict[str, np.ndarray] = {"iy": iy, "ix": ix}
        for i in range(nt):
            cols[f"w{i:03d}"] = flat[:, i]
        parts.append(pd.DataFrame(cols))

    df = pd.concat(parts, ignore_index=True)
    ds.close()

    out_parquet = PROCESSED_NDVI / f"ndvi_weekly_{year}_wide.parquet"
    df.to_parquet(out_parquet, index=False, engine="pyarrow", compression="zstd")
    print(f"[OK] Wrote {out_parquet.relative_to(REPO_ROOT)}  rows={len(df):,}  cols={len(df.columns)}")


def process_ndvi_all(chunk_y: int, year: int | None, interim_one: Path | None) -> None:
    if interim_one is not None:
        paths = [Path(interim_one).resolve()]
        if not paths[0].is_file():
            raise FileNotFoundError(paths[0])
    else:
        paths = _list_ndvi_interim_nc()
        if year is not None:
            paths = [p for p in paths if _year_from_ndvi_nc(p) == year]
    if not paths:
        raise FileNotFoundError(
            f"No ndvi_weekly_*.nc under {INTERIM_NDVI} (or legacy {INTERIM})"
        )
    for p in paths:
        process_ndvi_year(p, chunk_y=chunk_y)


def _list_smap_interim_nc() -> list[Path]:
    cands = sorted(INTERIM_SMAP.glob("smap_weekly_*.nc"))
    if not cands:
        cands = sorted(INTERIM.glob("smap_weekly_*.nc"))
    return cands


def _year_from_smap_nc(path: Path) -> int:
    m = re.match(r"smap_weekly_(\d{4})\.nc$", path.name)
    if not m:
        raise ValueError(f"Unexpected SMAP interim filename: {path.name}")
    return int(m.group(1))


def process_smap_year(interim_nc: Path, chunk_y: int = 200) -> None:
    import rioxarray  # noqa: F401
    import xarray as xr

    interim_nc = Path(interim_nc).resolve()
    if not interim_nc.is_file():
        raise FileNotFoundError(interim_nc)

    year = _year_from_smap_nc(interim_nc)
    PROCESSED_SMAP.mkdir(parents=True, exist_ok=True)

    ds = xr.open_dataset(interim_nc, engine="netcdf4")
    if "sm_surface" in ds:
        da = ds["sm_surface"]
    elif "smap" in ds:
        da = ds["smap"]
    else:
        names = list(ds.data_vars)
        if not names:
            raise ValueError(f"No data variables in {interim_nc}")
        da = ds[names[0]]

    for extra in ("band",):
        if extra in da.dims and da.sizes.get(extra, 0) == 1:
            da = da.squeeze(drop=True)

    if not {"time", "y", "x"} <= set(da.dims):
        raise ValueError(f"Expected dims time, y, x; got {tuple(da.dims)}")
    da = da.transpose("time", "y", "x")

    times = [str(pd.Timestamp(t).date()) for t in np.asarray(da["time"].values)]
    nt = int(da.sizes["time"])
    ny, nx = int(da.sizes["y"]), int(da.sizes["x"])

    meta: dict = {
        "source_nc": str(interim_nc.relative_to(REPO_ROOT)),
        "year": year,
        "height": ny,
        "width": nx,
        "n_time": nt,
        "time_start_day": times,
        "wide_columns": ["iy", "ix"] + [f"w{i:03d}" for i in range(nt)],
        "note": "w000.. are weekly SMAP (AVERAGE) layers in the same order as time_start_day.",
    }
    try:
        meta["crs"] = str(da.rio.crs) if da.rio.crs is not None else None
        meta["transform"] = [float(x) for x in da.rio.transform()]
    except Exception:
        meta["crs"] = None
        meta["transform"] = None

    meta_path = PROCESSED_SMAP / f"smap_weekly_{year}_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[OK] Wrote {meta_path.relative_to(REPO_ROOT)}")

    parts: list[pd.DataFrame] = []
    for y0 in range(0, ny, chunk_y):
        y1 = min(y0 + chunk_y, ny)
        sub = da.isel(y=slice(y0, y1)).load()
        vals = np.asarray(sub.values, dtype=np.float32)
        if vals.shape != (nt, y1 - y0, nx):
            vals = vals.reshape(nt, y1 - y0, nx)
        hh = y1 - y0
        flat = vals.reshape(nt, hh * nx).T
        iy = np.repeat(np.arange(y0, y1, dtype=np.int32), nx)
        ix = np.tile(np.arange(nx, dtype=np.int32), hh)
        cols: dict[str, np.ndarray] = {"iy": iy, "ix": ix}
        for i in range(nt):
            cols[f"w{i:03d}"] = flat[:, i]
        parts.append(pd.DataFrame(cols))

    df = pd.concat(parts, ignore_index=True)
    ds.close()

    out_parquet = PROCESSED_SMAP / f"smap_weekly_{year}_wide.parquet"
    df.to_parquet(out_parquet, index=False, engine="pyarrow", compression="zstd")
    print(f"[OK] Wrote {out_parquet.relative_to(REPO_ROOT)}  rows={len(df):,}  cols={len(df.columns)}")


def process_smap_all(chunk_y: int, year: int | None, interim_one: Path | None) -> None:
    if interim_one is not None:
        paths = [Path(interim_one).resolve()]
        if not paths[0].is_file():
            raise FileNotFoundError(paths[0])
    else:
        paths = _list_smap_interim_nc()
        if year is not None:
            paths = [p for p in paths if _year_from_smap_nc(p) == year]
    if not paths:
        raise FileNotFoundError(
            f"No smap_weekly_*.nc under {INTERIM_SMAP} (or legacy {INTERIM})"
        )
    for p in paths:
        process_smap_year(p, chunk_y=chunk_y)


# ── WMS helpers ───────────────────────────────────────────────────────────────

def _load_cfg() -> dict:
    import yaml

    cfg_path = REPO_ROOT / "configs" / "task1_ndvi_analysis.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _bbox_5070_from_states(states: list[str]) -> tuple[float, float, float, float]:
    """Union bounding box of *states* projected to EPSG:5070 (CONUS Albers)."""
    from pyproj import Transformer

    unknown = [s for s in states if s not in _STATE_BOUNDS_4326]
    if unknown:
        raise ValueError(
            f"States not in lookup: {unknown}. "
            "Add entries to _STATE_BOUNDS_4326 or use --bbox."
        )
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    lons, lats = [], []
    for s in states:
        b = _STATE_BOUNDS_4326[s]
        lons.extend([b[0], b[2]])
        lats.extend([b[1], b[3]])
    corners_x, corners_y = transformer.transform(
        [min(lons), max(lons), min(lons), max(lons)],
        [min(lats), min(lats), max(lats), max(lats)],
    )
    return (min(corners_x), min(corners_y), max(corners_x), max(corners_y))


WMS_TILE_MAX = 4096  # max pixels per WMS request dimension


def _wms_get_tile(
    base_url: str,
    layer: str,
    bbox: tuple[float, float, float, float],
    width: int,
    height: int,
    version: str,
) -> np.ndarray:
    """Fetch one WMS tile, return the pixel array (bands, h, w)."""
    import requests
    import rasterio

    xmin, ymin, xmax, ymax = bbox
    params: dict[str, str] = {
        "SERVICE": "WMS",
        "VERSION": version,
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "FORMAT": "image/tiff",
        "STYLES": "",
    }
    if version.startswith("1.1"):
        params["SRS"] = "EPSG:5070"
    else:
        params["CRS"] = "EPSG:5070"

    resp = requests.get(base_url, params=params, timeout=300)
    resp.raise_for_status()
    ct = resp.headers.get("Content-Type", "")
    if "xml" in ct or b"ServiceException" in resp.content[:1000]:
        raise RuntimeError(f"WMS error for '{layer}': {resp.text[:500]}")

    with rasterio.io.MemoryFile(resp.content) as memf:
        with memf.open() as src:
            return src.read()


def _wms_get_map(
    base_url: str,
    layer: str,
    bbox_5070: tuple[float, float, float, float],
    width: int,
    height: int,
    version: str = "1.1.1",
) -> tuple[np.ndarray, list[float], str]:
    """Fetch a WMS layer, automatically tiling if it exceeds WMS_TILE_MAX."""
    from rasterio.transform import from_bounds

    xmin, ymin, xmax, ymax = bbox_5070

    if width <= WMS_TILE_MAX and height <= WMS_TILE_MAX:
        data = _wms_get_tile(base_url, layer, bbox_5070, width, height, version)
        t = from_bounds(xmin, ymin, xmax, ymax, width, height)
        return data, [float(v) for v in t], "EPSG:5070"

    nx_tiles = -(-width // WMS_TILE_MAX)   # ceil division
    ny_tiles = -(-height // WMS_TILE_MAX)

    result = None
    for ty in range(ny_tiles):
        row_parts = []
        py0 = ty * (height // ny_tiles)
        py1 = min(py0 + (height // ny_tiles) + (1 if ty == ny_tiles - 1 else 0),
                   height)
        tile_h = py1 - py0
        frac_y0 = py0 / height
        frac_y1 = py1 / height
        tile_ymax = ymax - frac_y0 * (ymax - ymin)
        tile_ymin = ymax - frac_y1 * (ymax - ymin)

        for tx in range(nx_tiles):
            px0 = tx * (width // nx_tiles)
            px1 = min(px0 + (width // nx_tiles) + (1 if tx == nx_tiles - 1 else 0),
                       width)
            tile_w = px1 - px0
            frac_x0 = px0 / width
            frac_x1 = px1 / width
            tile_xmin = xmin + frac_x0 * (xmax - xmin)
            tile_xmax = xmin + frac_x1 * (xmax - xmin)

            tile_bbox = (tile_xmin, tile_ymin, tile_xmax, tile_ymax)
            tile_data = _wms_get_tile(
                base_url, layer, tile_bbox, tile_w, tile_h, version,
            )
            row_parts.append(tile_data)

        row = np.concatenate(row_parts, axis=2)  # concat along x
        if result is None:
            result = row
        else:
            result = np.concatenate([result, row], axis=1)  # concat along y

    t = from_bounds(xmin, ymin, xmax, ymax, width, height)
    return result, [float(v) for v in t], "EPSG:5070"


def _discover_ndvi_layers(
    year: int, doy_range: tuple[int, int] | None = None,
) -> list[dict]:
    """Fetch NDVI WMS GetCapabilities for *year*, return weekly layer metadata."""
    import xml.etree.ElementTree as ET

    import requests

    base_url = NDVI_WMS_URL_TPL.format(year=year)
    resp = requests.get(
        base_url,
        params={"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetCapabilities"},
        timeout=60,
    )
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns = {"wms": "http://www.opengis.net/wms"}
    layers: list[dict] = []
    pattern = re.compile(rf"NDVI-WEEKLY_{year}_(\d+)_(\d{{4}}\.\d{{2}}\.\d{{2}})_")
    for el in root.iter("{http://www.opengis.net/wms}Name"):
        name = (el.text or "").strip()
        m = pattern.match(name)
        if not m:
            continue
        start_str = m.group(2).replace(".", "-")
        try:
            start_date = pd.Timestamp(start_str)
        except Exception:
            continue
        doy = start_date.day_of_year
        if doy_range and not (doy_range[0] <= doy <= doy_range[1]):
            continue
        layers.append({"name": name, "start_date": str(start_date.date()), "doy": doy})
    layers.sort(key=lambda l: l["doy"])
    return layers


# ── WMS → Parquet processors ─────────────────────────────────────────────────

WMS_MAX_PX = 8192
WMS_WORKERS = 6  # concurrent download threads


def _fit_resolution(bbox: tuple, resolution: float) -> tuple[int, int, float]:
    """Ensure pixel dims fit WMS max; bump resolution if needed."""
    xmin, ymin, xmax, ymax = bbox
    w = int(round((xmax - xmin) / resolution))
    h = int(round((ymax - ymin) / resolution))
    while w > WMS_MAX_PX or h > WMS_MAX_PX:
        resolution += 10
        w = int(round((xmax - xmin) / resolution))
        h = int(round((ymax - ymin) / resolution))
    return w, h, resolution


def process_cdl_wms(years: list[int], resolution: float = 250) -> None:
    cfg = _load_cfg()
    states = cfg.get("study_area", {}).get("states", ["Iowa", "Nebraska"])
    bbox = _bbox_5070_from_states(states)
    width, height, resolution = _fit_resolution(bbox, resolution)
    if resolution > 250:
        print(f"  (auto-adjusted resolution to {resolution}m to fit WMS {WMS_MAX_PX}px limit)")

    print(f"CDL WMS → Parquet")
    print(f"  states : {states}")
    print(f"  bbox   : {[round(v) for v in bbox]}  (EPSG:5070)")
    print(f"  grid   : {width} x {height}  ({resolution}m)")
    print(f"  years  : {years[0]}–{years[-1]} (n={len(years)})")

    PROCESSED_CDL.mkdir(parents=True, exist_ok=True)
    arrays: dict[int, np.ndarray] = {}
    transform_out: list[float] | None = None

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_cdl(yr: int):
        data, transform, _ = _wms_get_map(
            CDL_WMS_URL, f"cdl_{yr}", bbox, width, height, version="1.1.1",
        )
        return yr, np.asarray(data[0], dtype=np.int32), transform

    print(f"  downloading {len(years)} years ({WMS_WORKERS} threads) ...")
    with ThreadPoolExecutor(max_workers=WMS_WORKERS) as pool:
        futures = {pool.submit(_fetch_cdl, yr): yr for yr in years}
        for fut in as_completed(futures):
            yr = futures[fut]
            try:
                yr, arr, transform = fut.result()
                arrays[yr] = arr
                if transform_out is None:
                    transform_out = transform
                print(f"    CDL {yr}  OK  {arr.shape}")
            except Exception as exc:
                print(f"    CDL {yr}  FAILED  {exc}")

    if not arrays:
        raise RuntimeError("No CDL years downloaded. Check network / WMS availability.")

    ny, nx = next(iter(arrays.values())).shape
    iy = np.repeat(np.arange(ny, dtype=np.int32), nx)
    ix = np.tile(np.arange(nx, dtype=np.int32), ny)
    cols: dict[str, np.ndarray] = {"iy": iy, "ix": ix}
    for yr in sorted(arrays):
        cols[f"cdl_{yr}"] = arrays[yr].ravel()

    df = pd.DataFrame(cols)
    out_pq = PROCESSED_CDL / "cdl_stack_wide.parquet"
    df.to_parquet(out_pq, index=False, engine="pyarrow", compression="zstd")
    print(f"[OK] {out_pq.relative_to(REPO_ROOT)}  rows={len(df):,}  cols={len(df.columns)}")

    meta = {
        "source": "WMS",
        "wms_url": CDL_WMS_URL,
        "height": ny,
        "width": nx,
        "years": sorted(arrays),
        "crs": "EPSG:5070",
        "transform": transform_out,
        "states": states,
        "bbox_5070": list(bbox),
        "resolution_m": resolution,
    }
    meta_path = PROCESSED_CDL / "cdl_stack_spatial_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[OK] {meta_path.relative_to(REPO_ROOT)}")


def process_ndvi_wms(
    years: list[int], resolution: float = 250, single_year: int | None = None,
) -> None:
    cfg = _load_cfg()
    states = cfg.get("study_area", {}).get("states", ["Iowa", "Nebraska"])
    bbox = _bbox_5070_from_states(states)
    doy_range = tuple(cfg.get("ndvi", {}).get("growing_season_doy", [100, 310]))
    width, height, resolution = _fit_resolution(bbox, resolution)
    if resolution > 250:
        print(f"  (auto-adjusted resolution to {resolution}m to fit WMS {WMS_MAX_PX}px limit)")

    if single_year is not None:
        years = [single_year]

    print(f"NDVI WMS → Parquet")
    print(f"  states    : {states}")
    print(f"  bbox      : {[round(v) for v in bbox]}  (EPSG:5070)")
    print(f"  grid      : {width} x {height}  ({resolution}m)")
    print(f"  DOY range : {doy_range}")
    print(f"  years     : {years[0]}–{years[-1]} (n={len(years)})")

    PROCESSED_NDVI.mkdir(parents=True, exist_ok=True)

    for yr in years:
        print(f"\n── NDVI {yr} ──")
        base_url = NDVI_WMS_URL_TPL.format(year=yr)

        print("  discovering layers ...", end=" ", flush=True)
        try:
            layer_info = _discover_ndvi_layers(yr, doy_range=doy_range)
        except Exception as exc:
            print(f"FAILED  {exc}")
            continue
        print(f"found {len(layer_info)} weeks")

        if not layer_info:
            continue

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _fetch_ndvi(info: dict):
            data, transform, _ = _wms_get_map(
                base_url, info["name"], bbox, width, height, version="1.3.0",
            )
            return info, np.asarray(data[0], dtype=np.float32), transform

        print(f"  downloading {len(layer_info)} weeks ({WMS_WORKERS} threads) ...")
        fetched: dict[int, tuple[dict, np.ndarray, list]] = {}
        with ThreadPoolExecutor(max_workers=WMS_WORKERS) as pool:
            futs = {pool.submit(_fetch_ndvi, info): li
                    for li, info in enumerate(layer_info)}
            done_count = 0
            for fut in as_completed(futs):
                li = futs[fut]
                done_count += 1
                try:
                    info, arr, transform = fut.result()
                    fetched[li] = (info, arr, transform)
                    print(f"    [{done_count:>2}/{len(layer_info)}] "
                          f"{info['start_date']}  OK")
                except Exception as exc:
                    print(f"    [{done_count:>2}/{len(layer_info)}] "
                          f"week {li}  FAILED  {exc}")

        if not fetched:
            print(f"  no layers downloaded for {yr}, skipping")
            continue

        ordered = [fetched[i] for i in sorted(fetched)]
        weekly = [item[1] for item in ordered]
        times = [item[0]["start_date"] for item in ordered]
        transform_out: list[float] | None = ordered[0][2]

        ny, nx = weekly[0].shape
        nt = len(weekly)
        iy = np.repeat(np.arange(ny, dtype=np.int32), nx)
        ix = np.tile(np.arange(nx, dtype=np.int32), ny)
        cols: dict[str, np.ndarray] = {"iy": iy, "ix": ix}
        for i, arr in enumerate(weekly):
            cols[f"w{i:03d}"] = arr.ravel()

        df = pd.DataFrame(cols)
        out_pq = PROCESSED_NDVI / f"ndvi_weekly_{yr}_wide.parquet"
        df.to_parquet(out_pq, index=False, engine="pyarrow", compression="zstd")
        print(
            f"  [OK] {out_pq.relative_to(REPO_ROOT)}  "
            f"rows={len(df):,}  weeks={nt}"
        )

        meta = {
            "source": "WMS",
            "source_nc": f"WMS {base_url}",
            "year": yr,
            "height": ny,
            "width": nx,
            "n_time": nt,
            "time_start_day": times,
            "wide_columns": ["iy", "ix"] + [f"w{i:03d}" for i in range(nt)],
            "note": "w000.. are weekly NDVI layers in the same order as time_start_day.",
            "crs": "EPSG:5070",
            "transform": transform_out,
        }
        meta_path = PROCESSED_NDVI / f"ndvi_weekly_{yr}_metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"  [OK] {meta_path.relative_to(REPO_ROOT)}")


def _parse_years(raw: str) -> list[int]:
    """Parse '2008-2025' or '2018,2019,2020' into a sorted list of ints."""
    if "-" in raw and "," not in raw:
        lo, hi = raw.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return sorted(int(y.strip()) for y in raw.split(","))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Export data to Parquet under data/processed/. "
        "Default reads data/interim/ NetCDF built from data/raw/ by build_interim_data.py. "
        "Use --source wms only for direct WMS export (different grid than repo pipeline).",
    )
    parser.add_argument(
        "--dataset",
        choices=["cdl", "ndvi", "smap"],
        default="cdl",
        help="Which product to export.",
    )
    parser.add_argument(
        "--source",
        choices=["interim", "wms"],
        default="interim",
        help="'interim' (default): read NetCDF from data/interim/ (from raw GeoTIFFs). "
        "'wms': download from CropSmart / CropScape WMS (not the same as cornbelt raw stack).",
    )
    parser.add_argument(
        "--years",
        type=str,
        default=None,
        help="WMS mode: year range '2008-2025' or comma list '2018,2019'. "
        "Defaults to 2008-2025.",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=250.0,
        help="WMS mode: pixel size in metres (default 250).",
    )
    # Legacy interim-mode flags
    parser.add_argument("--interim", type=Path, default=None,
                        help="(interim mode) Path to one interim NetCDF.")
    parser.add_argument("--year", type=int, default=None,
                        help="(interim/wms) Export only this year.")
    parser.add_argument("--chunk-y", type=int, default=200,
                        help="(interim mode) Y-chunk size.")
    args = parser.parse_args()

    if args.source == "wms":
        if args.years:
            years = _parse_years(args.years)
        elif args.year:
            years = [args.year]
        else:
            years = list(range(2008, 2026))

        if args.dataset == "cdl":
            process_cdl_wms(years, resolution=args.resolution)
        elif args.dataset == "ndvi":
            process_ndvi_wms(years, resolution=args.resolution,
                             single_year=args.year)
        elif args.dataset == "smap":
            print("SMAP WMS download not yet implemented. Use --source interim.")
            sys.exit(1)
    else:
        if args.dataset == "cdl":
            nc = args.interim or _default_cdl_stack_path()
            process_cdl(nc, chunk_y=args.chunk_y)
        elif args.dataset == "ndvi":
            process_ndvi_all(chunk_y=args.chunk_y, year=args.year,
                             interim_one=args.interim)
        elif args.dataset == "smap":
            process_smap_all(chunk_y=args.chunk_y, year=args.year,
                             interim_one=args.interim)

    print("\nDone.")


if __name__ == "__main__":
    main()
