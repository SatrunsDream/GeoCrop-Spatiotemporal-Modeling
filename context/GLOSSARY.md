# GLOSSARY.md

Domain terms, acronyms, and CDL class codes used throughout this project.

---

## Acronyms

| Term | Meaning |
|------|---------|
| CDL | Cropland Data Layer — annual 30 m USDA NASS raster crop classification |
| CONUS | Contiguous United States (lower 48 states) |
| DOY | Day of Year (1–365/366) |
| EOS | End of Season — phenological metric |
| IQR | Interquartile Range |
| MODIS | Moderate Resolution Imaging Spectroradiometer (NASA Terra/Aqua) |
| NAFSI | National Agricultural Food Security Initiative (challenge organizer) |
| NASS | National Agricultural Statistics Service (USDA) |
| NDP | National Data Platform |
| NDVI | Normalized Difference Vegetation Index |
| OA | Overall Accuracy |
| RECRUIT | Representative Crop Rotations Using Edit Distance (algorithm) |
| SMAP | Soil Moisture Active Passive (NASA satellite mission) |
| SG | Savitzky–Golay smoothing |
| SITS | Satellite Image Time Series |
| SOS | Start of Season — phenological metric |
| TIMESAT | Software for time-series phenology extraction from satellite data |
| VI | Vegetation Index |

---

## CDL Class Codes (selected)

| Code | Crop / Land Cover |
|------|------------------|
| 1 | Corn |
| 5 | Soybeans |
| 21 | Barley |
| 22 | Durum Wheat |
| 23 | Spring Wheat |
| 24 | Winter Wheat |
| 26 | Winter Wheat (also 24 in some years; check year-specific legend) |
| 28 | Oats |
| 36 | Alfalfa |
| 61 | Fallow / Idle Cropland |
| 111 | Open Water |
| 121 | Developed / Open Space |
| 131 | Barren |
| 141 | Deciduous Forest |
| 176 | Grassland / Pasture |

*Always verify codes against the CDL legend for the specific year.*

---

## Phenological Terms

| Term | Definition |
|------|-----------|
| Greenup DOY | Day of Year when NDVI first rises steeply (start of growing season) |
| Peak DOY | Day of Year of maximum NDVI |
| Senescence DOY | Day of Year when NDVI begins rapid decline |
| Amplitude | Peak NDVI minus base NDVI |
| Integral | Area under the NDVI curve over the growing season (proxy for cumulative greenness) |
| Phenometrics | Set of quantitative phenological timing and magnitude features |
| Trusted pixel | NDVI pixel with high crop purity fraction (≥ 0.80) in corresponding 250 m CDL cell |

---

## Rotation Terms

| Term | Definition |
|------|-----------|
| Regular rotation | Field exhibiting consistent annual alternation (e.g., corn–soy–corn–soy) |
| Monoculture | Consecutive years of the same crop (run length ≥ threshold) |
| Irregular cropping | All other patterns; high sequence entropy |
| Alternation score | Fraction of adjacent-year transitions that are corn↔soy |
| Edit distance | Minimum edits to convert observed sequence to canonical rotation pattern |
| Run length | Number of consecutive years with the same crop |
