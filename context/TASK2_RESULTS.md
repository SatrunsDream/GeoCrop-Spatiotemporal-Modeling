# Task 2 — Results and interpretation (crop rotation from CDL)

**Last updated:** 2026-04-11  
**Analysis window:** CDL years **2013–2022** (10 years), processed wide Parquet + spatial metadata from `data/processed/cdl/`.  
**Pipeline:** Notebooks **02→05** executed via `python -m jupyter nbconvert --execute` (non-interactive `MPLBACKEND=Agg`), after `python scripts/build_task2_notebooks.py`.

---

## 0. Executive summary (diagnostic read)

1. **Denominator shift matters.** There are **530,472** pixels that were **ever** corn or soy in the decade; **301,485 (56.8%)** meet the **rotation-eligibility** rule (corn or soy in **≥5** of 10 years, YAML `rotation_eligibility.min_cornsoy_years_for_metrics`). All metrics, classification shares, and sensitivity tables below use the **eligible** set unless stated otherwise.

2. **Strict composite classification is selective, not “broken.”** Under the primary YAML rule (alternation ≥ **0.70**, Hamming distance ≤ **3**, corn/soy years ≥ **7**, and not monoculture), **~16.5%** of eligible pixels are **regular rotation**, **~26.5%** **monoculture**, and **~57%** **irregular** (`rotation_metrics_classified.parquet`). The **smoothed GeoTIFF** export shows **~17.3% / 27.6% / 55.2%** (small edge effect from 3×3 majority filter). These are **internally consistent**; the story is **definition + simultaneous thresholds**, not a pipeline bug.

3. **Threshold sensitivity recovers “survey-like” fractions.** Relaxing only `alternation_min` and `pattern_dist_max` (holding `cs_min` and monoculture rules fixed) shows, for example, **~41.6% regular** at **(0.50, 5)** and **~44.3%** at **(0.50, 6)** (`artifacts/tables/task2/task2__threshold_sensitivity_grid.csv`). Use **strict** numbers as the **primary** headline; use the **sweep** in the report to answer **which metric combination is informative** and to relate to **USDA survey rotation** (~50–60% of Iowa cropland in *some* corn–soy rotation — a different definition and scale).

4. **Markov structure matches agronomic intuition at the transition level.** On eligible pixels, **P(corn→corn) ≈ 0.57** and **P(corn→soy) ≈ 0.31** (corn tends to **persist**); **P(soy→corn) ≈ 0.76** and **P(soy→soy) ≈ 0.10** (after soy, **return to corn** dominates). That is **consistent with a corn-heavy two-year logic** mixed with **other crops** and label noise — even when the strict **10-year Hamming** label is often “irregular.”

5. **Geography of *this* stack vs Corn Belt narrative.** Pixel centroids fall near **longitude −105.6 to −98.2** (all **west** of the **−96.35°W** proxy used for Iowa vs Nebraska in Notebook 05). The **per-region CSV** therefore has a **single** bucket (`Nebraska_proxy_west`) covering **all** classified pixels — not because the code failed, but because **no pixel lies east of that meridian** in the current extent. **Map text annotations** (Platte / Iowa belt) are **illustrative** for the report rubric; for a **literal** Iowa–Nebraska contrast, **extend or re-center the CDL stack** and/or use **state polygons** that intersect the raster footprint.

---

## 1. What we measured

| Metric | Meaning |
|--------|---------|
| **alternation_score** | Share of adjacent-year transitions that are corn↔soy when both years are corn or soy. |
| **max_run_length** | Longest run of the same CDL code. |
| **pattern_edit_distance** | Minimum Hamming distance to a strict 10-yr corn–soy alternation template (corn-first or soy-first). |
| **entropy** | Shannon entropy (bits) of the 10-year CDL code sequence at the pixel. |
| **n_cornsoy_years** | Count of years in {corn, soy}. |
| **crop_share** | Fraction of years equal to the modal crop code. |

**Denominators**

