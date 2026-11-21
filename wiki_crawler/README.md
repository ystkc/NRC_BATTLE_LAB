# NRC Wiki 爬虫

从wiki.biligame.com更新项目所需的精灵立绘、头像、技能图标、特性图标、其他图标等资源及其对应的描述。其中talent、skill、blood、nature四项精灵绑定数据不再允许批量更新，改为运行时增量更新。

## 目录与入口

```text
wiki_crawler/
├── __init__.py
├── __main__.py     模块启动入口
├── sync.py         BeautifulSoup 解析、网络请求、资源缓存、增量确认
├── database.py     v4 SQLite 业务表写入、JSON 同步日志、进化查询
├── distribution_cache.py  培养分布内存缓存与 SQLite 回填
├── usage.py        单只精灵的 Wiki 培养查询
├── manual_data.yaml 固定的人工补充文件（含注释示例）
└── README.md       使用说明与数据库结构
```

全库抓取方法；

首先安装环境：
```
pip install -e ".[wiki]"
```
然后：
```powershell
python -m wiki_crawler --kind all --spirit-detail --verbose
```

四类培养分布（`skill`、`nature`、`blood`、`talent`）只保存在 `nrc_wiki.db`。
`DistributionCache` 初始化时把 SQLite 中的记录加载到内存。平台查询单只精灵时，缓存缺失才请求该精灵的 PVP 统计，将缺失类别和成功返回的空结果一起写入 SQLite。目录索引只读缓存，选中精灵时再按需查询。Wiki 暂不可用时，平台使用已缓存的统计和原有默认配置。


## 人工 YAML 补充

固定文件为 `wiki_crawler/manual_data.yaml`，默认每次运行都会读取。用于补充官方wiki中没有收录但有价值的结构化数据。

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

## 表结构（版本 4）

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
| `spirit_skills` | 独立精灵与技能的关系及学习方式 `level/blood/machine`，保存 `level/blood` 的学习等级、完整精灵名称、详情来源及允许缺失的外键；不对技能关系去掉括号后缀。 |
| `distribution_records` | 精灵培养分布缓存，保留已有记录并按需填充缺失类别。 |
| `distribution_cache_completed` | 已成功查询培养分布的精灵，记住接口明确返回的空分布。 |
| `elements` | 系别字典，供技能、精灵和规则引用。 |
| `assets` | 本地相对路径、来源 URL、SHA-256 与缓存状态，路径唯一；图标/立绘文件本身仍放在资源目录。 |
