"""US Census TIGER/Line county polygons (Corn Belt subset) for Task 2 zonal summaries."""

from __future__ import annotations

import zipfile
from pathlib import Path

import requests

# 13-state Corn Belt — USPS FIPS (zero-padded).
CORN_BELT_STATEFP: frozenset[str] = frozenset(
    {"17", "18", "19", "20", "21", "26", "27", "29", "31", "38", "39", "46", "55"}
)

_TIGER_COUNTY_ZIP = "https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip"


def _zip_path(repo_root: Path) -> Path:
    d = repo_root / "data" / "external" / "tiger"
    d.mkdir(parents=True, exist_ok=True)
    return d / "tl_2024_us_county.zip"


def _extract_dir(repo_root: Path) -> Path:
    return repo_root / "data" / "external" / "tiger" / "tl_2024_us_county_extracted"


def load_cornbelt_counties_5070(repo_root: str | Path, *, timeout_s: int = 120) -> object | None:
    """
    Load county polygons for the 13 Corn Belt states, reprojected to EPSG:5070.

    Caches the national county zip under ``data/external/tiger/`` and extracts
    shapefile components on first read. Returns ``None`` if ``geopandas`` is missing
    or download/read fails.
    """
    repo_root = Path(repo_root)
    try:
        import geopandas as gpd
    except ImportError:
        return None

    zpath = _zip_path(repo_root)
    if not zpath.is_file():
        try:
            r = requests.get(_TIGER_COUNTY_ZIP, timeout=timeout_s)
            r.raise_for_status()
            zpath.write_bytes(r.content)
        except Exception:
            return None

    exdir = _extract_dir(repo_root)
    shp = exdir / "tl_2024_us_county.shp"
    if not shp.is_file():
        try:
            exdir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zpath, "r") as zf:
                zf.extractall(exdir)
        except Exception:
            return None
    if not shp.is_file():
        return None

    try:
        g = gpd.read_file(shp)
    except Exception:
        return None

    if "STATEFP" not in g.columns:
        return None
    sub = g[g["STATEFP"].astype(str).isin(CORN_BELT_STATEFP)].copy()
    if sub.empty:
        return None
    try:
        return sub.to_crs("EPSG:5070")
    except Exception:
        return None
