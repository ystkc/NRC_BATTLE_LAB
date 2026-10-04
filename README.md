# NRC Battle Lab

## Manual battle input

OCR is no longer required for manual collection. Start the browser recorder from the repository root:

    python scripts/manual_input.py

Open http://127.0.0.1:8766/. The recorder reads Pokémon and skills from data/nrc_wiki.db, indexes Chinese initials and full pinyin, removes apostrophes from queries, and sorts shorter candidates first. Use 1-9, arrow keys, Tab, Space, and Enter in candidate fields. Numbers are ignored when the input is empty.

The opening screen records only six names and maximum HP values per side. Current HP is initialized to maximum HP and energy to 10. Enter /nc from the central command popup to skip the opponent lineup, then start with /start 1 or /start 2; the number selects the starting side. After starting, the lineup screen is hidden and only the active creature's four skills are editable.

During battle, k focuses the next unknown own skill and l does the same for the opponent. e edits energy, p edits power, and u/d changes the effect indicator. m/n opens opponent/own action input: mk1-mk4 selects a skill, ms1-ms6 switches, me means 聚能, and mp means item. Esc cancels focus. Press Enter twice within one second, or click 下一回合, to save the complete nrc_core request automatically.

The overlay sidebar contains the battle and round tree. Internal battle IDs and round numbers are not editable fields. Unknown Pokémon and skills remain explicit unknown/manual values rather than being silently discarded.

### Wiki crawler

The maintained BeautifulSoup crawler lives in `scripts/wiki_crawler/`:

    python -m scripts.wiki_crawler --kind all --verbose

It downloads assets and prepares a staged incremental report, then requests
confirmation before writing canonical CSV/JSON and `data/nrc_wiki.db`.
Use `--stage-only` to inspect without committing and `--crawl-skill-relations`
to opt into skill-detail relationship collection. Only the current v2 schema
is supported; obsolete scrapers, alias entry points, and migration code have
been removed. Existing battle consumers still use the separate `data/nrc_wiki.db`.
See `scripts/wiki_crawler/README.md` for usage, tables, and SQLite queries.


## Windows real-time battle monitor

The real-time path is intentionally separate from the offline video auditor.
It captures only the selected window's client area, runs cheap downsampled
ROI/color-structure tests, and never invokes OCR in the capture loop.

Start it from `NRC_BATTLE_LAB` on Windows:

    pip install -e ".[screen]"
    python scripts/run_realtime_monitor.py --output data/screen/live.mp4

When prompted, switch to the target game window. The monitor watches the
foreground top-level window, ignores its own console, and records its client
rectangle. The detector transitions through state 1 (entrance), state 2
(normal/聚能 icon), and state 3 (skill banners). The speed-comparison panel is
reported as transient state 4 and does not change the underlying state.

### Control pipe

The monitor exposes a line-delimited UTF-8 JSON pipe at
`\\.\pipe\nrc-battle-lab` by default. The request is one JSON object per line:

    {"op":"status"}
    {"op":"ocr","feature":"perform","timeout":5}
    {"op":"ocr","feature":"speedcomp","timeout":5}
    {"op":"ocr","feature":"current"}

`feature` waits for a newly captured frame containing the requested feature,
then sends that full BGR frame as BGRA32 over the persistent OCR pipe from
`ocr_service/protocol.md`. Supported aliases include `entrance`, `normal`,
`perform`, `perform_counter`, `speedcomp`, `state1`-`state4`, and `current`.
OCR has a one-item latest-frame queue: a slow OCR request never backlogs
frames or blocks recording. The OCR service pipe defaults to
`\\.\pipe\pixpin-ocr` and can be changed with `--ocr-pipe`.

## Screen-stream collection

### Pixel-based entrance region detection

Run from NRC_BATTLE_LAB:

    python -m collector.screen.entrance_regions --image ../entrance.jpg --compare-raw --repeats 5
    python -m unittest tests.test_entrance_regions -v

The feature detector in collector/screen/entrance_detector.py receives only a
BGR image. It does not load annotation coordinates, fixed ROIs, screenshot
templates, or scoring weights. It searches the entire image for:

- Repeated, vertically aligned green health bars, used as local card anchors.
- Dark/gold connected components containing each health bar. Row projections
  separate the card body from its protruding circular badge.
- Circular badges near each measured card body, using local Hough detection.
- Long dark strips, gold rounded buttons, enclosed artwork above a detected
  team, and a near-square bright emblem with a low-saturation surrounding disc.

The optimized variant derives a shared card width from the longest observed
card in each detected stack. Border allowances are proportional to measured
health-bar or panel dimensions, not annotation coordinates. The raw-contour
variant disables these two refinements for comparison.

