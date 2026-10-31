// @cpu-intensive
import { describe, expect, test } from "vitest";

import { mush, sprite } from "./grid-test-images.ts";
import { detectWithAlgorithm } from "./pixelation-algorithm-registry.ts";
import { PixelationAlgorithm } from "./types.ts";
const { Auto } = PixelationAlgorithm;
describe("soft upscales the edge detectors refuse", () => {
  test("a tilt claimed on soft edges does not hide the upright grid", () => {
    const image = mush(sprite(56, 53), 14, 54);
    const result = detectWithAlgorithm(image, Auto);
    expect([result.width, result.height]).toEqual([56, 56]);
    expect(result.rotation).toBeUndefined();
  });
});
