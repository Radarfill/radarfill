"""PASTIS-R starter: sanity-check a few patches and draw RGB / NDVI / radar figures.

Layer 0, Week 1 check. Reads dataset/PASTIS-R (read-only); writes only to outputs/.

    .venv/bin/python code/data_kit/pastis_starter.py --n 5
    .venv/bin/python code/data_kit/pastis_starter.py --patches 10000 20000

For each patch it records evidence for three questions:
  1. Band order  - does the brightest-vegetation spectrum have the expected shape,
                   and does RGB = channels (2,1,0) look natural?
  2. NDVI        - (ch6 - ch2) / (ch6 + ch2): is it high on green fields?
  3. Radar units - are S1 values in dB, and is channel 2 = VV - VH?

Outputs
  outputs/starter/inventory.json        file counts, sizes, unannotated patch IDs
  outputs/starter/checks.csv            one row of checks per patch
  outputs/starter/class_curves.csv      per-class median NDVI / VV / VH per date (exploration only)
  outputs/figures/starter_<id>.png      maps + per-class time series for one patch
  outputs/figures/starter_overview.png  RGB / NDVI / VV / classes for all checked patches

The cloud flag here is a crude brightness test used ONLY to choose a display date and
grey out likely-cloudy dates in plots. Real cloud masks come later (OmniCloudMask).
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset" / "PASTIS-R"
OUT = ROOT / "outputs"

S2_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]
B2, B3, B4, B8 = 0, 1, 2, 6
VV, VH, RATIO = 0, 1, 2
REFERENCE_DATE = pd.Timestamp("2018-09-01")  # same as the official PASTIS loader

CLASS_NAMES = [
    "Background", "Meadow", "Soft winter wheat", "Corn", "Winter barley",
    "Winter rapeseed", "Spring barley", "Sunflower", "Grapevine", "Beet",
    "Winter triticale", "Winter durum wheat", "Fruits, vegetables, flowers",
    "Potatoes", "Leguminous fodder", "Soybeans", "Orchard", "Mixed cereal",
    "Sorghum", "Void label",
]
CROP_CLASSES = range(1, 19)  # skip 0 (background) and 19 (void)

# Fixed class -> colour so a crop keeps its colour in every figure.
# Classes 1-8 take the validated categorical slots in order; 9-18 share a neutral grey.
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER_CROP = "#9b9a94"
BACKGROUND = "#f0efec"
VOID = "#3b3b38"
INK, INK_MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

CLOUD_B2 = 2000        # crude: blue reflectance > 0.20 looks like cloud (display only)
CLEAR_MAX_FRAC = 0.10  # date counts as "clear" for display if < 10 % of valid pixels are flagged
RGB_MAX = 3000         # fixed linear stretch: 0 - 0.30 reflectance
MAX_CLASSES_PLOTTED = 5


def class_color(c):
    return SLOTS[c - 1] if 1 <= c <= 8 else OTHER_CROP


def class_linestyle(c):
    """Classes 9-18 share one grey, so each gets its own dash pattern to stay identifiable."""
    if c <= 8:
        return "-"
    dashes = [(0, (5, 2)), (0, (1, 1.5)), (0, (6, 2, 1, 2)), (0, (2, 2)), (0, (8, 3))]
    return dashes[(c - 9) % len(dashes)]


def class_cmap():
    colors = [BACKGROUND] + [class_color(c) for c in CROP_CLASSES] + [VOID]
    return ListedColormap(colors)


# --------------------------------------------------------------------------- loading

def load_metadata():
    with open(DATA / "metadata.geojson") as f:
        feats = json.load(f)["features"]
    return {int(ft["properties"]["ID_PATCH"]): ft["properties"] for ft in feats}


def parse_dates(d):
    """metadata stores {'0': YYYYMMDD, '1': ...}; return DatetimeIndex in index order."""
    if isinstance(d, str):
        d = json.loads(d.replace("'", '"'))
    keys = sorted(d, key=int)
    return pd.DatetimeIndex(pd.to_datetime([str(d[k]) for k in keys], format="%Y%m%d"))


def load_patch(pid):
    def npy(sub, name):
        return np.load(DATA / sub / f"{name}_{pid}.npy", mmap_mode="r")

    return {
        "s2": np.asarray(npy("DATA_S2", "S2"), dtype=np.float32),
        "s1a": np.asarray(npy("DATA_S1A", "S1A"), dtype=np.float32),
        "s1d": np.asarray(npy("DATA_S1D", "S1D"), dtype=np.float32),
        "dtypes": {k: str(npy(s, n).dtype) for k, s, n in
                   [("s2", "DATA_S2", "S2"), ("s1", "DATA_S1A", "S1A")]},
        "sem": np.asarray(npy("ANNOTATIONS", "TARGET")[0]),
        "inst": np.asarray(npy("INSTANCE_ANNOTATIONS", "INSTANCES")),
    }


def pick_patches(meta, n, seed):
    """Spread the sample over tiles: shuffle each tile's patches, then take them round-robin."""
    rng = np.random.default_rng(seed)
    by_tile = {}
    for pid in sorted(meta):
        by_tile.setdefault(meta[pid]["TILE"], []).append(pid)
    queues = {t: list(rng.permutation(ids)) for t, ids in sorted(by_tile.items())}
    picked = []
    while len(picked) < n and any(queues.values()):
        for t in sorted(queues):
            if queues[t] and len(picked) < n:
                picked.append(int(queues[t].pop(0)))
    return picked


