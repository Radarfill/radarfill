"""Dataset-wide no-data scan for PASTIS-R (Layer 0). Read-only on dataset/.

For every annotated patch, sensor and acquisition date, count pixels that carry no data:
  S2 : any band < 0, or all bands == 0
  S1 : VV == 0 or VH == 0 exactly (missing radar is stored as 0 dB), or non-finite

This is NOT a cloud mask; it only finds missing / corrupt values.

    .venv/bin/python code/data_kit/scan_validity.py            # all 2,433 patches
    .venv/bin/python code/data_kit/scan_validity.py --limit 50

Output: outputs/validity_scan.parquet
  patch, fold, sensor, date, n_invalid, frac_invalid (of 128*128 px), s2_neg_values
"""

import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pastis_starter import DATA, OUT, load_metadata, parse_dates  # noqa: E402

N_PX = 128 * 128


def scan_patch(args):
    pid, props = args
    rows = []
    s2 = np.load(DATA / "DATA_S2" / f"S2_{pid}.npy")
    bad = (s2 < 0).any(axis=1) | (s2 == 0).all(axis=1)
    neg = (s2 < 0).sum(axis=(1, 2, 3))
    for t, dt in enumerate(parse_dates(props["dates-S2"])):
        rows.append((pid, props["Fold"], "S2", dt, int(bad[t].sum()), int(neg[t])))
    for key in ["S1A", "S1D"]:
        s1 = np.load(DATA / f"DATA_{key}" / f"{key}_{pid}.npy")
        bad = (s1[:, 0] == 0) | (s1[:, 1] == 0) | ~np.isfinite(s1).all(axis=1)
        for t, dt in enumerate(parse_dates(props[f"dates-{key}"])):
            rows.append((pid, props["Fold"], key, dt, int(bad[t].sum()), 0))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="scan only the first N patches (by ID)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    meta = load_metadata()
    items = sorted(meta.items())[: args.limit]
    rows = []
    with Pool(args.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(scan_patch, items, chunksize=4), 1):
            rows.extend(r)
            if i % 250 == 0:
                print(f"{i}/{len(items)} patches", flush=True)

    df = pd.DataFrame(rows, columns=["patch", "fold", "sensor", "date", "n_invalid", "s2_neg_values"])
    df.insert(5, "frac_invalid", df["n_invalid"] / N_PX)
    df = df.sort_values(["patch", "sensor", "date"]).reset_index(drop=True)
    OUT.mkdir(exist_ok=True)
    df.to_parquet(OUT / "validity_scan.parquet", index=False)

    summary = {}
    for sensor, g in df.groupby("sensor"):
        summary[sensor] = {
            "acquisitions": len(g),
            "with_any_invalid_px": int((g["n_invalid"] > 0).sum()),
            "over_50pct_invalid": int((g["frac_invalid"] > 0.5).sum()),
            "fully_invalid": int((g["frac_invalid"] >= 1).sum()),
            "patches_affected": int(g.loc[g["n_invalid"] > 0, "patch"].nunique()),
            "invalid_px_share": round(float(g["n_invalid"].sum() / (len(g) * N_PX)), 5),
        }
    (OUT / "validity_scan_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
