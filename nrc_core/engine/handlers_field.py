"""奉献、传动、契约与萌化效果处理器。"""

from typing import TYPE_CHECKING
from nrc_core.effect_models import EffectTag
from nrc_core.rng import choice as rng_choice
from nrc_core.engine.context import (
    Ctx,
)

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


DEVOTION_TYPES = ["假寐", "飞断", "虫茧", "捆缚", "虫群过境"]



DEVOTION_CAPS = {"假寐": 10, "飞断": 5, "虫茧": 10, "捆缚": 10, "虫群过境": 10}



def _grant_devotion(state, team: str, devotion_type: str, is_random: bool = False) -> None:
    if devotion_type not in DEVOTION_TYPES:
        return
    devotion = state._get_devotion(team)
    cap = DEVOTION_CAPS[devotion_type]
    next_value = devotion.get(devotion_type, 0) + 1
    devotion[devotion_type] = min(cap, next_value) if is_random else next_value
    random_counts = state.random_devotion_counts_a if team == "a" else state.random_devotion_counts_b
    if is_random:
        random_counts[devotion_type] = min(cap, random_counts.get(devotion_type, 0) + 1)



def _h_devotion_grant(tag: EffectTag, ctx: Ctx) -> None:
    """DEVOTION_GRANT: 使用技能时获得指定类型的奉献1层"""
    dtype = tag.params.get("type", "")
    _grant_devotion(ctx.state, ctx.team, dtype)



def _h_devotion_grant_random(tag: EffectTag, ctx: Ctx) -> None:
    """DEVOTION_GRANT_RANDOM: 花精灵 — 回合结束随机获得1种奉献1层"""
    team = ctx.team
    chosen = rng_choice(DEVOTION_TYPES)
    _grant_devotion(ctx.state, team, chosen, is_random=True)



def _h_devotion_on_hit(tag: EffectTag, ctx: Ctx) -> None:
    """DEVOTION_ON_HIT: 坚韧铠甲 — 受攻击时随机获得1种奉献1层"""
    team = ctx.team
    chosen = rng_choice(DEVOTION_TYPES)
    _grant_devotion(ctx.state, team, chosen, is_random=True)



def _h_refraction(tag: EffectTag, ctx: Ctx) -> None:
    """折射：按使用者携带的其他系别技能独立结算效果。"""
    from nrc_core.models import Type as PokemonType

    carried_types = {skill.skill_type for skill in ctx.user.skills if skill is not ctx.skill}
    carried_types.discard(PokemonType.LIGHT)

    if PokemonType.LIGHT in {skill.skill_type for skill in ctx.user.skills if skill is not ctx.skill}:
        ctx.user.spatk_up += 0.3
    if PokemonType.NORMAL in carried_types:
        ctx.user.skill_power_bonus += 10
    if PokemonType.WATER in carried_types:
        for skill in ctx.user.skills:
            skill.energy_cost = max(0, skill.energy_cost - 1)
    if PokemonType.GRASS in carried_types:
        heal = int(ctx.user.hp * 0.15)
        if heal > 0:
            ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)
    if PokemonType.ELECTRIC in carried_types:
        ctx.user.speed_up += 20.0 / max(1, ctx.user.speed)
    if PokemonType.STEEL in carried_types:
        ctx.user.def_up += 0.3
    if PokemonType.FLYING in carried_types:
        ctx.user.hit_count_mod += 1
    if PokemonType.DARK in carried_types:
        ctx.user.life_drain_mod += 0.3
    if PokemonType.FIGHTING in carried_types:
        ctx.user.atk_up += 0.3

    if not ctx.target:
        return
    if PokemonType.FIRE in carried_types:
        if not ctx.target.ability_state.get("burn_immune") and not ctx.target.ability_state.get("debuff_immune"):
            ctx.target.burn_stacks += 4
    if PokemonType.ICE in carried_types:
        if not ctx.target.ability_state.get("freeze_immune") and not ctx.target.ability_state.get("debuff_immune"):
            from nrc_core.models import add_freeze_stacks
            add_freeze_stacks(ctx.target, 2, ctx.user, state=ctx.state, team=ctx.team)
    if PokemonType.POISON in carried_types:
        if not ctx.target.ability_state.get("poison_immune") and not ctx.target.ability_state.get("debuff_immune"):
            ctx.target.poison_stacks += 2
    if PokemonType.PSYCHIC in carried_types:
        if not ctx.target.ability_state.get("meteor_immune") and not ctx.target.ability_state.get("debuff_immune"):
            ctx.target.meteor_stacks += 1
    if PokemonType.BUG in carried_types:
        if not ctx.target.ability_state.get("debuff_immune"):
            ctx.target.def_down += 0.4
    if PokemonType.DRAGON in carried_types:
        if not ctx.target.ability_state.get("debuff_immune"):
            ctx.target.spdef_down += 0.4
    if PokemonType.FAIRY in carried_types:
        if not ctx.target.ability_state.get("debuff_immune"):
            ctx.target.atk_down += 0.3
            ctx.target.spatk_down += 0.3
    if PokemonType.GHOST in carried_types:
        if not ctx.target.ability_state.get("energy_immune"):
            ctx.target.energy = max(0, ctx.target.energy - 2)
    if PokemonType.GROUND in carried_types:
        if not ctx.target.ability_state.get("debuff_immune"):
            ctx.target.speed_down += 0.4
            ctx.target.hit_count_mod -= 2



