"""
ndvi_smoothing.py — NDVI time-series smoothing methods.

Smoothing is required to remove noise from cloud contamination and
view-geometry compositing artifacts before phenometric extraction.

Approach options considered:
  A) Savitzky–Golay (SG) — classic, fast, preserves peaks/derivatives
  B) Whittaker smoothing — penalized least-squares, robust to negatively biased noise
  C) TIMESAT double-logistic — produces phenometrics directly but requires parameter tuning
  D) Harmonic / Fourier regression — handles gaps, can smear asymmetric curves

Selected approach: Whittaker as primary, SG as secondary — see DECISIONS.md DEC-002.
"""

import numpy as np
from numpy.typing import NDArray


def smooth(
    ndvi: NDArray,
    method: str = "whittaker",
    **kwargs,
) -> NDArray:
    """
    Smooth a 1D or ND NDVI time series.

    Parameters
    ----------
    ndvi : NDArray
        NDVI array. If 1D, shape (T,). If 3D, shape (T, H, W) — smoothing applied per pixel.
    method : str
        Smoothing method: 'whittaker', 'savitzky_golay', 'harmonic'.
    **kwargs
        Method-specific parameters (e.g., lambda_=100 for Whittaker, window=7 for SG).

    Returns
    -------
    NDArray
        Smoothed array, same shape as input.
    """
    # TODO: dispatch to method-specific functions
    raise NotImplementedError


def whittaker_smooth(ndvi_1d: NDArray, lambda_: float = 100.0) -> NDArray:
    """
    Apply Whittaker (penalized least-squares) smoothing to a 1D NDVI series.

    Parameters
    ----------
    ndvi_1d : NDArray
        1D NDVI array with possible NaN gaps.
    lambda_ : float
        Smoothing penalty strength. Higher = smoother.

    Returns
    -------
    NDArray
        Smoothed 1D array.
    """
    # TODO: implement
    raise NotImplementedError


def savitzky_golay_smooth(ndvi_1d: NDArray, window: int = 7, polyorder: int = 2) -> NDArray:
    """
    Apply Savitzky–Golay smoothing to a 1D NDVI series.

    Parameters
    ----------
    ndvi_1d : NDArray
        1D NDVI array.
    window : int
        Window length (must be odd).
    polyorder : int
        Polynomial order.

    Returns
    -------
    NDArray
        Smoothed 1D array.
    """
    # TODO: implement using scipy.signal.savgol_filter
    raise NotImplementedError
