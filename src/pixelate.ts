import type { PixelBuffer } from "./base.ts";
import { assertDimension, assertPixelBuffer } from "./base.ts";
import { protectPixelationContours } from "./contours.ts";
import { smoothPixelation } from "./denoise.ts";
import { blockPartition } from "./grid.ts";
import { prepareGridSampling } from "./grid-sampling.ts";
import { runPixeloe } from "./line-guided/pixeloe-entry.ts";
import { resizeMostFrequent } from "./most-frequent.ts";
import {
  applyOutlinePrepass,
  DEFAULT_LINE_GUIDE,
  runsStockPixeloe,
} from "./outline-prepass.ts";
import { removeOrphanPixels } from "./orphan-pixels.ts";
import { snapPalette } from "./palette-snap.ts";
import { settlePixelAlpha } from "./pixel-alpha.ts";
import {
  detectWithAlgorithm,
  detectWithAlgorithmAsync,
  recoverWithGrid,
} from "./pixelation-algorithm-registry.ts";
import { resizeBox, resizeNearest } from "./resize.ts";
import { samplePixelation } from "./sampling.ts";
import {
  OutlinePrepass,
  PixelationDither,
  PixelationMethod,
  PixelationMode,
  PixelationAlgorithm,
} from "./types.ts";
import type {
  PixelateOptions,
  PixelationSize,
  PixelGridAnalysis,
} from "./types.ts";

const WORKING_SCALE = 4;
const MAX_WORKING_PIXELS = 1_048_576;
const MAX_OUTLINE_STRENGTH = 100;
function prepareSource(
  image: PixelBuffer,
  target: PixelationSize,
  outlineStrength: number,
): PixelBuffer {
  const scale = Math.min(
    WORKING_SCALE,
    Math.sqrt(MAX_WORKING_PIXELS / (target.width * target.height)),
  );
  const width = Math.min(image.width, Math.max(1, Math.ceil(target.width * scale)));
  const height = Math.min(image.height, Math.max(1, Math.ceil(target.height * scale)));
  const working =
    image.width === width && image.height === height
      ? image
      : resizeBox(image, width, height, "premultiplied");
  return protectPixelationContours(working, outlineStrength);
}
function uniformBlocks(image: PixelBuffer, target: PixelationSize): PixelGridAnalysis {
  return {
    ...blockPartition(image, target.width, target.height),
    confidence: 1,
    reliable: true,
    algorithm: PixelationAlgorithm.UniformGrid,
  };
}
function sampleImage(
  image: PixelBuffer,
  options: PixelateOptions,
  method: PixelationMethod,
): PixelBuffer {
  // Grid recovery runs when asked for, or when only an algorithm was named and it finds a reliable grid.
  const wantsGrid =
    options.mode === PixelationMode.RecoverGrid ||
    (options.mode === undefined && options.algorithm !== undefined);
  const grid =
    options.grid ??
    (wantsGrid
      ? detectWithAlgorithm(image, options.algorithm ?? PixelationAlgorithm.Auto)
      : undefined);
  const mode =
    options.mode ??
    (grid && (!("reliable" in grid) || grid.reliable)
      ? PixelationMode.RecoverGrid
      : PixelationMode.Convert);
  if (mode !== PixelationMode.Convert && mode !== PixelationMode.RecoverGrid)
    throw new RangeError("Unknown pixelation mode.");
  const prepass = options.prepass ?? OutlinePrepass.None;
  const guide =
    prepass === OutlinePrepass.PixeloeLines ? (options.lineGuide ?? DEFAULT_LINE_GUIDE) : undefined;
  if (mode === PixelationMode.RecoverGrid) {
    const found = grid ?? detectWithAlgorithm(image, options.algorithm ?? PixelationAlgorithm.Auto);
    if ("reliable" in found && !found.reliable)
      throw new Error(
        "No consistent pixel grid was detected. Turn off Automatic grid and choose cell sizes.",
      );
    const cell = (found.cellWidth + found.cellHeight) / 2;
    const analysis = found as PixelGridAnalysis;
    const upright = prepareGridSampling(image, analysis);
    const gridForRecover = { ...analysis, rotation: undefined, sampling: undefined };
    // Custom size's even blocks with PixelOE + Contrast: stock PixelOE to that size.
    if (runsStockPixeloe({ ...options, mode }, found))
      return runPixeloe(upright, { width: found.width, height: found.height }, guide);
    return recoverWithGrid(
      applyOutlinePrepass(upright, cell, prepass, options.lineGuide),
      gridForRecover,
      options.colorPicker,
    );
  }
  const target = resolveTargetSize(image, options);
  // PixelOE + Contrast without a recovered grid is stock PixelOE: the reference result.
  if (runsStockPixeloe({ ...options, mode }, undefined)) return runPixeloe(image, target, guide);
  // Otherwise an independent pre-pass; whatever sampler or colour picker follows works on its result.
  image = applyOutlinePrepass(
    image,
    (image.width / target.width + image.height / target.height) / 2,
    prepass,
    options.lineGuide,
  );
  const strength = options.outlineStrength ?? 0;
  if (!Number.isFinite(strength) || strength < 0 || strength > MAX_OUTLINE_STRENGTH)
    throw new RangeError("Outline protection must be between 0 and 100.");
  if (options.blockPicker)
    return recoverWithGrid(image, uniformBlocks(image, target), options.colorPicker);
  const alphaMode = options.alphaMode ?? "straight";
  if (alphaMode !== "straight" && alphaMode !== "premultiplied")
    throw new RangeError("alphaMode must be 'straight' or 'premultiplied'");
  const prepared =
    strength || method === PixelationMethod.Dominant || method === PixelationMethod.Structure
      ? prepareSource(image, target, strength)
      : image;
  const { width, height } = target;
  let sampled: PixelBuffer;
  switch (method) {
    case PixelationMethod.Nearest:
      sampled = resizeNearest(prepared, width, height);
      break;
    case PixelationMethod.Box:
      sampled = resizeBox(prepared, width, height, alphaMode);
      break;
    case PixelationMethod.MostFrequent:
      sampled = resizeMostFrequent(prepared, width, height);
      break;
    default:
      sampled = samplePixelation(prepared, width, height, method);
  }
  return settlePixelAlpha(image, sampled);
}

