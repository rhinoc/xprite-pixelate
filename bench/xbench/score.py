"""Scores of one recovered image against its ground truth.

The size of a sprite on a clear canvas is read from the sprite, not the canvas: the margin has no
visible grid, so its cell count is not scored. Every score compares the bounding boxes of the
visible art, in cells.

- exact / within1: the recovered art spans exactly (within one cell of) the native columns and rows.
- pixel_match (exact cases): share of native pixels inside the box recovered right: clear stays
  clear, visible becomes visible with every channel within COLOUR_TOLERANCE.
- delta_e (exact cases): mean CIELAB dE76 over the visible native pixels.
- fringe (exact cases, RGBA methods): share of the visible recovered pixels that are partly
  transparent where the native pixel is fully clear or fully opaque (the half-transparent ring).
- grid_align: pixel-bench's F1 of the implied uniform grid lines against the true cuts.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

COLOUR_TOLERANCE = 24
HALF_ALPHA = 128
OPAQUE = 255


def _visible(img: np.ndarray, background: np.ndarray | None) -> np.ndarray:
    if img.shape[2] == 4 and (img[:, :, 3] < HALF_ALPHA).any():
        return img[:, :, 3] >= HALF_ALPHA
    if background is None:
        return np.ones(img.shape[:2], bool)
    return np.abs(img[:, :, :3].astype(int) - background.astype(int)).max(2) > COLOUR_TOLERANCE


def _box(mask: np.ndarray):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _lab(rgb: np.ndarray) -> np.ndarray:
    import cv2
    return cv2.cvtColor(rgb.astype(np.float32) / 255, cv2.COLOR_RGB2Lab)


def _true_cuts(coord_line: np.ndarray) -> np.ndarray:
    f = np.floor(coord_line)
    return np.where(np.abs(np.diff(f)) >= 1)[0].astype(np.float64) + 0.5


def _uniform_cuts(length: int, cells: int) -> np.ndarray:
    return np.arange(1, cells) * (length / cells) if cells > 1 else np.empty(0)


def _f1(true_c: np.ndarray, pred_c: np.ndarray, tol: float) -> float:
    if not len(true_c) and not len(pred_c):
        return 1.0
    if not len(true_c) or not len(pred_c):
        return 0.0
    d = np.abs(true_c[:, None] - pred_c[None, :])
    t_used = np.zeros(len(true_c), bool)
    p_used = np.zeros(len(pred_c), bool)
    matched = 0
    for flat in np.argsort(d, axis=None):
        i, j = divmod(int(flat), len(pred_c))
        if d[i, j] > tol:
            break
        if not t_used[i] and not p_used[j]:
            t_used[i] = p_used[j] = True
            matched += 1
    precision, recall = matched / len(pred_c), matched / len(true_c)
    return 0.0 if not matched else 2 * precision * recall / (precision + recall)


def grid_align(u_row: np.ndarray, v_col: np.ndarray, cols: int, rows: int) -> float:
    ow, oh = len(u_row), len(v_col)
    tol_x = max(1.5, 0.25 * ow / max(cols, 1))
    tol_y = max(1.5, 0.25 * oh / max(rows, 1))
    return 0.5 * (_f1(_true_cuts(u_row), _uniform_cuts(ow, cols), tol_x)
                  + _f1(_true_cuts(v_col), _uniform_cuts(oh, rows), tol_y))


def score(gt: np.ndarray, rec: np.ndarray | None, background: np.ndarray | None,
          u_row: np.ndarray, v_col: np.ndarray, rgba_method: bool) -> dict:
    s = {"exact": 0.0, "within1": 0.0}
    if rec is None:
        return s
    if rec.ndim == 2:
        rec = np.dstack([rec] * 3)
    s["grid_align"] = grid_align(u_row, v_col, rec.shape[1], rec.shape[0])
    gb = _box(gt[:, :, 3] >= HALF_ALPHA)
    rb = _box(_visible(rec, background))
    if gb is None or rb is None:
        return s
    gw, gh = gb[2] - gb[0], gb[3] - gb[1]
    rw, rh = rb[2] - rb[0], rb[3] - rb[1]
    s.update(cols=rw, rows=rh, gt_cols=gw, gt_rows=gh)
    s["exact"] = float(rw == gw and rh == gh)
    s["within1"] = float(abs(rw - gw) <= 1 and abs(rh - gh) <= 1)
    if not s["exact"]:
        return s
    g = gt[gb[1]:gb[3], gb[0]:gb[2]].astype(int)
    r = rec[rb[1]:rb[3], rb[0]:rb[2]].astype(int)
    g_visible = g[:, :, 3] >= HALF_ALPHA
    r_visible = _visible(rec, background)[rb[1]:rb[3], rb[0]:rb[2]]
    colour = np.abs(r[:, :, :3] - g[:, :, :3]).max(2) <= COLOUR_TOLERANCE
    s["pixel_match"] = float(np.where(g_visible, r_visible & colour, ~r_visible).mean())
    if g_visible.any():
        de = np.linalg.norm(_lab(r[:, :, :3][g_visible][None]) - _lab(g[:, :, :3][g_visible][None]),
                            axis=-1)
        s["delta_e"] = float(de.mean())
    if rgba_method and r.shape[2] == 4:
        partial = (r[:, :, 3] > 0) & (r[:, :, 3] < OPAQUE)
        native_binary = (g[:, :, 3] == 0) | (g[:, :, 3] == OPAQUE)
        shown = max(1, int((r[:, :, 3] > 0).sum()))
        s["fringe"] = float((partial & native_binary).sum() / shown)
    return s


def save_png(path, rgba: np.ndarray) -> None:
    Image.fromarray(rgba).save(path, optimize=True)
