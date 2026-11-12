"""独立推导听桥期望；不导入被审计代码或伤害计算器。"""
import json
from fractions import Fraction
from pathlib import Path

OUT=Path(__file__).resolve().parent
exact=Fraction(80)*Fraction(2)*Fraction(200)*Fraction(37,41)
rounded=(exact.numerator*2+exact.denominator)//(exact.denominator*2)
expected=rounded//100
actual=json.loads((OUT/'probe_output.json').read_text(encoding='utf-8'))['mirror_raw_damage']['actual_damage']
result={'rule_basis':'data/伤害数值计算.md:6-8；data/wiki/skills.csv:96',
        'inputs':{'power':80,'physical_attack':200,'physical_defense':100,'fighting_vs_normal':2,'stab':1,'other_modifiers':1},
        'formula':'floor(half_up(80*2*1*200*37/41)/100)',
        'exact_before_half_up':str(exact),'half_up':rounded,'expected':expected,'actual_from_recorded_probe':actual,
        'source_of_expected':'Fraction精确有理数独立实现；不导入nrc_core，不调用DamageCalculator',
        'prior_calculator_expected':'原probe曾以被审计计算器产生相同288，只可作差异线索；本补件替代其期望依据'}
(OUT/'independent_oracle_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
