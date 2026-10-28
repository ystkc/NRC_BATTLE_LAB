"""效果运行条件与技能过滤。"""

from typing import Dict, TYPE_CHECKING
from nrc_core.effect_models import EffectTag
from nrc_core.engine.context import (
    Ctx,
)

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


def _check_runtime_condition(tag: EffectTag, ctx: Ctx) -> bool:
    condition = tag.params.get("condition", "")
    if not condition:
        return True
    if condition == "after_use_hp_gt_half":
        return ctx.user.current_hp > ctx.user.hp / 2
    if condition in ("self_hp_above", "self_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        ratio = ctx.user.current_hp / max(1, ctx.user.hp)
        return ratio > threshold if condition == "self_hp_above" else ratio < threshold
    if condition in ("enemy_hp_above", "enemy_hp_below"):
        threshold = float(tag.params.get("threshold", 0.5))
        ratio = ctx.target.current_hp / max(1, ctx.target.hp)
        return ratio > threshold if condition == "enemy_hp_above" else ratio < threshold
    if condition == "enemy_switch":
        return bool(ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a)
    return True



def _check_skill_filter(filt: Dict, ctx: Ctx) -> bool:
    """检查 SkillEffect 的 filter 条件是否满足。"""
    if not filt:
        return True

    # 应对类别匹配（ON_COUNTER 阶段由 execute_counter_se 单独处理，此处跳过）
    if "category" in filt:
        return True

    if filt.get("enemy_switch"):
        enemy_switched = (
            ctx.state.switch_this_turn_b if ctx.team == "a" else ctx.state.switch_this_turn_a
        )
        if not enemy_switched:
            return False

    if filt.get("first_strike"):
        if not ctx.is_first:
            return False

    if "self_hp_lt" in filt:
        ratio = ctx.user.current_hp / max(1, ctx.user.hp)
        if ratio >= filt["self_hp_lt"]:
            return False

    if "self_hp_gt" in filt:
        ratio = ctx.user.current_hp / max(1, ctx.user.hp)
        if ratio <= filt["self_hp_gt"]:
            return False

    if "enemy_hp_lt" in filt:
        ratio = ctx.target.current_hp / max(1, ctx.target.hp)
        if ratio >= filt["enemy_hp_lt"]:
            return False

    if "enemy_hp_gt" in filt:
        ratio = ctx.target.current_hp / max(1, ctx.target.hp)
        if ratio <= filt["enemy_hp_gt"]:
            return False

    if filt.get("on_kill"):
        # is_fainted 在 battle.py 扣血后设置
        # 在 execute_skill 内部，用 damage 是否能击杀来判断
        damage_dealt = ctx.result.get("damage", 0)
        target_dead = ctx.target.is_fainted or (
            damage_dealt > 0 and ctx.target.current_hp <= damage_dealt
        )
        if not target_dead:
            return False

    if filt.get("energy_zero_after"):
        if ctx.user.energy > 0:
            return False

    if filt.get("prev_counter_success"):
        if ctx.user.ability_state.get("last_counter_success_turn") != ctx.state.turn - 1:
            return False

    if filt.get("counter"):
        # counter 模式: 只在 execute_counter 上下文中生效
        return True

    if "per" in filt:
        # per 条件由 handler 处理缩放逻辑，这里只判断是否有层数
        per = filt["per"]
        if per == "enemy_poison":
            if ctx.target.poison_stacks <= 0:
                return False
        elif per == "enemy_burn":
            if ctx.target.burn_stacks <= 0:
                return False

    if "self_hp_above" in filt:
        threshold = float(filt["self_hp_above"])
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        if start_hp / max(1, ctx.user.hp) <= threshold:
            return False

    if "self_hp_below" in filt:
        threshold = float(filt["self_hp_below"])
        start_hp = ctx.result.get("_user_hp_start", ctx.user.current_hp)
        if start_hp / max(1, ctx.user.hp) >= threshold:
            return False

    if "prev_status" in filt:
        if not (ctx.user.ability_state.get("last_skill_category") == "状态"
                and ctx.user.ability_state.get("last_skill_turn") == ctx.state.turn - 1):
            return False

    if "self_missing_hp_step" in filt:
        # 始终通过 — 实际缩放在 handler 里
        pass

    if "energy_cost_above_base" in filt:
        # 始终通过 — 实际缩放在 handler 里
        pass

    if "per_enemy_poison" in filt:
        if ctx.target.poison_stacks <= 0:
            return False

    return True



