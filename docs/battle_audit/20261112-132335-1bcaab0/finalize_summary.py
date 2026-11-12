"""生成可复核的审计入口、统计和必查场景索引。"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
STATUSES = ["通过", "确认缺陷", "未实现", "规则存疑", "检查受阻", "未上线"]


def read_csv(path):
    """读取最终主表。"""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def scenario_rows():
    """把要求的场景映射到实际证据及未完成的行为验证。"""
    return [
        ("数值与边界", "六维精度和四舍五入", "确认缺陷", "T03-I01", "625形态×30性格×6维，IV0，112500标量；独立Float32逐步公式，12325项不符", "tasks/T03/stat_mismatches.csv", "正资质倍率待T00-Q03裁决，未将IV0通过扩展为所有IV"),
        ("数值与边界", "性格和正资质数量", "确认缺陷", "T02-I02/I03；T03-Q01", "30性格映射核对；六正资质被接受；默认零修正使用非中性性格", "tasks/T02/probe_output.json;tasks/T03/probe_output.json", "资质6倍文字与+8→40示例冲突待裁决"),
        ("数值与边界", "伤害公式和取整顺序", "确认缺陷", "T04-I01", "基础11显式面板案例独立有理数期望相符；逐段和最终减伤顺序有反例", "tasks/T00/independent_damage.json;tasks/T04/repro_output.json", "未穷举全部技能动态威力和分段时点"),
        ("数值与边界", "本系与血脉区别", "确认缺陷", "T10-I07；T06最终对象表", "本系样本独立算术核对；花宝血脉18参数分支核对，17缺失且固定萌", "tasks/T00/independent_damage.json;tasks/T10/semantic_review.csv", "所有血脉与特性叠加尚无完整组合证明"),
        ("数值与边界", "单/双属性克制", "通过", "T03", "18×18单系及18³有序双系6156输入，独立文档矩阵全部一致", "tasks/T03/type_matrix.csv", "通过限克制矩阵函数，不含动态转系/首领类型同步"),
        ("数值与边界", "增减益并存及99层上限", "确认缺陷", "T03-I02/I03；T02-I05", "普通正负并存和组合展开；99/100边界与双攻双防40/9截断、构建覆盖反例", "tasks/T03/probe_output.json;tasks/T02/probe_output.json", "速度/特殊组合层数规则不明的保留T03问项"),
        ("数值与边界", "无威力技能和动态威力", "确认缺陷", "T06-I04/I13；T08-I10", "空效果扣能后无行为；固定威力被当百分比；冰锋横扫/钢钻缺动态条件", "tasks/T06/skill_probe.json;tasks/T08/probe_output.json", "每名技能待证条件见final_object_review，不能以中性一击推为完整通过"),
        ("数值与边界", "最低伤害与多重减伤", "确认缺陷", "T04-I01", "Fraction独立期望：80%技能减伤与50%特性减伤三击3实际2，最低1被减为0", "tasks/T00/cross_module_output.json", "其他减伤、免疫、盾、反击组合仍逐对象待证"),
        ("数值与边界", "回复上限、吸血及反转", "确认缺陷", "T08-I01/I07；T09-I10", "吸血早于最终伤害；50%减伤样本heal90/实际damage45；反转2倍仅按布尔处理", "tasks/T08/probe_output.json;tasks/T09/probe_output.json", "过量伤害、多人分配、全部回复来源边界未穷举"),
        ("行动与时序", "共鸣→换人入场顺序", "规则存疑", "T05；T04；T00-Q06", "共鸣合法动作与单方补位各有实测；静态关联动作编排", "tasks/T05/probe_output.json;tasks/T04/coverage.csv", "双方同时共鸣+换人+入场触发的所有速度组合未独立验证"),
        ("行动与时序", "迅捷、应对、先手和拼速", "确认缺陷", "T07-I02/I03/I06；T06-I14", "迅捷算出伤害未扣HP、动态agility不识别、旧路径执行多项；优先级未生成", "tasks/T07/probe_output.json;tasks/T06/probe.py", "致命/非致命应对、每段嵌套组合未逐项穷举"),
        ("行动与时序", "同速随机及种子作用域", "确认缺陷", "T04；T05-I05", "固定结算seed重放一致；初始化/补位/下一回合准备在seed域外有反例", "tasks/T04/repro_output.json;tasks/T05/probe_output.json", "通过只限已验证随机域，不能宣称整个对局仅由seed决定"),
        ("行动与时序", "失败行动的扣能、计数与迸发机会", "规则存疑", "T04-Q；T08-Q；T00-Q06", "相关函数和真实配置已逐项定位，部分失败结果见探针", "tasks/T04/questions.md;tasks/T08/questions.md", "需要明确失败/打断/蓄力时是否消耗行动机会，并补条件两侧独立预期"),
        ("行动与时序", "迸发首次行动及动态能耗", "确认缺陷", "T04-I02/I07/I10；T02跨模块charge", "首次行动标记误用入场回合；石头大餐重复扣费；龙印费用基准不符；5蓄力技能首回合直接攻击", "tasks/T04/repro_output.json;tasks/T02/probe_output.json", "失败后首次机会、逐段费用与退款的完整组合保留待证"),
        ("行动与时序", "多段中途力竭及后续触发", "规则存疑", "T04；T08-I11；T00-Q06", "多击公式/单击不应受多击增益已有反例；死亡中断源码已读", "tasks/T08/probe_output.json;tasks/T04/coverage.csv", "每段受击/吸血/击杀/换人暂停与继续的交叉路径未全部实测"),
        ("行动与时序", "状态伤害→回合末时点", "确认缺陷", "T04-I08；T09-I07/I09", "回血早于DOT、固定A/B代替速度；固定被动重复累加；充分燃烧4%误算", "tasks/T04/repro_output.json;tasks/T09/probe_output.json", "全部EOT触发连锁和多次重复边界未穷举"),
        ("切换与终局", "主动、强制、随机及普通脱离", "确认缺陷", "T04-I04/I11；T09-I05", "普通脱离随机代替选择；新入场离场免疫缺失；自动换人字段无消费者", "tasks/T04/repro_output.json;tasks/T09/probe_output.json", "各类强制切换的全部合法目标/免疫组合未验证"),
        ("切换与终局", "力竭补位及连锁入场", "确认缺陷", "T05-I04", "荆刺/冻结真实入场连锁进入replacement但不扣MP；网页单方补位与刷新恢复实测", "tasks/T05/probe_output.json;tasks/T12/supplement_output.json", "自力竭是否暂停并继续对方行动属T04-I12待裁决，未当确认问题"),
        ("切换与终局", "复活与后台状态", "确认缺陷", "T02-I01；T05-P01/P06；T10-I13", "构建力竭状态被复活；光合后台三次/死者不治疗有样本；系统发育全额复制到后台", "tasks/T02/probe_output.json;tasks/T05/probe_output.json;tasks/T10/probe_output.json", "其他复活来源、HP恢复精确比例及后台所有状态未穷举"),
        ("切换与终局", "MP归零及全队倒下", "通过", "T04；T11", "单侧MP归零/全队倒下和终局actions空、新提交拒绝有实测", "tasks/T04/repro_output.json;tasks/T11/probe_output.json", "仅单侧明确败北；双方同时败北另列存疑"),
        ("切换与终局", "同时终局及50回合四指标全平", "规则存疑", "T00-Q01", "保存同时MP0、同时全倒及四项全平的当前结果，未猜测期望", "tasks/T00/cross_module_output.json", "需明确平局/固定胜方/其他终结协议，随后检查双视角锁定"),
        ("切换与终局", "50回合明确胜者", "确认缺陷", "T04-I03", "依次仅MP/存活/HP/能量决定胜方四个独立场景均进51回合winner=null", "tasks/T00/cross_module_output.json", "指标全平的规则疑问不影响这些明确反例"),
        ("特殊机制", "三个已上线共鸣及次数限制", "确认缺陷", "T05-I01/I02/I03", "愿力费用/交换后还原、首领类型漏更新有反例；普通愿力次数/CD与光合即时+三EOT有限通过", "tasks/T05/probe_output.json", "所有共鸣+技能交换/退化/血脉/同时共鸣组合未穷举"),
        ("特殊机制", "闪焰爆发和节流术", "未上线", "T00-N01/N02", "共鸣文档明确未上线；不作为正常可选动作要求", "tasks/T00/questions.md;tasks/T05/report.md", "未来上线需新增明确规则与正常执行证据"),
        ("特殊机制", "选择类两个分支", "未实现", "T05-I08", "真实补觉两分支均仅扣2费，无回血或回8能；选择字段被记录却未执行", "tasks/T05/probe_output.json", "静默接受，未抛UnsupportedMechanicError；其他选择技能逐名结论见T06"),
        ("特殊机制", "临时技能替换及恢复", "确认缺陷", "T05-I02", "真实隐藏条款交换后愿力还原原槽，其他槽保留临时技能", "tasks/T05/probe_output.json", "应恢复哪个持有者、跨传动的所有权细节仍需规则补充"),
        ("特殊机制", "首领化与萌化退化", "确认缺陷", "T05-I03；T10-I08/I09；T03-I01", "首领类型不更新；清零/转移萌化形态不恢复；后续退化丢永久速度", "tasks/T05/probe_output.json;tasks/T10/probe_output.json", "恢复HP公式、退化临界值及常驻首领支持协议仍有问项"),
        ("特殊机制", "奉献候选池、上限与满层", "确认缺陷", "T10-I01；T02-I08；T00-Q04", "满层仍候选、指定获取绕上限、初始化别名崩溃均有实测", "tasks/T10/probe_output.json;tasks/T02/probe_output.json", "均匀权重是暂定依据；抽样不证明游戏正式概率"),
        ("特殊机制", "折射全部属性与免疫", "确认缺陷", "T10-I02/I03/I04", "18分支参数核对；去重/排除当前技能，火毒免疫缺失，地系单位错，幻系归属错", "tasks/T10/semantic_review.csv;tasks/T10/probe_output.json", "光系本技能30%样本已有；所有叠加来源完整回合组合未穷举"),
        ("特殊机制", "传动循环与扩展", "未实现", "T07-I05/I03；T10-I12", "新回合移位协议缺失仍走旧使用后路径，扩展标志无消费者，翼轴迅捷不识别", "tasks/T07/probe_output.json;tasks/T10/probe_output.json", "当前未明确拒绝；移动后技能恢复/愿力归属须待完整实现后再验证"),
        ("特殊机制", "契约与随机球效果", "确认缺陷", "T10-I05/I06", "常规与柔软球18属性参数分支，固定/百分比及整包误用反例", "tasks/T10/semantic_review.csv;tasks/T10/probe_output.json", "柔软球重入场是否重抽仍需裁决，非统计猜测"),
        ("特殊机制", "时间与周末条件", "规则存疑", "T09；T00-Q02/Q06", "已列所有相关配置、handler和时间条件；秋收环境依据未定", "tasks/T09/clause_review.csv;tasks/T06/final_object_review.csv", "未对所有日期边界/时区/跨午夜/快照恢复组合建立独立输入，不能判整体通过"),
        ("状态与运行一致性", "精灵、技能槽和阵营归属", "确认缺陷", "T07-I04/I09/I10；T08-I05/I06；T11-I04", "中毒印记单槽旁路、星陨归属、减益清除漏项、萌化分类和公共技能修正反例", "tasks/T07/cleanse_probe_output.json;tasks/T08/probe_output.json;tasks/T11/probe_output.json", "各对象所有状态归属/持续/消耗分支见逐项待证，不以一个正确原语覆盖全部参数"),
        ("状态与运行一致性", "同名技能与目录副本隔离", "通过", "T02；T03", "两个精灵同名技能修改与目录副本不互写已有实际身份/数值核对", "tasks/T02/probe_output.json;tasks/T03/probe_output.json", "此通过不包含Skill.copy基准遗失或天气id键缺陷"),
        ("状态与运行一致性", "复制、导入和导出", "确认缺陷", "T03-I04/I05/I07；T05；T11", "分精灵copy破图/丢基准/天气id坏；runtime整体clone修图与pending平台快照语义往返样本通过", "tasks/T03/probe_output.json;tasks/T05/probe_output.json;tasks/T11/probe_output.json", "pickle字节不同不等于语义错；只检查可信本地快照，不发散假设安全问题"),
        ("状态与运行一致性", "重复预览和查询只读", "通过", "T05-P02；T00；T11", "pickle前后状态、RNG和对象身份检查；1007双顺序68只读/幂等/过期契约检查", "tasks/T05/probe_output.json;tasks/T00/1007_replay.log;tasks/T11/probe_output.json", "限定已执行预览输入和查询路径，未覆盖所有异常输入"),
        ("状态与运行一致性", "固定种子全程复现", "确认缺陷", "T05-I05", "1007结算回放事件一致；独立探针证明初始化、补位和回合准备脱离seed", "tasks/T00/1007_replay.log;tasks/T05/probe_output.json", "固定种子回放一条路径不能证明全部随机作用域"),
        ("双人平台与页面", "双方提交先后及并发", "通过", "T11；T00", "1007两提交顺序11回合一致；两线程只推进一次，单history/decision_index", "tasks/T00/1007_replay.log;tasks/T11/probe_output.json", "仅契约推进，不作伤害语义正确性的依据"),
        ("双人平台与页面", "重复、过期、异常回滚", "通过", "T11；T12", "同request幂等、新重复pending/旧decision409；外层抛错核心/缓存/历史/房间全恢复", "tasks/T11/probe_output.json;tasks/T12/browser_output.json", "所有异常注入位置和网络超时重排未穷举"),
        ("双人平台与页面", "身份、席位和全部HTTP方法", "通过", "T12", "17路由方法成功路径；8GET401/非成员403、第三席拒绝、side注入不能换身份", "tasks/T12/route_coverage.csv;tasks/T12/static_output.json;tasks/T12/browser_output.json", "成功路由覆盖不等于每个异常/非法结构均正确；base500另T02-I07"),
        ("双人平台与页面", "单方补位、锁定和终局", "通过", "T12；T11", "真实单方replacement、只显示候选、刷新后继续；终局后actions空且提交拒绝", "tasks/T12/supplement_output.json;tasks/T11/probe_output.json", "全部终局UI动画和双侧同时连锁补位未完整运行"),
        ("双人平台与页面", "战报增量、刷新和退出恢复", "确认缺陷", "T12-I03", "正常历史11条刷新不重复、尾游标空；在途summary在退出后回填旧房间", "tasks/T12/browser_output.json;tasks/T12/supplement_output.json", "断线/所有响应排列及损坏sessionStorage分支未穷举"),
        ("双人平台与页面", "未出场和已出场替补双视角", "确认缺陷", "T11-I02；T12", "本体投影/已出场弹窗样本正确；赤子之心后台事件泄露未出场替补名", "tasks/T11/probe_output.json;tasks/T12/browser_output.json", "准备期队伍可见范围待T11-Q01；全部事件类型仍需逐类负向验证"),
        ("双人平台与页面", "技能专属效果和公共修正", "确认缺陷", "T07-I04；T11-I04", "应对水环全技能修正缺来源；predict_damage漏组合修正；实际技能卡样本直用core显示", "tasks/T07/probe_output.json;tasks/T11/probe_output.json;tasks/T12/browser_output.json", "全部skill-slot隐私标签与所有事件格式组合没有完整证明"),
        ("双人平台与页面", "奉献双视角与双方MP", "确认缺陷", "T11-I03；T12-I06", "自己的总数/分布有显示；对方分布正确隐藏但总数缺失；双方MP已在HTTP返回却无页面消费者", "tasks/T12/missing_mp_evidence.json;tasks/T12/supplement_output.json;tasks/T11/probe_output.json", "已检查两真实context及全屏截图；未用静态API自洽代替规则依据"),
        ("双人平台与页面", "编辑器、共鸣菜单与性格", "确认缺陷", "T12-I01/I02/I04/I05", "零资质输入自动填3×8、共鸣动作同名、显示莽撞但提交null、拼音候选重复", "tasks/T12/supplement_output.json;tasks/T12/pure_js_output.json", "未推定后端null等于中性；具体默认后端性格另T02-I03"),
        ("资料和执行边界", "19现有pytest及人工1002/1007", "检查受阻", "T00-Q05", "19/19回归通过；1007两序11回合及独立11伤害样本；1002仅有不完整观察", "tasks/T00/pytest.xml;tasks/T00/1007_replay.log;tasks/T00/independent_damage.json", "1002缺完整初始状态；1007手记124/123、技能名和最终补位不唯一，未伪造复演结论"),
        ("资料和执行边界", "真实网络采集与故障分支", "检查受阻", "T01-I01；T01-Q04/Q05", "实际CLI迁移错误已复现，内存适配只用于只读理解；未运行联网采集/生产写库", "tasks/T01/probe_output.json;tasks/T01/questions.md", "外部站点/下载/故障注入无运行证据；先修复明确CLI问题再在审计副本重现，不能据此宣布规则未上线"),
    ]


def main():
    """使用最终结果生成文字，不改业务与原始证据。"""
    validation = json.loads((AUDIT / "validation.json").read_text(encoding="utf-8"))
    baseline = json.loads((AUDIT / "baseline.json").read_text(encoding="utf-8"))
    questions = read_csv(AUDIT / "question_index.csv")
    inventory = read_csv(AUDIT / "inventory.csv")
    coverage = read_csv(AUDIT / "coverage.csv")
    object_review = read_csv(AUDIT / "tasks/T06/final_object_review.csv")
    issues = read_csv(AUDIT / "issue_index.csv")
    numeric = validation["conclusions"]
    rows = scenario_rows()
    fields = ["scenario_id", "group", "scenario", "conclusion", "references", "verified_scope", "evidence", "remaining_validation"]
    with (AUDIT / "scenario_matrix.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, values in enumerate(rows, 1):
            writer.writerow(dict(zip(fields, [f"SCN-{index:03}", *values])))
    kind_counts = Counter(row["kind"] for row in inventory)
    review_counts = Counter(row["overall_conclusion"] for row in object_review)
    statistics = {
        "head": validation["head"], "source_files": validation["source_files"],
        "recorded_units": len(inventory), "units_with_conclusion": len(coverage),
        "record_coverage_percent": 100 * len(coverage) / len(inventory),
        "limited_pass_percent": 100 * numeric.get("通过", 0) / len(coverage),
        "conclusions": numeric, "confirmed_issue_groups": len(issues),
        "issue_severity": validation["issue_severity"], "question_groups": len(questions),
        "question_categories": dict(Counter(row["category"] for row in questions)),
        "object_overall": dict(review_counts), "kinds": dict(kind_counts),
        "scenario_count": len(rows), "scenario_conclusions": dict(Counter(row[2] for row in rows)),
        "data_record_checks_separate": 78224,
        "interpretation": "记录覆盖100%仅表示每单位有结论；通过比例不是机制正确率；分支未独立验证以及含糊规则均明确保留，不宣称组合穷举。",
    }
    (AUDIT / "statistics.json").write_text(json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8")
    table = "\n".join(f"| {status} | {numeric.get(status, 0):,} |" for status in STATUSES)
    task_links = "\n".join(f"| T{index:02} | [报告](tasks/T{index:02}/report.md) · [逐项表](tasks/T{index:02}/coverage.csv) · [问题](tasks/T{index:02}/issues.md) · [存疑](tasks/T{index:02}/questions.md) |" for index in range(13))
    leading = "\n".join(f"- [{row['source_ids'].split(';')[0]} {row['title']}](issues.md#{row['issue_id'].lower()})。" for row in issues[:9])
    readme = f'''# 全战斗规则审计

本轮只检查、保存证据和列出问题。业务代码、规则、现有测试、生成产品和原数据库均未修改；没有代用户裁决含糊规则。确认问题共 **{len(issues)} 组**（P1 {validation['issue_severity']['P1']}、P2 {validation['issue_severity']['P2']}、P3 {validation['issue_severity']['P3']}），去重后的存疑/受阻/待证议题 **{len(questions)} 组**。明细分别见 [issues.md](issues.md)、[questions.md](questions.md)。

审计建账、12模块静态审阅、必要反例和交付核验已完成。**完整行为正确性尚未证明**：每个检查单位有结论不代表每条路径都执行过，未验证的条件和组合保留明确待证项。通过只适用于行内范围，没有证据不计通过。

## 基线与范围

- 目录创建时 HEAD 为 `1bcaab0348aa52e328e3b48523b080b964a5ff2d`。用户在预检阶段提交已有改动后，正式枚举于 `{baseline['created']}` 冻结 HEAD **`{baseline['head']}`**。目录保留原短码；不是基于旧提交回退审计。见 [baseline.json](baseline.json)、[assignments.md](assignments.md)。
- 初始119个源/规则/资料文件，后补30个JSON，共 **149 个唯一主责文件**。末次 SHA-256 **149/149 相同**，无需因审计期间内容变化重跑。含625形态、580技能、242特性、18属性、57规则记录及所有纳入的规则文档。详见 [baseline_files_final.csv](baseline_files_final.csv)。
- 原库 `data/nrc_wiki.db`：SHA-256 `f133f6a9b4f24f348cf1cbe0994e0c444b0eba62a1ad7378d37009a21ad13cd6`；SQLite `user_version=3`、`schema_version=60`、`quick_check=ok`、外键检查为空。规范/staging数据版本与9类提交记录见 [T01证据](tasks/T01/probe_output.json)。数据库仅以 `mode=ro` 打开；写入型边界在内存数据库验证。
- 纳入规则核心、效果生成链、战斗相关数据和采集转换、多回合平台、双人房间、HTTP/网页、现有测试和人工1002/1007。排除AI训练、废弃OCR及旧入口、旧审计结论；历史脚本与手记只作线索。
- 保留用户原有未跟踪 `tests/playwright_ui_changes.js`、`tests/test_compound_status.py`。最终 git 状态仅本审计目录及这两个原文件，无业务差异；见 [validation.json](validation.json)。

## 覆盖统计与读法

[inventory.csv](inventory.csv) 和 [coverage.csv](coverage.csv) 一一对应 **{len(inventory):,}** 个唯一ID，结论记录率100%，缺失0、文件归属冲突0。[id_aliases.csv](id_aliases.csv) 为原枚举同行三元分支的46个ID消歧保留列位置；[branch_inventory_addendum.csv](branch_inventory_addendum.csv) 另补2456个Python短路/推导式路径，全部作为实现待证实列入，没有借父函数通过推为分支通过。

| 结论 | 检查单位数 |
|---|---:|
{table}

“通过”占记录的 **{statistics['limited_pass_percent']:.2f}%**，这是混合检查单位的有限证据比例，**不是战斗正确率**。其中6156项是属性矩阵；625形态通过只证明数据/关联一致；1208项语义样本、222枚举等各有限定范围。确认缺陷的行数也不是缺陷数，同根反例按108组去重。373条未实现记录包含对象、子句、分支，不等于373种机制；4条未上线记录只对应2个明确未上线共鸣。149条受阻主要为采集外部故障分支及人工初始数据缺失，具体原因与后续步骤在行内和questions中。

| 独立统计口径 | 结果 |
|---|---|
| 技能580对象总体 | 290确认至少一处差异；290规则存疑；完整通过0 |
| 特性242对象总体 | 74确认至少一处差异；98规则存疑；70未实现；完整通过0 |
| 配置局部检查 | 原149项局部通过保留，协同后另3项局部通过；不覆盖共享时序/边界。配置、执行、总体结论分列 |
| 57条规则记录总体 | 3通过、27确认缺陷、3未实现、24规则存疑 |
| Python显式控制方向 | 5076项：472有限通过、518关联确认缺陷、3946待证、140受阻 |
| Python短路/推导式路径 | 2456项，逐条件列所需输入和实现位置；未单独验证，全部待证 |
| JavaScript控制方向 | 1310项已枚举/审阅；未逐方向取得独立输入，全部待证 |
| 数据记录逐项检查 | 另表78,224行，包括关系/分布/进化/资源；不叠加主表分母 |

逐名技能、特性终表：[final_object_review.csv](tasks/T06/final_object_review.csv)。T06原始冻结检查点仍保留，最终应读取 [final_addendum_report.md](tasks/T06/final_addendum_report.md)、[coverage_addendum.csv](tasks/T06/coverage_addendum.csv)，旧“317待handler”已经收口为82确认、235待证，未继续作为等待协同阻塞。独立子句不继承对象整体错误；新增321个精确特性子句分别结论。来源/实现/对象/方法/证据/可达性在主表，具体下一输入在对象终表及分支补表；[statistics.json](statistics.json) 提供机器可读统计。

## 已执行的验证

- 现有pytest **19/19通过**，耗时8.37秒。重新查看预期来源，只当回归证据，不以测试结果证明规则。见 [pytest.log](tasks/T00/pytest.log)、[pytest.xml](tasks/T00/pytest.xml)。
- 单/双系克制6156项全部符合独立文档矩阵；六维625×30×6的112500标量以IV0隔离倍数歧义，独立Float32计算发现12325不符。见 [T03](tasks/T03/report.md)。
- 1007双提交顺序各回放11回合，68项查询只读/幂等/过期检查，固定seed事件相同；独立有理数核算11个显式面板伤害样本全匹配。人工手记124与独立推导123等差异保留存疑，不拿旧结果做权威。1002及1007最终补位缺输入，不宣称完整重放。见 [T00](tasks/T00/report.md)。
- 50回合MP/存活/HP/能量四种明确胜者均未终结；多重减伤和最低伤害另有独立有理数反例。同速/入场/补位/全局RNG，复制、状态、特殊系统和完整执行链的反例分别保存在各任务输入/输出，未把synthetic原语输入说成当前配置必达。
- CSV/DB逐字段及顺序一致，9类JSON/staging/提交快照一致，全部3364资源存在且已存哈希匹配；262进化边、44缺失名称对应2564条关系、旧XLSX版本冲突另列问项。见 [T01](tasks/T01/report.md)、[data_record_checks.csv](tasks/T01/data_record_checks.csv)。
- 前端用已安装Node Playwright，显式 `channel: 'chrome'`，Chrome153，一个新浏览器中的两个独立context；17个HTTP方法成功路径、身份/席位、pending刷新、重复/过期、补位、战报游标、对手弹窗与窄屏均有实际证据。11张截图已查看；并发/异常回滚和pending快照往返见T11。端口8774及浏览器已关闭，无连接用户既有浏览器。见 [T12报告](tasks/T12/report.md)、[截图与关闭证据](tasks/T12/cleanup.json)。

要求的场景逐项映射见 [scenario_matrix.csv](scenario_matrix.csv)（{len(rows)}项），每行分开“实证范围”和“剩余验证”。静态读取、单次中性探针、成功路由覆盖均不等于所有组合已穷举。

## 主要确认问题

{leading}

另有伤害减伤/吸血顺序、状态上限和归属、生成参数/目标/时点丢失、普通脱离、传动/选择/禁足静默缺口、后台事件泄名、双方MP不显示等。按根因和严重度的全部最小输入、预期/实际、影响范围及证据见 [issues.md](issues.md)、[issue_index.csv](issue_index.csv)；跨模块重复合并见 [issue_aliases.csv](issue_aliases.csv)。

70空特性在direct builder正确抛 `UnsupportedMechanicError`，但平台抹特性名后错误放行，两种事实并列。空技能、未知原语/动作、未实现血脉/传动/禁足/选择的静默行为单独记录。内部AttributeError不是正确的Unsupported拒绝；不可达也不代表未上线。

## 存疑、受阻与局限

首批要求的50回合四指标全平/同时终局、秋收草系环境、资质6倍与+8→40冲突、奉献均匀权重暂定均保留。其他如普通离场与自力竭含义、临时技能归属、萌化恢复HP、准备期阵容可见性、契约重抽等均有已有依据、当前行为和确认后验证方式。仅明确写未上线的闪焰爆发、节流术标“未上线”。

需要用户裁决的是规则冲突/缺失；已经有明确原文的实现待证实不转嫁给用户批准。大量静态条件、时间/周末、分段中途切换、共享状态与EOT连锁尚无逐分支独立运行证据，不能给整体通过；按具体条件和对象列下一输入。网络采集没有执行，生产库未写；新环境依赖安装没有实做，缺numpy用隔离导入探针确认。运行环境版本见 [dependency_output.json](tasks/T00/dependency_output.json)，当前FastAPI/uvicorn低于项目声明下限，本轮HTTP结论只针对当前环境。

首次CSV中文终端输出乱码已即时报告，设置显式UTF-8后重读正常，原始文件无损；另有审计脚本输入/路径/等待条件修正，失败尝试保留且不计产品缺陷。见baseline及各任务报告。审计副本生成比较没有覆盖技能生成物。

## 文件入口与复核

| 任务 | 交付入口 |
|---|---|
{task_links}

[assignments.md](assignments.md) 为唯一文件归属；[inventory.csv](inventory.csv) 为对象/子句/实现方向；[coverage.csv](coverage.csv) 为双向关联和证据结论；[scenario_matrix.csv](scenario_matrix.csv) 为必查场景；[validation.json](validation.json) 与 [deliverable_validation.json](deliverable_validation.json) 为最终完整性和哈希核验。

复核命令只写本次审计目录。不要重新执行build_inventory.py覆盖原始基线；如业务内容有变化，应新建审计或明确重核变更项。

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
python docs/battle_audit/{AUDIT.name}/consolidate.py
python docs/battle_audit/{AUDIT.name}/build_questions.py
python docs/battle_audit/{AUDIT.name}/finalize_summary.py
python docs/battle_audit/{AUDIT.name}/verify_deliverables.py
```
'''
    (AUDIT / "README.md").write_text(readme, encoding="utf-8")
    t00 = '''# T00 主协调审计与跨模块证据

唯一主责为权威Markdown规则、现有测试/人工资料、依赖与迁移入口及总台账。各业务文件完整审阅由T01–T12原负责人承担；本任务只跨接口追踪和独立反例，不重新代审整文件。并行初始T04/T06/T07，最多三名GPT-6.1-Sol High子agent，任务换批后归属保持。

规则依据优先data根md、部分规则详解、game_descriptions；技能与特性各自原文用于具名效果。先按所有来源建立台账，再把规则→配置→原语/时点→实际调用→状态/数值→双视角串联。旧测试、旧审计及手记不作为正确性权威。57规则、权威md条款及例外与未上线项的逐行映射在本任务coverage，状态归属、伤害、速度/应对、特殊系统由对应任务协同；反向代码项没有充分依据的保留具体待证。

## 实际运行

1. 现有pytest：19通过/8.37秒，原测试均查看来源；有些期望来自被检查计算器，故只记兼容性。命令与结果在pytest.log/xml。
2. replay_1007.py：审计内新平台，完整1007A/B输入，固定seed，双方先后提交两序各11回合，68只读/幂等/过期检查，状态和事件对比一致。r8/r10真实替补；r11手记目标古拉多不在阵容，不能继续猜测。原始大JSON包含状态/双视角/事件，1007_replay.log为简表。
3. independent_damage.py：显式原始六维，Fraction独立推导STAB、属性、增益及公式，11例相符；没有调用被检查DamageCalculator或克制函数生成答案。这里不证明Float32初始化正确。r3爆裂飞弹独立为123，手记124仍待核，不从旧预期反推规则。
4. cross_module.py：50回合四种场景，每次高优先级平手，仅MP/存活/HP/能量一项决定A胜，均winner=None且turn51，合T04-I03。全平、双方MP0和全倒只存实际，不臆造期望。另用独立有理数证明三段/两类减伤及最低1伤害错误，合T04-I01；当前输入使用模型真实attack/pokemon_types字段，早期探针临时错误不作证据。
5. dependency_probe.py：不卸包，仅在隔离子进程令numpy不存在；平台导入真实失败。项目依赖声明缺numpy为T00-I01。记录当前已装版本，不联网安装或升级；没有把模拟缺包说成真实干净环境安装测试。
6. 收到全部任务后比对动态耗能、特性时点、状态生命周期、copy图、天气技能id、补位暂停/继续、平台事务和可见性。普通脱离随机、入场死亡不扣MP、平台抹空特性、未出场姓名事件泄露等证据按主责合并。自力竭后动作规则不明、同时败北和50全平则保持存疑。

## 台账与复核

consolidate.py按AST列拆原同行ID碰撞，保留original_id及id_aliases；人工1002观察归evidence_clause，不作权威rule_clause。T06旧冻结报告与原coverage不覆盖，最终增补4076行包含822对象总体/配置/执行结论和321精确协同子句。对象某一处错误不扩为所有子句都错。

extend_branch_inventory.py补2456短路/推导式路径，关联父函数已有依据与下一输入，全部待证；这种补枚举不能称已独立行为验证。前端1310分支亦保留待证。每个主表单位有结论，具体未验证范围清楚列出，不宣称机制或组合全部正确。最终统计、场景索引和验收结果以根目录README/statistics/validation为准。

主表问题根因合并T07嵌套SkillEffect→T06、T03冻结致死→T04、T10传动→T07；沙暴凭空伤害→T04，而重复折半独立T08-I02B；毒牙/毒腺已有配置缺陷合T06，虫群自身时点/目标仍由T09保留。issue_aliases和question_aliases保存所有去重关系。T04-I12是待裁决行为，不纳入确认问题数。

T00原子问题T00-I01见issues，其余跨模块发现只协同原根因。questions包含首批4条及人工资料不足；复杂实现待证按各行条件和原文映射，不要求用户批准常规验证。没有依据的结论不记通过。

## 资料、环境与修改边界

初始目录用1bcaab0命名，正式baseline HEAD为a393307。用户在预检阶段提交已有改动，全部149个源码/规则/数据来源最终哈希相同；原2个未跟踪测试保留。全部探针/记录只写本审计目录，库只读，生成产品不覆盖。Python显式UTF8，首次控制台CSV乱码重读已纠正并记录，未损坏文件；工具查询误用不存在文件名的报错只是路径错误，没有用于判定。

T12使用Node Playwright channel=chrome独立2context并已关闭，11张图由负责人查看；T00另查看正常共鸣与replacement全屏，确认MP缺失显示证据。没有computer-use。XLSX由T01按电子表格技能只读OpenXML核对，无artifact_tool时采用标准库，无保存/重算。

复现各本目录脚本时设置PYTHONIOENCODING=utf-8、PYTHONUTF8=1、PYTHONDONTWRITEBYTECODE=1。跨模块运行证据：[cross_module_output.json](cross_module_output.json)、[independent_damage.json](independent_damage.json)、[1007_replay.log](1007_replay.log)、[dependency_output.json](dependency_output.json)。本轮没有修复业务，也没有留下服务器或浏览器会话。
'''
    (AUDIT / "tasks/T00/report.md").write_text(t00, encoding="utf-8")
    print(json.dumps(statistics, ensure_ascii=False))


if __name__ == "__main__":
    main()
