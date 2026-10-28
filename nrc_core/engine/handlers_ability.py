"""特性触发与常规被动效果处理器。"""

from typing import TYPE_CHECKING
from nrc_core.effect_models import E, EffectTag, Timing, SkillTiming, SkillEffect
from nrc_core.rng import choice as rng_choice, shuffle as rng_shuffle
from nrc_core.engine.context import (
    Ctx,
)
from nrc_core.engine.helpers import (
    _apply_prince_promise,
    _promise_modifiers,
)
from nrc_core.engine.handlers_field import (
    DEVOTION_TYPES,
)
from nrc_core.engine.handlers_skill import (
    _mark_stacks,
)
from nrc_core.engine.helpers import (
    _adjust_cost_delta,
    _apply_buff,
    _apply_matching_skill_mods,
    _iter_flat_tags_static,
    _record_public_skill_modifier,
)

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


def _h_ability_compute(tag: EffectTag, ctx: Ctx) -> None:
    """ABILITY_COMPUTE: 运行时计算并存入 pokemon.ability_state"""
    action = tag.params.get("action", "")
    pokemon = ctx.user

    if action == "multiple_borrow":
        pokemon.ability_state["multiple_borrow"] = True

    elif action in {"magic_hat", "sleep_context", "context_time_buff", "autumn_harvest"}:
        pokemon.ability_state[action] = True

    elif action == "prince_promise":
        current = _promise_modifiers(pokemon)
        previous = pokemon.ability_state.get("prince_promise_snapshot")
        if previous is not None:
            _apply_prince_promise(pokemon, previous, ctx.state.turn)
        pokemon.ability_state["prince_promise_snapshot"] = current

    elif action == "count_poison_skills":
        from nrc_core.models import TYPE_NAME_MAP as _TYPE_MAP
        from nrc_core.models import Type, has_type
        count = sum(1 for s in pokemon.skills if s.skill_type == Type.POISON)
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["poison_skill_count"] = count

    elif action == "modify_matching_skills":
        _apply_matching_skill_mods(pokemon, ctx.target, tag.params)

    elif action == "shared_wing_skills":
        from nrc_core.models import Type, has_type
        team_list = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
        my_skills = {s.name for s in pokemon.skills}
        shared = set()
        for p in team_list:
            if p.name == pokemon.name:
                continue
            if has_type(p, Type.FLYING):
                for s in p.skills:
                    if s.name in my_skills:
                        shared.add(s.name)
        for s in pokemon.skills:
            if s.name in shared:
                s.agility = True
                if getattr(s, "effects", None):
                    if not any(e.type == E.AGILITY for e in _iter_flat_tags_static(s.effects)):
                        if isinstance(s.effects[0], SkillEffect):
                            # Insert AGILITY into the first ON_USE SE
                            for se in s.effects:
                                if se.timing == SkillTiming.ON_USE:
                                    se.effects.insert(0, EffectTag(E.AGILITY))
                                    break
                            else:
                                s.effects.insert(0, SkillEffect(SkillTiming.ON_USE, [EffectTag(E.AGILITY)]))
                        else:
                            s.effects.insert(0, EffectTag(E.AGILITY))

    elif action == "grant_first_skill_agility":
        # 给第一个技能添加迅捷标记
        if pokemon.skills:
            first_skill = pokemon.skills[0]
            first_skill.agility = True
            # 如果技能有 effects 框架，添加 AGILITY 标记
            if getattr(first_skill, "effects", None) and isinstance(first_skill.effects, list):
                # 检查是否已有 AGILITY
                has_agility = any(
                    e.type == E.AGILITY for e in _iter_flat_tags_static(first_skill.effects)
                )
                if not has_agility:
                    if isinstance(first_skill.effects[0], SkillEffect):
                        for se in first_skill.effects:
                            if se.timing == SkillTiming.ON_USE:
                                se.effects.insert(0, EffectTag(E.AGILITY))
                                break
                        else:
                            first_skill.effects.insert(0, SkillEffect(SkillTiming.ON_USE, [EffectTag(E.AGILITY)]))
                    else:
                        first_skill.effects.insert(0, EffectTag(E.AGILITY))

    elif action == "first_strike_power_bonus":
        # 标记 Pokemon 在先手时应用威力提升（需要在 battle.py 中检查并应用）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["first_strike_power_bonus"] = tag.params.get("bonus_pct", 0.0)

    elif action == "first_strike_hit_bonus":
        # 标记 Pokemon 在先手时应用连击数提升（需要在 battle.py 中检查并应用）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["first_strike_hit_bonus"] = True

    elif action == "auto_switch_on_zero_energy":
        # 标记能量为0时自动换人（需要在 battle.py 中检查并触发）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["auto_switch_zero_energy"] = True

    elif action == "auto_switch_every_turn":
        # 标记每回合末自动换人（需要在 battle.py 中检查并触发）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["auto_switch_every_turn"] = True

    elif action == "swap_ally_on_zero_energy":
        # 标记能量为0时替换队友入场（需要在 battle.py 中检查并触发）
        if not hasattr(pokemon, "ability_state"):
            pokemon.ability_state = {}
        pokemon.ability_state["swap_ally_zero_energy"] = True

    # ── 第四轮技能修复: 特殊action ──

    elif action == "swap_hp_ratio":
        # 恶念交换：与敌方交换生命比例
        target = ctx.target
        if pokemon.hp > 0 and target.hp > 0:
            my_ratio = pokemon.current_hp / pokemon.hp
            enemy_ratio = target.current_hp / target.hp
            pokemon.current_hp = max(1, int(pokemon.hp * enemy_ratio))
            target.current_hp = max(1, int(target.hp * my_ratio))

    elif action == "swap_buffs":
        # 欺诈契约：与敌方交换增益和减益
        target = ctx.target
        for attr in ("atk_up", "atk_down", "def_up", "def_down",
                     "spatk_up", "spatk_down", "spdef_up", "spdef_down",
                     "speed_up", "speed_down"):
            my_val = getattr(pokemon, attr, 0.0)
            enemy_val = getattr(target, attr, 0.0)
            setattr(pokemon, attr, enemy_val)
            setattr(target, attr, my_val)

    elif action == "swap_skills":
        # 隐藏条款：与敌方交换携带的技能
        target = ctx.target
        pokemon.skills, target.skills = target.skills, pokemon.skills

    elif action == "borrow_ally_skill":
        # 借用：变成己方其他精灵的随机技能
        team_list = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
        current_idx = ctx.state.current_a if ctx.team == "a" else ctx.state.current_b
        ally_skills = []
        for i, p in enumerate(team_list):
            if i != current_idx and not p.is_fainted:
                ally_skills.extend(p.skills)
        if ally_skills:
            borrow_slots = [
                i for i, s in enumerate(pokemon.skills)
                if s.name == "借用" or getattr(s, "random_source", "") == "借用"
            ]
            if not pokemon.ability_state.get("multiple_borrow"):
                borrow_slots = borrow_slots[:1]
            for slot in borrow_slots:
                chosen = rng_choice(ally_skills).copy()
                chosen.random_source = "借用"
                if pokemon.ability_state.get("multiple_borrow"):
                    from nrc_core.models import Type
                    if chosen.skill_type != Type.PSYCHIC:
                        chosen.energy_cost = max(0, chosen.energy_cost - 2)
                pokemon.skills[slot] = chosen

    elif action == "copy_enemy_skill":
        # 取念：变成敌方随机技能，能耗-2
        target = ctx.target
        enemy_team = ctx.state.team_b if ctx.team == "a" else ctx.state.team_a
        enemy_skills = []
        for p in enemy_team:
            if not p.is_fainted:
                enemy_skills.extend(p.skills)
        if enemy_skills:
            slots = [
                i for i, s in enumerate(pokemon.skills)
                if s.name == "取念" or getattr(s, "random_source", "") == "取念"
            ]
            if not pokemon.ability_state.get("multiple_borrow"):
                slots = slots[:1]
            for slot in slots:
                chosen = rng_choice(enemy_skills).copy()
                chosen.random_source = "取念"
                cost_reduce = tag.params.get("cost_reduce", 2)
                chosen.energy_cost = max(0, chosen.energy_cost - cost_reduce)
                if pokemon.ability_state.get("multiple_borrow"):
                    from nrc_core.models import Type
                    if chosen.skill_type != Type.PSYCHIC:
                        chosen.energy_cost = max(0, chosen.energy_cost - 2)
                pokemon.skills[slot] = chosen

    elif action == "copy_random_skill":
        # 复写：变成自己未携带的随机技能，能耗-2
        current_names = {s.name for s in pokemon.skills}
        all_skills = ctx.state.catalog.all_skills() if ctx.state.catalog is not None else {}
        all_names = list(all_skills)
        candidates = [n for n in all_names if n not in current_names]
        if candidates:
            slots = [
                i for i, s in enumerate(pokemon.skills)
                if s.name == "复写" or getattr(s, "random_source", "") == "复写"
            ]
            if not pokemon.ability_state.get("multiple_borrow"):
                slots = slots[:1]
            for slot in slots:
                chosen = all_skills.get(rng_choice(candidates))
                if chosen is None:
                    continue
                replacement = chosen.copy()
                cost_reduce = tag.params.get("cost_reduce", 2)
                replacement.energy_cost = max(0, replacement.energy_cost - cost_reduce)
                replacement.random_source = "复写"
                if pokemon.ability_state.get("multiple_borrow"):
                    from nrc_core.models import Type
                    if replacement.skill_type != Type.PSYCHIC:
                        replacement.energy_cost = max(0, replacement.energy_cost - 2)
                pokemon.skills[slot] = replacement

    elif action == "double_enemy_burn_and_tick":
        # 充分燃烧：敌方灼烧翻倍+触发1次灼烧伤害
        target = ctx.target
        if target.burn_stacks > 0:
            target.burn_stacks *= 2
            dmg = int(target.hp * 0.04 * target.burn_stacks)
            target.current_hp -= max(1, dmg)
            if target.current_hp <= 0:
                target.current_hp = 0
                from nrc_core.models import StatusType
                target.status = StatusType.FAINTED

    elif action == "double_enemy_debuffs":
        # 落井下毒：敌方所有减益层数翻倍
        target = ctx.target
        target.atk_down *= 2
        target.def_down *= 2
        target.spatk_down *= 2
        target.spdef_down *= 2
        target.speed_down *= 2
        target.poison_stacks *= 2
        target.burn_stacks *= 2

    elif action == "grant_random_devotion":
        # 虫群智慧：随机获得N次奉献
        count = tag.params.get("count", 2)
        from nrc_core.engine.handlers_field import DEVOTION_TYPES
        team = ctx.team
        devotion = ctx.state._get_devotion(team)
        for _ in range(count):
            chosen = rng_choice(DEVOTION_TYPES)
            devotion[chosen] = devotion.get(chosen, 0) + 1

    elif action == "cast_all_normal_skills_double_cost":
        # 荟萃：释放所有普通系技能（能耗翻倍）— 标记，由battle.py执行
        pokemon.ability_state["cast_all_normal_double_cost"] = True

    elif action == "anti_heal":
        # 伪造账单：标记本回合敌方回复变为失去
        multiplier = tag.params.get("multiplier", 2)
        ctx.target.ability_state["anti_heal_multiplier"] = multiplier



