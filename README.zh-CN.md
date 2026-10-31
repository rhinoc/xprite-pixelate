# @xprite/pixelate

[![npm](https://img.shields.io/npm/v/@xprite/pixelate)](https://www.npmjs.com/package/@xprite/pixelate)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](https://github.com/rhinoc/xprite-pixelate/blob/main/README.md) | 简体中文

| AI 生成，887×887 | 找到的网格 | 真正的像素画，48×49 |
| :---: | :---: | :---: |
| ![输入](docs/images/griffith-input.png) | ![网格](docs/images/griffith-mesh.png) | ![结果](docs/images/griffith-result.png) |

## 简介

图像生成模型画出的“像素画”边缘发虚，有噪点，轮廓半透明，每一格的宽度也不一样。这个包找出图里真正的像素网格，每一格还原成一个干净的像素。它也能把普通图片转成像素画。

它可以在浏览器和 Node 中运行，没有运行时依赖，包内自带一个 WebAssembly 模块。它是像素编辑器 [Xprite](https://xprite.cc) 的导入器。

## 目录

- [示例](#示例)
- [与其他工具对比](#与其他工具对比)
- [安装](#安装)
- [用法](#用法)
- [原理](#原理)
- [基准测试](#基准测试)
- [许可证](#许可证)

## 示例

下面的输入来自基准测试的 AI 套件：把 CC0 像素画按生成模型的方式渲染成假像素画。每个结果的尺寸都和原画完全一致。

### 一张画布上的两个角色

- 哥布林，作者 LuizMelo（[Monsters Creatures Fantasy](https://luizmelo.itch.io/monsters-creatures-fantasy)，CC0）

| 输入，1800×845 | 找到的网格 | 结果，103×49 |
| :---: | :---: | :---: |
| ![输入](docs/images/goblins-input.png) | ![网格](docs/images/goblins-mesh.png) | ![结果](docs/images/goblins-result.png) |

### 格内有绘画式明暗

- 娜迦法师，来自 [Dungeon Crawl Stone Soup tiles](https://github.com/crawl/tiles)（CC0）

| 输入，411×425 | 找到的网格 | 结果，50×50 |
| :---: | :---: | :---: |
| ![输入](docs/images/naga-input.png) | ![网格](docs/images/naga-mesh.png) | ![结果](docs/images/naga-result.png) |

### 格子漂移和抖动

- 怪物，作者 Denzi（[Denzi's public domain art](https://opengameart.org/content/denzis-public-domain-art)，CC0）

| 输入，606×924 | 找到的网格 | 结果，45×67 |
| :---: | :---: | :---: |
| ![输入](docs/images/wobble-input.png) | ![网格](docs/images/wobble-mesh.png) | ![结果](docs/images/wobble-result.png) |

### 小格子和 WebP 压缩损伤

- 老人，作者 ansimuz（[Gothicvania Town](https://opengameart.org/content/gothicvania-town)，CC0）

| 输入，250×380 | 找到的网格 | 结果，39×57 |
| :---: | :---: | :---: |
| ![输入](docs/images/oldman-input.png) | ![网格](docs/images/oldman-mesh.png) | ![结果](docs/images/oldman-result.png) |

## 与其他工具对比

顶部那张图，各工具用默认设置还原的结果：

| Xprite Auto，48×49 | [pixel-art-fixer](https://github.com/Retro-Diffusion/pixel-art-fixer)，47×48 | [perfectPixel](https://github.com/theamusing/perfectPixel)，50×50 | [proper-pixel-art](https://github.com/KennethJAllen/proper-pixel-art)，53×54 |
| :---: | :---: | :---: | :---: |
| ![Xprite](docs/images/griffith-result.png) | ![pixel-art-fixer](docs/images/griffith-fixer.png) | ![perfectPixel](docs/images/griffith-perfectpixel.png) | ![proper-pixel-art](docs/images/griffith-proper.png) |

这张图的格宽在 15 到 21 像素之间，所以等宽网格总会在某处切进画好的像素。Xprite 把每一刀都切在颜色边缘上。1746 个用例的得分见[基准测试](#基准测试)。

## 安装

```bash
npm install @xprite/pixelate
```

## 用法

图像是 `{ width, height, data }`，`data` 是逐行排列的 RGBA 字节，alpha 未预乘。canvas 的 `ImageData` 就是这个结构。

### 还原网格

```ts
import {
  CellColorPicker,
  PixelationAlgorithm,
  PixelationMode,
  detectWithAlgorithm,
  pixelateImage,
  preloadWasm,
} from "@xprite/pixelate";

await preloadWasm(); // 可选：在处理第一张图之前加载格数检测器

const image = { width, height, data: new Uint8ClampedArray(rgba) };

const grid = detectWithAlgorithm(image, PixelationAlgorithm.Auto);
if (grid.reliable) {
  const art = pixelateImage(image, {
    mode: PixelationMode.RecoverGrid,
    grid,
    colorPicker: CellColorPicker.TwoStage,
    paletteSnap: { adaptive: true }, // 合并生成模型留下的相近色
  });
  // art.width × art.height 是原生尺寸：每个格子一个像素。
}
```

图里没有一致的网格时（照片、手绘，或本来就是 1× 的像素画），`grid.reliable` 为 false，`RecoverGrid` 模式会对这种网格抛出错误。这类图片请用 `Convert` 模式。

### 转换图片

```ts
const art = pixelateImage(photo, {
  mode: PixelationMode.Convert,
  targetSize: { width: 64, height: 64 },
  paletteSnap: { colors: 16 },
});
```

### 去除纯色背景

```ts
import { removeBackground } from "@xprite/pixelate";

const clear = removeBackground(image); // 以边框上最常见的颜色为键
```

生成模型画了白色或棋盘格背景时，先调用它，再检测网格。

### 选项

`pixelateImage(image, options)`：

| 选项 | 说明 |
| --- | --- |
| `mode` | `RecoverGrid` 使用检测到的网格；`Convert` 按给定尺寸生成像素画。 |
| `grid` | `detectWithAlgorithm` 返回的网格。省略时用 `algorithm` 检测。 |
| `algorithm` | 网格检测器。`Auto` 运行全部检测器并选出一个网格。 |
| `colorPicker` | 每格的取色规则：`TwoStage`、`MostCommon`（默认）、`Median`、`Average`、`KMeans`、`Contrast` 等。 |
| `targetSize`、`targetWidth`、`targetHeight`、`blockSize` | `Convert` 模式的输出尺寸。 |
| `paletteSnap` | 限制颜色：`{ adaptive: true }`、`{ colors: 16 }` 或 `{ palette: [...] }`，可选 `dither`。 |
| `prepass` | 来自 PixelOE 的轮廓预处理（`Pixeloe`、`PixeloeLines`）。 |
| `removeNoise` | 对相近的相邻颜色做轻度平滑。 |
| `preserveDimensions` | 用最近邻把结果放大回原图尺寸。 |

所有选项见 [`src/types.ts`](src/types.ts)。

### Worker

`detectWithAlgorithm` 和 `pixelateImage` 是同步函数，大图可能要几秒，请在 Web Worker 中运行。在浏览器中，Auto 还可以把格数检测器放进嵌套 Worker，和其他检测器并行：

```ts
import { setAcRlBrowserWorkerFactory, detectWithAlgorithmAsync } from "@xprite/pixelate";

setAcRlBrowserWorkerFactory(
  () =>
    new Worker(
      new URL("@xprite/pixelate/wasm/ac-rl-detect-browser-worker.js", import.meta.url),
      { type: "module" },
    ),
);
const grid = await detectWithAlgorithmAsync(image);
```

在 Node 中，检测器会自己从 `wasm/ac-rl-detect-worker.mjs` 启动一个 `worker_threads` Worker。设置 `XPRITE_AC_RL_WORKER=0` 可以让它留在调用线程。

## 原理

1. **扶正。** Auto 先估计倾斜角。倾斜明确时，在扶正后的副本上检测。
2. **提议。** 七个检测器提议网格：均匀网格、边缘网格、边框晶格、格距晶格、颜色周期、边界游程和边缘间距。pixel-art-fixer 的自相关与游程投票移植成 WebAssembly，给出一个独立的格数。
3. **沿边缘切。** 在检测器保留的每个格宽上，动态规划沿每条轴走一遍，把每一刀切在颜色边缘上。每格宽度保持在格宽的 0.75 到 1.25 倍之间，宽度变化另有代价。这一步处理宽度不均的格子。
4. **过滤。** 候选网格的切线若没有落在更粗网格所跟随的颜色边缘上，就被剔除。
5. **选择。** 描述图像所需比特数最少的网格胜出（最小描述长度）。没有锁定到内容相位的网格要付出额外代价。漂移和错位的行读作条带位移或相位场。
6. **取色。** 每格取一个颜色（`TwoStage` 分两步归并格内颜色），自适应调色板再合并近似色。
7. **整理透明度。** 被画覆盖的格子变为完全不透明，画外的格子变为透明。

`src/` 中每个源文件都说明了自己负责的步骤，见 [`src/`](src)。

## 基准测试

[`bench/`](bench) 在 CC0 原生像素画上比较本包和另外三个工具。基准测试以已知方式损伤原画，再把每个结果和原画对比打分。每个工具都使用默认设置。

AI 套件（1746 个用例，按生成模型伪造像素画的方式渲染）：

| 方法 | 尺寸完全正确 | 差 1 格以内 | 像素一致率 | ΔE | 半透明毛边 | 中位耗时 |
| --- | --- | --- | --- | --- | --- | --- |
| Xprite Auto | **83.6%** | **90.0%** | **99.8%** | 0.82 | 0.1% | 1.55 s |
| pixel-art-fixer | 49.7% | 80.9% | 98.3% | 1.74 | 0.0% | 0.18 s |
| perfectPixel | 53.3% | 68.0% | 96.7% | 2.42 | - | 0.03 s |
| proper-pixel-art | 72.2% | 80.4% | 99.7% | **0.64** | 0.0% | 0.49 s |

[pixel-bench](https://github.com/Retro-Diffusion/pixel-bench) v1 套件（7651 个放大和有损处理用例）：

| 方法 | 尺寸完全正确 | 差 1 格以内 | 像素一致率 | ΔE | 中位耗时 |
| --- | --- | --- | --- | --- | --- |
| Xprite Auto | **87.1%** | **90.1%** | 94.3% | **2.79** | 0.24 s |
| pixel-art-fixer | 77.8% | 83.5% | **94.4%** | 2.83 | 0.04 s |
| perfectPixel | 24.2% | 32.9% | 89.7% | 4.31 | 0.002 s |
| proper-pixel-art | 16.5% | 28.6% | 93.0% | 3.85 | 0.05 s |

像素一致率和 ΔE 只在尺寸完全正确的用例上统计。四个工具中 Xprite 最慢。损伤是合成的，所以得分反映各工具在这些特征上的排名，不代表在真实图片上的成功率。方法、类别和运行步骤见 [bench/README.md](bench/README.md)。

## 许可证

MIT。部分代码改编自 pixel-art-fixer、PixelOE、proper-pixel-art 和 tensorhead/dithering（见 [NOTICE.md](NOTICE.md)）。示例图均为 CC0（见 [bench/corpus/CREDITS.md](bench/corpus/CREDITS.md)）。
