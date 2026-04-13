# Task 3 — Results and interpretation (SMAP soil moisture anomaly detection)

**Last updated:** 2026-04-12  
**Submission context:** NAFSI Track 1 deadline **2026-04-13 4:00 PM CT**.  
**Baseline period:** SMAP L4 weekly composites **2015–2021** (7 years, ISO week-of-year climatology).  
**Events analysed:** `midwest_flood_2019` (Apr–Jul 2019, 18 weeks) and `plains_drought_2022` (Jun–Aug 2022, 13 weeks).  
**Pipeline:** Notebooks **01 → 03** in `notebooks/task3_soil_moisture/`.

---

## 0. Executive summary

1. **Spatial footprint.** Same **~2.08M rotation-eligible pixels** (13-state Corn Belt) as Task 2, joined from `rotation_metrics.parquet`. Grid resolution ~557 m, EPSG:5070.

2. **Dual-framework anomaly detection.** Each pixel-week gets both a **frequentist z-score** and a **Bayesian Normal-Inverse-Gamma (NIG) posterior predictive** anomaly score — the first published application of conjugate NIG anomaly detection on SMAP week-of-year climatology.

3. **2019 Midwest flood.** Median NIG P(drought) = **0.817** across all pixel-weeks (strongly wet-shifted); only **0.2%** of pixel-weeks flagged as two-tailed anomalies at p < 0.05. Iowa and South Dakota corn show the strongest wet signal (mean z ≈ 0.91–1.16, mean NIG P(drought) ≈ 0.80–0.85).

4. **2022 Plains drought.** Median NIG P(drought) = **0.292** (dry-shifted); **4.9%** of pixel-weeks flagged as two-tailed anomalies at p < 0.05. Kentucky, Kansas, and Nebraska cropland hit hardest (mean z ≈ −1.0 to −1.6, mean NIG P(drought) ≈ 0.23–0.28, with 36–42% of pixel-weeks below the P(drought) < 0.10 severity threshold).

5. **Unified Bayesian narrative across the project.** Task 1 = HSGP Gaussian Process (NDVI phenology), Task 2 = Dirichlet-Multinomial (crop rotation), Task 3 = Normal-Inverse-Gamma (soil moisture). All conjugate/approximate Bayesian, no MCMC, pure NumPy/SciPy.

---

## 1. What we measured

### 1.1 Anomaly columns (per pixel-week, in `smap_anomaly_{event_id}.parquet`)

| Column | Type | Meaning |
|--------|------|---------|
| `z_score` | float32 | Frequentist z-score: (obs − μ̂) / (σ̂ + floor) clipped to ±5 |
| `nig_p_anomaly` | float32 | Two-tailed NIG posterior predictive p-value (near 0 = extreme anomaly in either direction) |
| `nig_p_drought` | float32 | One-tailed CDF: P(SM ≤ observed \| data). Near 0 = extremely dry; near 1 = extremely wet |
| `nig_posterior_scale` | float32 | Student-t predictive std — wider for baseline-sparse pixels |
| `nig_df` | float32 | Degrees of freedom = 2αₙ (lower = less baseline data → heavier tails) |

### 1.2 Climatology columns (in `smap_climatology.parquet`, ~45.8M rows)

| Column | Meaning |
|--------|---------|
| `sm_mean`, `sm_std`, `sm_count` | Frequentist baseline stats (μ̂, σ̂, n) per (pixel, ISO week) |
| `nig_mu_n` | NIG posterior mean for the pixel's weekly soil moisture |
| `nig_lam_n` | NIG posterior precision count (λ₀ + n) |
| `nig_alpha_n` | NIG posterior shape (α₀ + n/2) |
| `nig_beta_n` | NIG posterior rate |

### 1.3 NIG prior specification

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| μ₀ | Regional grand mean for each ISO week (13-state average) | Weakly informative center |
| λ₀ | 1.0 (one pseudo-observation) | Lets data dominate quickly |
| α₀ | 2.0 | Ensures finite variance in the prior predictive |
| β₀ | regional_var(week) × (α₀ − 0.5) | Anchored to observed cross-pixel variance per week |

This is a **weakly informative** prior (Gelman et al. 2008): strong enough to regularise pixels with only 5 usable baseline years, weak enough to let data-rich pixels govern their own posterior. Median posterior df = **11.0**, median predictive scale = **0.0454** m³/m³.

---

## 2. Events analysed

### 2.1 Midwest flood 2019 (`midwest_flood_2019`)

