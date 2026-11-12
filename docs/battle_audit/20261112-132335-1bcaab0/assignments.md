# 文件独占与执行约定

基线为当前工作区，包含审计开始时已有的修改。目录在预检时按初始 HEAD `1bcaab0348aa52e328e3b48523b080b964a5ff2d` 命名；正式枚举记录的 HEAD 已为 `a393307d302bb97482b68ddf1516e84a21314127`，见 [baseline.json](baseline.json)。期间用户提交了已有改动，审计没有提交或改写业务文件。文件内容以 SHA-256 为准，不能把目录短码误认为最终冻结的提交。
初始 119 个文件及后补 30 个来源 JSON 的唯一主责、最终哈希核对见 [baseline_files_final.csv](baseline_files_final.csv)，全部检查单位见 [inventory.csv](inventory.csv)，原始枚举保留于 [inventory_baseline.csv](inventory_baseline.csv)。

| 任务 | 唯一主责范围 | 检查重点 |
|---|---|---|
| T00 | `data/**/*.md`、现有测试、1002/1007资料、依赖清单、迁移脚本、主台账 | 规则拆解、独立预期、跨模块接口、合并去重和基线复核 |
| T01 | `wiki_crawler/**`、战斗CSV/SQLite/XLSX | 转换覆盖、名称关系、重复失联、形态技能血脉进化与源冲突 |
| T02 | `nrc_platform/{catalog,builder,input}.py` | 规范化、默认补全、实例隔离、全知边界、首领与退化链、拒绝 |
| T03 | `nrc_core/{models,compound_status,catalog,constant,pokemon_nature_table}.py` | 数值精度、属性矩阵、归属上限、生命周期和复制 |
| T04 | `nrc_core/{battle,core,rng}.py` | 伤害、排序、应对迸发能耗、多段换人、回合末终局和随机 |
| T05 | `nrc_core/{runtime,rules_support,actions,codec,contracts,schema,unknown,devotion,debug,__init__}.py` | 阶段、合法动作、共鸣补位、只读观测预览、快照和复现 |
| T06 | `nrc_core/{effect_data,skill_effects_generated}.py`、`scripts/generate_skill_effects.py` | 全技能特性原文子句、参数条件目标时点、生成与手写覆盖 |
| T07 | `nrc_core/{effect_models,effect_engine}.py`、其余`engine/*.py` | 原语注册过滤分发、嵌套、执行路径和公共事件 |
| T08 | `nrc_core/engine/handlers_skill.py` | 伤害回复偷取状态增减益减伤打断条件与逐段 |
| T09 | `nrc_core/engine/handlers_ability.py` | 特性全部分支、触发次数临时修改、技能变换和时间 |
| T10 | `nrc_core/engine/handlers_field.py` | 奉献折射契约传动血脉萌化、免疫随机池归属持续 |
| T11 | `nrc_platform/{platform,rooms,state,__init__}.py`及本层说明文件 | 双人事务幂等过期回滚、历史快照、出场与遮蔽 |
| T12 | `nrc_server/**` | HTTP身份席位所有接口、双context Chrome页面与刷新恢复 |

每个任务只写 `tasks/Txx/`。跨文件发现以主责任务 + 协同任务 + 接口两端位置记录，不转移文件归属。
源文件、业务生成物、原数据库及已有审计不改写。数据库连接使用 `mode=ro`。
并行最多三个子agent，采用本轮用户指定的 GPT-6.1-Sol / High Effort（覆盖 AGENTS.md 的 Low 建议）。
优先 T04/T06/T07，随后在空闲槽位调度其余任务；每个任务保存中间证据。

## 台账与结论

`assigned_inventory.csv` 为基线文件、AST对象/控制流分支和原文子句的原始清单；条件中的语义子分支、配置树节点、前端分支由所属任务补充 `inventory_extra.csv`。
AST分支只表示语法分支，不等同于所有机制组合已穷举。数据描述按句号拆分只是初始单位，同句并列效果仍要单独记录。

各任务的 `coverage.csv` 字段：`item_id,conclusion,rule_basis,implementation,objects,method,evidence,notes,reachability`。
结论严格使用：通过、确认缺陷、未实现、规则存疑、检查受阻、未上线。
可达性单列，不将不可达等价为通过。复用证据必须说明所覆盖的参数、对象和独立分支。
源表一致、配置非空、handler存在、旧测试通过、迁移一致均不能单独证明语义正确。

问题需包含编号、严重度、主责/协同、规则位置、代码位置、最小复现、独立预期、实际状态/事件、影响范围和证据链接。
存疑需包含具体问题、既有依据与冲突、待补充内容、影响对象、当前行为、确认后的验证方式。

## 重点跨模块关系

| 接口 | 主责与协同 |
|---|---|
| 目录→技能实例→动态能耗/合法动作/显示/支付 | T02 + T04/T05/T06/T08/T12 |
| 配置→过滤/时点→特性触发→事件 | T06 + T07/T09/T04/T11 |
| 退化链注入→萌化数值→上限/技能状态→快照展示 | T02 + T10/T03/T05/T11/T12 |
| 精灵/技能槽/阵营归属→离场→恢复→遮蔽 | T03 + T04/T08/T09/T10/T11 |
| 中途暂停→单方补位→继续→事务与刷新 | T04 + T05/T11/T12 |
| 随机池/时间→显式输入/种子→导出恢复 | T10/T09 + T04/T05/T11 |
| 50回合/同时终局/全平 | T04 + T05/T00；依据不足不替用户裁决 |

首批存疑固定纳入：50回合四指标全平、秋收草系环境、资质倍数与示例冲突、奉献均匀分布暂定。
