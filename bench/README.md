# Benchmark

This benchmark measures how well a tool turns AI-generated "pixel art" back into real pixel art.
It builds on [pixel-bench](https://github.com/Retro-Diffusion/pixel-bench) (MIT) and keeps its
method: start from native 1x pixel art, damage it in a known way, keep the exact source
coordinates of every output pixel, then score the tool's result against the original.

pixel-bench imitates upscalers and lossy pipelines. It puts transparent art on a flat colour and
fills the frame with art scaled 2-8x. Images from generators look different, so this benchmark
adds an AI suite with those features (see [Suites](#suites)) and also times each tool.

## Methods

| Name | Tool | How it runs |
| --- | --- | --- |
| `xprite` | `@xprite/pixelate` (this repository) | Auto detect, then grid recovery with the TwoStage picker and adaptive colours, in a persistent Node worker on `dist/` |
| `fixer` | [pixel-art-fixer](https://github.com/Retro-Diffusion/pixel-art-fixer) | The native Rust CLI, `process <in> <out> full`. Time is the CLI's own detect + reconstruct time. |
| `perfectpixel` | [perfectPixel](https://github.com/theamusing/perfectPixel) | `get_perfect_pixel(rgb)` with its defaults. RGB only: the input is composited over its background. |
| `proper` | [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art) | `proper_pixel_art.image.pixelate(rgba)` with its defaults |
| `spritefusion` | [Sprite Fusion Pixel Snapper](https://github.com/Hugo-Dz/spritefusion-pixel-snapper), commit `02f9315d73d3219274d17767b36d9a231a6b1f4b` (1.0.0) | Native release CLI `INPUT OUTPUT`, automatic grid, default 16-color quantization, one Rayon thread |

Each method uses its default settings; Xprite uses adaptive color merging while Snapper quantizes
to 16 colors before grid detection. These are complete pipelines, not a color-matched experiment.
The Xprite worker uses Auto plus TwoStage and adaptive palette merging, without a PixelOE prepass.
The four original adapters report their own detection/reconstruction times. Sprite Fusion reports
CLI wall time including startup and PNG decode/encode, so its `seconds` values cannot be compared
directly with the others and are omitted from README timing tables. Accuracy runs use eight workers for xprite and six workers for the other methods;
their wall times are not a speed benchmark.

## Corpus

`corpus/` holds native 1x pixel art under CC0 (and one CC-BY source, credited). Its images vary in
size (8 to 320 px per side), palette (2 to 100+ colours) and genre (characters, monsters, items,
tiles, portraits, scenes, isometric, UI, animation frames). Sources and licences are in
[corpus/CREDITS.md](corpus/CREDITS.md), and every image's origin is in `corpus/manifest.json`.

## Suites

**ai** (`xbench/suite.py`, version `ai-v1`). Each category models one feature of generator
output:

| Category | What it models |
| --- | --- |
| `gen_clean` | Soft alpha edge, near-flat cells, pitch 8-20 px, opaque alpha 250-254 |
| `gen_sparse` | The sprite spans 20-35% of a large clear canvas |
| `gen_white` | An off-white opaque background instead of transparency |
| `gen_soft_edge` | A 3-5 px partly transparent outline |
| `gen_webp` | Drift, small cut jitter, noise, WebP |
| `gen_halo_jpeg` | Sharpening halos and JPEG colour damage |
| `gen_painterly` | Painterly shading inside cells |
| `gen_small_pitch` | Pitch 4-8 px |
| `gen_large_pitch` | Pitch 24-48 px: a small sprite drawn across a large canvas |
| `gen_wobble` | Strong drift and jitter |
| `gen_pair` | Two sprites side by side on one canvas |
| `gen_shadow` | A translucent drop shadow under the sprite |

Opaque art (tiles, scenes) is not used in the categories that need a clear background. Each case
is a deterministic function of the image id, the category and the suite version.

**v1**: pixel-bench suite v1, unchanged (43 categories), on the same corpus.

**speed**: `gen_clean` renders with the longest side at 256, 512, 1024, 1448 and 2000 px (2000 x
2000 is pixel-art-fixer's 4 MP limit), run with one worker. For each size, up to 12 images are
picked whose pitch at that size is 8-20 px, so every size measures the same task.

## Scores

For a sprite on a clear canvas, the margin has no visible grid, so its size is read from the
sprite: scores compare the bounding boxes of the visible art, in cells.

| Score | Meaning |
| --- | --- |
| `exact` | The recovered art has exactly the native columns and rows |
| `within1` | Both within one cell |
| `pixel_match` | On exact cases: share of native pixels recovered right (clear stays clear; visible pixels within 24 per channel) |
| `delta_e` | On exact cases: mean CIELAB dE76 of the visible pixels |
| `fringe` | On exact cases, for RGBA tools: share of visible output with alpha 1–254 where the art is binary. Alpha 254 counts; this is not the visible fringe area. |
| `grid_align` | pixel-bench's F1 of uniformly spaced lines implied by the output dimensions against the true cuts; not the actual potentially nonuniform cuts |
| `median_s`, `p90_s` | Time per image |

## Run

```bash
cd bench
python3 -m venv .venv
.venv/bin/pip install numpy scipy opencv-python-headless Pillow matplotlib "perfect-pixel[opencv]" proper-pixel-art
git clone https://github.com/Retro-Diffusion/pixel-bench vendor/pixel-bench
git clone https://github.com/Retro-Diffusion/pixel-art-fixer vendor/pixel-art-fixer
git clone https://github.com/Hugo-Dz/spritefusion-pixel-snapper vendor/spritefusion-pixel-snapper
git -C vendor/spritefusion-pixel-snapper checkout 02f9315d73d3219274d17767b36d9a231a6b1f4b
(cd vendor/spritefusion-pixel-snapper && cargo build --release --locked)
(cd vendor/pixel-art-fixer/rust && cargo build --release)
(cd .. && pnpm install && pnpm run build)
.venv/bin/python -I xbench/run.py --suite ai
.venv/bin/python -I xbench/run.py --suite v1
.venv/bin/python -I xbench/run.py --suite speed --workers 1
.venv/bin/python -I xbench/timing.py
.venv/bin/python -I xbench/charts.py
```

The pixel-art-fixer CLI reads its peak memory with a Windows-only call. On other systems, replace
the body of `peak_rss()` in `vendor/pixel-art-fixer/rust/src/main.rs` with `0`.
Set `PIXEL_SNAPPER_CLI` to an absolute path to use an existing binary. Existing JSONL files are
resumed by key; remove a method's file before rerunning it. Summaries are rewritten using the
selected methods, so pass all methods when producing a full comparison.

The recorded Sprite Fusion results were run on macOS 26.5.2 arm64 with rustc 1.83.0, six workers,
and `RAYON_NUM_THREADS=1`. The other four methods' committed results predate this addition;
their algorithm source and benchmark scoring have not changed since those records were created.
The AI suite has 1,746 cases and v1 has 7,651. Sprite Fusion produced no errors or refusals in
either. Xprite refused 21 AI and 237 v1 cases, which remain in the denominators. Pixel match, ΔE
and fringe are measured only on each method’s exact-size cases. Sample sets can differ, so these
values are not directly comparable across methods.

`timing.py` warms each method once and runs three repetitions of each of the 60 speed inputs,
one case at a time. It records every sample and its median can be computed from
`results/speed/timing-repeated.json`. Xprite is a persistent Node worker that exchanges raw RGBA;
Sprite Fusion is a fresh Rust CLI process per image and exchanges PNG. The outer wall time includes
the adapter's file I/O; the CLI's reported adapter time excludes Python's input PNG encoding and
output loading. This is an operational measurement, not an algorithm-only speed ratio.

The repeated run on the same machine produced these median per-case outer wall times (12 cases per
size; each case first reduced to the median of three repetitions):

| Longest side | Xprite persistent worker | Sprite Fusion CLI |
| --- | ---: | ---: |
| 256 | 0.143 s | 0.017 s |
| 512 | 0.423 s | 0.026 s |
| 1024 | 1.161 s | 0.053 s |
| 1448 | 2.151 s | 0.244 s |
| 2000 | 2.262 s | 0.255 s |

The worker and CLI have different startup, I/O, grid and palette behavior. Both completed all 180
measured runs without errors or refusals; startup warmup is outside the table.

## Limits

The damage is synthetic. Real generator output varies more, so the scores show how tools rank on
these features, not how often they succeed on real images. Every tool runs with its default
settings, and some of them have options that may do better on some categories.
