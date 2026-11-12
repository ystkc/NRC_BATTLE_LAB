"""汇总规则疑问和未证分支，明确下一步而不替用户裁决。"""

import csv
import re
from collections import Counter
from pathlib import Path

AUDIT = Path(__file__).resolve().parent


def main():
    """保留任务原文并合并相同疑问。"""
    records = {}
    for path in sorted((AUDIT / "tasks").glob("T*/questions.md")):
        text = path.read_text(encoding="utf-8")
        headers = list(re.finditer(r"^## (.+)$", text, flags=re.M))
        for index, header in enumerate(headers):
            identity = re.search(r"(?:T\d\d-)?Q\d\d", header.group(1))
            if identity is None:
                continue
            key = identity.group()
            if not key.startswith("T"):
                key = f"{path.parent.name}-{key}"
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
            title = re.sub(r"^(?:T\d\d-)?Q\d\d[：:　 ]*", "", header.group(1))
            records[key] = {"source_id": key, "task": path.parent.name, "title": title, "body": text[header.end():end].strip(), "source": path.relative_to(AUDIT).as_posix(), "related": []}
    records["T00-Q06"] = {"source_id": "T00-Q06", "task": "T00", "title": "复杂条件的实现待证实与缺少定向输入", "source": "coverage.csv", "related": [], "body": "具体问题：原始AST和JS已全文审阅，但许多条件真假、短路、循环退出与异常分支没有独立规则预期和实际输入，不能把静态阅读记为行为通过。每个条件的位置、文本、对象、已有证据与可达性见coverage.csv，T06最终对象表进一步逐名列出了时点/filter/params和待测输入。已有依据：当前规则及技能/特性原文，代码实现不能自证正确。需要补充的是定向验证输入与独立预期；仅原文确有歧义才需用户裁决，不要求用户批准常规验证。当前行为和影响：已实测部分见各probe，未覆盖方向不猜测，其影响对象由inventory的parent_id与objects定位。确认后验证：按每行条件构造真/假、阈值前/恰等/后、异常/正常和共享阶段组合，保存状态与事件；只把有明确预期且实际相符的方向转通过。此次完成了检查记录与现有必要复现，没有穷举所有机制组合。"}
    merges = {"T04-Q01": "T00-Q01", "T04-Q02": "T00-Q01", "T06-Q03": "T00-Q02", "T03-Q01": "T00-Q03", "T04-Q03": "T03-Q04", "T12-Q01": "T11-Q01"}
    aliases = []
    for secondary, primary in merges.items():
        if secondary in records:
            records[primary]["related"].append(records.pop(secondary))
            aliases.append({"source_id": secondary, "primary_id": primary, "reason": "同一规则缺口合并；各任务当前行为和影响保留原文"})
    resolved = records.pop("T03-Q02", None)
    if resolved:
        aliases.append({"source_id": "T03-Q02", "primary_id": "T02-I02", "reason": "六项正资质经正式build放行已确证，不再计未决疑问；辅助函数职责只是协议分工"})
    output = ["# 规则存疑、实现待证实与检查受阻", "", "只把需要解释的规则交给用户裁决。原文已经明确但实现不符的部分已移入issues；等待另一任务的旧检查点已用最终协同结果收口。静态审阅没有独立输入的方向仍保留‘实现待证实’，不计通过。", "", "首批四项均保留：50回合四指标全平/同时终局、秋收草系环境、资质倍数冲突、奉献暂定均匀权重。", ""]
    index = []
    for number, key in enumerate(sorted(records), 1):
        row = records[key]
        question_id = f"QUE-{number:03}"
        category = "检查受阻" if key in {"T01-Q04", "T00-Q05"} else "实现待证实" if key in {"T00-Q06", "T04-Q08", "T11-Q02"} else "暂定规则" if key == "T00-Q04" else "规则/协议存疑"
        ids = ";".join([key] + [related["source_id"] for related in row["related"]])
        index.append({"question_id": question_id, "category": category, "primary_task": row["task"], "source_ids": ids, "title": row["title"], "evidence": row["source"]})
        output += [f"## {question_id} · {row['title']}", "", f"类别：{category}；主责{row['task']}；原编号{key}。[完整任务记录]({row['source']})。", ""]
        body = re.sub(r"\]\((?!https?://|#|[A-Za-z]:)([^)]+)\)", lambda match: f"](tasks/{row['task']}/{match.group(1)})", row["body"])
        output += [body, ""]
        for related in row["related"]:
            output += [f"协同：[{related['source_id']} {related['title']}]({related['source']})，已有事实、受影响接口和后续验证以该记录补充，不重复计算疑问。", ""]
    output += ["## 明确未上线，单列两种共鸣", "", "闪焰爆发、节流术分别见data/部分规则详解/共鸣魔法.md:44、48。只有这两种有明确‘尚未上线’依据；秋收、没有配置的handler或不可达分支不依此归类。主表有两条声明与两个对象记录，代表两个机制，不是四个机制。", "", "## 已由协同确认的旧存疑", "", "T03-Q02的六项资质是否进入正式构建已由T02-I02实测确认缺陷；保留原记录便于追溯，但不再要求用户解释是否允许六项。T07关于萌化的增减益分类由GAME_RULE8明确，反向触发已记T07-I10；清除减益遗漏亦已记T07-I09。", "", "所有对应对象/条件的细节见[coverage.csv](coverage.csv)、[最终技能特性总表](tasks/T06/final_object_review.csv)。合并别名见[question_aliases.csv](question_aliases.csv)。", ""]
    (AUDIT / "questions.md").write_text("\n".join(output), encoding="utf-8")
    for filename, fields, rows in (("question_index.csv", ["question_id", "category", "primary_task", "source_ids", "title", "evidence"], index), ("question_aliases.csv", ["source_id", "primary_id", "reason"], aliases)):
        with (AUDIT / filename).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    print({"question_groups": len(index), "categories": dict(Counter(row['category'] for row in index))})


if __name__ == "__main__":
    main()
