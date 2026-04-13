# Disclaimer: Fully AI-generated.
"""Load weekly SMAP from processed wide Parquet (Task 3) — no interim NetCDF required."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def smap_processed_dir(repo_root: Path) -> Path:
    return repo_root / "data" / "processed" / "smap"


def smap_wide_parquet_path(repo_root: Path, year: int) -> Path:
    return smap_processed_dir(repo_root) / f"smap_weekly_{int(year)}_wide.parquet"


def smap_metadata_path(repo_root: Path, year: int) -> Path:
    return smap_processed_dir(repo_root) / f"smap_weekly_{int(year)}_metadata.json"


def load_smap_year_metadata(repo_root: Path, year: int) -> dict[str, Any]:
    p = smap_metadata_path(repo_root, year)
    if not p.is_file():
        raise FileNotFoundError(f"Missing SMAP metadata: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def wide_sm_columns(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("wide_columns") or []
    return [c for c in raw if isinstance(c, str) and c.startswith("w")]


def iso_week_for_w_index(meta: dict[str, Any], w_index: int) -> int | None:
    dates = meta.get("time_start_day") or []
    if w_index < 0 or w_index >= len(dates):
        return None
    return int(pd.Timestamp(dates[w_index]).isocalendar().week)


def wcol_for_iso_week(meta: dict[str, Any], iso_week: int) -> str | None:
    """First ``w###`` column in this calendar year whose ISO week equals ``iso_week``."""
    dates = meta.get("time_start_day") or []
    wcols = set(wide_sm_columns(meta))
    target = int(iso_week)
    for j, date_str in enumerate(dates):
        wcol = f"w{j:03d}"
        if wcol not in wcols:
            continue
        if int(pd.Timestamp(date_str).isocalendar().week) == target:
            return wcol
    return None


def event_week_columns(meta: dict[str, Any], start: str, end: str) -> list[tuple[str, str, int]]:
    """
    List (wcol, date_str, iso_week) for columns whose start date falls in [start, end] inclusive.

    ``time_start_day[k]`` aligns with week column ``w{k:03d}`` (same index k).
    """
    dates = meta.get("time_start_day") or []
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    out: list[tuple[str, str, int]] = []
    for j, date_str in enumerate(dates):
        wcol = f"w{j:03d}"
        if wcol not in set(wide_sm_columns(meta)):
            continue
        ts = pd.Timestamp(date_str)
        if ts < t0 or ts > t1:
            continue
        out.append((wcol, str(date_str)[:10], int(ts.isocalendar().week)))
    return out


# Backward-compatible name used in early Task 3 drafts
event_week_columns_2019 = event_week_columns
