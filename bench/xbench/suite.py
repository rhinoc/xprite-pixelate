"""The AI suite: native 1x pixel art rendered the way image generators emit "pixel art".

pixel-bench (https://github.com/Retro-Diffusion/pixel-bench) composites transparency onto a flat
colour and fills the frame with the art at 2-8x. Generated sprites look different:

- a transparent background, or an off-white one, with a soft, partly transparent outline;
- the sprite fills only part of a large canvas (wide margins), sometimes two sprites side by side;
- the pseudo-pixel pitch is 4-20 output px and not an integer;
- the cell size wanders across the image (drift) and the cuts jitter by a pixel or two;
- cells are nearly flat inside, with a little noise and sometimes painterly shading;
- the opaque alpha is 250-254, not 255, and soft shadows stay translucent;
- the file is often WebP or JPEG compressed.

Every case is a deterministic function of (image id, category, SUITE_VERSION). The native art is
padded with whole transparent cells first, so the ground truth is one native canvas whose grid
covers the whole output image, and the exact source coordinates (U, V) of every output pixel are
kept for grid-alignment scoring.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image

SUITE_VERSION = "ai-v1"
MAX_CANVAS_SIDE = 1800
MIN_PITCH = 4.0
HALF_ALPHA = 128
OPAQUE = 255


@dataclass
class Spec:
    pitch_x: float
    pitch_y: float
    fill: float             # share of the canvas side the art spans (1 = no margin)
    drift: float            # cell-size drift, share of a cell
    jitter: float           # per-cut jitter, share of a cell
    edge_soft: float        # alpha edge blur sigma, output px
    colour_soft: float      # colour blur sigma, output px
    cell_noise: float       # per-pixel noise sigma (0-255)
    cell_shade: float       # per-cell gradient amplitude (0-255)
    halo: float             # sharpening ring strength at colour edges
    opaque_alpha: int       # alpha of fully covered pixels
    codec: str              # none | webp | jpeg
    quality: int
    background: str = "clear"   # clear | white
    pair: bool = False      # two sprites side by side
    shadow: bool = False    # translucent drop shadow under the sprite
    name: str = ""


def seed(image_id: str, category: str, salt: str) -> int:
    digest = hashlib.sha256(f"{SUITE_VERSION}|{category}|{salt}|{image_id}".encode()).hexdigest()
    return int(digest[:8], 16)


def _base(rng) -> dict:
    return dict(
        pitch_x=float(rng.uniform(8, 20)), fill=float(rng.uniform(0.55, 0.75)),
        drift=0.0, jitter=0.0, edge_soft=0.6, colour_soft=0.4, cell_noise=1.5,
        cell_shade=0.0, halo=0.0, opaque_alpha=int(rng.integers(250, 255)),
        codec="none", quality=90,
    )


def _spec(rng, **overrides) -> Spec:
    d = _base(rng)
    aspect = float(rng.uniform(0.97, 1.05))
    d.update(overrides)
    d["pitch_y"] = d["pitch_x"] * aspect
    return Spec(**d)


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    build: object
    sprites_only: bool = False   # needs a transparent background in the native art


CATEGORIES = [
    Category("gen_clean", "Soft alpha edge, near-flat cells, large pitch.",
             lambda r: _spec(r)),
    Category("gen_sparse", "The sprite spans 20-35% of a large clear canvas.",
             lambda r: _spec(r, fill=float(r.uniform(0.2, 0.35))), True),
    Category("gen_white", "Off-white opaque background instead of transparency, light noise.",
             lambda r: _spec(r, background="white", cell_noise=2.0), True),
    Category("gen_soft_edge", "A 3-5 px partly transparent outline and opaque alpha 250-254.",
             lambda r: _spec(r, edge_soft=float(r.uniform(1.5, 2.5))), True),
    Category("gen_webp", "Drift, small cut jitter, noise, WebP.",
             lambda r: _spec(r, drift=0.03, jitter=0.06, cell_noise=2.5, codec="webp",
                             quality=int(r.integers(70, 90)))),
    Category("gen_halo_jpeg", "Sharpening halos and JPEG colour damage.",
             lambda r: _spec(r, halo=0.6, drift=0.02, codec="jpeg",
                             quality=int(r.integers(65, 85)))),
    Category("gen_painterly", "Painterly shading inside cells, as diffusion models paint them.",
             lambda r: _spec(r, drift=0.03, cell_shade=18, cell_noise=3, colour_soft=0.6)),
    Category("gen_small_pitch", "Pitch 4-8 px: low-resolution generations and downsized posts.",
             lambda r: _spec(r, pitch_x=float(r.uniform(4, 8)), edge_soft=0.5, drift=0.03,
                             jitter=0.05, codec="webp", quality=80)),
    Category("gen_large_pitch", "Pitch 24-48 px: a small sprite drawn across a large canvas.",
             lambda r: _spec(r, pitch_x=float(r.uniform(24, 48)), edge_soft=1.0, colour_soft=0.6,
                             codec="webp", quality=85)),
    Category("gen_wobble", "Strong drift and jitter: the grid wanders like a melted render.",
             lambda r: _spec(r, drift=0.08, jitter=0.12, cell_noise=2.5, colour_soft=0.7)),
    Category("gen_pair", "Two sprites side by side on one clear canvas.",
             lambda r: _spec(r, pair=True, fill=float(r.uniform(0.7, 0.85))), True),
    Category("gen_shadow", "A translucent drop shadow under the sprite (alpha 60-110).",
             lambda r: _spec(r, shadow=True), True),
]
BY_NAME = {c.name: c for c in CATEGORIES}


def category_names() -> list[str]:
    return [c.name for c in CATEGORIES]


def make_spec(category: str, image_id: str) -> Spec:
    rng = np.random.default_rng(seed(image_id, category, "params"))
    spec = BY_NAME[category].build(rng)
    spec.name = category
    return spec


def load_native(path: str, transparent: bool) -> np.ndarray:
    """Native art as RGBA. Sprites keep their alpha, binarised unless it is deliberate
    (translucent pixels of a sprite stay as they are); opaque art (tiles, scenes) stays opaque."""
    a = np.asarray(Image.open(path).convert("RGBA")).copy()
    if not transparent:
        a[:, :, 3] = OPAQUE
    a[a[:, :, 3] == 0, :3] = 0
    return a


def _mirror_pair(art: np.ndarray, rng) -> np.ndarray:
    h, w = art.shape[:2]
    gap = max(1, int(round(w * rng.uniform(0.15, 0.4))))
    out = np.zeros((h, 2 * w + gap, 4), np.uint8)
    out[:, :w] = art
    out[:, w + gap:] = art[:, ::-1]
    return out


def _with_shadow(art: np.ndarray, rng) -> np.ndarray:
    """A flat translucent ellipse below the sprite's feet, drawn behind it."""
    h, w = art.shape[:2]
    rows = max(2, int(round(h * 0.12)))
    out = np.zeros((h + rows, w, 4), np.uint8)
    out[:h] = art
    cy, cx = h + rows / 2 - 1, w / 2
    ry, rx = rows * 0.9, w * rng.uniform(0.3, 0.45)
    yy, xx = np.mgrid[0:h + rows, 0:w]
    inside = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1
    alpha = int(rng.integers(60, 111))
    behind = inside & (out[:, :, 3] == 0)
    out[behind] = [0, 0, 0, alpha]
    return out