1. **Ever corn/soy** — ≥1 year as corn or soy (**n = 530,472**): used in NB02 only for the **`n_cornsoy_years` histogram** before filtering.  
2. **Rotation-eligible** — ≥**5** years as corn or soy (**n = 301,485**): rows in `rotation_metrics.parquet`, classification, sensitivity, and Markov aggregates.

**Classification rules** (`configs/task2_crop_rotation.yaml`)

- **Regular rotation (0):** alternation ≥ 0.70, pattern distance ≤ 3, corn/soy years ≥ 7, and **not** monoculture.  
- **Monoculture (1):** max run ≥ 7 **or** crop_share ≥ 0.80.  
- **Irregular (2):** all other **eligible** pixels.

---

## 2. Numeric results (this run)

### 2.1 Metric summaries — **rotation-eligible** pixels only (`rotation_metrics.parquet`, n = 301,485)

| Metric | Mean | Median | Notes |
|--------|------|--------|--------|
| alternation_score | **0.47** | **0.50** | After eligibility, the median is no longer stuck at zero: pixels with very few corn/soy years (no transitions) were removed. |
| max_run_length | 3.7 | 3 | Typical longest run remains modest. |
| pattern_edit_distance | **4.4** | **5** | Still **far** from perfect alternation (0); Hamming to a strict 10-step template remains **harsh** for CDL mixed sequences. |
| entropy | 1.13 | 1.0 | Moderate label diversity. |
| n_cornsoy_years | **8.4** | **9** | Eligibility + classification both push toward **corn/soy-heavy** years. |
| crop_share | 0.64 | 0.60 | Modal crop dominates most years on average. |

### 2.2 Class distribution — primary YAML (`rotation_metrics_classified.parquet`)

| Class | Code | Share of **eligible** pixels |
|-------|------|--------------------------------|
| Regular rotation | 0 | **~16.5%** |
| Monoculture | 1 | **~26.5%** |
| Irregular | 2 | **~57.0%** |

### 2.3 Areal summary — **smoothed** GeoTIFF (`task2__areal_stats_by_class__20260411.csv`)

Footprint = **classified cells only** on the **analysis grid** (~**10.22 ha/pixel**, ~**320 m** effective cell size, NAD83 / Conus Albers — see companion `*__metadata.json`). **Not** native 30 m USDA field area.

| Class | Pixel count | Area (10³ ha) | % of valid cells |
|-------|-------------|-----------------|------------------|
| regular_rotation | 52,080 | ~532 | **17.27%** |
| monoculture | 83,069 | ~849 | **27.55%** |
| irregular | 166,337 | ~1,700 | **55.17%** |
| **Total** | **301,485** | **~3.08 × 10⁶ ha** | 100% |

### 2.4 Markov transitions — corn / soy / other (`task2__markov_transition_probs.csv`)

Row = **from** (year t), column = **to** (year t+1). Values are **empirical P(to | from)** across all eligible pixel-years.

| From \\ To | corn | soy | other |
|------------|------|-----|-------|
| corn | **0.57** | **0.31** | 0.11 |
| soy | **0.76** | 0.10 | 0.14 |
| other | 0.54 | 0.12 | 0.35 |

**Read:** Strong **soy → corn** and **corn → corn** mass; **corn → soy** is substantial but **below 0.5**, so the matrix does **not** look like a perfect two-state alternator — consistent with **continuous corn**, **third crops**, and **CDL noise** at coarse resolution.

### 2.5 Threshold sensitivity (excerpt — full grid in CSV)

Same **301,485** pixels; only **alternation_min** and **pattern_dist_max** vary; **cs_min = 7** and monoculture rule unchanged.

| alternation_min | pattern_dist_max | % regular | % monoculture | % irregular |
|-----------------|------------------|-----------|----------------|---------------|
| 0.70 | 3 | **16.48** | 26.46 | 57.06 |
| 0.60 | 4 | 28.11 | 26.46 | 45.43 |
| 0.50 | 5 | **41.56** | 26.46 | 31.98 |
| 0.50 | 6 | **44.32** | 26.46 | 29.21 |

