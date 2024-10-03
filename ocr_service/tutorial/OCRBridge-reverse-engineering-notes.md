# PixPin 本地 OCR 逆向与 C++ Bridge 调试笔记

## 1. 目标

PixPin 的 OCR 在本地运行，但原始使用方式依赖截图热键和 GUI。目标不是复制 PixPin，而是复现它调用 PixOCR2.dll 的最小链路，使其他程序可以批量提交图片并快速取得 JSON。大致分为以下三个阶段

1. **能调用**：哪怕依赖 PixPin 界面和剪贴板，也能自动完成一次识别。
2. **能稳定调用**：不依赖鼠标焦点、截图窗口和用户剪贴板。
3. **能高效批量调用**：模型常驻内存，连续请求不必重复启动程序。

最终希望得到能够常驻的 Windows 服务，通过命名管道接收裁剪后的 BGRA32 帧，返回 JSON。


环境：
- 使用 x64dbg 调试。
- Bridge 使用 g++ MSYS2 14.2.0：


主要难点，由于PixPin的DLL并不是标准C API，其中的 Windows x64 ABI 只告诉我们大致的寄存器传参规则，不会自动告诉我们 PixOcrParams、QString 或 QImage 的对象布局。后者必须靠导出、调用点、汇编和运行结果共同确认。


## 2. 阶段一：从安装目录判断 OCR 是否值得复用

### 2.1 观察到的文件线索

最初检查 `D:\PixPin`，发现了：

- `PixOCR.dll`、`PixOCR2.dll`：名称直接指向 OCR 核心；
- `PixModelRunner.dll`、`onnxruntime.dll`：说明 OCR 很可能使用本地推理引擎；
- `model`、`OcrModel` 等目录：说明模型并非只能从云端取得；
- `pixpin.log`、`pixpin.1.log`、`pixpin.2.log`：可以用来观察真实程序调用 OCR 的顺序；
- `Config\PixPinConfig.json`：其中出现了 `pixpin.screenShot(ShotAction.CopyOcrText)`，说明软件已有“截图并复制 OCR 文本”的动作。

### 2.2 先失败一次：递归搜索被锁文件打断

第一次对整个目录做文本搜索时，搜索工具报告多个文件被占用，例如 IDA 数据库文件和 Crashpad 锁文件。这个失败很有价值：它说明“对整个安装目录无差别扫描”既不可靠，也会混入大量无关二进制数据。

正确的判断是：

- 日志和配置只读必要文件；
- DLL 不用普通文本搜索，而用 PE 分析工具查看导入、导出、字符串和依赖；
- 被进程锁定的文件不强行读取，避免把文件访问错误误判成“没有线索”。

### 2.3 用图形化工具替换命令行探索

原过程使用了目录枚举、文本搜索和进程查询。初学者可以按下面的图形化方式完成同样的判断：

| 原来的目的 | 推荐的图形化工具 | 操作和要观察的结果 |
|---|---|---|
| 浏览安装目录 | Windows 文件资源管理器或 Everything | 搜索 `PixOCR*.dll`、`*Ocr*`、`model`、`*.log` |
| 查看 PE 类型、编译器、签名 | PEiD、Detect It Easy、PE-bear | 确认是 x64 MSVC DLL，是否加壳，是否有签名 |
| 查看 DLL 依赖 | Dependencies | 打开 `PixOCR2.dll`，确认 `Qt5Core.dll`、`Qt5Gui.dll`、`PixModelRunner.dll` 等依赖 |
| 查看导出函数 | PE-bear、CFF Explorer、Dependencies 的 Exports 页 | 搜索 `PixOcrObject`、`PixOcrParams`、`getLayoutResult`、`toJson` |
| 查看日志 | Notepad++、LogExpert | 搜索 `OCR task`、`PixOcrRunner`、`modelPath`、`hasResult` |
| 观察进程和模块 | Process Explorer | 打开 PixPin 进程的 DLL 列表，确认 `PixOCR2.dll` 已加载 |
| 观察文件访问 | Process Monitor | 过滤进程名 `PixPin.exe`，看 OCR 时读取了哪些 `.bin` 模型 |

PEiD 的作用主要是识别文件类型和编译器，**不能**代替函数级调试。看到“x64 Microsoft Visual C++ v14.44、DLL、Signed”后，只能得出 ABI 和工具链方向，不能据此猜出类成员布局。

## 3. 阶段二：日志证明 OCR 是本地异步组件

日志中出现了类似如下的事件序列：

```text
PixOcrRunner::run          OCR task started
PixOcrRunner::finishTask   OCR task state released
PixOcrRunner::run          OCR task finished ... hasResult: true
PixOcrObject::onPixOcrRecFinished OCR result received ...
```

这几行给出了三个关键事实：

1. OCR 不是一个同步的“传入图片、立即返回字符串”函数，而是异步任务；
2. 结果通过 `PixOcrObject` 的完成通知返回；
3. 识别结果已经在本地生成，不需要调用在线 OCR 接口。

