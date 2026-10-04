# PixPin 本地 OCR Bridge 续篇教程：从“多两次推理”定位到参数 ABI 对齐

> 本文是 Codex-conversation.txt 前置教程的续篇，只记录后续性能对比、调用约定校准和 PixOcrParams 复原过程。阅读前应先理解 DLL 动态加载、Qt 对象生命周期、QImage 裸像素构造、命名管道和 JSON 返回链路；本文只补充与本轮定位直接相关的最小背景。

## 1. 先看最终问题是什么

目标不是重新实现 OCR，而是让独立的 C++ Bridge 在同一张图片上走出和 PixPin 相同的 OCR 分支。

本轮起点是“相同图片内容、近似相同尺寸”的性能对比：PixPin 约 1.5 秒，Bridge 约 5 秒。这里的“冷启动”并不完全公平：PixPin 请求前已经初始化过部分 PixModelRunner，而 Bridge 在第一次请求中才初始化。应区分三件事：进程冷启动、OCR runner 冷启动、ONNX session 冷启动。真正有价值的线索不是总耗时，而是推理序列：

~~~text
PixPin：首个推理（沿用原日志的“检测”命名）1 次，识别 1 次，版面/段落 1 次，共 3 次 inference
Bridge：检测及后处理分支更多，共 5 次 inference
~~~

第一条推理规则是：如果首个模型的模型大小、输入和输出字节数一致，而后续模型的序列不同，优先检查 OCR 参数与构造路径；不要先把问题归因于命名管道、JSON 序列化或图片读写。

本轮有两个独立修复，不能混成一个因果链：恢复 5 参数构造调用后，推理次数先从 5 次降到 3 次、耗时约 1.59 秒；随后补齐 PixOcrParams 默认数值字段，候选相关输入计数从约 91 降到 65，计算时间进一步降到约 1.23 秒。后者主要修复后处理参数，不是第一次把 5 次变成 3 次的原因。

### 最小背景：这里说的 ABI 是什么

ABI 是二进制接口约定，包含函数参数如何放入寄存器/栈、C++ 对象的内存布局、Qt 对象的构造与析构方式，以及按值返回对象时的隐藏参数。PixOCR2.dll 没有公开头文件，所以 Bridge 不能只凭函数名写普通 C++ 声明；必须用 x64dbg/IDA 观察真实调用，再用最小 A/B 验证。

## 2. 时间线总览

| 阶段 | 核心问题 | 关键证据 | 结论/产物 |
|---|---|---|---|
| A | 5 秒是否只是冷启动 | PixPin 和 Bridge 的推理日志逐项对比 | 差异是推理分支，不只是启动耗时 |
| B | Bridge 调用了哪个构造重载 | IDA/反汇编的导入调用点 | 先发现 6 参数候选，随后确认 Alt+X 主路径实际是 5 参数 |
| C | 能否用预热或 6 参数重载追平 | 独立 A/B 二进制、x64dbg 异常现场 | 预热调用不安全；6 参数路径异常或引入额外分支，回到 5 参数 |
| D | 5 参数路径仍为何多两次推理 | 首个推理的模型大小和张量规模一致，后处理输入不同 | 当前优先怀疑 PixOcrParams 数值字段，而非图片输入 |
| E | 如何得到完整参数布局 | IDA 默认构造函数伪代码和四个调用点 | 复原 0x80 字节布局与默认阈值 |
| F | 修复是否有效 | 独立 A/B、PixPin 日志、正式服务回归 | 3 次推理、约 1.23 秒、正式二进制更新 |

后文按这个顺序展开。每个阶段都说明“为什么下一步应该这样做”，这是学习逆向调试时最重要的部分。

## 3. 阶段 A：把总耗时拆成可解释的证据

### 3.1 先比推理序列，不比总耗时

PixPin 日志中可以看到三次模型推理。下面保留模型大小、输入/输出规模和候选相关字段，避免把不同模型的字节数误当成同一次推理：

