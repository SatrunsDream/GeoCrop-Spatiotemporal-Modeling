# Disclaimer: Fully AI-generated.
"""
Normal-Inverse-Gamma (NIG) conjugate Bayesian anomaly detection for SMAP soil moisture (Task 3).

Given n baseline observations per (pixel, ISO week), the NIG posterior yields a Student-t
posterior predictive whose heavier tails honestly reflect the limited 7-year SMAP baseline.
Outputs: two-tailed p-value, one-tailed drought exceedance, and predictive scale.

References:
  Murphy (2007) "Conjugate Bayesian analysis of the Gaussian distribution" (NIG derivation).
  Gelman et al. (2008) prior-choice recommendations for weakly informative priors.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import stats


def nig_posterior_params(
    sm_mean: NDArray[np.floating],
    sm_std: NDArray[np.floating],
    sm_count: NDArray[np.integer],
    *,
    mu_0: float | NDArray[np.floating],
    lam_0: float = 1.0,
    alpha_0: float = 2.0,
    beta_0: float | NDArray[np.floating] | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """
    Closed-form NIG posterior update from sufficient statistics.

    Parameters are broadcast-safe over arrays of (pixel, iso_week) rows.

    Returns ``(mu_n, lam_n, alpha_n, beta_n)`` — all float64 arrays.
    """
    n = np.asarray(sm_count, dtype=np.float64)
    xbar = np.asarray(sm_mean, dtype=np.float64)
    s = np.asarray(sm_std, dtype=np.float64)
    S = np.maximum(n - 1, 0) * (s ** 2)  # sum of squared deviations

    mu0 = np.asarray(mu_0, dtype=np.float64)
    l0 = float(lam_0)
    a0 = float(alpha_0)
    if beta_0 is None:
        regional_var = np.nanmedian(s ** 2)
        b0 = np.full_like(xbar, max(float(regional_var) * (a0 - 0.5), 1e-8))
    else:
        b0 = np.asarray(beta_0, dtype=np.float64)

    lam_n = l0 + n
    mu_n = np.where(n > 0, (l0 * mu0 + n * xbar) / lam_n, mu0)
    alpha_n = a0 + n / 2.0
    beta_n = b0 + S / 2.0 + (n * l0 * (xbar - mu0) ** 2) / (2.0 * lam_n)

    return mu_n, lam_n, alpha_n, beta_n


def nig_predictive_scores(
    sm_obs: NDArray[np.floating],
    mu_n: NDArray[np.floating],
    lam_n: NDArray[np.floating],
    alpha_n: NDArray[np.floating],
    beta_n: NDArray[np.floating],
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.float32], NDArray[np.float32]]:
    """
    Student-t posterior predictive anomaly scores.

    Returns
    -------
    nig_p_anomaly
        Two-tailed p-value (near 0 = extreme anomaly).
    nig_p_drought
        One-tailed CDF (near 0 = extremely dry; near 1 = extremely wet).
    nig_posterior_scale
        Predictive std — wider for sparse pixels.
    nig_df
        Degrees of freedom of the Student-t (= 2 * alpha_n).
    """
    mu = np.asarray(mu_n, dtype=np.float64)
    lam = np.asarray(lam_n, dtype=np.float64)
    alpha = np.asarray(alpha_n, dtype=np.float64)
    beta = np.asarray(beta_n, dtype=np.float64)
    obs = np.asarray(sm_obs, dtype=np.float64)

    df = 2.0 * alpha
    scale = np.sqrt(beta * (1.0 + 1.0 / np.maximum(lam, 1e-12)) / np.maximum(alpha, 1e-12))

    t_stat = (obs - mu) / np.maximum(scale, 1e-12)
    p_drought = stats.t.cdf(t_stat, df).astype(np.float32)
    p_anomaly = (2.0 * stats.t.cdf(-np.abs(t_stat), df)).astype(np.float32)

    return (
        p_anomaly,
        p_drought,
        scale.astype(np.float32),
        df.astype(np.float32),
    )


def regional_prior_mu0(clim: "pd.DataFrame") -> "pd.Series":
    """Per-``iso_week`` grand mean across all pixels — used as μ₀ in the NIG prior."""
    return clim.groupby("iso_week")["sm_mean"].transform("mean")


def regional_prior_beta0(
    clim: "pd.DataFrame",
    alpha_0: float = 2.0,
) -> "pd.Series":
    """Per-``iso_week`` β₀ anchored to regional variance: β₀ = regional_var × (α₀ − 0.5)."""
    rvar = clim.groupby("iso_week")["sm_std"].transform(lambda s: np.nanmedian(s ** 2))
    return rvar * max(alpha_0 - 0.5, 0.1)
