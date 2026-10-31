/**
 * Browser Worker for the AC+RL grid-count detector. Auto starts it through the factory given to
 * `setAcRlBrowserWorkerFactory`, so the detector runs while the other detectors run on the
 * calling worker.
 *
 *   setAcRlBrowserWorkerFactory(() => new Worker(
 *     new URL("@xprite/pixelate/wasm/ac-rl-detect-browser-worker.js", import.meta.url),
 *     { type: "module" }));
 *
 * Protocol (one MessagePort per job), the same as ac-rl-detect-worker.mjs:
 *   { type: "init", port } -> { ok, type: "init", ms }
 *   { type: "detect", width, height, data: ArrayBuffer, port } ->
 *     { ok, type: "detect", consensus: { cols, rows } | null, ms }
 */
import init, { detectFastAcRl } from "./pixelfixer_detect.js";

const CONSENSUS = "fast:ac+rl(S)";
let ready = null;

self.onmessage = async (event) => {
  const { type, port, width, height, data } = event.data ?? {};
  if (!port) return;
  try {
    const started = performance.now();
    ready ??= init();
    await ready;
    if (type === "init") {
      port.postMessage({ ok: true, type: "init", ms: performance.now() - started });
      return;
    }
    if (type === "detect") {
      const begun = performance.now();
      const result = detectFastAcRl(new Uint8Array(data), width, height);
      const consensus =
        result.consensus === CONSENSUS ? { cols: result.cols, rows: result.rows } : null;
      result.free?.();
      port.postMessage({ ok: true, type: "detect", consensus, ms: performance.now() - begun });
      return;
    }
    port.postMessage({ ok: false, error: `unknown type ${type}` });
  } catch (error) {
    ready = null;
    port.postMessage({ ok: false, error: String(error?.stack ?? error) });
  }
};