~~~text
modelDataSize: 9880512, inputTensorBytes: 8404992, outputTensorBytes: 2801664
modelDataSize: 3198623, inputTensorBytes: 72836,   outputTensorBytes: 3136
modelDataSize: 21234344, inputTensorCount: 59,      outputTensorBytes: 108742520
~~~

Bridge 的第一轮日志则出现相同的检测模型规模，但后续进入了不同的模型/分支：

~~~text
modelDataSize: 9880512, inputTensorBytes: 8404992, outputTensorBytes: 2801664
modelDataSize: 21234344, inputTensorBytes: 1899236, inputTensorCount: 91
~~~

这里可以降低三类错误的优先级，但不能仅凭这些字段完全排除它们：

1. 首个推理没有明显加载异常：两边的模型数据大小和张量字节数一致；这不等于证明模型内容哈希相同；
2. 图片尺寸或基本像素格式完全错误：OCR 对象看到的尺寸和检测输入一致，但仍需字节级比较才能证明像素完全一致；
3. 命名管道是主要瓶颈：最终计时显示管道读写只有毫秒级，因此优先检查 OCR 内部，但这不能替代对最初测试条件的单独计时。

日志中的 inputTensorCount 不是“候选框数量”的公开定义；本轮是结合 PixPin 的 lineResultCount/blockResultCount、后处理输入规模随该字段变化、以及修复后推理序列同步变化，才把 59/91 作为候选相关输入计数来使用。全文统一称为“候选相关输入计数”，不把它推广成最终检测框总数。

剩下的高概率原因是：检测后的候选框筛选阈值、段落识别开关、识别阈值等参数不一致，导致后处理生成更多候选相关输入并进入额外分支。

### 3.2 模型阶段名称从哪里来

三个阶段名称来自当前 PixPin 配置、推理顺序和日志的交叉对照，而不是仅凭 modelDataSize 猜测：配置中明确有检测模型、识别模型和 paragraph_recognition.onnx；日志按同一顺序出现 9880512、3198623、21234344 三种模型数据大小。教程沿用“检测/识别/版面或段落”的方便称呼，但本轮没有对模型文件做内容哈希，也没有把这些名字当成 DLL 的公开元数据。

### 3.3 初学者如何用图形化工具复现

原对话中有大量目录搜索、导出枚举和文本过滤。学习时可以按下面的 GUI 流程操作：

| 目的 | 工具 | 操作 |
|---|---|---|
| 对照运行日志 | Notepad++ 或 LogExpert | 分别打开 PixPin 日志和 Bridge 日志，搜索 inference、inputTensorBytes、lineResultCount |
| 观察加载的 DLL | Process Explorer | 查看两个进程的 Modules，确认都加载同一目录下的 Qt、PixModelRunner 和 PixOCR2 |
| 查看导出/导入符号 | PE-bear、Dependencies | 在 Exports/Imports 中搜索 PixOcrObject、PixOcrParams、getModelParams |
| 查看实际调用参数 | x64dbg | 附加 PixPin，在 OCR 构造函数入口断点，观察 RCX/RDX/R8/R9 及栈参数 |
| 反编译默认构造函数 | IDA | 在 Functions 或 Imports 中定位 PixOcrParams 初始化函数，查看 对象+偏移 的写入值 |

PEiD/Detect It Easy 只能确认文件是 x64 MSVC DLL，不能告诉你 PixOcrParams 的布局；布局必须靠调用点、伪代码和运行结果共同确认。

## 4. 阶段 B：追踪 OCR 对象构造重载

### 4.1 为什么检查构造函数

日志表现为“同一个图片，检测相同，后处理不同”。在 C++ ABI 未公开的 DLL 中，构造函数往往不仅创建对象，还会根据布尔标志和父对象选择不同的 OCR 模式。因此下一步不是继续调模型，而是验证 Bridge 和 PixPin 是否调用同一个构造重载。

在 IDA 的 Imports/C++ 符号中，看到两个相关签名：

