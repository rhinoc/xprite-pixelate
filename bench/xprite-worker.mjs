// Recovery worker for the benchmark: @xprite/pixelate Auto detect, then grid recovery.
// One JSON job per stdin line: { in, out, width, height } with raw RGBA files; one JSON reply per line.
import { readFileSync, writeFileSync } from "node:fs";
import readline from "node:readline";

const pixelate = await import(new URL("../dist/index.js", import.meta.url).href);
const {
  CellColorPicker,
  PixelationAlgorithm,
  PixelationMode,
  detectWithAlgorithm,
  pixelateImage,
  preloadWasm,
} = pixelate;

await preloadWasm();
console.log(JSON.stringify({ ready: true, version: process.env.npm_package_version ?? null }));

for await (const line of readline.createInterface({ input: process.stdin, crlfDelay: Infinity })) {
  if (!line.trim()) continue;
  const job = JSON.parse(line);
  if (job.cmd === "quit") break;
  try {
    const image = {
      width: job.width,
      height: job.height,
      data: new Uint8ClampedArray(readFileSync(job.in)),
    };
    let started = performance.now();
    const grid = detectWithAlgorithm(image, PixelationAlgorithm.Auto);
    const detectMs = performance.now() - started;
    if (!grid.reliable) {
      console.log(JSON.stringify({ ok: true, refused: true, detectMs, recoverMs: 0 }));
      continue;
    }
    started = performance.now();
    const out = pixelateImage(image, {
      mode: PixelationMode.RecoverGrid,
      grid,
      colorPicker: CellColorPicker.TwoStage,
      paletteSnap: { adaptive: true },
    });
    const recoverMs = performance.now() - started;
    writeFileSync(job.out, Buffer.from(out.data.buffer, out.data.byteOffset, out.data.byteLength));
    console.log(
      JSON.stringify({ ok: true, width: out.width, height: out.height, detectMs, recoverMs }),
    );
  } catch (error) {
    console.log(JSON.stringify({ ok: false, error: String(error?.stack ?? error).slice(0, 400) }));
  }
}
process.exit(0);