def _h_drive_position_shift(tag: EffectTag, ctx: Ctx) -> None:
    """DRIVE_POSITION_SHIFT: 翼轴 — 指定位置技能获得迅捷+传动"""
    slot = tag.params.get("slot", 0)
    agility = tag.params.get("agility", True)
    drive_val = tag.params.get("drive", 1)
    skills = ctx.user.skills
    if slot < len(skills):
        if agility:
            skills[slot].agility = True
        # 传动值存在 ability_state 中，battle.py 的传动循环会使用
        existing_drives = ctx.user.ability_state.setdefault("extra_drives", {})
        existing_drives[slot] = existing_drives.get(slot, 0) + drive_val



def _h_drive_on_position_change(tag: EffectTag, ctx: Ctx) -> None:
    """DRIVE_ON_POSITION_CHANGE: 机械变式 — 技能位置变化时能耗-1"""
    ctx.user.ability_state["drive_on_position_change_reduce"] = tag.params.get("reduce", 1)



def _h_charge_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """CHARGE_COST_REDUCE: 洄游 — 每次蓄力全技能能耗永久-1（标记，由battle.py蓄力流程读取）"""
    ctx.user.ability_state["charge_cost_reduce"] = tag.params.get("reduce", 1)



def _h_charge_free_skill(tag: EffectTag, ctx: Ctx) -> None:
    """CHARGE_FREE_SKILL: 嫉妒 — 蓄力状态下可用任一技能（标记）"""
    ctx.user.ability_state["charge_free_skill"] = True



def _h_share_gains(tag: EffectTag, ctx: Ctx) -> None:
    """SHARE_GAINS: 系统发育 — 获得能量/生命时分配给场下精灵（标记）"""
    ctx.user.ability_state["share_gains"] = True



def _h_contract_entry(tag: EffectTag, ctx: Ctx) -> None:
    """CONTRACT_ENTRY: apply the configured gulu-ball entry package."""
    from nrc_core.models import add_freeze_stacks, has_type, Type

    ball = tag.params.get("ball") or ctx.user.ability_state.get("gulu_ball")
    if ball == "柔软咕噜球":
        options = [
            "skill_power", "heal", "burn", "skill_cost", "spatk", "slow_combo",
            "speed", "poison", "def", "atk", "combo", "enemy_atk", "spdef",
            "meteor", "freeze", "enemy_spdef", "energy", "drain",
        ]
        ball = ctx.user.ability_state.setdefault("contract_random_ball", rng_choice(options))

    def add_speed(value: int) -> None:
        ctx.user.speed_up += value / max(1, ctx.user.speed)

    if ball == "普通咕噜球":
        ctx.user.atk_up += 0.05; ctx.user.spatk_up += 0.05
        ctx.user.def_up += 0.05; ctx.user.spdef_up += 0.05; add_speed(5)
    elif ball == "高级咕噜球":
        ctx.user.atk_up += 0.10; ctx.user.spatk_up += 0.10
        ctx.user.def_up += 0.10; ctx.user.spdef_up += 0.10; add_speed(10)
    elif ball == "国王球":
        ctx.user.atk_up += 0.15; ctx.user.spatk_up += 0.15
        ctx.user.def_up += 0.15; ctx.user.spdef_up += 0.15; add_speed(15)
    elif ball in {"美妙球", "skill_power"}:
        ctx.user.skill_power_bonus += 20
        ctx.target.atk_down += 0.30; ctx.target.spatk_down += 0.30
    elif ball in {"好战球", "atk"}:
        ctx.user.atk_up += 0.40; ctx.target.spdef_down += 0.40
    elif ball in {"光合球", "heal"}:
        ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + round(ctx.user.hp * 0.10))
        ctx.user.spatk_up += 0.40
    elif ball in {"skill_cost"}:
        for skill in ctx.user.skills:
            skill.energy_cost = max(0, skill.energy_cost - 1)
    elif ball in {"spatk"}:
        ctx.user.spatk_up += 0.40
    elif ball in {"网兜球", "combo"}:
        ctx.user.hit_count_mod += 1
        for skill in ctx.user.skills:
            skill.energy_cost = max(0, skill.energy_cost - 1)
    elif ball in {"暗星球", "energy"}:
        ctx.target.energy = max(0, ctx.target.energy - 1)
        ctx.user.life_drain_mod += 0.30
    elif ball in {"调温球", "freeze"}:
        if not has_type(ctx.target, Type.ICE):
            add_freeze_stacks(ctx.target, 1, ctx.user, state=ctx.state, team=ctx.team)
        if not has_type(ctx.target, Type.FIRE):
            ctx.target.burn_stacks += 4
    elif ball in {"绝缘球", "speed"}:
        add_speed(50)
        if not has_type(ctx.target, Type.POISON):
            ctx.target.poison_stacks += 1
    elif ball in {"淘沙球", "slow_combo"}:
        ctx.target.speed_down += 0.40
        ctx.target.hit_count_mod -= 2
        ctx.target.def_down += 0.40
    elif ball in {"变幻球", "def"}:
        ctx.user.def_up += 0.30; ctx.user.spdef_up += 0.30
        marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
        marks["meteor_mark"] = min(99, max(0, int(marks.get("meteor_mark", 0)) + 1))
    elif ball in {"对手攻击", "enemy_atk"}:
        ctx.target.atk_down += 0.30; ctx.target.spatk_down += 0.30
    elif ball in {"对手魔防", "enemy_spdef"}:
        ctx.target.spdef_down += 0.40
    elif ball in {"poison"}:
        if not has_type(ctx.target, Type.POISON):
            ctx.target.poison_stacks += 1
    elif ball in {"spdef"}:
        ctx.user.def_up += 0.30
        ctx.user.spdef_up += 0.30
    elif ball in {"meteor"}:
        marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
        marks["meteor_mark"] = min(99, max(0, int(marks.get("meteor_mark", 0)) + 1))
    elif ball == "drain":
        ctx.user.life_drain_mod += 0.30
    elif ball == "burn":
        if not has_type(ctx.target, Type.FIRE):
            ctx.target.burn_stacks += 4



