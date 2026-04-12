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

# ---------------------------------------------------------------------------
# Grid / mask
# ---------------------------------------------------------------------------


def load_grid_meta(repo_root: Path) -> dict[str, Any]:
    meta_path = repo_root / "data" / "processed" / "cdl" / "cdl_stack_spatial_metadata.json"
    if not meta_path.is_file():
        raise FileNotFoundError(meta_path)
    return json.loads(meta_path.read_text(encoding="utf-8"))


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


# ---------------------------------------------------------------------------
# CDL history (per target year t, prior years only)
# ---------------------------------------------------------------------------


def _history_year_list(available: list[int], t: int, lookback: int) -> list[int]:
    prior = [y for y in available if y < t]
    return prior[-lookback:] if len(prior) >= lookback else prior


def _max_run_length(seq: np.ndarray) -> int:
    if seq.size == 0:
        return 0
    m = 1
    cur = 1
    for i in range(1, len(seq)):
        if seq[i] == seq[i - 1] and seq[i] >= 0:
            cur += 1
            m = max(m, cur)
        else:
            cur = 1
    return int(m)


def _alternation_score(seq: np.ndarray) -> float:
    if len(seq) < 2:
        return 0.0
    a, b = seq[:-1], seq[1:]
    valid = ((a == 1) | (a == 5)) & ((b == 1) | (b == 5))
    n_valid = int(valid.sum())
    if n_valid == 0:
        return 0.0
    switches = int(((a == 1) & (b == 5) | ((a == 5) & (b == 1)))[valid].sum())
    return switches / max(n_valid, 1)


def _pattern_distance(seq: np.ndarray, pattern_len: int = 10) -> float:
    s = np.asarray(seq[-pattern_len:], dtype=np.float64)
    if s.size < pattern_len:
        pad = np.repeat(s[:1] if s.size else np.array([-1.0]), pattern_len - s.size)
        s = np.concatenate([pad, s]) if s.size else np.full(pattern_len, -1.0)
    alt1 = np.array([1 if i % 2 == 0 else 5 for i in range(pattern_len)], dtype=np.float64)
    alt2 = np.array([5 if i % 2 == 0 else 1 for i in range(pattern_len)], dtype=np.float64)
    # non corn/soy positions count as mismatch
    def ham(u):
        return float(np.sum((s != u) & (s >= 0)))

    return min(ham(alt1), ham(alt2))


def _sequence_entropy(seq: np.ndarray) -> float:
    s = seq[seq >= 0]
    if s.size == 0:
        return 0.0
    _, counts = np.unique(s, return_counts=True)
    p = counts.astype(np.float64) / counts.sum()
    return float(-np.sum(p * np.log(p + 1e-12)))


def _time_since_code(seq_rev: np.ndarray, code: int) -> float:
    """seq_rev: newest first (t-1, t-2, …)."""
    for i, v in enumerate(seq_rev):
        if v == code:
            return float(i)
    return np.nan


