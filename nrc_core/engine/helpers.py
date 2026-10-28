"""效果状态修改与战报辅助。"""

from typing import Dict, TYPE_CHECKING
from nrc_core.effect_models import E, Timing, SkillEffect
from nrc_core.rng import choice as rng_choice

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


def _get_ability_name(pokemon: "Pokemon") -> str:
    """从 '特性名:描述' 格式中提取特性名"""
    if ":" in pokemon.ability:
        return pokemon.ability.split(":")[0]
    if "：" in pokemon.ability:
        return pokemon.ability.split("：")[0]
    return pokemon.ability




def _promise_modifiers(pokemon: "Pokemon") -> tuple[tuple[float, ...], tuple[float, ...]]:
    """快照王子诺言监听的增益和减益。"""
    buffs = tuple(getattr(pokemon, attribute, 0) for attribute in (
        "atk_up", "def_up", "spatk_up", "spdef_up", "speed_up", "life_drain_mod",
        "skill_power_bonus", "skill_power_pct_mod", "hit_count_mod", "power_multiplier", "cute_stacks",
    ))
    debuffs = tuple(getattr(pokemon, attribute, 0) for attribute in (
        "atk_down", "def_down", "spatk_down", "spdef_down", "speed_down",
        "poison_stacks", "burn_stacks", "freeze_stacks", "leech_stacks", "electric_stacks",
    ))
    return buffs, debuffs



def _apply_prince_promise(pokemon: "Pokemon", before: tuple, turn: int) -> None:
    """每回合首次获得增益或减益时应用能耗修正。"""
    if _ability_name(pokemon) != "王子的诺言":
        return
    after = _promise_modifiers(pokemon)
    for index, kind, delta in ((0, "buff", -1), (1, "debuff", 1)):
        if not any(current > previous for current, previous in zip(after[index], before[index])):
            continue
        key = f"prince_promise_{kind}_turn"
        if pokemon.ability_state.get(key) == turn:
            continue
        pokemon.ability_state[key] = turn
        previous_costs = [skill.energy_cost for skill in pokemon.skills]
        for skill in pokemon.skills:
            skill.energy_cost = max(0, skill.energy_cost + _adjust_cost_delta(pokemon, delta))
        _record_public_skill_modifier(pokemon, "energy_cost", _adjust_cost_delta(pokemon, delta), previous_costs)



def _find_skill_index(pokemon: "Pokemon", skill: "Skill") -> int:
    """找到技能在精灵技能列表中的索引"""
    for i, s in enumerate(pokemon.skills):
        if s.name == skill.name:
            return i
    return -1



_ABILITY_REPORT_FIELDS = {
    "current_hp": ("生命", False), "energy": ("能量", False),
    "atk_up": ("物攻提升", True), "atk_down": ("物攻降低", True),
    "def_up": ("物防提升", True), "def_down": ("物防降低", True),
    "spatk_up": ("魔攻提升", True), "spatk_down": ("魔攻降低", True),
    "spdef_up": ("魔防提升", True), "spdef_down": ("魔防降低", True),
    "speed_up": ("速度提升", True), "speed_down": ("速度降低", True),
    "poison_stacks": ("中毒", False), "burn_stacks": ("燃烧", False),
    "freeze_stacks": ("冻结", False), "leech_stacks": ("寄生", False),
    "electric_stacks": ("引电", False), "meteor_stacks": ("星陨", False),
    "cute_stacks": ("萌化", False), "skill_cost_mod": ("全部技能能耗", False),
    "skill_power_bonus": ("全部技能威力", False),
    "skill_power_pct_mod": ("全部技能威力", True),
    "hit_count_mod": ("连击", False), "priority_stage": ("先手等级", False),
}



def _ability_report_snapshot(state: "BattleState") -> list:
    """仅记录可解释的数值，不复制特性运行时对象或隐藏技能定义。"""
    return [
        (side, index, pokemon,
         {field: getattr(pokemon, field) for field in _ABILITY_REPORT_FIELDS},
         [(skill.name, skill.energy_cost, skill.power, skill.hit_count, skill.priority_mod) for skill in pokemon.skills],
         dict(pokemon.ability_state.get("public_skill_modifiers", {})),
         [dict(item) for item in pokemon.ability_state.get("_public_skill_modifier_deltas", [])],
         _ability_runtime_snapshot(pokemon))
        for side, members in (("a", state.team_a), ("b", state.team_b))
        for index, pokemon in enumerate(members)
    ]



