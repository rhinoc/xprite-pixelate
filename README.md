# @xprite/pixelate

Recover the real pixel grid of AI-generated and upscaled pixel art, and turn ordinary images into
pixel art. It runs in browsers and Node and has no runtime dependencies. One WebAssembly module
ships inside the package.

This is the importer of the [Xprite](https://xprite.cc) pixel editor.

```bash
npm install @xprite/pixelate
```

## Recover a grid

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

// RGBA, row by row, straight alpha (for example ImageData from a canvas).
const image = { width, height, data: new Uint8ClampedArray(rgba) };

const grid = detectWithAlgorithm(image, PixelationAlgorithm.Auto);
if (grid.reliable) {
  const art = pixelateImage(image, {
    mode: PixelationMode.RecoverGrid,
    grid,
    colorPicker: CellColorPicker.TwoStage,
    paletteSnap: { adaptive: true }, // merge the near-shades a generator leaves behind
  });
  // art.width x art.height is the native size; one pixel per recovered cell.
}
```

`grid.reliable` is false when the image has no consistent grid (a photo, a drawing, real 1x pixel
art). Use the convert mode for those images.

## Convert an image

```ts
const art = pixelateImage(photo, {
  mode: PixelationMode.Convert,
  targetSize: { width: 64, height: 64 },
  paletteSnap: { colors: 16 },
});
```

## Workers

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

Auto runs seven grid detectors on the image, removes candidates whose cuts miss the colour edges,
and chooses the grid that describes the image in the fewest bits, with a penalty for grids that
are not locked to the content's phase. It handles non-integer cell sizes, drift, tilt, soft edges
and transparent canvases. The source files in `src/` describe each step.

## Benchmark

`bench/` compares this package with pixel-art-fixer, perfectPixel and proper-pixel-art on CC0
native pixel art rendered the way image generators fake it. See [bench/README.md](bench/README.md).

## License

MIT. Parts are adapted from other open-source projects; see [NOTICE.md](NOTICE.md).
