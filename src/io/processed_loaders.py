"""
Load CDL / NDVI / SMAP stacks from ``data/processed/{cdl,ndvi,smap}/`` wide Parquet.

Outputs match the spirit of ``interim_loaders`` (xarray stacks for notebooks) but
read **processed** tables produced by ``scripts/process_interim_to_parquet.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from src.io.interim_loaders import find_repo_root


def load_cdl_stack_wide_dataframe(repo_root: Path | None = None) -> pd.DataFrame:
    """Return ``cdl_stack_wide.parquet`` as a DataFrame (``iy``, ``ix``, ``cdl_*``)."""
    repo_root = repo_root or find_repo_root()
    pq = repo_root / "data" / "processed" / "cdl" / "cdl_stack_wide.parquet"
    if not pq.is_file():
        raise FileNotFoundError(
            f"Missing {pq}. Run: python scripts/process_interim_to_parquet.py --dataset cdl"
        )
    return pd.read_parquet(pq)


def load_cdl_stack_from_processed(repo_root: Path | None = None) -> xr.DataArray:
    """
    Reconstruct a (year, y, x) CDL stack from wide Parquet + spatial metadata JSON.

    Equivalent layout to ``load_cdl_stack_from_interim`` for downstream code.
    """
    repo_root = repo_root or find_repo_root()
    meta_path = repo_root / "data" / "processed" / "cdl" / "cdl_stack_spatial_metadata.json"
    if not meta_path.is_file():
        raise FileNotFoundError(
            f"Missing {meta_path}. Run: python scripts/process_interim_to_parquet.py --dataset cdl"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    ny, nx = int(meta["height"]), int(meta["width"])
    df = load_cdl_stack_wide_dataframe(repo_root)
    year_cols = sorted(
        [c for c in df.columns if c.startswith("cdl_")],
        key=lambda c: int(c.replace("cdl_", "")),
    )
    if not year_cols:
        raise ValueError("No cdl_<year> columns in CDL wide Parquet")
    years = [int(c.replace("cdl_", "")) for c in year_cols]
    n_year = len(years)
    arr = np.full((n_year, ny, nx), -1, dtype=np.int32)
    iy = df["iy"].to_numpy(dtype=np.intp)
    ix = df["ix"].to_numpy(dtype=np.intp)
    for i, col in enumerate(year_cols):
        arr[i, iy, ix] = df[col].to_numpy(dtype=np.int32)

    return xr.DataArray(
        arr,
        dims=("year", "y", "x"),
        coords={"year": years, "y": np.arange(ny), "x": np.arange(nx)},
        name="cdl",
        attrs={"source": "data/processed/cdl/cdl_stack_wide.parquet"},
    )


def _wide_weekly_parquet_to_3d(
    df: pd.DataFrame, meta: dict, dtype: type = np.float32
) -> np.ndarray:
    ny, nx = int(meta["height"]), int(meta["width"])
    wcols = sorted(
        [c for c in df.columns if c.startswith("w")],
        key=lambda x: int(x[1:]),
    )
    if not wcols:
        raise ValueError("No w* weekly columns in parquet")
    nt = len(wcols)
    arr = np.full((nt, ny, nx), np.nan, dtype=dtype)
    iy = df["iy"].to_numpy(dtype=np.intp)
    ix = df["ix"].to_numpy(dtype=np.intp)
    for ti, wc in enumerate(wcols):
        arr[ti, iy, ix] = df[wc].to_numpy(dtype=dtype)
    return arr


def _pad_time_to(arr: np.ndarray, target_nt: int) -> np.ndarray:
    nt, ny, nx = arr.shape
    if nt == target_nt:
        return arr
    if nt > target_nt:
        return arr[:target_nt]
    out = np.full((target_nt, ny, nx), np.nan, dtype=arr.dtype)
    out[:nt] = arr
    return out


def load_ndvi_weekly_all_years_processed(
    repo_root: Path | None = None,
) -> xr.DataArray:
    """
    Combine per-year ``ndvi_weekly_{year}_wide.parquet`` into one DataArray.

    Dims: ``calendar_year``, ``time``, ``y``, ``x``. Calendar years can have
    different true week counts; shorter years are **NaN-padded** along ``time``
    to a common length so stacks concatenate cleanly (fine for feature extraction).
    """
    repo_root = repo_root or find_repo_root()
    folder = repo_root / "data" / "processed" / "ndvi"
    paths = sorted(folder.glob("ndvi_weekly_*_wide.parquet"))
    if not paths:
        raise FileNotFoundError(
            f"No ndvi_weekly_*_wide.parquet in {folder}. "
            "Run: python scripts/process_interim_to_parquet.py --dataset ndvi"
        )
    stem_re = re.compile(r"ndvi_weekly_(\d{4})_wide\.parquet$")
    chunks: list[tuple[int, np.ndarray]] = []
    max_nt = 0
    ny = nx = None
    for p in paths:
        m = stem_re.match(p.name)
        if not m:
            continue
        year = int(m.group(1))
        meta_path = folder / f"ndvi_weekly_{year}_metadata.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        h, w = int(meta["height"]), int(meta["width"])
        if ny is None:
            ny, nx = h, w
        elif (h, w) != (ny, nx):
            raise ValueError(
                f"NDVI grid size mismatch: {year} is {h}x{w}, expected {ny}x{nx}"
            )
        df = pd.read_parquet(p)
        arr = _wide_weekly_parquet_to_3d(df, meta, dtype=np.float32)
        max_nt = max(max_nt, arr.shape[0])
        chunks.append((year, arr))

    if not chunks:
        raise FileNotFoundError(
            f"No valid NDVI wide Parquet + metadata pairs under {folder}"
        )

    out: list[xr.DataArray] = []
    for year, arr in sorted(chunks, key=lambda x: x[0]):
        arr_p = _pad_time_to(arr, max_nt)
        da = xr.DataArray(
            arr_p,
            dims=("time", "y", "x"),
            coords={
                "time": np.arange(max_nt, dtype=np.int32),
                "y": np.arange(ny),
                "x": np.arange(nx),
            },
            name="ndvi",
        )
        out.append(da.expand_dims(calendar_year=[year]))

    merged = xr.concat(out, dim="calendar_year")
    return merged.sortby("calendar_year")


def load_smap_weekly_all_years_processed(
    repo_root: Path | None = None,
) -> xr.DataArray:
    """Same stacking convention as NDVI, for ``smap_weekly_{year}_wide.parquet``."""
    repo_root = repo_root or find_repo_root()
    folder = repo_root / "data" / "processed" / "smap"
    paths = sorted(folder.glob("smap_weekly_*_wide.parquet"))
    if not paths:
        raise FileNotFoundError(
            f"No smap_weekly_*_wide.parquet in {folder}. "
            "Run: python scripts/process_interim_to_parquet.py --dataset smap"
        )
    stem_re = re.compile(r"smap_weekly_(\d{4})_wide\.parquet$")
    chunks: list[tuple[int, np.ndarray]] = []
    max_nt = 0
    ny = nx = None
    for p in paths:
        m = stem_re.match(p.name)
        if not m:
            continue
        year = int(m.group(1))
        meta_path = folder / f"smap_weekly_{year}_metadata.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        h, w = int(meta["height"]), int(meta["width"])
        if ny is None:
            ny, nx = h, w
        elif (h, w) != (ny, nx):
            raise ValueError(
                f"SMAP grid size mismatch: {year} is {h}x{w}, expected {ny}x{nx}"
            )
        df = pd.read_parquet(p)
        arr = _wide_weekly_parquet_to_3d(df, meta, dtype=np.float32)
        max_nt = max(max_nt, arr.shape[0])
        chunks.append((year, arr))

    if not chunks:
        raise FileNotFoundError(
            f"No valid SMAP wide Parquet + metadata pairs under {folder}"
        )

    out: list[xr.DataArray] = []
    for year, arr in sorted(chunks, key=lambda x: x[0]):
        arr_p = _pad_time_to(arr, max_nt)
        da = xr.DataArray(
            arr_p,
            dims=("time", "y", "x"),
            coords={
                "time": np.arange(max_nt, dtype=np.int32),
                "y": np.arange(ny),
                "x": np.arange(nx),
            },
            name="sm_surface",
        )
        out.append(da.expand_dims(calendar_year=[year]))

    merged = xr.concat(out, dim="calendar_year")
    return merged.sortby("calendar_year")
