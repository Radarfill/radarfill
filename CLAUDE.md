# RadarFill — Final Year Research Project (UoM FIT, BSc (Hons) IT)

## What this project is
Early-season crop recognition from satellite time series under cloud cover.
Radar (Sentinel-1) fills cloud gaps in each field's optical (Sentinel-2) greenness curve using
**past data only**, crops are named weeks earlier, and confidence is checked to be honest.

Team: 3 members, 8 months (Nov 2026 – Jun 2027).
- Layer 0 (Nov, all): shared Data Kit — field curves, folds, cut-off function, leak test.
- Layer 1 (Dec – mid-Apr): three independent research tracks, one paper each
  - Track A: past-only radar-guided gap filling with calibrated uncertainty (± bands)
  - Track B: early crop recognition — fill vs fuse, observation-aware classifier, earliest reliable date
  - Track C: gap-aware trust — gap-conditional calibration + gap-stratified (Mondrian) conformal sets
- Layer 2 (mid-Apr – May, all): RadarFill app (FastAPI + React/MapLibre), each member builds own module.

## Folder layout (keep it like this)
```
FYP/
  dataset/PASTIS-R/        # RAW DATA — READ ONLY, never modify, move or delete
  dataset/BreizhCrops/     # second dataset (added later)
  code/data_kit/           # shared Layer-0 code
  code/member_a/  code/member_b/  code/member_c/
  code/app/                # Layer 2
  outputs/                 # generated tables (curves.parquet, folds, figures)
  notebooks/
  docs/                    # data card, decisions log, papers
```

## PASTIS-R facts (from official docs)
- 2,433 patches, 128x128 px at 10 m, France, Sept 2018 – Nov 2019; 124,422 fields, 18 crop classes
- metadata.geojson: ID_PATCH, Fold (1–5), TILE, dates-S2 / dates-S1A / dates-S1D (JSON dict of YYYYMMDD)
- DATA_S2/S2_<id>.npy (T,10,128,128); DATA_S1A, DATA_S1D (T,3,128,128) channels VV, VH, VV/VH
- ANNOTATIONS/TARGET_<id>.npy (3,128,128), layer 0 = class (0 background, 1–18 crops, 19 void)
- INSTANCE_ANNOTATIONS/INSTANCES_<id>.npy (128,128) = field ID per pixel
- NORM_*_patch.json = band mean/std per fold
- S2 band order assumed B2,B3,B4,B5,B6,B7,B8,B8A,B11,B12 — VERIFY (RGB = channels 2,1,0; NDVI = (ch6-ch2)/(ch6+ch2))
- Reference date used by official loader: 2018-09-01

## Rules (important)
1. Never write inside dataset/. All outputs go to outputs/ or code/.
2. No peeking at the future: at cut-off date t use only observations dated <= t (filling, scaling, features).
   Radar paired with an optical date must be on or before that date.
3. Folds: train 1–3, validate 4, test 5 (rotate x5). Scaling stats from training folds only.
   Tune / calibrate on validation only. Test fold is touched once.
4. Skip classes 0 (background) and 19 (void). Report macro-F1 and per-class results (imbalance ~57:1).
5. Leak test must pass: scrambling data after t must not change any output at t.
6. Log every data decision (thresholds, min field size, class mapping) in docs/data_decisions.md.

## Agreed file formats
- outputs/curves.parquet: patch, field, crop, fold, sensor (S2/S1A/S1D), date, n_pix, cloud_frac, ndvi, B2..B12 | VV, VH, ratio
- fills.parquet (A): field, date, method, mean, spread
- preds.parquet (B): field, cutoff_date, model, p_crop1..p_crop18
- calibrated.parquet (C): field, cutoff_date, p_calibrated..., safe_set

## Current phase: Layer 0, Week 1
Verify dataset, run code/data_kit/pastis_starter.py on a few patches, confirm band order / NDVI / radar units,
write docs/data_card.md, check free disk space. Then cloud masks (OmniCloudMask), field curves, folds, cut-off, leak test.

## Environment
Python 3.10+, numpy, pandas, geopandas, matplotlib, pyarrow, omnicloudmask, lightgbm, torch, scikit-learn.
Prefer a virtual environment in FYP/.venv. Explain commands briefly before running long jobs.
