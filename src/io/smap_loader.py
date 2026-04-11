"""
smap_loader.py — SMAP L4 soil moisture loader.

Loads SMAP L4 HDF5 files from the EASE-Grid 2.0 (~9 km) projection.
Converts to xarray DataArray and optionally reprojects to target CRS.

Approach options considered:
  A) h5py — direct HDF5 reading, full control
  B) xarray + h5netcdf — if files support NetCDF-style access
  C) earthaccess + direct streaming — for NASA Earthdata authenticated access
  D) CropSmart API download — if portal provides pre-processed downloads

Selected approach: h5py (A) for raw HDF5; earthaccess (C) as fallback — see DECISIONS.md.
"""

from pathlib import Path
import xarray as xr


def load_smap(
    date_range: tuple[str, str],
    data_path: str | Path,
    variable: str = "sm_surface",
    bbox: tuple | None = None,
    crs: str = "EPSG:5070",
) -> xr.DataArray:
    """
    Load SMAP L4 soil moisture for a date range.

    Parameters
    ----------
    date_range : tuple[str, str]
        ('YYYY-MM-DD', 'YYYY-MM-DD') start and end dates (inclusive).
    data_path : str or Path
        Directory containing SMAP HDF5 files.
    variable : str
        Variable name to extract (e.g., 'sm_surface').
    bbox : tuple or None
        Bounding box (lon_min, lat_min, lon_max, lat_max) in WGS-84.
    crs : str
        Target CRS for reprojection.

    Returns
    -------
    xr.DataArray
        Soil moisture with dims (time, y, x), dtype float32, units m³/m³.
    """
    # TODO: implement
    raise NotImplementedError


def load_smap_climatology(
    baseline_years: tuple[int, int],
    data_path: str | Path,
    variable: str = "sm_surface",
    temporal_agg: str = "weekly",
) -> xr.Dataset:
    """
    Load and aggregate SMAP data to build a baseline climatology.

    Parameters
    ----------
    baseline_years : tuple[int, int]
        (start_year, end_year) inclusive for climatology computation.
    data_path : str or Path
        Directory containing SMAP HDF5 files.
    variable : str
        SMAP variable to use.
    temporal_agg : str
        Aggregation unit: 'daily' or 'weekly'.

    Returns
    -------
    xr.Dataset
        Dataset with 'mean' and 'std' variables over the baseline period.
    """
    # TODO: implement
    raise NotImplementedError
