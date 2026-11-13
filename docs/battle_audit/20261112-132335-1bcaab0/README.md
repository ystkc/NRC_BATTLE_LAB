# 全战斗规则审计

后续完整修复规划已基于 `911babc` 整理，覆盖AUD-001–108和QUE-001–064：见 [完整计划](repair_plan_full.md)、[172项台账](repair_ledger.csv)、[门禁清单](repair_gates.md)、[规划校验](repair_plan_validation.json)。本轮仅编制规划，业务修复和规则验收尚未执行。以下正文保留原审计时点的基线、结论与验证范围；原始审计证据不因后续裁决自动变为通过。

本轮只检查、保存证据和列出问题。业务代码、规则、现有测试、生成产品和原数据库均未修改；没有代用户裁决含糊规则。确认问题共 **108 组**（P1 91、P2 16、P3 1），去重后的存疑/受阻/待证议题 **64 组**。明细分别见 [issues.md](issues.md)、[questions.md](questions.md)。

审计建账、12模块静态审阅、必要反例和交付核验已完成。**完整行为正确性尚未证明**：每个检查单位有结论不代表每条路径都执行过，未验证的条件和组合保留明确待证项。通过只适用于行内范围，没有证据不计通过。

## 基线与范围

- 目录创建时 HEAD 为 `1bcaab0348aa52e328e3b48523b080b964a5ff2d`。用户在预检阶段提交已有改动后，正式枚举于 `2026-11-12T13:25:22.455537` 冻结 HEAD **`a393307d302bb97482b68ddf1516e84a21314127`**。目录保留原短码；不是基于旧提交回退审计。见 [baseline.json](baseline.json)、[assignments.md](assignments.md)。
- 初始119个源/规则/资料文件，后补30个JSON，共 **149 个唯一主责文件**。末次 SHA-256 **149/149 相同**，无需因审计期间内容变化重跑。含625形态、580技能、242特性、18属性、57规则记录及所有纳入的规则文档。详见 [baseline_files_final.csv](baseline_files_final.csv)。
- 原库 `data/nrc_wiki.db`：SHA-256 `f133f6a9b4f24f348cf1cbe0994e0c444b0eba62a1ad7378d37009a21ad13cd6`；SQLite `user_version=3`、`schema_version=60`、`quick_check=ok`、外键检查为空。规范/staging数据版本与9类提交记录见 [T01证据](tasks/T01/probe_output.json)。数据库仅以 `mode=ro` 打开；写入型边界在内存数据库验证。
- 纳入规则核心、效果生成链、战斗相关数据和采集转换、多回合平台、双人房间、HTTP/网页、现有测试和人工1002/1007。排除AI训练、废弃OCR及旧入口、旧审计结论；历史脚本与手记只作线索。
- 保留用户原有未跟踪 `tests/playwright_ui_changes.js`、`tests/test_compound_status.py`。最终 git 状态仅本审计目录及这两个原文件，无业务差异；见 [validation.json](validation.json)。

## 覆盖统计与读法

[inventory.csv](inventory.csv) 和 [coverage.csv](coverage.csv) 一一对应 **22,487** 个唯一ID，结论记录率100%，缺失0、文件归属冲突0。[id_aliases.csv](id_aliases.csv) 为原枚举同行三元分支的46个ID消歧保留列位置；[branch_inventory_addendum.csv](branch_inventory_addendum.csv) 另补2456个Python短路/推导式路径，全部作为实现待证实列入，没有借父函数通过推为分支通过。

| 结论 | 检查单位数 |
|---|---:|
| 通过 | 9,132 |
| 确认缺陷 | 1,330 |
| 未实现 | 373 |
| 规则存疑 | 11,499 |
| 检查受阻 | 149 |
| 未上线 | 4 |

“通过”占记录的 **40.61%**，这是混合检查单位的有限证据比例，**不是战斗正确率**。其中6156项是属性矩阵；625形态通过只证明数据/关联一致；1208项语义样本、222枚举等各有限定范围。确认缺陷的行数也不是缺陷数，同根反例按108组去重。373条未实现记录包含对象、子句、分支，不等于373种机制；4条未上线记录只对应2个明确未上线共鸣。149条受阻主要为采集外部故障分支及人工初始数据缺失，具体原因与后续步骤在行内和questions中。

| 独立统计口径 | 结果 |
|---|---|
| 技能580对象总体 | 290确认至少一处差异；290规则存疑；完整通过0 |
| 特性242对象总体 | 74确认至少一处差异；98规则存疑；70未实现；完整通过0 |
| 配置局部检查 | 原149项局部通过保留，协同后另3项局部通过；不覆盖共享时序/边界。配置、执行、总体结论分列 |
| 57条规则记录总体 | 3通过、27确认缺陷、3未实现、24规则存疑 |
| Python显式控制方向 | 5076项：472有限通过、518关联确认缺陷、3946待证、140受阻 |
| Python短路/推导式路径 | 2456项，逐条件列所需输入和实现位置；未单独验证，全部待证 |
| JavaScript控制方向 | 1310项已枚举/审阅；未逐方向取得独立输入，全部待证 |
| 数据记录逐项检查 | 另表78,224行，包括关系/分布/进化/资源；不叠加主表分母 |