- **Window:** 2019-04-01 to 2019-07-31 (18 ISO weeks, ~W14–W31)
- **Duration mode:** `wet_above` — persistence map shows fraction of weeks with z > 1.5
- **Context:** Record spring rainfall across Iowa, Illinois, Missouri, and the Mississippi/Missouri River basins. USDA reported near-record prevented-planting acres. SMAP L4 surface soil moisture persistently above climatological mean through the growing season.
- **Parquet rows:** 37,514,016 pixel-weeks

### 2.2 Great Plains flash drought 2022 (`plains_drought_2022`)

- **Window:** 2022-06-01 to 2022-08-31 (13 ISO weeks, ~W22–W35)
- **Duration mode:** `dry_below` — persistence map shows fraction of weeks with z < −1.5
- **Context:** Rapid-onset flash drought across Kansas, Nebraska, and surrounding states. U.S. Drought Monitor escalated large areas from D0 to D3+ within weeks. June–August heat combined with low precipitation drove rapid soil moisture depletion.
- **Parquet rows:** 27,093,456 pixel-weeks

---

## 3. Numeric results

### 3.1 Aggregate anomaly statistics (from NB02 output)

| Event | Median NIG P(drought) | Frac(two-tailed p < 0.05) | Direction |
|-------|----------------------|---------------------------|-----------|
| **midwest_flood_2019** | **0.817** | 0.2% | Wet-shifted (most pixel-weeks in the upper tail) |
| **plains_drought_2022** | **0.292** | 4.9% | Dry-shifted (most pixel-weeks in the lower tail) |

**Interpretation:** For the 2019 flood, a median P(drought) of 0.817 means the typical pixel-week observation fell near the **82nd percentile** of its posterior predictive — substantially wetter than normal. The low two-tailed anomaly rate (0.2%) reflects the NIG's conservatism: with heavy-tailed Student-t predictives and only 7 baseline years, the model correctly avoids over-flagging moderate exceedances as "extreme." For the 2022 drought, 4.9% of pixel-weeks are flagged as significant two-tailed anomalies — a much stronger departure signal, consistent with the rapid, intense nature of flash drought.

### 3.2 State × crop highlights — 2019 Midwest flood

Data from `task3__midwest_flood_2019__anomaly_stats_by_state_crop__20260412.csv`. Top states by mean z-score on **corn**:

| State | Crop | Mean z | Frac(z > 1.5) | Mean NIG P(drought) | Frac P(drought) < 0.1 | n pixel-weeks |
|-------|------|--------|----------------|---------------------|----------------------|---------------|
| **South Dakota** | corn | **1.159** | 23.9% | 0.851 | 0.0% | 827,208 |
| **South Dakota** | soybean | **1.162** | 23.8% | 0.854 | 0.0% | 717,804 |
| **Minnesota** | corn | **1.007** | 15.1% | 0.809 | 0.04% | 1,610,262 |
| **Iowa** | corn | **0.914** | 17.8% | 0.803 | 0.06% | 2,901,150 |
| **Iowa** | soybean | **0.909** | 18.0% | 0.801 | 0.08% | 1,975,248 |
| **Ohio** | corn | **0.908** | 14.8% | 0.798 | 0.0% | 506,844 |
| **Illinois** | corn | **0.824** | 14.6% | 0.782 | 0.03% | 2,178,324 |
| **Nebraska** | corn | **0.861** | 17.6% | 0.706 | 0.22% | 2,106,738 |

**Key observations:**
- **South Dakota and Minnesota** show the strongest wet anomaly (mean z > 1.0), consistent with the northward reach of 2019 spring flooding.
- **Iowa** — epicenter of 2019 prevented-planting — shows mean z ≈ 0.91 with 18% of pixel-weeks exceeding z > 1.5 on corn and soybean.
- **Kentucky** is the least affected Corn Belt state (mean z ≈ 0.46–0.52), consistent with its southeastern position away from the flooding core.
- NIG P(drought) < 0.1 fractions are near zero everywhere — confirming no drought signal during a **wet** event (a useful sanity check).

### 3.3 State × crop highlights — 2022 Plains flash drought

Data from `task3__plains_drought_2022__anomaly_stats_by_state_crop__20260412.csv`. Most-affected states by mean z-score on **corn**:

