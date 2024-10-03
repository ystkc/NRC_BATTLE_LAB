# PixPin OCR Service

这是一个x64 Windows可执行文件，它调用PixPin 3.5.5.1中的本地OCR实现，并返回JSON格式的结果。

该桥接程序使用 Windows 命名管道，以 BGRA32 原始像素直接通信，并返回 UTF-8 JSON。

## 构建

如果需要从源代码构建，在 x64 MinGW 环境中：

~~~powershell
g++ -std=c++17 -O2 -o ocr_service\\pixpin_ocr_service.exe ocr_service\\main.cpp
~~~

或：

~~~powershell
cmake -S ocr_service -B ocr_service\\build -G Ninja
cmake --build ocr_service\\build --config Release
~~~

## 配置 PixPin 路径

优先级从低到高为：

1. 可执行文件旁的 pixpin-ocr.ini。
2. PIXPIN_DIR 环境变量。
3. --config 指定的配置文件。
4. --pixpin-dir 命令行参数。

示例：

~~~powershell
.\\ocr_service\\pixpin_ocr_service.exe --pixpin-dir D:\\Apps\\PixPin
~~~

也可以修改 pixpin-ocr.ini 中的 pixpin_dir。服务启动后会打印命名管道名称。

配置中的 `timeout_ms` 是单次 OCR 的最长保护时间，不是固定等待时间。OCR 正常完成后，服务会立即唤醒超时监控线程并返回结果，不会继续等待剩余的超时时间。

## 通信方式

默认管道：

~~~text
\\.\pipe\pixpin-ocr
~~~

输入优先使用裁剪后的 BGRA32 原始像素，不需要 JPEG。客户端应保持连接并连续发送固定头 + 像素负载；服务端返回固定响应头 + UTF-8 JSON。

服务支持多个客户端并发连接。为了避免未经验证的 PixOCR2 全局状态发生竞态，OCR 任务由独立线程串行执行；连接处理、读取、排队和响应可以并发进行。实时视频客户端建议使用“最新帧覆盖”策略，而不是把每一帧都排入队列。

## 通信协议

### 协议设计

服务使用 Windows Named Pipe：

~~~text
\\.\pipe\pixpin-ocr
~~~

它适合本机屏幕录制程序，避免 HTTP/TCP 的端口管理和文本 Base64 开销。一个客户端连接可以连续发送多个请求；服务端同时接受多个客户端连接。OCR 核心由于 PixOCR2/Qt ABI 的线程安全性没有官方保证，内部采用有界队列和单独 OCR 线程执行，多个客户端可以并发提交，但核心任务按队列顺序安全处理。

### 图像格式

当前高效路径只接受 BGRA32 原始像素：

- `format = 1`。
- 每像素 4 字节，内存顺序为 `B、G、R、A`。
- `stride` 可以大于 `width * 4`，服务端会去除每行 padding。
- `payloadBytes` 必须等于 `stride * height`。
- `width`、`height` 和 `stride` 使用 little-endian `uint32`。

对于屏幕录制程序，推荐直接从解码后的帧裁剪 BGRA/RGBA，再转换为 BGRA 后发送。不要先把原始帧编码成 JPG，再让服务端解码；这会增加一次 JPEG 编码、一次解码、CPU 消耗和有损压缩误差。

如果上游本来就只有 JPEG，直接传 JPEG 会比“重新解码成原始帧再编码”更合理，但当前服务的高效协议优先实现了原始 BGRA 路径。后续可以增加 `format = 2` 的 JPEG 兼容分支，但不应把它作为本机高帧率默认路径。

### 请求头

固定 32 字节，按 1 字节对齐：

~~~text
uint32 magic       = 0x3152434f  // ASCII OCR1 的 little-endian 表示
uint16 version     = 1
uint16 format      = 1           // BGRA32
uint32 width
uint32 height
uint32 stride
uint32 payloadBytes
uint64 requestId
uint8  payload[payloadBytes]
~~~

### 响应头

固定 32 字节：

~~~text
uint32 magic       = 0x3153434f  // ASCII OCS1 的 little-endian 表示
uint16 version     = 1
uint16 reserved    = 0
uint32 status       // 0 成功，1 请求错误，2 队列满，3 OCR 错误，4 超时，5 服务错误
uint32 width
uint32 height
uint32 jsonBytes
uint64 requestId
uint8  json[jsonBytes]
~~~

JSON 是 UTF-8。成功时结构为：

~~~json
{"ok":true,"image":{"width":123,"height":45},"result":{}}
~~~

### 性能建议

1. 保持命名管道连接，不要每帧重新连接。
2. 只发送裁剪后的区域，不发送完整屏幕。
3. 使用 BGRA32，避免 PNG/JPEG 编码。
4. 控制队列深度；实时视频通常应丢弃过期帧，而不是无限排队。
5. 如果 OCR 延迟高于帧间隔，应在客户端只保留最新帧，避免识别结果滞后。
6. 如果以后需要跨机器传输，再考虑 TCP + JPEG/WebP/共享内存，而不是在本机路径上牺牲无损原始帧性能。


## 示例客户端

### C++

构建后运行：

~~~powershell
.\ocr_service\pixpin_ocr_example_client.exe --input D:\PixPin\model\normal.jpg
~~~

指定裁剪区域，并在同一个命名管道连接上连续发送 3 次：

~~~powershell
.\ocr_service\pixpin_ocr_example_client.exe --input .\frame.png --crop 100 80 800 300 --repeat 3
~~~

### Python

Python 示例使用 Pillow 读取 JPG/PNG/BMP，并把 RGBA 转换成协议要求的 BGRA32：

~~~powershell
python -m pip install Pillow
python .\ocr_service\example_client.py --input .\frame.jpg
~~~

裁剪并复用同一条管道连接：

~~~powershell
python .\ocr_service\example_client.py --input .\frame.png --crop 100 80 800 300 --repeat 3
~~~

JSON 输出到标准输出，状态和 requestId 输出到标准错误。屏幕录制程序可以复用示例中的 request() 逻辑，把 Pillow 图像替换成录屏库提供的 BGRA 缓冲区；不要再次编码成 JPG。

### Python 分阶段测速

客户端支持对两种输入处理方案测速：

~~~powershell
python .\example_client.py --input .\test.png --benchmark --benchmark-mode both --benchmark-repeat 3
~~~

- `bgra`：按普通路径执行 `RGBA -> BGRA`。
- `no-alpha`：输入先转换为 RGB，去掉原图 Alpha 后补固定 `A=255`，再按协议要求发送 BGRA32。
- `both`：依次执行以上两种方案，默认每种方案先做 1 次不计入统计的预热请求。

当前服务端只接受 BGRA32，因此不能直接发送 3 字节 BGR；`no-alpha` 只比较去除输入 Alpha 的处理成本，线上负载仍然是合法的 BGRA32。

每次测速会输出：读取文件、图像转换、发送 request、等待服务端响应头（包含排队和 OCR 计算）以及读取 response JSON 的耗时。`compute_ms` 是客户端可观测的服务端等待时间，不是服务端内部 OCR 函数的纯 CPU 时间。
