"""SMAP weekly baseline climatology and event-window z-score anomalies (Task 3, Parquet path)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.io.smap_weekly_parquet import (
    load_smap_year_metadata,
    smap_wide_parquet_path,
    wcol_for_iso_week,
)


def event_windows_from_cfg(cfg: dict) -> list[dict]:
    """
    Return ``event_windows`` list from YAML, or migrate legacy single ``event_window`` block.
    """
    wins = cfg.get("event_windows")
    if isinstance(wins, list) and wins:
        return [dict(w) for w in wins]
    ev = cfg.get("event_window") or {}
    return [
        {
            "id": "midwest_flood_2019",
            "label": str(ev.get("label", "2019 Midwest / Mississippi spring flood")),
            "year": 2019,
            "start_date": str(ev["start_date"]),
            "end_date": str(ev["end_date"]),
            "duration_mode": "wet_above",
            "duration_z": 1.5,
        }
    ]


def load_rotation_eligible_pixels(repo_root: Path) -> pd.DataFrame:
    """Unique ``(iy, ix)`` from Task 2 rotation metrics (reduces SMAP join size)."""
    p = repo_root / "data" / "processed" / "task2" / "rotation_metrics.parquet"
    if not p.is_file():
        raise FileNotFoundError(f"Missing {p} — run Task 2 notebook 02 first.")
    df = pd.read_parquet(p, columns=["iy", "ix"])
    return df.drop_duplicates().reset_index(drop=True)


def attach_cdl_2019(repo_root: Path, pixels: pd.DataFrame) -> pd.DataFrame:
    from src.io.cdl_parquet import cdl_wide_parquet_path

    pq = cdl_wide_parquet_path(repo_root)
    cdl = pd.read_parquet(pq, columns=["iy", "ix", "cdl_2019"])
    return pixels.merge(cdl, on=["iy", "ix"], how="left")


def baseline_climatology_iso_weeks(
    repo_root: Path,
    baseline_years: Iterable[int],
    iso_weeks: Iterable[int],
    pixels: pd.DataFrame,
    *,
    min_count: int = 2,
) -> pd.DataFrame:
    """
    For each ISO week in ``iso_weeks``, stack SMAP ``m³/m³`` across ``baseline_years`` at each pixel.

    Returns columns: ``iy``, ``ix``, ``iso_week``, ``sm_mean``, ``sm_std``, ``sm_count``.
    """
    base = sorted(int(y) for y in baseline_years)
    rows_out: list[pd.DataFrame] = []
    px = pixels[["iy", "ix"]].copy()

    for wk in sorted(set(int(w) for w in iso_weeks)):
        parts: list[pd.DataFrame] = []
        for y in base:
            meta = load_smap_year_metadata(repo_root, y)
            wcol = wcol_for_iso_week(meta, wk)
            if wcol is None:
                continue
            path = smap_wide_parquet_path(repo_root, y)
            df = pd.read_parquet(path, columns=["iy", "ix", wcol]).merge(px, on=["iy", "ix"], how="inner")
            df = df.rename(columns={wcol: f"sm_{y}"}).set_index(["iy", "ix"])
            parts.append(df)
        if not parts:
            continue
        wide = parts[0]
        for p in parts[1:]:
            wide = wide.join(p, how="outer")
        sm_mean = wide.mean(axis=1, skipna=True)
        sm_std = wide.std(axis=1, ddof=1, skipna=True)
        sm_count = wide.count(axis=1)
        ok = sm_count >= min_count
        block = pd.DataFrame(
            {
                "iy": wide.index.get_level_values(0).to_numpy(),
                "ix": wide.index.get_level_values(1).to_numpy(),
                "iso_week": wk,
                "sm_mean": sm_mean.to_numpy(),
                "sm_std": np.where(ok.to_numpy(), sm_std.to_numpy(), np.nan),
                "sm_count": sm_count.to_numpy().astype(np.int16),
            }
        )
        rows_out.append(block)

    if not rows_out:
        return pd.DataFrame(columns=["iy", "ix", "iso_week", "sm_mean", "sm_std", "sm_count"])
    return pd.concat(rows_out, ignore_index=True)


def compute_event_anomalies(
    repo_root: Path,
    event_year: int,
    event_specs: list[tuple[str, str, int]],
    clim: pd.DataFrame,
    pixels: pd.DataFrame,
    *,
    z_clip: float = 5.0,
    sigma_floor: float = 1e-4,
) -> pd.DataFrame:
    """
    ``event_specs`` is ``(wcol, date_str, iso_week)`` from ``src.io.smap_weekly_parquet.event_week_columns``.

    ``pixels`` must include ``iy``, ``ix`` (and optionally ``cdl_2019`` for downstream tables).
    """
    path = smap_wide_parquet_path(repo_root, event_year)
    use = pixels[["iy", "ix"]].copy()
    if "cdl_2019" in pixels.columns:
        use = pixels[["iy", "ix", "cdl_2019"]].copy()

    out: list[pd.DataFrame] = []
    for wcol, date_str, iso_w in event_specs:
        df = pd.read_parquet(path, columns=["iy", "ix", wcol]).merge(use, on=["iy", "ix"], how="inner")
        df = df.rename(columns={wcol: "sm_obs"})
        df["iso_week"] = int(iso_w)
        merged = df.merge(
            clim,
            on=["iy", "ix", "iso_week"],
            how="left",
            suffixes=("", "_clim"),
        )
        denom = merged["sm_std"].replace(0, np.nan).fillna(sigma_floor)
        merged["z_score"] = ((merged["sm_obs"] - merged["sm_mean"]) / denom).clip(-z_clip, z_clip)
        merged["date"] = date_str
        out.append(merged)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