def _ability_runtime_snapshot(pokemon: "Pokemon") -> dict:
    def value_snapshot(value, depth=0):
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if depth < 4 and isinstance(value, dict):
            return {key: value_snapshot(item, depth + 1) for key, item in value.items()
                    if isinstance(key, (str, int)) and not str(key).startswith("_")}
        if depth < 4 and isinstance(value, (list, tuple)):
            return tuple(value_snapshot(item, depth + 1) for item in value)
        return None

    return {key: value_snapshot(value) for key, value in pokemon.ability_state.items()
            if not key.startswith("_") and key not in {"lab_metadata", "layered_state", "battle_context"}
            and isinstance(value, (str, int, float, bool, dict, list, tuple, type(None)))}



def _report_ability_changes(state: "BattleState", before: list, source: "Pokemon", team: str, timing: Timing) -> None:
    """按实际差值报告，能量达到上限、条件未满足等情况不生成虚假增益。"""
    ability = _get_ability_name(source)
    for side, index, pokemon, old, old_skills, old_public, old_public_deltas, old_runtime in before:
        changes = []
        descriptions = []
        for field, (label, percent) in _ABILITY_REPORT_FIELDS.items():
            value = getattr(pokemon, field)
            delta = value - old[field]
            if abs(delta) < 1e-9:
                continue
            changes.append({"kind": field, "before": old[field], "after": value})
            amount = delta * 100 if percent else delta
            descriptions.append(f"{label}{amount:+g}{'%' if percent else ''}")
        public = pokemon.ability_state.get("public_skill_modifiers", {})
        for field, label in (("energy_cost", "全部技能能耗"), ("power", "全部技能威力"),
                             ("power_pct", "全部技能威力百分比"),
                             ("hit_count", "全部技能连击"), ("priority_mod", "全部技能先手等级")):
            delta = public.get(field, 0) - old_public.get(field, 0)
            if delta:
                changes.append({"kind": "modifier", "name": field,
                                "before": old_public.get(field, 0), "after": public.get(field, 0)})
                descriptions.append(f"{label}{delta:+g}")
        base = {"type": "ability", "team": team, "pokemon": source.name,
                "ability": ability, "timing": timing.name,
                "target_team": side, "target_index": index, "target": pokemon.name}
        runtime = _ability_runtime_snapshot(pokemon)
        if runtime != old_runtime and not changes:
            # 运行时标记的键是内部实现细节，不在战报中暴露英文键或隐私值。
            changes.append({"kind": "ability_runtime", "changed": True})
            descriptions.append("特性效果生效")
        if changes:
            state.turn_report.append({**base, "changes": changes,
                                      "description": f"[{ability}] {pokemon.name}：" + "，".join(descriptions)})
        # 指定技能的变化只发给所属队伍，避免通过特性战报泄露技能配置。
        skill_changes = []
        skill_descriptions = []
        public_deltas = pokemon.ability_state.get("_public_skill_modifier_deltas", [])
        for slot, skill in enumerate(pokemon.skills):
            if slot >= len(old_skills):
                continue
            _, cost, power, hits, priority = old_skills[slot]
            for field, label, previous in (("energy_cost", "能耗", cost), ("power", "威力", power),
                                           ("hit_count", "连击", hits), ("priority_mod", "先手等级", priority)):
                value = getattr(skill, field)
                old_global = old_public_deltas[slot].get(field, 0) if slot < len(old_public_deltas) else 0
                new_global = public_deltas[slot].get(field, 0) if slot < len(public_deltas) else 0
                delta = value - previous - (new_global - old_global)
                if delta:
                    skill_changes.append({"kind": "skill", "slot": slot, "name": skill.name,
                                          "field": field, "before": previous, "after": previous + delta})
                    skill_descriptions.append(f"{skill.name}{label}{delta:+g}")
        if skill_changes:
            state.turn_report.append({**base, "private": True, "visibility": "owner", "owner_team": side,
                                      "changes": skill_changes,
                                      "description": f"[{ability}] {pokemon.name}：" + "，".join(skill_descriptions)})



def _share_heal_to_bench(ctx: "Ctx", heal: int) -> None:
    """系统发育：将回复的HP等量随机分配给场下存活精灵"""
    team_list = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
    current_idx = ctx.state.current_a if ctx.team == "a" else ctx.state.current_b
    bench = [p for i, p in enumerate(team_list) if i != current_idx and not p.is_fainted]
    if bench:
        target = rng_choice(bench)
        target.current_hp = min(target.hp, target.current_hp + heal)



