"""
Task 2 — crop rotation from CDL (NAFSI Track 1).

There is no single long-running CLI here: the analysis is implemented as Jupyter
notebooks under ``notebooks/task2_crop_rotation/`` (run **01 → 05** in order).

**Prerequisites**
  1. Processed CDL: ``data/processed/cdl/cdl_stack_wide.parquet`` +
     ``cdl_stack_spatial_metadata.json`` from
     ``python scripts/process_interim_to_parquet.py --dataset cdl --source interim``
  2. Config: ``configs/task2_crop_rotation.yaml`` (years, thresholds, ``output.*`` paths)

**Outputs (YAML-driven)**
  - Figures → ``artifacts/figures/task2/``
  - Tables → ``artifacts/tables/task2/``
  - Rasters + Parquet cache → ``data/processed/task2/``

See ``context/TASK2_NAFSI_DATA_CONTRACT.md`` and ``resources/CropSmart_NAFSI_Track1_Challenge_Brief.docx.pdf``.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    nb = REPO_ROOT / "notebooks" / "task2_crop_rotation"
    print("Task 2 - run notebooks in order:\n")
    for name in (
        "01_cdl_timeseries_loading.ipynb",
        "02_rotation_metrics_computation.ipynb",
        "03_rotation_classification.ipynb",
        "04_spatial_mapping_rotation.ipynb",
        "05_areal_statistics_export.ipynb",
    ):
        print(f"  {nb / name}")
    print("\nConfig:", REPO_ROOT / "configs" / "task2_crop_rotation.yaml")
    print("Data contract:", REPO_ROOT / "context" / "TASK2_NAFSI_DATA_CONTRACT.md")


if __name__ == "__main__":
    main()