同时，配置中的 `CopyOcrText` 证明了备用方案：自动触发 PixPin 的 OCR 快捷键，再从剪贴板取文本。这条路线实现快，但有明显缺点：依赖焦点、窗口、剪贴板和截图交互，不适合长期批处理。因此优先级被确定为：

1. 原生 DLL Bridge；
2. PixPin 快捷键/脚本 + 剪贴板，作为验证或故障备用；
3. 最后才考虑重新实现 OCR 模型。

## 4. 阶段三：先做可行性检查，再决定是否写 C++

### 4.1 用户提供的 PEiD 结果

用户用 PEiD 检查 `PixOCR2.dll`，得到大意为：

```text
x64 Microsoft Visual C++ v14.44
DLL
Signed
```

它说明目标是 64 位 MSVC C++ DLL。于是 Python `ctypes` 不再是优先方案，因为导出的对象包含 Qt 类型，可能涉及：

- MSVC C++ 名字修饰；
- `QString`、`QByteArray`、`QImage` 等 Qt 对象；
- C++ 对象的构造、析构和返回值；
- Qt 信号、事件循环和异步线程；
- x64 MSVC 的隐藏返回对象指针。

直接写 `ctypes.CDLL("PixOCR2.dll")` 只能证明 DLL 能被加载，不能保证传入对象的内存布局正确。错误的 ABI 通常表现为“调用后立刻崩溃”或“识别完成后取结果时崩溃”。

### 4.2 第二个失败：找不到 Qt 开发包

检查 Qt 头文件和 `.lib` 文件后，发现 PixPin 目录有运行时 DLL，却没有可直接编译的 Qt SDK。于是放弃“包含 Qt 头文件并正常链接”的常规写法，改为：

1. 用 PixPin 自带的 Qt DLL；
2. 在运行时通过 `GetProcAddress` 解析需要的导出符号；
3. 在自己的 C++ 代码中只保留足够大的原始存储空间；
4. 用 Qt 自己的构造函数初始化这些存储空间。

这是一个重要的思维转折：**没有头文件不代表不能调用，但必须把每一个未知的 ABI 假设变成可验证的证据。**

## 5. 阶段四：从导出符号还原最小调用链

### 5.1 导出符号提供了什么

在 `PixOCR2.dll` 的导出表中找到了类似这些符号：

```text
??0PixOcrObject@PixOcr@@QEAA@VQImage@@UPixOcrParams@1@W4OcrMode@1@PEAVQObject@@@
?getLayoutResult@PixOcrObject@PixOcr@@QEBAAEBVTextBlockList@2@XZ
?sigPixOcrRecFinished@PixOcrObject@PixOcr@@QEAAXXZ
?toJson@TextBlockList@PixOcr@@QEBA?AVQJsonDocument@@XZ
?sigError@PixOcrObject@PixOcr@@QEAAXAEBUPixOcrError@2@@Z
```

从命名可以推断最小链路：

```text
QImage + PixOcrParams
        ↓
PixOcrObject 构造函数
        ↓
等待 sigPixOcrRecFinished
        ↓
getLayoutResult()
        ↓
TextBlockList::toJson()
```

这仍然只是“函数名称层面的推断”，还没有证明参数顺序和对象大小正确。

### 5.2 反汇编确认调用约定

通过反汇编构造函数，确认了两个关键点：

- `QImage` 和 `PixOcrParams` 是 C++ 对象参数，在 x64 MSVC ABI 下不能简单当作普通指针参数；
- 完整 OCR 使用的模式值是 `2`，与日志里的 `mode: 2` 一致。

因此 Bridge 的首个目标不是“猜出全部类定义”，而是只实现一个闭环：加载 DLL、初始化 Qt 对象、创建 OCR 对象、运行事件循环、取得 JSON。

## 6. 阶段五：Bridge 初版和连续失败

### 6.1 初版结构

Bridge 采用单次进程模型：每次启动时读取一张图片，调用一次 OCR，把 JSON 写到标准输出。它先不做 HTTP，因为标准输出更容易观察原始结果。

精简后的结构如下，省略了具体符号名和错误处理：

```cpp
struct Api {
    HMODULE core;
    HMODULE gui;
    HMODULE ocr;
    void (*qCoreApplicationExec)();
    void (*pixOcrObjectCtor)(void*, void*, void*, int, void*);
    void (*textBlockListToJson)(void*, void*);
};

int run(const Options& options) {
    auto inputPath = makeAbsolutePath(options.input);
    auto directory = executableDirectory();
    SetCurrentDirectoryW(directory.c_str());

    loadPixPinLibraries(directory);
    decodeImageWithGdiplus(inputPath, decodedImage);
    constructQtImage(imageStorage, decodedImage);
    constructPixOcrParams(paramsStorage);
    constructPixOcrObject(ocrStorage, imageStorage, paramsStorage, 2);
    runQtEventLoopUntilFinishedOrTimeout();
    serializeLayoutResultAsJson();
}
```

### 6.2 失败一：编译成功，但相对路径失效

