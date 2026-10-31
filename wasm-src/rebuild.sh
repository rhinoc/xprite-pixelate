#!/usr/bin/env bash
# Rebuild ../wasm/ from these Rust sources.
# Env overrides: OUT_DIR (default ../wasm), WASM_BINDGEN (default wasm-bindgen on PATH).
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${OUT_DIR:-$SRC_DIR/../wasm}"
WASM_BINDGEN="${WASM_BINDGEN:-wasm-bindgen}"
BINDGEN_VERSION="0.2.129"

cd "$SRC_DIR"

command -v cargo >/dev/null || { echo "ERROR: cargo not found. Install Rust: https://rustup.rs" >&2; exit 1; }
command -v "$WASM_BINDGEN" >/dev/null || {
    echo "ERROR: wasm-bindgen not found. Install with:" >&2
    echo "  cargo install wasm-bindgen-cli --version $BINDGEN_VERSION --locked" >&2
    exit 1
}
FOUND="$("$WASM_BINDGEN" --version | awk '{print $2}')"
[ "$FOUND" = "$BINDGEN_VERSION" ] || {
    echo "ERROR: wasm-bindgen $FOUND found; $BINDGEN_VERSION required (must match Cargo.toml)." >&2
    exit 1
}

# rust-toolchain.toml selects the compiler and the wasm32 target.
cargo build --release --target wasm32-unknown-unknown --lib

TARGET_DIR="${CARGO_TARGET_DIR:-$SRC_DIR/target}"
mkdir -p "$OUT_DIR"
"$WASM_BINDGEN" "$TARGET_DIR/wasm32-unknown-unknown/release/pixelfixer_detect.wasm" \
    --out-dir "$OUT_DIR" \
    --target web

echo "Wrote $OUT_DIR: $(wc -c < "$OUT_DIR/pixelfixer_detect_bg.wasm") bytes wasm"
