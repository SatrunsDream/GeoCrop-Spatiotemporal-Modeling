# Disclaimer: Fully AI-generated.
"""Aggregate SMAP anomaly tables by state and CDL crop (Task 3)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.io.cdl_parquet import load_cdl_spatial_metadata
from src.viz.rotation_maps import load_cornbelt_state_boundaries_5070
from src.viz.task3_maps import pixel_xy_from_metadata


CDL_CROP_NAMES: dict[int, str] = {
    1: "corn",
    5: "soybean",
    26: "winter_wheat",
    28: "oats",
}


def attach_state_name(
    repo_root: Path,
    df: pd.DataFrame,
    *,
    crs: str = "EPSG:5070",
    chunk_size: int = 400_000,
) -> pd.DataFrame:
    """Point-in-polygon join to Corn Belt state polygons (``NAME`` / ``name`` column).

    Chunked so anomaly tables with **tens of millions** of pixel-week rows do not
    build one giant ``GeoDataFrame`` or one giant ``rio_xy`` allocation.
    """
    try:
        import geopandas as gpd
    except ImportError:
        df = df.copy()
        df["state"] = "unknown"
        return df

    meta = load_cdl_spatial_metadata(Path(repo_root))
    crs_s = str(meta.get("crs") or crs)
    states = load_cornbelt_state_boundaries_5070(repo_root)
    if states is None or states.empty:
        out = df.copy()
        out["state"] = "unknown"
        return out

    states = states.to_crs(crs_s)
    name_col = next((c for c in ("NAME", "name", "NAME_1") if c in states.columns), None)
    if name_col is None:
        out = df.copy()
        out["state"] = "unknown"
        return out

    b = states[[name_col, "geometry"]].rename(columns={name_col: "state"})
    n = len(df)
    state_vals: list[np.ndarray] = []
    cs = max(50_000, int(chunk_size))
    for start in range(0, n, cs):
        end = min(start + cs, n)
        sub = df.iloc[start:end].reset_index(drop=True)
        iy = sub["iy"].to_numpy()
        ix = sub["ix"].to_numpy()
        xs, ys = pixel_xy_from_metadata(meta, iy, ix, chunk_size=min(cs, 200_000))
        g = gpd.GeoDataFrame(sub, geometry=gpd.points_from_xy(xs, ys), crs=crs_s)
        j = gpd.sjoin(g, b, how="left", predicate="within")
        if j.index.duplicated().any():
            j = j[~j.index.duplicated(keep="first")]
        st = j["state"].fillna("outside").to_numpy()
        state_vals.append(np.asarray(st, dtype=object))

    out = df.copy()
    out["state"] = np.concatenate(state_vals) if state_vals else "unknown"
    return out


def state_crop_anomaly_summary(anom: pd.DataFrame) -> pd.DataFrame:
    """
    ``anom`` must include ``z_score``, ``cdl_label`` (or legacy ``cdl_2019``), and ``state``.

    One row per (state, crop_label) for CDL codes in ``CDL_CROP_NAMES``.
    When NIG columns are present, adds ``mean_nig_p_drought`` and ``frac_pdrought_lt_0p1``.
    """
    has_nig = "nig_p_drought" in anom.columns
    x = anom.copy()
    cdl_col = "cdl_label" if "cdl_label" in x.columns else "cdl_2019"
    x["crop"] = x[cdl_col].map(CDL_CROP_NAMES)
    x = x[x["crop"].notna()]
    rows = []
    for (st, cr), g in x.groupby(["state", "crop"]):
        mean_z = float(g["z_score"].mean())
        max_z = float(g["z_score"].max())
        frac_gt_1 = float(np.mean(g["z_score"].to_numpy() > 1.0))
        frac_gt_1p5 = float(np.mean(g["z_score"].to_numpy() > 1.5))
        row = {
            "state": st,
            "crop": cr,
            "mean_z": round(mean_z, 4),
            "max_z": round(max_z, 4),
            "frac_obs_z_gt_1": round(frac_gt_1, 4),
            "frac_obs_z_gt_1p5": round(frac_gt_1p5, 4),
            "n_pixel_weeks": int(len(g)),
        }
        if has_nig:
            pd_arr = g["nig_p_drought"].to_numpy()
            row["mean_nig_p_drought"] = round(float(np.nanmean(pd_arr)), 4)
            row["frac_pdrought_lt_0p1"] = round(float(np.nanmean(pd_arr < 0.1)), 4)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["state", "crop"]).reset_index(drop=True)
