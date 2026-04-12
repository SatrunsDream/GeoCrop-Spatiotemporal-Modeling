"""Rotation class map visualization (Task 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.patches as mpatches
import yaml

_NATURAL_EARTH_ADMIN1_110M = (
    "https://naciscdn.org/naturalearth/110m/cultural/"
    "ne_110m_admin_1_states_provinces.zip"
)
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

# U.S. Corn Belt — 13 states (Wikipedia infobox / CRS “Corn Belt” usage).
CORN_BELT_13_STATE_NAMES: frozenset[str] = frozenset(
    {
        "Illinois",
        "Indiana",
        "Iowa",
        "Kansas",
        "Kentucky",
        "Michigan",
        "Minnesota",
        "Missouri",
        "Nebraska",
        "North Dakota",
        "Ohio",
        "South Dakota",
        "Wisconsin",
    }
)

_TASK2_CFG = Path("configs") / "task2_crop_rotation.yaml"


def _state_names_for_task2(repo_root: Path) -> frozenset[str]:
    cfg_path = repo_root / _TASK2_CFG
    if not cfg_path.is_file():
        return CORN_BELT_13_STATE_NAMES
    try:
        with cfg_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        raw = (cfg.get("study_area") or {}).get("states")
        if isinstance(raw, list) and raw:
            return frozenset(str(x).strip() for x in raw if str(x).strip())
    except Exception:
        pass
    return CORN_BELT_13_STATE_NAMES


def load_cornbelt_state_boundaries_5070(
    repo_root: str | Path,
    *,
    state_names: frozenset[str] | None = None,
) -> Any | None:
    """
    Return state polygons in **EPSG:5070** for map overlays.

    Default state list: ``study_area.states`` in ``configs/task2_crop_rotation.yaml``,
    or the **13-state Corn Belt** if that key is missing.

    Order of attempt:
    1. First ``*.shp`` under ``data/external/states/`` (TIGER etc.), filtered by name.
    2. **Natural Earth 110m** admin-1 (requires network on first use) — subset of U.S. states.

    Returns ``None`` if ``geopandas`` is missing or both paths fail.
    """
    repo_root = Path(repo_root)
    names = state_names or _state_names_for_task2(repo_root)
    try:
        import geopandas as gpd
    except ImportError:
        return None

    states_dir = repo_root / "data" / "external" / "states"
    if states_dir.is_dir():
        shp = sorted(states_dir.glob("*.shp"))
        if shp:
            try:
                g = gpd.read_file(shp[0])
                name_col = next(
                    (c for c in ("NAME", "NAME_1", "name", "STATE_NAME") if c in g.columns),
                    None,
                )
                if name_col:
                    sub = g[g[name_col].isin(names)].copy()
                    if len(sub) > 0:
                        return sub.to_crs("EPSG:5070")
            except Exception:
                pass

    try:
        g = gpd.read_file(_NATURAL_EARTH_ADMIN1_110M)
        usa = g[g["adm0_a3"] == "USA"]
        sub = usa[usa["name"].isin(names)].copy()
        if sub.empty:
            return None
        return sub.to_crs("EPSG:5070")
    except Exception:
        return None


def plot_rotation_class_map(
    raster_path: str | Path,
    *,
    state_shapes: Any | None = None,
    title: str = "Crop rotation classes (CDL 2015–2024)",
    figsize: tuple[float, float] = (12, 9),
    dpi: int = 200,
    nodata: int = 255,
    focus_state_names: frozenset[str] | set[str] | None = None,
    focus_pad_frac: float = 0.04,
) -> tuple[plt.Figure, plt.Axes]:
    """
    Plot a single-band uint8 rotation map (0/1/2) with RGB class colors.

    Parameters
    ----------
    state_shapes
        Optional ``geopandas.GeoDataFrame`` in the same CRS as the raster (e.g. EPSG:5070).
    focus_state_names
        If set with ``state_shapes``, draw only those states' boundaries and set axis
        limits to their union bounds (padding ``focus_pad_frac``) for a regional zoom.
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

    bnd_gdf = state_shapes
    zoom_bounds: tuple[float, float, float, float] | None = None
    if bnd_gdf is not None and not getattr(bnd_gdf, "empty", True) and focus_state_names:
        names = frozenset(str(x) for x in focus_state_names)
        name_col = next(
            (c for c in ("NAME", "name", "NAME_1", "STATE_NAME") if c in bnd_gdf.columns),
            None,
        )
        if name_col:
            sub = bnd_gdf[bnd_gdf[name_col].isin(names)].copy()
            if not sub.empty:
                bnd_gdf = sub
                zoom_bounds = tuple(sub.total_bounds)

    if bnd_gdf is not None and not getattr(bnd_gdf, "empty", True):
        bnd_gdf.boundary.plot(
            ax=ax,
            color="#1a1a1a",
            linewidth=1.1,
            alpha=0.9,
            zorder=10,
        )
        if zoom_bounds is not None:
            minx, miny, maxx, maxy = zoom_bounds
            dx = (maxx - minx) * float(focus_pad_frac)
            dy = (maxy - miny) * float(focus_pad_frac)
            ax.set_xlim(minx - dx, maxx + dx)
            ax.set_ylim(miny - dy, maxy + dy)

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
