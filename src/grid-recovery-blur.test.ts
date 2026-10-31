// @cpu-intensive
import { describe, expect, test } from "vitest";

import { boxBlur, sprite, upscaleNearest } from "./grid-test-images.ts";
import { pixelateImage } from "./pixelate.ts";
import { detectWithAlgorithm } from "./pixelation-algorithm-registry.ts";
import { PixelationAlgorithm, PixelationMode } from "./types.ts";
describe("soft upscales the edge detectors refuse", () => {
  test("heavily blurred sprite", () => {
    const image = boxBlur(upscaleNearest(sprite(64), 16), 6);
    for (const algorithm of [PixelationAlgorithm.EdgeGrid, PixelationAlgorithm.UniformGrid])
      expect(detectWithAlgorithm(image, algorithm).reliable).toBe(false);
    const grid = detectWithAlgorithm(image, PixelationAlgorithm.Auto);
    expect(grid.reliable).toBe(true);
    expect(grid.cellWidth).toBeCloseTo(16, 0);
    expect(grid.cellHeight).toBeCloseTo(16, 0);
    expect(Math.abs(grid.width - 64)).toBeLessThanOrEqual(1);
    expect(Math.abs(grid.height - 64)).toBeLessThanOrEqual(1);
    const out = pixelateImage(image, {
      algorithm: PixelationAlgorithm.Auto,
      mode: PixelationMode.RecoverGrid,
      grid,
    });
    expect([out.width, out.height]).toEqual([grid.width, grid.height]);
  });
});
