# nrc_server

`nrc_server` is the browser-facing layer for the multi-turn NRC platform.
It keeps the UI thin: catalog lookup, roster normalization, action legality,
turn resolution, replacement phases, and public battle events remain owned by
`nrc_platform` and `nrc_core`.

Start it from the repository root:

```bash
python -m nrc_server.server --host 127.0.0.1 --port 8767
```

Open `http://127.0.0.1:8767/`. The current console follows the manual battle
rhythm: build both teams, lock the two sides' actions, resolve one turn, append
the public event stream, and expose the next legal action set. It intentionally
does not invent hidden opponent data or auto-pick a replacement creature.

The HTTP layer is session-scoped and in-memory. Use the platform snapshot APIs
for durable replay or reconnect support.

## 双用户对战

当前页面默认使用 `full` 双用户模式：

1. 第一位用户选择自己的阵容，点击“创建并提交阵容”，复制页面上的对战 ID。
2. 第二位用户在同一页面输入对战 ID，点击“加入对局”，选择并提交自己的阵容。
3. 两位用户分别提交自己的行动；服务端只在双方都提交后推进回合。

浏览器通过 `X-Player-Token` 将请求绑定到加入者。观察接口会按加入者交换“我方/对方”视角，并隐藏对方精灵名称、技能、属性和完整血量，只保留对方血量百分数及双方能量。战报只保留可读的技能、伤害和回合结束文本，并同步隐藏对手未公开的技能名。