# T12 确认问题

本任务主责六项。仅审计，未修改业务。所有令牌均为本轮独立测试服务生成，证据已脱敏；服务结束后不再有效。

<a id="T12-I01"></a>
## T12-I01　直接 HP 输入与显式空资质导入被自动填入三个 8 资质

- 严重度：P2。主责 T12；协同 T02/T03 核对面板输入与公式。
- 规则依据：`nrc_server/README.md:48-58` 的 Direct stat input 明确只给 HP 时其余五维用零资质、中性性格公式；`data/属性数值计算.md:30` 明确资质可为零。README 是本功能输入契约，不作为战斗公式权威。
- 代码位置：`nrc_server/static/app.js:72-83` 的 `ensureDefaultCustomization`；`addCreature:181-190`；`importRoster:256-257`。无条件对空 `individual_values` 填目录前三项，未区分显式空值与缺省，也未排除 `base.stats` 的直接输入。
- 最小输入/步骤：全新标签页，己方搜索输入 `迪莫 420`，确认，导出阵容。第二条独立输入是在合法阵容 JSON 中显式设 `base.individual_values={}`，导入后导出。
- 预期：第一条保留 `stats.hp=420`，其他五维不增添资质；第二条保留用户显式空资质。
- 实际：两条都变为 `individual_values={speed:8,spatk:8,atk:8}`，血脉还按目录首项补为首领。此处只将不该补的资质判缺陷，不擅自判断血脉默认政策。
- 影响：单 HP 直接输入的其余面板改变；零资质阵容导入导出不能保持配置。六维全部覆盖时资质可能不影响显式六维，不能把本问题泛化成六维覆盖被忽略。
- 证据：`browser_output.json` 的 `directStatExport`、失败检查 `direct HP does not add aptitudes`；`supplement_output.json` 的 `emptyAptitudeRoundtrip`；`06_editor.png`。
- 复现命令：`node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/browser_probe.js` 和 `supplement_probe.js`。两脚本自动使用已空闲的 8774，均关闭自己创建的浏览器和服务。

<a id="T12-I02"></a>
## T12-I02　不同共鸣魔法复合行动显示成完全相同按钮

- 严重度：P2。主责 T12；协同 T05 提供合法复合行动。
- 规则依据：`data/部分规则详解/共鸣魔法.md:3-18,34-38` 区分愿力强化与光合治愈，两者效果、次数和本场所携带种类不同；页面选择必须能区分实际提交的合法动作。
- 代码位置：`nrc_server/static/app.js:528-532` 的 `actionLabel` 只读 `primary.kind/skill_name`；`:566-568` 的 `renderBagDrawer` 把完整含 resonance 的 key 放在按钮，文字却不显示 resonance。
- 最小输入/步骤：1007 A/B 各前两只即可，把 A 首只迪莫技能换为 `[假寐,火焰箭,棘突,超导]`，光血脉，正常准备确认后打开“背包”。
- 预期：至少用“假寐 + 愿力强化”和“假寐 + 光合治愈”等不同文字说明将提交哪种共鸣。
- 实际：两个按钮文字都只有“假寐”，一个提交 `skill:slot=0|resonance=willpower`，另一个提交 `skill:slot=0|resonance=solar_heal`；没有 title、图标或辅助文字区分。其它共鸣条目也只显示原技能或聚能名。
- 影响：玩家无法从 UI 判断正在选择的共鸣种类，可能提交另一种共鸣并消耗对应次数。本问题不判断下层共鸣实现是否符合原文。
- 证据：`supplement_output.json` 的 `bagButtons/indistinguishable`；已人工查看 `07_resonance_choices.png`。
- 复现：运行 `supplement_probe.js`，检查 `bag distinguishes resonance choices=false`。

<a id="T12-I03"></a>
## T12-I03　退出后在途房间摘要响应回填已清空的对局

