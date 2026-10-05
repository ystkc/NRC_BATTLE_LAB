# NRC Wiki 爬虫

## 目录与入口

```text
scripts/wiki_crawler/
├── __init__.py
├── __main__.py     模块启动入口
├── sync.py         BeautifulSoup 解析、网络请求、资源缓存、增量确认
├── database.py     v2 SQLite 业务表写入、JSON 同步日志、进化查询
├── manual_data.yaml 固定的人工补充文件（含注释示例）
└── README.md       使用说明与数据库结构
```

在项目根目录启动：

```powershell
python -m scripts.wiki_crawler --kind all --verbose
python -m scripts.wiki_crawler --kind all --stage-only --verbose
python -m scripts.wiki_crawler --kind all --crawl-skill-relations --verbose
```

也可以直接执行 `python scripts/wiki_crawler/sync.py --help`。所有数据路径相对于项目根目录计算，不随启动目录改变。

## 使用与边界

- 依赖 `beautifulsoup4` 和 `PyYAML`，已包含在项目的 `collector` 可选依赖组中。
- 默认仅访问技能列表、精灵列表、精灵图鉴和游戏描述图鉴；直接读取服务器渲染的 HTML，不需要浏览器，也不跟随条目详情链接。
- `--crawl-skill-relations` 默认为关闭，只适用于 `--kind skills/all`；显式启用后访问技能详情，采集 `default/blood/stone` 来源的精灵技能关联。
- 资源正常下载到 `data/spirit_icons/`、`data/skill_icons/`、`data/ability_icons/`、`data/icon_rules/`，缓存命中立即返回，默认网络请求间隔为 0。
- 信息先存入 `data/wiki_staging/` 的 CSV/JSON，打印已有、新增、变更、未找到记录及每项采集的第一条完整数据，再请求最终写入同意。
- 差异比较只使用各类 canonical CSV 的业务字段，并统一为 CSV 文本格式：缺失字段、`null` 与空字符串等价，数字与相同文本（如 `1` 和 `"1"`）等价；抓取/提交时间等元数据不计入变化，业务字段实际变化仍会报告。
- 确认后更新 `data/wiki/` 的 canonical CSV/JSON 和独立的 `data/nrc_wiki.db`；不会导入或修改旧战斗数据库 `data/nrc.db`。
- `--stage-only` 不询问、也不写入 canonical 或数据库。`--yes` 表示明确允许自动写入；主要列表为空时即使带此参数也拒绝写库。
- 未找到的旧记录默认保留，移除需明确选择；`--remove-missing` 与 `--keep-missing` 可指定策略。
- `--kind skills|spirits|game-descriptions` 只更新所选类型；`--limit` 用于少量采集检查，不能把小样本当成全量结果来自动移除记录。
- `--database` 可指定其他 v2 库或新的空数据库文件。`--verbose` 输出详细网络通信日志，`--quiet` 只输出警告和错误。
- 当前仅支持已完成迁移的 v2 结构，或首次创建空库；已移除旧爬虫、兼容别名、v1 升级和旧 HTML `.divsort` 回退，不会自动修复/迁移其他结构。
- 对战、手动录入及识别模块仍读取旧 `data/nrc.db`，本模块不会切换这些消费者。它们的初始化/审计工具不是爬虫，不属于此目录。

## 人工 YAML 补充

固定文件为 `scripts/wiki_crawler/manual_data.yaml`，默认每次运行都会读取，不受启动目录影响。文件已经提供技能、精灵、游戏描述、进化、精灵技能关系五类注释示例；示例都是虚构数据，默认五个列表为空，不会污染数据库。先安装依赖：

```powershell
pip install -e ".[collector]"
python -m scripts.wiki_crawler --kind all --stage-only
python -m scripts.wiki_crawler --kind all --yes --keep-missing
python -m scripts.wiki_crawler --manual-data data/my_manual_data.yaml --stage-only
python -m scripts.wiki_crawler --no-manual-data --stage-only
```

使用示例时，将相应分类的 `[]` 删除并取消示例注释。例如给已有技能补上描述，同时录入一个 Wiki 没有的技能：

```yaml
version: 1
skills:
  - 名称: "已有技能的完整名称"
    描述: "人工核实后的技能描述。"
  - 名称: "尚未收录的技能"
    属性: "普通系"
    分类: "物攻"
    耗能: 0
    威力: 35
    描述: "人工录入的新技能。"
    标签: ["回能", "连击"]
```

