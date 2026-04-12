"""Regenerate NB05-style per-state CSV + bar chart when boundaries work (e.g. after nbconvert without network)."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from rasterio.transform import Affine, xy as rio_xy

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    import geopandas as gpd

    with open(REPO_ROOT / "configs" / "task2_crop_rotation.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    tbl_dir = REPO_ROOT / Path(cfg["output"].get("task4_tables_dir", cfg["output"]["tables_dir"]))
    tbl_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = REPO_ROOT / cfg["output"]["figures_dir"]
    fig_dir.mkdir(parents=True, exist_ok=True)

    from src.io.cdl_parquet import load_cdl_spatial_metadata
    from src.viz.rotation_maps import load_cornbelt_state_boundaries_5070

    cls_pq = REPO_ROOT / cfg["output"]["processed_dir"] / "rotation_metrics_classified.parquet"
    meta_sp = load_cdl_spatial_metadata(REPO_ROOT)
    mdf = pd.read_parquet(cls_pq)
    tlist = meta_sp["transform"]
    aff = Affine(tlist[0], tlist[1], tlist[2], tlist[3], tlist[4], tlist[5])
    crs_s = meta_sp.get("crs") or "EPSG:5070"
    xs, ys = rio_xy(aff, mdf["iy"].to_numpy(), mdf["ix"].to_numpy(), offset="center")

    boundaries = load_cornbelt_state_boundaries_5070(REPO_ROOT)
    if boundaries is None or boundaries.empty:
        raise SystemExit("load_cornbelt_state_boundaries_5070 returned nothing (geopandas / network / shp).")

    boundaries = boundaries.to_crs(crs_s)
    name_col = next((c for c in ("NAME", "name", "NAME_1") if c in boundaries.columns), None)
    if name_col is None:
        raise SystemExit(f"No state name column in boundaries: {list(boundaries.columns)[:20]}")

    bnd = boundaries[[name_col, "geometry"]].copy()
    bnd["region"] = bnd[name_col].astype(str)
    bnd = bnd[["region", "geometry"]]
    pts = gpd.GeoDataFrame(mdf, geometry=gpd.points_from_xy(xs, ys), crs=crs_s)
    joined = gpd.sjoin(pts, bnd, how="left", predicate="within")
    if joined.index.duplicated().any():
        joined = joined[~joined.index.duplicated(keep="first")]
    joined["region"] = joined["region"].fillna("outside_configured_states")

    region_rows = []
    for reg, g in joined.groupby("region"):
        vc = g["rotation_class"].value_counts(normalize=True)
        n = len(g)
        region_rows.append(
            {
                "region": reg,
                "n_pixels": n,
                "pct_regular": round(100 * float(vc.get(0, 0)), 2),
                "pct_monoculture": round(100 * float(vc.get(1, 0)), 2),
                "pct_irregular": round(100 * float(vc.get(2, 0)), 2),
            }
        )
    reg_df = pd.DataFrame(region_rows).sort_values("region")
    date_s = date.today().strftime("%Y%m%d")
    reg_csv = tbl_dir / f"task2__areal_stats_by_region__{date_s}.csv"
    reg_df.to_csv(reg_csv, index=False)
    print("Wrote", reg_csv.relative_to(REPO_ROOT))

    plot_df = reg_df[~reg_df["region"].isin({"outside_configured_states", "full_raster_extent"})].copy()
    if len(plot_df) > 0:
        plot_df = plot_df.sort_values("pct_regular", ascending=True)
        y = np.arange(len(plot_df))
        fig, ax = plt.subplots(figsize=(10, max(6.0, 0.35 * len(plot_df))))
        pr = plot_df["pct_regular"].to_numpy()
        pm = plot_df["pct_monoculture"].to_numpy()
        pi = plot_df["pct_irregular"].to_numpy()
        ax.barh(y, pr, label="regular", color="#2ecc71")
        ax.barh(y, pm, left=pr, label="monoculture", color="#e74c3c")
        ax.barh(y, pi, left=pr + pm, label="irregular", color="#f39c12")
        ax.set_yticks(y)
        ax.set_yticklabels(plot_df["region"])
        ax.set_xlabel("% of rotation-eligible pixels in region")
        ax.set_title("Rotation class mix by state (strict YAML)")
        ax.legend(loc="lower right", fontsize=9)
        ax.set_xlim(0, 100)
        fig.tight_layout()
        pfig = fig_dir / "task2__per_state_rotation_classes.png"
        fig.savefig(pfig, dpi=200, bbox_inches="tight")
        plt.close()
        print("Wrote", pfig.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