逐名技能、特性终表：[final_object_review.csv](tasks/T06/final_object_review.csv)。T06原始冻结检查点仍保留，最终应读取 [final_addendum_report.md](tasks/T06/final_addendum_report.md)、[coverage_addendum.csv](tasks/T06/coverage_addendum.csv)，旧“317待handler”已经收口为82确认、235待证，未继续作为等待协同阻塞。独立子句不继承对象整体错误；新增321个精确特性子句分别结论。来源/实现/对象/方法/证据/可达性在主表，具体下一输入在对象终表及分支补表；[statistics.json](statistics.json) 提供机器可读统计。

## 已执行的验证

- 现有pytest **19/19通过**，耗时8.37秒。重新查看预期来源，只当回归证据，不以测试结果证明规则。见 [pytest.log](tasks/T00/pytest.log)、[pytest.xml](tasks/T00/pytest.xml)。
- 单/双系克制6156项全部符合独立文档矩阵；六维625×30×6的112500标量以IV0隔离倍数歧义，独立Float32计算发现12325不符。见 [T03](tasks/T03/report.md)。
- 1007双提交顺序各回放11回合，68项查询只读/幂等/过期检查，固定seed事件相同；独立有理数核算11个显式面板伤害样本全匹配。人工手记124与独立推导123等差异保留存疑，不拿旧结果做权威。1002及1007最终补位缺输入，不宣称完整重放。见 [T00](tasks/T00/report.md)。
- 50回合MP/存活/HP/能量四种明确胜者均未终结；多重减伤和最低伤害另有独立有理数反例。同速/入场/补位/全局RNG，复制、状态、特殊系统和完整执行链的反例分别保存在各任务输入/输出，未把synthetic原语输入说成当前配置必达。
- CSV/DB逐字段及顺序一致，9类JSON/staging/提交快照一致，全部3364资源存在且已存哈希匹配；262进化边、44缺失名称对应2564条关系、旧XLSX版本冲突另列问项。见 [T01](tasks/T01/report.md)、[data_record_checks.csv](tasks/T01/data_record_checks.csv)。
- 前端用已安装Node Playwright，显式 `channel: 'chrome'`，Chrome153，一个新浏览器中的两个独立context；17个HTTP方法成功路径、身份/席位、pending刷新、重复/过期、补位、战报游标、对手弹窗与窄屏均有实际证据。11张截图已查看；并发/异常回滚和pending快照往返见T11。端口8774及浏览器已关闭，无连接用户既有浏览器。见 [T12报告](tasks/T12/report.md)、[截图与关闭证据](tasks/T12/cleanup.json)。

要求的场景逐项映射见 [scenario_matrix.csv](scenario_matrix.csv)（48项），每行分开“实证范围”和“剩余验证”。静态读取、单次中性探针、成功路由覆盖均不等于所有组合已穷举。

## 主要确认问题