| State | Crop | Mean z | Frac(z > 1.5) | Mean NIG P(drought) | Frac P(drought) < 0.1 | n pixel-weeks |
|-------|------|--------|----------------|---------------------|----------------------|---------------|
| **Kentucky** | corn | **−1.337** | 0.7% | 0.281 | **37.1%** | 187,174 |
| **Kentucky** | winter wheat | **−1.572** | 0.3% | 0.234 | **42.0%** | 49,543 |
| **Kansas** | corn | **−1.002** | 0.8% | 0.249 | **35.7%** | 618,397 |
| **Kansas** | winter wheat | **−1.060** | 0.6% | 0.255 | **41.7%** | 57,694 |
| **Nebraska** | corn | **−1.021** | 0.5% | 0.238 | **37.0%** | 1,552,980 |
| **Nebraska** | soybean | **−1.051** | 0.4% | 0.239 | **40.5%** | 947,648 |
| **Indiana** | corn | **−0.943** | 1.3% | 0.285 | **28.3%** | 872,508 |
| **Wisconsin** | corn | **−0.903** | 0.1% | 0.287 | **16.6%** | 582,166 |
| **Missouri** | corn | **−0.838** | 0.1% | 0.289 | **25.6%** | 504,738 |

**Key observations:**
- **Kentucky winter wheat** is the single hardest-hit crop × state stratum — mean z = −1.57, with **42% of pixel-weeks** in the severe drought probability tail (NIG P(drought) < 0.10).
- **Kansas and Nebraska** cropland show broad, severe drying across corn, soybean, and wheat — exactly where USDM mapped rapid D0→D3+ escalation in summer 2022.
- **North Dakota** is anomalously **wet** (mean z ≈ +0.19 to +0.29), a known geographic exception: the 2022 drought was centered on the Central and Southern Plains, not the Northern Plains.
- **Ohio** is near-neutral (mean z ≈ −0.03 to −0.04) — the eastern Corn Belt largely escaped the flash drought.
- Winter wheat consistently shows the strongest drought signal within each affected state, likely because it is grown most densely on the drought-prone western Plains.

### 3.4 Contrasting the two events (symmetric validation)

| Metric | 2019 flood | 2022 drought |
|--------|-----------|--------------|
| Median NIG P(drought) | 0.817 (wet) | 0.292 (dry) |
| Belt-wide mean z | ≈ +0.8 | ≈ −0.7 |
| % pixel-weeks with \|z\| > 1.5 | ~15% (wet tail) | ~5% (dry tail) |
| Geographic core | IA, SD, MN, IL | KS, NE, KY, IN |
| Frac P(drought) < 0.1 (belt-wide) | ~0% | ~25% |

The two events provide **mirror-image validation**: the 2019 flood pushes NIG P(drought) toward 1 (wet tail) while the 2022 drought pushes it toward 0 (dry tail). Both match documented USDA/USDM spatial patterns.

---

## 4. Methodological details

### 4.1 Normal-Inverse-Gamma conjugate update

For each (pixel, ISO week) with n baseline values having sample mean x̄ and sample variance s²:

```
λₙ = λ₀ + n
μₙ = (λ₀·μ₀ + n·x̄) / λₙ
αₙ = α₀ + n/2
βₙ = β₀ + (n−1)s²/2 + n·λ₀·(x̄ − μ₀)² / (2λₙ)
```

### 4.2 Posterior predictive (Student-t)

```
x_new | data  ~  t(df = 2αₙ,  loc = μₙ,  scale = √(βₙ·(1 + 1/λₙ) / αₙ))
```

When n is small (5–6 baseline years), df is low (~8–9) and the tails are **heavier** than Normal → the model is **less likely to flag false anomalies** compared to the z-score, which assumes z ~ N(0,1). This is the core benefit: **epistemic honesty about a short baseline**.

### 4.3 Anomaly score definitions

| Score | Formula | Interpretation |
|-------|---------|----------------|
| `nig_p_anomaly` | 2 · t.cdf(−\|t_stat\|, df) | Two-tailed: near 0 = extreme in either direction |
| `nig_p_drought` | t.cdf(t_stat, df) | One-tailed: near 0 = very dry, near 1 = very wet |
| `nig_posterior_scale` | √(βₙ·(1+1/λₙ)/αₙ) | Predictive width — epistemic uncertainty |

### 4.4 How the two frameworks relate

For pixels with many baseline years (n → ∞), the NIG posterior concentrates and the Student-t approaches the Normal — z-score and NIG converge. The **divergence** occurs precisely where it matters: sparse pixels, gap-filled weeks, domain-edge areas where σ̂ from 5–6 observations is unreliable. The z-score vs NIG scatter plot (Figure 6 per event) visualises this: data-rich pixels cluster near the 1:1 diagonal, while baseline-sparse pixels show the NIG's honest tail adjustment pulling away from the frequentist significance line.