# --------------------------------------------------------------------------- inventory

def inventory(meta):
    counts, ids = {}, {}
    for sub in ["DATA_S2", "DATA_S1A", "DATA_S1D", "ANNOTATIONS", "INSTANCE_ANNOTATIONS"]:
        files = sorted((DATA / sub).glob("*.npy"))
        prefixes = {}
        for f in files:
            prefix, num = f.stem.rsplit("_", 1)
            prefixes.setdefault(prefix, set()).add(int(num))
        counts[sub] = {p: len(v) for p, v in prefixes.items()}
        ids.update(prefixes)
    gb = sum(f.stat().st_size for f in DATA.rglob("*") if f.is_file()) / 1e9
    return {
        "metadata_patches": len(meta),
        "file_counts": counts,
        "unannotated_patch_ids": sorted(ids["S2"] - set(meta)),
        "metadata_ids_missing_s2": sorted(set(meta) - ids["S2"]),
        "dataset_size_gb": round(gb, 1),
        "folds": {int(k): int(v) for k, v in
                  pd.Series([p["Fold"] for p in meta.values()]).value_counts().sort_index().items()},
        "tiles": pd.Series([p["TILE"] for p in meta.values()]).value_counts().sort_index().to_dict(),
    }


# --------------------------------------------------------------------------- checks

def ndvi(s2, valid):
    red, nir = s2[:, B4], s2[:, B8]
    denom = nir + red
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (nir - red) / denom
    out[~valid | (denom <= 0)] = np.nan
    return out


def band_order_checks(spec):
    """Expected shape of a green-vegetation spectrum in B2..B12 order."""
    b = dict(zip(S2_BANDS, spec))
    return {
        "green_peak": b["B3"] > b["B2"] and b["B3"] > b["B4"],
        "red_edge_rises": b["B4"] < b["B5"] < b["B6"] < b["B7"],
        "nir_plateau": min(b["B8"], b["B8A"]) > b["B6"] and b["B8"] > 4 * b["B4"],
        "swir_falls": b["B8A"] > b["B11"] > b["B12"],
    }


