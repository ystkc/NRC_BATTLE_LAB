# 双人对战平台

依赖方向：`nrc_server → nrc_platform → nrc_core`。

一次操作由 RoomService 校验身份、管理准备和确认，再由 BattlePlatform 解析资料、提交动作，调用 BattleRuntime。核心成功返回后，平台提交状态与历史并登记实际已上场身份，最后生成玩家视角。

| 数据 | 唯一持有者 | 生效时机 |
|---|---|---|
| 血量、能量、回合、阶段、胜负 | _ManagedBattle.episode | 核心初始化或推进成功 |
| 待提交动作、重复请求结果 | _ManagedBattle.pending/requests | 当前决策提交 |
| 已公开身份 | _ManagedBattle.revealed | 实际上场后，查询不写入 |
| 规则事件、操作记录 | 平台历史 | 结算成功后 |
| 准备阵容、首发确认、房间成员 | RoomService | 玩家提交或加入 |
| 浏览器令牌 | HTTP 适配层 | 认证映射为稳定玩家身份 |

get_battle_status() 从核心读取状态。单局操作串行化，异常恢复暂存、核心与历史。动作缓存按提交方及请求编号隔离；旧 decision_index 的新请求被拒绝。

Web 使用 RoomService。BattlePlatform 提供 create_battle(mode="full")、set_roster、submit_selection、get_legal_actions、get_display_info、get_public_observation、export_battle 和 import_battle。普通回合等待双方动作，替补仅等待核心指定玩家，终局拒绝新动作。partial、HP 校准、训练包装和单浏览器控制双方路径已停用。

state.normalize_observation 按实际上场事实投影。未上场身份未知；已上场保留公开血量、能量、属性、血脉、形态与公共状态。对手技能、冷却、性格、资质和完整六维隐藏。奉献分布及技能专属效果仅己方可见；双方印记、天气和 MP 公开。平台按观察方过滤事件，HTTP 与页面不二次遮蔽。

显示与伤害预览在副本计算。每个平台注入自己的 CoreCatalog，不使用全局目录配置。

平台快照格式 nrc_platform.session.v2；保留待提交动作、请求缓存、公开身份与历史。旧格式拒绝，无迁移器。核心载荷为本地可信 pickle，不能作为公开上传协议。

验证：`python -m pytest tests/test_platform_boundaries.py -q`。
