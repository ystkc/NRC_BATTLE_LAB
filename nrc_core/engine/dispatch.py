"""效果统一分发与全技能公开修正归属。"""

from typing import Callable, TYPE_CHECKING
from nrc_core.effect_models import EffectTag, Timing
from nrc_core.debug import core_log
from nrc_core.engine.context import (
    Ctx,
)
from nrc_core.engine.helpers import (
    _adjust_cost_delta,
    _record_public_skill_modifier,
    _promise_modifiers,
    _apply_prince_promise,
)
from nrc_core.engine.registry import (
    _ABILITY_HANDLER_OVERRIDES,
    _HANDLERS,
)

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


def _global_skill_cost_sources(tag: EffectTag, ctx: Ctx, handler: Callable) -> list:
    """由规则入口明确作用域，不能用四个技能变化相同推断全局。"""
    name = handler.__name__
    user = ctx.user
    target = ctx.target
    params = tag.params
    reduce_handlers = {
        "_h_on_skill_element_cost_reduce", "_h_enemy_switch_self_cost_reduce",
        "_h_cute_on_gain_cost_reduce", "_h_passive_energy_reduce_water_ring",
    }
    if name in reduce_handlers:
        if name == "_h_passive_energy_reduce_water_ring" and params.get("range", "all") != "all":
            return []
        defaults = {"_h_on_skill_element_cost_reduce": 1, "_h_enemy_switch_self_cost_reduce": 3,
                    "_h_cute_on_gain_cost_reduce": 4, "_h_passive_energy_reduce_water_ring": 0}
        return [(user, "energy_cost", _adjust_cost_delta(user, -params.get("reduce", defaults[name])))]
    if name == "_h_counter_success_cost_reduce":
        return [(user, "energy_cost", -params.get("delta", 5))]
    if name in {"_h_enemy_all_cost_up", "_h_enemy_energy_cost_up"}:
        if params.get("duration") or params.get("filter", "all") != "all":
            return []
        return [(target, "energy_cost", _adjust_cost_delta(target, params.get("amount", 0 if name == "_h_enemy_energy_cost_up" else 1)))]
    if name == "_h_contract_entry":
        ball = params.get("ball") or user.ability_state.get("gulu_ball")
        if ball in {"skill_cost", "网兜球", "combo"}:
            return [(user, "energy_cost", -1)]
    if name == "_h_extra_consumption_on_freeze":
        if ctx.result.get("_ability_timing") != Timing.ON_INFLICT_FREEZE.name or ctx.result.get("freeze_stacks_added", 0) <= 0:
            return []
        return [(target, "energy_cost", _adjust_cost_delta(target, params.get("extra", 1)))]
    if name == "_h_entry_freeze_extra":
        return [(target, "energy_cost", _adjust_cost_delta(target, params.get("extra_cost_up", 1)))]
    if name == "_h_carry_skill_cost_reduce" and not params.get("category"):
        return [(user, "energy_cost", _adjust_cost_delta(user, -params.get("reduce", 2)))]
    if name == "_h_cute_bench_cost_reduce":
        bench = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
        total = sum(p.cute_stacks for p in bench if p is not user and not p.is_fainted)
        return [(user, "energy_cost", -total)]
    if name == "_h_refraction":
        from nrc_core.models import Type
        if any(s is not ctx.skill and s.skill_type == Type.WATER for s in user.skills):
            return [(user, "energy_cost", -1)]
    if name == "_h_entry_buff_per_skill_count" and not params.get("element_filter"):
        counts = ctx.state.skill_use_counts_a if ctx.team == "a" else ctx.state.skill_use_counts_b
        keys = params.get("count_keys") or [params.get("count_key", "")]
        count = sum(counts.get(key, 0) for key in keys)
        delta = -params.get("per_count", {}).get("cost_reduce", 0) * count
        return [(user, "energy_cost", _adjust_cost_delta(user, delta))]
    if name == "_h_permanent_mod_ability" and ctx.skill is None:
        if params.get("trigger") in {"per_position_change", "per_counter", "per_use"}:
            return []
        filters = ctx.result.get("_ability_filter", {})
        if not filters.get("positions") and not params.get("skill_filter") and not params.get("per_counter"):
            field = {"cost": "energy_cost", "power": "power", "hit_count": "hit_count"}.get(params.get("target"))
            if field:
                delta = params.get("delta", 0)
                return [(user, field, _adjust_cost_delta(user, delta) if field == "energy_cost" else delta)]
    return []