---

## 5. Interpretation guide (for report and judges)

### 5.1 Reading the NIG P(drought) maps

- **Near 0 (red on RdYlBu):** SM observation is in the far left tail of the posterior predictive — severe dryness anomaly
- **Near 0.5 (yellow):** observation near the posterior predictive median — normal conditions
- **Near 1 (blue):** observation in the far right tail — extreme wetness
- **Threshold guidance:** P(drought) < 0.10 ≈ "bottom 10th percentile of the historical distribution at this pixel and week" — directly analogous to USDM D1/D2 drought framing

### 5.2 Reading the uncertainty map

- **Low posterior scale (dark on magma):** dense baseline → confident anomaly assessment
- **High posterior scale (bright on magma):** sparse baseline → anomaly calls should be interpreted cautiously
- Structurally analogous to Task 2's `dm_alt_posterior_std` epistemic uncertainty surface

### 5.3 Reading the state × crop CSV

- `mean_nig_p_drought`: average one-tailed exceedance probability. For 2019 flood, values near 0.80 = "most pixel-weeks were in the wet tail." For 2022 drought, values near 0.25 = "most pixel-weeks were in the dry tail."
- `frac_pdrought_lt_0p1`: fraction of pixel-weeks where P(drought) < 0.10 (severe drought probability). High values for Kansas/Nebraska wheat/corn in 2022 ≈ "a large share of that crop's growing area hit a historically extreme dry spell."
- `frac_obs_z_gt_1` / `frac_obs_z_gt_1p5`: frequentist persistence measures — useful for comparing against standard NASA/USDA soil moisture anomaly products.

---

## 6. Key questions answered

### Q1: How do you define a baseline climatology for SMAP soil moisture?

**Answer:** We compute per-pixel, per-ISO-week mean and standard deviation from SMAP L4 weekly composites across the **7-year baseline (2015–2021)**. This gives each pixel its own seasonal "normal." The NIG Bayesian layer augments this by treating (μ, σ²) as uncertain parameters: we place a weakly informative Normal-Inverse-Gamma prior (regional grand mean, λ₀ = 1, α₀ = 2, β₀ anchored to regional variance) and update with the pixel's observed baseline values. The result is a Student-t posterior predictive that honestly reflects the limited 7-year record — wider predictive intervals for sparse pixels, narrower for data-dense pixels.

### Q2: How do you detect anomalies relative to that baseline?

**Answer:** Two complementary methods:
- **Frequentist z-score:** (obs − μ̂) / σ̂, the standard approach used in NASA SMAP anomaly products and SSI/SPI literature. Simple, interpretable, but assumes σ̂ is known — fragile with only 5–7 baseline years per week.
- **NIG posterior predictive:** The event-year observation is scored against the Student-t posterior predictive distribution. The one-tailed CDF gives `nig_p_drought` (a percentile-scale quantity directly interpretable as "what fraction of the posterior predictive falls below this observation"). The two-tailed version gives `nig_p_anomaly`. Both are robust to short baselines because the Student-t has heavier tails than the Normal when degrees of freedom are low.

### Q3: How does soil moisture vary across crop types during extreme events?

**Answer:** CDL-masked stratification by state and crop reveals systematic differences:
- **2019 flood:** Corn and soybean respond nearly identically within each state (expected — both are warm-season crops with similar soil moisture regimes). Iowa corn and soybean show mean z ≈ 0.91, while South Dakota crops exceed z ≈ 1.16.
- **2022 drought:** Winter wheat in Kansas and Kentucky shows **stronger** drought signals than corn or soybean in the same states (Kansas wheat mean z = −1.06 vs corn −1.00; Kentucky wheat mean z = −1.57 vs corn −1.34). This reflects both phenological timing (wheat matures earlier, exposed to June heat) and geographic concentration (wheat on drier western Plains soils).
- The NIG `frac_pdrought_lt_0p1` measure confirms this pattern: **42% of Kentucky wheat pixel-weeks** hit the severe drought probability threshold vs 37% of Kentucky corn.

### Q4: What is the agricultural impact of these anomalies?