- **合并规则**：按名称匹配技能、精灵、游戏描述；进化按基本名称端点匹配；技能关系按完整精灵名称、技能名和技能类别匹配。人工明确填写的字段优先，未填写的字段保留本次 Wiki 值；Wiki 没有该条记录时先使用已有 canonical/已提交记录作为基线，再补充或新增。不修改 YAML 文件本身。
- **清空与数值**：`null` 或 `""` 显式清空字段，0 保留为真实数值。编号/ID 应写成带引号的字符串（如 `"005"`）。布尔值接受 `true/false`，或带引号的 `"yes"/"no"`；未提供的数值仍按原流程保存 NULL。
- **格式与校验**：顶层支持 `version: 1` 及五个分类列表；未使用的分类可省略或写 `[]`。字段名与 `sync.py` 中的 `CSV_FIELDS` 一致，不接受未知字段、重复 YAML 字段或重复记录标识。实体必须有名称；进化必须有两端名称；技能关系必须有精灵、技能、技能类别。错误会在联网前终止，不写数据库。
- **多值字段**：精灵属性、标签、可学习精灵、立绘路径可用字符串列表，自动转为 `|` 分隔文本；也可直接填写已有 CSV 格式的字符串。
- **资源与特性**：图片路径相对于 `data/`，文件需自行放入，不自动下载人工条目的图片。特性名称、效果及图标通过精灵的 `特性/特性效果/特性图标路径` 录入，再归纳到特性目录。纯人工条目的来源默认标记为 `manual:<YAML文件名>`，也可显式填写 `来源URL`。
- **类型选择**：`--kind` 仍限制本次更新类型。人工进化仅随精灵更新；人工技能关系随技能或精灵更新，不要求启用 `--crawl-skill-relations`。未爬技能详情时，补充关系会保留已有关系，不因 `--remove-missing` 清空旧关系。
- **进化**：补充精灵后，按合并后的编号、阶段重新推断进化；显式填写的 `evolutions` 随后覆盖同端点边或新增边，默认方法为 `manual`。独立精灵的进化摘要仍按推断结果生成；人工额外边以进化表为准。
- **确认与安全**：合并后统一生成 staging、差异报告、canonical、数据库和同步日志，确认机制不变。`staging/snapshot.json` 同时记录 Wiki 数量、人工文件路径与各类人工条数。即使人工列表非空，只要所选 Wiki 主列表为空，仍拒绝正式写入，避免人工数据掩盖抓取失败。
- **长期维护**：只要字段留在 YAML 中，就会在后续同步中持续优先使用；Wiki 补齐后可删除对应字段/条目，让 Wiki 接管。人工数据本次已参与采集，不会被 `--remove-missing` 误删；从 YAML 删除整条且 Wiki 也没有时，则遵循原有旧记录保留/移除策略。

## 表结构（版本 2）

所有实体用 SQLite 整数主键。Wiki 标识和编号作为来源字段保存，不冒充可靠的关系主键。

| 表 | 内容与关键字段 |
| --- | --- |
| `skill_catalog` | 技能名称、目录 ID、系别、分类、能耗、威力、描述、赛季、近期状态、原始可学习精灵文本、图标及来源。名称唯一。 |
| `skill_tags` | 技能标签与顺序，一条技能可有多个标签。 |
| `spirit_forms` | 每个完整名称一条独立精灵：名称、Wiki ID、编号、阶段、是否首领、是否有异色、赛季、特性、六项种族值及总值、蛋组、身高/体重原文及排序值、骑乘、介绍、头像、进化摘要及来源。 |
| `spirit_elements` | 独立精灵的单系/双系与顺序，不把双系塞进单个外键。 |
| `spirit_portraits` | 独立精灵与立绘的一对多关系，保留展示顺序。 |
| `ability_catalog` | 从精灵列表归纳特性名称、效果、图标与来源。相同名称效果冲突时标记 `description_conflict=1`，不以最后一条覆盖前面的记录。 |
| `game_rules` | 游戏描述名称、类别、系别、描述、规则图标、系别图标与来源。规则允许没有图标。 |
| `evolution_links` | 每次基本类型进化一条有向边，使用两端基本名称作为联合唯一约束，保留编号、阶段、条件、链文本、推断方法。无外观端点键或嵌套 JSON key。 |
| `spirit_skills` | 独立精灵与技能的关系及来源 `default-skill/blood-skill/stone-skill`，保留完整精灵名称、详情来源及允许缺失的外键；不对技能关系去掉括号后缀。 |
| `elements` | 系别字典，供技能、精灵和规则引用。 |
| `assets` | 本地相对路径、来源 URL、SHA-256 与缓存状态，路径唯一；图标/立绘文件本身仍放在资源目录。 |

仅保留 11 张业务表；另有视图 `spirit_evolution_neighbors`，列出基本名称的上一阶/下一阶。同步批次和完整快照不建数据库表，改存 JSON 日志。

## 精灵身份与进化