Annotations live in data/screen/entrance_references.json and are consumed only
by the evaluator. The report and annotated image are written to
data/screen/inspection/entrance_regions.json and entrance_regions.jpg.

The JSON includes all five detect(image) timings, their mean, per-reference
coverage, and penalty details. Timing includes segmentation, contour extraction,
Hough detection, and box construction; file I/O, imports, drawing, and scoring
are excluded. OpenCV uses one worker thread for this benchmark.

The supplied rule charges area * weight for a completely missed reference,
10 points per predicted pixel outside the reference union, 15 points per pixel
for a completely disjoint prediction, and 10 points per millisecond. Because
partial-overlap treatment is unspecified, coverage_score additionally charges
uncovered reference pixels * weight. This stricter diagnostic prevents a tiny
intersecting box from claiming full recall. Both scores must remain positive
in the real-frame regression test. Overlapping references use union geometry.

Reference rectangles remain unchanged even outside the image: the right
banner ends at x=1561 while entrance.jpg is 1558 pixels wide. The conservative
score includes this unobservable strip rather than hiding it by clipping the
annotations. The detector is specialized to these UI colors and shapes; it
does not claim general object recognition or support arbitrary color themes.

### Single-frame structural inspection

Before enabling OCR, inspect the cheap geometric detectors on a supplied
frame. This writes an annotated image and a JSON feature dump without loading
or running OCR:

    python scripts/inspect_frame.py --image ../entrance.jpg \
      --output data/screen/inspection/entrance_annotated.jpg \
      --json data/screen/inspection/entrance.json

The detector draws fixed ROIs, dark-banner candidates, bright-panel
candidates, horizontal information bands, and rough skill-card contours.

### Semantic-segmentation baseline

The repository also includes a model-based segmentation experiment. It uses
the COCO-pretrained torchvision DeepLabV3 model and writes an original-size
label mask, a color overlay, and per-class pixel statistics:

    pip install -e ".[segmentation]"
    python scripts/semantic_segment.py ../entrance.jpg ../normal.jpg \
      --output-dir data/screen/inspection/segmentation

This checkpoint is a generic object model, not a game-UI model, so labels such
as `health_bar`, `skill_card`, and `button` are not expected to appear. The
CLI keeps the backend and output contract isolated so a UI-specific checkpoint
can later replace `DeepLabSegmenter` without changing the inspection flow.
For production UI recognition, annotate masks for a small vocabulary such as
`ui_panel`, `health_bar`, `skill_card`, `status_icon`, `button`, and `text`
and fine-tune a lightweight segmentation backbone on screenshots from several
resolutions and UI states.

The mitmproxy path is not required for screen-based auditing. Install the
optional screen dependencies and run the complete video-to-record pipeline:

    pip install -e ".[screen]"
    python scripts/collect_video.py \
      --video ../recording_20261001_162236.mp4 \
      --references .. \
      --output data/screen/battle_record.json

The output preserves raw OCR/template evidence, the detected turn boundary,
the database rows used by the simulator, the full simulator result, and a
calculation trace. Unknown OCR or an unpaired action remains explicit and can
be corrected with a manifest:

    {"events": [{"time": 9.6, "side": "opponent", "skill_name": "力量增效"}]}

Use --no-simulate when only collecting evidence. --sample-fps 10 is the
default because short willpower animations may not appear in a single frame.

新的、与原 `NRC_AI` 隔离的洛克王国战斗核心与对战数据审计项目。

当前阶段不包含 Web 前端、FastAPI 后端和旧 MCTS 入口，只保留：

- `src/`：复制并隔离的旧规则执行内核（数据模型、战斗流程、效果引擎、数据库加载）
- `nrc_core/`：新的稳定输入/输出协议和核心适配器
- `collector/`：技能/特性审计、分支匹配、mitmproxy 原始流采集
- `scripts/`：数据库工具和审计命令；爬虫独立位于 `scripts/wiki_crawler/`
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

## 当前限制

1. 旧核心中的部分技能/特性仍是历史实现，需通过 mitmproxy 数据逐条校准。
2. 道具动作协议已经存在，但愿力/首领化规则尚未接入。
3. 对手隐藏技能可以输入为未知，但当前规则执行需要当前回合实际出招的技能名；上层采集器应在截获出招后补齐。
4. 特性只标记可能触发的时机，复杂条件需要人工确认后写入审计记录。
5. 解析器不是最终规则引擎；它首先服务于“哪些分支需要采集”和“哪些分支已被实际观察”。