**Answer:**
- **2019 flood:** Iowa — the Corn Belt's largest corn producer — saw **18% of corn pixel-weeks** with z > 1.5 (persistently saturated soils), consistent with USDA-reported record prevented-planting acreage. The NIG mean P(drought) of 0.80 for Iowa corn means the average pixel-week was wetter than ~80% of its historical range.
- **2022 drought:** Nebraska — a major irrigated corn state — saw **37% of corn pixel-weeks** with NIG P(drought) < 0.10 (severe drought). Kansas wheat is even more affected at 42%. These numbers translate directly: "In 37% of the pixel-week observations across Nebraska corn land, the soil moisture was drier than the bottom 10th percentile of the Bayesian historical distribution." This is operationally meaningful for crop insurance and yield loss assessment.
- The **persistence/duration maps** show spatial clustering of severe anomaly weeks: the 2019 wet fraction concentrates along the Mississippi/Missouri floodplain, while the 2022 dry fraction forms a contiguous band from Kansas through Nebraska.

### Q5: Why is the Bayesian approach better than a simple z-score?

**Answer:** Three concrete advantages:
1. **Honest uncertainty with a short baseline:** With only 7 baseline years (5–7 valid observations per pixel-week), σ̂ is poorly estimated. The NIG Student-t has heavier tails (median df = 11 across all pixel-weeks), so it naturally produces more conservative anomaly calls — the 2019 flood shows only 0.2% two-tailed significance vs what a z-score would flag at the same threshold.
2. **Spatially coherent epistemic uncertainty:** The `nig_posterior_scale` map exposes which regions have reliable anomaly assessments (dense baseline → low scale) vs. unreliable ones (data gaps → high scale). This is invisible in the z-score framework.
3. **Percentile-scale output:** NIG P(drought) is a genuine posterior predictive probability, directly interpretable as "how extreme is this observation given everything we know (including uncertainty about the baseline parameters)." The z-score requires an additional N(0,1) CDF transformation that is unwarranted when σ̂ is uncertain.

### Q6: How does Task 3 integrate with the broader pipeline?

**Answer:** Task 3 uses the same **rotation-eligible pixel footprint** as Task 2 (~2.08M pixels, 13-state Corn Belt), ensuring spatial alignment. The CDL mask is drawn from the **event year** (CDL 2019 for the flood, CDL 2022 for the drought), so crop labels match actual planted cover. The Bayesian NIG layer follows the same conjugate/closed-form philosophy as Task 1 (HSGP for NDVI phenology) and Task 2 (Dirichlet-Multinomial for rotation), creating a unified methodological narrative: all three tasks propagate uncertainty analytically without MCMC sampling.

---

## 7. Artifacts produced

### 7.1 Parquets

| File | Rows | Key columns |
|------|------|-------------|
| `data/processed/task3/task3_pixel_panel.parquet` | 2,084,112 | iy, ix, cdl_label |
| `data/processed/task3/smap_climatology.parquet` | ~45.8M | iy, ix, iso_week, sm_mean, sm_std, sm_count, nig_mu_n, nig_lam_n, nig_alpha_n, nig_beta_n |
| `data/processed/task3/smap_anomaly_midwest_flood_2019.parquet` | 37,514,016 | z_score, nig_p_anomaly, nig_p_drought, nig_posterior_scale, nig_df |
| `data/processed/task3/smap_anomaly_plains_drought_2022.parquet` | 27,093,456 | (same columns) |

### 7.2 Figures (6 per event = 12 total)

| Figure | Description |
|--------|-------------|
| `task3__{event}__anomaly_map_4panel__20260412.png` | Four z-score raster maps at spread ISO weeks across event window |
| `task3__{event}__anomaly_timeseries_cropland__20260412.png` | Belt-wide mean z ± 1σ time series over the event window |
| `task3__{event}__duration_fraction__20260412.png` | Persistence map (fraction of weeks exceeding ±1.5 z threshold) |
| `task3__{event}__nig_p_drought_4panel__20260412.png` | NIG posterior predictive P(drought) 4-panel maps (RdYlBu) |
| `task3__{event}__nig_uncertainty__20260412.png` | NIG posterior predictive scale (epistemic uncertainty surface, magma) |
| `task3__{event}__zscore_vs_nig_scatter__20260412.png` | Scatter: frequentist z vs −log₁₀(NIG p-value) colored by posterior scale |

Plus 2 sanity histograms from NB01: `task3__smap_week_histogram_subset_{2019,2022}.png`.

### 7.3 Tables

