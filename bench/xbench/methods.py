"""The recovery methods the benchmark compares. Each takes the input RGBA image (H x W x 4 uint8)
and returns a Result with the recovered native image and the time it took.

- xprite: @xprite/pixelate (this repository), Auto grid detection then grid recovery, through a
  persistent Node worker (bench/xprite-worker.mjs) on the built package in dist/.
- fixer: Retro Diffusion's pixel-art-fixer, the native Rust CLI (`process <in> <out> full`).
- perfectpixel: theamusing/perfectPixel, `get_perfect_pixel` (RGB only).
- proper: KennethJAllen/proper-pixel-art, `proper_pixel_art.image.pixelate` (RGBA).

Methods that read RGB only get the input composited over the case's background, the way the
picture looks to the person who runs them.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import selectors
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

BENCH = Path(__file__).resolve().parent.parent
FIXER_CLI = BENCH / "vendor/pixel-art-fixer/rust/target/release/pixelfixer"
XPRITE_WORKER = BENCH / "xprite-worker.mjs"
TIMEOUT_S = 180


@dataclass
class Result:
    native: np.ndarray | None      # recovered art, uint8 H x W x 3 or 4
    seconds: float
    refused: bool = False
    error: str | None = None


class Method:
    name = ""
    label = ""
    rgba = True                    # reads and writes alpha

    def run(self, image: np.ndarray) -> Result:
        raise NotImplementedError

    def close(self) -> None:
        pass


class Xprite(Method):
    name, label = "xprite", "Xprite Auto"

    def __init__(self) -> None:
        self.proc = None
        self.tmp = tempfile.TemporaryDirectory(prefix="xbench-xprite-")

    def _start(self) -> None:
        self.proc = subprocess.Popen(["node", str(XPRITE_WORKER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1, cwd=BENCH.parent)
        ready = self._read()
        if not ready.get("ready"):
            raise RuntimeError(ready)

    def _read(self) -> dict:
        with selectors.DefaultSelector() as sel:
            sel.register(self.proc.stdout, selectors.EVENT_READ)
            if not sel.select(TIMEOUT_S):
                self.proc.kill()
                self.proc = None
                raise TimeoutError("timeout")
        line = self.proc.stdout.readline()
        if not line:
            self.proc = None
            raise RuntimeError("worker exited")
        return json.loads(line)

    def run(self, image):
        if self.proc is None:
            self._start()
        h, w = image.shape[:2]
        src, dst = Path(self.tmp.name, "in.rgba"), Path(self.tmp.name, "out.rgba")
        src.write_bytes(np.ascontiguousarray(image).tobytes())
        try:
            self.proc.stdin.write(json.dumps({"in": str(src), "out": str(dst),
                                              "width": w, "height": h}) + "\n")
            self.proc.stdin.flush()
            reply = self._read()
        except Exception as e:  # a hung or crashed worker restarts on the next case
            if self.proc:
                self.proc.kill()
            self.proc = None
            return Result(None, TIMEOUT_S, error=str(e))
        seconds = (reply.get("detectMs", 0) + reply.get("recoverMs", 0)) / 1000
        if not reply.get("ok"):
            return Result(None, seconds, error=reply.get("error"))
        if reply.get("refused"):
            return Result(None, seconds, refused=True)
        out = np.frombuffer(dst.read_bytes(), np.uint8).reshape(reply["height"], reply["width"], 4)
        return Result(out.copy(), seconds)

    def close(self):
        if self.proc:
            with contextlib.suppress(Exception):
                self.proc.stdin.write('{"cmd":"quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=10)
        self.tmp.cleanup()


class Fixer(Method):
    name, label = "fixer", "pixel-art-fixer"

    def run(self, image):
        with tempfile.TemporaryDirectory(prefix="xbench-fixer-") as d:
            src, dst = os.path.join(d, "in.png"), os.path.join(d, "out.png")
            Image.fromarray(image, "RGBA").save(src, compress_level=1)
            started = time.perf_counter()
            try:
                done = subprocess.run([str(FIXER_CLI), "process", src, dst, "full"],
                                      capture_output=True, text=True, timeout=TIMEOUT_S)
            except subprocess.TimeoutExpired:
                return Result(None, TIMEOUT_S, error="timeout")
            wall = time.perf_counter() - started
            lines = done.stdout.strip().splitlines()
            if done.returncode or not lines or not os.path.exists(dst):
                return Result(None, wall, error=(done.stderr or done.stdout)[-300:])
            meta = json.loads(lines[-1])
            out = np.asarray(Image.open(dst).convert("RGBA"))
        # The CLI's own detect + reconstruct time, without PNG decode/encode and process start.
        return Result(out, meta.get("detect_s", 0) + meta.get("recon_s", 0))


class PerfectPixel(Method):
    name, label, rgba = "perfectpixel", "perfectPixel", False

    def run(self, image):
        from perfect_pixel import get_perfect_pixel
        rgb = np.ascontiguousarray(image[:, :, :3])
        sink = io.StringIO()
        started = time.perf_counter()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            w, h, out = get_perfect_pixel(rgb)
        seconds = time.perf_counter() - started
        if w is None or h is None or out is None:
            return Result(None, seconds, refused=True)
        out = np.asarray(out)
        if out.dtype != np.uint8:
            out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
        return Result(out[:, :, :3], seconds)


class Proper(Method):
    name, label = "proper", "proper-pixel-art"

    def run(self, image):
        from proper_pixel_art.image import pixelate
        pil = Image.fromarray(image, "RGBA")
        started = time.perf_counter()
        result = pixelate(pil)
        seconds = time.perf_counter() - started
        return Result(np.asarray(result.image.convert("RGBA")), seconds)


METHODS = {m.name: m for m in (Xprite, Fixer, PerfectPixel, Proper)}
