# Disclaimer: Fully AI-generated.
"""Raster visualization helpers for Task 3 SMAP anomalies (EPSG:5070 grid)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from affine import Affine
from rasterio.transform import array_bounds, xy as rio_xy


def grid_shape_from_metadata(meta: dict) -> tuple[int, int]:
    return int(meta["height"]), int(meta["width"])


def affine_from_metadata(meta: dict) -> Affine:
    t = meta["transform"]
    return Affine(t[0], t[1], t[2], t[3], t[4], t[5])


def plot_extent_from_metadata(meta: dict) -> tuple[float, float, float, float]:
    """``imshow`` ``extent`` as ``(left, right, bottom, top)``."""
    h, w = grid_shape_from_metadata(meta)
    aff = affine_from_metadata(meta)
    left, bottom, right, top = array_bounds(h, w, aff)
    return left, right, bottom, top


def fill_raster(
    height: int,
    width: int,
    iy: np.ndarray,
    ix: np.ndarray,
    values: np.ndarray,
    *,
    nodata: float = np.nan,
    dtype: type = np.float32,
) -> np.ndarray:
    """Scatter ``values`` into a (height, width) raster at integer ``(iy, ix)``."""
    g = np.full((height, width), nodata, dtype=dtype)
    ii = iy.astype(np.int64, copy=False)
    jj = ix.astype(np.int64, copy=False)
    m = (ii >= 0) & (ii < height) & (jj >= 0) & (jj < width)
    g[ii[m], jj[m]] = values[m].astype(dtype, copy=False)
    return g


def plot_z_map(
    grid: np.ndarray,
    extent: tuple[float, float, float, float],
    *,
    title: str,
    vmin: float = -3.0,
    vmax: float = 3.0,
    cmap: str = "RdBu_r",
    state_shapes: Any | None = None,
    figsize: tuple[float, float] = (8.5, 7.0),
) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=figsize, dpi=120)
    im = ax.imshow(
        grid,
        extent=list(extent),
        origin="upper",
        interpolation="nearest",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
    )
    plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="z-score")
    if state_shapes is not None and not getattr(state_shapes, "empty", True):
        state_shapes.boundary.plot(ax=ax, color="#222", linewidth=0.8, alpha=0.85)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_aspect("equal")
    return fig, ax


def pixel_xy_from_metadata(
    meta: dict,
    iy: np.ndarray,
    ix: np.ndarray,
    *,
    chunk_size: int = 400_000,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Map grid ``(iy, ix)`` to projected coordinates (pixel **center**).

    ``rasterio.transform.xy`` allocates large internal buffers; long inputs are
    processed in chunks to avoid ``MemoryError`` on wide anomaly tables
    (~2M pixels × many weeks).
    """
    aff = affine_from_metadata(meta)
    iy = np.asarray(iy)
    ix = np.asarray(ix)
    n = int(iy.size)
    if n == 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    xs_out = np.empty(n, dtype=np.float64)
    ys_out = np.empty(n, dtype=np.float64)
    cs = max(10_000, int(chunk_size))
    for start in range(0, n, cs):
        end = min(start + cs, n)
        xsc, ysc = rio_xy(aff, iy[start:end], ix[start:end], offset="center")
        xs_out[start:end] = np.asarray(xsc, dtype=np.float64).ravel()
        ys_out[start:end] = np.asarray(ysc, dtype=np.float64).ravel()
    return xs_out, ys_out
