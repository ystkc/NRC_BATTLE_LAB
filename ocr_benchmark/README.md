# OCR Benchmark

本目录用于比较 test.png 上的全图 OCR 和固定 region OCR。所有脚本、JSON、预览图和可视化产物都放在当前目录。

## 环境

- 推理方式：CPU 推理
- 处理器：Intel Core i5-13500H
- 内存：16 GB DDR4 4266 MHz
- 测试图片：test.png，1558 × 974

## 全图结果

数据文件：full_image_results.json

| 引擎 | 平均耗时 | 字符准确率 | 数字准确率 | 文本准确率 |
|---|---:|---:|---:|---:|
| OCR Service | 2735.7 ms | 11.6% | 8.8% | 18.6% |
| RapidOCR | 1783.1 ms | 64.0% | 70.6% | 69.8% |
| EasyOCR | 3496.7 ms | 40.7% | 58.8% | 48.8% |
| PaddleOCR | 33592.4 ms | 64.0% | 88.2% | 62.8% |
| WinRT OCR | 56.6 ms | 0.0% | 0.0% | 0.0% |

以上数据来自 2026-10-03 的全图记录。当前合并 JSON 保存汇总指标和检测数量，不包含原始检测框；下次重新采样后运行绘图脚本即可生成带框版本。

## 可视化

每个引擎对应一张 test.png 可视化图片。绿色表示置信度不低于 0.80，橙色表示 0.50–0.79，红色表示低于 0.50，灰色或 N/A 表示没有置信度信息。

| 引擎 | 图片 |
|---|---|
| OCR Service | ![OCR Service](visualizations/ocr_service.jpg) |
| RapidOCR | ![RapidOCR](visualizations/rapidocr.jpg) |
| EasyOCR | ![EasyOCR](visualizations/easyocr.jpg) |
| PaddleOCR | ![PaddleOCR](visualizations/paddleocr.jpg) |
| WinRT OCR | ![WinRT OCR](visualizations/winrt_ocr.jpg) |

清单文件：visualizations/manifest.json

## Region 状态

数据文件：region_results.json

region 结果当前标记为 stale_pending_manual_run，等待手动执行后再更新实验结论。区域定义使用 (x, y, width, height)，每个引擎只执行 1 次识别，不做 3 次重复采样。region 绘图脚本只生成裁剪预览和 contact sheet，不读取识别结果，也不会把 OCR 文本绘制到图片上。

## 脚本

- run_full_image_experiment.py：全图识别实验，写入 full_image_results.json。
- plot_full_image_experiment.py：根据全图 JSON 绘制检测框和置信度。
- run_region_experiment.py：统一运行 region 实验，写入 region_results.json。
- plot_region_preview.py：只绘制 region 预览，不执行识别。
- ocr_benchmark_common.py：共享区域坐标、评分和 OCR 适配逻辑。
- winrt_ocr.ps1：WinRT OCR 的内部调用辅助脚本。

## 使用方法

生成或刷新 region 预览：

~~~powershell
d:\python\python.exe .\plot_region_preview.py
~~~

手动运行 region 实验。默认会运行配置中的全部引擎，每个 region 每个引擎只识别 1 次：

~~~powershell
d:\python\python.exe .\run_region_experiment.py
~~~

也可以只运行指定引擎：

~~~powershell
d:\python\python.exe .\run_region_experiment.py --engines rapidocr,winrt
~~~

全图实验只有在需要重新采样时才运行：

~~~powershell
d:\python\python.exe .\run_full_image_experiment.py --repeats 3
d:\python\python.exe .\plot_full_image_experiment.py
~~~
