# Disclaimer: Fully AI-generated.
"""
Task 4 — rolling panel feature construction (CDL + NDVI + SMAP + optional externals).

Implements cropland mask, CDL history / rotation features, NDVI (scaled /250),
coarse SMAP context (parent cell iy//stride), and panel assembly per plan.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter
from tqdm.auto import tqdm

# ---------------------------------------------------------------------------
# Grid / mask
# ---------------------------------------------------------------------------


def load_grid_meta(repo_root: Path) -> dict[str, Any]:
    """Load grid metadata (height, width, crs, transform).

    Tries ``cdl_stack_spatial_metadata.json`` first; if absent, derives
    height/width from the CDL parquet and borrows crs/transform from the
    first available NDVI yearly metadata JSON.
    """
    meta_path = repo_root / "data" / "processed" / "cdl" / "cdl_stack_spatial_metadata.json"
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))

    import pyarrow.parquet as pq
    import pyarrow.compute as pc

    cdl_pq = repo_root / "data" / "processed" / "cdl" / "cdl_stack_wide.parquet"
    if not cdl_pq.is_file():
        raise FileNotFoundError(
            f"Neither {meta_path} nor {cdl_pq} found. "
            "Run: python scripts/process_interim_to_parquet.py --dataset cdl"
        )

    table = pq.read_table(cdl_pq, columns=["iy", "ix"])
    height = int(pc.max(table.column("iy")).as_py()) + 1
    width = int(pc.max(table.column("ix")).as_py()) + 1
    years = sorted(
        int(c.replace("cdl_", ""))
        for c in pq.read_schema(cdl_pq).names
        if c.startswith("cdl_")
    )

    meta: dict[str, Any] = {"height": height, "width": width, "years": years}

    ndvi_dir = repo_root / "data" / "processed" / "ndvi"
    ndvi_metas = sorted(ndvi_dir.glob("ndvi_weekly_*_metadata.json"))
    if ndvi_metas:
        ref = json.loads(ndvi_metas[0].read_text(encoding="utf-8"))
        meta["crs"] = ref.get("crs", "EPSG:5070")
        meta["transform"] = ref.get("transform", [])

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def build_cropland_mask(
    cdl: pd.DataFrame,
    mask_year_lo: int,
    mask_year_hi: int,
    cropland_max: int = 61,
    min_cropland_years: int = 3,
) -> pd.DataFrame:
    """
    Pixels with at least ``min_cropland_years`` years in [mask_year_lo, mask_year_hi]
    where CDL code <= cropland_max.
    Returns columns: iy, ix.
    """
    years = range(mask_year_lo, mask_year_hi + 1)
    cols = [f"cdl_{y}" for y in years if f"cdl_{y}" in cdl.columns]
    if len(cols) < min_cropland_years:
        raise ValueError(f"Not enough CDL year columns for mask: have {cols[:3]}…")
    m = cdl[cols].values
    is_crop = (m <= cropland_max) & (m >= 0)
    count = is_crop.sum(axis=1)
    keep = count >= min_cropland_years
    out = cdl.loc[keep, ["iy", "ix"]].copy().reset_index(drop=True)
    return out


def map_cdl_code_to_label(
    codes: np.ndarray,
    corn: int = 1,
    soy: int = 5,
    wheat: int = 24,
    cropland_max: int = 61,
) -> np.ndarray:
    """
    Map raw CDL codes to model labels:
    0=other_cropland, 1=corn, 2=soy, 3=winter_wheat; NaN where not cropland.
    """
    x = np.asarray(codes, dtype=np.float64)
    out = np.full(x.shape, np.nan, dtype=np.float64)
    valid = (x >= 0) & (x <= cropland_max)
    out = np.where(x == corn, 1.0, out)
    out = np.where(x == soy, 2.0, out)
    out = np.where(x == wheat, 3.0, out)
    other = valid & (x != corn) & (x != soy) & (x != wheat)
    out = np.where(other, 0.0, out)
    out = np.where(~valid, np.nan, out)
    return out


def stratified_sample_indices(
    labels: np.ndarray,
    sample_n: int,
    seed: int = 42,
) -> np.ndarray:
    """Return row indices for a class-balanced subsample of *sample_n* rows.

    *labels* is a 1-D float array (0/1/2/3/NaN from ``map_cdl_code_to_label``).
    Rows with NaN labels are excluded.  Each class gets an equal quota
    (``sample_n // n_classes``); if a class has fewer rows than its quota, all
    its rows are taken and the surplus is redistributed to the remaining classes.
    """
    rng = np.random.RandomState(seed)
    valid_mask = np.isfinite(labels)
    valid_idx = np.where(valid_mask)[0]
    valid_labels = labels[valid_idx].astype(np.int32)

    classes = np.unique(valid_labels)
    n_classes = len(classes)
    if n_classes == 0 or sample_n <= 0:
        return valid_idx

    if len(valid_idx) <= sample_n:
        return valid_idx

    per_class = {c: np.where(valid_labels == c)[0] for c in classes}

    quota = sample_n // n_classes
    chosen: list[np.ndarray] = []
    surplus = 0
    small_classes: list[int] = []
    large_classes: list[int] = []

    for c in classes:
        pool = per_class[c]
        if len(pool) <= quota:
            chosen.append(pool)
            surplus += quota - len(pool)
            small_classes.append(c)
        else:
            large_classes.append(c)

    extra_each = surplus // max(len(large_classes), 1)
    remainder = surplus - extra_each * len(large_classes)
    for i, c in enumerate(large_classes):
        pool = per_class[c]
        n_take = quota + extra_each + (1 if i < remainder else 0)
        chosen.append(rng.choice(pool, size=min(n_take, len(pool)), replace=False))

    local_idx = np.concatenate(chosen)
    return valid_idx[local_idx]


# ---------------------------------------------------------------------------
# CDL history (per target year t, prior years only) — fully vectorized
# ---------------------------------------------------------------------------


def _history_year_list(available: list[int], t: int, lookback: int) -> list[int]:
    prior = [y for y in available if y < t]
    return prior[-lookback:] if len(prior) >= lookback else prior


def _vec_max_run_length(X: np.ndarray) -> np.ndarray:
    """Vectorized max consecutive run of identical values (where >= 0).

    X : (n_pixels, n_years) int32.  Returns (n_pixels,) int32.
    Loops over the time axis (~10 iters) instead of the pixel axis (~48M).
    """
    n, L = X.shape
    if L == 0:
        return np.zeros(n, dtype=np.int32)
    valid_first = X[:, 0] >= 0
    current = np.where(valid_first, 1, 0).astype(np.int32)
    result = current.copy()
    for j in range(1, L):
        same_and_valid = (X[:, j] == X[:, j - 1]) & (X[:, j] >= 0)
        current = np.where(
            same_and_valid,
            current + 1,
            np.where(X[:, j] >= 0, 1, 0),
        )
        result = np.maximum(result, current)
    return result


def _vec_time_since(newest_first: np.ndarray, code: int) -> np.ndarray:
    """Vectorized time-since-last for a given crop code.

    newest_first : (n, L) ordered t-1, t-2, …
    Returns (n,) float32, NaN where the code never appears.
    """
    matches = newest_first == code
    idx = np.argmax(matches, axis=1)
    found = matches[np.arange(len(matches)), idx]
    result = idx.astype(np.float32)
    result[~found] = np.nan
    return result


def _vec_alternation_score(X: np.ndarray) -> np.ndarray:
    """Vectorized corn/soy alternation score.  X : (n, L) int32."""
    if X.shape[1] < 2:
        return np.zeros(X.shape[0], dtype=np.float32)
    a, b = X[:, :-1], X[:, 1:]
    valid = ((a == 1) | (a == 5)) & ((b == 1) | (b == 5))
    switches = (((a == 1) & (b == 5)) | ((a == 5) & (b == 1))) & valid
    n_valid = valid.sum(axis=1).astype(np.float32)
    safe_denom = np.maximum(n_valid, 1)
    return np.where(n_valid > 0, switches.sum(axis=1) / safe_denom, 0.0).astype(np.float32)


def _vec_pattern_distance(X: np.ndarray, pattern_len: int = 10) -> np.ndarray:
    """Vectorized hamming distance to canonical corn-soy alternations.

    X : (n, L) int32.  Returns (n,) float32.
    """
    L = X.shape[1]
    S = X[:, -pattern_len:] if L >= pattern_len else X
    cur_len = S.shape[1]
    if cur_len < pattern_len:
        pad_width = pattern_len - cur_len
        first_col = S[:, :1] if cur_len > 0 else np.full((S.shape[0], 1), -1, dtype=S.dtype)
        S = np.concatenate([np.repeat(first_col, pad_width, axis=1), S], axis=1)

    alt1 = np.tile(np.array([1, 5], dtype=np.int32), (pattern_len + 1) // 2)[:pattern_len]
    alt2 = np.tile(np.array([5, 1], dtype=np.int32), (pattern_len + 1) // 2)[:pattern_len]
    valid = S >= 0
    ham1 = ((S != alt1[None, :]) & valid).sum(axis=1)
    ham2 = ((S != alt2[None, :]) & valid).sum(axis=1)
    return np.minimum(ham1, ham2).astype(np.float32)


def _vec_sequence_entropy(X: np.ndarray) -> np.ndarray:
    """Vectorized Shannon entropy of crop-code sequences.

    X : (n, L) int32.  Returns (n,) float32.
    Loops over unique codes (~62 iters) instead of pixels (~48M).
    """
    valid = X >= 0
    valid_counts = valid.sum(axis=1).astype(np.float64)
    result = np.zeros(X.shape[0], dtype=np.float64)
    codes_present = np.unique(X[valid])
    codes_present = codes_present[codes_present >= 0]
    for code in codes_present:
        count = ((X == code) & valid).sum(axis=1).astype(np.float64)
        p = count / np.maximum(valid_counts, 1)
        mask = p > 0
        result[mask] -= (p[mask] * np.log(p[mask] + 1e-12))
    result[valid_counts == 0] = 0.0
    return result.astype(np.float32)


def compute_cdl_history_features(
    sub: pd.DataFrame,
    t: int,
    available_years: list[int],
    lookback: int = 10,
    lag_n: int = 5,
    height: int = 1520,
    width: int = 2048,
) -> pd.DataFrame:
    """Vectorized CDL history features for target panel year *t*."""
    hy = _history_year_list(available_years, t, lookback)
    if not hy:
        raise ValueError(f"No history years before t={t}")
    col_y = [f"cdl_{y}" for y in hy]
    X = sub[col_y].values.astype(np.int32)
    n = X.shape[0]
    L = X.shape[1]
    newest_first = X[:, ::-1]

    rows: dict[str, np.ndarray] = {
        "iy": sub["iy"].values,
        "ix": sub["ix"].values,
    }
    for k in range(1, min(lag_n, L) + 1):
        rows[f"cdl_t{k}"] = X[:, L - k].astype(np.int32)

    rows["n_corn_to_soy"] = np.sum((X[:, :-1] == 1) & (X[:, 1:] == 5), axis=1).astype(np.int32)
    rows["n_soy_to_corn"] = np.sum((X[:, :-1] == 5) & (X[:, 1:] == 1), axis=1).astype(np.int32)
    rows["n_corn_corn"] = np.sum((X[:, :-1] == 1) & (X[:, 1:] == 1), axis=1).astype(np.int32)
    rows["n_soy_soy"] = np.sum((X[:, :-1] == 5) & (X[:, 1:] == 5), axis=1).astype(np.int32)

    rows["time_since_last_corn"] = _vec_time_since(newest_first, 1)
    rows["time_since_last_soy"] = _vec_time_since(newest_first, 5)

    rows["frac_years_corn"] = np.mean(X == 1, axis=1).astype(np.float32)
    rows["frac_years_soy"] = np.mean(X == 5, axis=1).astype(np.float32)
    rows["max_run_length"] = _vec_max_run_length(X)
    rows["alternation_score"] = _vec_alternation_score(X)
    rows["pattern_distance"] = _vec_pattern_distance(X)
    rows["sequence_entropy"] = _vec_sequence_entropy(X)

    # 3x3 neighbourhood fractions (already vectorized via scipy)
    fc = np.full((height, width), np.nan, dtype=np.float32)
    fs = np.full((height, width), np.nan, dtype=np.float32)
    iy, ix = sub["iy"].values, sub["ix"].values
    fc[iy, ix] = rows["frac_years_corn"]
    fs[iy, ix] = rows["frac_years_soy"]
    fc_f = uniform_filter(np.nan_to_num(fc, nan=0.0), size=3, mode="nearest")
    fs_f = uniform_filter(np.nan_to_num(fs, nan=0.0), size=3, mode="nearest")
    rows["neigh_frac_corn"] = fc_f[iy, ix].astype(np.float32)
    rows["neigh_frac_soy"] = fs_f[iy, ix].astype(np.float32)

    alt = rows["alternation_score"]
    pdist = rows["pattern_distance"]
    mxrun = rows["max_run_length"]
    fcorn = rows["frac_years_corn"]
    fsoy = rows["frac_years_soy"]
    regime = np.full(n, "irregular", dtype=object)
    reg = (alt >= 0.7) & (pdist <= 3)
    mono = (mxrun >= 7) | (fcorn >= 0.8) | (fsoy >= 0.8)
    regime[reg & ~mono] = "regular"
    regime[mono] = "monoculture"
    rows["rotation_regime"] = regime

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# NDVI (wide parquet row block, scaled)
# ---------------------------------------------------------------------------


def compute_ndvi_features(
    ndvi_block: pd.DataFrame,
    scale: float = 250.0,
) -> pd.DataFrame:
    wcols = sorted(
        [c for c in ndvi_block.columns if c.startswith("w")],
        key=lambda x: int(x[1:]),
    )
    if not wcols:
        raise ValueError("No NDVI w* columns")
    M = ndvi_block[wcols].values.astype(np.float32) / np.float32(scale)
    M = np.where(np.isfinite(M), M, np.nan)
    base = np.nanpercentile(M, 10, axis=1)
    peak = np.nanmax(M, axis=1)
    amp = peak - base
    mean = np.nanmean(M, axis=1)
    integral = np.nansum(np.maximum(0.0, M - base[:, None]), axis=1)

    # 3-week uniform smooth along time (vectorized across all pixels)
    pad = np.pad(M, ((0, 0), (1, 1)), mode="edge")
    smooth = (pad[:, :-2] + pad[:, 1:-1] + pad[:, 2:]) / np.float32(3.0)
    peak_w = np.nanargmax(smooth, axis=1).astype(np.float32)
    thr = base + 0.2 * amp
    diffs = np.diff(smooth, axis=1, prepend=smooth[:, :1])
    inc = np.maximum(0.0, diffs)
    greenup_slope = np.nanmax(inc, axis=1)
    n = M.shape[1]
    above_thr = smooth >= thr[:, None]
    greenup = np.argmax(above_thr, axis=1).astype(np.float32)
    greenup[~above_thr.any(axis=1)] = np.nan
    i0, i1 = 0, min(7, n)
    i2, i3 = min(7, n), min(16, n)
    i4, i5 = min(16, n), n
    early = np.nanmean(M[:, i0:i1], axis=1)
    mid = np.nanmean(M[:, i2:i3], axis=1)
    late = np.nanmean(M[:, i4:i5], axis=1)

    return pd.DataFrame(
        {
            "ndvi_base": base.astype(np.float32),
            "ndvi_peak": peak.astype(np.float32),
            "ndvi_amplitude": amp.astype(np.float32),
            "ndvi_mean": mean.astype(np.float32),
            "ndvi_integral": integral.astype(np.float32),
            "ndvi_peak_week": peak_w.astype(np.float32),
            "ndvi_greenup_week": greenup.astype(np.float32),
            "ndvi_greenup_slope": greenup_slope.astype(np.float32),
            "ndvi_early_mean": early.astype(np.float32),
            "ndvi_mid_mean": mid.astype(np.float32),
            "ndvi_late_mean": late.astype(np.float32),
        }
    )


def ndvi_history_variability(
    hist_peak: np.ndarray,
    hist_peak_week: np.ndarray,
) -> dict[str, np.ndarray]:
    """hist_* shape (n_pixels, n_hist_years); may contain NaN."""
    return {
        "ndvi_peak_hist_mean": np.nanmean(hist_peak, axis=1).astype(np.float32),
        "ndvi_peak_hist_std": np.nanstd(hist_peak, axis=1).astype(np.float32),
        "ndvi_peak_week_hist_mean": np.nanmean(hist_peak_week, axis=1).astype(np.float32),
        "ndvi_peak_week_hist_std": np.nanstd(hist_peak_week, axis=1).astype(np.float32),
    }


# ---------------------------------------------------------------------------
# SMAP (parent cell, growing season stats)
# ---------------------------------------------------------------------------


def _smap_gs_features_for_cell_block(
    smap_px: pd.DataFrame,
    w_lo: int,
    w_hi: int,
    spring_lo: int,
    spring_hi: int,
    hist_gs: dict[tuple[int, int], list[np.ndarray]] | None,
    t: int,
) -> pd.DataFrame:
    """Vectorized SMAP growing-season features."""
    wcols = sorted(
        [c for c in smap_px.columns if c.startswith("w")],
        key=lambda x: int(x[1:]),
    )
    M = smap_px[wcols].values.astype(np.float32)
    lo, hi = w_lo, min(w_hi, M.shape[1] - 1)
    sl, sr = spring_lo, min(spring_hi, M.shape[1] - 1)
    gs = M[:, lo : hi + 1]
    spr = M[:, sl : sr + 1]
    smap_mean_gs = np.nanmean(gs, axis=1).astype(np.float32)
    smap_spring_sm = np.nanmean(spr, axis=1).astype(np.float32)

    n_px = len(smap_px)
    wet = np.zeros(n_px, dtype=np.float32)
    dry = np.zeros(n_px, dtype=np.float32)

    siy = (smap_px["iy"].values // 28).astype(np.int32)
    six = (smap_px["ix"].values // 28).astype(np.int32)
    cell_id = siy.astype(np.int64) * 100_000 + six.astype(np.int64)

    if hist_gs is not None and len(hist_gs) > 0:
        hist_p80 = {}
        hist_p20 = {}
        for key, arrs in hist_gs.items():
            if arrs:
                pooled = np.concatenate(arrs)
                hist_p80[key] = np.nanpercentile(pooled, 80)
                hist_p20[key] = np.nanpercentile(pooled, 20)
        if hist_p80:
            unique_cells = np.unique(cell_id)
            p80_arr = np.full(n_px, np.nan, dtype=np.float32)
            p20_arr = np.full(n_px, np.nan, dtype=np.float32)
            for uc in unique_cells:
                c_siy = int(uc // 100_000)
                c_six = int(uc % 100_000)
                key = (c_siy, c_six)
                mask = cell_id == uc
                if key in hist_p80:
                    p80_arr[mask] = hist_p80[key]
                    p20_arr[mask] = hist_p20[key]
            has_hist = np.isfinite(p80_arr)
        else:
            has_hist = np.zeros(n_px, dtype=bool)
    else:
        has_hist = np.zeros(n_px, dtype=bool)

    gs_valid_count = np.sum(np.isfinite(gs), axis=1)
    has_data = gs_valid_count > 0

    if has_hist.any():
        m = has_hist & has_data
        gs_m = gs[m]
        wet[m] = np.nanmean(gs_m > p80_arr[m, None], axis=1).astype(np.float32)
        dry[m] = np.nanmean(gs_m < p20_arr[m, None], axis=1).astype(np.float32)

    no_hist = ~has_hist & has_data
    if no_hist.any():
        gs_nh = gs[no_hist]
        p80_local = np.nanpercentile(gs_nh, 80, axis=1)
        p20_local = np.nanpercentile(gs_nh, 20, axis=1)
        wet[no_hist] = np.nanmean(gs_nh > p80_local[:, None], axis=1).astype(np.float32)
        dry[no_hist] = np.nanmean(gs_nh < p20_local[:, None], axis=1).astype(np.float32)

    return pd.DataFrame(
        {
            "smap_mean_gs": smap_mean_gs,
            "smap_spring_sm": smap_spring_sm,
            "smap_pct_wet_weeks": wet,
            "smap_pct_dry_weeks": dry,
        }
    )


def update_smap_cell_history(
    hist: dict[tuple[int, int], list[np.ndarray]],
    smap_px: pd.DataFrame,
    w_lo: int,
    w_hi: int,
) -> None:
    wcols = sorted(
        [c for c in smap_px.columns if c.startswith("w")],
        key=lambda x: int(x[1:]),
    )
    M = smap_px[wcols].values.astype(np.float32)
    lo, hi = w_lo, min(w_hi, M.shape[1] - 1)
    gs = M[:, lo : hi + 1]
    siy = (smap_px["iy"].values // 28).astype(np.int32)
    six = (smap_px["ix"].values // 28).astype(np.int32)
    cell_id = siy.astype(np.int64) * 100_000 + six.astype(np.int64)
    unique_cells = np.unique(cell_id)
    for uc in unique_cells:
        c_siy = int(uc // 100_000)
        c_six = int(uc % 100_000)
        key = (c_siy, c_six)
        mask = cell_id == uc
        block = gs[mask].flatten()
        hist.setdefault(key, []).append(block)


# ---------------------------------------------------------------------------
# Panel assembly
# ---------------------------------------------------------------------------


def assemble_training_panel(
    repo_root: Path,
    cfg: dict[str, Any],
    save_path: Path | None = None,
) -> pd.DataFrame:
    """
    Build panel for years in ``cfg['panel']['train_years']`` (inclusive range ends).
    """
    repo_root = Path(repo_root)
    cdl_path = repo_root / cfg["cdl"]["data_path"]
    meta = load_grid_meta(repo_root)
    H, W = int(meta["height"]), int(meta["width"])
    cdl = pd.read_parquet(cdl_path)
    available_years = sorted(
        int(c.replace("cdl_", "")) for c in cdl.columns if c.startswith("cdl_")
    )

    my = cfg["cdl"]["mask_years"]
    mask = build_cropland_mask(
        cdl,
        my[0],
        my[1],
        cropland_max=cfg["target_classes"]["cropland_max_code"],
        min_cropland_years=cfg["cdl"]["min_cropland_years_in_mask"],
    )
    out_dir = repo_root / cfg["output"]["processed_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    mask_path = out_dir / "cropland_mask.parquet"
    mask.to_parquet(mask_path, index=False, compression="zstd")

    tc = cfg["target_classes"]
    corn, soy, wheat = tc["corn"], tc["soybean"], tc["winter_wheat"]
    cropland_max = tc["cropland_max_code"]

    py = cfg["panel"]["train_years"]
    year_lo, year_hi = int(py[0]), int(py[1])
    lookback = int(cfg["cdl"]["history_lookback_years"])
    lag_n = int(cfg["cdl"]["lag_codes"])

    sample_n = cfg["panel"].get("sample_per_year") or 0
    seed = int(cfg.get("run", {}).get("seed", 42))

    ndvi_dir = repo_root / cfg["ndvi"]["source_dir"]
    smap_dir = repo_root / cfg["smap"]["source_dir"]
    ndvi_scale = float(cfg["ndvi"]["scale_to_physical"])
    w_lo, w_hi = cfg["smap"]["growing_season_weeks"]
    sp_lo, sp_hi = cfg["smap"]["spring_weeks"]
    smap_start = int(cfg["smap"]["smap_start_year"])

    smap_hist: dict[tuple[int, int], list[np.ndarray]] = {}
    ndvi_peak_cache: dict[int, pd.DataFrame] = {}
    ndvi_pkw_cache: dict[int, pd.DataFrame] = {}

    sub_full = mask.merge(cdl, on=["iy", "ix"], how="left")

    year_range = [t for t in range(year_lo, year_hi + 1) if f"cdl_{t}" in sub_full.columns]
    parts: list[pd.DataFrame] = []
    pbar = tqdm(year_range, desc="Building training panel", unit="yr")
    for t in pbar:
        y_raw = sub_full[f"cdl_{t}"].values
        label = map_cdl_code_to_label(y_raw, corn, soy, wheat, cropland_max)

        if sample_n > 0:
            keep = stratified_sample_indices(label, sample_n, seed=seed + t)
            sub = sub_full.iloc[keep].reset_index(drop=True)
            label = label[keep]
        else:
            sub = sub_full

        pbar.set_postfix(year=t, pixels=f"{len(sub):,}")
        hist_df = compute_cdl_history_features(
            sub, t, available_years, lookback=lookback, lag_n=lag_n, height=H, width=W
        )
        hist_df["label"] = label.astype(np.float32)
        hist_df["year"] = np.int32(t)

        ndvi_path = ndvi_dir / f"ndvi_weekly_{t}_wide.parquet"
        if ndvi_path.is_file():
            ndvi = pd.read_parquet(ndvi_path)
            m = hist_df[["iy", "ix"]].merge(ndvi, on=["iy", "ix"], how="left")
            ndvi_feat = compute_ndvi_features(m, scale=ndvi_scale)
            for c in ndvi_feat.columns:
                hist_df[c] = ndvi_feat[c].values
            peaks = ndvi_feat["ndvi_peak"].values
            pkw = ndvi_feat["ndvi_peak_week"].values
        else:
            peaks = np.full(len(hist_df), np.nan, dtype=np.float32)
            pkw = np.full(len(hist_df), np.nan, dtype=np.float32)

        ndvi_peak_cache[t] = pd.DataFrame({"iy": hist_df["iy"], "ix": hist_df["ix"], "_pk": peaks})
        ndvi_pkw_cache[t] = pd.DataFrame({"iy": hist_df["iy"], "ix": hist_df["ix"], "_pkw": pkw})

        prior_years = [y for y in ndvi_peak_cache if y < t]
        if prior_years:
            pk_mat = np.stack(
                [
                    ndvi_peak_cache[y]
                    .merge(hist_df[["iy", "ix"]], on=["iy", "ix"], how="right")["_pk"]
                    .values
                    for y in prior_years
                ],
                axis=1,
            )
            pkw_mat = np.stack(
                [
                    ndvi_pkw_cache[y]
                    .merge(hist_df[["iy", "ix"]], on=["iy", "ix"], how="right")["_pkw"]
                    .values
                    for y in prior_years
                ],
                axis=1,
            )
            var = ndvi_history_variability(pk_mat, pkw_mat)
            for k, v in var.items():
                hist_df[k] = v

        if t >= smap_start:
            sp = smap_dir / f"smap_weekly_{t}_wide.parquet"
            if sp.is_file():
                sm = pd.read_parquet(sp)
                m2 = hist_df[["iy", "ix"]].merge(sm, on=["iy", "ix"], how="left")
                smf = _smap_gs_features_for_cell_block(
                    m2, w_lo, w_hi, sp_lo, sp_hi, smap_hist, t
                )
                for c in smf.columns:
                    hist_df[c] = smf[c].values
                update_smap_cell_history(smap_hist, m2, w_lo, w_hi)
        else:
            for c in (
                "smap_mean_gs",
                "smap_spring_sm",
                "smap_pct_wet_weeks",
                "smap_pct_dry_weeks",
            ):
                hist_df[c] = np.float32(np.nan)

        ext = cfg.get("external", {})
        if ext:
            for _name, key in (
                ("soil", ext.get("soil_parquet", "")),
                ("terrain", ext.get("terrain_parquet", "")),
            ):
                if key:
                    p = repo_root / key
                    if p.is_file():
                        hist_df = hist_df.merge(pd.read_parquet(p), on=["iy", "ix"], how="left")

            daymet_pat = ext.get("daymet_glob", "")
            if daymet_pat:
                dp = Path(str(daymet_pat).format(year=t))
                dp = repo_root / dp if not dp.is_absolute() else dp
                if dp.is_file():
                    hist_df = hist_df.merge(pd.read_parquet(dp), on=["iy", "ix"], how="left")

            csb = ext.get("csb_parquet", "")
            if csb:
                cp = repo_root / csb
                if cp.is_file():
                    hist_df = hist_df.merge(pd.read_parquet(cp), on=["iy", "ix"], how="left")

        parts.append(hist_df)

    panel = pd.concat(parts, ignore_index=True)
    if save_path is None:
        save_path = out_dir / "feature_matrix_panel.parquet"
    panel.to_parquet(save_path, index=False, compression="zstd")
    return panel


def train_val_test_split(panel: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, ...]:
    p = cfg["panel"]
    tr = panel[panel["year"] <= p["train_split_max_year"]].copy()
    va = panel[panel["year"] == p["val_year"]].copy()
    return tr, va


def build_test_year_frame(repo_root: Path, cfg: dict[str, Any], year: int) -> pd.DataFrame:
    """Feature rows for test year (labels from CDL for evaluation only)."""
    repo_root = Path(repo_root)
    cdl_path = repo_root / cfg["cdl"]["data_path"]
    meta = load_grid_meta(repo_root)
    H, W = int(meta["height"]), int(meta["width"])

    steps = tqdm(total=5, desc=f"Test year {year}", unit="step")

    steps.set_postfix_str("loading CDL & building mask")
    cdl = pd.read_parquet(cdl_path)
    available_years = sorted(
        int(c.replace("cdl_", "")) for c in cdl.columns if c.startswith("cdl_")
    )
    my = cfg["cdl"]["mask_years"]
    mask = build_cropland_mask(
        cdl,
        my[0],
        my[1],
        cropland_max=cfg["target_classes"]["cropland_max_code"],
        min_cropland_years=cfg["cdl"]["min_cropland_years_in_mask"],
    )
    sub_full = mask.merge(cdl, on=["iy", "ix"], how="left")
    del cdl, mask

    sample_n = cfg["panel"].get("sample_per_year") or 0
    seed = int(cfg.get("run", {}).get("seed", 42))
    tc = cfg["target_classes"]
    y_raw = sub_full[f"cdl_{year}"].values
    label = map_cdl_code_to_label(
        y_raw, tc["corn"], tc["soybean"], tc["winter_wheat"], tc["cropland_max_code"]
    )
    if sample_n > 0 and len(sub_full) > sample_n:
        keep = stratified_sample_indices(label, sample_n, seed=seed)
        sub = sub_full.iloc[keep].reset_index(drop=True)
        label = label[keep]
        del sub_full
        steps.set_postfix_str(f"sampled {len(sub):,} pixels")
    else:
        sub = sub_full
        del sub_full
    steps.update(1)

    steps.set_postfix_str("CDL history features")
    lookback = int(cfg["cdl"]["history_lookback_years"])
    lag_n = int(cfg["cdl"]["lag_codes"])
    hist_df = compute_cdl_history_features(
        sub, year, available_years, lookback=lookback, lag_n=lag_n, height=H, width=W
    )
    steps.update(1)
    hist_df["label"] = label.astype(np.float32)
    hist_df["year"] = np.int32(year)

    steps.set_postfix_str("NDVI features")
    ndvi_dir = repo_root / cfg["ndvi"]["source_dir"]
    ndvi_path = ndvi_dir / f"ndvi_weekly_{year}_wide.parquet"
    ndvi_scale = float(cfg["ndvi"]["scale_to_physical"])
    if ndvi_path.is_file():
        ndvi = pd.read_parquet(ndvi_path)
        m = hist_df[["iy", "ix"]].merge(ndvi, on=["iy", "ix"], how="left")
        ndvi_feat = compute_ndvi_features(m, scale=ndvi_scale)
        for c in ndvi_feat.columns:
            hist_df[c] = ndvi_feat[c].values
        prior_years = [y for y in range(cfg["panel"]["train_years"][0], year) if y >= 2000]
        pixel_keys = hist_df[["iy", "ix"]]
        pk_cols = []
        for y in tqdm(prior_years, desc="NDVI history (test year)", unit="yr", leave=False):
            pp = ndvi_dir / f"ndvi_weekly_{y}_wide.parquet"
            if not pp.is_file():
                continue
            o = pd.read_parquet(pp)
            o = pixel_keys.merge(o, on=["iy", "ix"], how="inner")
            wonly = [c for c in o.columns if c.startswith("w")]
            o = o[["iy", "ix"] + wonly]
            feats = compute_ndvi_features(o, scale=ndvi_scale)
            o2 = pd.concat([o[["iy", "ix"]], feats[["ndvi_peak", "ndvi_peak_week"]]], axis=1)
            o2 = o2.rename(columns={"ndvi_peak": f"_pk{y}", "ndvi_peak_week": f"_pkw{y}"})
            pk_cols.append((y, o2))
            del o, feats
        if pk_cols:
            base = hist_df[["iy", "ix"]].copy()
            for _, o2 in pk_cols:
                base = base.merge(o2, on=["iy", "ix"], how="left")
            pk_mat_cols = sorted(
                [c for c in base.columns if re.match(r"_pk\d+$", c)],
                key=lambda c: int(c[3:]),
            )
            pkw_mat_cols = sorted(
                [c for c in base.columns if re.match(r"_pkw\d+$", c)],
                key=lambda c: int(c[4:]),
            )
            pk_mat = base[pk_mat_cols].values
            pkw_mat = base[pkw_mat_cols].values
            var = ndvi_history_variability(pk_mat, pkw_mat)
            for k, v in var.items():
                hist_df[k] = v

    steps.update(1)
    steps.set_postfix_str("SMAP features")
    smap_dir = repo_root / cfg["smap"]["source_dir"]
    w_lo, w_hi = cfg["smap"]["growing_season_weeks"]
    sp_lo, sp_hi = cfg["smap"]["spring_weeks"]
    smap_start = int(cfg["smap"]["smap_start_year"])
    if year >= smap_start:
        sp = smap_dir / f"smap_weekly_{year}_wide.parquet"
        if sp.is_file():
            sm = pd.read_parquet(sp)
            m2 = hist_df[["iy", "ix"]].merge(sm, on=["iy", "ix"], how="left")
            smf = _smap_gs_features_for_cell_block(
                m2, w_lo, w_hi, sp_lo, sp_hi, None, year
            )
            for c in smf.columns:
                hist_df[c] = smf[c].values
    else:
        for c in (
            "smap_mean_gs",
            "smap_spring_sm",
            "smap_pct_wet_weeks",
            "smap_pct_dry_weeks",
        ):
            hist_df[c] = np.float32(np.nan)
    steps.update(1)

    steps.set_postfix_str("external joins")
    ext = cfg.get("external", {})
    if ext:
        for key in ("soil_parquet", "terrain_parquet"):
            val = ext.get(key, "")
            if val:
                p = repo_root / val
                if p.is_file():
                    hist_df = hist_df.merge(pd.read_parquet(p), on=["iy", "ix"], how="left")
        daymet_pat = ext.get("daymet_glob", "")
        if daymet_pat:
            dp = Path(str(daymet_pat).format(year=year))
            dp = repo_root / dp if not dp.is_absolute() else dp
            if dp.is_file():
                hist_df = hist_df.merge(pd.read_parquet(dp), on=["iy", "ix"], how="left")
        csb = ext.get("csb_parquet", "")
        if csb:
            cp = repo_root / csb
            if cp.is_file():
                hist_df = hist_df.merge(pd.read_parquet(cp), on=["iy", "ix"], how="left")
    steps.update(1)
    steps.close()

    return hist_df
