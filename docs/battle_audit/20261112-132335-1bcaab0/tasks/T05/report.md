# T05 运行接口、动作、共鸣与协议审计

完整静态读取runtime/rules_support/actions/codec/contracts/schema/unknown/devotion/debug/__init__.py及nrc_core/README.md，原始assigned清单508行、唯一ID504个；同一IfExp生成ID碰撞合并到一行，notes保留原条数/条件，待T00拆稳定后缀。额外20项实际语义验证列入inventory_extra和coverage。coverage每个唯一ID恰一行。分类计数：{"通过": 199, "确认缺陷": 188, "规则存疑": 135, "未实现": 2}。碰撞清单见id_collisions.json。

实际运行probe.py退出0。用CSV原文+现有效果表构建完整内存目录，不使用产品loader写数据库。验证真实技能补觉两分支、隐藏条款技能交换、流沙禁足，正式盲拧/契约的形状随机配置，首领resolved record，愿力合法动作/次数/冷却/还原与光合后台/死亡时长，替补入场荆刺与对方入场冻结连锁力竭。只读、快照与clone使用pickle字节前后、对象身份、天气新技能id直接比较，不泛化T03错误复制接口。

10个问题分别有实际输入输出；其中8项确认缺陷，2项规则机制未实现。初始化当前不触发初始ON_ENTER，正式抓到你了没有入场效果；入场引起双方力竭有replacement但无MP扣除；种子实际覆盖技能结算内部，new_game/replacement/下一回合准备未受seed隔离。首领化六维受T03 Float32缺陷影响，本任务独立确认types没有更新，不重复数值根因。

真实通过证据：P01光合HP轨迹500/650/800/800（立即+三次，每次150；切到后台继续），P06死亡不被治疗且倒数递减；首次无carried自动锁定solar、之后禁其他和再用。P05愿力首次uses1/CD2，等待两回合CD0，第二次uses2且无第三次，普通未换技能场景正确还原。P02预览状态字节与环境随机不变、整体clone与快照图引用/天气id正确。P03未知/不存在/False/choice结构转换；P04动作键重复和空拒绝。通过仅限明确的结构映射或实测路径，不宣称所有共鸣/非法输入/隐藏信息都完整正确。

重点边界：普通脱离需即时真实选择的问题沿用T04-I11，不重复统计；自力竭后后手是否继续沿用T04-Q00待裁决。愿力交换还原用真实隐藏条款，未假设传动已移动；传动移动缺失由T07主责。双人同时共鸣/补位速度顺序、蓄力是否禁止手动换人、首领血脉远古变化、缺catalog未实现错误类别等具体未明处见questions，不据可达性或函数存在刷通过。快照明确可信本地使用，不提出泛pickle安全问题。

全部输出限tasks/T05，未改业务或数据。复现命令：设置PYTHONIOENCODING=utf-8、PYTHONUTF8=1后运行python -m docs.battle_audit.20261112-132335-1bcaab0.tasks.T05.probe及build_audit。