def _h_ability_increment_counter(tag: EffectTag, ctx: Ctx) -> None:
    """ABILITY_INCREMENT_COUNTER: 海豹船长计数+1"""
    if ctx.team == "a":
        ctx.state.counter_count_a += 1
    else:
        ctx.state.counter_count_b += 1



def _h_transfer_mods(tag: EffectTag, ctx: Ctx) -> None:
    """TRANSFER_MODS: 洁癖离场时保存属性修正，存入 result 供 battle.py 传递。
    从 _snapshot_mods（on_switch_out 前的快照）读取，因为 on_switch_out 已清零 buff。"""
    snapshot = ctx.result.get("_snapshot_mods")
    if snapshot:
        ctx.result["transfer_mods"] = dict(snapshot)
    else:
        # fallback：直接从精灵读（可能已被清零）
        pokemon = ctx.user
        ctx.result["transfer_mods"] = {
            "atk_up": pokemon.atk_up, "atk_down": pokemon.atk_down,
            "def_up": pokemon.def_up, "def_down": pokemon.def_down,
            "spatk_up": pokemon.spatk_up, "spatk_down": pokemon.spatk_down,
            "spdef_up": pokemon.spdef_up, "spdef_down": pokemon.spdef_down,
            "speed_up": pokemon.speed_up, "speed_down": pokemon.speed_down,
        }



def _h_burn_no_decay(tag: EffectTag, ctx: Ctx) -> None:
    """BURN_NO_DECAY: 标记煤渣草在场，本回合灼烧不衰减"""
    ctx.result["burn_no_decay"] = True



def _h_power_multiplier_buff(tag: EffectTag, ctx: Ctx) -> None:
    """POWER_MULTIPLIER_BUFF: 独立威力提升乘法层，站场期间持续，下场重置"""
    ctx.user.power_multiplier *= tag.params.get("multiplier", 1.0)



def _h_threat_speed_buff(tag: EffectTag, ctx: Ctx) -> None:
    """THREAT_SPEED_BUFF: 预警/哨兵 — 敌方有击杀威胁时速度加成"""
    from nrc_core.battle import _has_ko_threat
    pokemon = ctx.user
    enemy = ctx.target
    # 清除上回合的临时标记
    pokemon.ability_state.pop("threat_speed_bonus_active", None)
    pokemon.ability_state.pop("force_switch_after_action", None)
    if _has_ko_threat(enemy, pokemon):
        speed_val = tag.params.get("speed", 0.5)
        pokemon.speed_up += speed_val
        pokemon.ability_state["threat_speed_bonus_active"] = True
        if tag.params.get("force_switch", False):
            pokemon.ability_state["force_switch_after_action"] = True