- 精灵明细表沿用 `spirit_forms` 名称，但每个完整名称是独立精灵，`name` 唯一；不再保存 `record_key/form_code/position_tags`，也不保存 `main/regional` 标记。
- 如 `板板壳` 和 `板板壳（蜕皮时的样子）` 各有自己的种族值、系别、技能、特性及资源；不会归并明细数据。同编号、同 Wiki ID 仍允许对应多个独立名称。
- `has_shiny` 仅表示异色可用性。Wiki ID、编号或异色状态修正不改变既有整数主键；改名视为新条目，并在增量报告中交给用户决定旧条目是否移除。
- 只有构建或查询进化链时归一基本名称：从第一个中文 `（` 或英文 `(` 起去掉后缀。例如两种板板壳都查询 `板板壳 -> 咔咔壳`。此关系不表示外观之间可以转换。
- 按数值编号相邻、阶段递增，生成 `1 -> 2` 或 `1 -> 2 -> 3` 进化链；首领不参与，单独一阶不生成链。外观先归一、去重，不再生成外观之间的笛卡尔积连线。
- 同一编号同一阶段如果归一后仍有多个不同基本名称，打印警告并跳过该链，不猜哪一个能够进化。
- `evolution_links` 保存 `from_name/to_name` 的联合唯一关系，不引用某个外观的记录 ID。删除某条精灵明细不会凭空改变基本类型之间的进化规则；进化表通过本次同步的进化快照和移除策略更新。
- 推断方法保存为 `inference_method=adjacent_number_stage`；这不是详情页证实的进化条件，不猜进化等级，没有等级就存 NULL。
- 精灵中的 `previous_stage_text/next_stage_text` 和 CSV 的“上一阶/下一阶”也是基本名称，不附加外观标记。
- 技能关联仍按完整名称精确匹配，不做进化名称归一。端点未采集时保留名称、将外键置 NULL 并输出日志警告，之后更新目录会重新关联；删除技能或精灵时相应技能关联外键置 NULL。

## JSON 同步日志

- 默认日志目录为 `data/nrc_wiki_sync_logs/`；自定义数据库路径时使用同目录的 `<数据库文件名去扩展名>_sync_logs/`。
- 每次成功提交后生成独立 JSON 文件，包含 `schema_version`、`committed_at`、各类 `counts` 和完整 `records`。文件名使用 UTC 时间和随机标识，未知新增字段也保留。
- 业务表不保存同步时间或批次外键；时间和数量只写入 JSON。未确认写入、仅 staging 或事务失败都不生成新的已提交日志。
- canonical CSV 不存在时，增量基线读取最近包含该类型的已提交 JSON 日志；明确的空快照不会回退到更早的非空数据。

## 完整性与增量写入

- 数值未知保存 NULL，不再把缺失威力、能耗或种族值变成 0；真实的 0 仍保留。身高和体重展示范围不再被排序用的最小值替换。
- 特性统一目录之外，每条独立精灵仍保存其原始特性效果。效果冲突时，统一目录描述留空并记录警告，各独立精灵与 JSON 完整快照不会丢失证据。
- 同一批已确认的数据在一个 SQLite 事务中更新：目录、标签、资源引用、进化和技能关系一起提交；失败则全部回滚。
- 只更新本次选中的类型；单独更新技能不会清空精灵或规则。未启用技能关系采集且没有人工关系补充时，已有技能关系不被替换。
- 爬虫先按移除策略合并新旧记录，再把合并结果传给 `apply_database`。写入器将传入的类型视为该类型的完整快照，不应绕过合并层传入任意子集。
- 表内使用外键和必要的非负/布尔约束；每次提交前运行 `PRAGMA foreign_key_check`。手动编辑数据库时也应开启 `PRAGMA foreign_keys=ON`。
- `PRAGMA user_version` 保存结构版本；只接受 v2 或新建空库，其他结构拒绝写入，不再执行迁移。
- 数据库成功提交后保存 JSON 同步日志，再输出 `data/wiki/` 的 canonical CSV/JSON。文件与数据库不构成跨介质原子事务；日志保存失败会明确报告“数据库已提交”，不会误报已回滚。canonical 导出失败时，已保存的同步日志仍保留完整数据。
- CSV 用于人工审阅/导出，SQLite 是结构化关系存储，JSON 用于保留全部来源字段。旧 CSV 已丢失的字段不会凭空恢复，需重新采集补全。

## SQLite 查询示例

查看基本类型的进化邻居：

```sql
SELECT spirit_name, direction, neighbor_name
FROM spirit_evolution_neighbors
WHERE spirit_name = '板板壳'
ORDER BY direction, neighbor_name;
```

Python 查询自动去掉区域变种的括号后缀：

```python
from pathlib import Path
from scripts.wiki_crawler.database import read_evolution_neighbors

neighbors = read_evolution_neighbors(Path("data/nrc_wiki.db"), "板板壳（蜕皮时的样子）")
print(neighbors)
```

查看待核对的技能关系：

```sql
SELECT spirit_name, skill_name, skill_source, source_url
FROM spirit_skills
WHERE spirit_id IS NULL OR skill_id IS NULL;
```

查看技能目录和图标：

```sql
SELECT skill.name, element.name AS element, skill.category,
       skill.energy_cost, skill.power, skill.description, asset.path AS icon
FROM skill_catalog AS skill
LEFT JOIN elements AS element ON element.id = skill.element_id
LEFT JOIN assets AS asset ON asset.id = skill.icon_asset_id;
```