def pad(art: np.ndarray, spec: Spec, rng) -> np.ndarray:
    """The native art inside a clear margin of whole cells: the canvas a generator draws its sprite
    on, whose grid covers the whole image. This is the ground truth."""
    if spec.pair:
        art = _mirror_pair(art, rng)
    if spec.shadow:
        art = _with_shadow(art, rng)
    h, w = art.shape[:2]
    extra_x = max(0, int(round(w / spec.fill)) - w)
    extra_y = max(0, int(round(h / spec.fill)) - h)
    left = int(round(rng.uniform(0.3, 0.7) * extra_x))
    top = int(round(rng.uniform(0.3, 0.7) * extra_y))
    out = np.zeros((h + extra_y, w + extra_x, 4), np.uint8)
    out[top:top + h, left:left + w] = art
    return out


def fit(spec: Spec, w: int, h: int) -> Spec | None:
    """Shrink the pitch so the canvas stays at generator sizes; None when too small."""
    scale = min(1.0, MAX_CANVAS_SIDE / (w * spec.pitch_x), MAX_CANVAS_SIDE / (h * spec.pitch_y))
    spec = replace(spec, pitch_x=spec.pitch_x * scale, pitch_y=spec.pitch_y * scale)
    return spec if min(spec.pitch_x, spec.pitch_y) >= MIN_PITCH else None


