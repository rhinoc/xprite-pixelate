"""Run the benchmark: build the cases, run every method on them, score and summarise.

  python -I bench/xbench/run.py --suite ai --methods xprite,fixer,perfectpixel,proper
  python -I bench/xbench/run.py --suite v1 --limit 40
  python -I bench/xbench/run.py --suite speed --workers 1

Suites:
- ai: the AI suite (suite.py) on bench/corpus. Sprite-only categories skip opaque art.
- v1: pixel-bench suite v1 (vendored, unchanged) on the same corpus, for comparison.
- speed: a size ladder of gen_clean renders (longest side SPEED_SIDES), run with one worker so
  the timings do not compete for cores.

Inputs are cached in bench/.cache/<suite>/, results in bench/results/<suite>/<method>.jsonl
(resumable: delete a file to re-run that method), the summary in bench/results/<suite>/summary.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BENCH / "vendor/pixel-bench"))

import methods as M  # noqa: E402
import score as S  # noqa: E402
import suite as A  # noqa: E402

CORPUS = BENCH / "corpus"
CACHE = BENCH / ".cache"
RESULTS = BENCH / "results"
SPEED_SIDES = (256, 512, 1024, 1448, 2000)  # 2000 x 2000 is pixel-art-fixer's 4 MP limit
SPEED_PITCH = (8.0, 20.0)
SPEED_IMAGES = 12


def corpus(limit: int | None):
    items = json.loads((CORPUS / "manifest.json").read_text())
    if limit and limit < len(items):
        rng = np.random.default_rng(1234)
        items = [items[i] for i in sorted(rng.choice(len(items), limit, replace=False))]
    return items


def _store(key_dir: Path, key: str, case: dict, meta: dict) -> dict:
    key_dir.mkdir(parents=True, exist_ok=True)
    img = case["img"]
    oh, ow = img.shape[:2]
    np.savez_compressed(key_dir / f"{key}.npz", img=img, gt=case["gt"],
                        u=case["U"][oh // 2] if case["U"].ndim == 2 else case["U"],
                        v=case["V"][:, ow // 2] if case["V"].ndim == 2 else case["V"],
                        bg=case.get("background", np.zeros(3, np.uint8)))
    meta = {**meta, "key": key, "width": int(ow), "height": int(oh),
            "megapixels": round(ow * oh / 1e6, 3)}
    (key_dir / f"{key}.json").write_text(json.dumps(meta))
    return meta


def _ai_case(item, category, key_dir):
    key = f"{item['id']}__{category}"
    if (key_dir / f"{key}.json").exists():
        return json.loads((key_dir / f"{key}.json").read_text())
    transparent = "transparent" in item.get("tags", [])
    case = A.build_case(str(CORPUS / item["file"]), item["id"], category, transparent)
    if case is None:
        return None
    return _store(key_dir, key, case, {
        "id": item["id"], "category": category, "genre": item.get("genre"),
        "size_bin": item.get("size_bin"), "palette_bin": item.get("palette_bin"),
        "background": case["spec"].background, "pitch": round(case["spec"].pitch_x, 2)})


def _v1_case(item, category, key_dir):
    from pixelbench.data import load_art
    from pixelbench.distort import damage_native, distort, make_spec
    from pixelbench.distort.suite import _seed
    from pixelbench.runner import MIN_DISTORTED_SIDE, _clamp
    key = f"{item['id']}__{category}"
    if (key_dir / f"{key}.json").exists():
        return json.loads((key_dir / f"{key}.json").read_text())
    name = Path(item["file"]).name
    art = damage_native(category, name, load_art(str(CORPUS / item["file"]),
                                                 np.random.default_rng(_seed(name, "bg"))))
    h, w = art.shape[:2]
    spec = _clamp(w, h, make_spec(category, name, 1.0))
    out = distort(art, spec, np.random.default_rng(spec.seed))
    if min(out["img"].shape[:2]) < MIN_DISTORTED_SIDE:
        return None
    opaque = lambda rgb: np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])  # noqa: E731
    case = {"img": opaque(out["img"]), "gt": opaque(art), "U": out["U"], "V": out["V"]}
    return _store(key_dir, key, case, {
        "id": item["id"], "category": category, "genre": item.get("genre"),
        "size_bin": item.get("size_bin"), "palette_bin": item.get("palette_bin"),
        "background": "opaque"})


def _speed_padded(item):
    transparent = "transparent" in item.get("tags", [])
    native = A.load_native(str(CORPUS / item["file"]), transparent)
    spec = A.make_spec("gen_clean", item["id"])
    spec = spec if transparent else A.replace(spec, fill=1.0)
    return A.pad(native, spec, np.random.default_rng(A.seed(item["id"], "speed", "pad"))), spec


def _speed_case(item, side, key_dir):
    """gen_clean at the pitch that makes the canvas's longest side `side`."""
    key = f"{item['id']}__side{side}"
    if (key_dir / f"{key}.json").exists():
        return json.loads((key_dir / f"{key}.json").read_text())
    art, spec = _speed_padded(item)
    h, w = art.shape[:2]
    pitch = side / max(w, h)
    spec = A.replace(spec, pitch_x=pitch, pitch_y=pitch)
    r = A.render(art, spec, np.random.default_rng(A.seed(item["id"], "speed", "render")))
    return _store(key_dir, key, {**r, "gt": art}, {
        "id": item["id"], "category": f"side{side}", "side": side, "pitch": round(pitch, 2),
        "genre": item.get("genre"), "size_bin": item.get("size_bin"),
        "palette_bin": item.get("palette_bin")})