初版编译成功，但运行时输入图片找不到。原因是程序为了让 DLL 搜索成功，先把当前目录切到了 `ocr_bridge`；之后才解析用户传入的相对路径，于是 `model\normal.jpg` 被解释成了 `ocr_bridge\model\normal.jpg`。

修正原则：

```cpp
auto inputPath = absolutePath(options.input); // 先解析
SetCurrentDirectoryW(executableDirectory().c_str()); // 再切换 DLL 目录
```

这类错误与 OCR 无关，却必须先解决；否则后面的崩溃位置没有意义。

### 6.3 失败二：DLL 目录不在可执行文件同级

Bridge 放在 `D:\PixPin\ocr_bridge`，而 Qt DLL 在 `D:\PixPin`。只按“可执行文件所在目录”加载依赖会失败。

修正为依次尝试：

1. Bridge 自身目录；
2. Bridge 的父目录；
3. 找到同时包含 `Qt5Core.dll`、`Qt5Gui.dll`、`PixOCR2.dll` 的目录后再加载。

这说明加载路径也应当从目标环境的目录结构推导，而不是硬编码一个临时工作目录。

### 6.4 失败三：把文件名当作裸 `char*` 传给 QImage

第一次真正进入 Qt 后，程序报：

```text
0x00007FFB418B3059 指令引用了 0xFFFFFFFFFFFFFFFF 内存。
```

调试回溯显示崩溃在 `Qt5Core!QByteArray::operator=(const char*)`，调用链经过 `Qt5Gui!QImage` 构造函数。初步猜测是选错了 `QImage` 重载，或者把 Qt 的 `QString`/`QByteArray` 对象当成了 C 字符串。

这个阶段没有继续盲目修改 OCR 参数，而是先用调试器确定崩溃层级：

- 如果崩在 QImage 构造，先修图片输入；
- 如果崩在 PixOcrObject 构造，再修 `PixOcrParams`；
- 如果识别完成后才崩，再修结果返回值。

### 6.5 图形化调试器做法

原过程用 GDB 和反汇编工具定位崩溃。用 x64dbg 可以这样复现：

1. 打开 `pixpin_ocr_bridge.exe`，在 `Qt5Core.dll` 和 `Qt5Gui.dll` 加载后暂停；
2. 在 `QImage` 构造函数和 `QByteArray` 赋值函数下断点；
3. 运行到异常，查看 Call Stack，确认是图片构造而不是 OCR 推理；
4. 查看 RCX/RDX/R8/R9 和栈上的对象地址，判断参数是不是合法的 Qt 对象；
5. 在 Memory Dump 中查看被当作 `QString` 的内存是否已经由 Qt 构造函数初始化。

PEiD 只能告诉我们“这是 MSVC x64”，x64dbg 才能回答“这一次调用实际把什么放进了哪个寄存器”。

### 6.6 修正：不依赖 Qt 图片插件，用 GDI+ 解码

即使手动 `LoadLibrary` 了 Qt 图片插件，运行时也没有可靠地完成插件注册，`QImage(QString)` 可能返回空图。因此改用 Windows GDI+ 解码 JPEG/PNG，得到：

- 宽度；
- 高度；
- 32 位 RGBA/BGRA 像素缓冲区。

再通过已经确认的 `QImage(裸像素缓冲区)` 构造函数建立 Qt 图像对象。核心思想是把“图片文件格式解析”与“Qt OCR 接口”拆开，避免同时调试两个不确定因素。

## 7. 阶段六：`PixOcrParams` 的对象布局问题

### 7.1 失败四：`PixOcrParams` 全零内存导致 QString 崩溃

图片构造修好后，OCR 对象创建阶段又崩溃，回溯落在 `Qt5Core!QString::operator=`。原因是 Bridge 使用了全零字节作为 `PixOcrParams`，但其中有多个 Qt `QString` 字段；全零并不等于一个合法、可赋值、可析构的 Qt 字符串对象。

反汇编显示至少需要在这些偏移初始化 Qt 字符串对象：

```text
0x00、0x50、0x60、0x68
```

因此要先调用 Qt 的默认构造函数，再写入真正的字符串。伪代码为：

```cpp
std::array<std::byte, kPixOcrParamsSize> params{};

for (auto offset : {0x00, 0x50, 0x60, 0x68}) {
    qStringDefaultCtor(params.data() + offset);
}
```

不能用 `memset` 代替构造函数；也不能在不知道析构行为时随意复制或释放这块内存。

### 7.2 里程碑：OCR 对象创建并启动推理

初始化 QString 后，日志出现：

```text
PixOcrObject::PixOcrObject OCR object created
PixModelRunnerPrivate::inference Starting inference
modelPath: "" modelDataSize: 0
```

这是一次重要的“部分成功”：图片和对象 ABI 已经正确，程序也进入了推理；失败范围缩小到模型参数。下一步不再检查图片，也不再重写事件循环，而是专门分析模型字段。

## 8. 阶段七：模型字段的两次错误假设

### 8.1 错误假设一：裸指针 + 长度

最初把模型理解为“内存地址 + 字节长度”，将两个本地 `.bin` 文件读入内存后写入参数结构。但日志仍然显示：

