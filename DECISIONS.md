# DECISIONS.md

Records every meaningful design or methodological choice made in this project.
Format: decision → alternatives considered → rationale → consequences → date.

If this file conflicts with `development_rules.md`, `development_rules.md` wins.

---

## Template

### DEC-000 — Title
- **Decision:**
- **Alternatives considered:**
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**
- **Run ID (if applicable):**

---

## Decisions

### DEC-001 — Spatial alignment strategy for CDL → NDVI (Task 1)
- **Decision:**
- **Alternatives considered:**
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-002 — NDVI smoothing method choice (Task 1)
- **Decision:**
- **Alternatives considered:** Savitzky–Golay, TIMESAT double-logistic, Whittaker, harmonic regression
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-003 — Rotation regularity criterion definition (Task 2)
- **Decision:**
- **Alternatives considered:** Edit-distance (RECRUIT-style), transition frequency, run-length penalty, entropy
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-004 — SMAP anomaly baseline method (Task 3)
- **Decision:**
- **Alternatives considered:** DOY climatology (z-score), week-of-year percentile rank
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-005 — Crop-type prediction model family (Task 4)
- **Decision:**
- **Alternatives considered:** Markov baseline, Random Forest, LightGBM/XGBoost, deep SITS (CNN/RNN/Transformer)
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**

### DEC-006 — Validation strategy for Task 4
- **Decision:**
- **Alternatives considered:** Random CV, temporal holdout, spatial block CV
- **Rationale:**
- **Consequences / follow-ups:**
- **Date:**
