"""技能伤害、状态与天气效果处理器。"""

from typing import TYPE_CHECKING
from nrc_core.effect_models import E, EffectTag, Timing, SkillTiming, SkillEffect
from nrc_core.engine.context import (
    Ctx,
)
from nrc_core.engine.filters import (
    _check_runtime_condition,
)
from nrc_core.engine.helpers import (
    _adjust_cost_delta,
    _apply_buff,
    _apply_debuff,
    _apply_permanent_mod,
    _clear_buffs,
    _clear_debuffs,
    _find_skill_index,
    _record_public_skill_modifier,
    _share_energy_to_bench,
    _share_heal_to_bench,
)

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


def _h_damage(tag: EffectTag, ctx: Ctx) -> None:
    from nrc_core.battle import DamageCalculator, get_mark_damage_modifiers
    skill = ctx.skill

    # ── 惊吓: 能量=0的攻击者无法对目标造伤 ──
    if ctx.target.ability_state.get("immune_zero_energy_attacker") and ctx.user.energy == 0:
        ctx.result["damage"] = ctx.result.get("damage", 0)
        return

    # ── 逐魂鸟: 能耗≤N的攻击技能无法对目标造伤 ──
    immune_cost_threshold = ctx.target.ability_state.get("immune_low_cost_attack")
    if immune_cost_threshold is not None:
        from nrc_core.models import SkillCategory
        if skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL):
            actual_cost = getattr(skill, "_last_actual_cost", skill.energy_cost)
            if actual_cost <= immune_cost_threshold:
                ctx.result["damage"] = ctx.result.get("damage", 0)
                return

    # ── 印记伤害修正 ──
    mark_mods = get_mark_damage_modifiers(ctx.state, ctx.team, ctx.is_first, skill)
    # 使用独立上下文，避免多段 DAMAGE 重复累积临时威力修正。
    attack_context = {"skill": skill, "is_first": ctx.is_first}
    ctx.execute_ability(
        ctx.state, ctx.user, ctx.target, Timing.BEFORE_ATTACK,
        ctx.user.ability_effects, ctx.team, attack_context,
    )

    power = (
        skill.power
        + ctx.user.skill_power_bonus
        + ctx.user.next_attack_power_bonus
        + ctx.result.get("_power_bonus", 0)
        + attack_context.get("_power_bonus", 0)
        + mark_mods["power_bonus"]
    )
    power_mult = (
        1.0
        + ctx.user.skill_power_pct_mod
        + ctx.user.next_attack_power_pct
        + (ctx.result.get("_power_mult", 1.0) - 1.0)
        + (attack_context.get("_power_mult", 1.0) - 1.0)
        + (mark_mods["power_mult"] - 1.0)
    )
    if power_mult != 1.0:
        power = int(power * power_mult)
    if power > 0 and not ctx.target.is_fainted:
        weather = getattr(ctx.state, "weather", None)
        hit_count = max(
            1,
            int(
                (skill.hit_count + ctx.user.hit_count_mod + ctx.result.get("_hit_count_bonus", 0))
                * ctx.result.get("_hit_count_mult", 1.0)
            ),
        )

        # ── 侵蚀: 敌方每有1层中毒，连击数+1 (仅攻击技能) ──
        if ctx.user.ability_state.get("hit_count_per_poison"):
            from nrc_core.models import SkillCategory as _SC
            if skill.category in (_SC.PHYSICAL, _SC.MAGICAL) and ctx.target.poison_stacks > 0:
                hit_count += ctx.target.poison_stacks

        # ── 自由飘: 自己每有1层萌化，连击+N (仅攻击技能) ──
        cute_per = ctx.user.ability_state.get("cute_hit_per_stack")
        if cute_per and ctx.user.cute_stacks > 0:
            from nrc_core.models import SkillCategory as _SC2
            if skill.category in (_SC2.PHYSICAL, _SC2.MAGICAL):
                hit_count += ctx.user.cute_stacks * cute_per

        # ── 噼啪！: 入场首次行动使用次数+1 ──
        # ── 无差别过滤: 任一方有此标记则连击数固定为2 ──
        fixed_hit = ctx.user.ability_state.get("fixed_hit_count_all") or ctx.target.ability_state.get("fixed_hit_count_all")
        if fixed_hit:
            hit_count = fixed_hit

        # 龙噬印记的攻击倍率：临时加到 atk_up
        old_atk_up = ctx.user.atk_up
        old_spatk_up = ctx.user.spatk_up
        if mark_mods["atk_mult"] > 1.0:
            extra = mark_mods["atk_mult"] - 1.0
            ctx.user.atk_up += extra
            ctx.user.spatk_up += extra

        dmg = DamageCalculator.calculate(ctx.user, ctx.target, skill,
                                         power_override=power, weather=weather,
                                         hit_count_override=hit_count)
        ctx.result["final_power"] = ctx.user.ability_state.get("_last_damage_details", {}).get("effective_power", power * power_mult)

        # 恢复临时修正
        ctx.user.atk_up = old_atk_up
        ctx.user.spatk_up = old_spatk_up

        ctx.result["damage"] = ctx.result.get("damage", 0) + dmg
        if ctx.user.next_attack_power_bonus or ctx.user.next_attack_power_pct:
            ctx.result["_consume_next_attack_mod"] = True

        # 星陨印记：造成伤害后消耗层数，造成额外魔伤
        meteor_stacks = mark_mods["meteor_mark_stacks"]
        if meteor_stacks > 0 and dmg > 0:
            enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
            for key in list(enemy_marks):
                if key == "meteor_mark" or key.startswith("bard_mark:meteor_mark:"):
                    del enemy_marks[key]
            meteor_power = 30 * meteor_stacks
            # 星陨印记造成魔法伤害（用攻方魔攻 vs 被攻方魔防）
            from nrc_core.models import SkillCategory, Type
            e_spatk = ctx.user.effective_spatk()
            t_spdef = max(1.0, ctx.target.effective_spdef())
            meteor_dmg = max(1, int((e_spatk / t_spdef) * meteor_power * 0.9))
            ctx.target.current_hp -= meteor_dmg
            ctx.result["damage"] = ctx.result.get("damage", 0) + meteor_dmg
            if ctx.target.current_hp <= 0:
                ctx.target.current_hp = 0
                from nrc_core.models import StatusType
                ctx.target.status = StatusType.FAINTED