def _apply_tag(tag: EffectTag, ctx: Ctx, ability_mode: bool = False) -> None:
    """统一效果分发入口。ability_mode=True 时优先用特性专属 handler。"""
    promise_before = [(pokemon, _promise_modifiers(pokemon)) for pokemon in (ctx.user, ctx.target)]
    before = {
        "user_hp": ctx.user.current_hp,
        "target_hp": ctx.target.current_hp,
        "user_energy": ctx.user.energy,
        "target_energy": ctx.target.energy,
        "target_poison": ctx.target.poison_stacks,
        "target_burn": ctx.target.burn_stacks,
    }
    if ability_mode:
        handler = _ABILITY_HANDLER_OVERRIDES.get(tag.type) or _HANDLERS.get(tag.type)
    else:
        handler = _HANDLERS.get(tag.type)
    if handler:
        modifier_slots = []
        for pokemon in (ctx.user, ctx.target):
            private = pokemon.ability_state.get("_public_skill_modifier_deltas")
            if private is not None:
                modifier_slots.append((pokemon, {id(skill): dict(private[index]) if index < len(private) else {}
                                                   for index, skill in enumerate(pokemon.skills)},
                                       [id(skill) for skill in pokemon.skills]))
        sources = [(pokemon, field, delta, [getattr(s, field, 0) for s in pokemon.skills],
                    [entry.get(field, 0) for entry in pokemon.ability_state.get("_public_skill_modifier_deltas", [])])
                   for pokemon, field, delta in _global_skill_cost_sources(tag, ctx, handler)]
        handler(tag, ctx)
        for pokemon, slots, previous_ids in modifier_slots:
            if previous_ids != [id(skill) for skill in pokemon.skills]:
                pokemon.ability_state["_public_skill_modifier_deltas"] = [slots.get(id(skill), {}) for skill in pokemon.skills]
        for pokemon, field, delta, values, previous_global in sources:
            current_global = pokemon.ability_state.get("_public_skill_modifier_deltas", [])
            values = [value + (current_global[index].get(field, 0) if index < len(current_global) else 0)
                      - (previous_global[index] if index < len(previous_global) else 0)
                      for index, value in enumerate(values)]
            if delta and (handler.__name__ != "_h_cute_on_gain_cost_reduce" or any(getattr(s, field, 0) != value for s, value in zip(pokemon.skills, values))):
                _record_public_skill_modifier(pokemon, field, delta, values)
    for pokemon, modifiers in promise_before:
        _apply_prince_promise(pokemon, modifiers, getattr(ctx.state, "turn", 0))
    core_log("ability" if ability_mode else "skill", "effect_tag",
             turn=getattr(ctx.state, "turn", None),
             user=ctx.user.name, target=ctx.target.name,
             skill=ctx.skill.name if ctx.skill else None,
             tag=getattr(tag.type, "value", str(tag.type)), params=tag.params,
             handled=handler is not None, before=before,
             after={
                 "user_hp": ctx.user.current_hp,
                 "target_hp": ctx.target.current_hp,
                 "user_energy": ctx.user.energy,
                 "target_energy": ctx.target.energy,
                 "target_poison": ctx.target.poison_stacks,
                 "target_burn": ctx.target.burn_stacks,
             }, result=ctx.result)