def _share_energy_to_bench(ctx: "Ctx", amount: int) -> None:
    """系统发育：将获得的能量等量随机分配给场下存活精灵"""
    team_list = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
    current_idx = ctx.state.current_a if ctx.team == "a" else ctx.state.current_b
    bench = [p for i, p in enumerate(team_list) if i != current_idx and not p.is_fainted]
    if bench:
        target = rng_choice(bench)
        target.gain_energy(amount)



def _apply_buff(pokemon: "Pokemon", params: Dict) -> None:
    """应用正向属性修改（写入 *_up 字段）"""
    # 营养液泡：获得增益时额外+N层
    extra = pokemon.ability_state.get("buff_extra_layers", 0)
    multiplier = 1 + extra if extra > 0 else 1
    if "atk" in params:
        pokemon.atk_up += params["atk"] * multiplier
    if "def" in params:
        pokemon.def_up += params["def"] * multiplier
    if "spatk" in params:
        pokemon.spatk_up += params["spatk"] * multiplier
    if "spdef" in params:
        pokemon.spdef_up += params["spdef"] * multiplier
    if "speed" in params:
        pokemon.speed_up += params["speed"] * multiplier
    if "all_atk" in params:
        pokemon.atk_up += params["all_atk"] * multiplier
        pokemon.spatk_up += params["all_atk"] * multiplier
    if "all_def" in params:
        pokemon.def_up += params["all_def"] * multiplier
        pokemon.spdef_up += params["all_def"] * multiplier

    # 公平鸽「衡量」镜像：若该精灵的对手身上有 mirror_buff_to 指向该精灵，
    # 则同步把相同 buff 也给对手（不再递归触发）
    mirror_target = pokemon.ability_state.get("mirror_buff_to")
    if mirror_target is not None and not mirror_target.is_fainted:
        # 直接写 *_up 字段，不调用 _apply_buff 避免递归
        mirror_extra = mirror_target.ability_state.get("buff_extra_layers", 0)
        mirror_mult = 1 + mirror_extra if mirror_extra > 0 else 1
        if "atk" in params:       mirror_target.atk_up   += params["atk"]   * mirror_mult
        if "def" in params:       mirror_target.def_up   += params["def"]   * mirror_mult
        if "spatk" in params:     mirror_target.spatk_up += params["spatk"] * mirror_mult
        if "spdef" in params:     mirror_target.spdef_up += params["spdef"] * mirror_mult
        if "speed" in params:     mirror_target.speed_up += params["speed"] * mirror_mult
        if "all_atk" in params:
            mirror_target.atk_up   += params["all_atk"] * mirror_mult
            mirror_target.spatk_up += params["all_atk"] * mirror_mult
        if "all_def" in params:
            mirror_target.def_up   += params["all_def"] * mirror_mult
            mirror_target.spdef_up += params["all_def"] * mirror_mult



def _apply_debuff(pokemon: "Pokemon", params: Dict) -> None:
    """应用负向属性修改（写入 *_down 字段，params 中的值为正数）"""
    if "atk" in params:
        pokemon.atk_down += params["atk"]
    if "def" in params:
        pokemon.def_down += params["def"]
    if "spatk" in params:
        pokemon.spatk_down += params["spatk"]
    if "spdef" in params:
        pokemon.spdef_down += params["spdef"]
    if "speed" in params:
        pokemon.speed_down += params["speed"]
    if "all_atk" in params:
        pokemon.atk_down += params["all_atk"]
        pokemon.spatk_down += params["all_atk"]
    if "all_def" in params:
        pokemon.def_down += params["all_def"]
        pokemon.spdef_down += params["all_def"]



def _clear_buffs(pokemon: "Pokemon") -> None:
    """清除所有正向增益（*_up 字段归零，power_multiplier 重置）"""
    pokemon.atk_up = 0.0
    pokemon.def_up = 0.0
    pokemon.spatk_up = 0.0
    pokemon.spdef_up = 0.0
    pokemon.speed_up = 0.0
    pokemon.power_multiplier = 1.0
    pokemon.life_drain_mod = 0.0
    pokemon.skill_power_bonus = min(0, pokemon.skill_power_bonus)
    pokemon.skill_power_pct_mod = min(0.0, pokemon.skill_power_pct_mod)
    pokemon.skill_cost_mod = max(0, pokemon.skill_cost_mod)
    pokemon.hit_count_mod = min(0, pokemon.hit_count_mod)
    pokemon.priority_stage = min(0, pokemon.priority_stage)
    pokemon.next_attack_power_bonus = 0
    pokemon.next_attack_power_pct = 0.0



