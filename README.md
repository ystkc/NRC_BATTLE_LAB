# NRC Battle Lab

新的、与原 `NRC_AI` 隔离的洛克王国战斗核心与对战数据审计项目。

当前阶段不包含 Web 前端、FastAPI 后端和旧 MCTS 入口，只保留：

- `src/`：复制并隔离的旧规则执行内核（数据模型、战斗流程、效果引擎、数据库加载）
- `nrc_core/`：新的稳定输入/输出协议和核心适配器
- `collector/`：技能/特性审计、分支匹配、mitmproxy 原始流采集
- `scripts/`：原有爬虫、数据库工具和新审计命令
- `data/`：SQLite、`skills_all.csv` 等必要资源

## 核心入口

```python
from nrc_core import BattleSimulator

result = BattleSimulator().resolve_turn(request_dict)
payload = result.to_json()
```

输入的核心结构：

```json
{
  "own_team": {"creatures": [], "active_index": 0},
  "opponent_team": {"creatures": [], "active_index": {"known": false}},
  "shared": {
    "turn": 1,
    "weather": {"known": false},
    "mp": {"own": 4, "opponent": {"known": false}}
  },
  "own_turn": {
    "primary": {"kind": "skill", "skill_name": "技能名"},
    "items": []
  },
  "opponent_turn": {
    "primary": {"kind": "charge"},
    "items": []
  },
  "seed": 7
}
```

`primary` 只能是 `skill`、`charge`、`switch`、`pass`；`items` 可附带 `willpower` 或 `boss`。技能槽位支持 `skill_id`、`name`、`current_energy_cost`、`current_power` 和 `use_count`；这些字段会随回合结果返回，适合表达机械变式、传动和其他永久改写。精灵支持 `entry_count`，状态支持 `fatigue_turns`。

队伍可以同时传入指定奉献和随机奉献。随机奉献不会展开为所有层数分配，而是作为带上下界的潜变量返回到 `latent_uncertainties`；训练时由上层采样具体离散隐藏状态，观测到受奉献影响的技能结果后再回填 `random_counts`。

所有输入字段均支持：

```json
{"known": false, "reason": "对手尚未展示"}
```

这用于表达“未知”和“确认不存在”的区别，而不是用 `null` 混淆。

## 技能分支审计

从完整技能描述生成审计表：

```bash
python scripts/build_skill_audit.py
```

输出：

- `data/audit/skills_audit.json`：完整机器可读表，含原文、命中模式、效果原子、分支组合和人工状态
- `data/audit/skills_audit.csv`：人工快速浏览表
- `data/audit/skills_unresolved.csv`：必须人工修改/补充的技能

当前固定模式包括：

- `probability:triggered` / `probability:not_triggered`
- `gulu_ball:normal|advanced|gold|prism|type`
- `counter:success|failure`
- `self_attribute:*`
- `opponent_attribute:*`
- `devotion_effect:latent`：随机奉献，不进入普通审计笛卡尔积
- `condition:true|false`

属性分支采用 18 个属性；多个条件会保留为“分支数组 × enum 选项”，并限制最多 128 个组合。随机奉献使用潜变量策略；随机技能、技能复制/替换以及超过组合上限的技能仍进入人工队列，不静默生成错误规则。

特性暂时只生成手工审计表：

```bash
python scripts/build_ability_audit.py
```

该命令同时生成 `data/audit/abilities_uncertain.csv`。其中的关键词只是审计辅助候选，不会直接改变战斗规则；确认后再绑定到 `Timing` 和特性原语。模拟器结果的 `effectiveness` 字段会提供属性倍率、是否克制、是否抵抗和是否免疫，供“最好的伙伴”等特性审计加速使用。

`借用`、`取念`、`复写`按每回合开始后已经观测到的当前技能状态处理，不作为随机审计分支；`水星水`只保留 `counter:success` 和 `counter:failure` 两个审计分支，属性状态只影响成功分支的计算。

## mitmproxy

当前插件只保存原始请求/响应，不猜测游戏协议：

```bash
pip install -e ".[collector]"
mitmdump -s collector/mitmproxy_addon/collector_addon.py \
  --set nrc_output=data/mitm/raw.jsonl
```

后续流程应为：

```text
原始流 → 协议归一化 → BattleRequest → 核心模拟 → 与实际结果对比 → 唯一分支匹配 → 回填审计表
```

半自动操作规划器已经提供：

```bash
python scripts/plan_collection_action.py --request path/to/request.json
```

它会优先选择当前精灵仍有未记录分支的已知技能；若当前已知技能没有待审分支，则建议聚能。真正的“实际结果 → enum 指标”归一化必须由后续 mitmproxy 协议适配器提供，匹配器遇到 0 个或多个候选时会保留为失败/歧义，不会自动污染审计记录。

## 原有爬虫

原项目的技能、精灵和技能关系爬虫已保留在 `scripts/`：

- `scrape_skills.py`
- `scrape_skills_bilibili.py`
- `crawl_pokemon_skills.py`
- `crawl_spirits.py`

## 当前限制

1. 旧核心中的部分技能/特性仍是历史实现，需通过 mitmproxy 数据逐条校准。
2. 道具动作协议已经存在，但愿力/首领化规则尚未接入。
3. 对手隐藏技能可以输入为未知，但当前规则执行需要当前回合实际出招的技能名；上层采集器应在截获出招后补齐。
4. 特性只标记可能触发的时机，复杂条件需要人工确认后写入审计记录。
5. 解析器不是最终规则引擎；它首先服务于“哪些分支需要采集”和“哪些分支已被实际观察”。
