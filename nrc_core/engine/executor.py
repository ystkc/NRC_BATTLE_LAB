"""技能、应对、特性和迅捷的执行入口。"""

from typing import List, Optional, Dict, TYPE_CHECKING
from nrc_core.effect_models import E, EffectTag, Timing, AbilityEffect, SkillTiming, SkillEffect
from nrc_core.debug import core_log
from nrc_core.engine.context import (
    Ctx,
)
from nrc_core.engine.dispatch import (
    _apply_tag,
)
from nrc_core.engine.filters import (
    _check_skill_filter,
)
from nrc_core.engine.handlers_skill import (
    _h_passive_energy_reduce_water_ring,
)
from nrc_core.engine.helpers import (
    _ability_report_snapshot,
    _adjust_cost_delta,
    _apply_buff,
    _execute_agility_old,
    _find_skill_index,
    _get_ability_name,
    _iter_flat_tags_static,
    _report_ability_changes,
)

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


class EffectExecutor:
    """
    无状态的效果执行器。所有方法均为 @staticmethod。
    """

    # ────────────────────────────────────────
    #  主入口: 执行技能
    # ────────────────────────────────────────

    @staticmethod
    def execute_skill(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        effects,
        is_first: bool = False,
        enemy_skill: "Skill" = None,
        team: str = "a",
    ) -> Dict:
        """
        执行技能的全部效果。
        自动检测 effects 是 List[SkillEffect] 还是 List[EffectTag]，分别走新/旧路径。
        """
        core_log("skill", "effect_start", turn=getattr(state, "turn", None),
                 team=team, user=user.name, target=target.name,
                 skill=skill.name, effect_count=len(effects or []),
                 engine="skill_effect" if effects and isinstance(effects[0], SkillEffect) else "legacy")
        if effects and isinstance(effects[0], SkillEffect):
            result = EffectExecutor._execute_skill_se(
                state, user, target, skill, effects,
                is_first=is_first, enemy_skill=enemy_skill, team=team,
            )
        # ── 旧格式: List[EffectTag] ──
        else:
            result = EffectExecutor._execute_skill_legacy(
            state, user, target, skill, effects,
            is_first=is_first, enemy_skill=enemy_skill, team=team,
            )
        core_log("skill", "effect_done", turn=getattr(state, "turn", None),
                 team=team, user=user.name, target=target.name,
                 skill=skill.name, result=result)
        return result

    @staticmethod
    def _execute_skill_legacy(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        effects: List[EffectTag],
        is_first: bool = False,
        enemy_skill: "Skill" = None,
        team: str = "a",
    ) -> Dict:
        """
        执行技能的全部效果（非应对部分）。
        应对容器（COUNTER_*）被收集到 result["counter_effects"]，
        由 battle.py 在之后调用 execute_counter 处理。
        """
        result = {
            "damage": 0,
            "interrupted": False,
            "countered": False,
            "force_switch": False,
            "force_enemy_switch": False,
            "counter_effects": [],
            "_user_hp_start": user.current_hp,
            "_target_hp_start": target.current_hp,
        }
        ctx = Ctx(
            execute_ability=EffectExecutor.execute_ability,
            state=state, user=user, target=target, skill=skill,
            result=result, is_first=is_first, team=team, enemy_skill=enemy_skill,
        )
        damage_tags: List[EffectTag] = []
        post_use_tags: List[EffectTag] = []
        for tag in effects:
            if tag.params.get("when") == "post_use":
                post_use_tags.append(tag)
                continue
            if tag.type == E.DAMAGE:
                damage_tags.append(tag)
                continue
            _apply_tag(tag, ctx)
        for tag in damage_tags:
            _apply_tag(tag, ctx)
        total_drain = result.get("_life_drain_pct", 0.0) + getattr(user, "life_drain_mod", 0.0)
        if total_drain > 0 and result.get("damage", 0) > 0:
            heal = int(result["damage"] * total_drain)
            anti = getattr(user, "ability_state", {}).get("anti_heal_multiplier", 0)
            if anti:
                user.current_hp = max(0, user.current_hp - heal)
            else:
                user.current_hp = min(user.hp, user.current_hp + heal)
        for tag in post_use_tags:
            _apply_tag(tag, ctx)
        for buff in result.pop("_post_use_self_buffs", []):
            _apply_buff(user, buff)
        if result.get("_consume_next_attack_mod"):
            user.next_attack_power_bonus = 0
            user.next_attack_power_pct = 0.0
        return result

    # ────────────────────────────────────────
    #  新格式: SkillEffect 按阶段执行
    # ────────────────────────────────────────

    @staticmethod
    def _execute_skill_se(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        effects: List[SkillEffect],
        is_first: bool = False,
        enemy_skill: "Skill" = None,
        team: str = "a",
    ) -> Dict:
        """按 SkillTiming 阶段顺序执行技能效果。"""
        result = {
            "damage": 0,
            "interrupted": False,
            "countered": False,
            "force_switch": False,
            "force_enemy_switch": False,
            "counter_effects": [],
            "_user_hp_start": user.current_hp,
            "_target_hp_start": target.current_hp,
        }
        ctx = Ctx(
            execute_ability=EffectExecutor.execute_ability,
            state=state, user=user, target=target, skill=skill,
            result=result, is_first=is_first, team=team, enemy_skill=enemy_skill,
        )

        # 按 filter 中的 per 缩放: 注入到 ctx 上供 handler 使用
        # 缩放因子在 PRE_USE 阶段计算一次

        # ── 阶段1: PRE_USE ──
        for se in effects:
            if se.timing == SkillTiming.PRE_USE and _check_skill_filter(se.filter, ctx):
                for tag in se.effects:
                    _apply_tag(tag, ctx)

        # ── 阶段2: IF (运行时条件 — 在伤害前，影响威力/连击数) ──
        for se in effects:
            if se.timing == SkillTiming.IF and _check_skill_filter(se.filter, ctx):
                for tag in se.effects:
                    _apply_tag(tag, ctx)

        # ── 阶段3: ON_USE (主体伤害/状态) ──
        #    DAMAGE 标签延后到其他 ON_USE 标签之后，确保威力修正先生效
        on_use_damage = []
        for se in effects:
            if se.timing == SkillTiming.ON_USE:
                for tag in se.effects:
                    if tag.type == E.DAMAGE:
                        on_use_damage.append(tag)
                    else:
                        _apply_tag(tag, ctx)
        for tag in on_use_damage:
            _apply_tag(tag, ctx)

        # ── 阶段4: ON_HIT (仅有伤害时) ──
        if result.get("damage", 0) > 0:
            for se in effects:
                if se.timing == SkillTiming.ON_HIT and _check_skill_filter(se.filter, ctx):
                    for tag in se.effects:
                        _apply_tag(tag, ctx)

        # ── 阶段5: ON_COUNTER (收集，由 battle.py 在应对时执行) ──
        for se in effects:
            if se.timing == SkillTiming.ON_COUNTER:
                result["counter_effects"].append(se)

        # ── 阶段6: POST_USE ──
        for se in effects:
            if se.timing == SkillTiming.POST_USE:
                for tag in se.effects:
                    _apply_tag(tag, ctx)

        # ── 吸血结算 ──
        total_drain = result.get("_life_drain_pct", 0.0) + getattr(user, "life_drain_mod", 0.0)
        if total_drain > 0 and result.get("damage", 0) > 0:
            heal = int(result["damage"] * total_drain)
            anti = getattr(user, "ability_state", {}).get("anti_heal_multiplier", 0)
            if anti:
                user.current_hp = max(0, user.current_hp - heal)
            else:
                user.current_hp = min(user.hp, user.current_hp + heal)

        # ── 后处理 ──
        for buff in result.pop("_post_use_self_buffs", []):
            _apply_buff(user, buff)
        if result.get("_consume_next_attack_mod"):
            user.next_attack_power_bonus = 0
            user.next_attack_power_pct = 0.0

        return result

    # ────────────────────────────────────────
    #  新格式: 应对效果执行
    # ────────────────────────────────────────

    @staticmethod
    def execute_counter_se(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        counter_se: SkillEffect,
        enemy_skill: "Skill",
        damage: int,
        team: str = "a",
    ) -> Optional[Dict]:
        """
        执行新格式应对效果。
        counter_se 是 SkillEffect(timing=ON_COUNTER, filter={"category": ...})
        """
        from nrc_core.models import SkillCategory

        result = {
            "final_damage": damage,
            "interrupted": False,
            "force_switch": False,
            "force_enemy_switch": False,
        }

        # 按 filter["category"] 匹配
        category = counter_se.filter.get("category", "")
        matched = False
        if category == "attack":
            matched = enemy_skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL)
        elif category == "status":
            matched = enemy_skill.category == SkillCategory.STATUS
        elif category == "defense":
            matched = enemy_skill.category == SkillCategory.DEFENSE
        elif not category:
            # 无类别限制 = 全匹配
            matched = True

        if not matched:
            core_log("skill", "counter_miss", turn=getattr(state, "turn", None),
                     team=team, user=user.name, target=target.name,
                     skill=skill.name, enemy_skill=enemy_skill.name)
            return None

        # 应对成功：更新计数
        if team == "a":
            state.counter_count_a += 1
        else:
            state.counter_count_b += 1

        ctx = Ctx(
            execute_ability=EffectExecutor.execute_ability,
            state=state, user=user, target=target, skill=skill,
            result=result, team=team, enemy_skill=enemy_skill, damage=damage,
        )

        for tag in counter_se.effects:
            if tag.type == E.INTERRUPT:
                result["interrupted"] = True
            elif tag.type == E.FORCE_SWITCH:
                result["force_switch"] = True
            elif tag.type == E.FORCE_ENEMY_SWITCH:
                result["force_enemy_switch"] = True
            elif tag.type == E.PASSIVE_ENERGY_REDUCE:
                _h_passive_energy_reduce_water_ring(tag, ctx)
            else:
                _apply_tag(tag, ctx)

        # 如果应对中有伤害/威力修正，重新计算伤害
        if any(key in result for key in ("_power_bonus", "_power_mult", "_hit_count_bonus", "_hit_count_mult")):
            from nrc_core.battle import DamageCalculator
            weather = getattr(state, "weather", None)
            power = (
                skill.power
                + user.skill_modifier(skill, "power")
                + user.skill_power_bonus
                + user.next_attack_power_bonus
                + result.get("_power_bonus", 0)
            )
            power_mult = (
                1.0
                + user.skill_power_pct_mod
                + user.skill_modifier(skill, "power_pct")
                + user.next_attack_power_pct
                + (result.get("_power_mult", 1.0) - 1.0)
            )
            if power_mult != 1.0:
                power = int(power * power_mult)
            hit_count = max(
                1,
                int(
                    (skill.hit_count + user.hit_count_mod + result.get("_hit_count_bonus", 0))
                    * result.get("_hit_count_mult", 1.0)
                ),
            )
            result["final_damage"] = DamageCalculator.calculate(
                user, target, skill,
                power_override=power, weather=weather, hit_count_override=hit_count,
            )

        core_log("skill", "counter_done", turn=getattr(state, "turn", None),
                 team=team, user=user.name, target=target.name,
                 skill=skill.name, enemy_skill=enemy_skill.name,
                 result=result)
        return result

    # ────────────────────────────────────────
    #  应对效果执行 (旧格式)
    # ────────────────────────────────────────

    @staticmethod
    def execute_counter(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        counter_tag,
        enemy_skill: "Skill",
        damage: int,
        team: str = "a",
    ) -> Optional[Dict]:
        """
        执行应对效果。自动检测新格式（SkillEffect）或旧格式（EffectTag）。
        """
        if isinstance(counter_tag, SkillEffect):
            return EffectExecutor.execute_counter_se(
                state, user, target, skill, counter_tag, enemy_skill, damage, team,
            )
        # ── 旧格式: EffectTag 容器 ──
        from nrc_core.models import SkillCategory

        result = {
            "final_damage": damage,
            "interrupted": False,
            "force_switch": False,
            "force_enemy_switch": False,
        }

        # 检查应对类型是否匹配
        matched = False
        if counter_tag.type == E.COUNTER_ATTACK:
            matched = enemy_skill.category in (SkillCategory.PHYSICAL, SkillCategory.MAGICAL)
        elif counter_tag.type == E.COUNTER_STATUS:
            matched = enemy_skill.category == SkillCategory.STATUS
        elif counter_tag.type == E.COUNTER_DEFENSE:
            matched = enemy_skill.category == SkillCategory.DEFENSE

        if not matched:
            return None

        # 应对成功：更新计数
        if team == "a":
            state.counter_count_a += 1
        else:
            state.counter_count_b += 1

        # 执行子效果（走同一套 _apply_tag）
        ctx = Ctx(
            execute_ability=EffectExecutor.execute_ability,
            state=state, user=user, target=target, skill=skill,
            result=result, team=team, enemy_skill=enemy_skill, damage=damage,
        )
        for sub in counter_tag.sub_effects:
            if sub.type == E.INTERRUPT:
                result["interrupted"] = True
            elif sub.type == E.FORCE_SWITCH:
                result["force_switch"] = True
            elif sub.type == E.FORCE_ENEMY_SWITCH:
                result["force_enemy_switch"] = True
            elif sub.type == E.PASSIVE_ENERGY_REDUCE:
                # 水环：应对时全技能能耗-N
                _h_passive_energy_reduce_water_ring(sub, ctx)
            else:
                _apply_tag(sub, ctx)

        if any(key in result for key in ("_power_bonus", "_power_mult", "_hit_count_bonus", "_hit_count_mult")):
            from nrc_core.battle import DamageCalculator
            weather = getattr(state, "weather", None)
            power = (
                skill.power
                + user.skill_modifier(skill, "power")
                + user.skill_power_bonus
                + user.next_attack_power_bonus
                + result.get("_power_bonus", 0)
            )
            power_mult = (
                1.0
                + user.skill_power_pct_mod
                + user.skill_modifier(skill, "power_pct")
                + user.next_attack_power_pct
                + (result.get("_power_mult", 1.0) - 1.0)
            )
            if power_mult != 1.0:
                power = int(power * power_mult)
            hit_count = max(
                1,
                int(
                    (skill.hit_count + user.hit_count_mod + result.get("_hit_count_bonus", 0))
                    * result.get("_hit_count_mult", 1.0)
                ),
            )
            result["final_damage"] = DamageCalculator.calculate(
                user,
                target,
                skill,
                power_override=power,
                weather=weather,
                hit_count_override=hit_count,
            )

        return result

    # ────────────────────────────────────────
    #  特性触发
    # ────────────────────────────────────────

    @staticmethod
    def execute_ability(
        state: "BattleState",
        pokemon: "Pokemon",
        enemy: "Pokemon",
        timing: Timing,
        ability_effects: List[AbilityEffect],
        team: str = "a",
        context: Optional[Dict] = None,
    ) -> Dict:
        """在指定时机触发特性效果。"""
        result = {"triggered": False, "damage_reduction": 0}
        report_start = len(state.turn_report)
        if context is None:
            context = {}

        for ae in ability_effects:
            if ae.timing != timing:
                continue

            context["_ability_filter"] = ae.filter
            if not EffectExecutor._check_ability_filter(ae, pokemon, enemy, state, team, context):
                continue

            result["triggered"] = True

            # 通用效果：走同一套 _apply_tag（ability_mode=True）
            # 用 context 充当 result，以便 ability 内部传递信息
            ctx = Ctx(
                execute_ability=EffectExecutor.execute_ability,
                state=state, user=pokemon, target=enemy, skill=context.get("skill"),
                result=context, team=team, is_first=context.get("is_first", False),
            )
            # 标记为 ability 上下文
            context["_is_ability_ctx"] = True
            context["_ability_timing"] = timing.name

            report_before = _ability_report_snapshot(state)
            report_context_before = {key: value for key, value in context.items()
                                     if isinstance(value, (str, int, float, bool, type(None)))}
            report_field_before = (state.weather, state.weather_turns, dict(state.marks_a), dict(state.marks_b), state.mp_a, state.mp_b)
            for tag in ae.effects:
                _apply_tag(tag, ctx, ability_mode=True)
                if tag.type == E.DAMAGE_REDUCTION:
                    result["damage_reduction"] = tag.params.get("pct", 0)

            _report_ability_changes(state, report_before, pokemon, team, timing)
            descriptions = []
            for key, label, percent in (
                ("_power_bonus", "本次技能威力", False), ("_power_pct", "本次技能威力", True),
                ("_power_mult", "本次技能威力倍率", False), ("_hit_count_bonus", "本次技能连击", False),
                ("power_multiplier", "本次技能威力倍率", False), ("cost_reduction", "本次技能能耗减少", False),
                ("_hit_count_mult", "本次技能连击倍率", False),
                ("ability_damage_reduction", "伤害减免", True), ("damage_reduction", "伤害减免", True),
            ):
                value, old_value = context.get(key), report_context_before.get(key)
                if isinstance(value, (int, float)) and value != old_value:
                    descriptions.append(f"{label}{value * 100 if percent else value:g}{'%' if percent else ''}")
            known_context_keys = {"_power_bonus", "_power_pct", "_power_mult", "_hit_count_bonus", "_hit_count_mult",
                                  "power_multiplier", "cost_reduction", "ability_damage_reduction", "damage_reduction", "_damage_reduction",
                                  "_ability_timing", "_is_ability_ctx"}
            if not descriptions and any(
                key not in known_context_keys and report_context_before.get(key) != value
                for key, value in context.items() if isinstance(value, (str, int, float, bool, type(None)))
            ):
                descriptions.append("本次特性效果生效")
            weather, weather_turns, marks_a, marks_b, mp_a, mp_b = report_field_before
            if (weather, weather_turns) != (state.weather, state.weather_turns):
                weather_name = {"sunny": "晴天", "rain": "雨天", "sandstorm": "沙暴", "hail": "冰雹", "snow": "雪天"}.get(state.weather, state.weather or "无天气")
                descriptions.append(f"天气变为{weather_name}（{state.weather_turns}回合）")
            for side, old_marks, marks in (("a", marks_a, state.marks_a), ("b", marks_b, state.marks_b)):
                if old_marks != marks:
                    descriptions.append(f"{'己方' if side == team else '敌方'}场地印记变化")
            for side, old_mp, mp in (("a", mp_a, state.mp_a), ("b", mp_b, state.mp_b)):
                if mp != old_mp:
                    descriptions.append(f"{'己方' if side == team else '敌方'}魔法值{mp - old_mp:+g}")
            if descriptions:
                ability = _get_ability_name(pokemon)
                state.turn_report.append({"type": "ability", "team": team, "pokemon": pokemon.name,
                                          "ability": ability, "timing": timing.name,
                                          "description": f"[特性：{ability}] " + "，".join(descriptions)})

            core_log("ability", "triggered", turn=getattr(state, "turn", None),
                     team=team, pokemon=pokemon.name, enemy=enemy.name,
                     timing=getattr(timing, "name", str(timing)),
                     tags=[getattr(tag.type, "value", str(tag.type)) for tag in ae.effects],
                     result=context)

        reports = state.turn_report[report_start:]
        result["description"] = "；".join(event["description"] for event in reports if not event.get("private"))
        result["reports"] = reports
        return result

    # ────────────────────────────────────────
    #  迅捷入场
    # ────────────────────────────────────────

    @staticmethod
    def execute_agility_entry(
        state: "BattleState",
        pokemon: "Pokemon",
        enemy: "Pokemon",
        team: str = "a",
    ) -> None:
        """入场时执行带迅捷标记的技能"""
        for skill in pokemon.skills:
            if not getattr(skill, "effects", None):
                if skill.agility and pokemon.energy >= skill.energy_cost:
                    _execute_agility_old(pokemon, enemy, skill)
                continue

            has_agility = any(e.type == E.AGILITY for e in _iter_flat_tags_static(skill.effects))
            if has_agility and pokemon.energy >= skill.energy_cost:
                pokemon.energy -= skill.energy_cost
                EffectExecutor.execute_skill(
                    state, pokemon, enemy, skill, skill.effects,
                    is_first=True, team=team,
                )
                break  # 只触发第一个迅捷技能

    # ────────────────────────────────────────
    #  传动系统
    # ────────────────────────────────────────

    @staticmethod
    def execute_drive(
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill",
        drive_value: int,
        team: str = "a",
    ) -> None:
        """执行传动：触发后方 N 位技能的被动效果。"""
        skill_idx = _find_skill_index(user, skill)
        if skill_idx < 0:
            return

        n_skills = len(user.skills)
        if n_skills == 0:
            return

        target_idx = (skill_idx + drive_value) % n_skills
        target_skill = user.skills[target_idx]

        if not getattr(target_skill, "effects", None):
            return

        for tag in _iter_flat_tags_static(target_skill.effects):
            if tag.type == E.PASSIVE_ENERGY_REDUCE:
                reduce = tag.params.get("reduce", 0)
                rng = tag.params.get("range", "self")
                if rng == "self":
                    target_skill.energy_cost = max(
                        0,
                        target_skill.energy_cost + _adjust_cost_delta(user, -reduce),
                    )
                elif rng == "adjacent":
                    for offset in [-1, 1]:
                        adj_idx = (target_idx + offset) % n_skills
                        user.skills[adj_idx].energy_cost = max(
                            0,
                            user.skills[adj_idx].energy_cost + _adjust_cost_delta(user, -reduce),
                        )
            elif tag.type == E.PERMANENT_MOD:
                if tag.params.get("trigger") == "per_position_change":
                    target_skill.power += tag.params.get("delta", 0)

    # ────────────────────────────────────────
    #  内部: 特性过滤
    # ────────────────────────────────────────

    @staticmethod
    def _check_ability_filter(
        ae: AbilityEffect,
        pokemon: "Pokemon",
        enemy: "Pokemon",
        state: "BattleState",
        team: str,
        context: Dict,
    ) -> bool:
        f = ae.filter
        if not f:
            return True

        if "element" in f:
            skill = context.get("skill")
            if not skill:
                return False
            from nrc_core.models import TYPE_NAME_MAP as _TYPE_MAP
            elements = f["element"]
            if not isinstance(elements, (list, tuple, set)):
                elements = [elements]
            # 规则配置同时使用“火”和“火系”等中文系别名称。
            expected_types = {_TYPE_MAP.get(el) or _TYPE_MAP.get(f"{el}系") for el in elements}
            if skill.skill_type not in expected_types:
                return False

        if f.get("condition") == "skill_element_not_enemy_type":
            skill = context.get("skill")
            if skill and skill.skill_type != enemy.pokemon_type:
                return True
            return False

        if f.get("condition") == "energy_zero":
            return pokemon.energy <= 0

        if f.get("condition") == "energy_not_zero":
            return pokemon.energy > 0

        if "positions" in f:
            skill = context.get("skill")
            if skill:
                idx = _find_skill_index(pokemon, skill)
                if idx not in f["positions"]:
                    return False
            else:
                # 位置型被动特性会在没有具体 skill 的时机触发，
                # 由 handler 依据 filter 自行选择目标技能。
                pass

        return True



