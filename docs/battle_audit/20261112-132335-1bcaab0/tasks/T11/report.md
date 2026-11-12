# T11 平台、房间与双视角记录

已完整静态阅读platform.py、rooms.py、state.py、__init__.py及本层两份说明；文件归属不变。依赖端仅沿runtime观测/状态变更、builder拒绝、handler后台萌化和前端调用核对。未修改业务、数据库、现有测试或原对局资料。

四项确认缺陷见 [issues.md](issues.md)：未实现特性被平台抹掉绕过拒绝、未出场替补经后台状态战报泄名、缺少对方奉献总层数、组合状态未纳入predict_damage。记录均保留预期、实际和输入；不是以现有测试预期证明规则。

实测：两个稳定身份准备与确认；普通双方收齐一次推进；同时线程提交只产生一个核心history且decision_index=1；外层事件生成异常时核心/暂存/历史/请求缓存/房间全部恢复；同request重试不改状态；两方独立event cursor空尾；终局actions=[]且新提交battle_terminated；含单方pending的平台快照在新实例恢复后补齐另一提交结果及双视角观测一致。pickle重新导出的字节不相等，记录这一差异，但语义结果相等，不判缺陷。不存在公开HTTP导入上传路线。

1007双提交顺序复演11回合，68项查询只读/幂等/过期检查及固定seed事件相等，证据在T00；这是特定路径契约通过，不能推出所有机制组合正确。T07水环全技能公开修正来源缺失保留其根因编号，T11不重复计数；T04减伤取整导致本地predict同错也只协同登记。

静态审阅重点：房间成员与席位由identity映射；set_rosters拒绝side/teams覆写，只确认后提交；嵌套RLock允许平台和房间共用事务；请求ID按side隔离且旧decision_index拒绝；revealed由实际entry_count登记，查询不更新；对手负载不含skills/stats/ability_state，未上场本体替换未知；双方印记按视角互换；技能专属状态与全技能公共修正由来源拆分。事件侧未做未出场身份过滤的反例独立列缺陷。

分配清单每个ID均有coverage记录。语法分支已阅读但多数未逐方向取得独立参数/机制证据，记录具体函数和条件及后续所需输入，保守为规则存疑（实现待证实）；不把“有代码”当通过。新增5项接口边界作为独立inventory_extra。完整主规则至实现映射由T00统一台账，不将平台说明作为战斗规则权威。

命令与证据：[probe.py](probe.py)、[probe.log](probe.log)、[probe_output.json](probe_output.json)。Python显式UTF-8，原生补丁中文读写正常。首次全局CSV终端乱码已由T00记录并重读。运行后所有来源文件仍按主基线哈希复核。
