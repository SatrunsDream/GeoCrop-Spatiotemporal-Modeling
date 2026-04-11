"""
download_data.py — Scripted WMS GeoTIFF download for all three CropSmart datasets.

Datasets (year ranges per NAFSI Track 1 challenge brief, Section 3):
  1. CDL  (30 m, 2008–2025) — from USDA NASS CropScape WMS
  2. NDVI Weekly (250 m, 2000–2026) — from CropSmart/NASSGEO WMS
  3. SMAP Weekly (9 km, 2015–2025, AVERAGE) — from CropSmart/NASSGEO WMS

Strategy: WMS GetMap → image/tiff (GeoTIFF).
  - One GeoTIFF per year for CDL.
  - One GeoTIFF per growing-season week for NDVI.
  - One GeoTIFF per week for SMAP (all 52 weeks, for baseline climatology).
  - All files clipped to the Iowa + Nebraska study-area BBOX in EPSG:5070.

NDVI/SMAP mapserv ``map=`` paths and the mapserv base URL are read from saved
GetCapabilities XML under data/external/ (e.g. NDVI-WEEKLY_2025.map). Layer
names still follow those documents. Override with --ndvi-capabilities etc. if needed.

Usage (from repo root on JupyterHub):
  python scripts/download_data.py --dataset all
  python scripts/download_data.py --dataset cdl
  python scripts/download_data.py --dataset ndvi --year 2022
  python scripts/download_data.py --dataset smap --year 2019

Resume after an interrupted run (skip years already on disk; uses latest
calendar year seen in each raw folder, then continues from the next year):
  python scripts/download_data.py --dataset cdl --resume
  python scripts/download_data.py --dataset ndvi --resume

Or set an explicit floor: ``--min-year 2024`` (still skips individual files
that already exist).

NOTE: Run this on your CropSmart JupyterHub for fastest download speeds
(same server as the WMS endpoints). This script is safe to re-run —
it skips files that already exist.
"""

import argparse
import html as html_lib
import re
import sys
import time
import datetime
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.nafsi_catalog import CDL_YEARS, NDVI_YEARS, SMAP_YEARS

# ── Study area bounding box (EPSG:5070 — CONUS Albers Equal Area) ──────────
# Covers Iowa + Nebraska corn belt. Verified via PROJ transformation.
# Iowa:     xmin=-505000, xmax=-207000, ymin=2063000, ymax=2392000
# Nebraska: xmin=-823000, xmax=-358000, ymin=1947000, ymax=2234000
# Combined + 20km buffer:
STUDY_BBOX = (-843000, 1927000, -187000, 2412000)  # (xmin, ymin, xmax, ymax)
STUDY_CRS  = "EPSG:5070"

# Output image dimensions (pixels). Width/height ratio must match bbox aspect ratio.
# BBOX is 656km wide × 485km tall → 656:485 ≈ 1.35:1
# For CDL (30m pixel): 656000/30 ≈ 21867 px — too large. Download in tiles, or use lower res.
# For a first pass use 2048×1520 px which gives ~320m/px (sufficient for inspection).
# For production CDL download you need tiling or WCS — see note below.
IMG_WIDTH  = 2048
IMG_HEIGHT = 1520

# ── WMS endpoint URLs (defaults; overridden by data/external GetCapabilities) ─
CDL_WMS_BASE  = "https://crop.csiss.gmu.edu/cgi-bin/wms_cdlall"
CROPSMART_WMS = "https://nassgeo.csiss.gmu.edu/cgi-bin/mapserv"

# Year lists: src.utils.nafsi_catalog (NAFSI brief §3 — CDL / NDVI / SMAP periods)

# ── Growing season weeks (NDVI only needs growing season) ───────────────────
# ISO weeks 18–43 ≈ DOY 120–300 ≈ late April through late October
GROWING_SEASON_WEEKS = list(range(18, 44))  # 26 weeks

