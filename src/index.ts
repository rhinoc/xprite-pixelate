export { analyzePixelArt, analyzePixelArtAsync } from "./analyze.ts";
export {
  extractPalette,
  extractPixelationPalette,
  countDistinctColors,
  reduceToPalette,
} from "./palette.ts";
export { snapPalette } from "./palette-snap.ts";
export { estimateTilt, straighten, MAX_TILT_DEGREES } from "./deskew.ts";
export { resizeNearest } from "./resize.ts";
export { pixelateImage, pixelateImageAsync } from "./pixelate.ts";
export {
  PixelArtClassification,
  PixelationMethod,
  PixelationMode,
  PixelationAlgorithm,
  CellColorPicker,
  LineGuideMode,
  OutlinePrepass,
  PixelationDither,
  PaletteColorMode,
  PixelGridSamplingAxis,
} from "./types.ts";
export {
  DEFAULT_LINE_GUIDE,
  readOutlinePrepass,
  runsStockPixeloe,
} from "./outline-prepass.ts";
export type {
  ExtractPaletteOptions,
  PaletteEntry,
  PixelArtAnalysis,
  PixelArtAnalysisOptions,
  PixelArtMetrics,
  PaletteSnapOptions,
  PixelateOptions,
  PixelationSize,
  PixelationSettings,
  PixelGridGeometry,
  PixelGridAnalysis,
  PixelGridSamplingStage,
} from "./types.ts";

export {
  defaultPixelationSettings,
  updatePixelationSettings,
  applyPixelationGrid,
  pixelationSizeFromAxis,
  pixelationSettingsOptions,
  MAX_PIXELATION_SIZE,
  PIXELATION_SIZES,
  PIXELATION_METHOD_OPTIONS,
} from "./settings.ts";

export { manualPixelGrid, MAX_GRID_CELL_SIZE } from "./grid.ts";

export {
  removeBackground,
  modeBorderColor,
  edgeSeededFloodAlpha,
  colorKeyDistance,
  adaptiveTolerance,
  sampleKeyColor,
  RemoveBackgroundMode,
  DEFAULT_REMOVE_BACKGROUND,
} from "./remove-background.ts";
export type {
  RemoveBackgroundOptions,
  RemoveBackgroundSettings,
} from "./remove-background.ts";

export {
  getAlgorithmEntry,
  getAllAlgorithms,
  getListedAlgorithms,
  getGridSources,
  pixelationMethodOf,
  detectWithAlgorithm,
  detectWithAlgorithmAsync,
  type PixelationAlgorithmEntry,
} from "./pixelation-algorithm-registry.ts";

export {
  getAllColorPickers,
  getColorPickerEntry,
  type CellColorPickerEntry,
} from "./cell-color-picker.ts";

export {
  preloadWasm,
  beginAcRlConsensusJob,
  finishAcRlConsensusJob,
  beginAcRlConsensusJobAsync,
  finishAcRlConsensusJobAsync,
  setAcRlBrowserWorkerFactory,
  warmAcRlBrowserWorker,
  acRlWorkerOverlapActive,
  acRlBrowserWorkerOverlapActive,
} from "./grid-ac-rl-consensus.ts";
