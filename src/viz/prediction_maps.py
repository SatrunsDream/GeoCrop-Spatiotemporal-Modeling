# Disclaimer: Fully AI-generated.
"""Prediction map utilities for Task 4 crop-type classification."""

from __future__ import annotations

from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch


def labels_to_raster(
    iy: np.ndarray,
    ix: np.ndarray,
    values: np.ndarray,
    height: int,
    width: int,
    nodata: int = -1,
) -> np.ndarray:
    """Scatter pixel-level labels into a 2-D raster array.

    Parameters
    ----------
    iy, ix : 1-D integer arrays of row/column indices.
    values : 1-D array of label values (same length as iy/ix).
    height, width : output raster dimensions.
    nodata : fill value for pixels with no prediction.

    Returns
    -------
    raster : 2-D ndarray of shape (height, width), dtype matching *values*.
    """
    raster = np.full((height, width), nodata, dtype=values.dtype)
    mask = (iy >= 0) & (iy < height) & (ix >= 0) & (ix < width)
    raster[iy[mask], ix[mask]] = values[mask]
    return raster


def plot_crop_type_map(
    raster: np.ndarray,
    *,
    ax: plt.Axes | None = None,
    class_names: Sequence[str],
    class_colors: Sequence[str],
    title: str = "",
    nodata: int = -1,
    extent: tuple[float, float, float, float] | None = None,
    state_shapes=None,
) -> plt.Axes:
    """Plot a categorical crop-type raster with a discrete colour legend.

    Parameters
    ----------
    extent : (left, right, bottom, top) in CRS units for geo-referenced display.
    state_shapes : GeoDataFrame of state boundaries (EPSG:5070) to overlay.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 7))

    n_classes = len(class_names)
    cmap = ListedColormap(["#FFFFFF"] + list(class_colors))
    bounds = [nodata - 0.5] + [i - 0.5 for i in range(n_classes + 1)]
    norm = BoundaryNorm(bounds, cmap.N)

    display_raster = np.where(raster == nodata, nodata, raster).astype(float)
    display_raster[raster == nodata] = nodata

    ax.imshow(display_raster, cmap=cmap, norm=norm, interpolation="nearest",
              extent=extent, aspect="equal" if extent else "auto")
    ax.set_title(title, fontsize=13, fontweight="bold")

    if state_shapes is not None and not getattr(state_shapes, "empty", True):
        state_shapes.boundary.plot(ax=ax, color="#222222", linewidth=0.8, alpha=0.85)

    if extent is not None:
        ax.set_xlabel("Easting (m)")
        ax.set_ylabel("Northing (m)")
    else:
        ax.set_axis_off()

    legend_handles = [
        Patch(facecolor=c, edgecolor="black", label=n)
        for n, c in zip(class_names, class_colors)
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=9, framealpha=0.9)
    return ax
