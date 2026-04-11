"""
ndvi_loader.py — MODIS NDVI time series loader (CropSmart 250m product).

Loads daily or weekly NDVI composites and applies QA/cloud masking.
Reprojects to target CRS.

Approach options considered:
  A) rioxarray with xarray.open_mfdataset — parallel loading of multiple files
  B) h5py + manual reconstruction — if files are HDF5
  C) pymodis utility functions — MODIS-specific helpers
  D) Direct NetCDF via xarray — if CropSmart delivers NetCDF

Selected approach: rioxarray / xarray.open_mfdataset (A) — see DECISIONS.md.
"""

from pathlib import Path
import xarray as xr


def load_ndvi(
    year: int,
    data_path: str | Path,
    doy_range: tuple[int, int] = (100, 310),
    temporal_resolution: str = "weekly",
    bbox: tuple | None = None,
    crs: str = "EPSG:5070",
    apply_qa: bool = True,
) -> xr.DataArray:
    """
    Load MODIS NDVI time series for a given year and DOY window.

    Parameters
    ----------
    year : int
        Year to load.
    data_path : str or Path
        Directory containing NDVI files.
    doy_range : tuple[int, int]
        (start_doy, end_doy) growing season window.
    temporal_resolution : str
        'daily' or 'weekly'.
    bbox : tuple or None
        Bounding box (lon_min, lat_min, lon_max, lat_max) in WGS-84.
    crs : str
        Target CRS.
    apply_qa : bool
        If True, mask pixels flagged by QA band.

    Returns
    -------
    xr.DataArray
        NDVI time series with dims (time, y, x), dtype float32, values in [-1, 1].
    """
    # TODO: implement
    raise NotImplementedError


def apply_qa_mask(ndvi: xr.DataArray, qa: xr.DataArray) -> xr.DataArray:
    """
    Apply QA/cloud mask to NDVI DataArray.

    Parameters
    ----------
    ndvi : xr.DataArray
        Raw NDVI time series.
    qa : xr.DataArray
        QA flag array (same shape as ndvi).

    Returns
    -------
    xr.DataArray
        NDVI with bad pixels set to NaN.
    """
    # TODO: implement
    raise NotImplementedError
