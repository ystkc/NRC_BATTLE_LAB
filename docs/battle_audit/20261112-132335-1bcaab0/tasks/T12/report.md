# T12 HTTP 与双人网页审计

发现六项本层问题：零资质被默认注入、共鸣菜单不同动作同名、退出后在途摘要回填旧房间、性格显示与实际提交不一致、少量拼音候选重复、双方 MP 数值未显示。详见 [issues.md](issues.md)。另保留四项 T11 和一项 T02 协同；准备阶段是否允许队伍预览见 [questions.md](questions.md)，未将未知范围擅自判为漏洞。

本任务完整静态阅读 `nrc_server/**` 的15个源码/说明/样式文件。页面没有重新计算战斗规则：技能卡直接使用核心 `/display` 的威力/能耗/连击/先手，按钮对照 `/actions`；对手弹窗只取投影中的 known 条目；公共事件直接格式化显示，因此平台已经泄漏的信息也会显示。技能描述和数值是否符合全部原文继续归 T06/T08/T09 等，本任务不以网页与同一后端一致证明核心规则正确。

实际使用已安装 Playwright `chromium.launch({channel:'chrome',headless:true})`，Chrome `153.0.8010.36`，一个新建浏览器中的两个独立 context，未连接现有浏览器或CDP。旧 `playwright_1007.js` 与 `tests/playwright_ui_changes.js` 已完整复制为任务内 legacy 文件，仅作流程线索，未执行旧 CDP 代码；1007 JSON 只复用合法输入，未以旧文本战斗数字为权威预期。独立服务器使用事前确认空闲的 127.0.0.1:8774，关闭核心诊断，stdout/stderr 只写任务内 server.log，业务层未配置文件日志。

运行证据覆盖以下路径：

- 双人从导入、创建、加入、确认首发到实际战斗；两 context 令牌和席位隔离；八类 GET 无认证401、已有非成员403；同令牌重加仍原席位，第三席拒绝，side query不改变身份，roster 的 side 注入拒绝。
- 单方 pending 刷新后认证和锁定保持，所有技能禁用；同 request_id 响应相同，不同新请求重复 pending 返回409，旧 decision 返回409；双方收齐正常推进。并发事务/回滚另由 T11 负责。
- 正常回合刷新前后历史均11条；尾游标读取为空。已知对手由一只变两只后，离场者仍保留公开HP/能量/特性，未出场乌拉塔不在弹窗；560×800 窄屏弹窗边界有效。
- 用显式低HP/高攻击面板仅强制制造力竭，真实进入单方 replacement；对手无可选技能，我方只显示可替换卡；刷新仍可补位，选择后继续下一回合。极端面板只服务于流程输入，未据此推断战斗规则。
- 初始四技能按钮合法性与核心显示返回值逐项对照，普通主动换宠正常；奉献自己的总数及分布显示，对方分布不显示，但对方总数缺失关联 T11-I03。
- 资源展示定向验证缺目录、缺名、形态回退、portrait选择、精确文件、递归列表/字典/标量、不修改输入、保留既有资源、六档关系；15类事件格式字段保留在 supplement_output.json.formatter。

全部17个 HTTP 路由方法均有成功请求证据，详见 [route_coverage.csv](route_coverage.csv)。`static_output.json` 是经过真实 FastAPI 路由栈的 TestClient 请求，不是直接绕过路由调用平台；Chrome 另有实际独立网络服务器。非法 nested base 的500保留给 T02，未知精灵 GET 的422是 `invalid_roster`，没有依据要求其一定404，所以不列缺陷。

原始 assigned 为120行、108个唯一ID，基线有同行三元导致的重复ID。保留原清单，按唯一ID聚合覆盖，并补逐条件 PYSEM 消歧。JS解析补222函数（含匿名回调）与1,310个 if/三元/短路/循环/catch 控制方向；再补16个 Python 条件方向、17个 route 和12个场景，总 extra=1,577。coverage 合计1,685个唯一ID，零缺失、零重复；186通过、22确认缺陷、1,477规则存疑。数量是对象/方向数，22个确认项不是22个独立根因。完整统计见 [checkpoint.json](checkpoint.json)，具名函数静态判断与输入范围见 [function_review.csv](function_review.csv)。

“通过”只限行内列明的契约与参数。本次未为所有1,310方向单独构造输入；静态已读但没有独立输入证据的方向保守存疑，未按“函数调用过”或“配置非空”放行。匿名回调也未仅继承外层函数通过。CLI `python -m` 入口本次没有直接启动，服务用显式关闭诊断后的 uvicorn.run(app)；剪贴板拒绝、损坏 sessionStorage、所有形态循环/边缘悬浮、异常网络与终局各 UI 分支没有完整运行证据。未把这些局限隐藏在整体通过里。

执行命令均在仓库根，Python 使用 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`、后续复现建议 `PYTHONDONTWRITEBYTECODE=1`：

```text
node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/browser_probe.js
node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/supplement_probe.js
python docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/static_probe.py
node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/pure_js_probe.mjs
node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/js_inventory.js
python docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/build_report.py
```

初轮复现保留在 `browser_first_attempt.json`、`supplement_first_attempt.json`、`supplement_second_attempt.json`：首轮初始 readiness 太早读到空 display，后改为等待真实可用按钮；补位首轮只有一个技能被正确拒绝，后补足四槽；初轮延迟 state 请求没有触发摘要回填，后定位到 summary 在途窗口。上述是探针修正或负对照，不作为额外产品缺陷。当前 browser_output 的“未知精灵404”失败是探针预期不受契约支持，正文已明确排除。pure Node 调用的模块类型检测警告保留，不修改 package.json。

中文原生补丁和UTF-8源文件读取正常。一次临时 PowerShell→Python stdin 查询中，中文筛选字面量未匹配；改为文件/ASCII脚本路径读取，不用于任何判定或数据写入，未掩盖为空结果。证据中的生成令牌已脱敏。来源哈希逐一对照主基线15/15一致，见 [source_hashes.json](source_hashes.json)，用户已有修改保留。任务脚本只写本任务目录；未修改业务或数据库。最终浏览器/自起服务器关闭与端口检查见 [cleanup.json](cleanup.json)。

末次交付复核新增 T12-I06：`data/对战过程中的信息遮蔽规则.md:3` 明确双方MP可见；已保存真实 A/B `shared.mp={own:4,opponent:4}`，但既有全屏 `07_resonance_choices.png` 与 `05_replacement.png` 均无MP显示，完整同步/渲染链没有MP消费者或隐藏展示入口。证据见 [missing_mp_evidence.json](missing_mp_evidence.json)。本次只复看既有截图、读取捕获状态和源码，没有重新启动 Chrome/服务器，未声称新增DOM快照。MP与奉献总量是不同字段、不同根因。T12-I04 同时收紧为“显示莽撞但实际未提交该性格、preview nature=null”，不由此推断实际中性面板；最终性格回退应与 T02 分路径验证。