# ── Output directories (REPO_ROOT set at top for nafsi_catalog import) ───────
EXTERNAL_DIR = REPO_ROOT / "data" / "external"
RAW_CDL     = REPO_ROOT / "data" / "raw" / "cdl"
RAW_NDVI    = REPO_ROOT / "data" / "raw" / "ndvi"
RAW_SMAP    = REPO_ROOT / "data" / "raw" / "smap"

# Filled by configure_from_external() from data/external/*.map (saved GetCapabilities XML)
_cropsmart_mapserv_base: str | None = None
_ndvi_map_path_ref: str | None = None
_ndvi_map_ref_year: int | None = None
_smap_map_path_ref: str | None = None
_smap_map_ref_year: int | None = None

RAW_CDL.mkdir(parents=True, exist_ok=True)
RAW_NDVI.mkdir(parents=True, exist_ok=True)
RAW_SMAP.mkdir(parents=True, exist_ok=True)


def filter_year_list(years: list[int], lo: int | None, hi: int | None) -> list[int]:
    """Restrict catalog years to an inclusive [lo, hi] window (either bound optional)."""
    out = years
    if lo is not None:
        out = [y for y in out if y >= lo]
    if hi is not None:
        out = [y for y in out if y <= hi]
    return out


def latest_year_cdl_raw() -> int | None:
    found: list[int] = []
    for p in RAW_CDL.glob("cdl_*_iowa_nebraska_5070.tif"):
        m = re.match(r"cdl_(\d{4})_iowa_nebraska_5070\.tif$", p.name)
        if m:
            found.append(int(m.group(1)))
    return max(found) if found else None


def latest_year_ndvi_raw() -> int | None:
    found: list[int] = []
    for p in RAW_NDVI.glob("NDVI-WEEKLY_*.tif"):
        m = re.match(r"NDVI-WEEKLY_(\d{4})_\d{2}_", p.name)
        if m:
            found.append(int(m.group(1)))
    return max(found) if found else None


def latest_year_smap_raw() -> int | None:
    found: list[int] = []
    for p in RAW_SMAP.glob("SMAP-9KM-WEEKLY-TOP_*.tif"):
        m = re.match(r"SMAP-9KM-WEEKLY-TOP_(\d{4})_\d{2}_", p.name)
        if m:
            found.append(int(m.group(1)))
    return max(found) if found else None


def _merge_year_floor(current: int | None, floor: int) -> int:
    return floor if current is None else max(current, floor)


def resolve_download_years(
    dataset: str,
    year_single: int | None,
    min_year: int | None,
    max_year: int | None,
    resume: bool,
) -> tuple[list[int], list[int], list[int]]:
    """
    Year lists per dataset. ``resume`` sets a floor of (latest year on disk) + 1
    for each dataset that is selected, so runs continue after the last full year.
    Missing NDVI/SMAP weeks in that last year are still filled when re-running
    without ``resume`` (per-file skip).
    """
    if year_single is not None:
        y = year_single
        return [y], [y], [y]

    cdl_lo = min_year
    ndvi_lo = min_year
    smap_lo = min_year
    if resume:
        if dataset in ("all", "cdl"):
            last = latest_year_cdl_raw()
            if last is not None:
                cdl_lo = _merge_year_floor(cdl_lo, last + 1)
        if dataset in ("all", "ndvi"):
            last = latest_year_ndvi_raw()
            if last is not None:
                ndvi_lo = _merge_year_floor(ndvi_lo, last + 1)
        if dataset in ("all", "smap"):
            last = latest_year_smap_raw()
            if last is not None:
                smap_lo = _merge_year_floor(smap_lo, last + 1)

    if dataset == "all":
        return (
            filter_year_list(CDL_YEARS, cdl_lo, max_year),
            filter_year_list(NDVI_YEARS, ndvi_lo, max_year),
            filter_year_list(SMAP_YEARS, smap_lo, max_year),
        )
    if dataset == "cdl":
        return (filter_year_list(CDL_YEARS, cdl_lo, max_year), [], [])
    if dataset == "ndvi":
        return ([], filter_year_list(NDVI_YEARS, ndvi_lo, max_year), [])
    if dataset == "smap":
        return ([], [], filter_year_list(SMAP_YEARS, smap_lo, max_year))
    return [], [], []


