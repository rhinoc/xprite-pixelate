// Detect and recover one raw RGBA image for the README figures.
//   node bench/tools/readme-detect.mjs <in.rgba> <width> <height> <out.rgba>
// Prints the grid as JSON.
import { readFileSync, writeFileSync } from "node:fs";

const {
  CellColorPicker,
  PixelationAlgorithm,
  PixelationMode,
  detectWithAlgorithm,
  pixelateImage,
  preloadWasm,
} = await import(new URL("../../dist/index.js", import.meta.url).href);

const [input, width, height, output] = process.argv.slice(2);
await preloadWasm();
const image = { width: +width, height: +height, data: new Uint8ClampedArray(readFileSync(input)) };
const grid = detectWithAlgorithm(image, PixelationAlgorithm.Auto);
const art = pixelateImage(image, {
  mode: PixelationMode.RecoverGrid,
  grid,
  colorPicker: CellColorPicker.TwoStage,
  paletteSnap: { adaptive: true },
});
writeFileSync(output, Buffer.from(art.data.buffer, art.data.byteOffset, art.data.byteLength));
const { cutsX, cutsY, ...rest } = grid;
console.log(JSON.stringify({ ...rest, cutsX, cutsY, outWidth: art.width, outHeight: art.height }));
process.exit(0);
