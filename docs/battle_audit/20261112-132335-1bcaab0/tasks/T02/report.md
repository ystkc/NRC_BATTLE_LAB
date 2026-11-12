# T02 目录装载、输入与建造审计

已完成 nrc_platform/catalog.py、builder.py、input.py 全文件静态读取，346/346 assigned ID 均有且仅有一行coverage；额外1224个语义/逐对象条目，共1570条。源文件冻结HEAD以主baseline.json的a393307为准；目录旧短码不代表实际HEAD。只写本任务目录、未改业务。

本地独立主问题8项（P1四项：I01/I02/I05/I08；P2四项：I03/I04/I06/I07）。T06-I15蓄力、T10-I01奉献封顶、T03状态上限、T05首领types/初始化、T11空特性绕过均按主责归并，协同证据保留。

逐ID统计：assigned {'确认缺陷': 31, '规则存疑': 261, '通过': 54}；含extra {'确认缺陷': 41, '规则存疑': 267, '通过': 1262}。这些是代码/语义条目计数，不是独立缺陷数。规则存疑逐行写具体待证实点；没有因当前生产未引用而标未上线。

检查方法：沿原始数据→load_catalog→结构化codec→BattleBuilder.build→CoreCatalog实例→simulate_turn逐边界追踪；现行权威data/*.md优先，详解其次，再技能/特性原文；旧测试与历史对局不作正确oracle。所有实际目录连接由probe只读包装强制SQLite URI mode=ro；固定内存输入隔离特性/数值公式，正式build或RoomService预览运行。Python显式UTF8，中文补丁仅原生apply_patch。

实际验证：625形态学习表逐项一致；580技能type/category/power/cost/id/description与独立CSV映射无差异（愿力原始wiki_id空，明示采用DB数字id606）；49343分布记录按2376组，blood/nature/skill/talent各594组，未串合。skills使用直接学习关系，不用skill分布替代；nature/talent默认确实使用分布并见Q02。P02同名技能及首层effect不同实例，改甲技能威力/能耗后乙与目录均不变。空队、越界首发、无技能、未知form、携带愿力、缺项六维六种实际拒绝；未实现特性与未上线共鸣实际Unsupported。

重要实际反例：HP0→满血；六项正资质进入；neutral套非中性坦率；ID-only被拒且name-only重写ID；两个物攻增益条目只保留后项；英文属性静默普通；坏base三个类型使预览AttributeError；随机奉献seed2抽假寐KeyError。协同反例：升龙咆哮首回合直接扣180；奉献power5满层仍可随机得到第6层，输入指定9+随机5最终14。

覆盖边界：六字段转换通过不证明效果配置、charge/选择/迅捷/随机源完整；学习表转换通过不裁括号继承资格与44未知form来源。退化链推断来源、远古血脉、首领多映射、unknown默认和skill_pool完整性保留问题。不重复T03全量Float32公式；不把pickle可信本地快照提成公开安全问题。P2接口/诊断偏差与P1游戏状态缺陷明确区分。

复现命令（PowerShell）：设置PYTHONIOENCODING=utf-8、PYTHONUTF8=1、PYTHONPATH=.后运行python docs/battle_audit/20261112-132335-1bcaab0/tasks/T02/probe.py；然后运行同目录build_audit.py。probe_output.json记录原始最小输入和实际输出。首次运行发现模块路径/取方法名等脚本问题均已修正，最终probe退出0；没有因工具诊断误读中文文件。