def _h_self_buff(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    _apply_buff(ctx.user, tag.params)



def _h_self_debuff(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    _apply_debuff(ctx.user, tag.params)



def _h_enemy_debuff(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    if tag.params.get("invert"):
        _apply_buff(ctx.target, {k: abs(v) for k, v in tag.params.items() if k != "invert"})
    else:
        _apply_debuff(ctx.target, tag.params)



def _h_heal_hp(tag: EffectTag, ctx: Ctx) -> None:
    pct = tag.params.get("pct", 0)
    # 条件缩放：per_enemy_poison / per_enemy_burn — 按敌方层数乘以基础比例
    per = tag.params.get("per", "")
    if per == "enemy_poison":
        pct *= ctx.target.poison_stacks
    elif per == "enemy_burn":
        pct *= ctx.target.burn_stacks
    heal = int(ctx.user.hp * pct)
    if heal > 0:
        # 伪造账单：回复变为失去（anti_heal_multiplier 由对手特性设置到本精灵上）
        anti = ctx.user.ability_state.get("anti_heal_multiplier", 0)
        if anti:
            ctx.user.current_hp = max(0, ctx.user.current_hp - heal)
        else:
            ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)
            # 系统发育：将等量回复随机分配给场下精灵
            if ctx.user.ability_state.get("share_gains"):
                _share_heal_to_bench(ctx, heal)



def _h_heal_energy(tag: EffectTag, ctx: Ctx) -> None:
    if "set_to" in tag.params:
        ctx.user.energy = tag.params["set_to"]
    else:
        amount = tag.params.get("amount", 1)
        ctx.user.gain_energy(amount)
        # 系统发育：将等量能量随机分配给场下精灵
        if ctx.user.ability_state.get("share_gains"):
            _share_energy_to_bench(ctx, amount)



def _h_self_ko(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_self_ko"] = True



def _h_energy_all_in(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_ALL_IN: 消耗所有能量，威力按消耗量缩放（魔能爆）。
    在 PRE_USE 阶段执行：把当前能量换算成威力加成，然后清空能量。
    """
    current_energy = ctx.user.energy
    power_per_energy = tag.params.get("power_per_energy", 30)
    if current_energy > 0:
        ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + current_energy * power_per_energy
        ctx.user.energy = 0



def _h_reset_skill_cost(tag: EffectTag, ctx: Ctx) -> None:
    ctx.skill.energy_cost = getattr(ctx.skill, "_base_energy_cost", ctx.skill.energy_cost)
    slot = _find_skill_index(ctx.user, ctx.skill)
    private = ctx.user.ability_state.get("_public_skill_modifier_deltas", [])
    if 0 <= slot < len(private):
        private[slot].pop("energy_cost", None)



def _h_steal_energy(tag: EffectTag, ctx: Ctx) -> None:
    amt = tag.params.get("amount", 1)
    ctx.user.gain_energy(amt)
    ctx.target.energy = max(0, ctx.target.energy - amt)



def _h_enemy_lose_energy(tag: EffectTag, ctx: Ctx) -> None:
    tgt = tag.params.get("target", "enemy")
    if tgt == "self_mp":
        # 飓风特性: 扣己方MP
        if ctx.team == "a":
            ctx.state.mp_a -= tag.params.get("amount", 1)
        else:
            ctx.state.mp_b -= tag.params.get("amount", 1)
    elif tgt in ("enemy_new", "enemy"):
        ctx.target.energy = max(0, ctx.target.energy - tag.params.get("amount", 1))
    else:
        ctx.target.energy = max(0, ctx.target.energy - tag.params.get("amount", 1))



def _h_life_drain(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_life_drain_pct"] = ctx.result.get("_life_drain_pct", 0.0) + tag.params.get("pct", 0)



def _h_grant_life_drain(tag: EffectTag, ctx: Ctx) -> None:
    ctx.user.life_drain_mod += tag.params.get("pct", 0)



def _h_poison(tag: EffectTag, ctx: Ctx) -> None:
    from nrc_core.models import has_type, Type
    if has_type(ctx.target, Type.POISON) or ctx.target.ability_state.get("poison_immune"):
        return
    stacks = tag.params.get("stacks", 1)
    # 特殊: stacks_per_poison_skill（溶解扩散特性）
    if tag.params.get("stacks_per_poison_skill"):
        ability_state = getattr(ctx.user, "ability_state", {})
        stacks = ability_state.get("poison_skill_count", 0)
    # 特殊: stacks_per_mark（扩散侵蚀特性）
    if tag.params.get("stacks_per_mark"):
        mult = tag.params["stacks_per_mark"]
        enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
        mark_stacks = _mark_stacks(enemy_marks, "poison_mark")
        stacks = mark_stacks * mult
    # 目标选择
    tgt = tag.params.get("target", "enemy")
    if tgt in ("enemy", "enemy_new"):
        ctx.target.poison_stacks += stacks
    else:
        ctx.user.poison_stacks += stacks



def _h_burn(tag: EffectTag, ctx: Ctx) -> None:
    from nrc_core.models import has_type, Type
    if has_type(ctx.target, Type.FIRE) or ctx.target.ability_state.get("burn_immune"):
        return
    ctx.target.burn_stacks += tag.params.get("stacks", 1)



def _h_freeze(tag: EffectTag, ctx: Ctx) -> None:
    from nrc_core.models import add_freeze_stacks, has_type, Type
    if has_type(ctx.target, Type.ICE) or ctx.target.ability_state.get("freeze_immune"):
        return
    add_freeze_stacks(ctx.target, tag.params.get("stacks", 1), ctx.user,
                      state=ctx.state, team=ctx.team)



def _h_electric_lure(tag: EffectTag, ctx: Ctx) -> None:
    from nrc_core.models import add_electric_stacks
    add_electric_stacks(ctx.target, tag.params.get("stacks", 1))



def _h_leech(tag: EffectTag, ctx: Ctx) -> None:
    from nrc_core.models import has_type, Type
    if has_type(ctx.target, Type.GRASS) or ctx.target.ability_state.get("leech_immune"):
        return
    ctx.target.leech_stacks += tag.params.get("stacks", 1)



def _h_meteor(tag: EffectTag, ctx: Ctx) -> None:
    ctx.target.meteor_stacks += tag.params.get("stacks", 1)
    if ctx.target.meteor_countdown <= 0:
        ctx.target.meteor_countdown = 3



def _h_poison_mark(tag: EffectTag, ctx: Ctx) -> None:
    marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    marks["poison_mark"] = marks.get("poison_mark", 0) + tag.params.get("stacks", 1)



def _h_moisture_mark(tag: EffectTag, ctx: Ctx) -> None:
    tgt = tag.params.get("target", "enemy")
    if tgt == "self":
        marks = ctx.state.marks_a if ctx.team == "a" else ctx.state.marks_b
    else:
        marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    stacks = tag.params.get("stacks", 1)
    marks["moisture_mark"] = marks.get("moisture_mark", 0) + stacks
    # 湿润印记立即生效：释放后当回合就减能耗，不等下回合
    team_id = ctx.team if tgt == "self" else ("b" if ctx.team == "a" else "a")
    team_list = ctx.state.team_a if team_id == "a" else ctx.state.team_b
    for p in team_list:
        previous_costs = [s.energy_cost for s in p.skills]
        for s in p.skills:
            delta = -stacks
            if p.ability_state.get("cost_invert"):
                delta = -delta
            s.energy_cost = max(0, s.energy_cost + delta)
        _record_public_skill_modifier(p, "energy_cost", stacks if p.ability_state.get("cost_invert") else -stacks, previous_costs)
    marks["moisture_mark"] = 0  # 已消耗



def _h_mark_generic(tag: EffectTag, ctx: Ctx, mark_key: str) -> None:
    """通用印记 handler：根据 target 参数放入对应队伍的 marks dict。
    
    同一阵营（己方/敌方 marks dict）同时仅能存在1种正面印记和1种负面印记。
    新印记会覆盖同类（正面/负面）中的旧印记。
    """
    tgt = tag.params.get("target", "enemy")
    if tgt == "self":
        marks = ctx.state.marks_a if ctx.team == "a" else ctx.state.marks_b
    else:
        marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    
    # 吟游之弦拥有按来源隔离的专属槽，不占用普通正/负面印记槽。
    if ctx.user.ability_state.get("mark_stack_additive"):
        owned_key = f"bard_mark:{mark_key}:{ctx.user.name}"
        marks[owned_key] = marks.get(owned_key, 0) + tag.params.get("stacks", 1)
        return

    # 同类印记覆盖：只清除普通槽，不清除吟游之弦专属槽。
    if mark_key in POSITIVE_MARKS:
        for existing_key in list(marks.keys()):
            if existing_key in POSITIVE_MARKS and existing_key != mark_key:
                del marks[existing_key]
    elif mark_key in NEGATIVE_MARKS:
        for existing_key in list(marks.keys()):
            if existing_key in NEGATIVE_MARKS and existing_key != mark_key:
                del marks[existing_key]
    
    marks[mark_key] = marks.get(mark_key, 0) + tag.params.get("stacks", 1)



def _mark_stacks(marks, mark_key):
    from nrc_core.models import get_mark_stacks
    return get_mark_stacks(marks, mark_key)



POSITIVE_MARKS = {
    "moisture_mark", "dragon_mark", "wind_mark", "charge_mark",
    "solar_mark", "attack_mark", "sluggish_mark", "momentum_mark",
}



NEGATIVE_MARKS = {
    "poison_mark", "slow_mark", "spirit_mark", "meteor_mark", "thorn_mark",
}



def _h_dragon_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "dragon_mark")



def _h_wind_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "wind_mark")



def _h_charge_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "charge_mark")



def _h_solar_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "solar_mark")



def _h_attack_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "attack_mark")



def _h_slow_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "slow_mark")



def _h_sluggish_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "sluggish_mark")



def _h_spirit_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "spirit_mark")



def _h_meteor_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "meteor_mark")



def _h_thorn_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "thorn_mark")



def _h_momentum_mark(tag: EffectTag, ctx: Ctx) -> None:
    _h_mark_generic(tag, ctx, "momentum_mark")



def _h_dispel_enemy_marks(tag: EffectTag, ctx: Ctx) -> None:
    """驱散敌方印记。stacks=N 时只驱散 N 层（从最大的印记扣），无 stacks 则全部清除。"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    stacks = tag.params.get("stacks", 0)
    if stacks <= 0:
        enemy_marks.clear()
    else:
        # 驱散 N 层：每次从层数最多的印记扣 1，直到扣完 N 层
        remaining = stacks
        while remaining > 0 and enemy_marks:
            max_key = max(enemy_marks, key=lambda k: enemy_marks[k] if isinstance(enemy_marks[k], (int, float)) else 0)
            if not isinstance(enemy_marks[max_key], (int, float)) or enemy_marks[max_key] <= 0:
                break
            enemy_marks[max_key] -= 1
            if enemy_marks[max_key] <= 0:
                del enemy_marks[max_key]
            remaining -= 1



def _h_convert_marks_to_burn(tag: EffectTag, ctx: Ctx) -> None:
    """炎爆术: 将敌方印记转换为 ratio 倍灼烧层数"""
    ratio = tag.params.get("ratio", 3)
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    if total > 0:
        ctx.target.burn_stacks += int(total * ratio)
        enemy_marks.clear()



def _h_dispel_marks_to_burn(tag: EffectTag, ctx: Ctx) -> None:
    """焚烧烙印: 驱散双方所有印记，每层→N层灼烧"""
    burn_per = tag.params.get("burn_per_mark", 5)
    total = 0
    total += sum(v for v in ctx.state.marks_a.values() if isinstance(v, (int, float)))
    total += sum(v for v in ctx.state.marks_b.values() if isinstance(v, (int, float)))
    ctx.state.marks_a.clear()
    ctx.state.marks_b.clear()
    if total > 0:
        ctx.target.burn_stacks += int(total * burn_per)



def _h_consume_marks_heal(tag: EffectTag, ctx: Ctx) -> None:
    """食腐: 驱散敌方印记，每层回复自己 heal_pct 生命"""
    heal_pct = tag.params.get("heal_pct_per_mark", 0.1)
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    enemy_marks.clear()
    if total > 0:
        heal = int(ctx.user.hp * heal_pct * total)
        anti = ctx.user.ability_state.get("anti_heal_multiplier", 0)
        if anti:
            ctx.user.current_hp = max(0, ctx.user.current_hp - heal)
        else:
            ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)



def _h_marks_to_meteor(tag: EffectTag, ctx: Ctx) -> None:
    """心灵洞悉: 敌方获得星陨，层数=敌方印记总层数"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    if total > 0:
        ctx.target.meteor_stacks += int(total)
        if ctx.target.meteor_countdown <= 0:
            ctx.target.meteor_countdown = 3



def _h_steal_marks(tag: EffectTag, ctx: Ctx) -> None:
    """翅刃应对时: 偷取敌方印记给己方"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    my_marks = ctx.state.marks_a if ctx.team == "a" else ctx.state.marks_b
    for k, v in enemy_marks.items():
        my_marks[k] = my_marks.get(k, 0) + v
    enemy_marks.clear()



def _h_energy_cost_per_enemy_mark(tag: EffectTag, ctx: Ctx) -> None:
    """四维降解: 敌方每层印记能耗-1"""
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    total = sum(v for v in enemy_marks.values() if isinstance(v, (int, float)))
    if total > 0:
        ctx.result["_energy_refund"] = ctx.result.get("_energy_refund", 0) + int(total)



def _h_damage_reduction(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_damage_reduction"] = tag.params.get("pct", 0)
    # 特性场景：减伤信息也存到 ability_damage_reduction
    if "ability_damage_reduction" in ctx.result or ctx.result.get("_is_ability_ctx"):
        ctx.result["ability_damage_reduction"] = tag.params.get("pct", 0)



def _h_force_switch(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["force_switch"] = True



def _h_force_enemy_switch(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["force_enemy_switch"] = True



def _h_agility(tag: EffectTag, ctx: Ctx) -> None:
    pass  # 标记，由 execute_agility_entry 处理



def _h_convert_buff_to_poison(tag: EffectTag, ctx: Ctx) -> None:
    total_buff = 0
    for attr in ["atk_up", "def_up", "spatk_up", "spdef_up", "speed_up"]:
        v = getattr(ctx.target, attr, 0)
        if v > 0:
            total_buff += int(v * 10)
            setattr(ctx.target, attr, 0.0)
    if total_buff > 0:
        ctx.target.poison_stacks += total_buff



def _h_convert_poison_to_mark(tag: EffectTag, ctx: Ctx) -> None:
    on = tag.params.get("on", "")
    ratio = tag.params.get("ratio", 0)
    marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    if on == "kill" and ctx.target.is_fainted:
        stacks = ctx.target.poison_stacks
        marks["poison_mark"] = marks.get("poison_mark", 0) + stacks
        ctx.target.poison_stacks = 0
    elif ratio > 0:
        stacks = ctx.target.poison_stacks
        converted = stacks // ratio
        if converted > 0:
            ctx.target.poison_stacks -= converted * ratio
            marks["poison_mark"] = marks.get("poison_mark", 0) + converted



def _h_dispel_marks(tag: EffectTag, ctx: Ctx) -> None:
    cond = tag.params.get("condition", "")
    if cond == "not_blocked":
        ctx.result["_dispel_if_not_blocked"] = True
    else:
        ctx.state.marks_a.clear()
        ctx.state.marks_b.clear()



def _h_conditional_buff(tag: EffectTag, ctx: Ctx) -> None:
    condition = tag.params.get("condition", "")
    buff = tag.params.get("buff", {})
    if condition == "enemy_switch":
        ctx.result["_conditional_enemy_switch_buff"] = buff
    elif condition == "after_use_hp_gt_half":
        if ctx.user.current_hp > ctx.user.hp / 2:
            ctx.result.setdefault("_post_use_self_buffs", []).append(buff)
    elif condition in ("self_hp_gt", "self_hp_lt", "enemy_hp_gt", "enemy_hp_lt"):
        threshold = float(tag.params.get("threshold", 0))
        source = ctx.user if condition.startswith("self") else ctx.target
        ratio = source.current_hp / max(1, source.hp)
        matched = ratio > threshold if condition.endswith("_gt") else ratio < threshold
        if matched:
            target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
            _apply_buff(target, buff)
    elif condition in ("self_hp_above", "self_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        ratio = start_hp / max(1, ctx.user.hp)
        matched = ratio > threshold if condition == "self_hp_above" else ratio < threshold
        if matched:
            target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
            _apply_buff(target, buff)
    elif condition == "per_enemy_poison":
        stacks = ctx.target.poison_stacks
        if stacks > 0:
            scaled_buff = {k: v * stacks for k, v in buff.items()}
            _apply_buff(ctx.user, scaled_buff)



def _h_energy_cost_dynamic(tag: EffectTag, ctx: Ctx) -> None:
    per = tag.params.get("per", "")
    reduce = tag.params.get("reduce", 0)
    if per == "enemy_poison":
        stacks = ctx.target.poison_stacks
        ctx.result["_energy_refund"] = stacks * reduce



def _h_power_dynamic(tag: EffectTag, ctx: Ctx) -> None:
    condition = tag.params.get("condition", "")
    if condition == "first_strike" and ctx.is_first:
        bonus_pct = tag.params.get("bonus_pct", 0)
        ctx.result["_power_mult"] = ctx.result.get("_power_mult", 1.0) + bonus_pct
    elif condition == "enemy_switch":
        enemy_switched = (
            ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a
        )
        if enemy_switched:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "prev_status":
        if ctx.user.ability_state.get("last_skill_category") == "状态" and ctx.user.ability_state.get("last_skill_turn") == ctx.state.turn - 1:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "prev_counter_success":
        if ctx.user.ability_state.get("last_counter_success_turn") == ctx.state.turn - 1:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "energy_zero_after_use":
        if ctx.user.energy == 0:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "enemy_energy_leq":
        threshold = tag.params.get("threshold", 0)
        if ctx.target.energy <= threshold:
            if "multiplier" in tag.params:
                mult = tag.params.get("multiplier", 1.0)
                ctx.result["_power_mult"] = ctx.result.get("_power_mult", 1.0) * mult
            else:
                ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + tag.params.get("bonus", 0)
    elif condition == "self_missing_hp_step":
        step_pct = float(tag.params.get("step_pct", 0.05))
        bonus_per_step = int(tag.params.get("bonus_per_step", 0))
        if step_pct > 0 and bonus_per_step:
            missing_pct = max(0.0, 1.0 - (ctx.user.current_hp / max(1, ctx.user.hp)))
            steps = int(missing_pct / step_pct)
            if steps > 0:
                ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + steps * bonus_per_step
    elif condition == "energy_cost_above_base":
        base_cost = int(tag.params.get("base_cost", ctx.skill.energy_cost))
        bonus_per_step = int(tag.params.get("bonus_per_step", 0))
        steps = max(0, ctx.skill.energy_cost - base_cost)
        if steps > 0 and bonus_per_step:
            ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + steps * bonus_per_step
    elif condition == "per_poison":
        stacks = ctx.target.poison_stacks
        bonus = tag.params.get("bonus_per_stack", 0) * stacks
        ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + bonus
    elif condition == "counter":
        # 应对时威力倍率（偷袭3倍），在 execute_counter 中处理
        mult = tag.params.get("multiplier", 1.0)
        from nrc_core.battle import DamageCalculator
        new_power = int(ctx.skill.power * mult)
        weather = getattr(ctx.state, "weather", None)
        ctx.result["final_damage"] = DamageCalculator.calculate(
            ctx.user, ctx.target, ctx.skill, power_override=new_power, weather=weather,
        )



def _h_permanent_mod(tag: EffectTag, ctx: Ctx) -> None:
    _apply_permanent_mod(ctx.user, ctx.skill, tag.params)



def _h_skill_mod(tag: EffectTag, ctx: Ctx) -> None:
    if not _check_runtime_condition(tag, ctx):
        return
    target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
    stat = tag.params.get("stat", "")
    value = tag.params.get("value", 0)
    condition = tag.params.get("condition", "")
    if condition == "enemy_switch":
        enemy_switched = (
            ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a
        )
        if not enemy_switched:
            return
    elif condition in ("self_hp_above", "self_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        ratio = start_hp / max(1, ctx.user.hp)
        matched = ratio > threshold if condition == "self_hp_above" else ratio < threshold
        if not matched:
            return
    if stat == "power":
        target.skill_power_bonus += int(value)
    elif stat == "power_pct":
        target.skill_power_pct_mod += value
    elif stat == "cost":
        target.skill_cost_mod += _adjust_cost_delta(target, int(value))
    elif stat == "hit_count":
        target.hit_count_mod += int(value)
    elif stat == "current_hit_count":
        ctx.result["_hit_count_bonus"] = ctx.result.get("_hit_count_bonus", 0) + int(value)
    elif stat == "current_hit_count_mult":
        ctx.result["_hit_count_mult"] = ctx.result.get("_hit_count_mult", 1.0) * float(value)
    elif stat == "priority":
        target.priority_stage += int(value)



def _h_next_attack_mod(tag: EffectTag, ctx: Ctx) -> None:
    ctx.user.next_attack_power_bonus += int(tag.params.get("power_bonus", 0))
    ctx.user.next_attack_power_pct += tag.params.get("power_pct", 0.0)



def _h_cleanse(tag: EffectTag, ctx: Ctx) -> None:
    target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
    mode = tag.params.get("mode", "all")
    if mode in ("buffs", "all"):
        _clear_buffs(target)
    if mode in ("debuffs", "all"):
        _clear_debuffs(target)



def _h_dispel_buffs(tag: EffectTag, ctx: Ctx) -> None:
    target = ctx.user if tag.params.get("target", "enemy") == "self" else ctx.target
    _clear_buffs(target)



def _h_dispel_debuffs(tag: EffectTag, ctx: Ctx) -> None:
    target = ctx.user if tag.params.get("target", "self") == "self" else ctx.target
    _clear_debuffs(target)



def _h_position_buff(tag: EffectTag, ctx: Ctx) -> None:
    positions = tag.params.get("positions", [])
    buff = tag.params.get("buff", {})
    skill_idx = _find_skill_index(ctx.user, ctx.skill)
    if skill_idx in positions:
        _apply_buff(ctx.user, buff)



def _h_drive(tag: EffectTag, ctx: Ctx) -> None:
    value = tag.params.get("value", 1)
    ability_filter = ctx.result.get("_ability_filter", {}) if isinstance(ctx.result, dict) else {}
    positions = ability_filter.get("positions", [])

    # 位置型特性：把"传动"转成对应技能本体上的 DRIVE 标签，避免每回合重复叠加。
    if ctx.skill is None and positions:
        for idx, skill in enumerate(ctx.user.skills):
            if idx not in positions:
                continue
            if not getattr(skill, "effects", None):
                skill.effects = []
            # 兼容 SE 和 EffectTag 列表：检查是否已有 DRIVE
            has_drive = False
            for item in skill.effects:
                if isinstance(item, SkillEffect):
                    has_drive = has_drive or any(
                        t.type == E.DRIVE and t.params.get("value", 1) == value
                        for t in item.effects
                    )
                elif hasattr(item, "type") and item.type == E.DRIVE and item.params.get("value", 1) == value:
                    has_drive = True
            if not has_drive:
                if skill.effects and isinstance(skill.effects[0], SkillEffect):
                    skill.effects.append(SkillEffect(SkillTiming.POST_USE, [EffectTag(E.DRIVE, {"value": value})]))
                else:
                    skill.effects.append(EffectTag(E.DRIVE, {"value": value}))
        return

    ctx.result["_drive_value"] = value



def _h_passive_energy_reduce(tag: EffectTag, ctx: Ctx) -> None:
    pass  # 由 execute_drive 处理



def _h_replay_agility(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_replay_agility"] = True



def _h_agility_cost_share(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result["_agility_cost_share"] = tag.params.get("divisor", 2)



def _h_energy_cost_accumulate(tag: EffectTag, ctx: Ctx) -> None:
    delta = tag.params.get("delta", 1)
    ctx.skill.energy_cost = max(0, ctx.skill.energy_cost + _adjust_cost_delta(ctx.user, delta))



def _h_weather(tag: EffectTag, ctx: Ctx) -> None:
    """设置天气，持续指定回合。params: {"type": "sunny"|"rain"|"sandstorm"|"hail"|"snow", "turns": 8}"""
    from nrc_core.models import Type as TypeEnum
    weather_type = tag.params.get("type", "sunny")
    turns = tag.params.get("turns", 5)
    ctx.state.weather = weather_type
    ctx.state.weather_turns = turns  # 写入持续回合数

    # 沙暴：地面系技能能耗减半（向下取整）
    if weather_type == "sandstorm":
        for p in ctx.state.team_a + ctx.state.team_b:
            if p.is_fainted:
                continue
            for sk in p.skills:
                if sk.skill_type == TypeEnum.GROUND:
                    key = id(sk)
                    if key not in ctx.state.sandstorm_original_costs:
                        ctx.state.sandstorm_original_costs[key] = sk.energy_cost
                    sk.energy_cost = max(1, sk.energy_cost // 2)



_WEATHER_DAMAGE_TYPES = {"sandstorm", "snow"}   # 洛克王国真实天气（沙暴/雪天）



_WEATHER_IMMUNE_TYPES = {"ground", "steel"}      # 游戏无岩系，免疫天气伤害的属性



def _apply_weather_damage(state) -> None:
    """回合结束时应用天气效果。
    - 沙暴：对非地/钢系造成 1/16 HP 伤害
    - 暴风雪：双方当前在场精灵获得 2 层冻结
    """
    from nrc_core.models import Type, has_type
    w = state.weather
    if not w:
        return
    immune = {Type.GROUND, Type.STEEL}
    if w == "sandstorm":
        dmg_pct = 1 / 16
        for p in state.team_a:
            if not p.is_fainted and not (has_type(p, Type.GROUND) or has_type(p, Type.STEEL)):
                p.current_hp = max(1, p.current_hp - int(p.hp * dmg_pct))
        for p in state.team_b:
            if not p.is_fainted and not (has_type(p, Type.GROUND) or has_type(p, Type.STEEL)):
                p.current_hp = max(1, p.current_hp - int(p.hp * dmg_pct))
    if w == "snow":
        from nrc_core.models import add_freeze_stacks, has_type, Type
        for team, index in ((state.team_a, state.current_a), (state.team_b, state.current_b)):
            p = team[index]
            if not p.is_fainted and not has_type(p, Type.ICE):
                opponent = state.team_b[state.current_b] if team is state.team_a else state.team_a[state.current_a]
                add_freeze_stacks(p, 2, opponent, state=state,
                                  team="b" if team is state.team_a else "a")
    if w in {"thunder", "雷鸣"}:
        from nrc_core.models import add_electric_stacks, has_type, Type
        for team, index in ((state.team_a, state.current_a), (state.team_b, state.current_b)):
            p = team[index]
            if not p.is_fainted and not has_type(p, Type.ELECTRIC):
                add_electric_stacks(p, 1)



def _h_enemy_energy_cost_up(tag: EffectTag, ctx: Ctx) -> None:
    from nrc_core.models import SkillCategory as SC
    amount = tag.params.get("amount", 0)
    filt = tag.params.get("filter", "all")
    duration = tag.params.get("duration", 0)

    # Timed cost modifiers are stored on the target and consumed by battle.py
    # when that target actually spends energy on a later turn.
    if duration:
        mod = {
            "amount": int(amount),
            "filter": filt,
            "turns": int(duration),
        }
        if filt in ("used_skill", "other_skills") and ctx.enemy_skill is not None:
            mod["skill_name"] = ctx.enemy_skill.name
        ctx.target.ability_state.setdefault("temporary_skill_cost_mods", []).append(mod)
        return

    for s in ctx.target.skills:
        if filt == "attack" and s.category in (SC.PHYSICAL, SC.MAGICAL):
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, amount))
        elif filt == "all":
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, amount))



def _h_mirror_damage(tag: EffectTag, ctx: Ctx) -> None:
    """
    反弹伤害（听桥）：将攻击方对自己造成的原始伤害值原样反弹给攻击方。
    ctx.damage 在 execute_counter 中传入的是减伤前的原始伤害值。
    如果 ctx.damage == 0（对方没有造成伤害，如状态/防御技能），则不反弹。
    """
    mirror_dmg = ctx.damage
    if mirror_dmg > 0 and not ctx.target.is_fainted:
        ctx.target.current_hp -= mirror_dmg
        from nrc_core.models import StatusType
        if ctx.target.current_hp <= 0:
            ctx.target.current_hp = 0
            ctx.target.status = StatusType.FAINTED



def _h_counter_override(tag: EffectTag, ctx: Ctx) -> None:
    replace_type = tag.params.get("replace", "")
    from_val = tag.params.get("from", 0)
    to_val = tag.params.get("to", 0)
    if replace_type == "poison":
        ctx.target.poison_stacks -= from_val
        ctx.target.poison_stacks += to_val



def _h_passive_energy_reduce_water_ring(tag: EffectTag, ctx: Ctx) -> None:
    """水环应对攻击时：全技能能耗 -N（在 execute_counter 子效果中）"""
    reduce = tag.params.get("reduce", 0)
    rng = tag.params.get("range", "all")
    if rng == "all":
        for s in ctx.user.skills:
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))



def _h_permanent_mod_ability(tag: EffectTag, ctx: Ctx) -> None:
    """特性中的永久修改（身经百练）"""
    per_counter = tag.params.get("per_counter", 0)
    ability_filter = ctx.result.get("_ability_filter", {}) if isinstance(ctx.result, dict) else {}
    positions = ability_filter.get("positions", [])

    if per_counter > 0:
        counter_count = getattr(
            ctx.state,
            "counter_count_a" if ctx.team == "a" else "counter_count_b",
            0
        )
        bonus_pct = per_counter * counter_count
        skill_filter = tag.params.get("skill_filter", {})
        elements = skill_filter.get("element", [])
        before_power = [s.power for s in ctx.user.skills]
        from nrc_core.models import TYPE_NAME_MAP as _TYPE_MAP
        for s in ctx.user.skills:
            if positions and _find_skill_index(ctx.user, s) not in positions:
                continue
            if elements:
                type_matched = any(_TYPE_MAP.get(el) == s.skill_type for el in elements)
                if not type_matched:
                    continue
            base_power = getattr(s, "_ability_base_power", s.power)
            setattr(s, "_ability_base_power", base_power)
            s.power = int(base_power * (1.0 + bonus_pct))
        if not positions and not elements:
            previous = ctx.user.ability_state.get("_global_per_counter_power_pct", 0)
            _record_public_skill_modifier(ctx.user, "power", bonus_pct * 100 - previous, before_power, "power_pct")
            ctx.user.ability_state["_global_per_counter_power_pct"] = bonus_pct * 100
    else:
        if ctx.skill is not None:
            _apply_permanent_mod(ctx.user, ctx.skill, tag.params)
            return

        if positions:
            for idx, s in enumerate(ctx.user.skills):
                if idx not in positions:
                    continue
                if tag.params.get("target") == "power":
                    base_power = getattr(s, "_ability_base_power", s.power)
                    setattr(s, "_ability_base_power", base_power)
                    s.power = max(0, base_power + int(tag.params.get("delta", 0)))
                else:
                    _apply_permanent_mod(ctx.user, s, tag.params)
        else:
            for s in ctx.user.skills:
                _apply_permanent_mod(ctx.user, s, tag.params)



def _h_counter_attack(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result.setdefault("counter_effects", []).append(tag)



def _h_counter_status(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result.setdefault("counter_effects", []).append(tag)



def _h_counter_defense(tag: EffectTag, ctx: Ctx) -> None:
    ctx.result.setdefault("counter_effects", []).append(tag)



