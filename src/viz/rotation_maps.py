"""Rotation class map visualization (Task 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.plot import plotting_extent


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


CLASS_COLORS = {
    0: "#2ecc71",
    1: "#e74c3c",
    2: "#f39c12",
}
CLASS_LABELS = {0: "Regular rotation", 1: "Monoculture", 2: "Irregular"}


def plot_rotation_class_map(
    raster_path: str | Path,
    *,
    state_shapes: Any | None = None,
    title: str = "Crop rotation classes (CDL 2013–2022)",
    figsize: tuple[float, float] = (12, 9),
    dpi: int = 200,
    nodata: int = 255,
) -> tuple[plt.Figure, plt.Axes]:
    """
    Plot a single-band uint8 rotation map (0/1/2) with RGB class colors.

    Parameters
    ----------
    state_shapes
        Optional ``geopandas.GeoDataFrame`` in the same CRS as the raster (e.g. EPSG:5070).
    """
    raster_path = Path(raster_path)
    with rasterio.open(raster_path) as src:
        data = src.read(1)
        extent = plotting_extent(src)

    h, w = data.shape
    rgb = np.ones((h, w, 3), dtype=np.float32)
    for cls, hx in CLASS_COLORS.items():
        r, g, b = _hex_to_rgb(hx)
        m = data == cls
        rgb[m] = [r, g, b]

    nodata_mask = data == nodata
    rgb[nodata_mask] = 0.92  # light gray background

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.imshow(rgb, extent=list(extent), origin="upper", interpolation="nearest")

    if state_shapes is not None:
        state_shapes.boundary.plot(ax=ax, color="k", linewidth=0.4, alpha=0.6)

    patches = [
        mpatches.Patch(color=CLASS_COLORS[c], label=CLASS_LABELS[c])
        for c in sorted(CLASS_COLORS)
    ]
    patches.append(mpatches.Patch(color=(0.92, 0.92, 0.92), label="No data"))
    ax.legend(handles=patches, loc="lower left", fontsize=9, framealpha=0.9)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_aspect("equal")
    return fig, ax
