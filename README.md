# @xprite/pixelate

[![npm](https://img.shields.io/npm/v/@xprite/pixelate)](https://www.npmjs.com/package/@xprite/pixelate)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

English | [简体中文](https://github.com/rhinoc/xprite-pixelate/blob/main/README.zh-CN.md)

Recover the real pixel grid of AI-generated pixel art and get back one clean pixel per cell. It
also turns ordinary images into pixel art. It runs in browsers and Node, has no runtime
dependencies, and is the importer of the [Xprite](https://xprite.cc) pixel editor.

## Compared with other tools

A real generated image (887×887, cells 15 to 21 px wide), recovered by each tool with its default
settings. Xprite puts each cut on a colour edge, so it does not cut through the eye, the boots or
the sword.

| Recovered grid | Xprite, 48×49 | [pixel-art-fixer](https://github.com/Retro-Diffusion/pixel-art-fixer), 47×48 | [perfectPixel](https://github.com/theamusing/perfectPixel), 50×50 | [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art), 53×54 |
| :---: | :---: | :---: | :---: | :---: |
| ![Grid](docs/images/griffith-mesh.png) | ![Xprite](docs/images/griffith-xprite.png) | ![pixel-art-fixer](docs/images/griffith-fixer.png) | ![perfectPixel](docs/images/griffith-perfectpixel.png) | ![proper-pixel-art](docs/images/griffith-proper.png) |

On the AI suite of [our benchmark](#benchmark) (1746 cases), Xprite gets the exact size most
often:

| Method | Exact size | Within 1 cell | Pixel match | Half-transparent fringe | Median time |
| --- | --- | --- | --- | --- | --- |
| Xprite Auto | **83.6%** | **90.0%** | **99.8%** | 0.1% | 1.55 s |
| pixel-art-fixer | 49.7% | 80.9% | 98.3% | 0.0% | 0.18 s |
| perfectPixel | 53.3% | 68.0% | 96.7% | - | 0.03 s |
| proper-pixel-art | 72.2% | 80.4% | 99.7% | 0.0% | 0.49 s |

## Contents

- [Examples](#examples)
- [Install](#install)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Benchmark](#benchmark)
- [License](#license)

## Examples

Each example is one case from a category of the benchmark's AI suite: CC0 pixel art rendered the
way generators fake it, with a known native size. The sizes are the visible art in cells; ✓ marks
the exact native size. Every tool runs with its default settings.

### Two sprites on one canvas

- [Goblins by LuizMelo](https://luizmelo.itch.io/monsters-creatures-fantasy), CC0. Category `gen_pair`. Native art: 78×36.

| Input, 1800×845 | Xprite, 78×36 ✓ | pixel-art-fixer, 78×35 ✗ | perfectPixel, 80×36 ✗ | proper-pixel-art, 79×36 ✗ |
| :---: | :---: | :---: | :---: | :---: |
| ![Input, 1800×845](docs/images/pair-input.png) | ![Xprite](docs/images/pair-xprite.png) | ![pixel-art-fixer](docs/images/pair-fixer.png) | ![perfectPixel](docs/images/pair-perfectpixel.png) | ![proper-pixel-art](docs/images/pair-proper.png) |

### Cells that drift and jitter

- [Boss dragon by ansimuz](https://opengameart.org/content/sideview-fantasy-patreon-collection), CC0. Category `gen_wobble`. Native art: 71×39.

| Input, 1226×664 | Xprite, 71×39 ✓ | pixel-art-fixer, 69×38 ✗ | perfectPixel, 74×39 ✗ | proper-pixel-art, 69×38 ✗ |
| :---: | :---: | :---: | :---: | :---: |
| ![Input, 1226×664](docs/images/wobble-input.png) | ![Xprite](docs/images/wobble-xprite.png) | ![pixel-art-fixer](docs/images/wobble-fixer.png) | ![perfectPixel](docs/images/wobble-perfectpixel.png) | ![proper-pixel-art](docs/images/wobble-proper.png) |

### Small cells and WebP damage

- [Monster by Denzi](https://opengameart.org/content/denzis-public-domain-art), CC0. Category `gen_small_pitch`. Native art: 32×48.

| Input, 218×339 | Xprite, 32×48 ✓ | pixel-art-fixer, 32×47 ✗ | perfectPixel, 32×49 ✗ | proper-pixel-art, 34×49 ✗ |
| :---: | :---: | :---: | :---: | :---: |
| ![Input, 218×339](docs/images/small-input.png) | ![Xprite](docs/images/small-xprite.png) | ![pixel-art-fixer](docs/images/small-fixer.png) | ![perfectPixel](docs/images/small-perfectpixel.png) | ![proper-pixel-art](docs/images/small-proper.png) |

### A small sprite on a large clear canvas

- [Nekomimi girl by cawfeecrow](https://opengameart.org/content/nekomimi-girl-portrait), CC0. Category `gen_sparse`. Native art: 123×136.

| Input, 1797×1800 | Xprite, 123×136 ✓ | pixel-art-fixer, 122×136 ✗ | perfectPixel, 124×136 ✗ | proper-pixel-art, 127×142 ✗ |
| :---: | :---: | :---: | :---: | :---: |
| ![Input, 1797×1800](docs/images/sparse-input.png) | ![Xprite](docs/images/sparse-xprite.png) | ![pixel-art-fixer](docs/images/sparse-fixer.png) | ![perfectPixel](docs/images/sparse-perfectpixel.png) | ![proper-pixel-art](docs/images/sparse-proper.png) |

### An off-white background

- [Dragon by ansimuz](https://opengameart.org/content/sideview-fantasy-patreon-collection), CC0. Category `gen_white`. Native art: 162×106.

| Input, 1800×1210 | Xprite, 162×106 ✓ | pixel-art-fixer, 325×208 ✗ | perfectPixel, 161×105 ✗ | proper-pixel-art, 168×106 ✗ |
| :---: | :---: | :---: | :---: | :---: |
| ![Input, 1800×1210](docs/images/white-input.png) | ![Xprite](docs/images/white-xprite.png) | ![pixel-art-fixer](docs/images/white-fixer.png) | ![perfectPixel](docs/images/white-perfectpixel.png) | ![proper-pixel-art](docs/images/white-proper.png) |

### Painterly shading inside cells

- [Naga mage, Dungeon Crawl Stone Soup](https://github.com/crawl/tiles), CC0. Category `gen_painterly`. Native art: 31×32.

| Input, 411×425 | Xprite, 31×32 ✓ | pixel-art-fixer, 30×33 ✗ | perfectPixel, 31×32 ✓ | proper-pixel-art, 31×34 ✗ |
| :---: | :---: | :---: | :---: | :---: |
| ![Input, 411×425](docs/images/painterly-input.png) | ![Xprite](docs/images/painterly-xprite.png) | ![pixel-art-fixer](docs/images/painterly-fixer.png) | ![perfectPixel](docs/images/painterly-perfectpixel.png) | ![proper-pixel-art](docs/images/painterly-proper.png) |

## Install

```bash
npm install @xprite/pixelate
```

## Usage

An image is `{ width, height, data }`, where `data` holds RGBA bytes, row by row, with straight
alpha. `ImageData` from a canvas has this shape.

### Recover a grid

```ts
import {
  CellColorPicker,
  PixelationAlgorithm,
  PixelationMode,
  detectWithAlgorithm,
  pixelateImage,
  preloadWasm,
} from "@xprite/pixelate";

await preloadWasm(); // optional: loads the grid-count detector once, before the first image

const image = { width, height, data: new Uint8ClampedArray(rgba) };

const grid = detectWithAlgorithm(image, PixelationAlgorithm.Auto);
if (grid.reliable) {
  const art = pixelateImage(image, {
    mode: PixelationMode.RecoverGrid,
    grid,
    colorPicker: CellColorPicker.TwoStage,
    paletteSnap: { adaptive: true }, // merge the near-shades a generator leaves behind
  });
  // art.width × art.height is the native size: one pixel per recovered cell.
}
```

`grid.reliable` is false when the image has no consistent grid (a photo, a drawing, or real 1×
pixel art). `RecoverGrid` mode throws an error for such a grid. Use `Convert` mode for those
images.

### Convert an image

```ts
const art = pixelateImage(photo, {
  mode: PixelationMode.Convert,
  targetSize: { width: 64, height: 64 },
  paletteSnap: { colors: 16 },
});
```

### Remove a flat background

```ts
import { removeBackground } from "@xprite/pixelate";

const clear = removeBackground(image); // keys the most common border colour
```

Call it before detection when a generator painted a white or checkerboard background.

### Options

`pixelateImage(image, options)`:

| Option | Description |
| --- | --- |
| `mode` | `RecoverGrid` uses a detected grid. `Convert` makes pixel art at a size you give. |
| `grid` | A grid from `detectWithAlgorithm`. If you omit it, the grid is detected with `algorithm`. |
| `algorithm` | Grid detector. `Auto` runs all of them and picks one grid. |
| `colorPicker` | Colour rule per cell: `TwoStage`, `MostCommon` (default), `Median`, `Average`, `KMeans`, `Contrast` and others. |
| `targetSize`, `targetWidth`, `targetHeight`, `blockSize` | Output size in `Convert` mode. |
| `paletteSnap` | Limit colours: `{ adaptive: true }`, `{ colors: 16 }` or `{ palette: [...] }`, with optional `dither`. |
| `prepass` | Outline pre-pass from PixelOE (`Pixeloe`, `PixeloeLines`). |
| `removeNoise` | Light smoothing of similar neighbour colours. |
| `preserveDimensions` | Scale the result back up to the source size, nearest neighbour. |

[`src/types.ts`](src/types.ts) documents every option.

### Workers

`detectWithAlgorithm` and `pixelateImage` are synchronous and can take a few seconds on large
images, so run them in a Web Worker. In a browser, Auto can also run its grid-count detector in a
nested worker, in parallel with the other detectors:

```ts
import { setAcRlBrowserWorkerFactory, detectWithAlgorithmAsync } from "@xprite/pixelate";

setAcRlBrowserWorkerFactory(
  () =>
    new Worker(
      new URL("@xprite/pixelate/wasm/ac-rl-detect-browser-worker.js", import.meta.url),
      { type: "module" },
    ),
);
const grid = await detectWithAlgorithmAsync(image);
```

In Node, the detector starts a `worker_threads` worker from `wasm/ac-rl-detect-worker.mjs` by
itself. Set `XPRITE_AC_RL_WORKER=0` to keep it on the calling thread.

## How it works

1. **Straighten.** Auto estimates the tilt. When the tilt is clear, it detects on a straightened
   copy.
2. **Propose.** Seven detectors propose grids: uniform grid, edge grid, frame lattice, pitch
   lattice, colour period, border runs and edge spacing. A WebAssembly port of pixel-art-fixer's
   autocorrelation and run-length vote gives an independent cell count.
3. **Follow the edges.** At each pitch the detectors keep, a dynamic program walks each axis and
   puts every cut on a colour edge. Each cell stays within 0.75 to 1.25 of the pitch, and a change
   of width costs extra. This step handles cells of uneven width.
4. **Filter.** A candidate is dropped when its cuts miss the colour edges that a coarser grid
   follows.
5. **Choose.** The grid that describes the image in the fewest bits wins (minimum description
   length). A grid that is not locked to the content's phase pays a penalty. Drift and sheared
   rows are read as strip shifts or as a phase field.
6. **Sample.** Each cell gets one colour (`TwoStage` packs the cell's colours in two steps).
   Adaptive palette snapping then merges near-duplicate shades.
7. **Settle alpha.** Cells that the art covers become fully opaque, and cells outside the art
   become clear.

Each source file in [`src/`](src) describes its step.

## Benchmark

[`bench/`](bench) compares this package with three other tools on CC0 native pixel art. The
benchmark damages the art in known ways and scores each result against the original. Every tool
runs with its default settings.

AI suite (1746 cases in 12 categories, rendered the way generators fake pixel art):

| Method | Exact size | Within 1 cell | Pixel match | ΔE | Half-transparent fringe | Median time |
| --- | --- | --- | --- | --- | --- | --- |
| Xprite Auto | **83.6%** | **90.0%** | **99.8%** | 0.82 | 0.1% | 1.55 s |
| pixel-art-fixer | 49.7% | 80.9% | 98.3% | 1.74 | 0.0% | 0.18 s |
| perfectPixel | 53.3% | 68.0% | 96.7% | 2.42 | - | 0.03 s |
| proper-pixel-art | 72.2% | 80.4% | 99.7% | **0.64** | 0.0% | 0.49 s |

Exact size per category:

| Category | Xprite | pixel-art-fixer | perfectPixel | proper-pixel-art |
| --- | --- | --- | --- | --- |
| Clean (`gen_clean`) | **93.6%** | 71.7% | 58.4% | 74.6% |
| Sparse canvas (`gen_sparse`) | **99.0%** | 63.5% | 71.9% | 88.5% |
| Off-white background (`gen_white`) | 77.7% | 65.2% | 66.1% | **82.1%** |
| Soft outline (`gen_soft_edge`) | **95.8%** | 61.9% | 67.8% | 82.2% |
| Drift and WebP (`gen_webp`) | **80.9%** | 40.5% | 57.8% | 71.1% |
| Halos and JPEG (`gen_halo_jpeg`) | **82.7%** | 52.6% | 60.1% | 72.8% |
| Painterly shading (`gen_painterly`) | **84.5%** | 39.1% | 67.8% | 79.3% |
| Small cells (4-8 px) (`gen_small_pitch`) | **72.2%** | 47.9% | 40.2% | 43.8% |
| Large cells (24-48 px) (`gen_large_pitch`) | 68.2% | 22.0% | 68.2% | **78.0%** |
| Strong drift (`gen_wobble`) | **73.3%** | 30.8% | 30.8% | 54.1% |
| Two sprites (`gen_pair`) | **97.1%** | 62.7% | 45.1% | 72.5% |
| Drop shadow (`gen_shadow`) | **97.3%** | 64.0% | 0.0% | 84.7% |

[pixel-bench](https://github.com/Retro-Diffusion/pixel-bench) suite v1 (7651 cases of upscales and
lossy pipelines):

| Method | Exact size | Within 1 cell | Pixel match | ΔE | Median time |
| --- | --- | --- | --- | --- | --- |
| Xprite Auto | **87.1%** | **90.1%** | 94.3% | **2.79** | 0.24 s |
| pixel-art-fixer | 77.8% | 83.5% | **94.4%** | 2.83 | 0.04 s |
| perfectPixel | 24.2% | 32.9% | 89.7% | 4.31 | 0.002 s |
| proper-pixel-art | 16.5% | 28.6% | 93.0% | 3.85 | 0.05 s |

Pixel match and ΔE are measured only on the cases with the exact size. Xprite is the slowest of
the four tools. The damage is synthetic, so the scores show how the tools rank on these features,
not how often they succeed on real images. [bench/README.md](bench/README.md) gives the method,
the categories and the steps to run it.

## License

MIT. Parts are adapted from pixel-art-fixer, PixelOE, proper-pixel-art and tensorhead/dithering
(see [NOTICE.md](NOTICE.md)). The example art is CC0 (see
[bench/corpus/CREDITS.md](bench/corpus/CREDITS.md)).
