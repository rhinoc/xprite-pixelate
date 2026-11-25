import { assertPixelBuffer, UINT8_MAX, type PixelBuffer } from "./base.ts";

const CHANNELS = 4;
const ALPHA = 3;

export interface RemoveOrphanPixelsOptions {
  /** Replace isolated interior colors. Disable this for dithered art. Defaults to true. */
  absorbInterior?: boolean;
}

function rgbAt(data: Uint8ClampedArray, offset: number): number {
  return (data[offset] << 16) | (data[offset + 1] << 8) | data[offset + 2];
}

function majorityNeighborColor(
  data: Uint8ClampedArray,
  offset: number,
  neighbors: readonly number[],
  colors: Uint32Array,
): number | undefined {
  const center = rgbAt(data, offset);
  let candidate = 0;
  let votes = 0;
  for (let i = 0; i < neighbors.length; i++) {
    const neighbor = offset + neighbors[i];
    if (data[neighbor + ALPHA] !== UINT8_MAX) return;
    const color = rgbAt(data, neighbor);
    if (color === center) return;
    colors[i] = color;
    // Cancel opposing votes, then verify the candidate has a strict majority.
    if (votes === 0) candidate = color;
    votes += color === candidate ? 1 : -1;
  }
  if (votes === 0) return;
  let count = 0;
  for (const color of colors) if (color === candidate) count++;
  if (count > neighbors.length / 2) return candidate;
}

/**
 * Clear fully opaque pixels separated from visible art on all four sides. In an opaque interior,
 * replace a color unsupported by all eight neighbors only if those neighbors have a strict
 * majority color. Decisions use the original pixels and never change the input buffer.
 */
export function removeOrphanPixels(
  image: PixelBuffer,
  { absorbInterior = true }: RemoveOrphanPixelsOptions = {},
): PixelBuffer {
  assertPixelBuffer(image);
  const { width, height, data } = image;
  if (width === 1 && height === 1) return image;
  const stride = width * CHANNELS;
  const neighbors = [
    -CHANNELS, CHANNELS, -stride, stride,
    -stride - CHANNELS, -stride + CHANNELS, stride - CHANNELS, stride + CHANNELS,
  ];
  const colors = new Uint32Array(neighbors.length);
  let output: Uint8ClampedArray | undefined;
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      const offset = y * stride + x * CHANNELS;
      const alpha = offset + ALPHA;
      if (data[alpha] !== UINT8_MAX) continue;
      if (
        (x === 0 || data[alpha - CHANNELS] === 0) &&
        (x === width - 1 || data[alpha + CHANNELS] === 0) &&
        (y === 0 || data[alpha - stride] === 0) &&
        (y === height - 1 || data[alpha + stride] === 0)
      ) {
        (output ??= data.slice()).fill(0, offset, offset + CHANNELS);
        continue;
      }
      if (!absorbInterior || x === 0 || y === 0 || x === width - 1 || y === height - 1) continue;
      const replacement = majorityNeighborColor(data, offset, neighbors, colors);
      if (replacement === undefined) continue;
      output ??= data.slice();
      output[offset] = replacement >> 16;
      output[offset + 1] = (replacement >> 8) & 255;
      output[offset + 2] = replacement & 255;
    }
  return output ? { ...image, data: output } : image;
}