function sizeFromBlock(blockSize: number | PixelationSize, image: PixelBuffer): PixelationSize {
  if (typeof blockSize === "number") {
    assertDimension(blockSize, "blockSize");
    return {
      width: Math.max(1, Math.ceil(image.width / blockSize)),
      height: Math.max(1, Math.ceil(image.height / blockSize)),
    };
  }
  if (!blockSize || typeof blockSize !== "object")
    throw new TypeError("blockSize must be a positive number or size");
  assertDimension(blockSize.width, "blockSize.width");
  assertDimension(blockSize.height, "blockSize.height");
  return {
    width: Math.max(1, Math.ceil(image.width / blockSize.width)),
    height: Math.max(1, Math.ceil(image.height / blockSize.height)),
  };
}

function resolveTargetSize(image: PixelBuffer, options: PixelateOptions): PixelationSize {
  const hasTargetFields = options.targetWidth !== undefined || options.targetHeight !== undefined;
  const hasTargetObject = options.targetSize !== undefined;
  if (hasTargetFields && hasTargetObject)
    throw new RangeError("Use a target size object or targetWidth/targetHeight, not both");
  if (
    (options.targetWidth !== undefined || options.targetHeight !== undefined) &&
    options.blockSize !== undefined
  ) {
    throw new RangeError("Use target dimensions or blockSize, not both");
  }
  if (options.targetSize && options.blockSize !== undefined) {
    throw new RangeError("Use target dimensions or blockSize, not both");
  }

  if (options.blockSize !== undefined) return sizeFromBlock(options.blockSize, image);
  const targetObject = options.targetSize;
  const targetWidth = targetObject?.width ?? options.targetWidth;
  const targetHeight = targetObject?.height ?? options.targetHeight;
  if (targetWidth === undefined && targetHeight === undefined)
    return { width: image.width, height: image.height };
  if (targetWidth !== undefined) assertDimension(targetWidth, "targetWidth");
  if (targetHeight !== undefined) assertDimension(targetHeight, "targetHeight");
  if (targetWidth === undefined) {
    return {
      width: Math.max(1, Math.round((image.width * (targetHeight as number)) / image.height)),
      height: targetHeight as number,
    };
  }
  if (targetHeight === undefined) {
    return {
      width: targetWidth,
      height: Math.max(1, Math.round((image.height * targetWidth) / image.width)),
    };
  }
  return { width: targetWidth, height: targetHeight };
}