def compute_cdl_history_features(
    sub: pd.DataFrame,
    t: int,
    available_years: list[int],
    lookback: int = 10,
    lag_n: int = 5,
    height: int = 1520,
    width: int = 2048,
) -> pd.DataFrame:
    """
    ``sub`` is merged mask+CDL rows. Adds CDL history columns for target panel year ``t``.
    """
    hy = _history_year_list(available_years, t, lookback)
    if not hy:
        raise ValueError(f"No history years before t={t}")
    col_y = [f"cdl_{y}" for y in hy]
    X = sub[col_y].values.astype(np.int32)
    n = X.shape[0]
    L = X.shape[1]
    # oldest → newest along axis 1 (hy sorted ascending)
    newest_first = X[:, ::-1]

    rows: dict[str, np.ndarray] = {
        "iy": sub["iy"].values,
        "ix": sub["ix"].values,
    }
    for k in range(1, min(lag_n, L) + 1):
        rows[f"cdl_t{k}"] = X[:, L - k].astype(np.int32)

    # transitions (full history order oldest→newest)
    rows["n_corn_to_soy"] = np.sum((X[:, :-1] == 1) & (X[:, 1:] == 5), axis=1).astype(np.int32)
    rows["n_soy_to_corn"] = np.sum((X[:, :-1] == 5) & (X[:, 1:] == 1), axis=1).astype(np.int32)
    rows["n_corn_corn"] = np.sum((X[:, :-1] == 1) & (X[:, 1:] == 1), axis=1).astype(np.int32)
    rows["n_soy_soy"] = np.sum((X[:, :-1] == 5) & (X[:, 1:] == 5), axis=1).astype(np.int32)

    tsc = np.array([_time_since_code(newest_first[i], 1) for i in range(n)], dtype=np.float32)
    tss = np.array([_time_since_code(newest_first[i], 5) for i in range(n)], dtype=np.float32)
    rows["time_since_last_corn"] = tsc
    rows["time_since_last_soy"] = tss

    rows["frac_years_corn"] = np.mean(X == 1, axis=1).astype(np.float32)
    rows["frac_years_soy"] = np.mean(X == 5, axis=1).astype(np.float32)
    rows["max_run_length"] = np.array([_max_run_length(X[i]) for i in range(n)], dtype=np.int32)
    rows["alternation_score"] = np.array([_alternation_score(X[i]) for i in range(n)], dtype=np.float32)
    rows["pattern_distance"] = np.array([_pattern_distance(X[i]) for i in range(n)], dtype=np.float32)
    rows["sequence_entropy"] = np.array([_sequence_entropy(X[i]) for i in range(n)], dtype=np.float32)

    # 3×3 neighborhood of frac (grid)
    fc = np.full((height, width), np.nan, dtype=np.float32)
    fs = np.full((height, width), np.nan, dtype=np.float32)
    iy, ix = sub["iy"].values, sub["ix"].values
    fc[iy, ix] = rows["frac_years_corn"]
    fs[iy, ix] = rows["frac_years_soy"]
    fc_f = uniform_filter(np.nan_to_num(fc, nan=0.0), size=3, mode="nearest")
    fs_f = uniform_filter(np.nan_to_num(fs, nan=0.0), size=3, mode="nearest")
    # re-normalize: uniform_filter on zeros padded - approximate; mask valid by count
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

    # 3-week smooth along time
    ker = np.ones(3, dtype=np.float32) / 3.0
    pad = np.pad(M, ((0, 0), (1, 1)), mode="edge")
    smooth = np.stack(
        [np.convolve(pad[i], ker, mode="valid") for i in range(M.shape[0])],
        axis=0,
    )
    peak_w = np.nanargmax(smooth, axis=1).astype(np.float32)
    thr = base + 0.2 * amp
    greenup = np.full(M.shape[0], np.nan, dtype=np.float32)
    diffs = np.diff(smooth, axis=1, prepend=smooth[:, :1])
    inc = np.maximum(0.0, diffs)
    greenup_slope = np.nanmax(inc, axis=1)
    n = M.shape[1]
    for i in range(M.shape[0]):
        crossed = np.where(smooth[i] >= thr[i])[0]
        greenup[i] = float(crossed[0]) if crossed.size else np.nan
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
    """smap_px: rows indexed by pixel with iy, ix and w* columns."""
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

    wet = np.zeros(len(smap_px), dtype=np.float32)
    dry = np.zeros(len(smap_px), dtype=np.float32)
    siy = (smap_px["iy"].values // 28).astype(np.int32)
    six = (smap_px["ix"].values // 28).astype(np.int32)
    for i in range(len(smap_px)):
        g = gs[i]
        g = g[np.isfinite(g)]
        if g.size == 0:
            continue
        key = (int(siy[i]), int(six[i]))
        if hist_gs is not None and key in hist_gs and len(hist_gs[key]) > 0:
            pooled = np.concatenate(hist_gs[key])
            p80 = np.nanpercentile(pooled, 80)
            p20 = np.nanpercentile(pooled, 20)
        else:
            p80 = np.nanpercentile(g, 80)
            p20 = np.nanpercentile(g, 20)
        wet[i] = float(np.mean(g > p80)) if g.size else np.nan
        dry[i] = float(np.mean(g < p20)) if g.size else np.nan

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
    for i in range(len(smap_px)):
        key = (int(siy[i]), int(six[i]))
        hist.setdefault(key, []).append(gs[i].flatten())


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

    ndvi_dir = repo_root / cfg["ndvi"]["source_dir"]
    smap_dir = repo_root / cfg["smap"]["source_dir"]
    ndvi_scale = float(cfg["ndvi"]["scale_to_physical"])
    w_lo, w_hi = cfg["smap"]["growing_season_weeks"]
    sp_lo, sp_hi = cfg["smap"]["spring_weeks"]
    smap_start = int(cfg["smap"]["smap_start_year"])

    smap_hist: dict[tuple[int, int], list[np.ndarray]] = {}
    ndvi_peak_cache: dict[int, pd.DataFrame] = {}
    ndvi_pkw_cache: dict[int, pd.DataFrame] = {}

    parts: list[pd.DataFrame] = []
    for t in range(year_lo, year_hi + 1):
        sub = mask.merge(cdl, on=["iy", "ix"], how="left")
        if f"cdl_{t}" not in sub.columns:
            continue
        hist_df = compute_cdl_history_features(
            sub, t, available_years, lookback=lookback, lag_n=lag_n, height=H, width=W
        )
        y_raw = sub[f"cdl_{t}"].values
        label = map_cdl_code_to_label(y_raw, corn, soy, wheat, cropland_max)
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

        # optional external joins
        for _name, key in (
            ("soil", cfg["external"]["soil_parquet"]),
            ("terrain", cfg["external"]["terrain_parquet"]),
        ):
            p = repo_root / key
            if p.is_file():
                ex = pd.read_parquet(p)
                hist_df = hist_df.merge(ex, on=["iy", "ix"], how="left")

        daymet_pat = cfg["external"]["daymet_glob"]
        dp = Path(str(daymet_pat).format(year=t))
        dp = repo_root / dp if not dp.is_absolute() else dp
        if dp.is_file():
            dm = pd.read_parquet(dp)
            hist_df = hist_df.merge(dm, on=["iy", "ix"], how="left")

        cp = repo_root / cfg["external"]["csb_parquet"]
        if cp.is_file():
            csb = pd.read_parquet(cp)
            hist_df = hist_df.merge(csb, on=["iy", "ix"], how="left")

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
    sub = mask.merge(cdl, on=["iy", "ix"], how="left")
    lookback = int(cfg["cdl"]["history_lookback_years"])
    lag_n = int(cfg["cdl"]["lag_codes"])
    hist_df = compute_cdl_history_features(
        sub, year, available_years, lookback=lookback, lag_n=lag_n, height=H, width=W
    )
    tc = cfg["target_classes"]
    y_raw = sub[f"cdl_{year}"].values
    hist_df["label"] = map_cdl_code_to_label(
        y_raw, tc["corn"], tc["soybean"], tc["winter_wheat"], tc["cropland_max_code"]
    ).astype(np.float32)
    hist_df["year"] = np.int32(year)

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
        pk_cols = []
        for y in prior_years:
            pp = ndvi_dir / f"ndvi_weekly_{y}_wide.parquet"
            if not pp.is_file():
                continue
            o = pd.read_parquet(pp)
            wonly = [c for c in o.columns if c.startswith("w")]
            o = o[["iy", "ix"] + wonly]
            feats = compute_ndvi_features(o, scale=ndvi_scale)
            o2 = pd.concat([o[["iy", "ix"]], feats[["ndvi_peak", "ndvi_peak_week"]]], axis=1)
            o2 = o2.rename(columns={"ndvi_peak": f"_pk{y}", "ndvi_peak_week": f"_pkw{y}"})
            pk_cols.append((y, o2))
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

    for key in ("soil_parquet", "terrain_parquet"):
        p = repo_root / cfg["external"][key]
        if p.is_file():
            hist_df = hist_df.merge(pd.read_parquet(p), on=["iy", "ix"], how="left")
    dp = Path(str(cfg["external"]["daymet_glob"]).format(year=year))
    dp = repo_root / dp if not dp.is_absolute() else dp
    if dp.is_file():
        hist_df = hist_df.merge(pd.read_parquet(dp), on=["iy", "ix"], how="left")
    cp = repo_root / cfg["external"]["csb_parquet"]
    if cp.is_file():
        hist_df = hist_df.merge(pd.read_parquet(cp), on=["iy", "ix"], how="left")

    return hist_df
