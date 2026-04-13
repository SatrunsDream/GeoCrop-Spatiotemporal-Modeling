# Task 3 — Results and interpretation (SMAP soil moisture anomaly detection)

**Last updated:** 2026-04-12  
**Submission context:** NAFSI Track 1 deadline **2026-04-13 4:00 PM CT** — frequentist z-score baseline plus **Normal-Inverse-Gamma (NIG) Bayesian** posterior predictive anomaly layer.  
**Baseline period:** SMAP L4 weekly composites **2015–2021** (7 years).  
**Events analysed:** `midwest_flood_2019` (Apr–Jul 2019, 18 weeks), `plains_drought_2022` (Jun–Aug 2022, 13 weeks).  
**Pipeline:** Notebooks **01→03** in `notebooks/task3_soil_moisture/`. Run NB01 (pixel panel), NB02 (climatology + NIG + anomaly), NB03 (figures + tables + run bundle).

---

## 0. Executive summary

1. **Spatial footprint.** Same **~2.08M rotation-eligible pixels** (13-state Corn Belt) as Task 2, joined from `rotation_metrics.parquet`.

2. **Frequentist baseline.** Z-score = (obs − μ̂) / σ̂ per (pixel, ISO week) from 7 baseline years. Provides the operational-standard anomaly frame (comparable to NASA SMAP drought products and SSI/SSMI literature).

3. **Bayesian NIG upgrade.** Conjugate Normal-Inverse-Gamma prior on (μ, σ²) per pixel per week → Student-t posterior predictive with exact closed-form update. Three new quantities:
   - `nig_p_anomaly` — two-tailed posterior predictive p-value (near 0 = extreme anomaly)
   - `nig_p_drought` — one-tailed exceedance probability (near 0 = very dry; near 1 = very wet)
   - `nig_posterior_scale` — predictive uncertainty width (wide for sparse baseline pixels)

4. **Why NIG is novel.** No published application of conjugate NIG posterior predictive anomaly detection on SMAP week-of-year climatology. The combination of weakly informative regional priors + Student-t heavy tails + honest uncertainty propagation for a 7-year baseline is the methodological contribution.

5. **Unified Bayesian narrative.** Task 1 = HSGP Gaussian Process (NDVI phenology), Task 2 = Dirichlet-Multinomial (crop rotation), Task 3 = Normal-Inverse-Gamma (soil moisture). All conjugate/approximate Bayesian, no MCMC, pure NumPy/SciPy.

---

## 1. What we measured

| Column | Type | Meaning |
|--------|------|---------|
| `z_score` | float32 | Frequentist z-score: (obs − μ̂) / σ̂ |
| `nig_p_anomaly` | float32 | Two-tailed NIG posterior predictive p-value (near 0 = extreme) |
| `nig_p_drought` | float32 | One-tailed CDF: P(SM ≤ observed \| data). Near 0 = extremely dry, near 1 = extremely wet |
| `nig_posterior_scale` | float32 | Student-t predictive std — wider for sparse pixels |
| `nig_df` | float32 | Degrees of freedom = 2αₙ (lower = less baseline data = heavier tails) |

**Climatology columns (in `smap_climatology.parquet`):**

| Column | Meaning |
|--------|---------|
| `sm_mean`, `sm_std`, `sm_count` | Frequentist baseline stats (μ̂, σ̂, n) |
| `nig_mu_n` | NIG posterior mean |
| `nig_lam_n` | NIG posterior precision count (λ₀ + n) |
| `nig_alpha_n` | NIG posterior shape (α₀ + n/2) |
| `nig_beta_n` | NIG posterior rate |

**Prior specification:**
- μ₀ = regional grand mean for each ISO week (13-state average)
- λ₀ = 1 (one pseudo-observation pulling toward regional mean)
- α₀ = 2
- β₀ = regional_var(week) × (α₀ − 0.5) — anchored to the cross-pixel variance for that week

This is a **weakly informative** prior (Gelman et al. 2008): strong enough to regularise pixels with only 5 usable baseline years, weak enough to let data-rich pixels dominate their own posterior.

---

## 2. Events analysed

### 2.1 Midwest flood 2019 (`midwest_flood_2019`)

- **Window:** 2019-04-01 to 2019-07-31 (18 ISO weeks, ~14–31)
- **Duration mode:** `wet_above` — duration map shows fraction of weeks with z > 1.5
- **Context:** Record spring rainfall across Iowa, Illinois, Missouri, and the Mississippi/Missouri River basins. Delayed planting, prevented-planting acres near USDA records. SMAP L4 surface SM persistently above climatological mean through the growing season.

### 2.2 Great Plains flash drought 2022 (`plains_drought_2022`)

- **Window:** 2022-06-01 to 2022-08-31 (13 ISO weeks, ~22–35)
- **Duration mode:** `dry_below` — duration map shows fraction of weeks with z < −1.5
- **Context:** Rapid-onset flash drought across Kansas, Nebraska, and surrounding states. Drought Monitor escalated large areas from D0 to D3+ within weeks. June–August heat + low precipitation drove rapid soil moisture depletion.

---

## 3. Artifacts produced

### 3.1 Parquets

| File | Rows (approx) | Key columns |
|------|--------------|-------------|
| `data/processed/task3/smap_climatology.parquet` | ~45.8M | iy, ix, iso_week, sm_mean, sm_std, sm_count, nig_mu_n, nig_lam_n, nig_alpha_n, nig_beta_n |
| `data/processed/task3/smap_anomaly_midwest_flood_2019.parquet` | ~37.5M | z_score, nig_p_anomaly, nig_p_drought, nig_posterior_scale, nig_df |
| `data/processed/task3/smap_anomaly_plains_drought_2022.parquet` | ~27.1M | (same columns) |