# ── Retry / rate-limit config ───────────────────────────────────────────────
RETRY_ATTEMPTS = 3
RETRY_DELAY_S  = 5
INTER_REQUEST_DELAY_S = 1.0   # pause between requests to be polite to the server


# ═══════════════════════════════════════════════════════════════════════════
# Layer-name generators — built from the naming conventions decoded from the
# GetCapabilities XML files in data/external/
# ═══════════════════════════════════════════════════════════════════════════

def cdl_layer_name(year: int) -> str:
    """CDL layer: cdl_{YEAR}  (e.g. cdl_2022)"""
    return f"cdl_{year}"


def ndvi_weekly_layer_name(year: int, week: int) -> str | None:
    """
    NDVI weekly layer: NDVI-WEEKLY_{YEAR}_{WEEK:02d}_{YEAR}.{MM}.{DD}_{YEAR}.{MM}.{DD}
    Returns None if the ISO week does not exist for this year.

    Naming convention decoded from NDVI-WEEKLY_2025.map GetCapabilities file.
    Week 1 of 2025 = 2024.12.30 – 2025.01.05  (ISO week, Monday–Sunday).
    """
    try:
        # ISO week starts on Monday
        monday = datetime.date.fromisocalendar(year, week, 1)
        sunday = monday + datetime.timedelta(days=6)
        week_str  = f"{week:02d}"
        start_str = monday.strftime("%Y.%m.%d")
        end_str   = sunday.strftime("%Y.%m.%d")
        return f"NDVI-WEEKLY_{year}_{week_str}_{start_str}_{end_str}"
    except ValueError:
        return None   # week does not exist for this year


def _map_path_for_year(map_path_ref: str, ref_year: int, year: int) -> str:
    """Swap the reference year in a server mapfile path for another calendar year."""
    return map_path_ref.replace(f"_{ref_year}.map", f"_{year}.map")


def ndvi_weekly_map_param(year: int) -> str:
    """MAP parameter for the NDVI WMS mapserv request (from data/external caps when configured)."""
    if _ndvi_map_path_ref is not None and _ndvi_map_ref_year is not None:
        return _map_path_for_year(_ndvi_map_path_ref, _ndvi_map_ref_year, year)
    return f"/DATA/SMAP_DATA/WMS/NDVI-WEEKLY_{year}.map"


def smap_weekly_layer_name(year: int, week: int, stat: str = "AVERAGE") -> str | None:
    """
    SMAP weekly layer:
    SMAP-9KM-WEEKLY-TOP_{YEAR}_{WEEK:02d}_{YEAR}.{MM}.{DD}_{YEAR}.{MM}.{DD}_AVERAGE

    stat = 'AVERAGE' (recommended) or 'MAX'

    Naming convention decoded from SMAP-9KM-WEEKLY-TOP_2025.map GetCapabilities file.
    """
    try:
        monday = datetime.date.fromisocalendar(year, week, 1)
        sunday = monday + datetime.timedelta(days=6)
        week_str  = f"{week:02d}"
        start_str = monday.strftime("%Y.%m.%d")
        end_str   = sunday.strftime("%Y.%m.%d")
        return f"SMAP-9KM-WEEKLY-TOP_{year}_{week_str}_{start_str}_{end_str}_{stat}"
    except ValueError:
        return None


def smap_weekly_map_param(year: int) -> str:
    """MAP parameter for the SMAP WMS mapserv request (from data/external caps when configured)."""
    if _smap_map_path_ref is not None and _smap_map_ref_year is not None:
        return _map_path_for_year(_smap_map_path_ref, _smap_map_ref_year, year)
    return f"/DATA/SMAP_DATA/WMS/SMAP-9KM-WEEKLY-TOP_{year}.map"


def _first_mapserv_href_from_capabilities_xml(text: str) -> str | None:
    """First xlink:href pointing to mapserv with a map= query (authoritative service URL)."""
    for m in re.finditer(r'xlink:href="([^"]+)"', text):
        href = html_lib.unescape(m.group(1).replace("&amp;", "&"))
        if "mapserv" in href and "map=" in href:
            return href
    return None