~~~text
PixOcrObject(QImage, PixOcrParams, OcrMode, QObject*)
PixOcrObject(QImage, PixOcrParams, OcrMode, bool, QObject*)
~~~

符号显示的是 C++ 层的按值参数；Bridge 中的函数指针则把对象存储写成 void*，是为了隐藏 Qt 类型。真正调用时还要考虑 this 指针、临时对象和寄存器/栈位置，不能把任意 C++ 函数都机械改成一串裸指针。这里的参数顺序是由 PixPin 的调用点和成功 A/B 共同验证的。

进一步查看 PixPin.exe 的调用点，发现存在三个 5 参数调用点和一个 6 参数调用点。这里的 Alt+X 是 PixPin 的“截图并识别”快捷键；本轮目标是复现它触发的普通截图 OCR，而不是图像分段/翻译流程。仅凭“PixPin 使用过 6 参数版本”不能得出“Alt+X 主 OCR 就该使用 6 参数版本”，必须把调用点放回业务流程判断。

### 4.2 第一次错误方向：把 6 参数版本当成主路径

当时的合理但未经充分验证的假设是：PixPin 的 6 参数调用额外传入 bool=true，也许这个标志就是优化或预热开关。于是尝试：

~~~cpp
using PixOcrObjectCtorWithFlag = void (*)(
    void*, const void*, const void*, int, bool, void*);

api.pixOcrObjectCtorWithFlag(
    ocrObject.data(), image.data(), params.data(), mode, true, nullptr);
~~~

同时尝试提前调用 PixModelRunner::getInstance()，希望把模型初始化从请求路径移到服务启动阶段。这个早期实验同时改变了两个变量，因此它只能生成“方向线索”，不能单独证明是哪一项导致异常；后面使用独立的 5/6 参数 A/B 做了可控验证。

### 4.3 失败：预热调用触发 OpenCV 空图错误

包含 getInstance() 预热和构造重载切换的早期实验观察到 OpenCV 空图错误。由于当时同时改变了两个变量，不能把异常唯一归因于 getInstance()；它只能说明这种手动预热方案在当前 worker 线程和 Qt 生命周期下不安全。这个结果说明：

- 导出函数虽然存在，但它不是可以随时手动调用的公共初始化 API；
- PixPin 可能在更完整的上下文、线程或参数初始化之后才创建 runner；
- “把一个看起来像单例的函数提前调用”不能替代真实调用顺序。

处理方式是撤销预热调用，而不是继续堆叠线程或异常处理。调试原则是：一个实验同时改变的因素越少，越容易知道是哪一项造成崩溃。

### 4.4 失败：直接覆盖正式 exe 时链接器报错

修改后编译正式服务时出现：

~~~text
ld.exe: cannot open output file pixpin_ocr_service.exe: Permission denied
~~~

这不是代码错误，而是旧服务进程仍持有 exe 文件。正确做法是：

1. 用 Process Explorer 或任务管理器确认并结束旧的 pixpin_ocr_service 进程；
2. 调试实验不要覆盖正式文件，先输出到独立的 A/B 文件名；
3. 只有回归通过后才替换正式二进制。

## 5. 阶段 C：用 A/B 实验确定 5 参数还是 6 参数

### 5.1 设计可重复的 A/B

为了避免把协议、图片解码和构造重载同时混在一起，Bridge 内部 A/B 固定以下条件：

- 同一份 test2.png；
- 同一尺寸，约 1121×586；
- 同一 PixPin DLL 目录；
- 同一命名管道协议；
- 只更换 OCR 构造函数版本；
- 每个版本使用独立的服务 exe 和独立管道名。

这是逆向中的“控制变量”思路：如果 Bridge 内部 A/B 只差一个构造调用，结果差异才有归因价值。它不代表这些 Bridge 日志已经和 PixPin 做到了像素级相同；与 PixPin 的最终对照还要单独确认尺寸、字节和哈希。

### 5.2 A/B 结果