def _h_bloodline_entry(tag: EffectTag, ctx: Ctx) -> None:
    """BLOODLINE_ENTRY: 稀兽花宝 — 根据系别入场效果，默认萌系：降低敌方60%双攻"""
    element = tag.params.get("element", "萌")
    if element == "萌":
        # 降低敌方60%双攻（各6层×10%）
        ctx.target.atk_down += 0.6
        ctx.target.spatk_down += 0.6



def _cute_max_stacks(pokemon: "Pokemon") -> int:
    """萌化层数上限（默认3层，特性'无忧无虑'无上限用999）"""
    if pokemon.ability_state.get("cute_no_cap"):
        return 999
    return 3



def _cute_add(pokemon: "Pokemon", stacks: int) -> int:
    """给精灵增加萌化层数，返回实际增加量。"""
    cap = min(_cute_max_stacks(pokemon), len(pokemon.devolution_forms))
    before = pokemon.cute_stacks
    pokemon.cute_stacks = min(cap, pokemon.cute_stacks + stacks)
    if pokemon.cute_stacks > before:
        form = pokemon.devolution_forms[pokemon.cute_stacks - 1]
        pokemon.name = form["name"]
        stats = form["stats"]
        pokemon.hp = stats["hp"]
        pokemon.current_hp = min(pokemon.current_hp, pokemon.hp)
        pokemon.attack = stats["atk"]
        pokemon.defense = stats["def"]
        pokemon.sp_attack = stats["spatk"]
        pokemon.sp_defense = stats["spdef"]
        pokemon.speed = stats["speed"]
    return pokemon.cute_stacks - before



