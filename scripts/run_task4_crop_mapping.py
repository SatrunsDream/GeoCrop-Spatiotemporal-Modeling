#!/usr/bin/env python3
# Disclaimer: Fully AI-generated.
"""Build Task 4 rolling panel, train LightGBM, evaluate temporal holdout, save artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=REPO_ROOT / "configs" / "task4_crop_mapping.yaml")
    p.add_argument("--skip-panel", action="store_true", help="Load existing feature_matrix_panel.parquet")
    args = p.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    out_t = REPO_ROOT / cfg["output"]["tables_dir"]
    out_m = REPO_ROOT / cfg["output"]["models_dir"]
    out_t.mkdir(parents=True, exist_ok=True)
    out_m.mkdir(parents=True, exist_ok=True)
    proc = REPO_ROOT / cfg["output"]["processed_dir"]
    panel_path = proc / "feature_matrix_panel.parquet"

    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from src.modeling.crop_type_model import (
        default_feature_columns,
        evaluate_multiclass,
        save_model,
        train_lightgbm_classifier,
    )
    from src.preprocessing.task4_panel import (
        assemble_training_panel,
        build_test_year_frame,
        train_val_test_split,
    )

    if args.skip_panel and panel_path.is_file():
        panel = pd.read_parquet(panel_path)
    else:
        panel = assemble_training_panel(REPO_ROOT, cfg, save_path=panel_path)

    tr, va = train_val_test_split(panel, cfg)
    tr = tr[np.isfinite(tr["label"])].copy()
    va = va[np.isfinite(va["label"])].copy()
    fe = default_feature_columns(tr)
    hp = dict(cfg["model"]["hyperparameters"])
    hp.setdefault("objective", "multiclass")
    hp["num_class"] = int(max(tr["label"].max(), va["label"].max()) + 1)
    hp["n_estimators"] = int(hp.get("n_estimators", 500))
    es = int(cfg["model"].get("early_stopping_rounds", 50))

    clf = train_lightgbm_classifier(
        tr,
        va,
        fe,
        hp=hp,
        early_stopping_rounds=es,
        categorical=None,
    )
    y_pred_va = clf.predict(va[fe])
    metrics = evaluate_multiclass(va["label"].values, y_pred_va)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    metrics_path = out_t / f"task4__classification_metrics__{stamp}.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    save_model(clf, out_m / "crop_type_model.joblib")

    test_y = int(cfg["panel"]["test_year"])
    test_df = build_test_year_frame(REPO_ROOT, cfg, test_y)
    test_df = test_df[np.isfinite(test_df["label"])].copy()
    y_te = clf.predict(test_df[fe])
    test_metrics = evaluate_multiclass(test_df["label"].values, y_te)
    (out_t / f"task4__test_metrics__{stamp}.json").write_text(
        json.dumps(test_metrics, indent=2), encoding="utf-8"
    )
    print("Wrote", panel_path, metrics_path)


if __name__ == "__main__":
    main()
