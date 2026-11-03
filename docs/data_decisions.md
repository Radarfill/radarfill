# Data decisions log

This is rule 6 from CLAUDE.md: log every data decision here.

Each entry has a status:
- **agreed**: the team has accepted it.
- **provisional**: proposed with evidence, but the team still needs to sign off.
- **open**: not decided yet.

Never edit an old entry in place. Add a new entry that supersedes it.

| ID | Date | Decision | Evidence | Status |
|---|---|---|---|---|
| D-01 | 2026-10-20 | `dataset/` is read-only. All generated files go to `outputs/` or `code/`. Scripts refuse to write under `dataset/`. | CLAUDE.md rule 1 | agreed |
| D-02 | 2026-10-20 | Use only the 2,433 patches in `metadata.geojson`. Ignore the 35 patches that have imagery but no labels. | Inventory: 2,468 data files vs 2,433 labels and metadata entries; IDs in `outputs/starter/inventory.json` | provisional |
| D-03 | 2026-10-20 | S2 channel order is B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12. RGB = channels (2, 1, 0). | Vegetation spectrum shape correct in 5/5 patches; RGB looks natural; per-class phenology is plausible. B8 vs B8A relies on the docs. | agreed (verified) |
| D-04 | 2026-10-20 | NDVI = (ch6 − ch2) / (ch6 + ch2), computed in float32 on the stored ×10,000 values (the scale cancels). If the denominator is ≤ 0, NDVI = NaN. | Green fields 0.85–0.95, bare soil 0.1–0.2 | agreed |
| D-05 | 2026-10-20 | S1 channels are VV dB, VH dB, and VV − VH in dB. Convert to float32 before any arithmetic. Linear power = 10^(dB/10). | Means about −11 / −17 dB; ratio = VV − VH within 0.03 dB | agreed (verified) |
| D-06 | 2026-10-20 | An S1 pixel with VV == 0 or VH == 0 is missing data. Exclude it, never treat it as 0 dB. | S1D 2019-01-04 is about 54% zeros in 62 patches; elsewhere zeros are scattered | provisional |
| D-07 | 2026-10-20 | An S2 pixel is invalid if any band is < 0 or all bands are 0. An S2 acquisition that is more than 50% invalid in a patch is dropped for that patch. This is separate from, and comes before, cloud masking. | 2.6% of S2 pixels invalid; 1,925 acquisitions over 50% invalid; at least 31 dates per patch remain | provisional (see OQ-05) |
| D-08 | 2026-10-20 | Field ID = `INSTANCE_ANNOTATIONS/INSTANCES` (0 = no field). `ParcelIDs` is not used. | Every one of the 121,868 instances holds a single class; the extra parcel IDs are background only | provisional |
| D-09 | 2026-10-20 | A field's crop = `TARGET[0]` inside the field. Drop class 0 and void (19), leaving 85,951 fields. Report macro-F1 and per-class results. | 35,917 void fields (29%); imbalance 56.8 : 1 | agreed (rule 4) |
| D-10 | 2026-10-20 | `TARGET[1:3]`, `ZONES` and `HEATMAP` (panoptic-task aids) are not used. | Constant within each field; not crop classes | provisional |
| D-11 | 2026-10-20 | Radar paired with an optical date t = the latest valid S1 acquisition dated ≤ t. If none exists (S2 dates before 2018-10-01/02), the pair is missing, never filled from the future. | Rule 2; 2–3 S2 dates per patch come before the first S1 date | agreed (rule 2) |
| D-12 | 2026-10-20 | Time axis: day offset from 2018-09-01, the same as the official loader. | CLAUDE.md | agreed |
| D-13 | 2026-10-20 | Folds come from metadata `Fold`: train 1–3, validate 4, test 5, rotated ×5. Scaling statistics come from training folds only. The official NORM files are not used for scaling (they are per fold, not per training split). | Rule 3; crop fields per fold 16.6k–17.6k | agreed (rule 3) |
| D-14 | 2026-10-20 | The rough cloud flag in the starter script (B2 > 2000) is only for choosing a display date and drawing plots. It is never used in any data product. | It's a heuristic, not a mask | agreed |
| D-15 | 2026-10-20 | The differences between field counts (121,868 in INSTANCES vs 124,422 in the docs vs 152,397 N_Parcel) are noted but not acted on. We use INSTANCES. | `outputs/starter/field_counts.csv` | provisional |

## Open questions (decide before building `curves.parquet`)
| ID | Question | Notes / options |
|---|---|---|
| OQ-01 | Minimum field size | 5% of fields are under 32 px and 12,869 are under 50 px; grapevine and orchard fields are small. Options: 10 / 25 / 50 px after erosion. Check what each costs per class. |
| OQ-02 | Erode field edges by 1 px? | Reduces mixed pixels at edges, but very small fields would disappear. Interacts with OQ-01. |
| OQ-03 | Cloud mask method and the `cloud_frac` cut-off for a field-date to count as observed | OmniCloudMask is planned. Options for the cut-off: 0 / 0.1 / 0.3. Also decide how to handle cloud shadow. |
| OQ-04 | How to average radar over a field | Average in linear power then convert to dB (physically correct) vs average the dB values directly. Also: whether to apply a speckle filter. |
| OQ-05 | Negative S2 values | Is "invalid" too strict for slightly negative reflectance over water or shadow? Check where they occur spatially. |
| OQ-06 | S1A, S1D or both | The two orbits view at different angles, so don't mix them in one series without a reason. |
| OQ-07 | Season window and cut-off grid | S2 ends 2019-10-27 and S1 ends 2019-12-04. Pick the grid of cut-off dates t for early classification (e.g. monthly or every 10 days). |
| OQ-08 | Licence, citation, and σ⁰ vs γ⁰ | Fill in from the official release page and paper. |
| OQ-09 | Spatial leakage | Folds split by patch; patches in the same tile can be neighbours. Is extra test-by-tile reporting needed? |
