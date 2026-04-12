"""
Conjugate Dirichlet–Multinomial summaries for corn/soy/other year-to-year transitions (Task 2).

Each rotation-eligible pixel contributes a 3×3 count matrix (row = from-state, col = to-state).
Independent Dirichlet posteriors per row yield Monte Carlo draws of P(corn→soy) and P(soy→corn);
a simple alternation proxy compares their mean to a threshold to form P(regular | data).

No MCMC: posterior sampling uses Gamma–Dirichlet identities (vectorized over pixels in chunks).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def per_pixel_transition_counts(
    seqs: NDArray[np.integer],
    *,
    corn: int = 1,
    soy: int = 5,
) -> NDArray[np.int32]:
    """
    Year-to-year transition counts per pixel, states **0=corn, 1=soy, 2=other**.

    Parameters
    ----------
    seqs
        Shape ``(N, T)`` CDL integer codes.

    Returns
    -------
    counts
        Shape ``(N, 3, 3)``, ``counts[i, from, to]``.
    """
    seqs = np.asarray(seqs, dtype=np.int16)
    a = seqs[:, :-1]
    b = seqs[:, 1:]
    sa = np.where(a == corn, 0, np.where(a == soy, 1, 2)).astype(np.int64)
    sb = np.where(b == corn, 0, np.where(b == soy, 1, 2)).astype(np.int64)
    idx = sa * 3 + sb
    n = seqs.shape[0]
    linear = (np.arange(n, dtype=np.int64)[:, None] * 9) + idx
    flat = linear.ravel()
    bc = np.bincount(flat, minlength=n * 9)
    return bc.reshape(n, 3, 3).astype(np.int32)


def _alpha_matrix_from_cfg(
    prior: str,
    *,
    jeffreys_scalar: float = 0.5,
    informative_boost: float = 1.0,
) -> NDArray[np.float64]:
    """Return (3, 3) prior pseudo-counts added to each row's observed counts."""
    p = (prior or "jeffreys").strip().lower()
    if p == "uniform":
        return np.ones((3, 3), dtype=np.float64)
    if p == "informative_alternation":
        # Mild pull toward corn↔soy when data are sparse (Corn Belt prior).
        a = np.full((3, 3), 0.5, dtype=np.float64)
        a[0, 1] += float(informative_boost)  # corn → soy
        a[1, 0] += float(informative_boost)  # soy → corn
        return a
    # jeffreys (default): Dirichlet(0.5, 0.5, 0.5) per row
    return np.full((3, 3), float(jeffreys_scalar), dtype=np.float64)


def p_regular_and_uncertainty_chunked(
    counts: NDArray[np.integer],
    *,
    alpha_prior: NDArray[np.float64],
    n_samples: int = 256,
    alt_threshold: float = 0.70,
    min_origin_transitions: int = 1,
    chunk_rows: int = 48_000,
    random_state: int | None = None,
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.int32]]:
    """
    For each pixel, Monte Carlo draws from independent Dirichlet posteriors for rows
    **corn** and **soy**; alternation proxy ``alt = (P(corn→soy) + P(soy→corn)) / 2``.

    Returns
    -------
    p_regular
        Fraction of draws with ``alt >= alt_threshold``.
    alt_sample_std
        Posterior std of ``alt`` across draws (epistemic spread).
    n_origin_cs
        Count of year-pairs originating from corn or soy (``row0.sum + row1.sum``).
    """
    counts = np.asarray(counts, dtype=np.int32)
    n = counts.shape[0]
    rng = np.random.default_rng(random_state)
    p_out = np.full(n, np.nan, dtype=np.float32)
    s_out = np.full(n, np.nan, dtype=np.float32)
    n_origin = counts[:, 0, :].sum(axis=1) + counts[:, 1, :].sum(axis=1)

    k_mc = max(10, int(n_samples))
    thr = float(alt_threshold)

    for start in range(0, n, int(chunk_rows)):
        end = min(start + int(chunk_rows), n)
        cc = counts[start:end].astype(np.float64)
        m = end - start
        valid = (n_origin[start:end] >= int(min_origin_transitions)) & (n_origin[start:end] > 0)
        hits = np.zeros(m, dtype=np.float64)
        a1 = np.zeros(m, dtype=np.float64)
        a2 = np.zeros(m, dtype=np.float64)
        alpha = np.asarray(alpha_prior, dtype=np.float64)[None, :, :].repeat(m, axis=0)
        params = np.maximum(alpha + cc, 1e-6)

        for _ in range(k_mc):
            g0 = rng.gamma(params[:, 0, :], 1.0, size=(m, 3))
            g1 = rng.gamma(params[:, 1, :], 1.0, size=(m, 3))
            t0 = g0 / np.maximum(g0.sum(axis=1, keepdims=True), 1e-12)
            t1 = g1 / np.maximum(g1.sum(axis=1, keepdims=True), 1e-12)
            alt = (t0[:, 1] + t1[:, 0]) * 0.5
            hits += (alt >= thr).astype(np.float64)
            a1 += alt
            a2 += alt * alt

        mean_alt = a1 / k_mc
        var_alt = np.maximum(a2 / k_mc - mean_alt * mean_alt, 0.0)
        pr = (hits / k_mc).astype(np.float32)
        std_alt = np.sqrt(var_alt).astype(np.float32)
        pr[~valid] = np.nan
        std_alt[~valid] = np.nan
        p_out[start:end] = pr
        s_out[start:end] = std_alt

    return p_out, s_out, n_origin.astype(np.int32)
