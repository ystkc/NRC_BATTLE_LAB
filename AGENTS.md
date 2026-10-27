# NRC Battle Lab

洛克王国 NRC 对战：Python 规则模拟器核心 + 多回合战斗状态记录平台 + Web 用户界面，AI 搜索训练待开发，屏幕 OCR 采集暂时废弃。Python ≥3.10。数据与注释以中文为主。

## Windows 补丁协议（强制要求）

- Windows 的修改必须使用原生补丁工具，通过 `functions.exec` 在 JavaScript 代码中直接调用 `tools.apply_patch(patch)`。
- 当原生工具可用时，切勿通过 PowerShell 调用 `apply_patch`、`apply_patch.bat` 或 `codex.exe --codex-run-as-apply-patch`。
- 如果出现 UTF-8 补丁参数错误，切勿重复执行相同命令或重新打印相同补丁。应立即切换到原生工具。
- 如果原生工具不可用，请在 `%TEMP%` 目录下创建一个 UTF-8 补丁文件，验证 `*** Begin Patch` 和 `*** End Patch` 标记，然后从 Node 子进程中调用 Codex 可执行文件。切勿使用 `.codex` 作为临时目录。

## 架构（依赖只向下，nrc_core 不依赖上层）

- `nrc_core/` 纯规则引擎。`core.py:simulate_turn`；`engine/_monolith.py` 效果执行（`_HANDLERS` 注册表）；`effect_models.py` 原语；`effect_data.py` 技能数据；`skill_effects_generated.py` **生成文件勿手改**（源：`scripts/generate_skill_effects.py`）；`catalog.py` 只读注入 `CoreCatalog`；`training.py:create_backend`。
- `nrc_platform/` 多回合状态与**唯一查库层**。`platform.py:BattlePlatform`；`catalog.py` 读 `data/nrc_wiki.db`；`README.md` §8 为上层 API 契约。
- `nrc_server/` 双人 Web 对战台（:8767，`server.py` + `static/app.js`，会话内存态）。
- `manual_input/` 手动录入与预测对比（:8766）。
- `nrc_ai/` 信念粒子、搜索、自博弈、训练（`cli.py`；协议见 `contracts.py`；`interface.py` 读平台观察者视角）。
- `ocr_service/` PixPin OCR 命名管道（预编译 exe）；`ocr_benchmark/` OCR 选型实验。
- `scripts/` 维护入口（`wiki_crawler/`：Wiki → CSV → `data/nrc_wiki.db`）。
- `data/` 规则文档（`*.md`，优先级最高）、`wiki/*.csv`、`nrc_wiki.db`（v2）、`audit/`。
- `tests/` pytest（`pythonpath="."`）。`track.md` 为任务清单。

## 硬规则

- `nrc_core` 不查库、不做名称搜索、不解析技能描述、不猜隐藏信息。对手观测不含对手技能、特性、隐藏属性。
- `advance()` 收到动作缺失、多余、非法或游戏已结束时直接报错，不自动跳过或聚能。
- 强制换人必须是显式替补决策节点，禁止自动选第一只存活精灵。
- 力竭或全队倒下：立即结算并等待换人，有精灵力竭时不得开始下一回合。
- 回合开始的特性、传动、天气在 `observe()` / `legal_actions()` 之前结算。
- 随机只用 `nrc_core.rng` 的作用域随机数，不用 `random`。
- 规则、数据、动作或观测语义变化，必须升级 `CoreManifest` 对应版本号。
- 未实现机制抛 `UnsupportedMechanicError`，不静默降级。
- 规则依据顺序：`data/*.md` → `data/部分规则详解/` → `data/wiki/game_descriptions.csv` → 请用户解释。禁止凭空补规则。
- 正式任务显式使用 `nrc_core.training:create_backend`，不回退到 `nrc_ai.toy_backend`。
- 只使用 `data/nrc_wiki.db`，不写旧 `data/nrc.db`（已不存在）。
- 属性克制以 `data/属性克制表.md` 为准：双克 3x，双抗 0.25x。血脉属性不参与克制。
- 提交信息用中文短句。只在用户要求时提交。

## 术语

精灵；技能（攻击=石头 物攻/魔攻，防御=布，状态=剪刀）；能量；聚能；魔力 MP（清零即结束）；力竭；应对；先手值；拼速（同速随机）；传动；迅捷；共鸣魔法；奉献；full（全知）/ partial（有限信息，未知字段显式 `unknown`）；信念粒子（一个粒子 = 一个完整规则状态候选）。

## 命令

```bash
pip install -e ".[dev]"
python -m pytest -q
python -m nrc_server.server --host 127.0.0.1 --port 8767
python -m manual_input.server --host 127.0.0.1 --port 8766
python -m nrc_ai check --backend nrc_core.training:create_backend --setup setup.json
python scripts/generate_skill_effects.py
python -m scripts.wiki_crawler --kind all --stage-only     # 确认写库加 --yes
```

核心调试日志：环境变量 `NRC_CORE_LOG=turn,damage,...`（或 `all`，空串关闭）。

## 先 grep，勿整读

- 根目录 `*.mp4`、`*.jpg`、`rules.txt`、`1002-r*.json`；`.screen-deps/`、`ocr_service/*.dll|*.exe|model/`、`ocr_benchmark/*_results.json`、`data/*icons/`、`data/wiki_staging/`。
- 大文件：`engine/_monolith.py`、`battle.py`、`effect_data.py`、`platform.py`、`nrc_server/static/app.js`、`data/audit/skills_audit.json`。

## 任务 → 先读

| 任务 | 文件 |
|---|---|
| 伤害、回合结算 | `nrc_core/core.py`、`battle.py` |
| 技能/特性效果 | `engine/_monolith.py`、`effect_models.py`、`effect_data.py` |
| 属性克制 | `nrc_core/models.py:get_type_effectiveness` |
| 六维、资质公式 | `nrc_core/catalog.py:calc_combat_stats` |
| 平台状态与 API | `nrc_platform/platform.py`、`README.md` §8 |
| Web 对战台 | `nrc_server/server.py`、`static/app.js`、`README.md` |
| 手动录入 | `manual_input/server.py`、`catalog.py`、`README.md` |
| AI 搜索训练 | `nrc_ai/contracts.py`、`interface.py`、`cli.py`、`README.md` |
| Wiki 同步、库结构 | `scripts/wiki_crawler/sync.py`、`database.py`、`README.md` |