def _h_counter_accumulate_transform(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_ACCUMULATE_TRANSFORM: 保卫 — 应对成功计数，达阈值变身棋绮后"""
    from nrc_core.battle import _transform_to_guard_queen
    pokemon = ctx.user
    skill = ctx.result.get("_counter_skill") or getattr(ctx, "skill", None)
    # 按 category_filter 过滤（默认只有防御类技能触发）
    cat_filter = tag.params.get("category_filter", "")
    if cat_filter and skill:
        from nrc_core.models import SkillCategory
        cat_map = {
            "攻击": (SkillCategory.PHYSICAL, SkillCategory.MAGICAL),
            "防御": (SkillCategory.DEFENSE,),
            "状态": (SkillCategory.STATUS,),
        }
        allowed = cat_map.get(cat_filter, ())
        if allowed and skill.category not in allowed:
            return
    # 每回合只计数一次
    if pokemon.ability_state.get("guard_counter_turn") == ctx.state.turn:
        return
    pokemon.ability_state["guard_counter_turn"] = ctx.state.turn
    count = pokemon.ability_state.get("guard_counters", 0) + 1
    pokemon.ability_state["guard_counters"] = count
    threshold = tag.params.get("threshold", 2)
    if count >= threshold:
        pokemon.ability_state["guard_counters"] = 0
        defer = ctx.result.get("_defer_transform", False)
        if defer:
            pokemon.ability_state["guard_transform_pending"] = True
        else:
            _transform_to_guard_queen(pokemon)



def _h_delayed_revive(tag: EffectTag, ctx: Ctx) -> None:
    """DELAYED_REVIVE: 不朽 — 力竭时设置延迟复活计时器"""
    turns = tag.params.get("turns", 4)
    ctx.user.ability_state["undying_revive_in"] = turns



def _h_copy_switch_state(tag: EffectTag, ctx: Ctx) -> None:
    """COPY_SWITCH_STATE: 贪婪 — 敌方换人时复制离场精灵状态到入场精灵"""
    from nrc_core.battle import _transfer_pokemon_state
    context = ctx.result if isinstance(ctx.result, dict) else {}
    # context 由 battle.py 的 execute_ability 调用传入
    snapshot = context.get("switch_snapshot")
    switched_in = context.get("switched_in")
    if snapshot and switched_in:
        _transfer_pokemon_state(snapshot, switched_in)



def _h_cost_invert(tag: EffectTag, ctx: Ctx) -> None:
    """COST_INVERT: 对流 — 设置能耗反转被动标记"""
    ctx.user.ability_state["cost_invert"] = True



def _h_mirror_enemy_buffs(tag: EffectTag, ctx: Ctx) -> None:
    """MIRROR_ENEMY_BUFFS: 公平鸽「衡量」
    ON_ENTER: 复制敌方当前所有属性提升（*_up）和能量到自身；
              同时在 ctx.user 上设置 mirror_buff_to=None（清除旧引用），
              在 ctx.target 上设置 mirror_buff_to=ctx.user（在场同步钩子）。
    ON_LEAVE / on_switch_out: 在 battle.py 的 on_switch_out 里清除 mirror_buff_to。
    """
    me = ctx.user
    enemy = ctx.target
    if not me or not enemy:
        return

    # ── 入场：复制敌方当前所有增益 ──
    me.atk_up   = max(me.atk_up,   enemy.atk_up)
    me.def_up   = max(me.def_up,   enemy.def_up)
    me.spatk_up = max(me.spatk_up, enemy.spatk_up)
    me.spdef_up = max(me.spdef_up, enemy.spdef_up)
    me.speed_up = max(me.speed_up, enemy.speed_up)
    # 能量取最大值（但不超过上限10）
    me.energy = min(10, max(me.energy, enemy.energy))

    # ── 设置在场同步钩子 ──
    # enemy（对手）获得 buff 时，_apply_buff 会读 enemy.ability_state["mirror_buff_to"]
    # 然后把相同 buff 复制给 me
    enemy.ability_state["mirror_buff_to"] = me
    # 自己的 mirror_buff_to 清空（防止两边互相镜像）
    me.ability_state.pop("mirror_buff_to", None)



def _h_counter_success_double_damage(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_DOUBLE_DAMAGE: 应对成功后下一次伤害翻倍"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["double_damage_next"] = True



def _h_counter_success_buff_permanent(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_BUFF_PERMANENT: 应对成功后获得永久增益（指挥家）"""
    if not ctx.user:
        return
    _apply_buff(ctx.user, tag.params)



def _h_counter_success_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_POWER_BONUS: 应对成功后威力永久+N（斗技）"""
    if not ctx.user:
        return
    delta = tag.params.get("delta", 20)
    ctx.user.skill_power_bonus += delta



def _h_counter_success_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_COST_REDUCE: 应对成功后全技能能耗永久-N（思维之盾）"""
    if not ctx.user:
        return
    delta = tag.params.get("delta", 5)
    for s in ctx.user.skills:
        s.energy_cost = max(0, s.energy_cost - delta)



def _h_counter_success_speed_priority(tag: EffectTag, ctx: Ctx) -> None:
    """COUNTER_SUCCESS_SPEED_PRIORITY: 应对成功后速度优先级+1（野性感官）"""
    if not ctx.user:
        return
    ctx.user.priority_stage += 1



def _h_first_strike_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_STRIKE_POWER_BONUS: 先手攻击威力加成（破空/顺风）"""
    if not ctx.is_first:
        return
    
    bonus_pct = tag.params.get("bonus_pct", 0.5)
    if "power_multiplier" not in ctx.result:
        ctx.result["power_multiplier"] = 1.0
    ctx.result["power_multiplier"] *= (1.0 + bonus_pct)



def _h_first_strike_hit_count(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_STRIKE_HIT_COUNT: 先手攻击连击数+1（咔咔冲刺）"""
    if not ctx.is_first:
        return
    
    if not ctx.skill or not hasattr(ctx.skill, 'hit_count'):
        return
    
    ctx.skill.hit_count += 1



def _h_first_strike_agility(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_STRIKE_AGILITY: 首个技能获得迅捷（起飞加速）— ON_ENTER 时设 flag"""
    ctx.user.ability_state["first_skill_agility"] = True



def _h_auto_switch_on_zero_energy(tag: EffectTag, ctx: Ctx) -> None:
    """AUTO_SWITCH_ON_ZERO_ENERGY: 能量为0时自动换人（警惕）"""
    if ctx.user and ctx.user.energy <= 0:
        ctx.user.force_switch = True



def _h_auto_switch_after_action(tag: EffectTag, ctx: Ctx) -> None:
    """AUTO_SWITCH_AFTER_ACTION: 每个回合结束后自动换人（防过载保护）"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["auto_switch_eot"] = True



def _h_team_synergy_bug_swarm_attack(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BUG_SWARM_ATTACK: 虫群突袭 — 队伍每多1只虫系+15%攻击"""
    if not ctx.user or not ctx.state:
        return
    from nrc_core.models import Type, has_type
    user_team = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
    bug_count = 0
    for mon in user_team:
        if mon and mon != ctx.user and not mon.is_fainted and has_type(mon, Type.BUG):
            bug_count += 1
    bonus_pct = tag.params.get("bonus_pct", 0.15)
    total = bonus_pct * bug_count
    if total > 0:
        ctx.user.atk_up += total
        ctx.user.spatk_up += total



def _h_team_synergy_bug_swarm_inspire(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BUG_SWARM_INSPIRE: 虫群鼓舞 — 队伍每多1只虫系+10%攻击"""
    if not ctx.user or not ctx.state:
        return
    from nrc_core.models import Type, has_type
    user_team = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
    bug_count = 0
    for mon in user_team:
        if mon and mon != ctx.user and not mon.is_fainted and has_type(mon, Type.BUG):
            bug_count += 1
    bonus_pct = tag.params.get("bonus_pct", 0.1)
    total = bonus_pct * bug_count
    if total > 0:
        ctx.user.atk_up += total
        ctx.user.spatk_up += total



def _h_team_synergy_brave_if_bugs(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BRAVE_IF_BUGS: 壮胆 — 队伍有虫系时攻击+50%"""
    if not ctx.user or not ctx.state:
        return
    from nrc_core.models import Type, has_type
    user_team = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
    has_bugs = any(mon and mon != ctx.user and not mon.is_fainted and has_type(mon, Type.BUG)
                   for mon in user_team)
    if has_bugs:
        bonus_pct = tag.params.get("bonus_pct", 0.5)
        ctx.user.atk_up += bonus_pct
        ctx.user.spatk_up += bonus_pct



def _h_team_synergy_bug_kill_aff(tag: EffectTag, ctx: Ctx) -> None:
    """TEAM_SYNERGY_BUG_KILL_AFF: 振奋虫心 - +5 aff on team kill (ON_KILL)"""
    if ctx.user and ctx.user.ability_state is not None:
        aff_bonus = tag.params.get("aff_bonus", 5)
        ctx.user.ability_state["aff_bonus"] = aff_bonus



def _h_stat_scale_defense_per_energy(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_DEFENSE_PER_ENERGY: 囤积 - +10% defense per energy"""
    if not ctx.user:
        return
    bonus_pct_per_energy = tag.params.get("bonus_pct_per_energy", 0.1)
    multiplier = 1.0 + (bonus_pct_per_energy * ctx.user.energy)
    if "stat_multiplier" not in ctx.result:
        ctx.result["stat_multiplier"] = {}
    ctx.result["stat_multiplier"]["def"] = multiplier



def _h_stat_scale_hits_per_hp_lost(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_HITS_PER_HP_LOST: 嫁祸 — 每损失25%HP连击+2"""
    if not ctx.user:
        return
    max_hp = ctx.user.hp if ctx.user.hp > 0 else 1
    hp_lost_pct = (max_hp - ctx.user.current_hp) / max_hp
    quarters_lost = int(hp_lost_pct * 4)  # 0-4
    hits_per_quarter = tag.params.get("hits_per_quarter", 2)
    extra_hits = quarters_lost * hits_per_quarter
    if extra_hits > 0:
        ctx.user.hit_count_mod += extra_hits



def _h_stat_scale_attack_decay(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_ATTACK_DECAY: 全神贯注 - +100% attack, -20% per action"""
    if not ctx.user or ctx.user.ability_state is None:
        return
    init_bonus = tag.params.get("init_bonus", 1.0)
    decay_per_action = tag.params.get("decay_per_action", 0.2)
    action_count = ctx.user.ability_state.get("action_count", 0)
    bonus = init_bonus - (decay_per_action * action_count)
    bonus = max(bonus, 0)  # Never go negative
    if "stat_multiplier" not in ctx.result:
        ctx.result["stat_multiplier"] = {}
    ctx.result["stat_multiplier"]["atk"] = 1.0 + bonus



def _h_stat_scale_meteor_marks_per_turn(tag: EffectTag, ctx: Ctx) -> None:
    """STAT_SCALE_METEOR_MARKS_PER_TURN: 吸积盘 - +2 meteor marks per turn (ON_TURN_END)"""
    if ctx.user and ctx.user.ability_state is not None:
        marks_per_turn = tag.params.get("marks_per_turn", 2)
        ctx.user.ability_state["meteor_mark_add"] = marks_per_turn



def _h_mark_power_per_meteor(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_POWER_PER_METEOR: 坠星/观星 - +15% power per meteor mark"""
    if not ctx.target:
        return
    # Get meteor mark count on target (enemy)
    enemy_marks = ctx.state.marks_b if ctx.team == "a" else ctx.state.marks_a
    meteor_count = _mark_stacks(enemy_marks, "meteor_mark")
    bonus_pct_per_mark = tag.params.get("bonus_pct_per_mark", 0.15)
    multiplier = 1.0 + (bonus_pct_per_mark * meteor_count)
    if "power_multiplier" not in ctx.result:
        ctx.result["power_multiplier"] = 1.0
    ctx.result["power_multiplier"] *= multiplier



def _h_mark_freeze_to_meteor(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_FREEZE_TO_METEOR: 月牙雪糕 - Freeze = meteor mark"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["freeze_becomes_meteor"] = True



def _h_mark_stack_no_replace(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_STACK_NO_REPLACE: 吟游之弦 - Marks stack (don't replace)"""
    if ctx.user and ctx.user.ability_state is not None:
        ctx.user.ability_state["mark_stack_additive"] = True



def _h_mark_stack_debuffs(tag: EffectTag, ctx: Ctx) -> None:
    """MARK_STACK_DEBUFFS: 灰色肖像 - Stack enemy debuffs +3"""
    if ctx.target and ctx.target.ability_state is not None:
        stack_bonus = tag.params.get("stack_bonus", 3)
        ctx.target.ability_state["debuff_stack_bonus"] = stack_bonus



def _h_damage_mod_non_stab(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_NON_STAB: 涂鸦 - +50% non-STAB power"""
    if not ctx.user or not ctx.skill:
        return
    # Check if skill is STAB (same type as either of user's types)
    if ctx.skill.type not in (ctx.user.type1, ctx.user.type2):
        bonus_pct = tag.params.get("bonus_pct", 0.5)
        if "power_multiplier" not in ctx.result:
            ctx.result["power_multiplier"] = 1.0
        ctx.result["power_multiplier"] *= (1.0 + bonus_pct)



def _h_damage_mod_non_light(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_NON_LIGHT: 目空 - +25% non-light power"""
    if not ctx.skill:
        return
    # Type.LIGHT = 18 (or check by name)
    from .types import Type
    if ctx.skill.type != Type.LIGHT:
        bonus_pct = tag.params.get("bonus_pct", 0.25)
        if "power_multiplier" not in ctx.result:
            ctx.result["power_multiplier"] = 1.0
        ctx.result["power_multiplier"] *= (1.0 + bonus_pct)



def _h_damage_mod_non_weakness(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_NON_WEAKNESS: 绒粉星光 - +100% vs non-weakness"""
    if not ctx.user or not ctx.skill or not ctx.target:
        return
    from .types import get_type_effectiveness
    # Check effectiveness
    effectiveness = get_type_effectiveness(ctx.skill.type, ctx.target.type1, ctx.target.type2)
    if effectiveness <= 1.0:  # Not super-effective
        bonus_pct = tag.params.get("bonus_pct", 1.0)
        if "power_multiplier" not in ctx.result:
            ctx.result["power_multiplier"] = 1.0
        ctx.result["power_multiplier"] *= (1.0 + bonus_pct)



def _h_damage_mod_pollutant_blood(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_POLLUTANT_BLOOD: 天通地明 - +100% vs pollutant blood (特定敌方血脉)"""
    if ctx.target and ctx.target.ability_state is not None:
        bloodlines = ctx.target.ability_state.get("lab_metadata", {}).get("bloodline_attributes") or []
        if (ctx.target.ability_state.get("blood_type") == "pollutant"
                or "污染血脉" in bloodlines):
            bonus_pct = tag.params.get("bonus_pct", 1.0)
            ctx.result["_power_mult"] = ctx.result.get("_power_mult", 1.0) + bonus_pct



def _h_damage_mod_leader_blood(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_MOD_LEADER_BLOOD: 月光审判 - +100% vs leader blood (特定敌方血脉)"""
    if ctx.target and ctx.target.ability_state is not None:
        bloodlines = ctx.target.ability_state.get("lab_metadata", {}).get("bloodline_attributes") or []
        if (ctx.target.ability_state.get("blood_type") == "leader"
                or "首领血脉" in bloodlines):
            bonus_pct = tag.params.get("bonus_pct", 1.0)
            ctx.result["_power_mult"] = ctx.result.get("_power_mult", 1.0) + bonus_pct



def _h_damage_resist_same_type(tag: EffectTag, ctx: Ctx) -> None:
    """DAMAGE_RESIST_SAME_TYPE: 偏振 - -40% from same-type attacks"""
    if not ctx.user or not ctx.skill:
        return
    # If enemy uses same type attack, reduce damage
    if ctx.skill.type == ctx.user.type1 or ctx.skill.type == ctx.user.type2:
        resist_pct = tag.params.get("resist_pct", 0.4)
        if "damage_reduction" not in ctx.result:
            ctx.result["damage_reduction"] = 0
        ctx.result["damage_reduction"] += resist_pct



def _h_heal_per_turn(tag: EffectTag, ctx: Ctx) -> None:
    """HEAL_PER_TURN: 生长 — 设置回合结束回血比例（由 battle.py turn_end_effects 结算）"""
    if not ctx.user:
        return
    heal_pct = tag.params.get("heal_pct", 0.12)
    ctx.user.ability_state["heal_per_turn_pct"] = heal_pct



def _h_heal_on_grass_skill(tag: EffectTag, ctx: Ctx) -> None:
    """HEAL_ON_GRASS_SKILL: 深层氧循环 — 使用草系技能后回血"""
    if not ctx.user or not ctx.result.get("skill"):
        return
    skill_obj = ctx.result.get("skill")
    from nrc_core.models import Type
    if not hasattr(skill_obj, "skill_type") or skill_obj.skill_type != Type.GRASS:
        return
    heal_pct = tag.params.get("heal_pct", 0.15)
    heal = int(ctx.user.hp * heal_pct)
    anti = ctx.user.ability_state.get("anti_heal_multiplier", 0)
    if anti:
        ctx.user.current_hp = max(0, ctx.user.current_hp - max(1, heal))
    else:
        ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + max(1, heal))



def _h_skill_cost_reduction_type(tag: EffectTag, ctx: Ctx) -> None:
    """SKILL_COST_REDUCTION_TYPE: 缩壳 - -2 cost on defense skills"""
    if not ctx.skill:
        return
    # Check if skill is defensive type (category == "防御")
    skill_category = getattr(ctx.skill, 'category', None)
    if skill_category != "防御":
        return
    cost_reduction = tag.params.get("cost_reduction", 2)
    if "cost_reduction" not in ctx.result:
        ctx.result["cost_reduction"] = 0
    ctx.result["cost_reduction"] += cost_reduction



def _h_poison_stat_debuff(tag: EffectTag, ctx: Ctx) -> None:
    """POISON_STAT_DEBUFF: 毒牙 — 敌方有中毒时，降低其魔攻/魔防"""
    if not ctx.target or ctx.target.poison_stacks <= 0:
        return
    spatk_red = tag.params.get("spatk_reduction", 0.4)
    spdef_red = tag.params.get("spdef_reduction", 0.4)
    ctx.target.spatk_down += spatk_red
    ctx.target.spdef_down += spdef_red



def _h_poison_on_skill_apply(tag: EffectTag, ctx: Ctx) -> None:
    """POISON_ON_SKILL_APPLY: 毒腺 — 使用能耗<阈值的技能后敌方获得中毒"""
    skill = ctx.skill or ctx.result.get("skill")
    if not skill:
        return
    cost_threshold = tag.params.get("cost_threshold", 5)
    actual_cost = getattr(skill, "_base_energy_cost", skill.energy_cost)
    if actual_cost >= cost_threshold:
        return
    poison_stacks = tag.params.get("poison_stacks", 4)
    if ctx.target:
        ctx.target.poison_stacks += poison_stacks



def _h_freeze_immunity_and_buff(tag: EffectTag, ctx: Ctx) -> None:
    """FREEZE_IMMUNITY_AND_BUFF: 吉利丁片 — 入场双防+20% + 冻结免疫"""
    if not ctx.user:
        return
    def_bonus = tag.params.get("def_bonus", 0.2)
    ctx.user.def_up += def_bonus
    ctx.user.spdef_up += def_bonus
    ctx.user.ability_state["freeze_immune"] = True



def _h_extra_freeze_on_freeze(tag: EffectTag, ctx: Ctx) -> None:
    """EXTRA_FREEZE_ON_FREEZE: 加个雪球 — 敌方获得冻结时额外+N层"""
    # 固定规则由 add_freeze_stacks 读取特性定义，不能转成可累加运行时状态。
    pass



def _h_extra_consumption_on_freeze(tag: EffectTag, ctx: Ctx) -> None:
    """EXTRA_CONSUMPTION_ON_FREEZE: 冻结敌方时额外+1层能耗增加"""
    if ctx.result.get("_ability_timing") != Timing.ON_INFLICT_FREEZE.name:
        return
    if ctx.result.get("freeze_stacks_added", 0) <= 0:
        return
    delta = _adjust_cost_delta(ctx.target, int(tag.params.get("extra", 1)))
    for skill in ctx.target.skills:
        skill.energy_cost = max(0, skill.energy_cost + delta)



def _h_faint_no_mp_loss(tag: EffectTag, ctx: Ctx) -> None:
    """FAINT_NO_MP_LOSS: 诈死 — 力竭时不扣MP"""
    ctx.user.ability_state["faint_no_mp_loss"] = True



def _h_on_skill_element_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_BUFF: 使用某系技能后获得buff（助燃/爆燃）"""
    buff = tag.params.get("buff", {})
    if buff:
        _apply_buff(ctx.user, buff)



def _h_on_skill_element_poison(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_POISON: 使用某系技能后敌方中毒（生物碱）"""
    stacks = tag.params.get("stacks", 2)
    ctx.target.poison_stacks += stacks



def _h_on_skill_element_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_COST_REDUCE: 使用某系技能后全能耗-N（浸润/浪潮）"""
    reduce = tag.params.get("reduce", 1)
    for s in ctx.user.skills:
        s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))



def _h_on_skill_element_heal(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_HEAL: 使用某系技能后回血（氧循环）"""
    heal_pct = tag.params.get("heal_pct", 0.1)
    heal = int(ctx.user.hp * heal_pct)
    anti = ctx.user.ability_state.get("anti_heal_multiplier", 0)
    if anti:
        ctx.user.current_hp = max(0, ctx.user.current_hp - heal)
    elif heal > 0:
        ctx.user.current_hp = min(ctx.user.hp, ctx.user.current_hp + heal)



def _h_on_skill_element_enemy_energy(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SKILL_ELEMENT_ENEMY_ENERGY: 使用某系技能后敌方失去能量（碰瓷）"""
    amount = tag.params.get("amount", 2)
    ctx.target.energy = max(0, ctx.target.energy - amount)



def _h_carry_skill_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """CARRY_SKILL_POWER_BONUS: 携带某条件技能威力+N%（勇敢）
    Store in ability_state for damage calc to pick up.
    """
    ctx.user.ability_state["carry_skill_power_bonus"] = {
        "condition": tag.params.get("condition", "cost_gt"),
        "value": tag.params.get("value", 3),
        "bonus_pct": tag.params.get("bonus_pct", 0.4),
    }



def _h_carry_skill_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """CARRY_SKILL_COST_REDUCE: 携带某类技能能耗-N"""
    from nrc_core.models import SkillCategory as SC
    category = tag.params.get("category", "")
    reduce = tag.params.get("reduce", 2)
    for s in ctx.user.skills:
        match = False
        if category == "defense" and s.category == SC.DEFENSE:
            match = True
        elif category == "attack" and s.category in (SC.PHYSICAL, SC.MAGICAL):
            match = True
        elif category == "status" and s.category == SC.STATUS:
            match = True
        elif not category:
            match = True
        if match:
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))



def _h_carry_element_count_buff(tag: EffectTag, ctx: Ctx) -> None:
    """CARRY_ELEMENT_COUNT_BUFF: 每携带N个某系技能获得效果（消波块）"""
    from nrc_core.models import TYPE_NAME_MAP as _TYPE_MAP
    element = tag.params.get("element", "")
    per_skill = tag.params.get("per_skill", {})
    target_type = _TYPE_MAP.get(element)
    count = sum(1 for s in ctx.user.skills if s.skill_type == target_type) if target_type else 0
    if count > 0 and per_skill:
        cost_reduce = per_skill.get("cost_reduce", 0) * count
        target_element = per_skill.get("target_element", "")
        target_skill_type = _TYPE_MAP.get(target_element)
        if cost_reduce and target_skill_type:
            for s in ctx.user.skills:
                if s.skill_type == target_skill_type:
                    s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -cost_reduce))



def _h_on_kill_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ON_KILL_BUFF: 击败敌方后获得buff（恶魔的晚宴）— ON_KILL 时机已确认击败"""
    buff = tag.params.get("buff", {})
    if buff and ctx.user:
        _apply_buff(ctx.user, buff)



def _h_recoil_damage(tag: EffectTag, ctx: Ctx) -> None:
    """RECOIL_DAMAGE: 受到攻击时反弹固定伤害（刺肤）"""
    power = tag.params.get("power", 50)
    dmg = max(1, int(power))
    if not ctx.target.is_fainted:
        ctx.target.current_hp -= dmg
        if ctx.target.current_hp <= 0:
            ctx.target.current_hp = 0
            from nrc_core.models import StatusType
            ctx.target.status = StatusType.FAINTED



def _h_entry_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ENTRY_BUFF: 入场时获得buff（专注力等）"""
    buff = tag.params.get("buff", {})
    duration = tag.params.get("duration", 0)
    if buff:
        _apply_buff(ctx.user, buff)
    if duration:
        ctx.user.ability_state["entry_buff_duration"] = duration
        ctx.user.ability_state["entry_buff_keys"] = list(buff.keys())



def _h_on_enter_grant_drain(tag: EffectTag, ctx: Ctx) -> None:
    """ON_ENTER_GRANT_DRAIN: 入场时获得吸血（渴求）"""
    pct = tag.params.get("pct", 0.5)
    ctx.user.life_drain_mod += pct



def _h_enemy_all_cost_up(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_ALL_COST_UP: 在场时敌方全技能能耗+N（冰封）"""
    amount = tag.params.get("amount", 1)
    for s in ctx.target.skills:
        s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, amount))



def _h_entry_freeze_extra(tag: EffectTag, ctx: Ctx) -> None:
    """ENTRY_FREEZE_EXTRA: 入场时冻结+额外能耗增加（抓到你了）"""
    freeze = tag.params.get("freeze", 2)
    extra_cost_up = tag.params.get("extra_cost_up", 1)
    from nrc_core.models import add_freeze_stacks
    add_freeze_stacks(ctx.target, freeze, ctx.user, state=ctx.state, team=ctx.team)
    if extra_cost_up:
        for s in ctx.target.skills:
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.target, extra_cost_up))



def _h_leave_heal_ally(tag: EffectTag, ctx: Ctx) -> None:
    """LEAVE_HEAL_ALLY: 离场后替换精灵回血（茶多酚）"""
    heal_pct = tag.params.get("heal_pct", 0.2)
    ctx.result["leave_heal_ally"] = heal_pct



def _h_leave_buff_ally(tag: EffectTag, ctx: Ctx) -> None:
    """LEAVE_BUFF_ALLY: 离场后替换精灵获得buff（美拉德反应）"""
    buff = tag.params.get("buff", {})
    ctx.result["leave_buff_ally"] = buff



def _h_leave_energy_refill(tag: EffectTag, ctx: Ctx) -> None:
    """LEAVE_ENERGY_REFILL: 离场时回复能量（快充）"""
    amount = tag.params.get("amount", 10)
    ctx.user.gain_energy(amount)



def _h_energy_regen_per_turn(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_REGEN_PER_TURN: 回合结束回复能量（养分重吸收）"""
    amount = tag.params.get("amount", 3)
    ctx.user.gain_energy(amount)



def _h_steal_all_enemy_energy(tag: EffectTag, ctx: Ctx) -> None:
    """STEAL_ALL_ENEMY_ENERGY: 回合结束偷取敌方全队能量（毒蘑菇）"""
    amount = tag.params.get("amount", 1)
    enemy_team = ctx.state.team_b if ctx.team == "a" else ctx.state.team_a
    for p in enemy_team:
        if not p.is_fainted:
            stolen = min(p.energy, amount)
            p.energy = max(0, p.energy - amount)
            ctx.user.gain_energy(stolen)



def _h_enemy_switch_debuff(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_SWITCH_DEBUFF: 敌方换人后对入场者施加效果（做噩梦/下黑手）"""
    if tag.params.get("energy_loss"):
        ctx.target.energy = max(0, ctx.target.energy - tag.params["energy_loss"])
    if tag.params.get("poison"):
        ctx.target.poison_stacks += tag.params["poison"]



def _h_enemy_switch_self_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_SWITCH_SELF_COST_REDUCE: 敌方换人时自己全技能能耗-N（珊瑚骨）"""
    reduce = tag.params.get("reduce", 3)
    for s in ctx.user.skills:
        s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -reduce))



def _h_on_interrupt_cooldown(tag: EffectTag, ctx: Ctx) -> None:
    """ON_INTERRUPT_COOLDOWN: 打断敌方时被打断技能进入冷却（威慑）"""
    turns = tag.params.get("turns", 2)
    ctx.user.ability_state["interrupt_cooldown_turns"] = turns



def _h_low_cost_skill_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """LOW_COST_SKILL_POWER_BONUS: 能耗≤N的技能威力+M%（挺起胸脯）"""
    ctx.user.ability_state["low_cost_skill_power_bonus"] = {
        "cost_threshold": tag.params.get("cost_threshold", 1),
        "bonus_pct": tag.params.get("bonus_pct", 0.5),
    }



def _h_energy_cost_condition_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_COST_CONDITION_BUFF: 使用能耗为N的技能时获得buff（鼓气/三鼓作气）"""
    cost = tag.params.get("cost", 0)
    buff = tag.params.get("buff", {})
    permanent = tag.params.get("permanent", False)
    skill = ctx.skill or ctx.result.get("skill")
    if skill and getattr(skill, "_base_energy_cost", skill.energy_cost) == cost:
        if buff:
            _apply_buff(ctx.user, buff)



def _h_enemy_tech_total_power(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_TECH_TOTAL_POWER: 敌方技能总能耗越多自己越强（冰钻）"""
    ctx.user.ability_state["enemy_tech_total_power"] = {
        "bonus_pct_per_cost": tag.params.get("bonus_pct_per_cost", 0.1),
    }



def _h_half_meteor_full_damage(tag: EffectTag, ctx: Ctx) -> None:
    """HALF_METEOR_FULL_DAMAGE: 星陨只消耗一半层数但满伤（守望星）"""
    ctx.user.ability_state["half_meteor_full_damage"] = True



def _h_energy_drain_by_cost_diff(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_DRAIN_BY_COST_DIFF: 石天平 — 回合结束，若己方上回合技能能耗高于敌方，
    敌方失去等于能耗差值的能量。
    利用 ability_state 中 last_skill_cost (由 battle.py 记录) 来判断。
    """
    my_cost = ctx.user.ability_state.get("last_skill_cost", 0)
    enemy_cost = ctx.target.ability_state.get("last_skill_cost", 0)
    diff = my_cost - enemy_cost
    if diff > 0:
        ctx.target.energy = max(0, ctx.target.energy - diff)



def _h_entry_buff_per_skill_count(tag: EffectTag, ctx: Ctx) -> None:
    """ENTRY_BUFF_PER_SKILL_COUNT: 入场时按全局技能计数给加成。
    params:
      count_key: str — 计数键（系别名如"水"/"火"，或类别名如"状态"/"防御"）
      per_count: dict — 每次计数的效果:
        cost_reduce: int — 全技能能耗-N
        power_pct: float — 威力+N%
        buff: dict — 属性加成
        grant_agility: bool — 获得迅捷
      element_filter: list — 只对某些系别技能生效（可选）
    """
    from nrc_core.models import TYPE_NAME_MAP as _TYPE_MAP
    counts = ctx.state.skill_use_counts_a if ctx.team == "a" else ctx.state.skill_use_counts_b
    count_key = tag.params.get("count_key", "")
    count_keys = tag.params.get("count_keys", [])
    if count_keys:
        count = sum(counts.get(k, 0) for k in count_keys)
    else:
        count = counts.get(count_key, 0)
    if count <= 0:
        return

    per = tag.params.get("per_count", {})
    element_filter = tag.params.get("element_filter", [])
    filter_types = {_TYPE_MAP.get(el) for el in element_filter} if element_filter else set()

    # cost_reduce: 全技能或特定系能耗-N×count
    cost_reduce = per.get("cost_reduce", 0)
    if cost_reduce:
        total_reduce = cost_reduce * count
        for s in ctx.user.skills:
            if filter_types and s.skill_type not in filter_types:
                continue
            s.energy_cost = max(0, s.energy_cost + _adjust_cost_delta(ctx.user, -total_reduce))

    # power_pct: 威力+N%×count
    power_pct = per.get("power_pct", 0.0)
    power_bonus = per.get("power_bonus", 0)
    before_power = [s.power for s in ctx.user.skills]
    if power_pct or power_bonus:
        for s in ctx.user.skills:
            if filter_types and s.skill_type not in filter_types:
                continue
            if s.power > 0:
                base = getattr(s, "_ability_base_power", s.power)
                setattr(s, "_ability_base_power", base)
                total_pct = power_pct * count if power_pct else 0.0
                total_bonus = power_bonus * count if power_bonus else 0
                s.power = max(0, int(base * (1.0 + total_pct)) + total_bonus)
        if not filter_types:
            previous = ctx.user.ability_state.get("_global_entry_count_power", {})
            _record_public_skill_modifier(ctx.user, "power", power_pct * count * 100 - previous.get("pct", 0), before_power, "power_pct")
            public = ctx.user.ability_state.setdefault("public_skill_modifiers", {})
            public["power"] = public.get("power", 0) + power_bonus * count - previous.get("bonus", 0)
            ctx.user.ability_state["_global_entry_count_power"] = {"pct": power_pct * count * 100, "bonus": power_bonus * count}

    # buff: 属性加成×count
    buff = per.get("buff", {})
    if buff:
        scaled = {k: v * count for k, v in buff.items()}
        _apply_buff(ctx.user, scaled)

    # grant_agility: 获得迅捷（不受count缩放）
    if per.get("grant_agility"):
        for s in ctx.user.skills:
            if filter_types and s.skill_type not in filter_types:
                continue
            s.agility = True



def _h_hit_count_per_poison(tag: EffectTag, ctx: Ctx) -> None:
    """HIT_COUNT_PER_POISON: 侵蚀 — 敌方每有1层中毒，自己连击数+1（仅攻击技能）
    PASSIVE handler: stores flag in ability_state. Actual hit_count bonus applied in _h_damage.
    """
    ctx.user.ability_state["hit_count_per_poison"] = True



def _h_first_action_hit_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """FIRST_ACTION_HIT_BONUS: 噼啪！ — 入场后首次行动使用次数+1（所有技能类型）
    ON_ENTER: set flag. Actual hit_count bonus applied in _h_damage and cleared after first skill use.
    """
    if ctx.result.get("_is_ability_ctx"):
        # ON_ENTER: set flag
        if not ctx.result.get("skill"):
            ctx.user.ability_state["first_action_bonus"] = True
            return
        # ON_USE_SKILL: clear the flag (bonus already applied in _h_damage)
        if ctx.user.ability_state.get("first_action_bonus"):
            ctx.user.ability_state["first_action_bonus"] = False



def _h_fixed_hit_count_all(tag: EffectTag, ctx: Ctx) -> None:
    """FIXED_HIT_COUNT_ALL: 无差别过滤 — 在场时所有精灵连击数固定为2"""
    ctx.user.ability_state["fixed_hit_count_all"] = tag.params.get("count", 2)



def _h_extra_poison_tick(tag: EffectTag, ctx: Ctx) -> None:
    """EXTRA_POISON_TICK: 复方汤剂 — 回合结束时中毒额外触发1次（写 flag，由 turn_end_effects 结算）"""
    ctx.user.ability_state["extra_poison_tick"] = True



def _h_conditional_entry_buff_total_cost(tag: EffectTag, ctx: Ctx) -> None:
    """CONDITIONAL_ENTRY_BUFF_TOTAL_COST: 保守派 — 总技能能耗<4时双防+80%"""
    threshold = tag.params.get("cost_threshold", 4)
    total_cost = sum(getattr(s, "_base_energy_cost", s.energy_cost) for s in ctx.user.skills)
    if total_cost < threshold:
        buff = tag.params.get("buff", {"def": 0.8, "spdef": 0.8})
        _apply_buff(ctx.user, buff)



def _h_conditional_entry_buff_mp(tag: EffectTag, ctx: Ctx) -> None:
    """CONDITIONAL_ENTRY_BUFF_MP: 图书守卫者 — MP=1时双攻+50%  /  构装契约者 — 敌方MP=1时双防+50%"""
    mp_value = tag.params.get("mp_value", 1)
    check_enemy = tag.params.get("check_enemy", False)
    team = ctx.team
    if check_enemy:
        mp = ctx.state.mp_b if team == "a" else ctx.state.mp_a
    else:
        mp = ctx.state.mp_a if team == "a" else ctx.state.mp_b
    if mp == mp_value:
        buff = tag.params.get("buff", {"atk": 0.5, "spatk": 0.5})
        _apply_buff(ctx.user, buff)



def _h_immune_zero_energy_attacker(tag: EffectTag, ctx: Ctx) -> None:
    """IMMUNE_ZERO_ENERGY_ATTACKER: 惊吓 — 能量=0的精灵无法对自己造伤"""
    ctx.user.ability_state["immune_zero_energy_attacker"] = True



def _h_immune_low_cost_attack(tag: EffectTag, ctx: Ctx) -> None:
    """IMMUNE_LOW_COST_ATTACK: 逐魂鸟 — 能耗≤1的攻击技能无法对自己造伤"""
    ctx.user.ability_state["immune_low_cost_attack"] = tag.params.get("cost_threshold", 1)



def _h_entry_self_damage(tag: EffectTag, ctx: Ctx) -> None:
    """ENTRY_SELF_DAMAGE: 铃兰晚钟 — 首次入场时失去一半当前HP"""
    if ctx.user.ability_state.get("entry_self_damage_triggered"):
        return
    ctx.user.ability_state["entry_self_damage_triggered"] = True
    ctx.user.current_hp = max(1, ctx.user.current_hp // 2)



def _h_specific_skill_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """SPECIFIC_SKILL_POWER_BONUS: 共鸣 — 携带的指定名称技能威力+N"""
    skill_name = tag.params.get("skill_name", "")
    power_bonus = tag.params.get("power_bonus", 20)
    for s in ctx.user.skills:
        if s.name == skill_name:
            if not hasattr(s, "_ability_base_power"):
                s._ability_base_power = s.power
            s.power = s._ability_base_power + power_bonus
            break



def _h_energy_no_cap(tag: EffectTag, ctx: Ctx) -> None:
    """ENERGY_NO_CAP: 多人宿舍 — 能量可超过上限（无上限）"""
    ctx.user.ability_state["energy_no_cap"] = True



def _h_hp_for_energy(tag: EffectTag, ctx: Ctx) -> None:
    """HP_FOR_ENERGY: 石头大餐 — 能量不足时每缺1点消耗5%HP代替"""
    ctx.user.ability_state["hp_for_energy"] = True



def _h_shuffle_skills_reduce_last(tag: EffectTag, ctx: Ctx) -> None:
    """SHUFFLE_SKILLS_REDUCE_LAST: 盲拧 — 回合开始打乱技能顺序,4号位能耗-4"""
    cost_reduce = tag.params.get("cost_reduce", 4)
    skills = ctx.user.skills
    if len(skills) >= 2:
        rng_shuffle(skills)
        # 新4号位(最后一个)能耗-4
        if len(skills) >= 4:
            last = skills[3]
            last.energy_cost = max(0, last.energy_cost - _adjust_cost_delta(ctx.user, cost_reduce))



def _h_weather_conditional_buff(tag: EffectTag, ctx: Ctx) -> None:
    """WEATHER_CONDITIONAL_BUFF: 得寸进尺 — 天气条件下获得buff"""
    weather = tag.params.get("weather", "rain")
    buff = tag.params.get("buff", {})
    if getattr(ctx.state, "weather", None) == weather:
        _apply_buff(ctx.user, buff)



def _h_fainted_allies_buff(tag: EffectTag, ctx: Ctx) -> None:
    """FAINTED_ALLIES_BUFF: 悲悯/悼亡 — 每有1只力竭精灵双攻+N%"""
    buff_per = tag.params.get("buff_per", {"atk": 0.3, "spatk": 0.3})
    scope = tag.params.get("scope", "allies")
    my_team = ctx.state.team_a if ctx.team == "a" else ctx.state.team_b
    enemy_team = ctx.state.team_b if ctx.team == "a" else ctx.state.team_a
    fainted = sum(1 for p in my_team if p.is_fainted)
    if scope == "all":
        fainted += sum(1 for p in enemy_team if p.is_fainted)
    if fainted > 0:
        scaled_buff = {k: v * fainted for k, v in buff_per.items()}
        _apply_buff(ctx.user, scaled_buff)



def _h_on_super_effective_buff(tag: EffectTag, ctx: Ctx) -> None:
    """ON_SUPER_EFFECTIVE_BUFF: 最好的伙伴 — 造成克制伤害后buff+回能"""
    if not ctx.skill:
        return
    from nrc_core.models import get_type_effectiveness
    effectiveness = get_type_effectiveness(ctx.skill.skill_type, ctx.target.pokemon_types)
    if effectiveness > 1.0:
        buff = tag.params.get("buff", {})
        energy = tag.params.get("energy", 0)
        if buff:
            _apply_buff(ctx.user, buff)
        if energy:
            ctx.user.gain_energy(energy)



def _h_enemy_element_diversity_power(tag: EffectTag, ctx: Ctx) -> None:
    """ENEMY_ELEMENT_DIVERSITY_POWER: 血型吸引 — 敌方每携带1种系别威力+N"""
    power_per_type = tag.params.get("power_per_type", 10)
    unique_types = set()
    for s in ctx.target.skills:
        unique_types.add(s.skill_type)
    bonus = len(unique_types) * power_per_type
    if bonus > 0:
        ctx.user.skill_power_bonus += bonus



def _h_kill_mp_penalty(tag: EffectTag, ctx: Ctx) -> None:
    """KILL_MP_PENALTY: 付给恶魔的赎价 — 击败敌方-1MP / 被击败自己-1MP
    ON_KILL: 敌方额外-1MP. ON_FAINT: 己方额外-1MP.
    """
    # Determine context based on timing (stored by the caller in result)
    timing = ctx.result.get("_ability_timing")
    if timing == "ON_KILL":
        # 击败敌方时，敌方额外-1MP
        if ctx.team == "a":
            ctx.state.mp_b = max(0, ctx.state.mp_b - 1)
        else:
            ctx.state.mp_a = max(0, ctx.state.mp_a - 1)
    elif timing == "ON_FAINT":
        # 被击败时，己方额外-1MP
        if ctx.team == "a":
            ctx.state.mp_a = max(0, ctx.state.mp_a - 1)
        else:
            ctx.state.mp_b = max(0, ctx.state.mp_b - 1)



def _h_turn_end_repeat(tag: EffectTag, ctx: Ctx) -> None:
    """TURN_END_REPEAT: 双向光速 — 回合结束效果触发次数+1"""
    delta = tag.params.get("delta", 1)
    ctx.user.ability_state["turn_end_repeat"] = ctx.user.ability_state.get("turn_end_repeat", 0) + delta



def _h_turn_end_skip(tag: EffectTag, ctx: Ctx) -> None:
    """TURN_END_SKIP: 陨落 — 回合结束效果触发次数-1"""
    delta = tag.params.get("delta", 1)
    ctx.user.ability_state["turn_end_skip"] = ctx.user.ability_state.get("turn_end_skip", 0) + delta



def _h_cost_change_double(tag: EffectTag, ctx: Ctx) -> None:
    """COST_CHANGE_DOUBLE: 倾轧 — 能耗变化效果翻倍（被动标记）"""
    ctx.user.ability_state["cost_change_double"] = True



def _h_noise_debuff(tag: EffectTag, ctx: Ctx) -> None:
    """NOISE_DEBUFF: 泛音列 — 使用状态技能后敌方攻击技能能耗+N，持续N回合
    走 temporary_skill_cost_mods 路径（filter=attack），turn_end_effects 自动递减回合数。
    """
    cost_up = tag.params.get("cost_up", 3)
    turns = tag.params.get("turns", 3)
    mods = ctx.target.ability_state.setdefault("temporary_skill_cost_mods", [])
    mods.append({"amount": cost_up, "filter": "attack", "turns": turns})



def _h_skill_slot_lock(tag: EffectTag, ctx: Ctx) -> None:
    """SKILL_SLOT_LOCK: 正位宝剑/宝剑王牌 — 限制可用技能位置"""
    allowed = tag.params.get("allowed_slots", [0])
    ctx.user.ability_state["skill_slot_lock"] = allowed



def _h_buff_extra_layers(tag: EffectTag, ctx: Ctx) -> None:
    """BUFF_EXTRA_LAYERS: 营养液泡 — 获得增益时额外+N层"""
    extra = tag.params.get("extra", 2)
    ctx.user.ability_state["buff_extra_layers"] = extra



def _h_barrel_state(tag: EffectTag, ctx: Ctx) -> None:
    """BARREL_STATE: 木桶戏法 — 离场后替换精灵以木桶状态登场

    木桶状态：属性克制和抵抗全部失效（所有克制=1.0），直到精灵主动行动。
    """
    # 标记己方下一个入场的精灵获得木桶状态
    team = ctx.team
    if team == "a":
        ctx.state._barrel_pending_a = True
    else:
        ctx.state._barrel_pending_b = True



def _h_burst_power_bonus(tag: EffectTag, ctx: Ctx) -> None:
    """BURST_POWER_BONUS: 电流刺激 — 迸发技能威力+N"""
    bonus = tag.params.get("bonus", 40)
    ctx.user.ability_state["burst_power_bonus"] = ctx.user.ability_state.get("burst_power_bonus", 0) + bonus



def _h_burst_enemy_cost_up(tag: EffectTag, ctx: Ctx) -> None:
    """BURST_ENEMY_COST_UP: 超负荷 — 迸发技能让敌方全能耗+1"""
    amount = tag.params.get("amount", 1)
    ctx.user.ability_state["burst_enemy_cost_up"] = ctx.user.ability_state.get("burst_enemy_cost_up", 0) + amount



def _h_burst_element_cost_reduce(tag: EffectTag, ctx: Ctx) -> None:
    """BURST_ELEMENT_COST_REDUCE: 生物电 — 指定系迸发能耗-N"""
    ctx.user.ability_state["burst_element_cost_reduce"] = {
        "element": tag.params.get("element", "电"),
        "reduce": tag.params.get("reduce", 2),
    }



def _h_burst_extend(tag: EffectTag, ctx: Ctx) -> None:
    """BURST_EXTEND: 连续负荷 — 迸发效果延长1回合"""
    extend = tag.params.get("extend", 1)
    ctx.user.ability_state["burst_extend"] = ctx.user.ability_state.get("burst_extend", 0) + extend