def check_patch(pid, props):
    d = load_patch(pid)
    s2, s1a, s1d, sem, inst = d["s2"], d["s1a"], d["s1d"], d["sem"], d["inst"]
    dates = {k: parse_dates(props[f"dates-{k}"]) for k in ["S2", "S1A", "S1D"]}
    assert len(dates["S2"]) == len(s2) and len(dates["S1A"]) == len(s1a) and len(dates["S1D"]) == len(s1d)

    # S2 validity: any negative band or all-zero pixel is treated as invalid.
    valid = (s2 >= 0).all(axis=1) & (s2.sum(axis=1) > 0)
    valid_frac = valid.mean(axis=(1, 2))
    date_invalid = valid_frac < 0.5
    bright = (s2[:, B2] > CLOUD_B2) & valid
    crude_cloud = bright.sum(axis=(1, 2)) / np.maximum(valid.sum(axis=(1, 2)), 1)
    clear = ~date_invalid & (crude_cloud < CLEAR_MAX_FRAC)
    nd = ndvi(s2, valid)

    # S1 validity: missing radar is stored as exactly 0 in VV / VH (and ratio).
    s1a_ok = (s1a[:, VV] != 0) & (s1a[:, VH] != 0)
    s1d_ok = (s1d[:, VV] != 0) & (s1d[:, VH] != 0)

    crop = np.isin(sem, list(CROP_CLASSES))

    # Display date: clearest June-August date, else clearest date overall.
    months = dates["S2"].month
    summer = np.where(clear & np.isin(months, [6, 7, 8]))[0]
    pool = summer if len(summer) else np.where(~date_invalid)[0]
    t = int(pool[np.argmin(crude_cloud[pool])])
    t_date = dates["S2"][t]

    # Radar paired with the display date: latest S1A acquisition on or before it.
    prior = np.where(dates["S1A"] <= t_date)[0]
    t1 = int(prior[-1]) if len(prior) else None

    nd_t = nd[t]
    ok = valid[t] & ~np.isnan(nd_t)
    top = ok & (nd_t >= np.nanquantile(nd_t[ok], 0.9))
    veg_spec = s2[t][:, top].mean(axis=1)
    order = band_order_checks(veg_spec)

    def med(mask):
        v = nd_t[mask & ok]
        return round(float(np.median(v)), 3) if v.size else np.nan

    n_inst = [i for i in np.unique(inst) if i > 0]
    inst_class = {i: int(np.bincount(sem[inst == i]).argmax()) for i in n_inst}
    row = {
        "patch": pid, "fold": props["Fold"], "tile": props["TILE"],
        "T_S2": len(s2), "T_S1A": len(s1a), "T_S1D": len(s1d),
        "s2_dtype": d["dtypes"]["s2"], "s1_dtype": d["dtypes"]["s1"],
        "dates_sorted": all(x.is_monotonic_increasing for x in dates.values()),
        "s2_min": int(s2.min()), "s2_max": int(s2.max()),
        "s2_neg_value_frac": round(float((s2 < 0).mean()), 5),
        "s2_invalid_dates": int(date_invalid.sum()),
        "s2_display_clear_dates": int(clear.sum()),
        "n_fields": len(n_inst),
        "n_fields_void": sum(c == 19 for c in inst_class.values()),
        "classes": " ".join(str(c) for c in sorted(set(inst_class.values()))),
        "display_date": t_date.date().isoformat(),
        "display_crude_cloud": round(float(crude_cloud[t]), 3),
        "veg_spectrum_top10pct_ndvi": " ".join(str(int(round(v))) for v in veg_spec),
        **order,
        "band_order_ok": all(order.values()),
        "ndvi_med_crop": med(crop),
        "ndvi_med_meadow": med(sem == 1),
        "ndvi_q90_crop": round(float(np.nanquantile(nd_t[crop & ok], 0.9)), 3) if (crop & ok).any() else np.nan,
        "ndvi_med_background": med(sem == 0),
        "s1a_nodata_frac": round(float(1 - s1a_ok.mean()), 5),
        "s1d_nodata_frac": round(float(1 - s1d_ok.mean()), 5),
        "s1a_vv_mean_db": round(float(s1a[:, VV][s1a_ok].mean()), 2),
        "s1a_vh_mean_db": round(float(s1a[:, VH][s1a_ok].mean()), 2),
        "s1d_vv_mean_db": round(float(s1d[:, VV][s1d_ok].mean()), 2),
        "s1a_vv_frac_positive": round(float((s1a[:, VV][s1a_ok] > 0).mean()), 5),
        "s1_ratio_minus_vv_vh_maxabs": round(float(max(
            np.abs(s1[:, RATIO] - (s1[:, VV] - s1[:, VH]))[ok1].max()
            for s1, ok1 in ((s1a, s1a_ok), (s1d, s1d_ok)))), 4),
        "s1a_display_date": dates["S1A"][t1].date().isoformat() if t1 is not None else "",
        "s2_dates_before_first_s1a": int((dates["S2"] < dates["S1A"][0]).sum()),
        "s2_dates_before_first_s1d": int((dates["S2"] < dates["S1D"][0]).sum()),
    }

    # Per-class median curves (pixel level; exploration only, not the Data Kit curves).
    present = [c for c in CROP_CLASSES if (sem == c).any()]
    curves = []
    for c in present:
        m = sem == c
        for ti, dt in enumerate(dates["S2"]):
            v = nd[ti][m & valid[ti]]
            curves.append((pid, "S2", c, dt, "ndvi", float(np.median(v)) if v.size else np.nan,
                           int(v.size), bool(clear[ti])))
        for key, arr, ok1 in [("S1A", s1a, s1a_ok)]:
            for ti, dt in enumerate(dates[key]):
                for ch, name in [(VV, "VV"), (VH, "VH")]:
                    v = arr[ti, ch][m & ok1[ti]]
                    curves.append((pid, key, c, dt, name, float(np.median(v)) if v.size else np.nan,
                                   int(v.size), np.nan))
    curves = pd.DataFrame(curves, columns=["patch", "sensor", "crop", "date", "var", "median", "n_px", "clear"])
    curves.insert(3, "crop_name", curves["crop"].map(lambda c: CLASS_NAMES[c]))

    fig_data = dict(pid=pid, props=props, s2=s2, s1a=s1a, s1a_ok=s1a_ok, sem=sem, nd=nd, t=t, t1=t1,
                    dates=dates, clear=clear, date_invalid=date_invalid, present=present)
    return row, curves, fig_data