```text
modelPath: ""
modelDataSize: 0
```

这说明“文件已读入内存”不等于“PixModelRunner 认识这个参数”。

### 8.2 错误假设二：模型字段是 QByteArray

继续反汇编复制构造和析构路径后，发现模型相关字段确实表现出 Qt 容器行为，于是尝试调用：

```cpp
using QByteArrayCtor = void (*)(void*, const char*, int);
qByteArrayCtor(field, bytes.data(), static_cast<int>(bytes.size()));
```

这次程序不再崩溃，但 OCR 内部仍没有读取到模型。说明“字段是 Qt 对象”这个判断可能接近事实，但“它就是嵌入的模型字节数组”仍没有被真实程序验证。

这一步的经验是：**反汇编能告诉你字段如何被操作，但不一定能告诉你业务语义。** 最可靠的办法是观察 PixPin 自己调用构造函数时传入的真实值。

## 9. 阶段八：附加到真实 PixPin，捕获真实参数

### 9.1 为什么要从“猜结构”切换到“抓现场”

此时 Bridge 已经可以创建对象，却无法加载模型；继续猜字段类型的成本很高。PixPin 本身能成功识别，所以它就是最好的“参考实现”。

下一步逻辑是：

1. 重启 PixPin，确保加载的 `PixOCR2.dll` 与 Bridge 使用的版本相同；
2. 用 x64dbg 附加到 `PixPin.exe`；
3. 在 `PixOcrObject` 构造函数的导入调用处下断点；
4. 再在 `getModelParams` 或推理入口附近下断点；
5. 在 PixPin 中触发一次 OCR；
6. 从寄存器和内存中读取实际的 `PixOcrParams` 内容。


### 9.3 用 Alt+X 触发样本 OCR

用户说明 `Alt+X` 是“截图并识别”的快捷键。调试器一开始让 PixPin 处于挂起状态，快捷键无法正常完成；正确顺序是：

1. 让调试器继续运行；
2. 发送 `Alt+X`；
3. 在屏幕上框选一小段文字；
4. 等待断点命中；
5. 查看传入构造函数的参数对象。

### 9.4 关键发现：模型参数是路径字符串

断点现场显示，PixPin 传入的不是“模型字节指针 + 长度”，而是模型路径字符串；语言字段为 `zh-cn`。因此最终参数填充改成：

```cpp
qStringCstrCtor(params + 0x00, detectionModelPath.c_str());
qStringCstrCtor(params + 0x50, recognitionModelPath.c_str());
qStringCstrCtor(params + 0x60, "zh-cn");
qStringDefaultCtor(params + 0x68); // 其余 Qt 字符串仍须合法构造
```

这里的偏移只适用于当时的 x64 `PixOCR2.dll`。升级 DLL 后必须重新通过构造函数和真实调用验证。

## 10. 阶段九：OCR 完整成功，但取 JSON 又崩溃

模型路径修正后，日志表明检测、识别和模型加载都成功。接下来崩溃发生在识别完成之后，说明问题从“输入/推理”转移到了“C++ 返回值”。

### 10.1 隐藏返回对象参数

Qt 的 `QJsonDocument` 是按值返回的 C++ 对象。对于 MSVC x64 ABI，函数可能需要一个隐藏的返回对象指针；而 `TextBlockList::toJson()` 的调用参数顺序也不能凭函数名猜测。

错误版本把普通 `this` 指针和返回对象地址顺序传反，于是：

- OCR 已经成功；
- 一调用 `toJson()` 就崩溃；
- 看起来像“识别后崩溃”，其实是 ABI 返回值错误。

### 10.2 修正方法

在 x64dbg 中观察真实调用点：

- 哪个寄存器装返回对象地址；
- 哪个寄存器装 `TextBlockList` 的 `this`；
- 函数返回后哪个对象需要析构。

再把函数指针声明和调用顺序调整为真实 ABI。修正后，识别结果可以安全序列化为 JSON。

## 11. 阶段十：最终输出和回归

最后还修正了一个容易忽略的问题：`QImage` 按 ABI 传值后，原先保存的 Qt 图像对象尺寸可能读成 0。因此输出图像尺寸不再从传值后的临时 Qt 对象读取，而使用 GDI+ 解码时已经知道的宽高。

最终回归结果：

```text
exit: 0
ok: true
image.width: 1558
image.height: 974
result.blocks: 64
result.lang: zh-cn
```

输出 JSON 的最小形状为：

```json
{
  "ok": true,
  "image": {"width": 1558, "height": 974},
  "result": {
    "lang": "zh-cn",
    "blocks": [
      {"text": "100%", "recognitionSucceeded": true},
      {"text": "中", "recognitionSucceeded": true}
    ]
  }
}
```

测试输入是 `model\normal.jpg`，测试程序是：

```powershell
.\ocr_bridge\pixpin_ocr_bridge.exe --input .\model\normal.jpg
```

Bridge 的 CMake 配置只需要把 C++17、源文件和 GDI+ 链接起来：

