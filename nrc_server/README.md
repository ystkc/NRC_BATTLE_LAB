# nrc_server

`nrc_server` is the browser-facing layer for the multi-turn NRC platform.
It keeps the UI thin: catalog lookup, roster normalization, action legality,
turn resolution, replacement phases, and public battle events remain owned by
`nrc_platform` and `nrc_core`.

Start it from the repository root:

```bash
python -m nrc_server.server --host 127.0.0.1 --port 8767
```

Open `http://127.0.0.1:8767/` in two separate browser sessions. Each player builds
their own team and submits their own action. The platform resolves a decision
after every required player has submitted.

The HTTP session table stores only token-to-player identity bindings. Room setup,
seat ownership, battle history, and visibility live in `nrc_platform.rooms`.
Battle state and pending actions remain in `BattlePlatform`; the server does not
keep a second mutable battle state. All state is currently in memory.

`server.py` handles HTTP and authentication; `presentation.py` adds static asset
URLs after platform projection. The browser uses native ES modules: `api.js`
handles requests, `session.js` restores the current tab, `state.js` stores UI
state, `roster.js` edits teams and previews, `battle.js` synchronizes decisions,
`presentation.js` formats events, and `app.js` binds the page interactions.

## 双用户对战

当前页面默认使用 `full` 双用户模式：

1. 第一位用户选择自己的阵容，点击“创建并提交阵容”，复制页面上的对战 ID。
2. 第二位用户在同一页面输入对战 ID，点击“加入对局”，选择并提交自己的阵容。
3. 两位用户分别提交自己的行动；服务端只在双方都提交后推进回合。

浏览器通过 `X-Player-Token` 将请求绑定到稳定身份，身份在房间内绑定固定席位。观察接口按席位交换“我方/对方”视角；对手未上场精灵保持未知，已上场精灵的公开面板由平台提供。客户端不能通过 `side` 参数冒充另一方，也不能一次提交双方阵容。阵容仅接受本人 `roster`；行动提交携带 `request_id` 与 `decision_index`，重复请求不会重复推进，过期决策返回冲突。

## 增量战报同步

战斗页面通过 `GET /api/battles/{battle_id}/operation` 轮询双方是否已提交操作；只有回合结算后才请求状态和技能展示数据。战报通过 `GET /api/battles/{battle_id}/events?since={cursor}` 使用游标增量读取：首次进入只建立历史，不播放旧战报，之后只播放游标之后的新事件。

## 合法动作与克制徽章

技能、聚能和精灵切换按钮只在 `GET /api/battles/{battle_id}/actions` 返回的合法动作中可点击，能量不足或冷却中的技能会置灰。力竭进入换人阶段时，技能栏会换成可切换的精灵卡片。

`GET /api/battles/{battle_id}/matchups` 返回己方每只精灵对当前对方上场精灵的最佳克制档位，优先级为双重克制 > 克制 > 双重抵抗 > 抵抗 > 平衡。只统计有伤害的技能（物攻、魔攻且威力大于 0），没有伤害技能的精灵不显示徽章。
## Direct stat input

The roster search accepts a creature name followed by either one HP value or
six values in this order: `hp atk def spatk spdef speed`. Examples:

- `bbh 420` supplies only HP.
- `hjcts 440 380 250 280 390 100` supplies all six combat stats.

Direct stat input does not invent a nature or individual values. With one HP
value, the other five stats use the database formula with zero aptitude and a
neutral nature; with six values, all six values are used exactly as entered.