- 严重度：P2。主责 T12；不需要下层业务配合才能复现。
- 规则依据：`nrc_server/static/session.js:11-29` 定义退出清除当前会话；`nrc_server/README.md:17-25` 说明页面状态由令牌绑定当前房间。清除后不应重新持有无令牌的旧房间。
- 代码位置：`nrc_server/static/battle.js:32-47` 的 `refreshBattle` 捕获 ID 后 await 摘要，随后直接写回 `state.battle`，没有请求代次、房间或认证检查。`app.js:644-655` 清理退出；相对地 `app.js:400` 的 operation 轮询已有房间/decision 复核，不能据此推定刷新也安全。
- 最小步骤：双方正常进入回合；提交双方聚能，使用 Playwright `route` 仅延迟 A 的 `GET /api/battles/{id}` 摘要请求，保持真实服务器响应；A 点击“退出”；释放摘要响应，等待 300ms。
- 预期：准备屏可见，`state.battle=null`、`playerToken=''`，旧响应不再改写本地状态。
- 实际：退出当刻二者均已清空；响应释放后 `state.battle` 恢复为旧房间 turn=3/initialized=true，`playerToken=''`，准备屏仍可见。后续状态请求因令牌清空而失败，页面处于房间与认证不一致的状态。
- 影响：快速退出与网络延迟组合可令旧战斗状态重现；随后创建/提交可能对旧房间发起无认证请求。未宣称导致服务端跨身份访问。
- 证据：`supplement_output.json` 的 `raceImmediately/raceAfter` 与失败检查；`10_exit_race.png`。`supplement_first_attempt.json` 延迟的是后续 state 请求、该时间点没有回填 battle，作为负对照保留。
- 复现：运行 `supplement_probe.js`。只控制网络时序，不注入或修改业务状态。

<a id="T12-I04"></a>
## T12-I04　未配置性格时编辑器显示目录第一性格，实际未提交该显示性格

- 严重度：P2。主责 T12；协同 T02/T03 为实际预览提供性格与数值。
- 规则依据：`data/属性数值计算.md:4-22`，性格直接改变属性；`nrc_server/README.md:56-58` 明确直接数值输入不臆造性格。展示当前配置时应与提交/预览一致。
- 代码位置：`nrc_server/static/roster.js:103`：`base.nature || customization.natures?.[0]?.name || ''`；该回退仅用于输入框和加成说明，不写入 base；`:244-249` 的 `previewPayload` 仍提交原 base。
- 最小输入/步骤：新标签页搜索 `迪莫 420`，确认，打开编辑器，不选择任何性格；导出并请求同一 base 的预览。
- 预期：输入框显示未设置/中性，或显式选定某性格并让预览/提交一致。
- 实际：输入框为“莽撞”，加成说明“魔防 -0.1 / 速度 +0.2”；base 没有 nature 字段，同一 HTTP 预览 `nature=null`。这里只证明实际未提交该显示性格，不推导最终面板是否中性；T02 已证明另一 neutral 构造路径实际套用非中性坦率。小数加成是否改成百分号另属文案，不额外记问题。
- 影响：未选择性格的用户会误认为已采用目录高频性格，但请求与预览没有该配置；最终计算走哪条性格回退路径尚未由本场景独立测定。导入性格缺省的阵容也可遇到。
- 证据：`supplement_output.json` 的 `editor.displayedNature/base` 与 `naturePreview.nature`；已人工查看 `11_nature_mismatch.png`。
- 复现：运行 `supplement_probe.js`，检查 `displayed nature matches submitted nature=false`。

<a id="T12-I05"></a>
## T12-I05　拼音匹配少量候选时重复追加已有候选

- 严重度：P3。主责 T12。
- 规则依据：目录检索/编辑器候选展示契约；没有战斗规则推断。
- 代码位置：`nrc_server/static/roster.js:34-38`：首次匹配已经包括 pinyin；少于5项时再次追加同一 pinyin 匹配集合，没有排重。
- 最小输入：真实浏览器目录提供的21项性格候选，query=`mangzhuang`。直接调用同一导出的 `createRosterEditor({}).choiceMatches`；该方法不依赖 DOM。
- 预期：`[莽撞]`。
- 实际：`[莽撞,莽撞]`。本次 `dimo` 匹配较多，因此原始页面探针没有暴露此分支；不能把那条通过推广到小候选集。
- 影响：性格、血脉、资质或技能检索出现重复按钮，挤占最多5项的显示位置。
- 证据：`pure_js_output.json`，输入候选来自 `supplement_output.json.editor.nature`，不是虚构 metadata。
- 复现：`node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/pure_js_probe.mjs`。Node 模块类型检测警告已保留；业务 package.json 未改。