**Figure:** `artifacts/figures/task2/task2__threshold_sensitivity_regular_pct.png`.

**Monoculture column:** `% monoculture` is **identical (26.46%)** for every row in the full 20-row grid — the monoculture rule depends only on **run length** and **crop share**, not on `alternation_min` or `pattern_dist_max`.

### 2.6 Per-region table (Notebook 05)

`task2__areal_stats_by_region__20260411.csv` currently lists **one** region because **every** eligible pixel centroid lies **west** of the **−96.35°W** proxy meridian (see §0). For a **meaningful Iowa vs Nebraska split**, align the **raster extent** with both states or use **polygons** that intersect the grid.

### 2.7 Novel findings from existing outputs (Findings A–F)

These are **interpretive** layers on artifacts already in the repo (no new downloads). Exact percentages update if you re-run NB02/03; values below match the **2026-04-11** run.

| ID | Source | Takeaway | Report hook |
|----|--------|----------|---------------|
| **A** | `task2__markov_transition_probs.csv` | **P(soy→corn) ≈ 0.76** vs **P(corn→soy) ≈ 0.31** → asymmetry ratio **~2.4×**. Soy acts as a **break** before returning to corn dominance, not as a symmetric 50/50 alternation partner (contrast symmetric C↔S narrative in much of the literature). | Q3 (which combinations are informative), innovation |
| **B** | `task2__threshold_sensitivity_grid.csv` | **pct_monoculture = 26.46%** on **all 20** threshold pairs — monoculture is **orthogonal** to the alternation–Hamming sweep; taxonomy has a **persistence axis** (run/share) separate from a **template-match axis** (alt + distance). | Q3 |
| **C** | Same sensitivity CSV | **Strict (0.70, 3):** regular **<** monoculture (~16.5% vs ~26.5%). **Relaxed (0.50, 4):** regular **>** monoculture (~33.6% vs ~26.5%). A **crossover / balance band** sits near **(0.60–0.65, dist_max 4)** where both classes are ~27–28% — useful **calibration** language. | Q4 (irregular / metric behavior) |
| **D** | Markov `other` row | **P(other→corn) ≈ 0.54** vs **P(other→soy) ≈ 0.12** — “other” CDL years are usually **short interruptions** before corn again; supports **entropy > 1 bit** without implying long diversified rotations. | Q4 |
| **E** | `task2__markov_transition_counts.csv` row sums | Share of **all** eligible pixel-year transitions by **origin** state ≈ **61% corn / 22% soy / 16% other** (volume ratio corn:soy ~**2.7:1** on this stack). Explains why **strict regular** remains a **minority** class on a **corn-heavy** footprint. | Q5 (decision support / agronomic calibration) |
| **F** | `max_run_length` in `rotation_metrics.parquet` | Discrete **run-length** distribution (`task2__runlength_distribution.png`) shows how mass sits below vs in the **≥7** monoculture rule zone — supports the monoculture **story** beyond a single scalar %. | Methods / monoculture |

---

## 3. Interpretation (what this means)

1. **Methodology is coherent.** Parquet metrics, `classify_batch` labels, GeoTIFF fills, areal CSV, sensitivity CSV, and Markov exports **tell one story**: strict **intersection** of rules yields a **modest regular class**; **relaxing** distance and alternation thresholds **monotonically** expands that class toward **literature-reported rotation prevalence** at the cost of **precision**.

2. **Eligibility (≥5 corn/soy years)** removed the **noisiest tail** of the ever pool (pixels with only 1–2 touch years). That **raised** interpretability of alternation and edit distance (median alternation **0.5** vs the old ever-pool **0** median) and **increased** the strict regular share vs the historical **~9%** “ever only” run — still **not** majority regular, because **Hamming ≤3** + **alternation ≥0.7** + **≥7** corn/soy years is **demanding**.