~~~text
5 参数构造：稳定完成，单次 OCR 约 1.59 秒，3 次 inference
6 参数构造：最终独立 A/B 以 0xC0000374 退出，含义是堆损坏
~~~

随后通过 IDA 的四个调用点确认：

- 普通 OCR、截图 OCR、图像 OCR 都使用 5 参数版本，parent 为 nullptr；
- 6 参数版本位于图像分段/翻译相关流程，额外布尔值不是 Alt+X 普通 OCR 的主路径。

因此源码恢复为：

~~~cpp
api.pixOcrObjectCtor(
    ocrObject.data(),
    image.data(),
    params.data(),
    kOcrModeFull,
    nullptr);
~~~

### 5.3 从结果得到的中间结论

恢复 5 参数版本后，Bridge 已从约 5 秒降到约 1.59 秒，与 PixPin 约 1.5 秒基本一致。这里的因果关系要分开记录：推理次数从 5 变成 3 主要由构造重载恢复造成；后续候选相关输入仍是 91 对 59，说明参数默认值问题尚未解决。

此时不应再改线程、管道或模型加载。因为这些修改无法解释“检测阶段完全相同、检测后候选数不同”的现象。下一步必须进入参数对象本身。

## 6. 阶段 D：定位 PixOcrParams 的真实语义

### 6.1 先比较差异出现的位置

对照日志可以这样读：

~~~text
检测模型：两边都是 1 次，输入输出相同
识别阶段：Bridge 的候选框更多
后续版面/段落阶段：Bridge 因候选框增多而出现额外推理
~~~

所以问题很可能不是模型路径。需要注意，日志里的 modelPath: "" 不能单独解释为“路径为空导致失败”：同一条日志同时有非零 modelDataSize，说明该 runner 可能使用已读入的模型数据或内部缓存。这里真正的证据是模型已经成功推理，故模型加载不是当前首要矛盾。

当前 Bridge 只做了四个 QString 的构造：

~~~cpp
qStringCstrCtor(params + 0x00, detectionPath);
qStringCstrCtor(params + 0x50, recognitionPath);
qStringCstrCtor(params + 0x60, language);
qStringDefaultCtor(params + 0x68);
~~~

这能让对象“可构造”，却不代表数值字段正确。未写入的 double、int、float、bool 全部保持零，等价于把 PixPin 的检测阈值和后处理开关改成了另一套配置。

### 6.2 为什么必须观察 PixPin 自己的调用现场

最初曾猜测模型字段是“地址+长度”，后来又猜测是 QByteArray。这些猜测都没有让日志中的模型语义发生变化。原因是：反汇编可以告诉我们“字段被怎样复制/析构”，但未必能告诉我们“字段在业务上代表模型路径还是模型字节”。

因此切换方法：

1. 在 x64dbg 中附加到 PixPin；
2. 让 PixPin 继续运行，不要在启动挂起时发送 Alt+X；
3. 在 PixOcrObject 的 5 参数构造入口断点；
4. 触发 Alt+X 并框选小段文字；
5. 观察传入参数对象的内存和字符串引用；
6. 在 IDA 中用同一对象偏移对照默认构造函数。

现场确认模型相关字段是路径字符串，语言字段是 zh-cn。这一步比继续猜 QByteArray 可靠，因为它直接观察了官方程序传入的真实对象。当前样本使用 ASCII 路径；如果模型目录包含中文或其他非 ASCII 字符，不能默认 const char* 构造在所有系统区域设置下都正确，应改用已验证的宽字符/QString 转换并重新回归。

## 7. 阶段 E：从 IDA 默认构造函数恢复 0x80 字节布局

### 7.1 定位默认构造函数

在 IDA 伪代码中，多个构造调用点都先调用 sub_7FF72013A510。该函数连续写入 QString 对象、double、int、float、bool 数值；随后这些对象被作为 PixOcrObject 的 PixOcrParams 参数传入，且析构路径按同样的 QString 偏移释放。调用点、对象生命周期和字段访问三者相互对应，才是把它识别为默认构造函数的依据，不是仅凭函数名猜测。

