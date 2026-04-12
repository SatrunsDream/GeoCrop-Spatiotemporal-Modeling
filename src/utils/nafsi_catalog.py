"""
NAFSI Track 1 — CropSmart dataset catalog years.

Source: resources/CropSmart_NAFSI_Track1_Challenge_Brief.docx.pdf, Section 3
(Data Provided), Period column for each dataset.

These are the official inclusive calendar-year windows for CDL, NDVI, and SMAP
on CropSmart. Task-specific analysis windows (e.g. 10-year rotation, train
Task 2 rotation window 2015–2024; train/validate splits for other tasks) are configured separately in configs/.
"""

# Product availability (challenge brief §3 — inclusive calendar years).
CDL_YEAR_MIN, CDL_YEAR_MAX = 2008, 2025
NDVI_YEAR_MIN, NDVI_YEAR_MAX = 2000, 2026
SMAP_YEAR_MIN, SMAP_YEAR_MAX = 2015, 2025

CDL_YEARS = list(range(CDL_YEAR_MIN, CDL_YEAR_MAX + 1))
NDVI_YEARS = list(range(NDVI_YEAR_MIN, NDVI_YEAR_MAX + 1))
SMAP_YEARS = list(range(SMAP_YEAR_MIN, SMAP_YEAR_MAX + 1))
