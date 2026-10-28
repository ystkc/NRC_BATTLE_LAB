# NRC Battle Lab

Python ≥ 3.10 的洛克王国 NRC 双人对战平台。

`HTTP/页面 → RoomService → BattlePlatform → BattleRuntime → 玩家视角 → 页面`

- nrc_core：全知规则计算，不查库、不猜未知信息。
- nrc_platform：唯一查库层、对局状态、提交事务、历史与可见性。
- nrc_server：HTTP 认证、路由、资源和原生 ES 模块页面。
- nrc_ai：暂存的后续研究代码，旧训练与预测入口停用。
- wiki_crawler：Wiki 数据采集；data：规则、数据库与素材。
- ocr_service：暂时废弃。

安装：`pip install -e ".[dev]"`。

启动：`python -m nrc_server.server --host 127.0.0.1 --port 8767`。两个浏览器分别创建和加入同一对局，各自配置并确认首发后行动。

字段归属见三层 README；核对记录见 [三层重构](docs/三层重构.md)。
