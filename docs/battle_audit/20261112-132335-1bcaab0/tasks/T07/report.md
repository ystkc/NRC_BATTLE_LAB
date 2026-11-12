# T07 效果协议、分发及执行路径审计

已检查分配的9个文件：effect_models.py、effect_engine.py及engine下context、dispatch、executor、filters、helpers、registry、__init__。未修改业务；只写tasks/T07。未读写数据库。中文读取及原生补丁写入正常，没有乱码或编码异常。

分配清单671行（9 FILE、54 CODE、608 BRANCH）均在coverage.csv有逐项记录。基线在executor.py:510的true/false各发生一次ID碰撞，共669个唯一ID；coverage合并碰撞行的notes，保留两条条件说明，没有静默丢失。额外补充200个E、16个Timing、6个SkillTiming成员，共222项，见inventory_extra.csv；coverage总891个唯一ID。补GAME_RULE8分类后统计338通过、542规则存疑、10确认缺陷、1未实现。原23条“未上线”已改为“规则存疑（实现待证实）”，可达性单列，没有文档明确声明尚未上线，不能用缺配置/未引用掩盖规则缺口。此统计按唯一清单项计数，问题数见issues.md，不将多行共享同一问题重复计算。

“通过”有明确范围，主要是兼容导入、数值原语、注册/枚举协议和事件信息流；不等于199个handler全部规则正确。全部分支完成源码定位与控制流阅读；未声称608个真假分支逐一动态执行。函数级复现不自动证明内部每个分支，故有问题函数关联的多数分支保守标为规则存疑。542项疑义包含具体边界不明、需外组处理器语义或完整对局才能定论的范围，不是542个确证缺陷，也不因缺专名md否认已授权原文。static_review.md逐函数说明实际检查范围，coverage的notes包含每个分支条件。

注册表AST双向核对：E共200项，默认注册199项、特性覆盖134项，两个字典均无重复键；唯一未默认注册INTERRUPT由新旧应对入口特判。所有Timing均找到核心调用或引用；不将仅有引用认定外层时点顺序正确。SkillTiming六阶段均有执行或收集入口。

issues.md记录10项：I01未知效果静默忽略，I02迅捷攻击不扣血，I03动态迅捷未识别，I04水环公开修正来源丢失，I05传动移位未实现，I06旧格式迅捷多次释放，I07极限撕裂POST_USE条件失效，I08嵌套SkillEffect崩溃，I09清除减益漏异常与技能负修正，I10王子把萌化当增益。I06只证明兼容入口；I08其余7项结构枚举不冒充运行。新增cleanse_probe.py已运行真实洗礼/除厄全部effects：六种明确异常均未清、属性减益被清，印记和特性控制保留；真实退化使王子技能成本2→1，而规则应+1至3。输出cleanse_probe_output.json。

questions.md保留6类具体边界：阶段过滤/HP取值时点、永久威力叠加公式、王子对技能绑定修正及复合状态消费、copy嵌套隔离、系统发育分配单位、应对重算临时修正。技能/特性原文已获用户授权用于子句核对，不再请求来源授权；data根md、详解、通用规则冲突仍优先。萌化属于减益已经明确，不留作分类疑问。

验证：probe.py运行成功（退出码0），probe_output.json保留确定输入对应实际结果；config_filters.json枚举当前生成+手写覆盖的全部非空SE.filter。现有POST_USE条件只有极限撕裂，ON_COUNTER113项、IF6项、ON_HIT4项；未用旧测试作规则证明。该脚本只构造核心对象，不覆盖平台目录、数据库读取、完整50回合或前端可见性。与回合组协同确认传动时点和迅捷结果处理；与状态组协同确认I04最终显示；与生成组协同I07/I08根因。

复跑：`python docs/battle_audit/20261112-132335-1bcaab0/tasks/T07/probe.py`；逐项表重建：`python docs/battle_audit/20261112-132335-1bcaab0/tasks/T07/build_coverage.py`。Windows环境需PYTHONIOENCODING=utf-8/PYTHONUTF8=1。
