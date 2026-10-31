# Third-party notices

| Part | Source | License | Text |
| --- | --- | --- | --- |
| `wasm/` and `wasm-src/`: AC+RL grid-count consensus (`acf`, `autocorr`, `runlengths`, `gray`, `sigproc`), made sequential and compiled to WebAssembly | [Retro-Diffusion/pixel-art-fixer](https://github.com/Retro-Diffusion/pixel-art-fixer), Copyright (c) 2026 Astropulse, LLC | MIT | [licenses/pixel-art-fixer-MIT.txt](licenses/pixel-art-fixer-MIT.txt) |
| `src/line-guided/pixeloe-legacy.ts`, `cv-ops.ts`, `cv-lab.ts`: port of PixelOE's legacy `pixelize()` | [KohakuBlueleaf/PixelOE](https://github.com/KohakuBlueleaf/PixelOE) | Apache-2.0 | [licenses/PixelOE-Apache-2.0.txt](licenses/PixelOE-Apache-2.0.txt) |
| `src/pixeloe-prepass.ts`: port of PixelOE's outline expansion and colour match (`torch/outline.py`, `torch/color.py`); `src/cell-color-picker.ts`: its contrast-based downscale | [KohakuBlueleaf/PixelOE](https://github.com/KohakuBlueleaf/PixelOE) | Apache-2.0 | [licenses/PixelOE-Apache-2.0.txt](licenses/PixelOE-Apache-2.0.txt) |
| `src/grid-detect.ts`: the edge-mesh idea (anchor cuts on projected edges, fill gaps at an even pitch); `src/cell-color-picker.ts`: per-cell colour choice and output colour merging | [KennethJAllen/proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art), Copyright (c) 2024 Kenneth Allen | MIT | [licenses/proper-pixel-art-MIT.txt](licenses/proper-pixel-art-MIT.txt) |
| `src/palette-snap.ts`: Bayer 8x8 matrix and ordered dithering to a palette (`matrices.rs`, `ordered.rs`) | [tensorhead/dithering](https://github.com/tensorhead/dithering) | MIT | [licenses/tensorhead-dithering-MIT.txt](licenses/tensorhead-dithering-MIT.txt) |

The PixelOE ports are modified versions: they were rewritten from Python, OpenCV and NumPy into
TypeScript, and the legacy port's expansion weight can be replaced by a line guide.