因此它不是普通的业务函数，而是 PixOcrParams 的默认构造函数。最大字段到 0x78，对象有效布局至少覆盖到 0x80。

复核常量时要区分类型：0.6f 的 IEEE-754 位模式是 0x3f19999a，0.52f 是 0x3f051eb8；IDA 可能把它们显示为整数或十六进制常量，先按字段类型解释再写入。bool 字段在当前 MSVC/Qt ABI 中按 1 字节使用，但仍应以实际读写指令验证。

### 7.2 复原出的布局

下表只记录当前版本已经从伪代码确认的字段。它不是公开 SDK，也不保证未来 PixPin 版本不变。

| 偏移 | 类型 | 反汇编直接确认的值 | 业务含义 |
|---:|---|---:|---|
| 0x00 | QString | 运行时字符串 | 检测模型路径（现场确认） |
| 0x08 | double | 0.5 | 数值字段；具体阈值名是推测 |
| 0x10 | double | 0.25 | 数值字段；具体阈值名是推测 |
| 0x18 | double | 0.3 | 数值字段；具体阈值名是推测 |
| 0x20 | double | 1.2 | 数值字段；具体缩放含义是推测 |
| 0x28 | int | 5 | 数值字段；具体上限含义是推测 |
| 0x2C | int | 1000 | 数值字段；具体上限含义是推测 |
| 0x30 | double | 8.0 | 数值字段；具体含义是推测 |
| 0x38 | double | 0.3 | 数值字段；具体含义是推测 |
| 0x40 | double | 0.8 | 数值字段；具体含义是推测 |
| 0x48 | double | 0.8 | 数值字段；具体含义是推测 |
| 0x50 | QString | 运行时字符串 | 识别模型路径（现场确认） |
| 0x58 | float | 0.6 | 识别相关数值字段，名称未完全确认 |
| 0x5C | bool | false | 识别相关开关，名称未完全确认 |
| 0x60 | QString | zh-cn | 语言字段（现场确认） |
| 0x68 | QString | 空字符串 | 保持合法 Qt 字符串对象 |
| 0x70 | float | 0.52 | 段落/后处理相关数值字段，名称未完全确认 |
| 0x74 | bool | true | 段落/后处理相关开关，名称未完全确认 |
| 0x78 | double | 1.2 | 段落/后处理相关数值字段，名称未完全确认 |

### 7.3 精简后的初始化思路

下面是教学用伪代码，不是可直接编译的独立程序。Api、Storage、writeDouble 等名称代表项目已有的函数指针、对齐存储和按字节写入辅助函数；真正实现还必须保留错误检查、对象对齐和异常路径。不要用 C++ 普通结构体猜布局，也不要只靠 memset。因为 QString 是 Qt 对象，必须调用目标 Qt DLL 中的构造函数和析构函数；数值字段才可以按偏移写入。

~~~cpp
void initializePixOcrParams(
    void* storage,
    const char* detection,
    const char* recognition,
    const char* language,
    const Api& api) {
    auto* bytes = static_cast<std::uint8_t*>(storage);

    api.qStringCstrCtor(bytes + 0x00, detection);
    api.qStringCstrCtor(bytes + 0x50, recognition);
    api.qStringCstrCtor(bytes + 0x60, language);
    api.qStringDefaultCtor(bytes + 0x68);

    writeDouble(bytes + 0x08, 0.5);
    writeDouble(bytes + 0x10, 0.25);
    writeDouble(bytes + 0x18, 0.3);
    writeDouble(bytes + 0x20, 1.2);
    writeInt(bytes + 0x28, 5);
    writeInt(bytes + 0x2C, 1000);
    writeDouble(bytes + 0x30, 8.0);
    writeDouble(bytes + 0x38, 0.3);
    writeDouble(bytes + 0x40, 0.8);
    writeDouble(bytes + 0x48, 0.8);
    writeFloat(bytes + 0x58, 0.6f);
    writeBool(bytes + 0x5C, false);
    writeFloat(bytes + 0x70, 0.52f);
    writeBool(bytes + 0x74, true);
    writeDouble(bytes + 0x78, 1.2);
}
~~~

