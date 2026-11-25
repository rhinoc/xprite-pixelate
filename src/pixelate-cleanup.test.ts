import { describe, expect, test } from "vitest";

import type { PixelBuffer, Rgba } from "./base.ts";
import {
  pixelateImage,
  pixelateImageAsync,
  PixelationDither,
  PixelationMethod,
  PixelationMode,
  removeOrphanPixels,
  settlePixelAlpha,
} from "./index.ts";

const CLEAR: Rgba = [0, 0, 0, 0];
const BLACK: Rgba = [0, 0, 0, 255];
const WHITE: Rgba = [255, 255, 255, 255];
const RED: Rgba = [240, 0, 0, 255];
const DARK_RED: Rgba = [80, 0, 0, 255];
const GRAY: Rgba = [200, 200, 200, 255];
const COLORS: Readonly<Record<string, Rgba>> = {
  ".": CLEAR, k: BLACK, w: WHITE, r: RED, d: DARK_RED,
};

function fixture(width: number, height: number, color: (x: number, y: number) => Rgba): PixelBuffer {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) data.set(color(x, y), (y * width + x) * 4);
  return { width, height, data };
}

function rows(...lines: string[]): PixelBuffer {
  return fixture(lines[0].length, lines.length, (x, y) => COLORS[lines[y][x]]);
}

function pixel(image: PixelBuffer, x: number, y: number): number[] {
  const offset = (y * image.width + x) * 4;
  return [...image.data.subarray(offset, offset + 4)];
}

describe("removeOrphanPixels", () => {
  test("clears floating pixels, including diagonal-only contacts, without wrapping rows", () => {
    const source = rows("...r", "w...", ".r..", "...r", "...r");
    const original = source.data.slice();
    expect(removeOrphanPixels(source)).toEqual(rows("....", "....", "....", "...r", "...r"));
    expect(source.data).toEqual(original);
  });

  test("keeps a one-pixel canvas and pixels supported by translucent art", () => {
    const dot = rows("r");
    const glass = fixture(3, 1, (x) => (x === 0 ? RED : x === 1 ? [0, 0, 0, 100] : CLEAR));
    expect(removeOrphanPixels(dot)).toEqual(dot);
    expect(removeOrphanPixels(glass)).toEqual(glass);
  });

  test("copies the strict neighborhood majority without introducing a color", () => {
    const source = rows("kkk", "wrk", "wwk");
    const cleaned = removeOrphanPixels(source);
    expect(cleaned).toEqual(rows("kkk", "wkk", "wwk"));
    expect(pixel(source, 1, 1)).toEqual(RED);
    expect(removeOrphanPixels(source, { absorbInterior: false })).toEqual(source);
  });

  test("preserves tied neighborhoods, diagonal strokes, and one-pixel corners", () => {
    const tie = rows("kkw", "krw", "wkw");
    const diagonal = rows("rkkkk", "krkkk", "kkrkk", "kkkrk", "kkkkr");
    const corner = rows(".....", ".www.", "...w.", "...w.", ".....");
    for (const art of [tie, diagonal, corner]) expect(removeOrphanPixels(art)).toEqual(art);
  });
});

