# Data card — PASTIS-R (RadarFill, Layer 0)

_First version: 2026-10-20 (Week 1). Every number below was measured on our local copy unless marked **(docs)**, meaning it comes from the official documentation and has not been re-checked by us._

## 1. What it is
- Sentinel-2 optical time series plus Sentinel-1 radar time series (ascending and descending orbits) for 2,433 patches of 128×128 px at 10 m in France, with crop-type labels per pixel and per field.
- Agricultural season covered: autumn 2018 to autumn 2019.
- Licence and citation: **TODO**. Copy them exactly from the official PASTIS-R release page; don't write them from memory.

## 2. Local copy
| Item | Value |
|---|---|
| Path | `dataset/PASTIS-R/` (read-only, see rule 1) |
| Size | 69 GB (S2 36 GB, S1A 16 GB, S1D 16 GB, annotations 1.2 GB) |
| Source archive | `~/Downloads/PASTIS-R.zip`, 53.7 GB |
| Free disk on 2026-10-20 | 36 GB of 197 GB (81% used) |

Not a single damaged or zero-byte `.npy` was found. Inventory: `outputs/starter/inventory.json`.

## 3. Files
| Folder / file | Count | Content |
|---|---|---|
| `metadata.geojson` | 2,433 features | ID_PATCH, Fold, TILE, N_Parcel, Parcel_Cover, dates-S2/S1A/S1D, patch polygon (EPSG:2154) |
| `DATA_S2/S2_<id>.npy` | 2,468 | (T, 10, 128, 128) **int16** |
| `DATA_S1A/S1A_<id>.npy`, `DATA_S1D/...` | 2,468 each | (T, 3, 128, 128) **float16** |
| `ANNOTATIONS/TARGET_<id>.npy` | 2,433 | (3, 128, 128) uint8 |
| `ANNOTATIONS/ParcelIDs_<id>.npy` | 2,433 | (128,128) int32, original parcel IDs |
| `INSTANCE_ANNOTATIONS/INSTANCES_<id>.npy` | 2,433 | (128,128) int64, field ID per pixel (0 = no field) |
| `INSTANCE_ANNOTATIONS/ZONES_*`, `HEATMAP_*` | 2,433 each | aids for the panoptic (field-outline) task; **not used** |
| `NORM_S2/S1A/S1D_patch.json` | 3 | band mean/std for each fold (Fold_1 to Fold_5) |

**35 patches have imagery but no labels and no metadata entry.** We ignore them (D-02). Their IDs are listed in `inventory.json`.

## 4. Space and folds
- Four Sentinel-2 tiles. The first digit of a patch ID gives its tile: 1 = t30uxv (531 patches), 2 = t31tfj (623), 3 = t31tfm (723), 4 = t32ulu (556).
- Folds (from metadata): 1 = 487, 2 = 494, 3 = 474, 4 = 482, 5 = 496 patches. Folds are made at patch level, so a field never appears in two folds.
- Crop fields per fold are roughly equal, between 16,640 and 17,559.

## 5. Time
| Sensor | First date | Last date | Dates per patch (min / median / max) | Distinct dates |
|---|---|---|---|---|
| S2 | 2018-09-17 | 2019-10-27 | 38 / 46 / 61 | 159 |
| S1A (ascending) | 2018-10-01 | 2019-12-04 | 65 / 71 / 71 | 207 |
| S1D (descending) | 2018-10-02 | 2019-12-02 | 69 / 70 / 70 | 209 |

- Dates are stored as `{'0': YYYYMMDD, ...}` with keys in time order. Verified sorted in the 5 sample patches.
- S2 dates differ by tile because each tile is imaged on a different schedule. S1 revisits every 6 days per orbit.
- **Radar starts about two weeks after optical.** So the first 2–3 S2 dates in each patch have no radar on or before them.
- Radar continues for about 5 weeks after the last S2 date. That extra radar is not useful under the past-only rule unless the season window is extended.
- Time origin: the official loader counts days from 2018-09-01 (D-12).

