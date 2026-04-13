# Disclaimer: Fully AI-generated.
"""
build_interim_data.py — Convert raw downloaded GeoTIFFs → interim NetCDF / Parquet.

Run this AFTER download_data.py has populated data/raw/.

Which years are stacked is defined in src.utils.nafsi_catalog (NAFSI brief §3).

Raw GeoTIFF filenames follow WMS layer names documented in the CropSmart
GetCapabilities snapshots under data/external/ (e.g. NDVI-WEEKLY_*.map,
SMAP-9KM-WEEKLY-TOP_*.map as saved XML).

What this script does:
  1. Stacks all CDL annual GeoTIFFs into a single multi-year xarray Dataset  →  data/interim/cdl/cdl_stack_{years}.nc
  2. Stacks all NDVI weekly growing-season GeoTIFFs → data/interim/ndvi/ndvi_weekly_{year}.nc  (one per year)
  3. Stacks all SMAP weekly GeoTIFFs → data/interim/smap/smap_weekly_{year}.nc  (one per year)

These interim NetCDF files are what the notebooks consume — no GeoTIFF
reading inside notebooks.

Usage:
  python scripts/build_interim_data.py --dataset all
  python scripts/build_interim_data.py --dataset cdl
  python scripts/build_interim_data.py --dataset ndvi --year 2022
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.nafsi_catalog import CDL_YEARS, NDVI_YEARS, SMAP_YEARS

# ── Repo paths ───────────────────────────────────────────────────────────────
RAW_CDL   = REPO_ROOT / "data" / "raw" / "cdl"
RAW_NDVI  = REPO_ROOT / "data" / "raw" / "ndvi"
RAW_SMAP  = REPO_ROOT / "data" / "raw" / "smap"
INTERIM     = REPO_ROOT / "data" / "interim"
INTERIM_CDL  = INTERIM / "cdl"
INTERIM_NDVI = INTERIM / "ndvi"
INTERIM_SMAP = INTERIM / "smap"
INTERIM.mkdir(parents=True, exist_ok=True)
INTERIM_CDL.mkdir(parents=True, exist_ok=True)
INTERIM_NDVI.mkdir(parents=True, exist_ok=True)
INTERIM_SMAP.mkdir(parents=True, exist_ok=True)

CDL_RAW_SUFFIX = "cornbelt_5070"
CDL_RAW_LEGACY_SUFFIX = "iowa_nebraska_5070"


def cdl_raw_tif_path(year: int) -> Path | None:
    """Prefer Corn Belt downloads; fall back to legacy Iowa+Nebraska filenames."""
    p_new = RAW_CDL / f"cdl_{year}_{CDL_RAW_SUFFIX}.tif"
    p_old = RAW_CDL / f"cdl_{year}_{CDL_RAW_LEGACY_SUFFIX}.tif"
    if p_new.is_file():
        return p_new
    if p_old.is_file():
        return p_old
    return None


# ── Layer name parsers ───────────────────────────────────────────────────────

def parse_ndvi_layer_date(filename: str) -> datetime.date | None:
    """
    Extract the start date of an NDVI weekly layer from its filename.
    Pattern: NDVI-WEEKLY_{YEAR}_{WEEK}_{YEAR}.{MM}.{DD}_{YEAR}.{MM}.{DD}.tif
    Returns the start date (Monday) of the week.
    """
    m = re.search(r"NDVI-WEEKLY_\d{4}_\d{2}_(\d{4})\.(\d{2})\.(\d{2})_", filename)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_smap_layer_date(filename: str) -> datetime.date | None:
    """
    Extract the start date of a SMAP weekly layer from its filename.
    Pattern: SMAP-9KM-WEEKLY-TOP_{YEAR}_{WEEK}_{YEAR}.{MM}.{DD}_{YEAR}.{MM}.{DD}_AVERAGE.tif
    """
    m = re.search(r"SMAP-9KM-WEEKLY-TOP_\d{4}_\d{2}_(\d{4})\.(\d{2})\.(\d{2})_", filename)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


# ── Build functions ──────────────────────────────────────────────────────────

def build_cdl_stack(cdl_years: list[int]) -> None:
    """
    Stack all annual CDL GeoTIFFs into a single multi-year xarray Dataset.
    Saves to data/interim/cdl/cdl_stack_{first_year}_{last_year}.nc
    """
    try:
        import xarray as xr
        import rioxarray  # noqa: F401 — needed for .rio accessor
    except ImportError:
        print("[ERR] xarray and rioxarray are required. Run: pip install xarray rioxarray")
        return

    print("\n══ Building CDL stack ══")
    arrays = []
    years_found = []

    for year in sorted(cdl_years):
        tif = cdl_raw_tif_path(year)
        if tif is None:
            print(
                f"  [SKIP] cdl_{year}_{CDL_RAW_SUFFIX}.tif (or legacy _{CDL_RAW_LEGACY_SUFFIX}) "
                "not found — run download_data.py first"
            )
            continue
        da = xr.open_dataarray(tif, engine="rasterio").squeeze("band", drop=True)
        da = da.expand_dims({"year": [year]})
        da.name = "cdl"
        arrays.append(da)
        years_found.append(year)
        print(f"  [OK]  {tif.name}  shape={da.shape}")

    if not arrays:
        print("  [WARN] No CDL files found.")
        return

    stack = xr.concat(arrays, dim="year")
    stack.attrs["description"] = "Annual CDL crop type, Corn Belt (EPSG:5070), WMS extent from study_extent.yaml"
    stack.attrs["source"]      = "USDA NASS CropScape WMS"
    # NetCDF3 (scipy default) cannot encode uint8 CDL class codes; use int16 + NetCDF4.
    stack = stack.astype("int16")

    out = INTERIM_CDL / f"cdl_stack_{years_found[0]}_{years_found[-1]}.nc"
    stack.to_netcdf(out, engine="netcdf4")
    print(f"\n  Saved → {out.relative_to(REPO_ROOT)}  (shape: {stack.shape})")


def build_ndvi_stack(ndvi_years: list[int]) -> None:
    """
    For each year, stack all growing-season weekly NDVI GeoTIFFs into a
    (time, y, x) xarray DataArray and save to data/interim/ndvi/ndvi_weekly_{year}.nc.
    """
    try:
        import xarray as xr
        import rioxarray  # noqa: F401
    except ImportError:
        print("[ERR] xarray and rioxarray are required.")
        return

    print("\n══ Building NDVI stacks ══")
    for year in sorted(ndvi_years):
        tifs = sorted(RAW_NDVI.glob(f"NDVI-WEEKLY_{year}_*.tif"))
        if not tifs:
            print(f"  [SKIP] No NDVI files for {year}")
            continue

        arrays = []
        for tif in tifs:
            date = parse_ndvi_layer_date(tif.name)
            if date is None:
                continue
            da = xr.open_dataarray(tif, engine="rasterio").squeeze("band", drop=True)
            da = da.expand_dims({"time": [np.datetime64(date, "D")]})
            arrays.append(da)

        if not arrays:
            continue

        stack = xr.concat(arrays, dim="time").sortby("time")
        stack.name = "ndvi"
        stack.attrs["description"] = (
            f"NDVI weekly growing season {year}, Corn Belt (EPSG:5070), extent from study_extent.yaml"
        )
        stack.attrs["source"]      = "CropSmart/NASSGEO WMS — MODIS 250m"

        out = INTERIM_NDVI / f"ndvi_weekly_{year}.nc"
        stack.to_netcdf(out, engine="netcdf4")
        print(f"  Saved → {out.relative_to(REPO_ROOT)}  (time={len(arrays)}, shape={stack.shape})")


def build_smap_stack(smap_years: list[int]) -> None:
    """
    For each year, stack all 52 weekly SMAP AVERAGE GeoTIFFs into a
    (time, y, x) xarray DataArray and save to data/interim/smap/smap_weekly_{year}.nc.
    """
    try:
        import xarray as xr
        import rioxarray  # noqa: F401
    except ImportError:
        print("[ERR] xarray and rioxarray are required.")
        return

    print("\n══ Building SMAP stacks ══")
    for year in sorted(smap_years):
        tifs = sorted(RAW_SMAP.glob(f"SMAP-9KM-WEEKLY-TOP_{year}_*_AVERAGE.tif"))
        if not tifs:
            print(f"  [SKIP] No SMAP files for {year}")
            continue

        arrays = []
        for tif in tifs:
            date = parse_smap_layer_date(tif.name)
            if date is None:
                continue
            da = xr.open_dataarray(tif, engine="rasterio").squeeze("band", drop=True)
            da = da.expand_dims({"time": [np.datetime64(date, "D")]})
            arrays.append(da)

        if not arrays:
            continue

        stack = xr.concat(arrays, dim="time").sortby("time")
        stack.name = "sm_surface"
        stack.attrs["description"] = (
            f"SMAP weekly surface soil moisture (9km) {year}, Corn Belt (EPSG:5070), extent from study_extent.yaml"
        )
        stack.attrs["source"]      = "CropSmart/NASSGEO WMS — SMAP L4"
        stack.attrs["units"]       = "m3/m3 (scaled from WMS — verify scale factor)"

        out = INTERIM_SMAP / f"smap_weekly_{year}.nc"
        stack.to_netcdf(out, engine="netcdf4")
        print(f"  Saved → {out.relative_to(REPO_ROOT)}  (time={len(arrays)}, shape={stack.shape})")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Stack raw GeoTIFFs into interim NetCDF files for notebook use."
    )
    parser.add_argument("--dataset", choices=["all", "cdl", "ndvi", "smap"], default="all")
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()

    cdl_years  = [args.year] if args.year else CDL_YEARS
    ndvi_years = [args.year] if args.year else NDVI_YEARS
    smap_years = [args.year] if args.year else SMAP_YEARS

    if args.dataset in ("all", "cdl"):
        build_cdl_stack(cdl_years)
    if args.dataset in ("all", "ndvi"):
        build_ndvi_stack(ndvi_years)
    if args.dataset in ("all", "smap"):
        build_smap_stack(smap_years)

    print("\n✓ Interim data build complete.")


if __name__ == "__main__":
    main()
