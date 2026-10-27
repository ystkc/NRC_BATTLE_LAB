# NRC Battle Lab

- `nrc_core/`：核心战斗单回合模拟器。
- `nrc_ai/`：搜索、自博弈、回放与训练。
- `nrc_platform/`：多回合对战状态记录平台。
- `ocr_service/`：OCR 服务（暂时废弃）。
- `data/`：规则、素材与数据。
- `wiki_crawler/`：Wiki 数据采集器。

详细说明见各目录内的 `README.md`。安装：`pip install -e .`；运行 Wiki 同步需额外安装 `pip install -e ".[wiki]"`。
