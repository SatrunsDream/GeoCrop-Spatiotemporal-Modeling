"""
Load multi-year CDL / NDVI / SMAP stacks from ``data/interim/{cdl,ndvi,smap}/``.

Built by ``scripts/build_interim_data.py``. Notebooks use this instead of
re-reading raw GeoTIFFs.
"""

from __future__ import annotations

import re
from pathlib import Path

import xarray as xr


def find_repo_root(start: Path | None = None) -> Path:
    """
    Walk upward from *start* (default: cwd) until ``requirements.txt`` and
    ``src/`` are found.
    """
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "requirements.txt").is_file() and (p / "src").is_dir():
            return p
    raise FileNotFoundError(
        "Could not locate repo root (requirements.txt + src/). "
        "Open Jupyter with the project folder as cwd, or chdir to the repo root."
    )


def load_cdl_stack_from_interim(repo_root: Path | None = None) -> xr.DataArray:
    """
    Load all CDL annual layers from interim NetCDF stack file(s).

    ``build_interim_data`` writes ``data/interim/cdl/cdl_stack_{y0}_{y1}.nc``
    (variable ``cdl``, dims ``year``, ``y``, ``x``). If multiple disjoint
    stacks exist, they are concatenated along ``year`` and de-duplicated.
    """
    repo_root = repo_root or find_repo_root()
    folder = repo_root / "data" / "interim" / "cdl"
    paths = sorted(folder.glob("cdl_stack_*.nc"))
    if not paths:
        raise FileNotFoundError(
            f"No CDL stack NetCDF in {folder}. Run: python scripts/build_interim_data.py --dataset cdl"
        )
    parts: list[xr.DataArray] = []
    for p in paths:
        ds = xr.open_dataset(p, engine="netcdf4")
        parts.append(ds["cdl"])
    if len(parts) == 1:
        return parts[0]
    merged = xr.concat(parts, dim="year")
    return merged.groupby("year").first().sortby("year")


def _parse_year_from_stem(pattern: re.Pattern[str], stem: str) -> int | None:
    m = pattern.match(stem)
    return int(m.group(1)) if m else None


def load_ndvi_weekly_all_years(repo_root: Path | None = None) -> xr.DataArray:
    """
    Combine per-year files ``ndvi_weekly_{year}.nc`` into one DataArray.

    Dims: ``calendar_year``, ``time``, ``y``, ``x`` (``time`` = weeks within
    that calendar year, sorted).
    """
    repo_root = repo_root or find_repo_root()
    folder = repo_root / "data" / "interim" / "ndvi"
    paths = sorted(folder.glob("ndvi_weekly_*.nc"))
    if not paths:
        raise FileNotFoundError(
            f"No NDVI interim files in {folder}. Run: python scripts/build_interim_data.py --dataset ndvi"
        )
    stem_re = re.compile(r"ndvi_weekly_(\d{4})$")
    arrays: list[xr.DataArray] = []
    for p in paths:
        y = _parse_year_from_stem(stem_re, p.stem)
        if y is None:
            continue
        da = xr.open_dataset(p, engine="netcdf4")["ndvi"]
        da = da.expand_dims(calendar_year=[y])
        arrays.append(da)
    if not arrays:
        raise FileNotFoundError(f"No valid ndvi_weekly_*.nc files under {folder}")
    return xr.concat(arrays, dim="calendar_year").sortby("calendar_year")


def load_smap_weekly_all_years(repo_root: Path | None = None) -> xr.DataArray:
    """
    Combine per-year files ``smap_weekly_{year}.nc`` into one DataArray.

    Dims: ``calendar_year``, ``time``, ``y``, ``x``; variable from file is
    ``sm_surface``.
    """
    repo_root = repo_root or find_repo_root()
    folder = repo_root / "data" / "interim" / "smap"
    paths = sorted(folder.glob("smap_weekly_*.nc"))
    if not paths:
        raise FileNotFoundError(
            f"No SMAP interim files in {folder}. Run: python scripts/build_interim_data.py --dataset smap"
        )
    stem_re = re.compile(r"smap_weekly_(\d{4})$")
    arrays: list[xr.DataArray] = []
    for p in paths:
        y = _parse_year_from_stem(stem_re, p.stem)
        if y is None:
            continue
        da = xr.open_dataset(p, engine="netcdf4")["sm_surface"]
        da = da.expand_dims(calendar_year=[y])
        arrays.append(da)
    if not arrays:
        raise FileNotFoundError(f"No valid smap_weekly_*.nc files under {folder}")
    return xr.concat(arrays, dim="calendar_year").sortby("calendar_year")