调用点只保留一个高层动作：

~~~cpp
initializePixOcrParams(
    params.data(), detection, recognition, language, api_);
api_.pixOcrObjectCtor(
    ocrObject.data(), image.data(), params.data(), kOcrModeFull, nullptr);
~~~

真实实现中的 Storage 至少要满足三点：分配容量不小于工作区常量，起始地址满足 Qt/C++ 对象所需的对齐；每个 QString 构造成功后才把对应字段标记为已构造；中途失败时只析构已经成功构造的字段。writeDouble、writeInt、writeFloat、writeBool 应使用固定宽度类型和 memcpy/等价的对齐安全写入，writeBool 只写 1 字节，不能用错误的 4 字节写入覆盖相邻字段。这些安全条件是伪代码省略的实现责任。

Bridge 仍使用 0x100 字节工作区，是保守的工作区选择，不等于已经证明 ABI 会访问完整的 0x100 字节；IDA 观察到的字段布局本身是 0x80。验证余量是否足够的方法是对默认构造、复制、OCR 构造和析构路径分别下断点，记录访问的最大偏移，再做连续回归和堆检查。两个数字不要混淆。

### 7.4 资源释放顺序

请求完成后，必须在 Qt 对象仍然有效的前提下完成 JSON 序列化；随后先销毁 PixOcrObject 和 QImage，再销毁参数中的 QString 以及 JSON 临时对象。下面只展示参数字段的反向析构，完整顺序以 main.cpp 的 RAII/清理路径为准：

~~~cpp
api_.qStringDtor(params + 0x68);
api_.qStringDtor(params + 0x60);
api_.qStringDtor(params + 0x50);
api_.qStringDtor(params + 0x00);
~~~

如果升级 DLL 后字段偏移变化，旧析构顺序也可能导致堆损坏；因此每次升级都必须重新验证构造、复制和析构访问范围。

## 8. 阶段 F：验证修复，而不是只看程序“不崩”

### 8.1 两次修复分别验证

第一组只比较 OCR 构造重载，使用同一份 test2.png：

~~~text
5 参数构造：5 次 → 3 次 inference，约 5 秒 → 1.59 秒
6 参数构造：以 0xC0000374 退出，不作为最终方案
~~~

第二组固定 5 参数构造，再比较是否补齐默认字段：

~~~text
候选相关输入计数：约 91 → 65
OCR compute：约 1.59 秒 → 1.228 秒
推理序列：仍为 3 次，但后处理输入规模明显收敛
~~~

日志恢复为：

~~~text
检测模型：1 次
识别模型：1 次
版面/段落模型：1 次
~~~

这比单看“总耗时下降”更有说服力，因为推理次数和分支结构也回到了 PixPin 的形状。

### 8.2 正式服务回归

结束所有旧服务进程后重新编译正式 pixpin_ocr_service.exe，再通过命名管道客户端提交同一图片。最终结果：

~~~text
read_ms          ≈ 16.984 ms
conversion_ms    ≈ 2.102 ms
compute_ms       ≈ 1227.720 ms
roundtrip_ms     ≈ 1229.520 ms
exit             = 0
~~~

因此这次正式回归的单次请求约 1.23 秒。它是一次指定图片、指定机器和指定进程状态下的测量，不是统计意义上的稳定均值；若要发布性能结论，应重复多次并分别报告冷启动、预热和稳态数据。服务协议、BGRA 转换和 JSON 返回仍然工作正常。

### 8.3 对候选框数量的谨慎解释

PixPin 对照日志是 59 个候选相关输入计数，Bridge 修复后是 65 个；不能直接宣称二者已经逐框完全一致，因为 PixPin 与 Bridge 的最终日志分别记录为 1121×586 和 1120×586。尺寸差异可能改变结果，但本轮没有做“只改变一列像素”的隔离实验，所以它只是待验证假设，不是已证明的根因。