```cmake
cmake_minimum_required(VERSION 3.20)
project(pixpin_ocr_bridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(pixpin_ocr_bridge main.cpp)
target_link_libraries(pixpin_ocr_bridge PRIVATE gdiplus)
target_compile_definitions(pixpin_ocr_bridge PRIVATE UNICODE _UNICODE)
```

构建方式可以是：

```powershell
cmake -S ocr_bridge -B ocr_bridge\build -G Ninja
cmake --build ocr_bridge\build --config Release
```

## 12. 从这次过程提炼出的排错方法

### 12.1 每次只缩小一个不确定性

本次顺序是：

1. 先确认 OCR 文件、日志和模型存在；
2. 再确认导出符号和依赖；
3. 再确认图片输入；
4. 再确认 Qt 对象构造；
5. 再确认 `PixOcrParams`；
6. 再确认模型路径；
7. 最后确认 JSON 返回值。

如果一开始同时改图片解码、模型参数、信号连接和 HTTP 层，任何一次崩溃都无法归因。

### 12.2 “能创建对象”不等于“调用成功”

必须区分这些里程碑：

- DLL 能加载；
- Qt 对象能构造；
- OCR 对象能创建；
- 推理线程能启动；
- 模型真的被读取；
- 识别任务完成；
- 结果能序列化；
- 输出 JSON 合法。

本次每一步都曾经成功而下一步失败，这正是 ABI 调试的典型特征。

### 12.3 日志、反汇编和调试器各自回答不同问题

- **日志**回答“程序认为自己正在做什么”，例如 `modelPath` 是否为空；
- **PE 分析工具**回答“文件导出了什么、依赖什么”；
- **反汇编**回答“函数如何读写对象”；
- **x64dbg 现场**回答“真实程序这一次传入了什么”；
- **回归测试**回答“外部可观察结果是否正确”。

不要用其中一种证据替代全部证据。

## 13. 产物、限制和后续改造

当前完成的是“一张图片启动一个进程”的 Bridge：标准输入参数是图片路径，标准输出是 JSON。它已经可以被 Python、Node.js、C# 等程序启动调用。

但它还不是高性能常驻 HTTP 服务，原因是：

- 每次启动都可能重新加载 Qt 和模型；
- `PixOCR2.dll` 是未公开的 C++/Qt ABI；
- 当前版本的 `PixOcrParams` 偏移与导出符号是针对特定 PixPin 版本的；
- OCR 内部是异步的，服务化时应先串行处理请求，再评估并发；
- PixPin 更新后必须重新检查 DLL、导出表、对象偏移和模型路径。

下一步若要服务化，推荐保持分层：

```text
HTTP 客户端
    ↓
Python/FastAPI 或 C++ HTTP 层
    ↓
常驻的原生 OCR Bridge
    ↓
Qt 事件循环 + PixOCR2.dll + 本地模型
```

最后，复用第三方软件的内部 DLL 前，应确认自己拥有相应软件和数据的使用权，并检查软件许可。技术上能调用，不等于在所有场景下都获得了再分发或长期自动化使用的许可。

## 14. 初学者复盘清单

读完本文后，应该能够回答：

- 为什么先做单图 JSON Bridge，而不是直接写 HTTP？
- 为什么 `ctypes.CDLL` 不足以安全调用带 Qt C++ 对象的 DLL？
- PEiD 的结果能证明什么，不能证明什么？
- 为什么全零 `PixOcrParams` 会在 `QString` 赋值时崩溃？
- 为什么日志中的 `modelDataSize: 0` 会推翻“裸指针 + 长度”的模型假设？
- 为什么从真实 PixPin 进程抓一次参数，比继续猜结构更可靠？
- 为什么 OCR 已经成功，`toJson()` 仍然可能崩溃？
- 为什么最终图像尺寸要使用 GDI+ 解码结果，而不是传值后的 QImage？

如果这些问题都能用“现象 → 假设 → 验证工具 → 结论”的方式解释，才算真正理解了这次开发过程，而不是只记住了几个偏移量。

## 15. 第二轮补充：把关键跳步补成可验证步骤

这一节专门回答审阅 agent 提出的初学者问题，并修正前文示意代码可能造成的误解。

### 15.1 Bridge 的真实边界

当前产物是一个独立的 x64 Windows 命令行进程：

~~~text
--input 图片路径
        ↓
pixpin_ocr_bridge.exe
        ↓ 动态加载
PixOCR2.dll + Qt5Core.dll + Qt5Gui.dll
        ↓
stdout: 一个 JSON 对象
~~~

它不是 DLL，也不是已经完成的 HTTP 服务。这里的“API”是“其他程序可以稳定调用的入口”，当前入口是命令行；将来可以在外层增加 `POST /ocr`，但那是另一层，不应和原生 Bridge 混为一谈。

### 15.2 为什么从文本搜索换成 PE 工具

两类工具回答的问题不同：

- 文本搜索回答“日志、配置或二进制字符串里有没有某个词”；
- PE 工具回答“文件是什么架构、依赖哪些 DLL、导出了哪些符号”；
- 反汇编回答“某个函数怎样读取寄存器和对象偏移”；
- 调试器回答“真实程序这一次实际传入了什么”。