function validateMethod(value: PixelationMethod | undefined): PixelationMethod {
  const method = value ?? PixelationMethod.Nearest;
  if (!Object.values(PixelationMethod).includes(method))
    throw new RangeError("Unknown pixelation method.");
  return method;
}

function finishPixelation(
  sampled: PixelBuffer,
  source: PixelBuffer,
  { removeNoise, paletteSnap, preserveDimensions }: PixelateOptions,
): PixelBuffer {
  let result = removeNoise ? smoothPixelation(sampled) : sampled;
  if (paletteSnap) result = snapPalette(result, paletteSnap);
  if (removeNoise) {
    const dither = paletteSnap?.dither;
    const dithered = dither === PixelationDither.Ordered || dither === PixelationDither.FloydSteinberg;
    result = removeOrphanPixels(result, { absorbInterior: !dithered });
  }
  if (preserveDimensions && (result.width !== source.width || result.height !== source.height))
    result = resizeNearest(result, source.width, source.height);
  return result;
}

/**
 * Pixelate an RGBA buffer without touching the source. Nearest mode follows
 * nearest-neighbor `floor(dst * src / dst)` mapping. Box mode averages the
 * source area covered by each destination pixel. Local dominant and structural
 * sampling preserve contrasting regions; grid recovery restores one RGBA pixel
 * per detected cell. Limiting colours keeps each pixel's own alpha.
 */
export function pixelateImage(image: PixelBuffer, options: PixelateOptions = {}): PixelBuffer {
  assertPixelBuffer(image);
  const method = validateMethod(options.method);
  return finishPixelation(sampleImage(image, options, method), image, options);
}

async function sampleImageAsync(
  image: PixelBuffer,
  options: PixelateOptions,
  method: PixelationMethod,
): Promise<PixelBuffer> {
  const wantsGrid =
    options.mode === PixelationMode.RecoverGrid ||
    (options.mode === undefined && options.algorithm !== undefined);
  const grid =
    options.grid ??
    (wantsGrid
      ? await detectWithAlgorithmAsync(image, options.algorithm ?? PixelationAlgorithm.Auto)
      : undefined);
  const mode =
    options.mode ??
    (grid && (!("reliable" in grid) || grid.reliable)
      ? PixelationMode.RecoverGrid
      : PixelationMode.Convert);
  if (mode !== PixelationMode.Convert && mode !== PixelationMode.RecoverGrid)
    throw new RangeError("Unknown pixelation mode.");
  const prepass = options.prepass ?? OutlinePrepass.None;
  const guide =
    prepass === OutlinePrepass.PixeloeLines ? (options.lineGuide ?? DEFAULT_LINE_GUIDE) : undefined;
  if (mode === PixelationMode.RecoverGrid) {
    const found =
      grid ??
      (await detectWithAlgorithmAsync(image, options.algorithm ?? PixelationAlgorithm.Auto));
    if ("reliable" in found && !found.reliable)
      throw new Error(
        "No consistent pixel grid was detected. Turn off Automatic grid and choose cell sizes.",
      );
    const cell = (found.cellWidth + found.cellHeight) / 2;
    const analysis = found as PixelGridAnalysis;
    const upright = prepareGridSampling(image, analysis);
    const gridForRecover = { ...analysis, rotation: undefined, sampling: undefined };
    if (runsStockPixeloe({ ...options, mode }, found))
      return runPixeloe(upright, { width: found.width, height: found.height }, guide);
    return recoverWithGrid(
      applyOutlinePrepass(upright, cell, prepass, options.lineGuide),
      gridForRecover,
      options.colorPicker,
    );
  }
  // Convert path is sync — reuse sampleImage body for non-recover.
  return sampleImage(image, { ...options, grid: undefined, mode: PixelationMode.Convert }, method);
}

/**
 * Async pixelate for product Auto path (import-worker). Same output as pixelateImage;
 * Auto detect overlaps WASM AC+RL with proposers via Promise join (no COOP/COEP).
 */
export async function pixelateImageAsync(
  image: PixelBuffer,
  options: PixelateOptions = {},
): Promise<PixelBuffer> {
  assertPixelBuffer(image);
  const method = validateMethod(options.method);
  const sampled = await sampleImageAsync(image, options, method);
  return finishPixelation(sampled, image, options);
}
