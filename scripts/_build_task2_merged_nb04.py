"""Build notebooks/task2_crop_rotation/04_spatial_maps_and_areal_export.ipynb from old 04+05 sources."""
from __future__ import annotations

import copy
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_DEP = REPO / "notebooks" / "task2_crop_rotation" / "_deprecated"
D04 = _DEP / "04_spatial_mapping_rotation.ipynb"
D05 = _DEP / "05_areal_statistics_export.ipynb"
OUT = REPO / "notebooks" / "task2_crop_rotation" / "04_spatial_maps_and_areal_export.ipynb"

MD0 = """# Task 2 — Notebook 04: Spatial maps, Bayesian DM surfaces, areal statistics, county export

**Order:** Run **01 → 02 → 03** first (metrics, classification, GeoTIFFs + `rotation_metrics_classified.parquet`).

This notebook combines the former **04** (rotation-class maps + core-belt zoom) and **05** (areal tables, per-state bars, `run_bundle.json`, county choropleths).

**NAFSI Task 2 deliverables addressed here:**
- **Spatial distribution** of rotation classes (raw + smoothed GeoTIFF maps).
- **Bayesian Dirichlet–Multinomial** companion maps: `rotation_dm_p_regular.tif` (posterior P(regular)) and `rotation_dm_alt_posterior_std.tif` (epistemic spread of the alternation proxy), written in Notebook **03** when `bayesian_dm` is enabled in `configs/task2_crop_rotation.yaml`.
- **Areal proportions** by class (CSV + metadata JSON), **per-state** class mix, **run bundle**.
- **County-level** shares (TIGER) and optional core-four-state zoom — association with administrative boundaries (water/soil still out of scope unless you add layers).

**Outputs:** `artifacts/figures/task2/`, `artifacts/tables/task4/`, `artifacts/logs/runs/*/run_bundle.json`.
"""

EXTRA_DM = """## Bayesian rotation probability maps (Dirichlet–Multinomial)

Monte Carlo posterior **P(regular)** uses independent Dirichlet posteriors on **corn-row** and **soy-row** transition counts (see `src/modeling/rotation_bayesian_dm.py`). Nodata = **-9999** outside eligible pixels or missing columns.
"""

CODE_DM = r"""import numpy as np
from pathlib import Path

import rasterio
from rasterio.plot import plotting_extent
from matplotlib.colors import Normalize

_dm_paths = [
    ("Posterior P(regular rotation)", "rotation_dm_p_regular.tif", "viridis", 0.0, 1.0, -9999.0),
    ("Posterior std of alternation proxy", "rotation_dm_alt_posterior_std.tif", "magma", None, None, -9999.0),
]
for title, fname, cmap, vmin, vmax, nd in _dm_paths:
    p = out_dir / fname
    if not p.is_file():
        print("skip missing", p.name)
        continue
    with rasterio.open(p) as src:
        arr = src.read(1).astype(np.float64)
    m = arr == nd
    arr = np.ma.array(arr, mask=m)
    fig_dm, ax_dm = plt.subplots(figsize=(9, 7), dpi=120)
    if vmin is None:
        vn = float(np.nanmin(arr.compressed())) if arr.count() else 0.0
        vx = float(np.nanmax(arr.compressed())) if arr.count() else 1.0
        norm = Normalize(vmin=vn, vmax=max(vx, vn + 1e-6))
    else:
        norm = Normalize(vmin=vmin, vmax=vmax)
    im = ax_dm.imshow(arr, extent=[*plotting_extent(src)], origin="upper", cmap=cmap, norm=norm)
    if states is not None and not states.empty:
        states.boundary.plot(ax=ax_dm, color="#222", linewidth=0.5)
    plt.colorbar(im, ax=ax_dm, fraction=0.035, pad=0.02)
    ax_dm.set_title(f"{title} | {_cdl_span}")
    ax_dm.set_axis_off()
    outp_dm = fig_dir / f"task2__{Path(fname).stem}__{date.today():%Y%m%d}.png"
    fig_dm.savefig(outp_dm, dpi=200, bbox_inches="tight")
    plt.show()
    print("Saved", outp_dm.relative_to(REPO_ROOT))
"""


def _clean_cell(c: dict) -> dict:
    c = copy.deepcopy(c)
    c.pop("outputs", None)
    c["execution_count"] = None
    return c


def main() -> None:
    nb4 = json.loads(D04.read_text(encoding="utf-8"))
    nb5 = json.loads(D05.read_text(encoding="utf-8"))

    cells = []
    cells.append({"cell_type": "markdown", "metadata": {}, "source": [MD0]})

    cells.append(_clean_cell(nb4["cells"][1]))
    cells.append(_clean_cell(nb4["cells"][2]))
    cells.append(_clean_cell(nb4["cells"][3]))

    cells.append({"cell_type": "markdown", "metadata": {}, "source": [EXTRA_DM]})
    cells.append(
        {
            "cell_type": "code",
            "metadata": {},
            "source": CODE_DM.splitlines(keepends=True),
        }
    )

    cells.append(
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Areal statistics, per-state summary, and run bundle\n",
                "\n",
                "Uses the **smoothed** class GeoTIFF when present (same as former Notebook 05).\n",
            ],
        }
    )
    cells.append(_clean_cell(nb5["cells"][1]))
    cells.append(_clean_cell(nb5["cells"][2]))
    cells.append(_clean_cell(nb5["cells"][3]))

    nb_out = {
        "cells": cells,
        "metadata": nb4.get("metadata", {}),
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUT.write_text(json.dumps(nb_out, indent=1), encoding="utf-8")
    nb_fix = json.loads(OUT.read_text(encoding="utf-8"))
    marker = (
        '        "rotation_map_smoothed": str(sm_tif.relative_to(REPO_ROOT)).replace("\\\\", "/"),\n'
    )
    ins = (
        marker
        + '        "rotation_dm_p_regular_tif": str((REPO_ROOT / cfg["output"]["processed_dir"] / "rotation_dm_p_regular.tif").relative_to(REPO_ROOT)).replace("\\\\", "/"),\n'
        + '        "rotation_dm_alt_posterior_std_tif": str((REPO_ROOT / cfg["output"]["processed_dir"] / "rotation_dm_alt_posterior_std.tif").relative_to(REPO_ROOT)).replace("\\\\", "/"),\n'
    )
    for c in nb_fix["cells"]:
        if c.get("cell_type") != "code":
            continue
        s = "".join(c.get("source", []))
        if '"rotation_dm_p_regular_tif"' in s or marker not in s:
            continue
        c["source"] = s.replace(marker, ins, 1).splitlines(keepends=True)
        break
    OUT.write_text(json.dumps(nb_fix, indent=1), encoding="utf-8")
    print("Wrote", OUT.relative_to(REPO))


if __name__ == "__main__":
    main()
