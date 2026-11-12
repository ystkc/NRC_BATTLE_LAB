# T01 确认问题

## T01-I01 · P1 · 采集目录迁移后入口导入及项目根路径失效

- 主责：T01；协同：T00（运行入口）。规则依据：AGENTS.md 指定 `python -m wiki_crawler`；本模块 README 的项目内 staging→确认→canonical/新库约定。
- 代码：`wiki_crawler/__main__.py:1` → `sync.py:33-45`；旧导入 `scripts.wiki_crawler.database`，`ROOT=parents[2]`。
- 最小输入与步骤：项目根执行 `python -m wiki_crawler --help`，无需网络或写权限；实际 exit 1、`ModuleNotFoundError`，预期能够展示参数。
- 第二端证据：只在审计内存模块替换失效 import 后，原 ROOT 算出 `D:/dotoro/project/python/rckdworld`，而项目为其下 `NRC_BATTLE_LAB`。默认 DB、CSV、staging 和资源路径均指向项目之外。没有实际执行下载或写入。
- 影响：全部采集模式当前入口不可运行；只修导入仍遗留错误数据目录。两处合并为同一目录迁移根因。
- 证据：[probe.py](probe.py)、[probe_output.json](probe_output.json) 的 `original_cli`、`configured_root`、[probe.log](probe.log)。

## T01-I02 · P2 · 分布表重写只做 upsert，不能移除旧项

- 主责：T01；协同：T02（目录消费 `distribution_records`）。依据：`sync.py:802-811,1056-1080` 的 `--remove-missing` 与 CSV/数据库同步约定；不是用旧实现推导战斗规则。
- 代码：`database.py:401-407` → `write_database:469-471`，缺少与其他类别相同的保留键清理；消费端 `nrc_platform/catalog.py:95`。
- 最小输入与步骤：在 `sqlite :memory:` 创建当前 schema，先写甲的“旧技能100%”，第二次仅写“新技能100%”。两次均调用实际 `_write_distributions`。
- 预期：按第二份完整、已合并快照只保留新技能；实际同时存在新、旧技能。空列表也不会清除旧项。四类分布均共用此函数。
- 影响：执行移除策略时 canonical CSV 已移除的分布仍可留在 SQLite，平台可能继续显示旧分布；当前快照字段核对一致，不声称历史已有此污染。
- 证据：[probe.py](probe.py)、[probe_output.json](probe_output.json) 的 `distribution_replace_probe`。源库只读，复现未创建持久数据库。
