import { UINT8_MAX, type PixelBuffer } from "./base.ts";

const CHANNELS = 4;
const ALPHA = 3;
const HALF_ALPHA = 128;
const TRANSLUCENT_LOW = 16;
const TRANSLUCENT_HIGH = 224;
/** Share of the visible pixels a soft outline around opaque art stays below. */
const TRANSLUCENT_SHARE = 0.2;

/** Whether the image's visible pixels are opaque but for a soft edge. */
function opaqueArt(image: PixelBuffer, requireSoftAlpha = false): boolean {
  let visible = 0;
  let translucent = 0;
  let solid = 0;
  let fullyOpaque = 0;
  for (let o = ALPHA; o < image.data.length; o += CHANNELS) {
    const alpha = image.data[o];
    if (!alpha) continue;
    visible++;
    if (alpha > TRANSLUCENT_HIGH) {
      solid++;
      if (alpha === UINT8_MAX) fullyOpaque++;
    } else if (alpha >= TRANSLUCENT_LOW) translucent++;
  }
  if (visible === 0 || translucent > TRANSLUCENT_SHARE * visible) return false;
  if (!requireSoftAlpha) return true;
  // A soft sprite has a solid core and some partial alpha. Look for a change
  // in coverage so an evenly translucent image keeps its original alpha.
  const hasEdge = solid < visible || visible < image.width * image.height;
  return hasEdge && solid > 0 && fullyOpaque < visible;
}

function hasPartialAlpha(image: PixelBuffer): boolean {
  const { data } = image;
  for (let alpha = ALPHA; alpha < data.length; alpha += CHANNELS)
    if (data[alpha] > 0 && data[alpha] < UINT8_MAX) return true;
  return false;
}

function writeBinaryAlpha(data: Uint8ClampedArray, offset: number, covered: boolean): void {
  if (covered) data[offset + ALPHA] = UINT8_MAX;
  else data.fill(0, offset, offset + CHANNELS);
}

/**
 * Settle soft alpha in a converted sprite using the sampled coverage. The
 * source supplies the opacity heuristic so resampling a hard-edged image keeps
 * its coverage alpha. Pass one buffer to settle alpha at its current size.
 * Returns a new buffer when any pixels change.
 */
export function settlePixelAlpha(source: PixelBuffer, sampled: PixelBuffer = source): PixelBuffer {
  if (!hasPartialAlpha(sampled) || !opaqueArt(source, true)) return sampled;
  const data = sampled.data.slice();
  for (let offset = 0; offset < data.length; offset += CHANNELS) {
    const alpha = data[offset + ALPHA];
    if (alpha > 0 && alpha < UINT8_MAX) writeBinaryAlpha(data, offset, alpha >= HALF_ALPHA);
  }
  return { ...sampled, data };
}

/** Settle alpha from the source pixels inside each recovered grid cell. */
export function settleEdgeAlpha(
  image: PixelBuffer,
  x: readonly number[],
  y: readonly number[],
  out: PixelBuffer,
): void {
  const opaque = opaqueArt(image);
  for (let row = 0; row < out.height; row++)
    for (let column = 0; column < out.width; column++) {
      const offset = (row * out.width + column) * CHANNELS;
      if (!out.data[offset + ALPHA]) continue;
      const left = Math.max(0, Math.ceil(x[column])),
        right = Math.min(image.width, Math.ceil(x[column + 1])),
        top = Math.max(0, Math.ceil(y[row])),
        bottom = Math.min(image.height, Math.ceil(y[row + 1]));
      let covered = 0,
        coveredAlpha = 0;
      const alphas: number[] = [];
      for (let py = top; py < bottom; py++)
        for (let px = left; px < right; px++) {
          const alpha = image.data[(py * image.width + px) * CHANNELS + ALPHA];
          alphas.push(alpha);
          if (alpha < HALF_ALPHA) continue;
          covered++;
          coveredAlpha += alpha;
        }
      const area = (right - left) * (bottom - top);
      if (!covered && !opaque) {
        // Translucent art fills its cell evenly; a soft outline leaves most of the cell clear.
        alphas.sort((a, b) => a - b);
        const median = alphas[alphas.length >> 1] ?? 0;
        if (median < TRANSLUCENT_LOW) out.data.fill(0, offset, offset + CHANNELS);
        else out.data[offset + ALPHA] = median;
        continue;
      }
      const outside = covered < area / 2;
      if (opaque || outside) writeBinaryAlpha(out.data, offset, !outside);
      else {
        // Translucent art (a shadow, a glow) keeps its alpha, but a covered cell above
        // TRANSLUCENT_HIGH is opaque art drawn a little below 255, as everywhere else.
        const alpha = covered < area ? coveredAlpha / covered : out.data[offset + ALPHA];
        out.data[offset + ALPHA] = alpha > TRANSLUCENT_HIGH ? UINT8_MAX : Math.round(alpha);
      }
    }
}