describe("removeNoise pixelation", () => {
  test("absorbs strays without a palette and retains continuous smoothing", async () => {
    const source = rows("kkk", "kwk", "kkk");
    const expected = rows("kkk", "kkk", "kkk");
    expect(pixelateImage(source, { removeNoise: true })).toEqual(expected);
    expect(await pixelateImageAsync(source, { removeNoise: true })).toEqual(expected);

    const near = fixture(2, 1, (x) => (x === 0 ? [24, 24, 24, 255] : BLACK));
    expect(pixel(pixelateImage(near, { removeNoise: true }), 0, 0)).toEqual([21, 21, 21, 255]);
  });

  test.each([undefined, PixelationDither.None])(
    "absorbs a stray after palette snapping (%s)",
    async (dither) => {
      const source = rows("kdk", "dwd", "kdk");
      const expected = rows("kkk", "kkk", "kkk");
      const options = { removeNoise: true, paletteSnap: { palette: [BLACK, WHITE], dither } };
      expect(pixelateImage(source, { removeNoise: true })).toEqual(source);
      expect(pixelateImage(source, options)).toEqual(expected);
      expect(await pixelateImageAsync(source, options)).toEqual(expected);
    },
  );

  test.each([PixelationDither.Ordered, PixelationDither.FloydSteinberg])(
    "preserves %s dots and clears floating pixels",
    async (dither) => {
      const source = fixture(18, 16, (x, y) =>
        x < 16 ? GRAY : x === 17 && y === 8 ? WHITE : CLEAR,
      );
      const paletteSnap = { palette: [BLACK, WHITE], dither };
      const dithered = pixelateImage(source, { paletteSnap });
      const expected = { ...dithered, data: dithered.data.slice() };
      expected.data.set(CLEAR, (8 * source.width + 17) * 4);
      expect(pixel(dithered, 17, 8)).toEqual(WHITE);
      expect(removeOrphanPixels(dithered)).not.toEqual(expected);
      expect(pixelateImage(source, { paletteSnap, removeNoise: true })).toEqual(expected);
      expect(await pixelateImageAsync(source, { paletteSnap, removeNoise: true })).toEqual(expected);
    },
  );
});

describe("plain Convert alpha", () => {
  const sprite = fixture(24, 4, (x) => {
    const alpha = x < 5 ? [0, 0, 40, 0, 160][x] : x < 22 ? 252 : 0;
    return [160, 80, 40, alpha];
  });

  test.each(Object.values(PixelationMethod))(
    "settles a soft opaque sprite with %s",
    async (method) => {
      const options = { mode: PixelationMode.Convert, method, targetWidth: 12, targetHeight: 2 };
      const out = pixelateImage(sprite, options);
      expect(pixel(out, 1, 0)).toEqual(CLEAR);
      expect(pixel(out, 2, 0)).toEqual([160, 80, 40, 255]);
      expect(pixel(out, 9, 0)).toEqual([160, 80, 40, 255]);
      expect(await pixelateImageAsync(sprite, options)).toEqual(out);
    },
  );

  test.each([PixelationMethod.Box, PixelationMethod.Dominant, PixelationMethod.Structure])(
    "preserves glass, shadows, and faint glow with %s",
    (method) => {
      const alphas = [0, 255, 180, 84, 12, 0];
      const art = fixture(12, 4, (x) => [160, 80, 40, alphas[Math.floor(x / 2)]]);
      const glow = fixture(12, 4, (x) => [160, 80, 40, x < 6 ? 0 : 12]);
      const options = { mode: PixelationMode.Convert, method, targetWidth: 6, targetHeight: 2 };
      const out = pixelateImage(art, options);
      expect(alphas.map((_, x) => pixel(out, x, 0)[3])).toEqual(alphas);
      expect(pixel(pixelateImage(glow, options), 4, 0)[3]).toBe(12);
    },
  );

  test("keeps coverage from hard source alpha and leaves opaque and even translucent art intact", () => {
    const hard = rows("kk..", "kkkk");
    const opaque = rows("kw", "wk");
    const translucent = fixture(2, 2, () => [40, 80, 120, 240]);
    const options = {
      mode: PixelationMode.Convert,
      method: PixelationMethod.Box,
      targetSize: { width: 1, height: 1 },
    };
    expect(pixel(pixelateImage(hard, options), 0, 0)).toEqual([0, 0, 0, 191]);
    expect(pixel(pixelateImage(opaque, options), 0, 0)).toEqual([128, 128, 128, 255]);
    expect(pixel(pixelateImage(translucent, options), 0, 0)).toEqual([40, 80, 120, 240]);
  });

  test("settles alpha on an existing grid without modifying the source", () => {
    const original = sprite.data.slice();
    const settled = settlePixelAlpha(sprite);
    expect([settled.width, settled.height]).toEqual([sprite.width, sprite.height]);
    expect(pixel(settled, 2, 0)).toEqual(CLEAR);
    expect(pixel(settled, 4, 0)).toEqual([160, 80, 40, 255]);
    expect(sprite.data).toEqual(original);
  });
});