# --------------------------------------------------------------------------- figures

def rgb_image(s2, t):
    img = s2[t][[B4, B3, B2]].transpose(1, 2, 0) / RGB_MAX
    return np.clip(img, 0, 1)


def style_axis(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_MUTED)
    ax.tick_params(colors=INK_MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def map_axis(ax, title):
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=9, color=INK, loc="left")


def draw_maps(axes, f, with_colorbars=True):
    s2, s1a, sem, nd, t, t1, dates = f["s2"], f["s1a"], f["sem"], f["nd"], f["t"], f["t1"], f["dates"]
    d2 = dates["S2"][t].date()
    axes[0].imshow(rgb_image(s2, t))
    map_axis(axes[0], f"RGB (B4,B3,B2)  {d2}")
    im = axes[1].imshow(nd[t], cmap="Greens", vmin=0, vmax=1)
    map_axis(axes[1], f"NDVI  {d2}")
    if with_colorbars:
        plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.02).ax.tick_params(labelsize=7)
    if t1 is not None:
        d1 = dates["S1A"][t1].date()
        im = axes[2].imshow(np.ma.masked_equal(s1a[t1, VV], 0), cmap="gray", vmin=-25, vmax=0)
        map_axis(axes[2], f"S1A VV dB  {d1}")
        if with_colorbars:
            plt.colorbar(im, ax=axes[2], fraction=0.046, pad=0.02).ax.tick_params(labelsize=7)
    else:
        map_axis(axes[2], "S1A VV: no pass on/before S2 date")
    k = 3
    if len(axes) == 5:
        if t1 is not None:
            im = axes[3].imshow(np.ma.masked_equal(s1a[t1, VH], 0), cmap="gray", vmin=-30, vmax=-5)
            map_axis(axes[3], f"S1A VH dB  {d1}")
            if with_colorbars:
                plt.colorbar(im, ax=axes[3], fraction=0.046, pad=0.02).ax.tick_params(labelsize=7)
        k = 4
    axes[k].imshow(sem, cmap=class_cmap(), vmin=-0.5, vmax=19.5, interpolation="nearest")
    map_axis(axes[k], "Crop class (TARGET layer 0)")