def _clear_debuffs(pokemon: "Pokemon") -> None:
    """清除属性负向减益（*_down 字段归零）。
    注意：不清除 poison/burn/leech/freeze 等持久状态——这些只能通过主动清除技能消除。
    """
    pokemon.atk_down = 0.0
    pokemon.def_down = 0.0
    pokemon.spatk_down = 0.0
    pokemon.spdef_down = 0.0
    pokemon.speed_down = 0.0
    # poison_stacks / burn_stacks / freeze_stacks / leech_stacks 不在此清除
    pokemon.priority_stage = max(0, pokemon.priority_stage)



def _ability_name(pokemon: "Pokemon") -> str:
    if not getattr(pokemon, "ability", ""):
        return ""
    return pokemon.ability.split(":")[0].split("（")[0].strip()



def _adjust_cost_delta(pokemon: "Pokemon", delta: int) -> int:
    """能耗增减调整：对流特性反转增减方向，倾轧特性翻倍"""
    if pokemon.ability_state.get("cost_invert"):
        delta = -delta
    if pokemon.ability_state.get("cost_change_double"):
        delta = delta * 2
    return delta



def _iter_flat_tags_static(effects) -> list:
    """从 List[SkillEffect] 或 List[EffectTag] 中提取所有 EffectTag（平铺）。"""
    if not effects:
        return
    for item in effects:
        if isinstance(item, SkillEffect):
            yield from item.effects
        else:
            yield item



def _apply_permanent_mod(user: "Pokemon", skill: "Skill", params: Dict,
                         force: bool = False) -> None:
    """应用永久修改（能耗/威力）。
    per_counter 和 per_position_change 由外部手动调用时传 force=True 绕过 guard。
    """
    target = params.get("target", "")
    delta = params.get("delta", 0)
    trigger = params.get("trigger", "")

    # 非 force 模式下，跳过需要由外部手动触发的类型
    if not force and trigger in ("per_position_change", "per_counter", "per_use"):
        return

    if target == "cost":
        skill.energy_cost = max(0, skill.energy_cost + _adjust_cost_delta(user, delta))
    elif target == "power":
        skill.power = max(0, skill.power + delta)
    elif target == "hit_count":
        skill.hit_count = max(1, skill.hit_count + int(delta))



def _execute_agility_old(pokemon: "Pokemon", enemy: "Pokemon", skill: "Skill") -> None:
    """旧逻辑：执行迅捷技能（没有 effects 字段的技能）"""
    pokemon.energy -= skill.energy_cost
    pokemon.apply_self_buff(skill)
    enemy.apply_enemy_debuff(skill)
    if skill.poison_stacks > 0:
        enemy.poison_stacks += skill.poison_stacks
    if skill.burn_stacks > 0:
        enemy.burn_stacks += skill.burn_stacks
    if skill.leech_stacks > 0:
        enemy.leech_stacks += skill.leech_stacks
    if skill.power > 0 and not enemy.is_fainted:
        from nrc_core.battle import DamageCalculator
        dmg = DamageCalculator.calculate(pokemon, enemy, skill)
        enemy.current_hp -= dmg
        if enemy.current_hp <= 0:
            enemy.current_hp = 0
            from nrc_core.models import StatusType
            enemy.status = StatusType.FAINTED