3. **Monoculture share ~27%** is **plausible** for continuous corn, long runs, or high modal crop share under CDL at **~320 m**.

4. **Maps and annotations** are best used as **communication** tools; tie **claims** to **actual bbox** and **metadata.json** so reviewers do not confuse **grid footprint** with **USDA NASS acreage**.

---

## 4. Are these results “very good / strong”?

| Dimension | Assessment |
|-----------|------------|
| **Reproducibility / methodology** | **Strong:** config-driven rules, documented denominators, sensitivity sweep, Markov layer, metadata JSON, executable notebooks (nbformat-valid for `nbconvert`). |
| **Plausibility vs surveys** | **Good if framed correctly:** strict **~16–17% regular** is **low vs farmer-reported rotation intent**; **relaxed (0.5, 5–6)** brings **~42–44% regular**, which **bridges** survey language. State that explicitly in the report. |
| **External validation** | **Not strong** — no independent field rotation labels in-repo; literature comparison is the right substitute. |

**Bottom line:** The run is **submission-ready** for **methods + sensitivity + honesty about scale**. It is **not** “validated strong” against ground truth until you add **external** or **independent** labels.

---

## 5. How to improve (short list)

1. **Geography:** extend CDL processing to a bbox that includes **eastern Nebraska + Iowa**, or drive NB05 from **state polygons** that intersect the stack; **retire or relocate** the **−96.35°W** proxy if it does not split your extent.  
2. **Report text:** one paragraph linking **strict** vs **relaxed** sweep to **USDA NASS** definitions (Q3/Q4).  
3. **Optional:** unit tests for small **synthetic** sequences against known Markov counts; keep **seaborn** out of NB02 so **minimal** envs still run (current NB02 uses **matplotlib** only).  
4. **Out of scope (per project brief):** full 30 m five-state re-download, CSB polygon join, replacing the entire metric family before the deadline.

---

## 6. File index (this run)

| Path | Role |
|------|------|
| `data/processed/task2/rotation_metrics.parquet` | Eligible-only metrics. |
| `data/processed/task2/task2__markov_transition_{counts,probs}.csv` | Markov aggregates. |
| `data/processed/task2/rotation_metrics_classified.parquet` | Metrics + `rotation_class`. |
| `data/processed/task2/rotation_class_map*.tif` | Raw + smoothed rasters. |
| `artifacts/tables/task2/task2__threshold_sensitivity_grid.csv` | Full sensitivity grid. |
| `artifacts/tables/task2/task2__areal_stats_by_class__*.csv` | Areal by class. |
| `artifacts/tables/task2/task2__areal_stats_by_class__*__metadata.json` | `pixel_area_ha`, ~320 m resolution note, CRS. |
| `artifacts/tables/task2/task2__areal_stats_by_region__*.csv` | Regional % (when extent supports split). |
| `artifacts/figures/task2/task2__ncornsoy_histogram.png` | Eligibility cutoff visualization. |
| `artifacts/figures/task2/task2__markov_corn_soy_other.png` | Markov heatmap. |
| `artifacts/figures/task2/task2__threshold_sensitivity_regular_pct.png` | Sensitivity lines. |
| `artifacts/figures/task2/task2__transition_asymmetry.png` | Four-bar corn/soy Markov transitions + asymmetry (NB02). |
| `artifacts/figures/task2/task2__runlength_distribution.png` | Discrete max run length 1–10 (NB02). |
| `artifacts/figures/task2/task2__metric_histograms.png`, `task2__alt_vs_distance.png` | Diagnostics. |
| `artifacts/figures/task2/task2__rotation_map__*__*.png` | Maps + annotations. |

---

## 7. Cross-references

- `configs/task2_crop_rotation.yaml` — thresholds and year window.  
- `context/RISKS.md` — CDL label noise, scale mismatch.  
- `context/structure.md` — artifact index and per-notebook log.  
- `context/STATUS.md` — project phase checklist.
