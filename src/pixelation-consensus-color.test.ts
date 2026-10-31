import { describe, expect, test, vi } from "vitest";

import type { PixelBuffer } from "./base.ts";
import { blockPartition } from "./grid.ts";
import { pixelateImage } from "./pixelate.ts";
import { detectWithAlgorithm } from "./pixelation-algorithm-registry.ts";
import {
  CellColorPicker,
  PixelationAlgorithm,
  PixelationMode,
} from "./types.ts";

vi.mock("./deskew.ts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./deskew.ts")>()),
  estimateTilt: () => ({ angle: 0, extreme: false }),
}));
vi.mock("./grid-ac-rl-consensus.ts", () => ({
  beginAcRlConsensusJob: () => ({}),
  finishAcRlConsensusJob: () => ({ cols: 16, rows: 16 }),
}));
vi.mock("./grid-detect.ts", () => ({
  detectUniformGrid: () => ({ reliable: false }),
  detectMeshGrid: () => ({ reliable: false }),
}));
vi.mock("./grid-frame-lattice.ts", () => ({
  detectFrameLattices: () => [],
}));
vi.mock("./grid-pitch-lattice.ts", () => ({ pitchLattices: () => [] }));
vi.mock("./grid-period-comb.ts", () => ({ combCountGrids: () => [] }));
vi.mock("./grid-period-boundary.ts", () => ({
  detectBoundaryPeriodGrids: () => [],
}));
vi.mock("./grid-period-distance.ts", () => ({
  distanceCountGrids: () => [],
}));
vi.mock("./grid-arbitrate.ts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./grid-arbitrate.ts")>()),
  arbitrateGrids: (source: PixelBuffer) => ({
    grid: {
      ...blockPartition(source, 17, 17),
      confidence: 0.4,
      reliable: true,
      algorithm: PixelationAlgorithm.UniformGrid,
    },
    length: -100,
    score: -100,
  }),
}));

function cleanUpscale(): { art: PixelBuffer; source: PixelBuffer } {
  const size = 16;
  const scale = 6;
  const palette = [
    [0, 0, 0, 255],
    [255, 0, 0, 255],
    [0, 255, 0, 255],
  ];
  const art: PixelBuffer = {
    width: size,
    height: size,
    data: new Uint8ClampedArray(size * size * 4),
  };
  let seed = 12345;
  for (let pixel = 0; pixel < size * size; pixel++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    art.data.set(palette[seed % palette.length], pixel * 4);
  }
  const source: PixelBuffer = {
    width: size * scale,
    height: size * scale,
    data: new Uint8ClampedArray(size * size * scale * scale * 4),
  };
  for (let y = 0; y < source.height; y++)
    for (let x = 0; x < source.width; x++) {
      const from = (Math.floor(y / scale) * size + Math.floor(x / scale)) * 4;
      source.data.set(art.data.subarray(from, from + 4), (y * source.width + x) * 4);
    }
  return { art, source };
}

describe("coloring a dimension-only consensus", () => {
  test("scores and samples the same original-frame lattice without inventing local warps", () => {
    const { art, source } = cleanUpscale();
    const grid = detectWithAlgorithm(source);
    expect([grid.width, grid.height]).toEqual([art.width, art.height]);
    expect(grid.cutsX).toEqual(Array.from({ length: 17 }, (_, index) => index * 6));
    expect(grid.cutsY).toEqual(grid.cutsX);
    expect(grid.sampling).toBeUndefined();
    const restored = pixelateImage(source, {
      grid,
      mode: PixelationMode.RecoverGrid,
      algorithm: PixelationAlgorithm.Auto,
      colorPicker: CellColorPicker.TwoStage,
    });
    expect(restored.data).toEqual(art.data);
  });
});
