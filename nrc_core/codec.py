"""JSON/dict 与协议 dataclass 之间的转换。"""

from __future__ import annotations

from typing import Any

from .actions import ActionIntent, ActionKind, ItemKind, SideTurnInput
from .devotion import DevotionInput
from .schema import (
    AbilityInput,
    BattleRequest,
    CreatureBaseInfo,
    CreatureInput,
    CreatureState,
    SharedBattleState,
    SkillSlotInput,
    TeamInput,
)
from .unknown import Maybe


def _maybe(raw: Any) -> Maybe:
    return Maybe.from_json(raw)


def _maybe_dict(raw: Any) -> Maybe:
    value = _maybe(raw)
    if value.known and value.exists and value.value is None:
        return Maybe.from_value({})
    return value


def action_from_dict(raw: dict[str, Any]) -> ActionIntent:
    kind = ActionKind(raw.get("kind", "pass"))
    item_kind = raw.get("item_kind")
    return ActionIntent(
        kind=kind,
        skill_id=raw.get("skill_id"),
        skill_name=raw.get("skill_name"),
        skill_slot=raw.get("skill_slot"),
        choice=raw.get("choice"),
        switch_index=raw.get("switch_index"),
        item_kind=ItemKind(item_kind) if item_kind else None,
        item_payload=dict(raw.get("item_payload") or {}),
        source=raw.get("source", "json"),
    )


def side_turn_from_dict(raw: dict[str, Any]) -> SideTurnInput:
    return SideTurnInput(
        primary=action_from_dict(raw.get("primary") or {"kind": "pass"}),
        items=[action_from_dict(item) for item in raw.get("items", [])],
    )


def creature_from_dict(raw: dict[str, Any]) -> CreatureInput:
    base = raw.get("base") or {}
    state = raw.get("state") or {}
    ability = raw.get("ability") or {}
    ability_items = raw.get("abilities") or []
    abilities = [
        AbilityInput(
            name=_maybe(item.get("name")),
            descriptions=list(item.get("descriptions") or []),
            possible_names=list(item.get("possible_names") or []),
        )
        for item in ability_items
    ]
    return CreatureInput(
        creature_id=_maybe(raw.get("creature_id")),
        name=_maybe(raw.get("name")),
        display_name=_maybe(raw.get("display_name")),
        base=CreatureBaseInfo(
            color=_maybe(base.get("color")),
            height=_maybe(base.get("height")),
            gender=_maybe(base.get("gender")),
            attributes=_maybe(base.get("attributes")),
            bloodline_attributes=_maybe(base.get("bloodline_attributes")),
            shiny=_maybe(base.get("shiny")),
            speed_range=_maybe(base.get("speed_range")),
            nature=_maybe(base.get("nature")),
            nature_modifiers=_maybe(base.get("nature_modifiers")),
            stats=_maybe(base.get("stats")),
        ),
        ability=AbilityInput(
            name=_maybe(ability.get("name")),
            descriptions=list(ability.get("descriptions") or []),
            possible_names=list(ability.get("possible_names") or []),
        ),
        abilities=abilities,
        skill_pool=_maybe(raw.get("skill_pool")),
        skills=[
            SkillSlotInput(
                skill_id=_maybe(slot.get("skill_id") if isinstance(slot, dict) else None),
                name=_maybe(slot.get("name") if isinstance(slot, dict) else slot),
                current_energy_cost=_maybe(slot.get("current_energy_cost") if isinstance(slot, dict) else None),
                current_power=_maybe(slot.get("current_power") if isinstance(slot, dict) else None),
                use_count=_maybe(slot.get("use_count", 1) if isinstance(slot, dict) else 1),
                known_to_observer=bool(slot.get("known_to_observer", True)) if isinstance(slot, dict) else True,
                source=slot.get("source", "json") if isinstance(slot, dict) else "json",
            )
            for slot in raw.get("skills", [])
        ],
        state=CreatureState(
            hp=_maybe(state.get("hp")),
            max_hp=_maybe(state.get("max_hp")),
            energy=_maybe(state.get("energy")),
            buffs=_maybe_dict(state.get("buffs")),
            debuffs=_maybe_dict(state.get("debuffs")),
            marks=_maybe_dict(state.get("marks")),
            status=_maybe(state.get("status")),
            fatigue_turns=_maybe(state.get("fatigue_turns")),
        ),
        evolution_stage=_maybe(raw.get("evolution_stage")),
        bossified=_maybe(raw.get("bossified")),
        entry_count=_maybe(raw.get("entry_count", 0)),
        metadata=dict(raw.get("metadata") or {}),
    )


def team_from_dict(raw: dict[str, Any]) -> TeamInput:
    devotion = raw.get("devotion") or {}
    return TeamInput(
        creatures=[creature_from_dict(item) for item in raw.get("creatures", [])],
        active_index=_maybe(raw.get("active_index", 0)),
        team_name=raw.get("team_name", ""),
        resonance_magic=_maybe(raw.get("resonance_magic")),
        devotion=DevotionInput(
            specified_counts=_maybe_dict(devotion.get("specified_counts", {})),
            random_draws=_maybe(devotion.get("random_draws", 0)),
            random_counts=_maybe_dict(devotion.get("random_counts")),
            visible_to_observer=bool(devotion.get("visible_to_observer", False)),
        ),
    )


def battle_request_from_dict(raw: dict[str, Any]) -> BattleRequest:
    shared = raw.get("shared") or {}
    mp = shared.get("mp") or {}
    return BattleRequest(
        own_team=team_from_dict(raw.get("own_team") or {}),
        opponent_team=team_from_dict(raw.get("opponent_team") or {}),
        shared=SharedBattleState(
            turn=_maybe(shared.get("turn", 1)),
            weather=_maybe(shared.get("weather")),
            weather_turns=_maybe(shared.get("weather_turns")),
            system_time=_maybe(shared.get("system_time")),
            weekend=_maybe(shared.get("weekend")),
            bypass=_maybe(shared.get("bypass")),
            mp={
                "own": _maybe(mp.get("own")),
                "opponent": _maybe(mp.get("opponent")),
            },
            metadata=dict(shared.get("metadata") or {}),
        ),
        own_turn=side_turn_from_dict(raw["own_turn"]) if raw.get("own_turn") else None,
        opponent_turn=side_turn_from_dict(raw["opponent_turn"]) if raw.get("opponent_turn") else None,
        seed=raw.get("seed"),
        battle_id=raw.get("battle_id", ""),
        source=raw.get("source", "json"),
    )