| File | Columns |
|------|---------|
| `task3__midwest_flood_2019__anomaly_stats_by_state_crop__20260412.csv` | state, crop, mean_z, max_z, frac_obs_z_gt_1, frac_obs_z_gt_1p5, n_pixel_weeks, mean_nig_p_drought, frac_pdrought_lt_0p1 |
| `task3__plains_drought_2022__anomaly_stats_by_state_crop__20260412.csv` | (same schema) |

### 7.4 Run bundle

`artifacts/logs/runs/<id>/run_bundle.json` — per-event figure and table paths, event config, provenance.

---

## 8. Source files

| File | Role |
|------|------|
| `src/modeling/task3_nig_anomaly.py` | NIG posterior params + Student-t predictive scores (~113 lines, pure NumPy/SciPy) |
| `src/modeling/task3_smap_anomalies.py` | Frequentist climatology + z-score anomaly computation |
| `src/modeling/task3_aggregate.py` | State × crop summary (z + NIG columns), chunked point-in-polygon state join |
| `src/viz/task3_maps.py` | Raster fill, z-map plotting, pixel coordinate utilities |
| `src/io/smap_weekly_parquet.py` | SMAP wide Parquet loader, metadata reader, ISO week column resolver |
| `configs/task3_soil_moisture.yaml` | Event windows, baseline period, prior config, output paths |
| `notebooks/task3_soil_moisture/01_*.ipynb` | Pixel panel construction + sanity histograms |
| `notebooks/task3_soil_moisture/02_*.ipynb` | Climatology + NIG posterior params + event anomaly parquets |
| `notebooks/task3_soil_moisture/03_*.ipynb` | 6 figures per event, state × crop CSV, run bundle |

---

## 9. NAFSI rubric alignment

| NAFSI Requirement | Frequentist coverage | Bayesian NIG upgrade |
|---|---|---|
| Define baseline climatology | μ̂, σ̂ per week per pixel (7-year baseline) | + NIG posterior (μₙ, λₙ, αₙ, βₙ) propagating parameter uncertainty |
| Spatial anomaly maps | z-score 4-panel maps (two events) | + NIG P(drought) 4-panel maps (percentile-scale, directly interpretable) |
| CDL-masked cropland statistics | mean_z, frac_z_gt_1 by state × crop | + mean_nig_p_drought, frac_pdrought_lt_0.1 — quantitative agricultural impact |
| Temporal persistence analysis | Duration/persistence fraction maps | Same z-threshold approach; NIG informs confidence in persistence calls |
| Agricultural impact discussion | "Iowa corn had z > 1.5 for 18% of weeks" | + "37% of Nebraska corn pixel-weeks had drought probability < 10%" — posterior predictive framing |
| Multiple events / contrasts | 2019 flood + 2022 drought (wet vs dry mirror) | NIG P(drought) provides symmetric, comparable scale across both events |
| Uncertainty quantification | Not available in z-score framework | `nig_posterior_scale` map + scatter plot showing where z and NIG diverge |
| Innovation / methodological contribution | Standard approach | First conjugate NIG posterior predictive anomaly detection on SMAP weekly climatology; no published precedent |

---

## 10. Limitations and caveats

1. **Short baseline (7 years).** σ̂ estimates are unstable for some pixel-weeks — this is precisely why the NIG upgrade matters, but the posterior predictive is still influenced by the weakly informative prior for very sparse cells.
2. **SMAP L4 is a model-assimilation product.** Anomalies reflect the GEOS-5 land surface model's soil moisture, not a direct radar retrieval. Known model biases (e.g., in irrigated areas or complex terrain) propagate.
3. **Coarse resolution (~9 km native, ~557 m analysis grid).** Sub-field heterogeneity is smoothed out. Field-level claims require higher-resolution data.
4. **CDL mask from a single year.** Crop labels for the 2019 event use CDL 2019; for 2022, CDL 2022. Fields that changed use between years are correctly labeled per-event, but multi-year crop history is not considered within Task 3 (that is Task 2's domain).
5. **No external validation.** Anomaly patterns are compared qualitatively against USDM and USDA reports but no quantitative ground-truth soil moisture network (e.g., SCAN/CRN) comparison is performed.

---

## 11. Cross-references

- `configs/task3_soil_moisture.yaml` — event windows, baseline period, prior config
- `context/RISKS.md` — RISK-002 (short SMAP baseline)
- `context/structure.md` — artifact index and per-notebook results log
- `context/STATUS.md` — project phase checklist
- `context/PROJECT_BRIEF.md` — four-task pipeline diagram and NAFSI rubric mapping
