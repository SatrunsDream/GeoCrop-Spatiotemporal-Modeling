"""
cdl_loader.py — Cropland Data Layer (CDL) data loader.

Loads annual CDL GeoTIFF files for a given year and spatial extent.
Reprojects to EPSG:5070 (CONUS Albers) by default.

Approach options considered:
  A) rasterio + numpy — low-level, maximum control over windowed reads
  B) rioxarray — xarray-native, integrates cleanly with the rest of the pipeline
  C) GDAL warp via subprocess — available if rioxarray unavailable, but less clean

Selected approach: rioxarray (B) — see DECISIONS.md DEC-001.
"""

from pathlib import Path
import xarray as xr


def load_cdl(
    year: int,
    data_path: str | Path,
    bbox: tuple | None = None,
    crs: str = "EPSG:5070",
) -> xr.DataArray:
    """
    Load CDL GeoTIFF for a given year and reproject to target CRS.

    Parameters
    ----------
    year : int
        CDL year to load (e.g., 2022).
    data_path : str or Path
        Directory containing CDL GeoTIFF files.
    bbox : tuple or None
        (lon_min, lat_min, lon_max, lat_max) bounding box in WGS-84.
        If None, loads the full available extent.
    crs : str
        Target coordinate reference system (default: EPSG:5070 CONUS Albers).

    Returns
    -------
    xr.DataArray
        CDL raster with dims (y, x), dtype int16, reprojected to `crs`.
    """
    # TODO: implement
    raise NotImplementedError


def load_cdl_stack(
    year_range: tuple[int, int],
    data_path: str | Path,
    bbox: tuple | None = None,
    crs: str = "EPSG:5070",
) -> xr.DataArray:
    """
    Load multiple CDL years and stack into a (year, y, x) DataArray.

    Parameters
    ----------
    year_range : tuple[int, int]
        (start_year, end_year) inclusive.
    data_path : str or Path
        Directory containing CDL GeoTIFF files.
    bbox : tuple or None
        Bounding box in WGS-84.
    crs : str
        Target CRS.

    Returns
    -------
    xr.DataArray
        Stacked CDL with dims (year, y, x), dtype int16.
    """
    # TODO: implement
    raise NotImplementedError