def _cuts(n: int, length: float, drift: float, jitter: float, rng) -> np.ndarray:
    base = length / n
    t = np.arange(n) / max(n - 1, 1)
    ph = rng.uniform(0, 2 * np.pi, 2)
    sizes = base * (1 + drift * (0.7 * np.sin(2 * np.pi * 1.1 * t + ph[0])
                                 + 0.3 * np.sin(2 * np.pi * 2.7 * t + ph[1])))
    cuts = np.concatenate([[0.0], np.cumsum(sizes)])
    cuts *= length / cuts[-1]
    if jitter > 0:
        inner = cuts[1:-1] + rng.uniform(-jitter, jitter, n - 1) * base
        cuts[1:-1] = np.maximum.accumulate(np.clip(inner, 0, length))
    return cuts


def _coords(cuts: np.ndarray, size: int) -> np.ndarray:
    """Continuous native coordinate of each output pixel centre."""
    x = np.arange(size) + 0.5
    i = np.clip(np.searchsorted(cuts, x, side="right") - 1, 0, len(cuts) - 2)
    return (i + (x - cuts[i]) / np.maximum(cuts[i + 1] - cuts[i], 1e-9)).astype(np.float32)


def _gauss(img: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return img
    import cv2
    return cv2.GaussianBlur(img, (0, 0), sigmaX=sigma, sigmaY=sigma,
                            borderType=cv2.BORDER_REPLICATE)


def white_of(image_id: str, category: str) -> np.ndarray:
    """The off-white background of a gen_white case (and of RGB-only methods' input)."""
    rng = np.random.default_rng(seed(image_id, category, "white"))
    return rng.integers(236, 256, 3).astype(np.uint8)


def composite(rgba: np.ndarray, background: np.ndarray) -> np.ndarray:
    alpha = rgba[:, :, 3:4].astype(np.float32) / OPAQUE
    rgb = rgba[:, :, :3].astype(np.float32) * alpha + background.astype(np.float32) * (1 - alpha)
    return np.dstack([np.clip(np.rint(rgb), 0, 255).astype(np.uint8),
                      np.full(rgba.shape[:2], OPAQUE, np.uint8)])


def render(art: np.ndarray, spec: Spec, rng, background: np.ndarray | None = None) -> dict:
    """art: padded native RGBA uint8. Returns the fake RGBA image and its coordinate maps."""
    h, w = art.shape[:2]
    cw, ch = int(round(w * spec.pitch_x)), int(round(h * spec.pitch_y))
    cx = _cuts(w, cw, spec.drift, spec.jitter, rng)
    cy = _cuts(h, ch, spec.drift, spec.jitter, rng)
    U, V = _coords(cx, cw), _coords(cy, ch)
    iu = np.clip(np.floor(U).astype(int), 0, w - 1)
    iv = np.clip(np.floor(V).astype(int), 0, h - 1)
    img = art.astype(np.float32)[np.ix_(iv, iu)]
    alpha = img[:, :, 3] / OPAQUE
    rgb = img[:, :, :3]
    if spec.cell_shade > 0:
        gx = rng.uniform(-1, 1, (h, w)).astype(np.float32)
        gy = rng.uniform(-1, 1, (h, w)).astype(np.float32)
        fu = U - np.floor(U) - 0.5
        fv = V - np.floor(V) - 0.5
        ramp = gx[np.ix_(iv, iu)] * fu[None, :] + gy[np.ix_(iv, iu)] * fv[:, None]
        rgb = rgb + spec.cell_shade * ramp[:, :, None]
    if spec.halo > 0:
        lum = rgb.mean(2)
        rgb = rgb + spec.halo * (lum - _gauss(lum, 1.5))[:, :, None]
    # Colour blur over premultiplied RGB, then a softer alpha edge.
    pre = _gauss(rgb * alpha[:, :, None], spec.colour_soft)
    soft_alpha = _gauss(alpha.astype(np.float32), spec.edge_soft)
    a_for_rgb = _gauss(alpha.astype(np.float32), spec.colour_soft)
    with np.errstate(invalid="ignore", divide="ignore"):
        rgb = np.where(a_for_rgb[:, :, None] > 1e-3, pre / a_for_rgb[:, :, None], 0)
    if spec.cell_noise > 0:
        rgb = rgb + rng.normal(0, spec.cell_noise, rgb.shape).astype(np.float32)
    # Translucent native pixels (shadows) keep their own alpha; covered ones sit just below 255.
    out_alpha = np.clip(soft_alpha * spec.opaque_alpha, 0, OPAQUE)
    out_alpha[out_alpha < 1] = 0
    out = np.dstack([np.clip(rgb, 0, 255), out_alpha]).astype(np.uint8)
    out[out[:, :, 3] == 0, :3] = 0
    if spec.background == "white":
        out = composite(out, background)
        out[:, :, :3] = np.clip(out[:, :, :3].astype(np.float32)
                                + rng.normal(0, spec.cell_noise, out[:, :, :3].shape), 0, 255)
    if spec.codec != "none":
        out = _encode(out, spec.codec, spec.quality)
    return {"img": out, "U": U, "V": V}


def _encode(rgba: np.ndarray, codec: str, quality: int) -> np.ndarray:
    buf = io.BytesIO()
    if codec == "webp":
        Image.fromarray(rgba, "RGBA").save(buf, "WEBP", quality=quality, alpha_quality=100)
        buf.seek(0)
        return np.asarray(Image.open(buf).convert("RGBA"))
    # JPEG colour, alpha kept losslessly: a PNG export of a JPEG-damaged render.
    Image.fromarray(rgba[:, :, :3]).save(buf, "JPEG", quality=quality)
    buf.seek(0)
    damaged = np.asarray(Image.open(buf).convert("RGB"))
    return np.dstack([damaged, rgba[:, :, 3]])


def build_case(path: str, image_id: str, category: str, transparent: bool) -> dict | None:
    """One case: the input image, its ground truth and its coordinate maps; None when the
    category does not apply to the art or the canvas would be too small."""
    if BY_NAME[category].sprites_only and not transparent:
        return None
    spec = make_spec(category, image_id)
    native = load_native(path, transparent)
    if not transparent:
        spec = replace(spec, fill=1.0)
    art = pad(native, spec, np.random.default_rng(seed(image_id, category, "pad")))
    h, w = art.shape[:2]
    spec = fit(spec, w, h)
    if spec is None:
        return None
    white = white_of(image_id, category)
    r = render(art, spec, np.random.default_rng(seed(image_id, category, "render")), white)
    # The ground truth keeps its alpha on every background: scores read the visible art from it.
    return {"img": r["img"], "U": r["U"], "V": r["V"], "gt": art, "spec": spec,
            "background": white}