- [T11-I01 平台自动抹去未实现特性，绕过核心构建拒绝](issues.md#aud-001)。
- [T06-I01 生成回退重复包装SkillEffect，8技能在执行时崩溃](issues.md#aud-002)。
- [T02-I08 奉献减耗别名错字使随机初始化崩溃](issues.md#aud-003)。
- [T05-I04 替补入场与连锁入场力竭不扣MP](issues.md#aud-004)。
- [T04-I03 50回合强制裁决未实现](issues.md#aud-005)。
- [T03-I01 Float16替代权威Float32导致六维错误](issues.md#aud-006)。
- [T10-I11 化茧未免疫致命伤害、主动降为1生命且缺2次上限](issues.md#aud-007)。
- [T09-I02 旧模型字段与不存在模块使属性倍率原语失效](issues.md#aud-008)。
- [T05-I05 初始化、补位和下一回合准备在种子随机域之外](issues.md#aud-009)。

另有伤害减伤/吸血顺序、状态上限和归属、生成参数/目标/时点丢失、普通脱离、传动/选择/禁足静默缺口、后台事件泄名、双方MP不显示等。按根因和严重度的全部最小输入、预期/实际、影响范围及证据见 [issues.md](issues.md)、[issue_index.csv](issue_index.csv)；跨模块重复合并见 [issue_aliases.csv](issue_aliases.csv)。

70空特性在direct builder正确抛 `UnsupportedMechanicError`，但平台抹特性名后错误放行，两种事实并列。空技能、未知原语/动作、未实现血脉/传动/禁足/选择的静默行为单独记录。内部AttributeError不是正确的Unsupported拒绝；不可达也不代表未上线。

## 存疑、受阻与局限

首批要求的50回合四指标全平/同时终局、秋收草系环境、资质6倍与+8→40冲突、奉献均匀权重暂定均保留。其他如普通离场与自力竭含义、临时技能归属、萌化恢复HP、准备期阵容可见性、契约重抽等均有已有依据、当前行为和确认后验证方式。仅明确写未上线的闪焰爆发、节流术标“未上线”。

需要用户裁决的是规则冲突/缺失；已经有明确原文的实现待证实不转嫁给用户批准。大量静态条件、时间/周末、分段中途切换、共享状态与EOT连锁尚无逐分支独立运行证据，不能给整体通过；按具体条件和对象列下一输入。网络采集没有执行，生产库未写；新环境依赖安装没有实做，缺numpy用隔离导入探针确认。运行环境版本见 [dependency_output.json](tasks/T00/dependency_output.json)，当前FastAPI/uvicorn低于项目声明下限，本轮HTTP结论只针对当前环境。

首次CSV中文终端输出乱码已即时报告，设置显式UTF-8后重读正常，原始文件无损；另有审计脚本输入/路径/等待条件修正，失败尝试保留且不计产品缺陷。见baseline及各任务报告。审计副本生成比较没有覆盖技能生成物。

## 文件入口与复核

| 任务 | 交付入口 |
|---|---|
| T00 | [报告](tasks/T00/report.md) · [逐项表](tasks/T00/coverage.csv) · [问题](tasks/T00/issues.md) · [存疑](tasks/T00/questions.md) |
| T01 | [报告](tasks/T01/report.md) · [逐项表](tasks/T01/coverage.csv) · [问题](tasks/T01/issues.md) · [存疑](tasks/T01/questions.md) |
| T02 | [报告](tasks/T02/report.md) · [逐项表](tasks/T02/coverage.csv) · [问题](tasks/T02/issues.md) · [存疑](tasks/T02/questions.md) |
| T03 | [报告](tasks/T03/report.md) · [逐项表](tasks/T03/coverage.csv) · [问题](tasks/T03/issues.md) · [存疑](tasks/T03/questions.md) |
| T04 | [报告](tasks/T04/report.md) · [逐项表](tasks/T04/coverage.csv) · [问题](tasks/T04/issues.md) · [存疑](tasks/T04/questions.md) |
| T05 | [报告](tasks/T05/report.md) · [逐项表](tasks/T05/coverage.csv) · [问题](tasks/T05/issues.md) · [存疑](tasks/T05/questions.md) |
| T06 | [报告](tasks/T06/report.md) · [逐项表](tasks/T06/coverage.csv) · [问题](tasks/T06/issues.md) · [存疑](tasks/T06/questions.md) |
| T07 | [报告](tasks/T07/report.md) · [逐项表](tasks/T07/coverage.csv) · [问题](tasks/T07/issues.md) · [存疑](tasks/T07/questions.md) |
| T08 | [报告](tasks/T08/report.md) · [逐项表](tasks/T08/coverage.csv) · [问题](tasks/T08/issues.md) · [存疑](tasks/T08/questions.md) |
| T09 | [报告](tasks/T09/report.md) · [逐项表](tasks/T09/coverage.csv) · [问题](tasks/T09/issues.md) · [存疑](tasks/T09/questions.md) |
| T10 | [报告](tasks/T10/report.md) · [逐项表](tasks/T10/coverage.csv) · [问题](tasks/T10/issues.md) · [存疑](tasks/T10/questions.md) |
| T11 | [报告](tasks/T11/report.md) · [逐项表](tasks/T11/coverage.csv) · [问题](tasks/T11/issues.md) · [存疑](tasks/T11/questions.md) |
| T12 | [报告](tasks/T12/report.md) · [逐项表](tasks/T12/coverage.csv) · [问题](tasks/T12/issues.md) · [存疑](tasks/T12/questions.md) |

[assignments.md](assignments.md) 为唯一文件归属；[inventory.csv](inventory.csv) 为对象/子句/实现方向；[coverage.csv](coverage.csv) 为双向关联和证据结论；[scenario_matrix.csv](scenario_matrix.csv) 为必查场景；[validation.json](validation.json) 与 [deliverable_validation.json](deliverable_validation.json) 为最终完整性和哈希核验。

复核命令只写本次审计目录。不要重新执行build_inventory.py覆盖原始基线；如业务内容有变化，应新建审计或明确重核变更项。

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
python docs/battle_audit/20261112-132335-1bcaab0/consolidate.py
python docs/battle_audit/20261112-132335-1bcaab0/build_questions.py
python docs/battle_audit/20261112-132335-1bcaab0/finalize_summary.py
python docs/battle_audit/20261112-132335-1bcaab0/verify_deliverables.py
```