def _skill_matches_ability_filter(skill: "Skill", params: Dict) -> bool:
    """判断技能是否匹配特性筛选条件。"""
    from nrc_core.models import SkillCategory
    from nrc_core.models import TYPE_NAME_MAP as _TYPE_MAP

    elements = params.get("element")
    if elements:
        if not isinstance(elements, (list, tuple, set)):
            elements = [elements]
        expected = {_TYPE_MAP.get(el) for el in elements}
        if skill.skill_type not in expected:
            return False

    category = params.get("category", "")
    if category == "attack" and skill.category not in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
        return False
    if category == "defense" and skill.category != SkillCategory.DEFENSE:
        return False
    if category == "status" and skill.category != SkillCategory.STATUS:
        return False

    if params.get("attack_only") and skill.power <= 0:
        return False

    if params.get("pure_attack"):
        if skill.power <= 0:
            return False
        # 兼容 SE 和 EffectTag: "纯攻击"= 只有 DAMAGE 效果
        flat_tags = list(_iter_flat_tags_static(skill.effects)) if skill.effects else []
        if not flat_tags or len(flat_tags) != 1 or flat_tags[0].type != E.DAMAGE:
            return False

    if "energy_cost_gt" in params and skill.energy_cost <= params["energy_cost_gt"]:
        return False
    if "energy_cost_ge" in params and skill.energy_cost < params["energy_cost_ge"]:
        return False
    if "energy_cost_lt" in params and skill.energy_cost >= params["energy_cost_lt"]:
        return False
    if "energy_cost_le" in params and skill.energy_cost > params["energy_cost_le"]:
        return False
    if "energy_cost_eq" in params and skill.energy_cost != params["energy_cost_eq"]:
        return False

    return True



def _apply_matching_skill_mods(pokemon: "Pokemon", enemy: "Pokemon", params: Dict) -> None:
    """对匹配的携带技能应用持久修改。"""
    count_source = params.get("count_source", "")
    count = 1
    if count_source == "self_element":
        from nrc_core.models import TYPE_NAME_MAP as _TYPE_MAP
        elements = params.get("count_element", params.get("element", []))
        if not isinstance(elements, (list, tuple, set)):
            elements = [elements]
        count_types = {_TYPE_MAP.get(el) for el in elements}
        count = sum(1 for s in pokemon.skills if s.skill_type in count_types)
    elif count_source == "enemy_energy_sum":
        count = sum(max(0, s.energy_cost) for s in enemy.skills)

    power_pct = float(params.get("power_pct", 0.0)) * count
    power_bonus = int(params.get("power_bonus", 0)) * count
    hit_count_bonus = int(params.get("hit_count_bonus", 0)) * count
    grant_agility = bool(params.get("grant_agility", False))
    filter_keys = {"element", "category", "attack_only", "pure_attack", "energy_cost_gt",
                   "energy_cost_ge", "energy_cost_lt", "energy_cost_le", "energy_cost_eq"}
    global_scope = not any(params.get(key) for key in filter_keys if not key.startswith("energy_cost_")) and not any(key in params for key in filter_keys if key.startswith("energy_cost_"))
    before_power = [s.power for s in pokemon.skills]
    before_hits = [s.hit_count for s in pokemon.skills]

    for s in pokemon.skills:
        if not _skill_matches_ability_filter(s, params):
            continue

        if power_pct or power_bonus:
            base_power = getattr(s, "_ability_base_power", s.power)
            setattr(s, "_ability_base_power", base_power)
            s.power = max(0, int(base_power * (1.0 + power_pct)) + power_bonus)

        if hit_count_bonus:
            s.hit_count = max(1, s.hit_count + hit_count_bonus)

        if grant_agility:
            s.agility = True
    if global_scope:
        previous = pokemon.ability_state.get("_global_matching_power", {})
        if power_pct or power_bonus:
            _record_public_skill_modifier(pokemon, "power", power_pct * 100 - previous.get("pct", 0), before_power, "power_pct")
            public = pokemon.ability_state.setdefault("public_skill_modifiers", {})
            public["power"] = public.get("power", 0) + power_bonus - previous.get("bonus", 0)
            pokemon.ability_state["_global_matching_power"] = {"pct": power_pct * 100, "bonus": power_bonus}
        if hit_count_bonus:
            _record_public_skill_modifier(pokemon, "hit_count", hit_count_bonus, before_hits)



def _record_public_skill_modifier(pokemon: "Pokemon", field: str, delta: float,
                                  before: list, public_field: str | None = None) -> None:
    """记录已知全技能来源；逐槽实际变化仅供可见性层扣除，禁止公开。"""
    public = pokemon.ability_state.setdefault("public_skill_modifiers", {})
    public_field = public_field or field
    public[public_field] = public.get(public_field, 0) + delta
    private = pokemon.ability_state.setdefault("_public_skill_modifier_deltas", [])
    while len(private) < len(pokemon.skills):
        private.append({})
    for index, skill in enumerate(pokemon.skills):
        actual = getattr(skill, field, 0) - before[index]
        private[index][field] = private[index].get(field, 0) + actual



