# T00 主协调审计与跨模块证据

唯一主责为权威Markdown规则、现有测试/人工资料、依赖与迁移入口及总台账。各业务文件完整审阅由T01–T12原负责人承担；本任务只跨接口追踪和独立反例，不重新代审整文件。并行初始T04/T06/T07，最多三名GPT-6.1-Sol High子agent，任务换批后归属保持。

规则依据优先data根md、部分规则详解、game_descriptions；技能与特性各自原文用于具名效果。先按所有来源建立台账，再把规则→配置→原语/时点→实际调用→状态/数值→双视角串联。旧测试、旧审计及手记不作为正确性权威。57规则、权威md条款及例外与未上线项的逐行映射在本任务coverage，状态归属、伤害、速度/应对、特殊系统由对应任务协同；反向代码项没有充分依据的保留具体待证。

## 实际运行

1. 现有pytest：19通过/8.37秒，原测试均查看来源；有些期望来自被检查计算器，故只记兼容性。命令与结果在pytest.log/xml。
2. replay_1007.py：审计内新平台，完整1007A/B输入，固定seed，双方先后提交两序各11回合，68只读/幂等/过期检查，状态和事件对比一致。r8/r10真实替补；r11手记目标古拉多不在阵容，不能继续猜测。原始大JSON包含状态/双视角/事件，1007_replay.log为简表。
3. independent_damage.py：显式原始六维，Fraction独立推导STAB、属性、增益及公式，11例相符；没有调用被检查DamageCalculator或克制函数生成答案。这里不证明Float32初始化正确。r3爆裂飞弹独立为123，手记124仍待核，不从旧预期反推规则。
4. cross_module.py：50回合四种场景，每次高优先级平手，仅MP/存活/HP/能量一项决定A胜，均winner=None且turn51，合T04-I03。全平、双方MP0和全倒只存实际，不臆造期望。另用独立有理数证明三段/两类减伤及最低1伤害错误，合T04-I01；当前输入使用模型真实attack/pokemon_types字段，早期探针临时错误不作证据。
5. dependency_probe.py：不卸包，仅在隔离子进程令numpy不存在；平台导入真实失败。项目依赖声明缺numpy为T00-I01。记录当前已装版本，不联网安装或升级；没有把模拟缺包说成真实干净环境安装测试。
6. 收到全部任务后比对动态耗能、特性时点、状态生命周期、copy图、天气技能id、补位暂停/继续、平台事务和可见性。普通脱离随机、入场死亡不扣MP、平台抹空特性、未出场姓名事件泄露等证据按主责合并。自力竭后动作规则不明、同时败北和50全平则保持存疑。

## 台账与复核

consolidate.py按AST列拆原同行ID碰撞，保留original_id及id_aliases；人工1002观察归evidence_clause，不作权威rule_clause。T06旧冻结报告与原coverage不覆盖，最终增补4076行包含822对象总体/配置/执行结论和321精确协同子句。对象某一处错误不扩为所有子句都错。

extend_branch_inventory.py补2456短路/推导式路径，关联父函数已有依据与下一输入，全部待证；这种补枚举不能称已独立行为验证。前端1310分支亦保留待证。每个主表单位有结论，具体未验证范围清楚列出，不宣称机制或组合全部正确。最终统计、场景索引和验收结果以根目录README/statistics/validation为准。

主表问题根因合并T07嵌套SkillEffect→T06、T03冻结致死→T04、T10传动→T07；沙暴凭空伤害→T04，而重复折半独立T08-I02B；毒牙/毒腺已有配置缺陷合T06，虫群自身时点/目标仍由T09保留。issue_aliases和question_aliases保存所有去重关系。T04-I12是待裁决行为，不纳入确认问题数。

T00原子问题T00-I01见issues，其余跨模块发现只协同原根因。questions包含首批4条及人工资料不足；复杂实现待证按各行条件和原文映射，不要求用户批准常规验证。没有依据的结论不记通过。

## 资料、环境与修改边界

初始目录用1bcaab0命名，正式baseline HEAD为a393307。用户在预检阶段提交已有改动，全部149个源码/规则/数据来源最终哈希相同；原2个未跟踪测试保留。全部探针/记录只写本审计目录，库只读，生成产品不覆盖。Python显式UTF8，首次控制台CSV乱码重读已纠正并记录，未损坏文件；工具查询误用不存在文件名的报错只是路径错误，没有用于判定。

T12使用Node Playwright channel=chrome独立2context并已关闭，11张图由负责人查看；T00另查看正常共鸣与replacement全屏，确认MP缺失显示证据。没有computer-use。XLSX由T01按电子表格技能只读OpenXML核对，无artifact_tool时采用标准库，无保存/重算。

复现各本目录脚本时设置PYTHONIOENCODING=utf-8、PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1。跨模块运行证据：[cross_module_output.json](cross_module_output.json)、[independent_damage.json](independent_damage.json)、[1007_replay.log](1007_replay.log)、[dependency_output.json](dependency_output.json)。本轮没有修复业务，也没有留下服务器或浏览器会话。
