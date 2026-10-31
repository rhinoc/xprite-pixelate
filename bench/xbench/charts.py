"""Charts for the benchmark results (static PNGs for the README and the article).

  python -I bench/xbench/charts.py [--out bench/results/charts]

Reads bench/results/<suite>/summary.json. The palette is the dataviz reference palette's first four
categorical slots in fixed order (validated: adjacent CVD dE >= 9.1, normal-vision >= 22.9). Two
slots are below 3:1 on the surface, so every bar carries a visible value label.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "results"
METHODS = ["xprite", "fixer", "perfectpixel", "proper"]
LABELS = {"xprite": "Xprite Auto", "fixer": "pixel-art-fixer", "perfectpixel": "perfectPixel",
          "proper": "proper-pixel-art"}
SERIES = {"xprite": "#2a78d6", "fixer": "#eb6834", "perfectpixel": "#1baf7a", "proper": "#eda100"}
SURFACE, TEXT, TEXT_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
GAP = 2 / 72  # 2 px surface gap between adjacent bars, in inches at 72 dpi


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": ["Hiragino Sans GB", "Helvetica Neue", "DejaVu Sans"], "font.size": 11,
        "text.color": TEXT, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2,
        "ytick.color": TEXT_2, "axes.edgecolor": AXIS, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.spines.top": False,
        "axes.spines.right": False, "axes.spines.left": False, "axes.titlelocation": "left",
        "axes.titlesize": 13, "axes.titleweight": "bold", "legend.frameon": False,
    })


def load(suite):
    path = RESULTS / suite / "summary.json"
    return json.loads(path.read_text()) if path.exists() else None


def present(summary):
    return [m for m in METHODS if m in summary["methods"]]


def grouped_bars(ax, groups, values, methods, percent=True):
    """values[method][group]; one cluster per group, one bar per method, value labels on top."""
    n = len(methods)
    width = 0.8 / n
    x = np.arange(len(groups))
    for i, m in enumerate(methods):
        v = np.array([values[m].get(g) or 0 for g in groups], float)
        bars = ax.bar(x + (i - (n - 1) / 2) * width, v, width, color=SERIES[m], label=LABELS[m],
                      edgecolor=SURFACE, linewidth=1.5)
        for b, val in zip(bars, v):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                    f"{val * 100:.0f}" if percent else f"{val:.2f}", ha="center", va="bottom",
                    fontsize=8.5, color=TEXT_2)
    ax.set_xticks(x, groups)
    ax.grid(axis="x", visible=False)
    if percent:
        ax.set_ylim(0, 1.08)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))


def overall(summary, title, out):
    methods = present(summary)
    groups = ["exact", "within1", "grid_align"]
    names = {"exact": "Exact size", "within1": "Within 1 cell", "grid_align": "Grid alignment"}
    values = {m: {names[g]: summary["methods"][m]["overall"][g] for g in groups} for m in methods}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    grouped_bars(ax, [zh(names[g]) for g in groups], {m: {zh(k): v for k, v in values[m].items()} for m in methods}, methods)
    ax.set_title(zh(title))
    ax.legend(ncol=len(methods), loc="upper left", bbox_to_anchor=(0, -0.08))
    n = summary["cases"]
    fig.text(0.01, 0.01, f"{n} 个样本。网格对齐：格线和真实切割的 F1。" if ZH else
             f"{n} cases. Grid alignment: pixel-bench F1 of grid lines against the true cuts.",
             color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, dpi=200)
    plt.close(fig)


def heatmap(summary, key, title, out, order=None):
    methods = present(summary)
    groups = order or sorted(summary["methods"][methods[0]][key])
    groups = [g for g in groups if g in summary["methods"][methods[0]][key]]
    data = np.array([[summary["methods"][m][key].get(g, {}).get("exact", np.nan) for g in groups]
                     for m in methods])
    cmap = LinearSegmentedColormap.from_list("blues", BLUES)
    fig, ax = plt.subplots(figsize=(max(7, 0.62 * len(groups) + 2.5), 0.55 * len(methods) + 1.9))
    ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(range(len(groups)), [CATEGORY_ZH.get(g, g) if ZH else g.replace("gen_", "") for g in groups], rotation=40,
                  ha="right")
    ax.set_yticks(range(len(methods)), [LABELS[m] for m in methods])
    ax.set_xticks(np.arange(-0.5, len(groups)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(methods)), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="both", length=0)
    for i in range(len(methods)):
        for j in range(len(groups)):
            if np.isnan(data[i, j]):
                continue
            ax.text(j, i, f"{data[i, j] * 100:.0f}", ha="center", va="center", fontsize=9,
                    color="#ffffff" if data[i, j] > 0.55 else TEXT)
    ax.set_title(zh(title))
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def speed(summary, out):
    methods = present(summary)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ends = []
    for m in methods:
        rows = summary["methods"][m]["category"]
        sides = sorted(int(k.replace("side", "")) for k in rows
                       if rows[k]["median_s"] is not None and rows[k]["errors"] < rows[k]["n"])
        med = [rows[f"side{s}"]["median_s"] for s in sides]
        ax.plot(sides, med, color=SERIES[m], linewidth=2, marker="o", markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=2, label=LABELS[m])
        ends.append((med[-1], sides[-1]))
    # End labels, nudged apart where two lines end close together on the log scale.
    ends.sort()
    offsets = [0.0] * len(ends)
    for i in range(1, len(ends)):
        if ends[i][0] / ends[i - 1][0] < 1.35:
            offsets[i] = offsets[i - 1] + 9
    for (value, side), dy in zip(ends, offsets):
        ax.annotate(f"{value:.2f}s" if value < 10 else f"{value:.0f}s", (side, value),
                    xytext=(8, dy), textcoords="offset points", va="center", fontsize=9,
                    color=TEXT_2)
    ax.set_yscale("log")
    ax.set_xlabel(zh("Longest side of the input (px)"))
    ax.set_ylabel(zh("Median time per image (s, log scale)"))
    ax.set_xticks(sides, [str(s) for s in sides])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_title(zh("Time per image by input size"))
    ax.legend(loc="upper left")
    fig.text(0.01, 0.01, "Apple M4 单线程；只计检测和重建，不计解码。" if ZH else
             "One worker on an Apple M4; detection and reconstruction, without decode.",
             color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, dpi=200)
    plt.close(fig)


def delta_e(suite, out, title):
    """ΔE on the cases every tool sized exactly, so each tool is judged on the same images."""
    import json as _json
    rows = {m: {(r := _json.loads(l))["key"]: r for l in open(RESULTS / suite / f"{m}.jsonl")} for m in METHODS
            if (RESULTS / suite / f"{m}.jsonl").exists()}
    methods = [m for m in METHODS if m in rows]
    common = [k for k in rows[methods[0]]
              if all(rows[m].get(k, {}).get("exact") and "delta_e" in rows[m][k] for m in methods)]
    values = {m: float(np.mean([rows[m][k]["delta_e"] for k in common])) for m in methods}
    fig, ax = plt.subplots(figsize=(8, 3.8))
    y = np.arange(len(methods))[::-1]
    bars = ax.barh(y, [values[m] for m in methods], color=[SERIES[m] for m in methods], height=0.62,
                   edgecolor=SURFACE, linewidth=1.5)
    for bar, m in zip(bars, methods):
        ax.text(bar.get_width() + 0.04, bar.get_y() + bar.get_height() / 2, f"{values[m]:.2f}",
                va="center", fontsize=10, color=TEXT_2)
    ax.set_yticks(y, [LABELS[m] for m in methods])
    ax.set_xlabel(zh("Mean ΔE (CIELAB) against the native art, lower is better"))
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(values.values()) * 1.18)
    ax.set_title(zh(title))
    fig.text(0.01, 0.01, f"{len(common)} 个四家都还原对尺寸的样本。" if ZH else f"{len(common)} cases every tool sized exactly.",
             color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return len(common), values


def table(summary, out):
    methods = present(summary)
    lines = ["| Method | Exact | Within 1 | Grid align | Pixel match | ΔE | Fringe | Median s | Errors |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    pct = lambda v: "-" if v is None else f"{v * 100:.1f}%"  # noqa: E731
    num = lambda v, d=2: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    for m in methods:
        o = summary["methods"][m]["overall"]
        lines.append(f"| {LABELS[m]} | {pct(o['exact'])} | {pct(o['within1'])} | "
                     f"{pct(o['grid_align'])} | {pct(o['pixel_match'])} | {num(o['delta_e'])} | "
                     f"{pct(o['fringe'])} | {num(o['median_s'], 3)} | {o['errors']} |")
    out.write_text("\n".join(lines) + "\n")


ZH = False
ZH_TEXT = {
    "Exact size": "尺寸完全正确", "Within 1 cell": "差一格以内", "Grid alignment": "网格对齐",
    "AI suite: recovered size and grid": "AI 套件：尺寸与网格",
    "pixel-bench v1 on the same corpus": "pixel-bench v1（同一语料）",
    "AI suite: exact size by category (%)": "AI 套件：各类别尺寸完全正确率（%）",
    "AI suite: exact size by native image size (%)": "AI 套件：按原图尺寸（%）",
    "AI suite: exact size by palette size (%)": "AI 套件：按色数（%）",
    "AI suite: exact size by genre (%)": "AI 套件：按题材（%）",
    "AI suite: colour error on shared exact cases": "AI 套件：色差（四家都还原对尺寸的样本）",
    "pixel-bench v1: colour error on shared exact cases": "pixel-bench v1：色差（四家都还原对尺寸的样本）",
    "Time per image by input size": "不同输入尺寸下的单张耗时",
    "Longest side of the input (px)": "输入图长边（像素）",
    "Median time per image (s, log scale)": "单张耗时中位数（秒，对数刻度）",
    "Mean ΔE (CIELAB) against the native art, lower is better": "和原图的平均色差 ΔE（CIELAB），越低越好",
}


CATEGORY_ZH = {
    "gen_clean": "干净软边", "gen_sparse": "大量留白", "gen_white": "灰白底", "gen_soft_edge": "半透明描边",
    "gen_webp": "漂移+WebP", "gen_halo_jpeg": "光晕+JPEG", "gen_painterly": "格内笔触", "gen_small_pitch": "小格宽",
    "gen_large_pitch": "大格宽", "gen_wobble": "强漂移", "gen_pair": "并排双人", "gen_shadow": "半透明投影",
    "tiny": "8–16 px", "small": "17–48 px", "medium": "49–128 px", "large": "129–320 px",
    "2-4": "2–4 色", "5-16": "5–16 色", "17-64": "17–64 色", "65+": "65+ 色",
    "animation-frame": "动画帧", "character": "角色", "isometric": "等距", "item": "道具", "monster": "怪物",
    "portrait": "头像", "scene": "场景", "tile": "地砖", "ui": "UI",
}


def zh(text):
    return ZH_TEXT.get(text, text) if ZH else text


def main():
    global ZH
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(RESULTS / "charts"))
    p.add_argument("--zh", action="store_true", help="Chinese titles and labels")
    args = p.parse_args()
    ZH = args.zh
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    style()
    ai = load("ai")
    if ai:
        overall(ai, "AI suite: recovered size and grid", out / "ai-overall.png")
        order = ["gen_clean", "gen_sparse", "gen_white", "gen_soft_edge", "gen_webp",
                 "gen_halo_jpeg", "gen_painterly", "gen_small_pitch", "gen_large_pitch",
                 "gen_wobble", "gen_pair", "gen_shadow"]
        heatmap(ai, "category", "AI suite: exact size by category (%)", out / "ai-categories.png", order)
        heatmap(ai, "size_bin", "AI suite: exact size by native image size (%)", out / "ai-size.png",
                ["tiny", "small", "medium", "large"])
        heatmap(ai, "palette_bin", "AI suite: exact size by palette size (%)", out / "ai-palette.png",
                ["2-4", "5-16", "17-64", "65+"])
        heatmap(ai, "genre", "AI suite: exact size by genre (%)", out / "ai-genre.png")
        table(ai, out / "ai-table.md")
        print("ai ΔE", delta_e("ai", out / "ai-delta-e.png", "AI suite: colour error on shared exact cases"))
    v1 = load("v1")
    if v1:
        overall(v1, "pixel-bench v1 on the same corpus", out / "v1-overall.png")
        table(v1, out / "v1-table.md")
        print("v1 ΔE", delta_e("v1", out / "v1-delta-e.png", "pixel-bench v1: colour error on shared exact cases"))
    sp = load("speed")
    if sp:
        speed(sp, out / "speed.png")
        table(sp, out / "speed-table.md")


if __name__ == "__main__":
    main()