所以锁文件导致的递归搜索失败本身不是换工具的充分理由；真正的理由是问题已经从“找线索”变成了“确认二进制接口”。GUI 复现步骤如下：

1. 在 Dependencies 打开 `PixOCR2.dll`，先看 Modules；红色项目只有在确实找不到文件或架构不匹配时才是运行阻断，延迟加载或可选组件不能仅凭红色下结论。
2. 在 Exports 搜索 `PixOcrObject`、`getLayoutResult`、`toJson`，记录完整修饰名。
3. 在 Process Monitor 添加过滤：`Process Name is PixPin.exe`，再加 `Path ends with .bin` 或 `Path contains model`；触发一次 OCR，观察 `CreateFile`/`ReadFile` 成功打开的实际模型路径。
4. 在 x64dbg 的 Modules 中确认 `PixOCR2.dll` 来自正在运行的 PixPin 安装目录，再设置断点；这样不会把旧版本 DLL 的地址误当成当前版本。

### 15.3 PEiD 与 ctypes 的准确关系

“x64 MSVC”本身并不禁止 `ctypes`。如果 DLL 导出的是简单 C ABI，例如 `int add(int, int)`，ctypes 可以正常使用。本例放弃直接 ctypes 的真正原因是导出表显示了 Qt/C++ 对象：`QImage`、`QString`、`QByteArray`、`QJsonDocument`、构造/析构函数和异步信号。PEiD 提供的是架构和编译器线索，Qt 导出符号才提供了 ABI 风险证据。

### 15.4 事件循环、应用对象和超时

日志中的 `finishTask`、`task finished` 和 `onPixOcrRecFinished` 可能来自不同线程，记录器也可能异步写入；不能把相邻日志行当成严格线程顺序。能确定的是 OCR 具有异步任务和完成通知。

Qt 事件循环的职责是处理线程投递的信号、定时器和退出事件。Bridge 的真实实现需要先创建 `QCoreApplication`（而不是只调用一个孤立的 `exec` 函数），然后创建 OCR 对象并进入事件循环；OCR 完成或错误时调用 `quit()`，超时定时器也调用 `quit()`。没有 Widgets 界面时使用 Core 层即可，不需要 `QApplication`。

前文的 `runQtEventLoopUntilFinishedOrTimeout()` 是伪代码。`exec()` 的返回值也不能随意写成 `void`；实际函数指针应按当前 Qt 导出和反汇编确认，原始实现保存了 `execResult` 并检查非正常退出。一个准确的逻辑形状是：

~~~cpp
QCoreApplication app(argc, argv);
connectSuccessAndErrorToQuit(ocrObject, app);
startTimeoutTimer(app, timeoutMs);
int execResult = qCoreApplicationExec();
check(execResult, ocrObject.hasError());
~~~

如果不想依赖信号，也可以轮询状态，但必须自行处理线程同步、睡眠、超时和 Qt 事件处理；本次选择事件循环是因为 DLL 已经明确使用 Qt 信号。

### 15.5 QImage 输入的四个 ABI 要点

“使用裸像素缓冲区构造 QImage”不是一句“传一个指针”就够了，至少要确认：

- 像素首地址；
- 宽度和高度；
- 每行字节数（stride）；
- Qt 像素格式枚举。

GDI+ 解码后，Bridge 将图像转换成固定的 32 位格式，并以 `width * 4` 作为 stride，再传给当前版本已确认的 QImage 构造重载。外部缓冲区不能在构造函数返回后立即释放：OCR 是异步的，必须保持到任务完成，或者使用会复制数据的构造方式并由调试验证。像素通道顺序、负 stride、旋转元数据不是原始对话中已验证的范围，因此教程不应声称已经覆盖这些情况；遇到颜色颠倒或旋转错误，应先用一张带明显红绿蓝块的测试图验证。

### 15.6 `PixOcrParams` 大小、对齐和初始化边界

`kPixOcrParamsSize` 不是公开常量，而是按当前 DLL 的构造函数访问范围预留的原始存储；安全条件是：存储足够大、地址满足至少指针/Qt 对象所需对齐、所有会被构造和析构的 Qt 字段都先调用对应构造函数。反汇编确认了 `0x00、0x50、0x60、0x68` 这些字段访问，但“当前样本可运行”不等于“未来版本只构造四个字段也安全”。升级后必须重新检查构造函数、复制构造和析构函数。

### 15.7 从空模型日志到真实参数的排除链

看到：

~~~text
modelPath: ""
modelDataSize: 0
~~~

不能立即断言“字段就是模型字节”。当时按以下顺序排除：

1. 图片是否有效：日志已显示 `imageSize: QSize(1558, 974)`。
2. OCR 对象是否创建：日志已显示对象创建并进入推理。
3. 是否只是路径基准错误：Bridge 已能找到安装目录和图片，仍然得到空字段。
4. 是否模型尚未初始化：等待到 inference 入口后仍为空。
5. 字段语义是什么：先试内存数据，再试 `QByteArray`，均没有使内部读取模型。
6. 最终附加真实 PixPin，在同一个构造调用点读取现场，确认是两个路径字符串和语言字符串。