## 6. Sentinel-2 (optical)
- **Units:** surface reflectance × 10,000, stored as int16. A typical green pixel has NIR ≈ 4,000.
- **Band order (verified):** B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12. In 5 of 5 patches, the top-10% NDVI pixels show:
  - a green bump (B3 higher than B2 and B4);
  - a red dip, then a rising red edge (B4 < B5 < B6 < B7);
  - a NIR plateau (B8 and B8A above 4×B4);
  - SWIR falling (B8A > B11 > B12).

  Example (patch 30286): 137, 407, 144, 814, 3127, 3956, 4085, 4316, 1699, 735. An RGB made from channels (2, 1, 0) looks natural. B8 and B8A can't be told apart by spectrum, so their order relies on the official docs.
- **NDVI** = (ch6 − ch2) / (ch6 + ch2). Results:
  - Green fields reach 0.85–0.95, and bare or harvested soil sits at 0.1–0.2.
  - Per-class phenology looks right: winter wheat peaks in April–May and drops after harvest in July. Corn stays bare (about 0.15) until June and peaks in August. Meadow stays high (about 0.8) all year. Rapeseed is green over winter and drops in July.
  - This also confirms that dates line up with the right image slices.
- **No cloud mask is provided.** Many dates are cloudy (on a cloudy date, NDVI over the whole patch drops to about 0). In the 5 sample patches, only 26 to 54 dates were clear by a rough brightness test. Proper cloud masks are the next task (OmniCloudMask).
- **Invalid values, dataset-wide** (`outputs/validity_scan.parquet`):
  - Overall, 2.6% of S2 pixels have a negative band or are all-zero.
  - 24,871 of 115,222 acquisitions (21.6%) contain at least one such pixel.
  - 1,925 acquisitions are more than half invalid, and 600 are completely invalid.
  - Share of acquisitions affected, by tile: t30uxv 47.5%, t32ulu 28.9%, t31tfj 18.8%, t31tfm 2.4%.
  - After dropping acquisitions more than half invalid, each patch still has 31–61 S2 dates (median 46).
- **NORM_S2 means** for Fold 1 are about 1,166 (B2) up to 3,319 (B8A), which fits ×10,000 reflectance. We will compute our own scaling from training folds only (rule 3).

## 7. Sentinel-1 (radar)
- **Channels:** VV, VH and a ratio, all **in dB**:
  - VV averages about −11 dB, and VH about −17 dB.
  - Fewer than 1.5% of VV pixels are above 0 dB; these are bright objects such as buildings.
  - The ratio channel equals VV − VH to within 0.03 dB (float16 precision), so it is a log ratio, not linear VV/VH.
  - To convert to linear power: σ = 10^(dB/10).
- Whether the values are σ⁰ or γ⁰, and which terrain correction was applied: **TODO**, check the PASTIS-R paper.
- **Missing radar is stored as exactly 0**, in VV, VH and ratio together. Dataset-wide:
  - S1A: 682 of 169,450 acquisitions have some zero pixels, none more than half missing.
  - S1D: 810 of 169,587 have some; 38 are more than half missing, almost all on **S1D 2019-01-04** (62 patches, about 54% missing on average).
  - Treated as no-data (D-06).
- **Signals look right per class.** Rapeseed VV and VH rise by about 5 dB in May–June, when it flowers and forms pods. Wheat VV dips during heading. Dense canopies raise VH. So radar does carry crop information through cloudy periods, which is what RadarFill relies on.
- **float16 precision** is about 0.01 dB near −10 dB. That's negligible next to speckle, but convert to float32 before doing any arithmetic.

## 8. Labels
- `TARGET[0]` is the crop class per pixel: 0 = background, 1–18 = crops, 19 = void (unknown or excluded). `TARGET[1]` and `[2]` are per-field attributes used by the panoptic task. They're constant within each field and **not used**.
- **Field ID = `INSTANCES`.** In the 4 patches checked, every field holds exactly one class and field 0 is always background. `ParcelIDs` has extra parcels, but they are all background (non-crop land).
- **Every one of the 121,868 fields across the dataset holds a single class.** None of them is labelled background.
- **The counts don't match the documentation.** CLAUDE.md says 124,422 fields (docs) and the metadata `N_Parcel` total is 152,397, while `INSTANCES` has 121,868. The likely cause is that N_Parcel also counts non-crop parcels. Documented, not resolved.
- **Void:** 35,917 fields (29%) are class 19 and are excluded. That leaves **85,951 usable crop fields**.

