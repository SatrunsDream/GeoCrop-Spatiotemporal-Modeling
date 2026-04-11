"""
spatial_alignment.py — Spatial alignment utilities for multi-resolution datasets.

Handles the core support-mismatch challenge:
  CDL @ 30m  →  NDVI @ 250m  →  SMAP @ 9km

Approach options considered:
  A) Aggregate CDL upward to match coarser grids (safer, less information loss)
  B) Downscale NDVI/SMAP to 30m (risky, introduces artifacts)
  C) Superpixel / SLIC segmentation as intermediate unit
  D) Field polygons from USDA CSB as aggregation unit

Selected approach: A (aggregation upward) — see DECISIONS.md DEC-001.
"""

import numpy as np
import xarray as xr


def compute_crop_fraction(
    cdl: xr.DataArray,
    target_grid: xr.DataArray,
    crop_code: int,
) -> xr.DataArray:
    """
    Compute the fraction of a given CDL crop code within each cell of a coarser target grid.

    Used to identify 'trusted pixels' for NDVI (250m) and to build crop masks for SMAP (9km).

    Parameters
    ----------
    cdl : xr.DataArray
        CDL raster at 30m, dims (y, x), values are int crop codes.
    target_grid : xr.DataArray
        Coarser grid defining target cells (e.g., NDVI 250m or SMAP 9km).
    crop_code : int
        CDL class code to compute fraction for (e.g., 1=corn, 5=soy).

    Returns
    -------
    xr.DataArray
        Fraction [0, 1] of the crop code within each target cell, dims (y_target, x_target).
    """
    # TODO: implement
    raise NotImplementedError


def reproject_match(
    source: xr.DataArray,
    target: xr.DataArray,
    resampling_method: str = "nearest",
) -> xr.DataArray:
    """
    Reproject and spatially align `source` to match the grid of `target`.

    Parameters
    ----------
    source : xr.DataArray
        DataArray to reproject.
    target : xr.DataArray
        Reference grid (CRS, resolution, extent).
    resampling_method : str
        Resampling algorithm: 'nearest', 'bilinear', 'average'.

    Returns
    -------
    xr.DataArray
        `source` reprojected to match `target` grid.
    """
    # TODO: implement via rioxarray reproject_match
    raise NotImplementedError