这就是“现象 → 候选解释 → 排除证据 → 新验证”的完整推理，而不是从一行日志直接猜答案。

### 15.8 用 x64dbg 现场确认模型字段

附加真实 PixPin 后，操作顺序是：

1. Modules 窗口确认当前 `PixOCR2.dll` 的完整路径和版本。
2. 在 Imports/Exports 或已解析的调用点找到 `PixOcrObject` 构造函数。
3. 设置断点，继续运行，不要让进程一直保持暂停。
4. 触发 `Alt+X`，完成一次小范围 OCR。
5. 断下后记录 Call Stack、Registers 和 Dump；跟随传入 `PixOcrParams` 的指针。
6. 在 `0x00、0x50、0x60` 处跟随字符串指针，确认内容是模型路径、模型路径和 `zh-cn`。
7. 再用 Process Monitor 观察这些路径是否发生 `CreateFile`/`ReadFile` 成功事件。

这两类证据共同证明字段业务含义：现场字符串说明“传入了什么”，文件访问和 OCR 成功说明“程序把它当成什么使用”。仅看到两个可读字符串还不足以证明字段顺序。

### 15.9 C++ 返回值、引用和生命周期

`getLayoutResult()` 返回的是由 `PixOcrObject` 持有的结果引用，不应在 OCR 对象析构后继续使用。正确顺序是：完成信号到达 → 在 OCR 对象仍存活时调用 `getLayoutResult()` → 将 `TextBlockList` 序列化到调用方提供的 `QJsonDocument` 存储 → 再把 JSON 转成字节输出 → 最后按相反顺序析构临时 Qt 对象。

`toJson()` 的隐藏返回对象不是所有 C++ 函数都通用的固定规则。当前版本的正确 `this`/返回对象顺序来自 x64dbg 调用现场和反汇编，而不是凭经验套一个通用表。教学时应把它描述为“本 DLL 的实测 ABI”，不能推广到别的编译器或 Qt 版本。

### 15.10 运行和部署判据

构建成功只说明编译器生成了 EXE；运行成功还必须同时满足：

- Bridge 为 x64；
- Qt、PixOCR、PixModelRunner 和 MSVC runtime 来自同一安装；
- 模型目录存在；
- stdout 是合法 JSON；
- `ok` 为 `true`；
- 图像尺寸非零；
- `blocks` 数量符合测试图预期；
- 退出码为 0。

原始对话只对 `normal.jpg` 做了成功回归，没有验证损坏图片、中文路径、缺失模型、超时、空白图和连续运行。因此这些应列为后续测试，而不是已经完成的保证。

## 16. 第二轮复盘：用“现象—假设—验证—结论”回答

复习每个问题时，不要只背最终结论。至少要能写出四段：

1. **现象**：例如 `modelPath` 为空或 `toJson()` 崩溃；
2. **假设**：例如模型字段类型错误或隐藏返回参数顺序错误；
3. **验证**：日志、PE 导出、反汇编、x64dbg、Process Monitor 中哪一个证据验证/排除了它；
4. **结论**：只对当前 PixPin 版本得出的最小结论。

如果读者能独立说明这四段，而不只是说“把偏移改成 0x50”，才算真正理解了这次开发过程。

## 17. 最后一轮代码级补充：把示意 ABI 对齐到实际版本

上一轮审阅留下的 5 个问题，可以用原始对话最后保留下来的 `main.cpp` 片段具体回答。下面这些声明只适用于当时的 PixPin x64 版本；它们不是通用 Qt ABI。

### 17.1 实际函数指针声明

Bridge 最终使用了以下精简声明：

~~~cpp
using QCoreApplicationCtor = void (*)(void*, int*, char**, int);
using QCoreApplicationExec = int (*)();
using QCoreApplicationQuit = void (*)();

using QImageRawCtor = void (*)(
    void*, const unsigned char*, int, int, int, int,
    void (*)(void*), void*);

using PixOcrObjectCtor = void (*)(
    void*, const void*, const void*, int, void*);

using QObjectConnect = void (*)(
    void*, const void*, const char*, const void*, const char*, int);

using TextBlockListToJson = void (*)(const void*, void*);
using QJsonDocumentToJson = void (*)(const void*, void*);
~~~

这些声明分别对应：

| 声明 | 第一个 `void*` 的意义 | 其余关键参数 |
|---|---|---|
| `QCoreApplicationCtor` | 调用方提供的应用对象存储 | `argc`、`argv`、额外参数 |
| `QImageRawCtor` | 调用方提供的 QImage 存储 | 像素指针、宽、高、stride、格式、cleanup |
| `PixOcrObjectCtor` | OCR 对象的 `this` 存储 | QImage 对象、参数对象、模式值 `2`、父对象 |
| `QObjectConnect` | `QMetaObject::Connection` 的返回对象存储 | sender、signal、receiver、slot、连接类型 |
| `TextBlockListToJson` | 当前对象作为 `this` | 返回的 QJsonDocument 存储地址 |
| `QJsonDocumentToJson` | 当前 QJsonDocument 作为 `this` | 返回的 QByteArray 存储地址 |

