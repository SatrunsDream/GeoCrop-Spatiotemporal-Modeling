"""
Export interim NetCDF stacks to Parquet under data/processed/.

Interim layout (see build_interim_data.py):
  CDL:  data/interim/cdl/cdl_stack_{y0}_{y1}.nc
  NDVI: data/interim/ndvi/ndvi_weekly_{year}.nc
  SMAP: data/interim/smap/smap_weekly_{year}.nc

CDL (wide, one row per pixel):
  data/processed/cdl/cdl_stack_wide.parquet
  Columns: iy, ix, cdl_<year>, ...
  data/processed/cdl/cdl_stack_spatial_metadata.json

NDVI (wide, one row per pixel; one Parquet per calendar year):
  data/processed/ndvi/ndvi_weekly_{year}_wide.parquet
  Columns: iy, ix, w000, w001, ... (weekly time steps in calendar order; see metadata JSON)
  data/processed/ndvi/ndvi_weekly_{year}_metadata.json

SMAP (wide, one row per pixel; one Parquet per calendar year):
  data/processed/smap/smap_weekly_{year}_wide.parquet
  data/processed/smap/smap_weekly_{year}_metadata.json

Usage:
  python scripts/process_interim_to_parquet.py --dataset cdl
  python scripts/process_interim_to_parquet.py --dataset cdl --interim data/interim/cdl/cdl_stack_2008_2025.nc
  python scripts/process_interim_to_parquet.py --dataset ndvi
  python scripts/process_interim_to_parquet.py --dataset ndvi --year 2013
  python scripts/process_interim_to_parquet.py --dataset smap
  python scripts/process_interim_to_parquet.py --dataset smap --year 2020
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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="Interim NetCDF → Parquet (processed/).")
    parser.add_argument(
        "--dataset",
        choices=["cdl", "ndvi", "smap"],
        default="cdl",
        help="Which product to export.",
    )
    parser.add_argument(
        "--interim",
        type=Path,
        default=None,
        help=(
            "Path to one interim NetCDF. CDL: single stack file. "
            "NDVI: one ndvi_weekly_YEAR.nc. SMAP: one smap_weekly_YEAR.nc. "
            "If set, only that file is exported for NDVI/SMAP."
        ),
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="NDVI or SMAP: export only this year (ignored if --interim is set).",
    )
    parser.add_argument(
        "--chunk-y",
        type=int,
        default=200,
        help="Rows of y to load per chunk (CDL, NDVI, SMAP).",
    )
    args = parser.parse_args()

    if args.dataset == "cdl":
        nc = args.interim or _default_cdl_stack_path()
        process_cdl(nc, chunk_y=args.chunk_y)
    elif args.dataset == "ndvi":
        process_ndvi_all(chunk_y=args.chunk_y, year=args.year, interim_one=args.interim)
    elif args.dataset == "smap":
        process_smap_all(chunk_y=args.chunk_y, year=args.year, interim_one=args.interim)

    print("\nDone.")


if __name__ == "__main__":
    main()
