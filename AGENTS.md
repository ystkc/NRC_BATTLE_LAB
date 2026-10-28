# NRC Battle Lab

洛克王国 NRC 对战：Python 规则模拟器核心 + 多回合战斗状态记录平台 + Web 用户界面，AI 搜索训练待开发，屏幕 OCR 采集暂时废弃。Python ≥3.10。数据与注释以中文为主。

# 中文文件读写规则（重要。本节内容仅适用于Codex。Claude Code直接走默认方式即可，无需理会本节）

- 如果在使用下列流程指定的工具进行中文文件读写时遇到错误、乱码，请务必报告用户；
- Windows 下补丁文件必须通过 `functions.exec` 内的原生 `tools.apply_patch(patch)` 完成；不要在 PowerShell 中调用 `apply_patch`、`apply_patch.bat` 或 `codex --codex-run-as-apply-patch`。禁止使用Unicode编码编写中文（\uXXXX）。
- 该项目为UTF-8编码，PowerShell 的 `Get-Content` 用系统默认编码解读 UTF-8 会显示为乱码，务必记得加上 -Encoding utf8 或用 Node.js `fs.readFileSync(path, 'utf8')` 读取


## 架构

- `nrc_core/` 单回合规则引擎，不依赖上层
- `nrc_platform/` 多回合战斗状态记录平台与**唯一查库层**
- `nrc_server/` 双人 Web 对战用户界面
- `nrc_ai/` 信念粒子、搜索、自博弈、训练
- `ocr_service/` PixPin OCR 命名管道（预编译 exe）；暂时废弃无需理会
- `scripts/` 功能脚本
- `wiki_crawler/`：爬虫，Wiki → CSV & `data/nrc_wiki.db`
- `data/` 规则文档：`*.md`（优先级最高）、`wiki/*.csv`（供人工核对）、`nrc_wiki.db`（供程序查询）
- `tests/` 临时测试脚本
- `./track.md` 为用户备忘录无需理会

## 架构规则

- `nrc_core` 属于全知核心，所有规则硬编码，不查库、不做名称搜索、不解析技能描述、不具备猜隐藏信息的能力。
- `nrc_platform` 属于全知和非全知的分界线，目前仅提供双人对战功能，即双方分别输入操作，模块将历史状态信息合并后通过nrc_core计算结果，然后遮蔽对手部分信息后分别返回给两个用户；
- 未实现机制抛 `UnsupportedMechanicError`，不静默降级。
- 规则依据顺序：`data/*.md` → `data/部分规则详解/` → `data/wiki/game_descriptions.csv` → 请用户解释。未注明随机的机制不得使用随机数，禁止凭空推测规则。

## agents编写规则

- 建议对于verbose命令，使用subagent执行，例如git挖掘，日志分析，批量测试等。如果要调用subagent，请务必使用6.1-Sol模型的Low Effort
- 减少tests脚本，只有你觉得非常不确定非常没有信心极有可能出现问题的代码才需要测试
- 这个项目需要维护人类可读性和开发性，需要将功能类似的代码集中并模块化，避免复杂难度的逻辑
- 在关键且难以理解的位置增加中文注释，且务必简洁，原则上一个函数不应超过5处
- 为函数、类和文件的开头增加中文描述字符串，且务必简洁
- 前端测试不应使用computer-use技能，而是使用node已安装好的playwright，并显式指定channel为chrome

## 命令

```bash
pip install -e ".[dev]"
python -m nrc_server.server --host 127.0.0.1 --port 8767
python -m pytest tests/test_platform_boundaries.py -q
python scripts/generate_skill_effects.py
python -m wiki_crawler --kind all --stage-only     # 确认写库加 --yes
```

## 重要模块垂直位点记录（请持续维护）

如果出现了新的重要但是未记录的模块，请完善到此表格；如果现有的过期/笼统，请进行更新和拆分。

| 任务 | 文件 |
|---|---|
| 伤害和回合结算 | `nrc_core/core.py:simulate_turn`、`nrc_core/battle.py` |
| 效果原语与注册 | `nrc_core/engine/registry.py:_HANDLERS`、`handlers_skill.py`、`handlers_ability.py`、`handlers_field.py` |
| 技能效果生成 | `scripts/generate_skill_effects.py`、`nrc_core/skill_effects_generated.py` **生成文件勿手改** |
| 特性原语 | `nrc_core/effect_models.py` |
| 特性阶段分发与攻击前修正 | `nrc_core/effect_models.py:Timing`、`nrc_core/engine/executor.py:EffectExecutor.execute_ability`、`handlers_skill.py:_h_damage` |
| 冻结施加与冻结成功特性事件 | `nrc_core/models.py:add_freeze_stacks` |
| 技能数据 | `nrc_core/effect_data.py` |
| 属性克制 | `nrc_core/models.py:get_type_effectiveness` |
| 六维和资质公式 | `nrc_core/catalog.py:calc_combat_stats` |
| 对战状态显示与战报可见性 | `nrc_platform/rooms.py:_visible_events`、`nrc_platform/state.py:normalize_observation`、`nrc_server/static/app.js` |
| 全技能修正归属与特性触发战报 | `nrc_core/engine/dispatch.py:_apply_tag`、`helpers.py:_record_public_skill_modifier`、`executor.py:EffectExecutor.execute_ability` |
| 平台状态分类与可见性适配 | `nrc_platform/state.py:normalize_observation`、`nrc_platform/platform.py:get_public_observation` |
| 核心初始化、决策、合法动作和只读预览 | `nrc_core/runtime.py:BattleRuntime` |
| 双人房间准备、确认与身份 | `nrc_platform/rooms.py:RoomService` |
| 提交事务与新快照 | `nrc_platform/platform.py:_serialized`、`submit_selection`、`export_battle` |
| 强化学习和MCTS | `nrc_ai/` 暂存，旧 CLI 停用 |