这也解释了前文的“不能把所有参数都当普通指针”：函数指针里的 `void*` 是为了隐藏 Qt 类型和对象存储，真正的按值/隐藏返回关系来自当前调用点的 ABI 验证。构造 `PixOcrObject` 时，最终调用形状是：

~~~cpp
api.pixOcrObjectCtor(
    ocrObject.data(),
    image.data(),
    params.data(),
    2,
    nullptr);
~~~

### 17.2 没有 Qt 头文件时如何连接信号

Bridge 没有调用 `sigPixOcrRecFinished()` 这个函数本身来“执行信号”，而是解析 Qt 的静态 `QObject::connect` 导出，通过 Qt 元对象字符串建立连接：

~~~cpp
api.qObjectConnect(
    connection.data(),
    ocrObject.data(),
    "2sigPixOcrRecFinished()",
    coreApplication.data(),
    "1quit()",
    kQtAutoConnection);
~~~

其中：

- `2` 和 `1` 是 Qt 旧式字符串信号/槽语法的标记；
- sender 是 `PixOcrObject`；
- receiver 是 `QCoreApplication`；
- OCR 完成后调用 `QCoreApplication::quit()`；
- `connection.data()` 是返回的 `QMetaObject::Connection` 的存储区。

错误信号还通过 OCR 对象的错误状态检查处理；超时线程则直接调用导出的 `QCoreApplication::quit()`。原始过程没有把错误信号连接的完整代码展开，因此教程只对已确认的成功信号连接给出代码，不虚构未展示的错误回调实现。

### 17.3 QImage 裸像素重载的实际参数

当前版本解析的 QImage 构造符号对应：

~~~cpp
QImage(
    const unsigned char* pixels,
    int width,
    int height,
    int bytesPerLine,
    QImage::Format format,
    QImageCleanupFunction cleanupFunction,
    void* cleanupInfo);
~~~

因此之前的检查清单可以具体化为：

1. GDI+ 解码图片；
2. 固定为 32 位像素缓冲区；
3. 传入宽、高和 `width * 4` 的每行字节数；
4. 传入当前版本对应的 Qt 32 位格式枚举；
5. 在 OCR 完成前保持像素缓冲区和 QImage 对象存活；
6. 析构 QImage 时再释放相关存储。

这也是为什么不能在 OCR 构造函数返回后立刻释放 GDI+ 缓冲区：QImage 可能只是引用外部内存，而 OCR 又是异步的。

### 17.4 `toJson()` 的最终调用顺序

最终代码中的调用顺序是：

~~~cpp
const void* layout = api.pixOcrObjectGetLayoutResult(ocrObject.data());

Storage jsonDocument(sizeofJsonDocumentStorage);
api.textBlockListToJson(layout, jsonDocument.data());

Storage bytes(sizeofQByteArrayStorage);
api.qJsonDocumentToJson(jsonDocument.data(), bytes.data());

const char* data = api.qByteArrayConstData(bytes.data());
int size = api.qByteArraySize(bytes.data());
writeStdout(data, size);
~~~

因此在这个版本中：

- `TextBlockListToJson` 的第一个参数是 `TextBlockList` 的 `this`；
- 第二个参数是调用方准备的 `QJsonDocument` 返回对象；
- `QJsonDocumentToJson` 的第一个参数是文档的 `this`；
- 第二个参数是调用方准备的 `QByteArray` 返回对象。

这些顺序来自最终成功运行的函数指针和调用，不应推广为所有 MSVC C++ 函数的通用模板。

### 17.5 `kPixOcrParamsSize` 的实际值和边界验证

原始 Bridge 使用：

~~~cpp
constexpr std::size_t kPixOcrParamsStorage = 0x100;
constexpr std::size_t kPixOcrObjectStorage = 4096;
~~~

`0x100` 不是从公开头文件得到的结构体大小，而是根据当前构造函数、字段访问和析构路径保留的工作空间。至少要满足：

- 最大已观察字段偏移 `0x68` 加上一个 Qt `QString` 对象空间；
- 复制/移动/析构路径在反汇编中访问的范围；
- 适合 Qt 对象的对齐要求。

验证方法是：在 x64dbg 中对构造、复制和析构路径分别设置断点，记录它们访问的 `[params + offset]` 最大范围；再用 Application Verifier、调试堆或连续运行回归观察越界和释放错误。原始对话最终验证了 `0x100` 的当前样本可运行，但没有证明它对未来版本仍然足够，所以升级 PixPin 后必须重新做这一步。

到这里，审阅 agent 剩下的 5 个代码级问题已经都有“实际声明—参数含义—成功判据—版本限制”的答案。教程仍然不是公开 SDK，也不保证第三方版本升级后的 ABI 兼容；它是一份基于一次成功逆向过程的学习记录。
