# Disclaimer: Fully AI-generated.
"""LightGBM crop-type classifier for Task 4 rolling panel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

import joblib

try:
    import lightgbm as lgb
except ImportError as e:  # pragma: no cover
    lgb = None
    _LGB_ERR = e


def default_feature_columns(df: pd.DataFrame) -> list[str]:
    drop = {"iy", "ix", "year", "label"}
    cols = []
    for c in df.columns:
        if c in drop:
            continue
        if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]):
            continue
        cols.append(c)
    return cols


def train_lightgbm_classifier(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    label_col: str = "label",
    hp: dict[str, Any] | None = None,
    early_stopping_rounds: int = 50,
    categorical: list[str] | None = None,
) -> Any:
    if lgb is None:
        raise ImportError("lightgbm is required") from _LGB_ERR
    hp = hp or {}
    X_tr = train_df[feature_cols]
    y_tr = train_df[label_col].astype(int)
    X_va = val_df[feature_cols]
    y_va = val_df[label_col].astype(int)
    cat = categorical or []
    clf = lgb.LGBMClassifier(**hp)
    fit_kw: dict[str, Any] = {
        "eval_set": [(X_va, y_va)],
        "callbacks": [
            lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=False),
            lgb.log_evaluation(period=0),
        ],
    }
    cfeat = [c for c in cat if c in feature_cols]
    if cfeat:
        fit_kw["categorical_feature"] = cfeat
    clf.fit(X_tr, y_tr, **fit_kw)
    return clf


def evaluate_multiclass(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list[str] | None = None,
) -> dict[str, Any]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    oa = float(accuracy_score(y_true, y_pred))
    f1s = f1_score(y_true, y_pred, average=None, zero_division=0)
    macro = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    cm = confusion_matrix(y_true, y_pred)
    out: dict[str, Any] = {
        "overall_accuracy": oa,
        "macro_f1": macro,
        "per_class_f1": {str(i): float(f1s[i]) for i in range(len(f1s))},
        "confusion_matrix": cm.tolist(),
    }
    if class_names:
        out["per_class_f1_named"] = {
            class_names[i]: float(f1s[i]) for i in range(min(len(class_names), len(f1s)))
        }
    return out


def save_model(model: Any, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def tune_lightgbm_optuna(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    label_col: str = "label",
    n_trials: int = 25,
    timeout: int | None = None,
    n_classes: int = 4,
    seed: int = 42,
    search_space: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run Optuna TPE search over LightGBM hyperparameters.

    Returns a dict with keys ``best_params``, ``best_value`` (macro F1),
    and ``study`` (the Optuna study object).
    """
    if lgb is None:
        raise ImportError("lightgbm is required") from _LGB_ERR
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    ss = search_space or {}
    X_tr = train_df[feature_cols]
    y_tr = train_df[label_col].astype(int)
    X_va = val_df[feature_cols]
    y_va = val_df[label_col].astype(int)

    def objective(trial: optuna.Trial) -> float:
        hp = {
            "objective": "multiclass",
            "num_class": n_classes,
            "verbosity": -1,
            "random_state": seed,
            "is_unbalance": True,
            "n_estimators": trial.suggest_int(
                "n_estimators",
                ss.get("n_estimators_lo", 500),
                ss.get("n_estimators_hi", 3000),
                step=100,
            ),
            "learning_rate": trial.suggest_float(
                "learning_rate",
                ss.get("learning_rate_lo", 0.005),
                ss.get("learning_rate_hi", 0.1),
                log=True,
            ),
            "max_depth": trial.suggest_int(
                "max_depth",
                ss.get("max_depth_lo", 5),
                ss.get("max_depth_hi", 12),
            ),
            "num_leaves": trial.suggest_int(
                "num_leaves",
                ss.get("num_leaves_lo", 31),
                ss.get("num_leaves_hi", 255),
            ),
            "min_child_samples": trial.suggest_int(
                "min_child_samples",
                ss.get("min_child_samples_lo", 5),
                ss.get("min_child_samples_hi", 100),
            ),
            "subsample": trial.suggest_float(
                "subsample",
                ss.get("subsample_lo", 0.6),
                ss.get("subsample_hi", 1.0),
            ),
            "colsample_bytree": trial.suggest_float(
                "colsample_bytree",
                ss.get("colsample_bytree_lo", 0.5),
                ss.get("colsample_bytree_hi", 1.0),
            ),
            "reg_alpha": trial.suggest_float(
                "reg_alpha",
                ss.get("reg_alpha_lo", 1e-3),
                ss.get("reg_alpha_hi", 10.0),
                log=True,
            ),
            "reg_lambda": trial.suggest_float(
                "reg_lambda",
                ss.get("reg_lambda_lo", 1e-3),
                ss.get("reg_lambda_hi", 10.0),
                log=True,
            ),
        }
        clf = lgb.LGBMClassifier(**hp)
        clf.fit(
            X_tr, y_tr,
            eval_set=[(X_va, y_va)],
            callbacks=[
                lgb.early_stopping(stopping_rounds=100, verbose=False),
                lgb.log_evaluation(period=0),
            ],
        )
        y_pred = clf.predict(X_va)
        return float(f1_score(y_va, y_pred, average="macro", zero_division=0))

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed),
    )
    study.optimize(objective, n_trials=n_trials, timeout=timeout)

    return {
        "best_params": study.best_trial.params,
        "best_value": study.best_trial.value,
        "study": study,
    }
