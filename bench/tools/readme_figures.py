"""README figures: a real generated image (docs/griffith-input.png) and one AI-suite case per
category, each recovered by every benchmark method, plus the recovered grid of the real image.

  bench/.venv/bin/python -I bench/tools/readme_figures.py

Needs `pnpm run build` first. Writes docs/images/ and prints docs/images/cases.json.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench/xbench"))
import methods as M  # noqa: E402
import score as S  # noqa: E402
import suite as A  # noqa: E402

OUT = ROOT / "docs/images"
DETECT = ROOT / "bench/tools/readme-detect.mjs"
VIEW = 240  # display height of every tile, px
HERO_VIEW = 320
CHECKER = 10
LIGHT, DARK = (252, 252, 251), (232, 231, 226)
WHITE = np.full(3, 255, np.uint8)
MESH = (235, 0, 140, 255)
# One AI-suite case per category: (image id, category, file stem).
CASES = [
    ("luizmelo-goblin-idle-f0", "gen_pair", "pair"),
    ("ansimuz-sv-boss-dragon", "gen_wobble", "wobble"),
    ("denzi-monster-r04c01", "gen_small_pitch", "small"),
    ("cawfeecrow-neko", "gen_sparse", "sparse"),
    ("ansimuz-sv-sunny-dragon", "gen_white", "white"),
    ("dcss-naga-mage", "gen_painterly", "painterly"),
]


def case(image_id, category):
    rec = {r["id"]: r for r in json.load(open(ROOT / "bench/corpus/manifest.json"))}[image_id]
    return A.build_case(str(ROOT / "bench/corpus" / rec["file"]), image_id, category,
                        "transparent" in rec["tags"])


def detect(img):
    h, w = img.shape[:2]
    with tempfile.TemporaryDirectory() as t:
        Path(t, "in").write_bytes(np.ascontiguousarray(img).tobytes())
        return json.loads(subprocess.check_output(
            ["node", str(DETECT), f"{t}/in", str(w), str(h), f"{t}/out"], cwd=ROOT))


def run_all(img):
    """Every method's native result as RGBA, or None when it refused or failed."""
    results = {}
    for name, cls in M.METHODS.items():
        method = cls()
        view = img if method.rgba else A.composite(img, WHITE)
        r = method.run(np.ascontiguousarray(view))
        method.close()
        if r.native is None:
            results[name] = None
            continue
        native = r.native if r.native.ndim == 3 else np.dstack([r.native] * 3)
        if native.shape[2] == 3:
            native = np.dstack([native, np.full(native.shape[:2], 255, np.uint8)])
        results[name] = (native, method.rgba)
    return results


def cuts(grid, axis):
    explicit = grid.get("cutsX" if axis == "x" else "cutsY")
    if explicit:
        return explicit
    size = grid["width" if axis == "x" else "height"]
    cell = grid["cellWidth" if axis == "x" else "cellHeight"]
    start = grid["offsetX" if axis == "x" else "offsetY"]
    return list(np.arange(start, size + 1e-6, cell))


def on_checker(rgba):
    h, w = rgba.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    board = np.where(((yy // CHECKER + xx // CHECKER) % 2 == 0)[:, :, None], LIGHT, DARK)
    a = rgba[:, :, 3:4] / 255.0
    return Image.fromarray((rgba[:, :, :3] * a + board * (1 - a)).astype(np.uint8))


def scaled(rgba, height, nearest):
    h, w = rgba.shape[:2]
    size = (max(1, round(w * height / h)), height)
    resample = Image.NEAREST if nearest else Image.LANCZOS
    return np.asarray(Image.fromarray(rgba, "RGBA").resize(size, resample))


def save(rgba, path, height, nearest):
    on_checker(scaled(rgba, height, nearest)).save(path, optimize=True)


def mesh(img, grid, height):
    k = height / img.shape[0]
    view = on_checker(scaled(img, height, False))
    draw = ImageDraw.Draw(view)
    for x in cuts(grid, "x"):
        draw.line([(x * k, 0), (x * k, height)], fill=MESH, width=1)
    for y in cuts(grid, "y"):
        draw.line([(0, y * k), (view.width, y * k)], fill=MESH, width=1)
    return view


def hero():
    img = np.asarray(Image.open(ROOT / "docs/griffith-input.png").convert("RGBA"))
    mesh(img, detect(img), HERO_VIEW).save(OUT / "griffith-mesh.png", optimize=True)
    sizes = {}
    for name, result in run_all(img).items():
        if result is None:
            sizes[name] = None
            continue
        native, _ = result
        sizes[name] = [native.shape[1], native.shape[0]]
        save(native, OUT / f"griffith-{name}.png", HERO_VIEW, True)
    return {"input": [img.shape[1], img.shape[0]], "methods": sizes}


def cases():
    report = {}
    for image_id, category, stem in CASES:
        c = case(image_id, category)
        img = c["img"]
        save(img, OUT / f"{stem}-input.png", VIEW, False)
        gt_box = S._box(c["gt"][:, :, 3] >= S.HALF_ALPHA)
        entry = {"id": image_id, "category": category, "input": [img.shape[1], img.shape[0]],
                 "native": [gt_box[2] - gt_box[0], gt_box[3] - gt_box[1]], "methods": {}}
        for name, result in run_all(img).items():
            if result is None:
                entry["methods"][name] = None
                continue
            native, rgba = result
            s = S.score(c["gt"], native if rgba else native[:, :, :3], c["background"],
                        c["U"], c["V"], rgba)
            entry["methods"][name] = {"cells": [s.get("cols"), s.get("rows")],
                                      "exact": bool(s["exact"])}
            save(native, OUT / f"{stem}-{name}.png", VIEW, True)
        report[stem] = entry
        print(stem, entry["native"], {k: v and v["cells"] for k, v in entry["methods"].items()})
    return report


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"griffith": hero(), "cases": cases()}
    (OUT / "cases.json").write_text(json.dumps(report, indent=1, default=int) + "\n")
    print(json.dumps(report["griffith"]))
