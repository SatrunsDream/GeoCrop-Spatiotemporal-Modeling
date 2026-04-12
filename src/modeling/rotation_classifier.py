"""
Per-pixel crop rotation metrics and rule-based classification (NAFSI Task 2).

Metrics follow the project brief / methods notes: alternation rate among corn–soy
years, run length, Hamming-style distance to canonical corn–soy alternation,
Shannon entropy of the sequence, and simple coverage summaries.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from numpy.typing import NDArray

CORN = 1
SOY = 5


def default_canonical_patterns(length: int = 10) -> list[NDArray[np.int_]]:
    """Corn-first and soy-first strict alternation patterns of *length* years."""
    c1 = np.array([(CORN if i % 2 == 0 else SOY) for i in range(length)], dtype=np.int16)
    c2 = np.array([(SOY if i % 2 == 0 else CORN) for i in range(length)], dtype=np.int16)
    return [c1, c2]


def alternation_score(seq: NDArray[np.integer]) -> float:
    """
    Fraction of adjacent-year transitions where both years are corn or soy and
    the crops differ (corn↔soy). Denominator counts valid corn/soy transitions only.
    """
    seq = np.asarray(seq).ravel()
    if seq.size < 2:
        return 0.0
    valid = 0
    alternating = 0
    for a, b in zip(seq[:-1], seq[1:]):
        if int(a) in (CORN, SOY) and int(b) in (CORN, SOY):
            valid += 1
            if int(a) != int(b):
                alternating += 1
    return alternating / valid if valid > 0 else 0.0


def alternation_score_batch(seqs: NDArray[np.integer]) -> NDArray[np.floating]:
    """``seqs`` shape ``(N, T)`` → vector of alternation scores."""
    seqs = np.asarray(seqs, dtype=np.int16)
    a, b = seqs[:, :-1], seqs[:, 1:]
    both = np.isin(a, [CORN, SOY]) & np.isin(b, [CORN, SOY])
    alt = (a != b) & both
    valid = both.sum(axis=1)
    num = alt.sum(axis=1).astype(np.float64)
    return np.where(valid > 0, num / np.maximum(valid, 1), 0.0)


def max_run_length(seq: NDArray[np.integer]) -> int:
    """Longest run of identical class codes (any code)."""
    seq = np.asarray(seq).ravel()
    if seq.size == 0:
        return 0
    best = cur = 1
    for i in range(1, len(seq)):
        if int(seq[i]) == int(seq[i - 1]):
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return int(best)


def max_run_length_batch(seqs: NDArray[np.integer]) -> NDArray[np.integer]:
    """``seqs`` shape ``(N, T)``."""
    seqs = np.asarray(seqs, dtype=np.int16)
    n, t = seqs.shape
    runs = np.ones((n, t), dtype=np.int32)
    for i in range(1, t):
        same = seqs[:, i] == seqs[:, i - 1]
        runs[:, i] = np.where(same, runs[:, i - 1] + 1, 1)
    return runs.max(axis=1).astype(np.int32)


def pattern_edit_distance(
    seq: NDArray[np.integer],
    canonical: Sequence[NDArray[np.integer]] | None = None,
    *,
    mask_to_cornsoy: bool = True,
) -> int:
    """
    Minimum Hamming distance to any canonical pattern (substitutions only;
    length fixed to ``len(seq)``).

    If ``mask_to_cornsoy``, only positions where the canonical value is corn or
    soy contribute to the distance (RECRUIT-style focus on rotation skeleton).
    """
    seq = np.asarray(seq, dtype=np.int16).ravel()
    L = len(seq)
    if canonical is None:
        canonical = default_canonical_patterns(L)
    best = L + 1
    for pat in canonical:
        pat = np.asarray(pat, dtype=np.int16).ravel()[:L]
        if pat.size != L:
            pat = np.pad(pat, (0, L - pat.size), mode="edge")[:L]
        if mask_to_cornsoy:
            mask = np.isin(pat, [CORN, SOY])
            dist = int(np.sum(seq[mask] != pat[mask]))
        else:
            dist = int(np.sum(seq != pat))
        best = min(best, dist)
    return int(best)


def pattern_edit_distance_batch(
    seqs: NDArray[np.integer],
    canonical: Sequence[NDArray[np.integer]] | None = None,
    *,
    mask_to_cornsoy: bool = True,
) -> NDArray[np.integer]:
    """``seqs`` shape ``(N, T)``."""
    seqs = np.asarray(seqs, dtype=np.int16)
    n, t = seqs.shape
    if canonical is None:
        canonical = default_canonical_patterns(t)
    best = np.full(n, t + 1, dtype=np.int32)
    for pat in canonical:
        pat = np.asarray(pat, dtype=np.int16).ravel()[:t]
        if pat.size < t:
            pat = np.pad(pat, (0, t - pat.size), mode="edge")[:t]
        if mask_to_cornsoy:
            mask = np.isin(pat, [CORN, SOY])
            diff = (seqs != pat) & mask
            dist = diff.sum(axis=1).astype(np.int32)
        else:
            dist = (seqs != pat).sum(axis=1).astype(np.int32)
        best = np.minimum(best, dist)
    return best


def shannon_entropy(seq: NDArray[np.integer]) -> float:
    """Base-2 Shannon entropy of crop categories in ``seq`` (ignores NaN)."""
    seq = np.asarray(seq, dtype=np.float64).ravel()
    seq = seq[~np.isnan(seq)]
    if seq.size == 0:
        return 0.0
    vals, counts = np.unique(seq.astype(np.int64), return_counts=True)
    p = counts.astype(np.float64) / counts.sum()
    return float(-np.sum(p * np.log2(p + 1e-12)))


def shannon_entropy_batch(seqs: NDArray[np.integer]) -> NDArray[np.floating]:
    """Row-wise entropy; ``seqs`` shape ``(N, T)``. Slower than other batch metrics."""
    seqs = np.asarray(seqs, dtype=np.int16)
    out = np.empty(seqs.shape[0], dtype=np.float64)
    for i in range(seqs.shape[0]):
        out[i] = shannon_entropy(seqs[i])
    return out


def cornsoy_years_count(seq: NDArray[np.integer]) -> int:
    """Years where pixel is corn or soybean."""
    seq = np.asarray(seq).ravel()
    return int(np.sum(np.isin(seq, [CORN, SOY])))


def cornsoy_years_count_batch(seqs: NDArray[np.integer]) -> NDArray[np.integer]:
    return np.isin(seqs, [CORN, SOY]).sum(axis=1).astype(np.int32)


def crop_share(seq: NDArray[np.integer]) -> float:
    """Fraction of years equal to the mode crop code."""
    seq = np.asarray(seq).ravel()
    if seq.size == 0:
        return 0.0
    _, counts = np.unique(seq, return_counts=True)
    return float(counts.max() / len(seq))


def crop_share_batch(seqs: NDArray[np.integer]) -> NDArray[np.floating]:
    """Mode crop fraction per row (same definition as ``crop_share``)."""
    seqs = np.asarray(seqs, dtype=np.int16)
    return np.apply_along_axis(lambda r: crop_share(r), 1, seqs)


def classify_pixel(
    alt: float,
    run: int,
    dist: int,
    n_cornsoy: int,
    share: float,
    *,
    alt_min: float = 0.70,
    dist_max: int = 3,
    cs_min: int = 7,
    mono_run: int = 7,
    mono_share: float = 0.80,
) -> int:
    """
    Rule-based class label.

    Returns
    -------
    0 — regular rotation (strong alternation + close to canonical + enough corn/soy years)
    1 — monoculture (long same-crop run or dominant single crop share)
    2 — irregular (catch-all)
    """
    if run >= mono_run or share >= mono_share:
        return 1
    if alt >= alt_min and dist <= dist_max and n_cornsoy >= cs_min:
        return 0
    return 2


def classify_batch(
    alt: NDArray[np.floating],
    run: NDArray[np.integer],
    dist: NDArray[np.integer],
    n_cornsoy: NDArray[np.integer],
    share: NDArray[np.floating],
    *,
    alt_min: float,
    dist_max: int,
    cs_min: int,
    mono_run: int,
    mono_share: float,
) -> NDArray[np.uint8]:
    """Vectorized ``classify_pixel`` (same rule order)."""
    alt = np.asarray(alt, dtype=np.float64)
    run = np.asarray(run, dtype=np.int32)
    dist = np.asarray(dist, dtype=np.int32)
    n_cornsoy = np.asarray(n_cornsoy, dtype=np.int32)
    share = np.asarray(share, dtype=np.float64)
    mono = (run >= mono_run) | (share >= mono_share)
    reg = (~mono) & (alt >= alt_min) & (dist <= dist_max) & (n_cornsoy >= cs_min)
    out = np.full(alt.shape, 2, dtype=np.uint8)
    out[mono] = 1
    out[reg] = 0
    return out


def transition_counts_corn_soy_other(
    seqs: NDArray[np.integer],
    *,
    corn: int = CORN,
    soy: int = SOY,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Aggregate year-to-year transitions across pixels.

    State codes in the 3×3 matrix: **0 = corn**, **1 = soybean**, **2 = other**
    (anything not corn or soy).

    Parameters
    ----------
    seqs
        Shape ``(N, T)`` integer CDL sequences.

    Returns
    -------
    counts
        ``(3, 3)`` transition counts (row = from, col = to).
    probs
        Row-normalized conditional probabilities ``P(to | from)``.
    """
    seqs = np.asarray(seqs, dtype=np.int16)
    a = seqs[:, :-1].ravel()
    b = seqs[:, 1:].ravel()

    def _state(x: np.ndarray) -> np.ndarray:
        return np.where(x == corn, 0, np.where(x == soy, 1, 2)).astype(np.int64)

    sa, sb = _state(a), _state(b)
    idx = sa * 3 + sb
    bc = np.bincount(idx, minlength=9).reshape(3, 3).astype(np.float64)
    row_sum = bc.sum(axis=1, keepdims=True)
    probs = np.divide(bc, np.maximum(row_sum, 1e-12))
    return bc, probs


def majority_smooth_classes(
    raster: NDArray[np.integer],
    *,
    nodata: int = 255,
    kernel: int = 3,
) -> NDArray[np.uint8]:
    """
    3×3 majority vote among classes {0,1,2}; nodata pixels stay nodata when the
    center is nodata. Uses fast ``scipy.ndimage.uniform_filter`` vote stacking.
    """
    from scipy.ndimage import uniform_filter

    r = np.asarray(raster, dtype=np.float32)
    h, w = r.shape
    counts = []
    for c in (0, 1, 2):
        m = (r == c).astype(np.float32)
        counts.append(uniform_filter(m, size=kernel, mode="nearest"))
    C = np.stack(counts, axis=0)
    winner = np.argmax(C, axis=0).astype(np.uint8)
    out = np.where(r == nodata, nodata, winner).astype(np.uint8)
    return out