def _h_cute_gain(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_GAIN: 自己获得N层萌化"""
    stacks = tag.params.get("stacks", 1)
    added = _cute_add(ctx.user, stacks)
    if added > 0:
        ctx.result.setdefault("log", []).append(f"{ctx.user.name} 获得{added}层萌化（共{ctx.user.cute_stacks}层）")



def _h_cute_enemy_gain(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_ENEMY_GAIN: 敌方获得N层萌化"""
    stacks = tag.params.get("stacks", 1)
    added = _cute_add(ctx.target, stacks)
    if added > 0:
        ctx.result.setdefault("log", []).append(f"{ctx.target.name} 获得{added}层萌化（共{ctx.target.cute_stacks}层）")



def _h_cute_all_bench(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_ALL_BENCH: 场下所有精灵获得萌化（赤子之心/玩具乐园）"""
    stacks = tag.params.get("stacks", 1)
    team = getattr(ctx, "team", "a")
    state = ctx.state
    bench = state.team_a if team == "a" else state.team_b
    for poke in bench:
        if not poke.is_fainted and poke is not ctx.user:
            _cute_add(poke, stacks)
    # 在场精灵也获得
    _cute_add(ctx.user, stacks)



def _h_cute_both(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_BOTH: 自己和敌方各获得N层萌化（甜心续航）"""
    stacks = tag.params.get("stacks", 1)
    _cute_add(ctx.user, stacks)
    _cute_add(ctx.target, stacks)



def _h_cute_transfer(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_TRANSFER: 将自身萌化全部转移给敌方（反弹）"""
    n = ctx.user.cute_stacks
    if n <= 0:
        return
    ctx.user.cute_stacks = 0
    _cute_add(ctx.target, n)
    ctx.result.setdefault("log", []).append(f"{ctx.user.name} 将{n}层萌化转移给{ctx.target.name}")



def _h_cute_clear_self(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_CLEAR_SELF: 解除自身萌化（逆向演化第一步）"""
    ctx.result["_cute_cleared"] = ctx.user.cute_stacks
    ctx.user.cute_stacks = 0



def _h_cute_if_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_IF_POWER_BONUS: 自己有萌化时本次技能威力+N（幼态延续/超级糖果）"""
    if ctx.user.cute_stacks > 0:
        bonus = tag.params.get("bonus", 60)
        ctx.result["_power_bonus"] = ctx.result.get("_power_bonus", 0) + bonus



def _h_cute_on_gain_power_perm(tag: EffectTag, ctx: Ctx) -> None:
    """获得萌化后，所有原本具有威力的携带技能永久加威力。"""
    stacks = tag.params.get("stacks", 1)
    added = _cute_add(ctx.user, stacks)
    if added > 0:
        delta = tag.params.get("delta", 10)
        before = [s.power for s in ctx.user.skills]
        for s in ctx.user.skills:
            if s.power >= 0:
                s.power = max(0, s.power + delta)
        from nrc_core.engine.helpers import _record_public_skill_modifier
        _record_public_skill_modifier(ctx.user, "power", delta, before)



def _h_cute_on_gain_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_ON_GAIN_COST_REDUCE: 获得萌化后全技能能耗永久-N（生日蛋糕）"""
    stacks = tag.params.get("stacks", 1)
    added = _cute_add(ctx.user, stacks)
    if added > 0:
        reduce = tag.params.get("reduce", 4)
        for s in ctx.user.skills:
            s.energy_cost = max(0, s.energy_cost - reduce)



def _h_cute_on_gain_speed_perm(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_ON_GAIN_SPEED_PERM: 获得萌化后速度永久+N（示弱）"""
    stacks = tag.params.get("stacks", 1)
    added = _cute_add(ctx.user, stacks)
    if added > 0:
        speed_bonus = tag.params.get("speed", 150)
        ctx.user.speed = ctx.user.speed + speed_bonus



def _h_cute_team_power(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_TEAM_POWER: 双方全队萌化总层数决定连击数（月光合奏）"""
    state = ctx.state
    team_a = state.team_a
    team_b = state.team_b
    total = sum(p.cute_stacks for p in team_a + team_b)
    if total > 0:
        ctx.skill.hit_count = max(1, ctx.skill.hit_count + total)



def _h_cute_lethal_shield(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_LETHAL_SHIELD: 受致命伤时+1萌化并免死（化茧特性 ON_TAKE_HIT）"""
    # 由特性 ON_TAKE_HIT 触发，检查是否会被致命一击
    dmg = ctx.result.get("damage", 0)
    if dmg >= ctx.user.current_hp and not ctx.user.is_fainted:
        _cute_add(ctx.user, 1)
        ctx.user.current_hp = 1  # 免死保留1点
        ctx.result["blocked_lethal"] = True
        ctx.result.setdefault("log", []).append(f"{ctx.user.name} 化茧！获得1层萌化，免疫致命伤")



def _h_cute_no_cap(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_NO_CAP: 萌化层数无上限（无忧无虑特性 PASSIVE）"""
    ctx.user.ability_state["cute_no_cap"] = True



def _h_cute_hit_per_stack(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_HIT_PER_STACK: 自由飘 — 自己每有1层萌化，技能连击+N（PASSIVE）
    PASSIVE handler: 存 ability_state 中的 per 值，实际连击在 _h_damage 里计算。
    """
    ctx.user.ability_state["cute_hit_per_stack"] = tag.params.get("per", 2)



def _h_cute_bench_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """CUTE_BENCH_COST_REDUCE: 友方场下每有1层萌化，入场时全能耗-1（守护者特性 ON_ENTER）"""
    state = ctx.state
    team = getattr(ctx, "team", "a")
    bench = state.team_a if team == "a" else state.team_b
    total = sum(p.cute_stacks for p in bench if p is not ctx.user and not p.is_fainted)
    if total > 0:
        for s in ctx.user.skills:
            s.energy_cost = max(0, s.energy_cost - total)