def parse_mapserv_capabilities_path(cap_xml_path: Path) -> tuple[str, str, int]:
    """
    Read a saved WMS 1.3.0 GetCapabilities XML (e.g. data/external/NDVI-WEEKLY_2025.map).

    Returns
    -------
    mapserv_base : str
        e.g. https://nassgeo.csiss.gmu.edu/cgi-bin/mapserv
    map_path : str
        e.g. /DATA/SMAP_DATA/WMS/NDVI-WEEKLY_2025.map
    ref_year : int
        Year encoded in that mapfile name (used to rewrite paths for other years).
    """
    text = cap_xml_path.read_text(encoding="utf-8", errors="replace")
    href = _first_mapserv_href_from_capabilities_xml(text)
    if not href:
        raise ValueError(f"No mapserv map= URL found in {cap_xml_path}")

    parsed = urlparse(href)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    q = parse_qs(parsed.query)
    raw_map = (q.get("map") or [None])[0]
    if not raw_map:
        raise ValueError(f"No map= parameter in first mapserv href in {cap_xml_path}")

    ym = re.search(r"_(\d{4})\.map$", raw_map)
    if not ym:
        raise ValueError(f"Could not parse reference year from map path: {raw_map}")
    return base, raw_map, int(ym.group(1))


def parse_cdl_wms_base_from_capabilities(cap_xml_path: Path) -> str:
    """CDL CropScape WMS base URL from saved wms_cdlall GetCapabilities (no map=)."""
    text = cap_xml_path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'xlink:href="([^"]+)"', text):
        href = html_lib.unescape(m.group(1).replace("&amp;", "&"))
        if "wms_cdlall" in href:
            base = href.split("?", 1)[0].rstrip("?")
            return base
    raise ValueError(f"No wms_cdlall URL found in {cap_xml_path}")


def _pick_latest_external(pattern: str) -> Path | None:
    paths = sorted(EXTERNAL_DIR.glob(pattern))
    return paths[-1] if paths else None


def configure_from_external(
    ndvi_caps: Path | None = None,
    smap_caps: Path | None = None,
    cdl_caps: Path | None = None,
) -> None:
    """
    Load WMS base URLs and mapfile path templates from data/external GetCapabilities.

    The *.map files in data/external are XML capability documents saved from CropSmart
    (same layer naming as the template notebook). The template preview sometimes uses
    cloud.csiss.gmu.edu + MAP=/WMS/...; the saved caps here use nassgeo.csiss.gmu.edu
    and map=/DATA/SMAP_DATA/WMS/... — both are valid CropSmart endpoints.
    """
    global CDL_WMS_BASE, CROPSMART_WMS
    global _cropsmart_mapserv_base, _ndvi_map_path_ref, _ndvi_map_ref_year
    global _smap_map_path_ref, _smap_map_ref_year

    ndvi_path = ndvi_caps or _pick_latest_external("NDVI-WEEKLY_*.map")
    smap_path = smap_caps or _pick_latest_external("SMAP-9KM-WEEKLY-TOP_*.map")

    if ndvi_path and ndvi_path.is_file():
        base, mpath, yref = parse_mapserv_capabilities_path(ndvi_path)
        _cropsmart_mapserv_base = base
        CROPSMART_WMS = base
        _ndvi_map_path_ref = mpath
        _ndvi_map_ref_year = yref
        print(f"[config] NDVI caps: {ndvi_path.name} -> mapserv={base} map={mpath}")
    else:
        print(
            f"[config] NDVI: no capabilities file under {EXTERNAL_DIR} "
            "(NDVI-WEEKLY_*.map); using built-in map path template."
        )

    if smap_path and smap_path.is_file():
        base, mpath, yref = parse_mapserv_capabilities_path(smap_path)
        if _cropsmart_mapserv_base is None:
            _cropsmart_mapserv_base = base
            CROPSMART_WMS = base
        elif base != _cropsmart_mapserv_base:
            print(
                f"[WARN] SMAP mapserv host {base!r} != NDVI {_cropsmart_mapserv_base!r}; "
                "keeping NDVI host for all mapserv requests."
            )
        _smap_map_path_ref = mpath
        _smap_map_ref_year = yref
        print(f"[config] SMAP caps: {smap_path.name} -> map={mpath}")
    else:
        print(
            f"[config] SMAP: no capabilities file (SMAP-9KM-WEEKLY-TOP_*.map); "
            "using built-in map path template."
        )

    cdl_path = cdl_caps
    if cdl_path is None:
        cands = sorted(EXTERNAL_DIR.glob("wms_cdlall*GetCapabilities*"))
        cdl_path = cands[0] if cands else None

    if cdl_path and cdl_path.is_file():
        CDL_WMS_BASE = parse_cdl_wms_base_from_capabilities(cdl_path)
        print(f"[config] CDL caps: {cdl_path.name} -> {CDL_WMS_BASE}")
    else:
        print(f"[config] CDL: using default CDL_WMS_BASE={CDL_WMS_BASE}")


