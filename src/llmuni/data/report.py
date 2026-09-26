"""Phase 1 report: POI coverage table (CSV + Markdown) and a small-multiples POI map."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

# Reference palette (dataviz skill), light mode. One series color: every panel shows one
# category, so identity comes from the panel title rather than from hue.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
ROAD = "#e1e0d9"
ROAD_MAJOR = "#c3c2b7"
SERIES = "#2a78d6"
FONTS = ["Segoe UI", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

EXTENT = (-122.517, -122.355, 37.704, 37.836)  # lon/lat view of mainland SF and Treasure Island
MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary"}


def label(category: str) -> str:
    return {"bank_atm": "Bank / ATM"}.get(category, category.replace("_", " ").capitalize())


def coverage_table(pois: pd.DataFrame, min_valid: int, order: list[str]) -> pd.DataFrame:
    g = pois.groupby("category")
    status = pois["hours_status"]
    table = pd.DataFrame({
        "pois": g.size(),
        "with_hours_tag": g["opening_hours"].count(),
        "parseable": (~status.isin(["missing", "unparseable"])).groupby(pois["category"]).sum(),
        "unknown": (status == "unknown").groupby(pois["category"]).sum(),
        "valid": g["valid_hours"].sum(),
    }).reindex(order, fill_value=0).astype(int)
    table["pct_valid"] = (100 * table["valid"] / table["pois"].where(table["pois"] > 0)).round(1).fillna(0.0)
    table["kept"] = table["valid"] >= min_valid
    table.index.name = "category"
    return table


def write_phase1(out_dir: Path, pois: pd.DataFrame, coverage: pd.DataFrame, roads, sf_geom, caption: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(out_dir / "poi_coverage.csv")
    (out_dir / "poi_coverage.md").write_text(_coverage_markdown(pois, coverage, caption), encoding="utf-8")
    plot_poi_map(pois, coverage, roads, sf_geom, caption, out_dir / "poi_map.png")


def _coverage_markdown(pois: pd.DataFrame, coverage: pd.DataFrame, caption: str) -> str:
    lines = [
        "# Phase 1: errand POI coverage",
        "",
        caption,
        "",
        "POIs are named, publicly accessible OSM features inside the San Francisco boundary, de-duplicated.",
        "*Valid* means the hours parse, have no `unknown` periods, and open at least once in the reference week;",
        "only valid places become task candidates. *Unknown* places parse but contain `unknown` periods.",
        "",
        "| Category | POIs | Hours tagged | Parseable | Unknown | Valid | % valid | Kept |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for cat, r in coverage.iterrows():
        kept = "yes" if r["kept"] else "**no**"
        lines.append(
            f"| {label(cat)} | {r['pois']} | {r['with_hours_tag']} | {r['parseable']} | {r['unknown']} | {r['valid']} "
            f"| {r['pct_valid']:.1f} | {kept} |"
        )
    total = coverage[["pois", "with_hours_tag", "parseable", "unknown", "valid"]].sum()
    pct = 100 * total["valid"] / max(total["pois"], 1)
    lines.append(
        f"| **All** | {total['pois']} | {total['with_hours_tag']} | {total['parseable']} | {total['unknown']} "
        f"| {total['valid']} | {pct:.1f} | |"
    )
    brands = pois[(pois["category"] == "supermarket") & pois["valid_hours"]]["brand"].value_counts()
    if len(brands):
        lines += ["", "Supermarket brands with valid hours: " + ", ".join(f"{b} {n}" for b, n in brands.items()) + "."]
    return "\n".join(lines) + "\n"


def plot_poi_map(pois: pd.DataFrame, coverage: pd.DataFrame, roads, sf_geom, caption: str, path: Path) -> None:
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": FONTS})
    minor, major = _roads_in(roads, sf_geom)
    lon0, lon1, lat0, lat1 = EXTENT
    aspect = 1 / math.cos(math.radians((lat0 + lat1) / 2))
    ncols = 4
    nrows = math.ceil(len(coverage) / ncols)
    panel_w = 3.4
    panel_h = panel_w * (lat1 - lat0) * aspect / (lon1 - lon0)
    header_in, title_in = 1.5, 0.62  # figure header; per-panel title + note
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(ncols * panel_w, nrows * (panel_h + title_in) + header_in), facecolor=SURFACE, squeeze=False
    )
    height = fig.get_figheight()
    fig.subplots_adjust(
        left=0.015, right=0.985, bottom=0.01, top=1 - header_in / height, hspace=title_in / panel_h, wspace=0.05
    )

    for ax in axes.flat:
        ax.set_axis_off()
    for ax, (cat, row) in zip(axes.flat, coverage.iterrows()):
        ax.add_collection(LineCollection(minor, colors=ROAD, linewidths=0.3, zorder=1))
        ax.add_collection(LineCollection(major, colors=ROAD_MAJOR, linewidths=0.6, zorder=1))
        sub = pois[pois["category"] == cat]
        missing, valid = sub[~sub["valid_hours"]], sub[sub["valid_hours"]]
        ax.scatter(missing["lon"], missing["lat"], s=5, color=MUTED, linewidths=0, zorder=2)
        ax.scatter(valid["lon"], valid["lat"], s=14, color=SERIES, edgecolors=SURFACE, linewidths=0.5, zorder=3)
        ax.set_xlim(lon0, lon1)
        ax.set_ylim(lat0, lat1)
        ax.set_aspect(aspect)
        ax.set_title(label(cat), loc="left", fontsize=11, fontweight="semibold", color=INK, pad=16)
        note = f"{row['valid']} of {row['pois']} with valid hours ({row['pct_valid']:.0f}%)"
        if not row["kept"]:
            note += " · dropped"
        ax.text(0, 1.015, note, transform=ax.transAxes, fontsize=8.5, color=INK_2, va="bottom")

    fig.text(0.015, 1 - 0.3 / height, "Errand POIs in San Francisco", fontsize=16, fontweight="semibold", color=INK, va="top")
    fig.text(0.015, 1 - 0.68 / height, caption, fontsize=9.5, color=INK_2, va="top")
    handles = [
        Line2D([], [], marker="o", linestyle="", markersize=6, markerfacecolor=SERIES, markeredgecolor=SURFACE, label="Valid opening hours"),
        Line2D([], [], marker="o", linestyle="", markersize=4, markerfacecolor=MUTED, markeredgecolor=MUTED, label="Hours missing, unparseable or unknown"),
    ]
    fig.legend(
        handles=handles, loc="upper right", bbox_to_anchor=(0.985, 1 - 0.22 / height), frameon=False,
        fontsize=9.5, labelcolor=INK_2, ncols=2,
    )
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def _roads_in(roads, sf_geom) -> tuple[list, list]:
    """Road polylines starting inside SF, split into minor and major classes."""
    if not roads:
        return [], []
    starts = np.array([coords[0] for _, coords in roads])
    inside = shapely.contains_xy(sf_geom, starts[:, 0], starts[:, 1])
    minor = [coords for (cls, coords), ok in zip(roads, inside) if ok and cls not in MAJOR_ROADS]
    major = [coords for (cls, coords), ok in zip(roads, inside) if ok and cls in MAJOR_ROADS]
    return minor, major
