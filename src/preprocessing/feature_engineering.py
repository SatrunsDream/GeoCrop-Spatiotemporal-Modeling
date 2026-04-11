"""
feature_engineering.py — Feature matrix construction for crop-type prediction (Task 4).

Combines CDL history features, NDVI phenometrics, and SMAP statistics
into a single pixel-level feature DataFrame.

Approach options considered:
  A) Tabular feature matrix (pixel as row) — compatible with gradient boosting (LightGBM/XGBoost)
  B) 3D tensor (pixel × time × feature) — required for SITS deep learning (CNN/RNN/Transformer)
  C) Field-level aggregation using CSB polygons — reduces noise but requires extra data

Selected approach: A (tabular) — see DECISIONS.md DEC-005.
"""

import numpy as np
import pandas as pd
import xarray as xr


def build_cdl_history_features(
    cdl_stack: xr.DataArray,
    n_years_lookback: int = 5,
    crop_codes: dict | None = None,
) -> pd.DataFrame:
    """
    Construct CDL-history feature columns for each pixel.

    Features include: crop sequence encoding (last N years),
    transition frequencies, neighborhood composition (3×3 window),
    monoculture run length, and corn↔soy alternation score.

    Parameters
    ----------
    cdl_stack : xr.DataArray
        Multi-year CDL stack, dims (year, y, x).
    n_years_lookback : int
        Number of prior years to encode.
    crop_codes : dict or None
        Mapping of crop name to CDL code (e.g., {'corn': 1, 'soy': 5}).

    Returns
    -------
    pd.DataFrame
        Feature DataFrame with one row per pixel, columns: lat, lon, cdl_hist_*, transitions_*.
    """
    # TODO: implement
    raise NotImplementedError


def augment_with_ndvi_features(
    feature_df: pd.DataFrame,
    ndvi_phenometrics_path: str,
) -> pd.DataFrame:
    """
    Join NDVI phenometric statistics to the pixel feature DataFrame.

    NDVI features are at 250m resolution; joined to 30m pixels by nearest-cell lookup.

    Parameters
    ----------
    feature_df : pd.DataFrame
        Existing pixel feature DataFrame with lat/lon columns.
    ndvi_phenometrics_path : str
        Path to phenometrics Parquet file (from Task 1).

    Returns
    -------
    pd.DataFrame
        Feature DataFrame with additional NDVI columns (peak_ndvi, greenup_doy, etc.).
    """
    # TODO: implement
    raise NotImplementedError


def augment_with_smap_features(
    feature_df: pd.DataFrame,
    smap_anomaly_path: str,
) -> pd.DataFrame:
    """
    Join SMAP soil moisture contextual statistics to the pixel feature DataFrame.

    SMAP features are at 9km resolution; each 30m pixel inherits its parent SMAP cell's value.

    Parameters
    ----------
    feature_df : pd.DataFrame
        Existing pixel feature DataFrame with lat/lon columns.
    smap_anomaly_path : str
        Path to SMAP anomaly NetCDF (from Task 3).

    Returns
    -------
    pd.DataFrame
        Feature DataFrame with additional SMAP columns (mean_sm, anomaly_zscore_*).
    """
    # TODO: implement
    raise NotImplementedError
