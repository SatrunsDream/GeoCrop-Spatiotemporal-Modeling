"""
Load multi-year CDL from **processed** wide Parquet (``data/processed/cdl/``).

Task 2 uses this path instead of interim NetCDF so notebooks stay aligned with
``process_interim_to_parquet.py`` output and ``cdl_stack_spatial_metadata.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def cdl_wide_parquet_path(repo_root: Path) -> Path:
    return repo_root / "data" / "processed" / "cdl" / "cdl_stack_wide.parquet"


def cdl_spatial_metadata_path(repo_root: Path) -> Path:
    return repo_root / "data" / "processed" / "cdl" / "cdl_stack_spatial_metadata.json"


def load_cdl_spatial_metadata(repo_root: Path) -> dict:
    p = cdl_spatial_metadata_path(repo_root)
    if not p.is_file():
        raise FileNotFoundError(
            f"Missing {p}. Run: python scripts/process_interim_to_parquet.py --dataset cdl"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def load_cdl_wide_years(repo_root: Path, years: list[int]) -> pd.DataFrame:
    """
    Read ``iy``, ``ix``, and ``cdl_<year>`` columns; sort by ``(iy, ix)`` to match
    raster row-major order used when building the Parquet file.
    """
    pq = cdl_wide_parquet_path(repo_root)
    if not pq.is_file():
        raise FileNotFoundError(
            f"Missing {pq}. Run: python scripts/process_interim_to_parquet.py --dataset cdl"
        )
    cols = ["iy", "ix"] + [f"cdl_{int(y)}" for y in years]
    df = pd.read_parquet(pq, columns=cols)
    return df.sort_values(["iy", "ix"], kind="mergesort").reset_index(drop=True)


def wide_to_label_stack(
    df: pd.DataFrame,
    years: list[int],
    height: int,
    width: int,
) -> np.ndarray:
    """
    Build ``(n_years, height, width)`` int16 stack from sorted wide Parquet.

    Raises if row count does not equal ``height * width``.
    """
    n = len(df)
    if n != height * width:
        raise ValueError(
            f"Parquet row count {n} != height*width ({height}*{width}={height * width}). "
            "Verify cdl_stack_spatial_metadata.json matches the wide export."
        )
    out = np.empty((len(years), height, width), dtype=np.int16)
    for i, y in enumerate(years):
        out[i] = df[f"cdl_{int(y)}"].to_numpy(dtype=np.int16).reshape(height, width)
    return out


def year_range_inclusive(year_range: list[int]) -> list[int]:
    """``[y0, y1]`` inclusive → list of calendar years."""
    y0, y1 = int(year_range[0]), int(year_range[1])
    return list(range(y0, y1 + 1))
