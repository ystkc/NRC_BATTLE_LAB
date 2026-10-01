from collector.parsing.skill_description import SkillDescriptionParser


def test_probability_has_trigger_and_not_triggered_branches():
    parsed = SkillDescriptionParser().parse("测试", "有50%概率触发xxx")
    codes = {option.key.code for option in parsed.options}
    assert codes == {"probability:triggered", "probability:not_triggered"}
    assert len(parsed.branches) == 2


def test_gulu_ball_has_five_stable_options():
    parsed = SkillDescriptionParser().parse("测试", "根据精灵居住的咕噜球类型决定增益")
    assert {option.key.value for option in parsed.options} == {"normal", "advanced", "gold", "prism", "type"}


def test_counter_and_attribute_dimensions_are_preserved():
    parsed = SkillDescriptionParser().parse("测试", "应对攻击：根据自身属性决定威力")
    dimensions = {option.key.dimension.value for option in parsed.options}
    assert dimensions == {"counter", "self_attribute"}
    assert len(parsed.branches) == 36


def test_random_devotion_is_a_latent_dimension_not_an_audit_failure():
    parsed = SkillDescriptionParser().parse("虫群智慧", "获得2次随机奉献")
    assert parsed.status.value == "parsed"
    assert {option.key.code for option in parsed.options} == {"devotion_effect:latent"}


def test_refraction_uses_a_runtime_loadout_dimension():
    parsed = SkillDescriptionParser().parse("折射", "造成魔伤，携带其他系别技能会给本技能带来不同效果")
    assert parsed.status.value == "parsed"
    assert {option.key.code for option in parsed.options} == {"refraction:loadout"}


def test_dynamic_skill_replacement_is_runtime_state_not_manual_audit():
    parsed = SkillDescriptionParser().parse("借用", "每回合随机变成己方队伍中其他精灵的技能")
    assert parsed.status.value == "parsed"
    assert parsed.strategy_key == "dynamic_skill_runtime"
    assert parsed.branches == [[]]


def test_water_star_only_has_counter_success_and_failure():
    parsed = SkillDescriptionParser().parse(
        "水星水",
        "造成魔伤，应对状态：本次伤害不受自身属性减益和敌方属性增益影响",
    )
    assert parsed.status.value == "parsed"
    assert {option.key.code for option in parsed.options} == {
        "counter:success",
        "counter:failure",
    }
    assert len(parsed.branches) == 2