### 3.2 Figures (per event, 6 per event = 12 total)

| Figure | Description |
|--------|-------------|
| `task3__{event}__anomaly_map_4panel__YYYYMMDD.png` | Four z-score maps at spread ISO weeks |
| `task3__{event}__anomaly_timeseries_cropland__YYYYMMDD.png` | Mean z ± 1σ over the event window |
| `task3__{event}__duration_fraction__YYYYMMDD.png` | Persistence map (wet/dry fraction) |
| `task3__{event}__nig_p_drought_4panel__YYYYMMDD.png` | **NIG** posterior predictive P(drought) — 4-panel, RdYlBu colormap |
| `task3__{event}__nig_uncertainty__YYYYMMDD.png` | **NIG** posterior predictive scale (epistemic uncertainty surface) |
| `task3__{event}__zscore_vs_nig_scatter__YYYYMMDD.png` | **Scatter**: frequentist z vs −log₁₀(NIG p-value) colored by posterior scale |

### 3.3 Tables

| File | Columns |
|------|---------|
| `task3__{event}__anomaly_stats_by_state_crop__YYYYMMDD.csv` | state, crop, mean_z, max_z, frac_obs_z_gt_1, frac_obs_z_gt_1p5, n_pixel_weeks, **mean_nig_p_drought**, **frac_pdrought_lt_0p1** |

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
x_new | data  ~  t(df=2αₙ, loc=μₙ, scale=√(βₙ·(1+1/λₙ)/αₙ))
```

Key property: when n is small (5–6 baseline years), df is low (~8–9) and the tails are **heavier** than Normal → the model is **less likely to flag false anomalies** compared to the z-score approach, which assumes z ~ N(0,1).

### 4.3 Anomaly scores

- **nig_p_anomaly** = 2 · t.cdf(−|t_stat|, df) — two-tailed
- **nig_p_drought** = t.cdf(t_stat, df) — one-tailed (low = dry, high = wet)
- **nig_posterior_scale** = √(βₙ·(1+1/λₙ)/αₙ) — interpretable as "how wide is the posterior predictive"

### 4.4 Relationship to frequentist z-score

For pixels with many baseline years (n → ∞), the NIG posterior concentrates and the Student-t approaches Normal — the two methods converge. The **divergence** occurs precisely where it matters: sparse pixels, gap-filled weeks, edge-of-domain areas where σ̂ from 5–6 observations is unreliable.

The scatter plot (Figure 6) visualises this: points near the 1:1 diagonal represent data-rich pixels where both methods agree. Points above/below the diagonal are sparse pixels where the NIG's heavier tails correctly adjust the anomaly significance.

---

## 5. Interpretation guide

### 5.1 Reading the NIG P(drought) maps

- **Near 0** (red on RdYlBu): SM observation is in the far left tail of the posterior predictive — severe dryness anomaly
- **Near 0.5** (yellow): observation is near the posterior predictive median — normal conditions
- **Near 1** (blue): observation is in the far right tail — extreme wetness
- **Threshold guidance:** P(drought) < 0.10 corresponds roughly to "bottom 10th percentile of the historical distribution at this pixel and week" — directly analogous to USDM D1/D2 framing

### 5.2 Reading the uncertainty map

- **Low posterior scale** (dark on magma): pixel has dense baseline → confident anomaly assessment
- **High posterior scale** (bright on magma): sparse baseline → anomaly calls should be interpreted cautiously
- Structurally analogous to Task 2's `dm_alt_posterior_std` surface

### 5.3 CSV table: new columns

- `mean_nig_p_drought`: state × crop average of the one-tailed exceedance. For the 2019 flood event, values near 0.8–0.9 for Iowa corn = "most pixels were in the wet tail"
- `frac_pdrought_lt_0p1`: fraction of pixel-weeks where P(drought) < 0.10. For the 2022 drought, high values for Kansas wheat = "many pixels hit severe drought probability"

---

## 6. NAFSI bullet coverage

| NAFSI Requirement | Frequentist (z-score) | Bayesian NIG upgrade |
|---|---|---|
| Define baseline climatology | μ̂, σ̂ per week per pixel | + NIG posterior (μₙ, λₙ, αₙ, βₙ) propagating uncertainty |
| Spatial anomaly maps | z-score 4-panel maps | + `nig_p_drought` maps (percentile-scale, directly interpretable) |
| CDL-masked cropland stats | mean_z, frac_z_gt_1 | + mean_nig_p_drought, frac_pdrought_lt_0.1 |
| Agricultural impact discussion | qualitative stages | + "X% of Iowa corn pixels had drought probability <10%" — quantitative |

---

## 7. Source files

| File | Role |
|------|------|
| `src/modeling/task3_nig_anomaly.py` | NIG posterior params + predictive scores (~100 lines) |
| `src/modeling/task3_smap_anomalies.py` | Frequentist climatology + z-score anomaly |
| `src/modeling/task3_aggregate.py` | State × crop summary (z + NIG columns) |
| `src/viz/task3_maps.py` | Raster fill + z-map plotting |
| `configs/task3_soil_moisture.yaml` | Event windows, baseline period, prior config |
| `notebooks/task3_soil_moisture/01_*.ipynb` | Pixel panel construction |
| `notebooks/task3_soil_moisture/02_*.ipynb` | Climatology + NIG params + anomaly parquets |
| `notebooks/task3_soil_moisture/03_*.ipynb` | Figures (6 per event), tables, run bundle |