<a id="T12-I06"></a>
## T12-I06　战斗及补位界面缺少双方 MP 数值

- 严重度：P2。主责 T12；投影已提供字段，无需 T11 配合补数据。
- 规则依据：`data/对战过程中的信息遮蔽规则.md:3` 明确双方 MP 值属于双方可见信息。MP 是阵营资源，精灵当前能量和阵容圆点不能代替 MP 数值。
- 代码位置：`nrc_server/static/battle.js:49-64` 取得 state 后交给 `mergeObservation/renderSide`；`app.js:420-430` 保存完整 shared，但 `:455-481` 只渲染精灵名字、HP、能量、状态及阵容圆点；`index.html:24-27` 没有 MP 容器。其它精灵/背包抽屉与公共状态渲染也未读取 `shared.mp`。
- 最小步骤：按照已有真实 `supplement_probe.js` 的双人场景进入战斗并打开共鸣背包；再对照已有 `browser_probe.js` 制造力竭后的 replacement。无需重新启动服务器复核静态证据。
- 预期：两视角均显示自己的及对方的当前 MP 数值。
- 实际：`supplement_output.json.devotion.a.mp` 与 `.b.mp` 均为 `{own:4,opponent:4}`，字段已由真实 HTTP 观测保存，但全屏 `07_resonance_choices.png` 与 `05_replacement.png` 只有HP/能量、状态和圆点，均无双方 MP。标准同步/渲染链没有MP读取或隐藏入口。
- 影响：用户无法从当前界面知道双方阵营资源，特别是精灵力竭后的剩余 MP；不是把后端缺字段再次计为UI问题。
- 证据：`missing_mp_evidence.json` 保存两个真实视角 MP、源码渲染片段、精准词匹配结果及两截图哈希；两截图已人工复看。只复用已完成 Chrome 真实截图与捕获状态，不重新打开浏览器，也不声称本轮另有DOM快照。
- 复核命令：`python docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/final_supplement.py`；原始真实场景可运行 `supplement_probe.js/browser_probe.js`，本轮未重跑。

## 协同而不重复计主问题

| 主问题 | 本任务核对及证据 | HTTP/网页影响 |
|---|---|---|
| T11-I01 未实现特性被抹除 | 阅读 T11 issues/probe，直接 builder 拒绝与平台正常初始化的差异保留 | 不是 server 鉴权或前端对特性的再次实现；不重复计数 |
| T11-I02 后台萌化事件泄漏未出场名字 | 阅读 T11 双视角事件证据；`eventText` 和 `renderEvents` 会原样显示平台公开事件里的 pokemon | 事件必须在投影端按已揭示索引过滤；前端没有再查隐藏资料 |
| T11-I03 缺对方奉献总数 | `supplement_output.json.devotion`；`08_devotion_owner.png`、`09_devotion_opponent.png` | A自己的假寐分布显示；B对手效果区无任何奉献总数；根因投影缺字段 |
| T11-I04 predict_damage 丢组合修正 | 阅读 T11 证据，并追页面实际只取 `/display` 的 `display_power` | HTTP 无直接 predict_damage 路由；没有把该本地预览缺陷误报成所有网页威力都错 |
| T02 输入合并未校验 nested base | `static_output.json.http`：POST `/api/pokemon/preview`，`{name:迪莫,base:invalid字符串}` →500 `AttributeError: str.get` | 父任务指定 T02 主责，server 正常捕获异常但下层把用户输入异常作为500输出；本任务不重复编号 |

## 不作为当前规则缺陷的观察

`decorate_response(type_effectiveness=0)` 生成平衡图标，而 `RELATION_NAMES.immune` 是“无”；定向失败值见 `static_output.json`。当前 NRC 18系矩阵只有 .5/1/2，双系最小 .25，没有可产生0的类型组合，故不将人工0输入上升为现有对局缺陷；可达性与实现观察分别保留。
