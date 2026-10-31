"""README figures: a real generated image (docs/griffith-input.png) with every tool's result, and
generated-style inputs built from the CC0 corpus with their recovered mesh and art.

  bench/.venv/bin/python -I bench/tools/readme_figures.py

Needs `pnpm run build` first. Writes docs/images/.
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
import suite as A  # noqa: E402

OUT = ROOT / "docs/images"
DETECT = ROOT / "bench/tools/readme-detect.mjs"
VIEW = 320  # display height of every tile, px
CHECKER = 12
LIGHT, DARK = (252, 252, 251), (232, 231, 226)
MESH = (235, 0, 140, 255)
EXAMPLES = [
    ("luizmelo-goblin-idle-f0", "gen_pair", "goblins"),
    ("dcss-naga-mage", "gen_painterly", "naga"),
    ("denzi-monster-r04c01", "gen_wobble", "wobble"),
    ("ansimuz-gothic-oldman", "gen_small_pitch", "oldman"),
]


def case(image_id, category):
    rec = {r["id"]: r for r in json.load(open(ROOT / "bench/corpus/manifest.json"))}[image_id]
    return A.build_case(str(ROOT / "bench/corpus" / rec["file"]), image_id, category,
                        "transparent" in rec["tags"])


def recover(img):
    h, w = img.shape[:2]
    with tempfile.TemporaryDirectory() as t:
        Path(t, "in").write_bytes(np.ascontiguousarray(img).tobytes())
        grid = json.loads(subprocess.check_output(
            ["node", str(DETECT), f"{t}/in", str(w), str(h), f"{t}/out"], cwd=ROOT))
        art = np.frombuffer(Path(t, "out").read_bytes(), np.uint8)
    return grid, art.reshape(grid["outHeight"], grid["outWidth"], 4)


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


def mesh(img, grid):
    h = img.shape[0]
    k = VIEW / h
    view = on_checker(scaled(img, VIEW, False))
    draw = ImageDraw.Draw(view)
    for x in cuts(grid, "x"):
        draw.line([(x * k, 0), (x * k, VIEW)], fill=MESH, width=1)
    for y in cuts(grid, "y"):
        draw.line([(0, y * k), (view.width, y * k)], fill=MESH, width=1)
    return view


def examples():
    for image_id, category, name in EXAMPLES:
        c = case(image_id, category)
        grid, art = recover(c["img"])
        on_checker(scaled(c["img"], VIEW, False)).save(OUT / f"{name}-input.png", optimize=True)
        mesh(c["img"], grid).save(OUT / f"{name}-mesh.png", optimize=True)
        on_checker(scaled(art, VIEW, True)).save(OUT / f"{name}-result.png", optimize=True)
        gt = c["gt"]
        print(name, c["img"].shape[1], c["img"].shape[0], "->", art.shape[1], art.shape[0],
              "native", gt.shape[1], gt.shape[0])


def hero():
    """The real generated image: input, recovered mesh, result, and every tool's result."""
    img = np.asarray(Image.open(ROOT / "docs/griffith-input.png").convert("RGBA"))
    grid, art = recover(img)
    on_checker(scaled(img, VIEW, False)).save(OUT / "griffith-input.png", optimize=True)
    mesh(img, grid).save(OUT / "griffith-mesh.png", optimize=True)
    on_checker(scaled(art, VIEW, True)).save(OUT / "griffith-result.png", optimize=True)
    report = {"xprite": f"{art.shape[1]}x{art.shape[0]}"}
    for name, cls in M.METHODS.items():
        if name == "xprite":
            continue
        method = cls()
        view = img if method.rgba else A.composite(img, np.full(3, 255, np.uint8))
        r = method.run(np.ascontiguousarray(view))
        method.close()
        if r.native is None:
            report[name] = "refused" if r.refused else r.error
            continue
        native = r.native if r.native.shape[2] == 4 else np.dstack(
            [r.native, np.full(r.native.shape[:2], 255, np.uint8)])
        report[name] = f"{native.shape[1]}x{native.shape[0]}"
        on_checker(scaled(native, VIEW, True)).save(OUT / f"griffith-{name}.png", optimize=True)
    print("griffith", img.shape[1], img.shape[0], report)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    hero()
    examples()