正确表述是：构造重载修复使推理次数从 5 回到 3；完整参数修复使后处理候选相关输入规模显著接近 PixPin；性能回到同一量级；仍需用完全相同的像素缓冲区、尺寸和哈希做最终逐框比较。

## 9. 哪些探索被保留为失败经验

### 9.1 把总耗时归因于冷启动

冷启动确实存在，但不能解释 3 次与 5 次推理的结构差异。正确做法是先比较日志中的模型次数、输入尺寸和候选数。

### 9.2 盲目使用 6 参数构造函数

DLL 存在某个重载，不代表当前业务路径应该使用它。必须从调用点所属功能确认；Alt+X 普通 OCR 最终确认使用 5 参数版本。

### 9.3 手动预热 getInstance()

导出函数不等于稳定公共接口。包含手动预热的实验触发 OpenCV 空图错误，说明调用上下文可能不完整；应撤销，而不是用更多异常捕获掩盖生命周期问题。

### 9.4 把 Qt 字段当成普通字节

全零内存、裸指针或猜测的 QByteArray 都不能替代 QString 正确构造。ABI 逆向的基本纪律是：只要字段会被 Qt 复制、赋值或析构，就必须用同一 Qt DLL 的对象函数初始化。

### 9.5 只验证“能输出 JSON”

能输出 JSON 只说明调用链没有立即崩溃，不说明参数和业务分支正确。还要检查推理次数、候选框数量、模型输入规模、耗时和结果质量。

## 10. 初学者可复用的调试决策树

1. 程序启动即失败：先用 Dependencies/Process Explorer 检查 DLL 搜索目录和位数。
2. QImage 构造处崩溃：用 x64dbg 看构造函数重载、像素指针、stride 和对象存储生命周期。
3. PixOcrObject 构造处崩溃：检查 QString 是否由 Qt 构造函数初始化，不能只分配零字节缓冲区。
4. 模型大小为零：在 x64dbg 中对比 PixPin 现场，确认参数是路径字符串还是内存容器，不要凭字段名称猜语义。
5. 识别完成、序列化时崩溃：检查 C++ 隐藏返回对象和 this 指针顺序，尤其是 QJsonDocument/QByteArray 按值返回。
6. 检测一致、后处理不一致：优先逐字段对照 PixOcrParams，再检查构造重载和模式值。
7. 推理次数一致但候选数略有差异：先确认图片字节级一致，再比较阈值和后处理字段。
8. 编译时 exe 被占用：结束旧进程，并用独立实验文件名，不要反复覆盖正式文件。

## 11. 最终产物与版本边界

本轮产物包括：

- main.cpp：新增完整的 PixOcrParams 初始化，并恢复 5 参数 OCR 构造调用；
- pixpin_ocr_service.exe：重新编译并完成命名管道回归；
- 若干独立 A/B 可执行文件：仅用于验证 5/6 参数构造和错误预热假设，不属于最终方案；
- 本教程：把原始探索压缩成可复现的决策链。

版本边界必须写清楚：

- PixOCR2.dll 是未公开的 Qt/C++ ABI，不是稳定 C API；
- PixOcrParams 偏移和默认值只对本次分析的 x64 DLL 版本成立；
- PixPin 升级后必须重新检查导出符号、构造调用点、默认构造函数和析构访问范围；
- 最终性能数字来自特定图片、特定机器和特定模型，不能当作所有图片的保证。

## 12. 一句话总结

这次问题的根因不是“Bridge 不会调用 OCR”，而是“Bridge 只构造了一个能运行的 PixOcrParams 外壳，却没有复现 PixPin 默认参数”。先用日志定位差异出现在哪个模型阶段，再用调用点确认构造重载，最后从默认构造函数恢复字段，才能把性能和推理分支真正对齐。
