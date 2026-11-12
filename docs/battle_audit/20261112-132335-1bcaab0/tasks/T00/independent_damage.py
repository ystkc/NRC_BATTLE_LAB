"""只用规则公式和显式输入核算人工对局伤害，避免实现自证。"""

from fractions import Fraction
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


def damage(power, attack, defense, stab=1, effectiveness=1, attack_up=0, defense_up=0, defense_down=0):
    """按伤害文档先半入后除防御下取整，所有运算使用有理数。"""
    effective_power = Fraction(power) * Fraction(stab) * Fraction(effectiveness)
    effective_power *= (1 + Fraction(attack_up) + Fraction(defense_down)) / (1 + Fraction(defense_up))
    intermediate = math.floor(effective_power * attack * 37 / 41 + Fraction(1, 2))
    return max(math.floor(Fraction(intermediate, defense)), 1)


def main():
    """基础六维当显式输入；其正确性由T03独立审计，不混同为数值已通过。"""
    cases = [
        (1, "火焰箭", dict(power=80, attack=181, defense=136, effectiveness=2), "火焰箭80；火克冰、萌中性；尚无伙伴"),
        (2, "闪光冲击", dict(power=100, attack=181, defense=152, stab=Fraction(5, 4), effectiveness=Fraction(1, 2), attack_up=Fraction(1, 5)), "光本系；冰抵抗；伙伴1层"),
        (3, "火焰箭", dict(power=80, attack=181, defense=152, effectiveness=2, attack_up=Fraction(1, 5)), "NRC火对火中性、克冰；伙伴1层"),
        (3, "爆裂飞弹", dict(power=160, attack=156, defense=163, stab=Fraction(5, 4), defense_up=Fraction(2, 5)), "火本系；A先攻击获得伙伴第2层后承伤"),
        (4, "火焰箭", dict(power=80, attack=181, defense=191, attack_up=Fraction(2, 5)), "火对冰地一克一抵；伙伴2层"),
        (6, "棘突", dict(power=100, attack=181, defense=171, effectiveness=2, attack_up=Fraction(2, 5)), "草克地；冰中性；伙伴2层"),
        (6, "冰雹", dict(power=105, attack=191, defense=175, stab=Fraction(5, 4), defense_up=Fraction(3, 5)), "冰本系；A先获得伙伴第3层；未应对攻击"),
        (7, "棘突", dict(power=100, attack=181, defense=163, effectiveness=2, attack_up=Fraction(3, 5)), "草克光；伙伴3层"),
        (8, "超导", dict(power=90, attack=174, defense=163, defense_up=Fraction(4, 5), defense_down=1), "电非本系且血脉恶不改变本系；伙伴4层与霜冻魔防-100%并存"),
        (9, "针刺射击", dict(power=80, attack=178, defense=177, stab=Fraction(5, 4)), "草本系；对恶冰中性"),
        (10, "暗突袭", dict(power=140, attack=234, defense=152, stab=Fraction(5, 4), effectiveness=2), "应对状态先将基础70翻倍；恶本系且克毒"),
    ]
    replay = json.loads((OUT / "1007_replay.json").read_text(encoding="utf-8"))
    results = []
    for turn, name, inputs, reason in cases:
        events = replay["runs"][0]["records"][turn - 1]["result"]["result"]["events"]
        actual = next(event["final_damage"] for event in events if event.get("type") == "skill" and event.get("skill") == name)
        expected = damage(**inputs)
        results.append({"turn": turn, "skill": name, "input": {key: str(value) for key, value in inputs.items()}, "reason": reason,
                        "expected": expected, "actual": actual, "match": actual == expected})
    result = {"rule_basis": ["data/伤害数值计算.md", "data/属性克制表.md", "data/部分规则详解/最好的伙伴.md", "data/wiki/skills.csv"],
              "limitation": "六维作为显式输入隔离伤害规则。资质倍数冲突和Float32精度另由T03审计，不证明初始六维正确。没有调用DamageCalculator或属性克制函数生成答案。", "cases": results}
    (OUT / "independent_damage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"total": len(results), "matched": sum(row["match"] for row in results), "differences": [row for row in results if not row["match"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