def get_available_ndvi_layers(year: int) -> list[str]:
    """
    Query the WMS GetCapabilities to get all available NDVI weekly layer names
    for a given year. More reliable than constructing names manually because the
    server controls exactly which weeks exist.
    """
    url = (
        f"{CROPSMART_WMS}"
        f"?map={ndvi_weekly_map_param(year)}"
        f"&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"wms": "http://www.opengis.net/wms"}
        names = [
            el.text for el in root.findall(".//wms:Layer/wms:Name", ns)
            if el.text and el.text.startswith("NDVI-WEEKLY_") and "." in el.text
        ]
        return names
    except Exception as e:
        print(f"    [WARN] Could not fetch NDVI capabilities for {year}: {e}")
        return []


def get_available_smap_layers(year: int, stat: str = "AVERAGE") -> list[str]:
    """Query SMAP WMS GetCapabilities and return available weekly AVERAGE layer names."""
    url = (
        f"{CROPSMART_WMS}"
        f"?map={smap_weekly_map_param(year)}"
        f"&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"wms": "http://www.opengis.net/wms"}
        names = [
            el.text for el in root.findall(".//wms:Layer/wms:Name", ns)
            if el.text and el.text.startswith("SMAP-9KM-WEEKLY-TOP_") and f"_{stat}" in el.text
        ]
        return names
    except Exception as e:
        print(f"    [WARN] Could not fetch SMAP capabilities for {year}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════
# Core download function
# ═══════════════════════════════════════════════════════════════════════════

def download_geotiff(
    wms_base: str,
    layer: str,
    out_path: Path,
    extra_params: dict | None = None,
    crs: str = STUDY_CRS,
    bbox: tuple = STUDY_BBOX,
    width: int = IMG_WIDTH,
    height: int = IMG_HEIGHT,
) -> bool:
    """
    Download a single WMS layer as a GeoTIFF and save to out_path.

    Parameters
    ----------
    wms_base : str
        Base WMS URL (without query parameters).
    layer : str
        WMS layer name to request.
    out_path : Path
        Output file path (.tif).
    extra_params : dict or None
        Additional URL parameters (e.g., MAP parameter for mapserv).
    crs : str
        Coordinate reference system for the request.
    bbox : tuple
        (xmin, ymin, xmax, ymax) in the CRS units.
    width, height : int
        Requested image dimensions in pixels.

    Returns
    -------
    bool
        True if downloaded successfully, False if failed.
    """
    if out_path.exists():
        print(f"    [SKIP] Already exists: {out_path.name}")
        return True

    params = {
        "SERVICE":     "WMS",
        "VERSION":     "1.3.0",
        "REQUEST":     "GetMap",
        "LAYERS":      layer,
        "CRS":         crs,
        "BBOX":        ",".join(str(v) for v in bbox),
        "FORMAT":      "image/tiff",
        "TRANSPARENT": "true",
        "WIDTH":       str(width),
        "HEIGHT":      str(height),
    }
    if extra_params:
        params.update(extra_params)

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(wms_base, params=params, timeout=120)
            resp.raise_for_status()

            # Check the response is actually a TIFF (not an XML error)
            content_type = resp.headers.get("Content-Type", "")
            if "tiff" not in content_type and "image" not in content_type:
                print(f"    [WARN] Unexpected content-type '{content_type}' for {layer}")
                print(f"           Response snippet: {resp.content[:200]}")
                return False

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(resp.content)
            print(f"    [OK]   {out_path.name}  ({len(resp.content)/1024:.0f} KB)")
            return True

        except requests.RequestException as e:
            print(f"    [ERR]  Attempt {attempt}/{RETRY_ATTEMPTS} failed for {layer}: {e}")
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_S)

    return False


# ═══════════════════════════════════════════════════════════════════════════
# Dataset-specific download routines
# ═══════════════════════════════════════════════════════════════════════════

def download_cdl(years: list[int]) -> None:
    """
    Download CDL GeoTIFFs for each year.

    NOTE: CDL is 30m resolution. A single WMS tile at 2048×1520 px covers
    the study area at ~320m/px — useful for inspection and rotation analysis.
    For full 30m resolution you would need WCS (Web Coverage Service) or
    tiled downloads. For this challenge 320m is a valid starting point for
    rotation analysis; adjust WIDTH/HEIGHT for finer detail.

    For true 30m over Iowa+Nebraska (656km×485km) you'd need:
    Width = 656000/30 ≈ 21867 px, Height = 485000/30 ≈ 16167 px
    which is within the CropScape WMS max (check server limits first).
    """
    print("\n══ Downloading CDL ══")
    for year in years:
        layer    = cdl_layer_name(year)
        out_path = RAW_CDL / f"cdl_{year}_iowa_nebraska_5070.tif"
        print(f"  Year {year} → {layer}")
        download_geotiff(CDL_WMS_BASE, layer, out_path)
        time.sleep(INTER_REQUEST_DELAY_S)


def download_ndvi(years: list[int], growing_season_only: bool = True) -> None:
    """
    Download NDVI weekly GeoTIFFs.

    For each year, first queries GetCapabilities to get the exact list of
    available layer names (more reliable than constructing them manually).
    Then filters to growing-season weeks if requested.
    """
    print("\n══ Downloading NDVI Weekly ══")
    for year in years:
        print(f"\n  Year {year} — fetching available layers...")
        layers = get_available_ndvi_layers(year)
        if not layers:
            print(f"    [WARN] No layers found for {year}, skipping.")
            continue

        if growing_season_only:
            # Keep only growing-season weeks (weeks 18–43)
            def is_growing_season(name: str) -> bool:
                try:
                    week_num = int(name.split("_")[2])
                    return week_num in GROWING_SEASON_WEEKS
                except (IndexError, ValueError):
                    return False
            layers = [l for l in layers if is_growing_season(l)]

        print(f"    {len(layers)} layers to download")
        map_param = ndvi_weekly_map_param(year)

        for layer in layers:
            # Filename: NDVI-WEEKLY_2022_18_2022.05.02_2022.05.08.tif
            out_path = RAW_NDVI / f"{layer}.tif"
            download_geotiff(
                CROPSMART_WMS,
                layer,
                out_path,
                extra_params={"map": map_param},
            )
            time.sleep(INTER_REQUEST_DELAY_S)


def download_smap(years: list[int], stat: str = "AVERAGE") -> None:
    """
    Download SMAP weekly GeoTIFFs (all 52 weeks per year for baseline climatology).
    Downloads the AVERAGE statistic by default.
    """
    print("\n══ Downloading SMAP Weekly (AVERAGE) ══")
    for year in years:
        print(f"\n  Year {year} — fetching available layers...")
        layers = get_available_smap_layers(year, stat=stat)
        if not layers:
            print(f"    [WARN] No layers found for {year}, skipping.")
            continue

        print(f"    {len(layers)} layers to download")
        map_param = smap_weekly_map_param(year)

        for layer in layers:
            out_path = RAW_SMAP / f"{layer}.tif"
            download_geotiff(
                CROPSMART_WMS,
                layer,
                out_path,
                extra_params={"map": map_param},
            )
            time.sleep(INTER_REQUEST_DELAY_S)


# ═══════════════════════════════════════════════════════════════════════════
# Summary / dry-run utility
# ═══════════════════════════════════════════════════════════════════════════

def print_download_plan(
    cdl_years: list[int] | None = None,
    ndvi_years: list[int] | None = None,
    smap_years: list[int] | None = None,
) -> None:
    """Print a summary of what will be downloaded without making any requests."""
    print("\n══ DOWNLOAD PLAN ══")

    cy = CDL_YEARS if cdl_years is None else cdl_years
    ny = NDVI_YEARS if ndvi_years is None else ndvi_years
    sy = SMAP_YEARS if smap_years is None else smap_years

    cdl_files = len(cy)
    ndvi_files = len(ny) * len(GROWING_SEASON_WEEKS)
    smap_files = len(sy) * 52  # all 52 weeks per year for baseline

    cdl_range = f"{cy[0]}-{cy[-1]}" if cy else "(none)"
    ndvi_range = f"{ny[0]}-{ny[-1]}" if ny else "(none)"
    smap_range = f"{sy[0]}-{sy[-1]}" if sy else "(none)"

    print(f"\nCDL  ({len(cy)} years × 1 file/year; {cdl_range}):")
    print(f"  Files: {cdl_files}")
    print(f"  Approx size: {cdl_files * 3:.0f} MB  (est. ~3 MB/file at 2048px)")
    print(f"  Destination: {RAW_CDL.relative_to(REPO_ROOT)}/")

    print(f"\nNDVI ({len(ny)} years × ~{len(GROWING_SEASON_WEEKS)} weeks/year — growing season only; {ndvi_range}):")
    print(f"  Files: {ndvi_files}")
    print(f"  Approx size: {ndvi_files * 2:.0f} MB  (est. ~2 MB/file at 2048px)")
    print(f"  Destination: {RAW_NDVI.relative_to(REPO_ROOT)}/")

    print(f"\nSMAP ({len(sy)} years × 52 weeks/year — all weeks for baseline; {smap_range}):")
    print(f"  Files: {smap_files}")
    print(f"  Approx size: {smap_files * 0.5:.0f} MB  (est. ~0.5 MB/file — 9km coarser)")
    print(f"  Destination: {RAW_SMAP.relative_to(REPO_ROOT)}/")

    total_files = cdl_files + ndvi_files + smap_files
    total_mb    = cdl_files * 3 + ndvi_files * 2 + smap_files * 0.5
    print(f"\nTotal: {total_files} files, est. {total_mb/1024:.1f} GB")
    print(f"Est. download time at 10 MB/s + 1s delay: "
          f"{(total_files * 1 + total_mb/10)/60:.0f} minutes")
    print("\nRun with --dry-run=False to start downloading.")


def layer_name_examples() -> None:
    """Print example layer names to verify naming conventions."""
    print("\n══ LAYER NAME EXAMPLES ══")
    print("\nCDL:")
    for y in [2008, 2017, 2025]:
        print(f"  {cdl_layer_name(y)}")
    print("\nNDVI Weekly (week 20 = ~mid May):")
    for y in [2000, 2013, 2026]:
        print(f"  {ndvi_weekly_layer_name(y, 20)}")
    print("\nSMAP Weekly AVERAGE (week 30 = ~late July):")
    for y in [2015, 2020, 2025]:
        print(f"  {smap_weekly_layer_name(y, 30)}")


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Download CropSmart data (CDL, NDVI, SMAP) via WMS GeoTIFF."
    )
    parser.add_argument(
        "--no-external-config",
        action="store_true",
        help="Do not load WMS/map= settings from data/external GetCapabilities.",
    )
    parser.add_argument(
        "--ndvi-capabilities",
        type=Path,
        default=None,
        help="Path to saved NDVI weekly GetCapabilities XML (default: latest data/external/NDVI-WEEKLY_*.map).",
    )
    parser.add_argument(
        "--smap-capabilities",
        type=Path,
        default=None,
        help="Path to saved SMAP weekly GetCapabilities XML (default: latest data/external/SMAP-9KM-WEEKLY-TOP_*.map).",
    )
    parser.add_argument(
        "--cdl-capabilities",
        type=Path,
        default=None,
        help="Path to saved CDL wms_cdlall GetCapabilities XML (default: data/external/wms_cdlall*... if present).",
    )
    parser.add_argument(
        "--dataset",
        choices=["all", "cdl", "ndvi", "smap", "plan", "names"],
        default="plan",
        help=(
            "Which dataset to download. "
            "'plan' prints the download plan without downloading. "
            "'names' prints example layer names."
        ),
    )
    parser.add_argument("--year",  type=int, default=None, help="Single year to download (overrides year range).")
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Only download catalog years >= this (applies to each selected dataset).",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=None,
        help="Only download catalog years <= this.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue after the latest calendar year already present under data/raw/ "
            "(per dataset: CDL, NDVI, or SMAP). Combine with --min-year to raise the floor further."
        ),
    )
    parser.add_argument("--stat",  default="AVERAGE",      help="SMAP statistic: AVERAGE or MAX.")
    parser.add_argument("--width", type=int, default=IMG_WIDTH,   help="Output image width in pixels.")
    parser.add_argument("--height",type=int, default=IMG_HEIGHT,  help="Output image height in pixels.")
    args = parser.parse_args()

    if not args.no_external_config:
        configure_from_external(
            ndvi_caps=args.ndvi_capabilities,
            smap_caps=args.smap_capabilities,
            cdl_caps=args.cdl_capabilities,
        )

    if args.dataset == "plan":
        if args.resume or args.min_year is not None or args.max_year is not None:
            ca, na, sa = resolve_download_years(
                "all", args.year, args.min_year, args.max_year, args.resume
            )
            if args.resume:
                print(
                    "[resume] Latest calendar year on disk (next download year is +1): CDL "
                    f"{latest_year_cdl_raw()!r} | NDVI {latest_year_ndvi_raw()!r} | "
                    f"SMAP {latest_year_smap_raw()!r}"
                )
            print_download_plan(ca, na, sa)
        else:
            print_download_plan()
        return
    if args.dataset == "names":
        layer_name_examples()
        return

    if args.year is not None and (args.resume or args.min_year is not None or args.max_year is not None):
        print("[warn] --year is set; --resume / --min-year / --max-year are ignored.")

    cdl_years, ndvi_years, smap_years = resolve_download_years(
        args.dataset, args.year, args.min_year, args.max_year, args.resume
    )

    if args.resume and args.dataset not in ("plan", "names"):
        bits = []
        if args.dataset in ("all", "cdl"):
            bits.append(f"CDL latest={latest_year_cdl_raw()!r}")
        if args.dataset in ("all", "ndvi"):
            bits.append(f"NDVI latest={latest_year_ndvi_raw()!r}")
        if args.dataset in ("all", "smap"):
            bits.append(f"SMAP latest={latest_year_smap_raw()!r}")
        print("[resume] " + " | ".join(bits))
    if cdl_years:
        print(f"[years] CDL: {cdl_years[0]}..{cdl_years[-1]} ({len(cdl_years)} years)")
    if ndvi_years:
        print(f"[years] NDVI: {ndvi_years[0]}..{ndvi_years[-1]} ({len(ndvi_years)} years)")
    if smap_years:
        print(f"[years] SMAP: {smap_years[0]}..{smap_years[-1]} ({len(smap_years)} years)")

    if args.dataset in ("all", "cdl"):
        download_cdl(cdl_years)
    if args.dataset in ("all", "ndvi"):
        download_ndvi(ndvi_years)
    if args.dataset in ("all", "smap"):
        download_smap(smap_years, stat=args.stat)

    print("\n✓ Download complete.")


if __name__ == "__main__":
    main()
