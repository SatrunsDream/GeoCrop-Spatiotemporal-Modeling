# Disclaimer: Fully AI-generated.
"""
Corn Belt study extent for NAFSI downloads (EPSG:5070).

The union of configured state polygons (see configs/study_extent.yaml) defines
the WMS BBOX. GetCapabilities MaxWidth/MaxHeight in data/external/*.map inform
sizing but are clamped to WMS_GETMAP_MAX_PIXEL (4096) because mapserv GetMap
enforces that limit even when caps advertise 8192.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from shapely.ops import unary_union

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STUDY_EXTENT_YAML = REPO_ROOT / "configs" / "study_extent.yaml"
STUDY_CRS = "EPSG:5070"

# GMU mapserv + CropScape: GetMap hard limit (caps may advertise e.g. 8192).
WMS_GETMAP_MAX_PIXEL = 4096

# Natural Earth 110m admin-1 (stable CDN; used only for state geometries).
_NE_ADMIN1_URL = (
    "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_1_states_provinces.zip"
)


@dataclass(frozen=True)
class StudyExtentConfig:
    iso_codes: tuple[str, ...]
    buffer_m: float
    target_res_m: float


def load_study_extent_config(path: Path | None = None) -> StudyExtentConfig:
    p = path or STUDY_EXTENT_YAML
    with open(p, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    codes = tuple(str(x).strip().upper() for x in raw["corn_belt_iso_3166_2"])
    return StudyExtentConfig(
        iso_codes=codes,
        buffer_m=float(raw.get("buffer_meters", 20_000)),
        target_res_m=float(raw.get("target_res_meters", 320)),
    )


def parse_wms_max_dimensions_from_capabilities(cap_xml_path: Path) -> tuple[int, int]:
    """Read MaxWidth / MaxHeight from a saved WMS GetCapabilities XML (.map)."""
    text = cap_xml_path.read_text(encoding="utf-8", errors="replace")
    mw = re.search(r"<MaxWidth>(\d+)</MaxWidth>", text, re.I)
    mh = re.search(r"<MaxHeight>(\d+)</MaxHeight>", text, re.I)
    w = int(mw.group(1)) if mw else WMS_GETMAP_MAX_PIXEL
    h = int(mh.group(1)) if mh else WMS_GETMAP_MAX_PIXEL
    return w, h


def _corn_belt_bbox_from_natural_earth(cfg: StudyExtentConfig) -> tuple[float, float, float, float]:
    import geopandas as gpd

    gdf = gpd.read_file(_NE_ADMIN1_URL)
    usa = gdf[gdf["adm0_a3"] == "USA"].copy()
    if "iso_3166_2" not in usa.columns:
        raise ValueError("Natural Earth layer missing iso_3166_2")
    sel = usa[usa["iso_3166_2"].str.upper().isin(cfg.iso_codes)]
    if len(sel) < len(cfg.iso_codes):
        found = set(sel["iso_3166_2"].str.upper())
        missing = set(cfg.iso_codes) - found
        raise ValueError(f"Corn Belt states not found in Natural Earth: {sorted(missing)}")
    geom = unary_union(sel.geometry.tolist())
    gs = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(STUDY_CRS)
    minx, miny, maxx, maxy = gs.total_bounds
    b = cfg.buffer_m
    return (minx - b, miny - b, maxx + b, maxy + b)


def _fallback_bbox_wgs84_buffer(cfg: StudyExtentConfig) -> tuple[float, float, float, float]:
    """Conservative Corn Belt rectangle if Natural Earth fetch fails (EPSG:5070)."""
    from pyproj import Transformer

    # Rough WGS84 envelope covering configured states; slightly padded.
    lon0, lat0, lon1, lat1 = -104.6, 35.8, -79.5, 49.6
    t = Transformer.from_crs("EPSG:4326", STUDY_CRS, always_xy=True)
    xs, ys = [], []
    for lon, lat in [(lon0, lat0), (lon1, lat0), (lon1, lat1), (lon0, lat1)]:
        x, y = t.transform(lon, lat)
        xs.append(x)
        ys.append(y)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    b = cfg.buffer_m
    return (minx - b, miny - b, maxx + b, maxy + b)


def corn_belt_bbox_epsg5070(
    cfg: StudyExtentConfig | None = None,
) -> tuple[float, float, float, float]:
    """(xmin, ymin, xmax, ymax) in EPSG:5070 for the Corn Belt union + buffer."""
    cfg = cfg or load_study_extent_config()
    try:
        return _corn_belt_bbox_from_natural_earth(cfg)
    except Exception:
        return _fallback_bbox_wgs84_buffer(cfg)


def wms_image_size_for_bbox(
    bbox: tuple[float, float, float, float],
    max_width: int,
    max_height: int,
    target_res_m: float,
) -> tuple[int, int]:
    """
    WIDTH/HEIGHT for WMS GetMap so the full bbox is visible and pixel size is
    not coarser than target_res_m (unless the server cap forces smaller images).
    """
    xmin, ymin, xmax, ymax = bbox
    w_m = xmax - xmin
    h_m = ymax - ymin
    if w_m <= 0 or h_m <= 0:
        raise ValueError(f"Invalid bbox: {bbox}")

    pw = w_m / target_res_m
    ph = h_m / target_res_m
    data_aspect = w_m / h_m
    cap_aspect = max_width / max_height

    if data_aspect > cap_aspect:
        img_w = max_width
        img_h = max(1, int(round(max_width / data_aspect)))
    else:
        img_h = max_height
        img_w = max(1, int(round(max_height * data_aspect)))

    eff_w = w_m / img_w
    eff_h = h_m / img_h
    if eff_w > target_res_m * 1.01 or eff_h > target_res_m * 1.01:
        # Cap hit: effective resolution is coarser than target (expected for large AOI).
        pass
    return img_w, img_h


@dataclass(frozen=True)
class WmsStudyGrid:
    bbox: tuple[float, float, float, float]
    width: int
    height: int
    max_width: int
    max_height: int


def resolve_wms_study_grid(
    ndvi_capabilities_path: Path | None,
    extent_cfg: StudyExtentConfig | None = None,
) -> WmsStudyGrid:
    """
    Corn Belt BBOX + pixel dimensions from the NDVI weekly GetCapabilities snapshot,
    clamped to WMS_GETMAP_MAX_PIXEL (mapserv enforces 4096 regardless of advertised caps).
    """
    cfg = extent_cfg or load_study_extent_config()
    bbox = corn_belt_bbox_epsg5070(cfg)
    if ndvi_capabilities_path and ndvi_capabilities_path.is_file():
        mw, mh = parse_wms_max_dimensions_from_capabilities(ndvi_capabilities_path)
    else:
        mw, mh = WMS_GETMAP_MAX_PIXEL, WMS_GETMAP_MAX_PIXEL
    mw = min(mw, WMS_GETMAP_MAX_PIXEL)
    mh = min(mh, WMS_GETMAP_MAX_PIXEL)
    w, h = wms_image_size_for_bbox(bbox, mw, mh, cfg.target_res_m)
    return WmsStudyGrid(bbox=bbox, width=w, height=h, max_width=mw, max_height=mh)


def resolve_cdl_wms_study_grid(
    cdl_capabilities_path: Path | None,
    extent_cfg: StudyExtentConfig | None = None,
) -> WmsStudyGrid:
    """
    Same Corn Belt BBOX as NDVI/SMAP; CDL GetCapabilities limits when present,
    always clamped to WMS_GETMAP_MAX_PIXEL.
    """
    cfg = extent_cfg or load_study_extent_config()
    bbox = corn_belt_bbox_epsg5070(cfg)
    mw, mh = WMS_GETMAP_MAX_PIXEL, WMS_GETMAP_MAX_PIXEL
    if cdl_capabilities_path and cdl_capabilities_path.is_file():
        cap_w, cap_h = parse_wms_max_dimensions_from_capabilities(cdl_capabilities_path)
        mw = min(cap_w, WMS_GETMAP_MAX_PIXEL)
        mh = min(cap_h, WMS_GETMAP_MAX_PIXEL)
    w, h = wms_image_size_for_bbox(bbox, mw, mh, cfg.target_res_m)
    return WmsStudyGrid(bbox=bbox, width=w, height=h, max_width=mw, max_height=mh)
