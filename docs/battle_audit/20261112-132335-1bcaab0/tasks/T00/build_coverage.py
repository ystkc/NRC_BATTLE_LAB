"""把权威规则逐行关联到模块证据，旧对局不作为规则依据。"""

import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parents[1]
FIELDS = ["item_id", "conclusion", "rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability"]
INVFIELDS = ["item_id", "kind", "name", "owner", "source", "line", "parent_id", "description", "reachability"]


def write(path, fields, rows):
    """保存含逐项证据和限制的中文表。"""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    """区分规则审阅、限定实证、明确缺陷和资料不全。"""
    rules = json.loads((HERE / "rules_review.json").read_text(encoding="utf-8"))
    changes = {
        "1": ["确认缺陷", "nrc_core/engine/handlers_skill.py:_h_poison/_h_convert_buff_to_poison", "T08-I04", "普通中毒免疫规则被转换写入旁路绕过；中性中毒样例不证明所有来源正确。"],
        "8": ["确认缺陷", "nrc_core/engine/helpers.py:_clear_debuffs;handlers_skill.py:_h_cleanse", "T07-I09", "减益定义含异常状态，实际清除只处理五维等字段；真实洗礼路径复现见T07补件。"],
        "10": ["确认缺陷", "nrc_core/engine/handlers_skill.py:_h_poison_mark", "T08-I05", "直接写入中毒印记绕过普通负面印记单槽，与通用替换函数产生不同结果。"],
        "11": ["确认缺陷", "nrc_core/engine/executor.py;handlers_skill.py:_h_life_drain;nrc_core/battle.py", "T08-I01", "减伤前预估伤害先回血；真实撕裂应对的本次吸血未消费。"],
        "21": ["确认缺陷", "nrc_core/models.py:add_electric_stacks", "T03-I06", "即时25%伤害跨冻结阈值后仍活着；类型免疫控制另见T08/T09。"],
        "30": ["确认缺陷", "nrc_core/engine/handlers_skill.py:_h_weather;nrc_core/models.py:BattleState.deep_copy", "T04-I14;T08-I02;T03-I07", "凭空沙暴扣血、同天气重设重复折半及默认深拷贝恢复键失联分别列根因；类型无效不掩盖缺口。"],
        "32": ["确认缺陷", "nrc_core/battle.py:_apply_moisture_mark", "T04-I13", "湿润印记无依据消费为0，并永久改写场上/场下技能成本；独立实测已保存。"],
        "33": ["确认缺陷", "nrc_core/engine/handlers_ability.py;handlers_skill.py", "T09-I09;T08-I04", "充分燃烧按4%而不是通用2%，转换写入绕过火系免疫；不据此否定正常燃烧路径的每个分支。"],
        "34": ["未实现", "nrc_core/runtime.py:legal_actions;nrc_core/models.py;effect_data.py", "T05-I07", "流沙无禁足效果、模型无持续表示，正式动作仍允许换人且无UnsupportedMechanicError。"],
        "45": ["确认缺陷", "nrc_core/engine/handlers_skill.py:_h_damage", "T08-I11", "原技能1击叠hit_count_mod=2后从90变270，违反只对原有连击生效。"],
        "47": ["未实现", "nrc_core/runtime.py:legal_actions;nrc_core/rules_support.py", "T05-I08", "选择选项只进入字符串，补觉两个分支都仅扣能没有对应回复；加尔/猫礼物复杂计数仍另列问题。"],
        "52": ["确认缺陷", "nrc_core/battle.py:turn_end_effects;nrc_core/engine/handlers_skill.py:_apply_weather_damage", "T08-I03", "内部有thunder分支，外层白名单不调用，真实回合末双方引电0而应各1。"],
        "55": ["规则存疑", "nrc_core/rules_support.py:_apply_resonance_items;nrc_core/battle.py:turn_end_effects", "T05/probe_output.json", "光合整数样例立即200→350、当回合末500、随后650→800→800，后台亦有效；任意血脉、分数取整/反治疗/复活组合未完整证实，不能由单样例通过整条。"],
        "56": ["确认缺陷", "nrc_core/runtime.py:_with_resonance_actions;nrc_core/rules_support.py", "T05-I01;T05-I02", "原首槽能量不足错误禁用2耗愿力，无未用选项，交换后还原不正确；冷却3起算仍待裁决。"],
        "57": ["确认缺陷", "nrc_core/rules_support.py:_apply_boss_resonance;nrc_platform/catalog.py", "T05-I03;T02", "首领形态数值特性更新但战斗属性未更新；生命比例/旧状态/远古血脉政策另列疑问。"],
    }
    rules.update(changes)
    replacements = {"compare_priority": "_compare_action_order", "compare_speed": "_compare_action_order", "execute_agility_skill": "execute_agility_entry", "battle.py:disengage": "battle.py:_random_disengage", "engine/helpers.py:_apply_weather_damage": "engine/handlers_skill.py:_apply_weather_damage"}
    for record in rules.values():
        for old, new in replacements.items():
            record[1] = record[1].replace(old, new)
    (HERE / "rules_review.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    assigned = list(csv.DictReader((HERE / "assigned_inventory.csv").open(encoding="utf-8-sig")))
    field_rows = list(csv.DictReader((AUDIT / "tasks/T10/semantic_review.csv").open(encoding="utf-8-sig")))
    field_cases = {row["case"]: row for row in field_rows}
    rows = []
    links = {
        "data/README.md": ("nrc_core/battle.py:execute_full_turn/turn_end_effects;runtime.py:advance", "T04/report.md;T05/report.md;cross_module_output.json", "规则存疑", "逐阶段追踪；已确证50回合、末尾顺序和离场缺口；双方同时阶段和四项全平的预期见questions与T05-Q01。"),
        "data/伤害数值计算.md": ("nrc_core/battle.py:DamageCalculator;engine/handlers_skill.py:_h_damage", "independent_damage.json;cross_module_output.json;T04/issues.md", "规则存疑", "11显式六维样例用Fraction独立求期望；减伤组合及最低伤害已确证T04-I01，其他条件需对应技能参数，不泛化为完整伤害路径通过。"),
        "data/属性数值计算.md": ("nrc_core/catalog.py:calc_combat_stats;constant.py;pokemon_nature_table.py", "T03/report.md;T03/stat_mismatches.csv;questions.md", "确认缺陷", "112500个IV0标量中12325差异证明Float16问题；性格30矩阵独立通过；资质倍率文字冲突单列T00-Q03。"),
        "data/属性克制表.md": ("nrc_core/models.py:get_type_effectiveness", "T03/type_matrix.csv;T03/report.md", "通过", "按本表独立构建18单系与18³有序双系输入，6156项相等；仅属性矩阵，不包括技能参数和状态免疫。"),
        "data/状态分类.md": ("nrc_core/models.py;compound_status.py;engine/helpers.py;nrc_platform/state.py", "T03/report.md;T07/report.md;T11/issues.md", "规则存疑", "三类归属及计算展开已逐接口核对；离场、技能交换/复制、公开修正与萌化恢复有独立缺口，不能以正常样例通过全部生命周期。"),
        "data/效果指示器.md": ("nrc_core/core.py:_effect_indicator;nrc_server/static/presentation.js", "T03/type_matrix.csv;T12/report.md", "规则存疑", "六种显示类别与全矩阵关联，界面和实际damage系数需逐独立分支证据；免疫0目前不在18系矩阵中，不能误报为现行属性缺陷。"),
        "data/对战过程中的信息遮蔽规则.md": ("nrc_platform/rooms.py:_visible_events;state.py:normalize_observation;nrc_server/static/app.js", "T11/probe_output.json;T12/report.md", "确认缺陷", "实际双视角未出场bench萌化事件泄露身份；准备阶段全阵容是否受本规则约束另列T11-Q01，技能专属正常遮蔽不证明全事件字段。"),
        "data/部分规则详解/传动机制.md": ("nrc_core/engine/executor.py:execute_drive;nrc_core/battle.py", "T07/issues.md;T10/issues.md", "未实现", "当前按用技能触发后槽被动，没有回合开始循环移位；未明确拒绝。A/B每轮分组与循环终止均无执行证据。"),
        "data/部分规则详解/共鸣魔法.md": ("nrc_core/runtime.py;rules_support.py;nrc_platform/builder.py", "T05/report.md;T02/report.md", "规则存疑", "三个已上线共鸣及限制逐项核对，愿力还原/合法性、首领属性明确缺陷；含糊血脉/HP/CD保留问题。"),
        "data/部分规则详解/奉献.md": ("nrc_core/devotion.py;engine/handlers_field.py;nrc_platform/builder.py;state.py", "T04/issues.md;T10/issues.md;T11/issues.md;questions.md", "确认缺陷", "满层排除/指定上限、每次永久重复加成和对手总层数显示有独立反例；均匀权重是暂定依据，按T00-Q04单列。"),
        "data/部分规则详解/折射效果.md": ("nrc_core/engine/handlers_field.py:_h_refraction", "T10/probe_output.json;T10/semantic_review.csv", "确认缺陷", "18类型逐候选实测；所有整体折射均因排除折射本身/同属性去重不完整，幻/火毒/地还有类型专属问题。"),
        "data/部分规则详解/契约的形状.md": ("nrc_core/engine/handlers_field.py:_apply_ball", "T10/probe_output.json;T10/semantic_review.csv", "规则存疑", "12常规+柔软18候选已实测；三个速度百分比、淘沙及柔软9项有确证。按候选台账逐项分结论，不将整个说明统一通过。"),
        "data/部分规则详解/稀兽花宝.md": ("nrc_core/engine/handlers_field.py:_h_bloodline_effect;effect_data.py", "T10/semantic_review.csv;T10/issues.md", "未实现", "18血脉逐一调用仅萌分支有效；其余17接口返回无效果，当前配置固定萌，未因不可达称未上线。"),
        "data/部分规则详解/最好的伙伴.md": ("nrc_core/engine/handlers_ability.py:_h_best_partner;nrc_core/compound_status.py", "T09/probe_output.json;T11/probe_output.json;1007_replay.json", "确认缺陷", "状态层存储展开及正常克制样例通过，但无伤害克制系状态技能仍触发；条件缺陷T09-I06。"),
        "data/部分规则详解/选择类技能.md": ("nrc_core/runtime.py:legal_actions;nrc_core/rules_support.py;handlers_ability.py", "T05/issues.md;T09/questions.md", "未实现", "两个固定己方选项的结构存在，效果未执行；加尔额外触发不重复使用却计猫礼物的组合规则需机制实现后验证，不能静默放行。"),
        "data/部分规则详解/战报.md": ("nrc_platform/rooms.py;state.py;nrc_server/static/presentation.js", "T11/report.md;T12/report.md;1007_replay.json", "规则存疑", "真实技能/应对/力竭/补位和双视角游标已验证，某些被动变化只报通用效果，所有事件内容未逐技能穷举，见T11/T12具体证据与限制。"),
        "data/部分规则详解/安眠、松弛有度：时间规则.md": ("nrc_core/battle.py:_apply_context_abilities;runtime.py:new_game;nrc_platform/builder.py", "T04/coverage.csv;T05/report.md;T09/questions.md", "规则存疑", "正常时间/周末和测试metadata覆盖追踪；UTC+8夜间锁定与可调游戏时间的全部真实边界未独立实证，需明确时钟输入按规则复验，不能拿专名空action认未实现。"),
        "data/部分规则详解/秋收：草系环境.md": ("nrc_core/engine/handlers_ability.py;nrc_core/battle.py", "questions.md;T09/questions.md", "规则存疑", "T00-Q02：权威文档本身只推测草系环境，没有定义；不替用户裁决也不标未上线。"),
    }
    for item in assigned:
        source, description = item["source"], item["description"]
        conclusion, impl, evidence, notes = "规则存疑", source, "report.md", "此项已审阅；不是可独立证明战斗规则的权威资料。"
        if item["kind"].startswith("game_rule"):
            key = str(int(item["item_id"].split(":")[1]))
            conclusion, impl, ref, notes = rules[key]
            evidence = f"rules_review.json;{ref};../{ref[:3]}/report.md" if ref.startswith("T") else f"rules_review.json;{ref}"
            notes += "本行子句保留完整对象风险；单条缺陷不等于其余所有子句均证实错误。" if item["kind"] == "game_rule_clause" else ""
        elif source in links:
            impl, evidence, conclusion, notes = links[source]
            if source.endswith("稀兽花宝.md") and description.startswith("萌血脉"):
                conclusion, notes = "通过", "萌血脉敌双攻-60%中性目标逐参数实证；其余17血脉缺失和配置固定萌另列。"
            if source.endswith("契约的形状.md") and item["kind"] == "rule_clause":
                selected = next((row for key, row in field_cases.items() if key.startswith("contract_") and description.startswith(key[len("contract_"):])) , None)
                soft_order = ["skill_power", "heal", "burn", "skill_cost", "spatk", "slow_combo", "speed", "poison", "def", "atk", "combo", "enemy_atk", "spdef", "meteor", "freeze", "enemy_spdef", "energy", "drain"]
                if 15 <= int(item["line"]) <= 32:
                    selected = field_cases[f"soft_{soft_order[int(item['line'])-15]}"]
                if selected:
                    conclusion, notes = selected["conclusion"], selected["notes"] + "；只通过候选基础效果，重入与免疫路径不外推。"
                    evidence = f"T10/{selected['evidence']};T10/semantic_review.csv"
            if source.endswith("最好的伙伴.md") and description.startswith(("每层使", "“最好的伙伴”作为")):
                conclusion, notes = "通过", "完整层状存储、计算时五维展开及重复查询不污染已有实证；无伤害状态技能错误触发独立列T09-I06。"
            if "资质" in description and "倍" in description:
                conclusion, notes = "规则存疑", "T00-Q03：6倍文字与8→40示例冲突，未用有资质输入判精度通过。"
            if source.endswith("共鸣魔法.md") and description in {"尚未上线"}:
                conclusion, notes = "未上线", "本行明确声明；只对应闪焰爆发/节流术，未用无配置或不可达代替此结论。"
            if source.endswith("奉献.md") and "暂定" in description:
                conclusion, notes = "规则存疑", "T00-Q04：均匀分布只是暂定；满层排除和上限是另两条明确规则。"
            if source.endswith("属性数值计算.md") and (description.startswith(("生命-", "物攻-", "魔攻-", "物防-", "魔防-", "速度-")) or "都是+20%" in description):
                conclusion, notes = "通过", "30个性格的升降维度及名称从md独立重建并核对；Float16计算精度缺陷另列，不能混为性格映射错误。"
            if source.endswith("README.md") and "全平" in description or "剩余规则不明确" in description:
                conclusion, notes = "规则存疑", "T00-Q01：四指标全平剩余裁决未定义；不添加随机胜负。"
            if item["kind"] == "file" and conclusion == "通过":
                notes += "全文件仅就本表的属性矩阵映射通过。"
        elif source.startswith("data/manual_battles/") or source.startswith("1007") or source.startswith("data/1002"):
            impl, evidence = "nrc_platform/platform.py;RoomService;对应技能/特性原语", "questions.md;1007_replay.json;independent_damage.json"
            notes = "仅作为人工观察证据逐条审阅，不能作权威规则；1002缺敌完整输入，1007有笔误和缺最终目标，具体缺项见T00-Q05。"
        elif source.startswith("tests/"):
            evidence, impl = "pytest.log;pytest.xml;independent_damage.json;../T12/report.md", source
            notes = "19 pytest已全部通过且逐条阅读；含直接调用被审计计算函数求expected的用例只证明回归兼容。网页脚本采用审计副本独立Chrome双context，原脚本不连接已有浏览器。"
        elif source == "playwright_1007.js":
            evidence, notes = "../T12/report.md;questions.md", "原脚本硬连9222/9223并写根目录结果，未执行；已阅读并在审计副本更改连接/结果路径。手记容差和预期不作为规则。"
        elif source == "pyproject.toml":
            conclusion, evidence, notes = "确认缺陷", "dependency_output.json;issues.md", "T00-I01：基础/dev未声明核心直接需要NumPy；本机已有依赖不能替代干净安装契约。"
        elif source == "scripts/check_runtime_migration.py":
            notes, evidence = "全文阅读；动态加载历史实现只作兼容线索，未执行且不以历史等价证明规则正确；快照/预览独立检查见T05/T11。", "../T05/report.md;../T11/probe_output.json"
        elif source in {"scripts/__init__.py", "tests/__init__.py"}:
            conclusion, notes, evidence = "通过", "文件为空/仅模块说明，无独立业务规则或运行分支。", source
        elif source == "AGENTS.md":
            conclusion, notes, evidence = "确认缺陷", "唯一查库边界静态保持；但未实现静默放行已由T07/T09/T11多入口证实，不能给整体遵守通过。", "../T07/issues.md;../T09/issues.md;../T11/issues.md"
        elif source.startswith("package"):
            notes, evidence = "只读核对依赖锁和本机Playwright可调用；实际Chrome双context运行见T12。不是战斗规则。", "../T12/report.md"
        rows.append(dict(item_id=item["item_id"], conclusion=conclusion, rule_basis=f"{source}:{item['line']} {description}" if item["kind"] in {"rule_clause", "game_rule", "game_rule_clause"} else "AGENTS.md；权威data规则；接口约定单列", implementation=impl, objects=item["name"], method="逐条规则/资料审阅；跨模块双向映射；独立公式与实际最小复现", evidence=evidence, notes=notes, reachability="见对应任务证据；不以不可达替代语义结论"))
    extras = []
    for label, conclusion, basis, impl, evidence, note in (
        ("resonance_unreleased_flame", "未上线", "data/部分规则详解/共鸣魔法.md:44", "nrc_core/actions.py;runtime.py", "../T05/report.md", "闪焰爆发明确尚未上线"),
        ("resonance_unreleased_throttle", "未上线", "data/部分规则详解/共鸣魔法.md:48", "nrc_core/actions.py;runtime.py", "../T05/report.md", "节流术明确尚未上线"),
        ("damage_fraction_11", "通过", "data/伤害数值计算.md", "nrc_core/battle.py;engine/handlers_skill.py", "independent_damage.json", "11个显式六维伤害用独立Fraction求期望，不证明六维本身正确"),
        ("turn50_four_metrics", "确认缺陷", "data/README.md:35-42", "nrc_core/battle.py;core.py", "cross_module_output.json", "分别只由MP/存活/HP/能量决定，四个均进51且无winner，合T04-I03"),
        ("multiple_reductions_minimum", "确认缺陷", "data/伤害数值计算.md:7-21", "nrc_core/battle.py:_apply_enemy_damage_reduction/_apply_ability_damage_reduction", "cross_module_output.json", "80%技能+50%特性，多段预期3实际2；最低1被减为0；合T04-I01"),
        ("two_submission_orders", "通过", "双人提交协议、固定种子与只读约定", "nrc_platform/platform.py;runtime.py", "1007_replay.json", "双顺序11回合一致及68只读/幂等/过期检查；不以回放自身作伤害预期"),
    ):
        item_id = f"T00-CONTRACT:{label}"
        extras.append(dict(item_id=item_id, kind="cross_module_contract", name=label, owner="T00", source=basis.split(":")[0], line=1, parent_id="", description=note, reachability="实际接口/明示未上线分别说明"))
        rows.append(dict(item_id=item_id, conclusion=conclusion, rule_basis=basis, implementation=impl, objects=label, method="独立明确预期；最小实际复现", evidence=evidence, notes=note, reachability="详证据中的输入与范围"))
    extra_file = "data/1002_round_replay_2026-10-05.json"
    extras.append(dict(item_id=f"FILE:{extra_file}", kind="file", name=extra_file, owner="T00", source=extra_file, line=1, parent_id="", description="旧回放14条记录，仅兼容线索不作规则", reachability="资料可读；缺完整初始输入"))
    rows.append(dict(item_id=f"FILE:{extra_file}", conclusion="检查受阻", rule_basis="原始1002对局；data规则独立核对", implementation="旧回放资料/当前平台入口", objects="1002旧回放", method="完整静态阅读；与手记核对", evidence="questions.md;../T01/probe_output.json", notes="14条status=ok不是规则通过；缺敌方完整阵容、六维资质和精确HP，不能唯一重放27回合，见T00-Q05及补充资料要求。", reachability="历史资料，不是业务状态输入"))
    write(HERE / "coverage.csv", FIELDS, rows)
    write(HERE / "inventory_extra.csv", INVFIELDS, extras)
    print(json.dumps({"coverage": len(rows), "conclusions": dict(Counter(row['conclusion'] for row in rows))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