def class_legend_handles(present):
    handles = [Patch(color=class_color(c), label=f"{c} {CLASS_NAMES[c]}") for c in present if c <= 8]
    if any(c > 8 for c in present):
        others = ", ".join(str(c) for c in present if c > 8)
        handles.append(Patch(color=OTHER_CROP, label=f"Other crops ({others})"))
    handles += [Patch(color=BACKGROUND, label="0 Background", ec=INK_MUTED, lw=0.5),
                Patch(color=VOID, label="19 Void")]
    return handles


def patch_figure(f, path):
    pid, props, sem = f["pid"], f["props"], f["sem"]
    fig = plt.figure(figsize=(17, 9.2), dpi=120)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.05], hspace=0.22)
    top = gs[0].subgridspec(1, 5, wspace=0.32)
    bot = gs[1].subgridspec(1, 3, wspace=0.18)
    draw_maps([fig.add_subplot(top[i]) for i in range(5)], f)

    counts = {c: int((sem == c).sum()) for c in f["present"]}
    shown = sorted(counts, key=counts.get, reverse=True)[:MAX_CLASSES_PLOTTED]
    nd, s1a, dates, clear, bad = f["nd"], f["s1a"], f["dates"], f["clear"], f["date_invalid"]

    ax = fig.add_subplot(bot[0])
    for c in shown:
        m = sem == c
        series = np.array([np.nanmedian(nd[ti][m]) if np.isfinite(nd[ti][m]).any() else np.nan
                           for ti in range(len(nd))])
        ax.plot(dates["S2"][clear], series[clear], color=class_color(c), ls=class_linestyle(c), lw=1.6,
                marker="o", ms=3.5, mec="white", mew=0.6)
    ax.plot(dates["S2"][~clear & ~bad], np.full((~clear & ~bad).sum(), -0.05), "|",
            color=INK_MUTED, ms=8, mew=1.2)
    ax.plot(dates["S2"][bad], np.full(bad.sum(), -0.05), "x", color=INK, ms=5, mew=1.2)
    ax.set_ylim(-0.1, 1.0)
    ax.set_title(f"Median NDVI per class, clear dates only ({clear.sum()}/{len(clear)})",
                 fontsize=9, color=INK, loc="left")
    style_axis(ax)

    for i, (ch, name, lim) in enumerate([(VV, "VV", (-22, -2)), (VH, "VH", (-28, -8))], start=1):
        ax = fig.add_subplot(bot[i])
        for c in shown:
            m = sem == c
            ok1 = f["s1a_ok"]
            ax.plot(dates["S1A"], [np.median(s1a[ti, ch][m & ok1[ti]]) if (m & ok1[ti]).any() else np.nan
                                   for ti in range(len(s1a))],
                    color=class_color(c), ls=class_linestyle(c), lw=1.6)
        ax.set_ylim(*lim)
        ax.set_title(f"Median S1A {name} (dB) per class, all {len(s1a)} passes",
                     fontsize=9, color=INK, loc="left")
        style_axis(ax)

    handles = [Line2D([], [], color=class_color(c), ls=class_linestyle(c), lw=2, label=f"{c} {CLASS_NAMES[c]}")
               for c in shown]
    handles += [Line2D([], [], color=INK_MUTED, marker="|", ls="", ms=8, mew=1.2,
                       label="S2 date, likely cloudy (crude B2 test)"),
                Line2D([], [], color=INK, marker="x", ls="", ms=5, mew=1.2,
                       label="S2 date, mostly invalid (negative values)")]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), fontsize=8, frameon=False,
               bbox_to_anchor=(0.5, 0.0))
    fig.legend(handles=class_legend_handles(f["present"]), loc="upper right", fontsize=7,
               frameon=False, bbox_to_anchor=(0.995, 0.985), title="Class map", title_fontsize=7)
    fig.suptitle(f"PASTIS-R patch {pid}  ·  fold {props['Fold']}  ·  tile {props['TILE']}",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.subplots_adjust(left=0.03, right=0.89, top=0.92, bottom=0.08)
    fig.savefig(path)
    plt.close(fig)


def overview_figure(figs, path):
    n = len(figs)
    fig, axes = plt.subplots(n, 4, figsize=(12, 3.05 * n), dpi=110)
    axes = np.atleast_2d(axes)
    for r, f in enumerate(figs):
        draw_maps(list(axes[r]), f, with_colorbars=False)
        axes[r, 0].set_ylabel(f"{f['pid']}  fold {f['props']['Fold']}\n{f['props']['TILE']}",
                              fontsize=9, color=INK)
    present = sorted({c for f in figs for c in f["present"]})
    fig.legend(handles=class_legend_handles(present), loc="lower center", ncol=6, fontsize=8,
               frameon=False)
    fig.suptitle("PASTIS-R starter check: RGB · NDVI (0 to 1, Greens) · S1A VV (-25 to 0 dB) · classes",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.subplots_adjust(left=0.07, right=0.99, top=0.95, bottom=0.07, wspace=0.05, hspace=0.18)
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=5, help="number of patches to sample (spread over tiles)")
    ap.add_argument("--patches", type=int, nargs="*", help="explicit patch IDs (overrides --n)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    out_tab, out_fig = OUT / "starter", OUT / "figures"
    for p in (out_tab, out_fig):
        assert DATA.resolve() not in p.resolve().parents, "refusing to write inside dataset/"
        p.mkdir(parents=True, exist_ok=True)

    meta = load_metadata()
    inv = inventory(meta)
    (out_tab / "inventory.json").write_text(json.dumps(inv, indent=2))
    print(f"metadata patches: {inv['metadata_patches']} | file counts: {inv['file_counts']}")
    print(f"unannotated patches with imagery: {len(inv['unannotated_patch_ids'])}")

    pids = args.patches or pick_patches(meta, args.n, args.seed)
    rows, curves, figs = [], [], []
    for pid in pids:
        row, cur, f = check_patch(pid, meta[pid])
        rows.append(row)
        curves.append(cur)
        figs.append(f)
        patch_figure(f, out_fig / f"starter_{pid}.png")
        print(f"patch {pid}: band_order_ok={row['band_order_ok']} display={row['display_date']} "
              f"NDVI crop med={row['ndvi_med_crop']} q90={row['ndvi_q90_crop']} "
              f"VV={row['s1a_vv_mean_db']} dB VH={row['s1a_vh_mean_db']} dB "
              f"ratio-(VV-VH)={row['s1_ratio_minus_vv_vh_maxabs']}")

    checks = pd.DataFrame(rows)
    checks.to_csv(out_tab / "checks.csv", index=False)
    pd.concat(curves).to_csv(out_tab / "class_curves.csv", index=False)
    overview_figure(figs, out_fig / "starter_overview.png")
    print(f"wrote {out_tab}/checks.csv, class_curves.csv, inventory.json and "
          f"{len(figs) + 1} figures in {out_fig}")


if __name__ == "__main__":
    main()
