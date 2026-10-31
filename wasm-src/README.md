# wasm-src

Rust source for `../wasm/pixelfixer_detect*` (the AC+RL grid-count consensus detector).

## Layout

```text
Cargo.toml            rustfft 6, wasm-bindgen =0.2.129
Cargo.lock            locked dependency versions (rustfft 6.4.1)
rust-toolchain.toml   rustc 1.99.1 + wasm32-unknown-unknown
rebuild.sh            build and write ../wasm/
src/lib.rs            detectFastAcRl(rgba, width, height) wasm-bindgen API
src/seq_join.rs       sequential stand-in for rayon::join
src/acf.rs            banded autocorrelation, comb and cepstrum scores
src/autocorr.rs       AC detector
src/gray.rs           alpha-folded luminance and derivatives
src/runlengths.rs     RL detector
src/sigproc.rs        median, percentile and peak helpers
```

## Upstream

`acf`, `autocorr`, `gray`, `runlengths` and `sigproc` come from
[Retro-Diffusion/pixel-art-fixer](https://github.com/Retro-Diffusion/pixel-art-fixer)
`rust/src/`, commit `ef376e57e1c272633ca2dbf5f29ec3fcf6596465`, MIT
(`../licenses/pixel-art-fixer-MIT.txt`). The only change: `rayon` parallel iterators and
`rayon::join` are replaced with sequential equivalents. Results keep the same order, so float
sums stay identical. `acf`, `gray` and `sigproc` are unchanged.

## Rebuild

```bash
rustup toolchain install 1.99.1 --target wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.129 --locked
./rebuild.sh
```

`rebuild.sh` writes `pixelfixer_detect.js`, `pixelfixer_detect.d.ts`,
`pixelfixer_detect_bg.wasm` and `pixelfixer_detect_bg.wasm.d.ts` to `../wasm/`
(`--target web`). Set `OUT_DIR` to write elsewhere and `WASM_BINDGEN` to use a CLI that is
not on `PATH`. The CLI version must equal the `wasm-bindgen` version in `Cargo.toml`.

The shipped glue is formatted and has lint-disable headers; raw wasm-bindgen output differs
only in formatting.

## Verification (2026-10-31)

A rebuild into a temporary directory was compared with the shipped `../wasm/` in Node.
Inputs: 265 RGBA images (nearest-neighbour upscales of game sprites at factors 2 to 17 and
2.5 to 12.2, blurred, noisy and JPEG versions, random noise, smooth photo-like images, flat,
transparent and 3x5 images). `cols`, `rows`, `step_x`, `step_y` and `consensus` matched for
265/265. Both builds panic in `autocorr::axis_estimate` on the 3x5 image.

The rebuilt `.wasm` is 457,076 bytes; the shipped one is 456,760 bytes (+316). The shipped
binary was built on Linux x86_64 (`/home/box/.cargo` paths); this rebuild ran on macOS arm64.
Longer registry paths add 68 bytes. The code section is 170 bytes larger, with one extra
out-of-line allocator helper. Byte-identical output is not expected across hosts.

An earlier native build of the same sources matched the Python reference
(`core.detect(mode="fast")`) on 8 of 8 pixel-art-fixer golden cases. That smoke binary is not part
of this tree.
