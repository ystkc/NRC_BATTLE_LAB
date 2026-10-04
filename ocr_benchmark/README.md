# OCR Benchmark

本目录用于比较 `test.png` 上的全图 OCR 与局部区域 OCR。脚本、JSON 结果、局部裁剪预览和全图可视化产物均保存在当前目录。

## 环境

- 推理方式：CPU 推理
- 处理器：Intel Core i5-13500H
- 内存：16 GB DDR4 4266 MHz
- 测试图片：`test.png`，尺寸 `1558 × 974`
- 统计日期：2026-10-03

## 全图识别结果

数据文件：`full_image_results.json`

每个引擎重复识别 3 次；平均耗时只统计推理耗时，不包含初始化。字符、数字和文本准确率均由 `ocr_benchmark_common.py` 中的编辑距离评分逻辑计算。

| 引擎 | 平均耗时 | 字符准确率 | 数字准确率 | 文本准确率 |
|---|---:|---:|---:|---:|
| PixPin OCR | 2421.9 ms | 11.6% | 8.8% | 18.6% |
| RapidOCR | 1758.5 ms | 64.0% | 70.6% | 69.8% |
| EasyOCR | 3697.9 ms | 40.7% | 58.8% | 48.8% |
| PaddleOCR | 31267.5 ms | 64.0% | 88.2% | 62.8% |
| WinRT OCR | 59.4 ms | 0.0% | 0.0% | 0.0% |

全图结果表明：PaddleOCR 的数字准确率最高，但耗时也最高；RapidOCR 在耗时和整体文本准确率之间更均衡；WinRT OCR 本次全图结果未识别出文本。

## 全图可视化

每个引擎对应一张 `test.png` 可视化结果图。绿色表示置信度不低于 `0.80`，橙色表示 `0.50–0.79`，红色表示低于 `0.50`，灰色或 `N/A` 表示没有置信度信息。

| 引擎 | 图片 |
|---|---|
| PixPin OCR | ![PixPin OCR](visualizations/ocr_service.jpg) |
| RapidOCR | ![RapidOCR](visualizations/rapidocr.jpg) |
| EasyOCR | ![EasyOCR](visualizations/easyocr.jpg) |
| PaddleOCR | ![PaddleOCR](visualizations/paddleocr.jpg) |
| WinRT OCR | ![WinRT OCR](visualizations/winrt_ocr.jpg) |

清单文件：`visualizations/manifest.json`

## 局部识别结果

数据文件：`region_results.json`

局部实验已完成，共定义 16 个固定区域、96 条识别记录：

- PixPin OCR：16 个区域 × `native`、`x3` 两种版本，共 32 条记录。
- RapidOCR：16 个区域 × `color_x3`、`gray_x3`、`contrast_x3` 三种版本，共 48 条记录。
- WinRT OCR：16 个区域 × `x3` 版本，共 16 条记录。

局部识别的 `numeric_exact` 表示区域中的数字/符号串是否完全匹配；`text_edit_distance` 和 `numeric_edit_distance` 越小越好。局部结果不直接与全图字符准确率横向等价，因为每个区域的预期文本长度和评分方式不同。

### 局部区域定义

坐标格式为 `(x, y, width, height)`。

| 区域 | 坐标 | 预期内容 |
|---|---|---|
| `left_header` | `(86, 29, 169, 62)` | 画间沉铁兽 60级 490/490 |
| `right_header` | `(1359, 29, 162, 60)` | 恶魔狼 60级 100% |
| `left_energy` | `(203, 87, 41, 26)` | ★10 |
| `right_energy` | `(1359, 84, 44, 29)` | ★10 |
| `skill_1` | `(245, 407, 94, 29)` | 连续爪击 |
| `skill_2` | `(224, 516, 84, 32)` | 反击拳 |
| `skill_3` | `(238, 629, 89, 32)` | 幻象 |
| `skill_4` | `(294, 725, 106, 41)` | 鼓劲 |
| `energy_1` | `(251, 334, 45, 32)` | ★2 |
| `energy_2` | `(214, 447, 50, 34)` | ★2 |
| `energy_3` | `(222, 569, 52, 28)` | ★1 |
| `energy_4` | `(277, 669, 49, 36)` | ★3 |
| `power_1` | `(292, 390, 47, 29)` | 37 |
| `power_2` | `(260, 498, 54, 28)` | 62 |
| `power_3` | `(274, 607, 55, 32)` | 30 |
| `power_4` | `(331, 708, 58, 29)` | -- |

### 局部识别汇总

下表按引擎和版本汇总 16 个区域的结果；平均耗时为单个区域单次识别耗时。

| 引擎 | 版本 | 区域数 | 平均耗时 | 数字完全匹配率 | 平均数字编辑距离 | 平均文本编辑距离 |
|---|---|---:|---:|---:|---:|---:|
| PixPin OCR | native | 16 | 1216.4 ms | 68.8% | 0.38 | 0.81 |
| PixPin OCR | x3 | 16 | 1753.5 ms | 75.0% | 0.31 | 0.50 |
| RapidOCR | color_x3 | 16 | 1025.7 ms | 37.5% | 1.25 | 1.88 |
| RapidOCR | gray_x3 | 16 | 781.7 ms | 43.8% | 1.19 | 1.75 |
| RapidOCR | contrast_x3 | 16 | 830.7 ms | 50.0% | 1.06 | 1.50 |
| WinRT OCR | x3 | 16 | 474.7 ms | 50.0% | 1.19 | 2.00 |

按引擎合并不同版本后，PixPin OCR 的数字完全匹配率为 71.9%（32 条），RapidOCR 为 43.8%（48 条），WinRT OCR 为 50.0%（16 条）。在 PixPin OCR 的两种版本中，`x3` 的数字匹配率高于 `native`；RapidOCR 的 `contrast_x3` 在三种版本中数字匹配率最高。

## 脚本

- `run_full_image_experiment.py`：运行全图识别实验，写入 `full_image_results.json`。
- `plot_full_image_experiment.py`：根据全图 JSON 绘制检测框和置信度。
- `run_region_experiment.py`：运行局部区域识别实验，写入 `region_results.json`。
- `plot_region_preview.py`：只生成局部裁剪预览和 contact sheet，不执行识别。
- `ocr_benchmark_common.py`：共享区域坐标、评分和 OCR 适配逻辑。
- `winrt_ocr.ps1`：WinRT OCR 内部调用辅助脚本。

## 使用方法

生成或刷新局部区域预览：

```powershell
d:\python\python.exe .\plot_region_preview.py
```

手动运行局部实验。默认运行配置中的全部引擎，每个区域每个引擎识别 1 次：

```powershell
d:\python\python.exe .\run_region_experiment.py
```

也可以只运行指定引擎：

```powershell
d:\python\python.exe .\run_region_experiment.py --engines rapidocr,winrt
```

全图实验只在需要重新采样时运行：

```powershell
d:\python\python.exe .\run_full_image_experiment.py --repeats 3
d:\python\python.exe .\plot_full_image_experiment.py
```