def build(suite: str, limit: int | None) -> list[dict]:
    key_dir = CACHE / suite
    items = corpus(limit if suite != "speed" else None)
    cases = []
    if suite == "ai":
        for item in items:
            for category in A.category_names():
                cases.append(_ai_case(item, category, key_dir))
    elif suite == "v1":
        from pixelbench.distort import category_names
        for item in items:
            for category in category_names():
                cases.append(_v1_case(item, category, key_dir))
    else:
        # Per size, art whose padded side gives a generator-like pitch, so every size measures
        # the same task.
        rng = np.random.default_rng(7)
        sides = {item["id"]: max(_speed_padded(item)[0].shape[:2]) for item in items}
        for side in SPEED_SIDES:
            fits = [i for i in items if SPEED_PITCH[0] <= side / sides[i["id"]] <= SPEED_PITCH[1]]
            picked = [fits[k] for k in sorted(rng.choice(len(fits), min(SPEED_IMAGES, len(fits)),
                                                         replace=False))]
            cases += [_speed_case(item, side, key_dir) for item in picked]
    return [c for c in cases if c]


_METHOD = None


def _init(name: str):
    global _METHOD
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    try:
        import cv2
        cv2.setNumThreads(1)
    except Exception:
        pass
    _METHOD = M.METHODS[name]()


def _run_case(args):
    suite, case = args
    data = np.load(CACHE / suite / f"{case['key']}.npz")
    img, gt, bg = data["img"], data["gt"], data["bg"]
    background = bg if case.get("background") == "white" else None
    view = img
    if not _METHOD.rgba and (img[:, :, 3] < 255).any():
        view = A.composite(img, bg if background is not None else np.full(3, 255, np.uint8))
    try:
        result = _METHOD.run(np.ascontiguousarray(view))
    except Exception as e:
        result = M.Result(None, 0.0, error=f"{type(e).__name__}: {e}"[:300])
    rgb_background = background
    if not _METHOD.rgba and background is None and (img[:, :, 3] < 255).any():
        rgb_background = np.full(3, 255, np.uint8)
    scores = S.score(gt, result.native, rgb_background, data["u"], data["v"], _METHOD.rgba)
    return {"key": case["key"], "category": case["category"], "id": case["id"],
            "genre": case.get("genre"), "size_bin": case.get("size_bin"),
            "palette_bin": case.get("palette_bin"), "megapixels": case["megapixels"],
            "seconds": round(result.seconds, 4), "refused": result.refused,
            "error": result.error, **{k: (round(v, 5) if isinstance(v, float) else v)
                                      for k, v in scores.items()}}


def run_method(suite: str, name: str, cases: list[dict], workers: int) -> list[dict]:
    out = RESULTS / suite / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["key"]: json.loads(l) for l in out.read_text().splitlines()} \
        if out.exists() else {}
    todo = [c for c in cases if c["key"] not in done]
    started = time.time()
    with out.open("a") as sink, ProcessPoolExecutor(workers, initializer=_init,
                                                    initargs=(name,)) as pool:
        for n, record in enumerate(pool.map(_run_case, [(suite, c) for c in todo], chunksize=1), 1):
            sink.write(json.dumps(record) + "\n")
            sink.flush()
            done[record["key"]] = record
            if n % 50 == 0 or n == len(todo):
                print(f"  {name}: {n}/{len(todo)} {time.time() - started:.0f}s", flush=True)
    keys = {c["key"] for c in cases}
    return [r for k, r in done.items() if k in keys]


def summarise(records: list[dict], group_keys=("category", "size_bin", "palette_bin", "genre")):
    def stats(rows):
        n = len(rows)
        exact = [r for r in rows if r["exact"]]
        mean = lambda key, rs: (float(np.mean([r[key] for r in rs if key in r]))  # noqa: E731
                                if any(key in r for r in rs) else None)
        seconds = sorted(r["seconds"] for r in rows if not r.get("error"))
        return {"n": n, "exact": sum(r["exact"] for r in rows) / n if n else 0,
                "within1": sum(r["within1"] for r in rows) / n if n else 0,
                "grid_align": mean("grid_align", rows), "pixel_match": mean("pixel_match", exact),
                "delta_e": mean("delta_e", exact), "fringe": mean("fringe", exact),
                "refused": sum(bool(r["refused"]) for r in rows),
                "errors": sum(bool(r.get("error")) for r in rows),
                "median_s": seconds[len(seconds) // 2] if seconds else None,
                "p90_s": seconds[int(len(seconds) * 0.9)] if seconds else None}
    out = {"overall": stats(records)}
    for key in group_keys:
        groups = {}
        for r in records:
            groups.setdefault(r.get(key), []).append(r)
        out[key] = {str(g): stats(rows) for g, rows in sorted(groups.items(), key=lambda kv: str(kv[0]))
                    if g is not None}
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--suite", choices=["ai", "v1", "speed"], default="ai")
    p.add_argument("--methods", default="xprite,fixer,perfectpixel,proper")
    p.add_argument("--limit", type=int)
    p.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    cases = build(a.suite, a.limit)
    print(f"{a.suite}: {len(cases)} cases", flush=True)
    summary = {"suite": a.suite, "suite_version": A.SUITE_VERSION if a.suite != "v1" else "v1",
               "cases": len(cases), "workers": a.workers, "methods": {}}
    for name in a.methods.split(","):
        records = run_method(a.suite, name, cases, a.workers)
        summary["methods"][name] = summarise(records)
        o = summary["methods"][name]["overall"]
        print(f"{name:14} exact {o['exact']:.3f} within1 {o['within1']:.3f} "
              f"match {o['pixel_match'] or 0:.3f} fringe {o['fringe'] or 0:.3f} "
              f"median {o['median_s'] or 0:.2f}s errors {o['errors']}", flush=True)
    (RESULTS / a.suite / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
