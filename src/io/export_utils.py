"""
export_utils.py — Helpers for saving DataArrays and DataFrames to artifact paths.

Enforces consistent naming convention:
  <stage>__<short_description>__<YYYY-MM-DD>.<ext>

Approach options considered:
  A) Pure rioxarray .to_raster() for GeoTIFFs, pandas .to_parquet() for tables
  B) GDAL-based export for maximum format control
  C) zarr for cloud-native array storage
  D) netCDF4 via xarray .to_netcdf()

Selected approach: A + D — rioxarray GeoTIFF + xarray NetCDF + pandas Parquet.
"""

from pathlib import Path
from datetime import date
import xarray as xr
import pandas as pd


def make_artifact_name(stage: str, description: str, ext: str, run_date: str | None = None) -> str:
    """
    Build a standardized artifact filename.

    Parameters
    ----------
    stage : str
        Pipeline stage (e.g., 'eda', 'preprocess', 'eval').
    description : str
        Short snake_case description.
    ext : str
        File extension (e.g., 'png', 'csv', 'tif').
    run_date : str or None
        Date string YYYY-MM-DD. Defaults to today.

    Returns
    -------
    str
        Filename string: '<stage>__<description>__<date>.<ext>'
    """
    d = run_date or str(date.today())
    return f"{stage}__{description}__{d}.{ext}"


def save_geotiff(da: xr.DataArray, path: Path) -> None:
    """Save an xr.DataArray as a GeoTIFF using rioxarray."""
    # TODO: implement — da.rio.to_raster(path)
    raise NotImplementedError


def save_netcdf(ds: xr.Dataset | xr.DataArray, path: Path) -> None:
    """Save an xr.Dataset or DataArray as NetCDF4."""
    # TODO: implement — ds.to_netcdf(path)
    raise NotImplementedError


def save_parquet(df: pd.DataFrame, path: Path, **kwargs) -> None:
    """Save a DataFrame as Parquet (requires pyarrow or fastparquet)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    opts = {"index": False, "engine": "pyarrow", "compression": "zstd"}
    opts.update(kwargs)
    df.to_parquet(path, **opts)