| # | Class | Fields | % fields | Pixels | Median field size (px) |
|---|---|---|---|---|---|
| 1 | Meadow | 31,292 | 36.41 | 7,289,116 | 136 |
| 2 | Soft winter wheat | 8,206 | 9.55 | 2,733,960 | 222 |
| 3 | Corn | 13,123 | 15.27 | 3,451,442 | 174 |
| 4 | Winter barley | 2,766 | 3.22 | 810,895 | 200 |
| 5 | Winter rapeseed | 1,769 | 2.06 | 705,329 | 290 |
| 6 | Spring barley | 908 | 1.06 | 254,693 | 167 |
| 7 | Sunflower | 1,355 | 1.58 | 395,551 | 177 |
| 8 | Grapevine | 10,640 | 12.38 | 1,108,797 | 65 |
| 9 | Beet | 871 | 1.01 | 324,825 | 283 |
| 10 | Winter triticale | 1,208 | 1.41 | 294,045 | 181 |
| 11 | Winter durum wheat | 1,704 | 1.98 | 419,760 | 155 |
| 12 | Fruits, vegetables, flowers | 2,619 | 3.05 | 373,283 | 90 |
| 13 | Potatoes | 551 | 0.64 | 111,600 | 124 |
| 14 | Leguminous fodder | 3,174 | 3.69 | 635,561 | 129 |
| 15 | Soybeans | 1,212 | 1.41 | 420,060 | 238 |
| 16 | Orchard | 2,998 | 3.49 | 412,080 | 83 |
| 17 | Mixed cereal | 848 | 0.99 | 207,035 | 190 |
| 18 | Sorghum | 707 | 0.82 | 166,966 | 151 |

- Class names follow the official PASTIS order **(docs)**. Check them against the release README.
- **Imbalance:** 56.8 : 1 by fields (Meadow vs Potatoes), 65 : 1 by pixels. Report macro-F1 and per-class results.
- **Smallest classes per fold:** Potatoes has 90–146 fields per fold and Sorghum 113–206. Per-class calibration on the validation fold (fold 4) will be noisy for those (relevant to Track C).
- **Field size:** median 139 px (1.4 ha). 5% are under 32 px, 1,603 fields are under 25 px, and 12,869 are under 50 px. Grapevine and orchard fields are small (median 65 and 83 px), so mixed edge pixels matter for them (see open questions).
- Counts per field: `outputs/starter/field_counts.csv`.

## 9. Known risks for RadarFill
1. **No cloud mask.** Optical gaps must be detected by us, and any mask errors feed straight into Tracks A–C.
2. **Invalid S2 pixels are concentrated in tile t30uxv.** The amount of missing data differs by tile, so Track C's stratification by gap length should also be checked by tile.
3. **Radar coverage starts on 2018-10-01.** The earliest optical dates can't be filled using only past radar.
4. **Label quality:** 29% of fields are void, and the labels come from farmers' declarations, so some noise is expected.
5. **Spatial dependence:** patches inside a tile are near each other. Folds are by patch, not by region, so the test scores may be optimistic.

## 10. Reproduce
```bash
.venv/bin/python code/data_kit/pastis_starter.py --n 5     # sample checks + figures (~10 s)
.venv/bin/python code/data_kit/scan_validity.py           # dataset-wide no-data scan (~2 min)
```
Outputs: `outputs/starter/{inventory.json,checks.csv,class_curves.csv,field_counts.csv}`, `outputs/validity_scan.parquet`, `outputs/figures/starter_*.png`.
`field_counts.csv` was made by a one-off script. It will be replaced by `curves.parquet`.
