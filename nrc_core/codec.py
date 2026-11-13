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


class InputValidationError(ValueError):
    """输入协议结构非法时抛出的可定位错误。"""

    def __init__(self, message: str, *, path: str | None = None, code: str = "invalid_input") -> None:
        self.code = code
        self.path = path
        detail = f"{path}: {message}" if path else message
        super().__init__(detail)


def _object(raw: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InputValidationError("必须是对象", path=path, code="invalid_object")
    return raw


def _optional_object(raw: dict[str, Any], key: str, *, path: str) -> dict[str, Any]:
    """读取可省略的嵌套对象；显式非对象值必须拒绝。"""
    if key not in raw or raw[key] is None:
        return {}
    return _object(raw[key], path=path)


def _maybe(raw: Any) -> Maybe:
    return Maybe.from_json(raw)


def _maybe_dict(raw: Any) -> Maybe:
    value = _maybe(raw)
    if value.known and value.exists and value.value is None:
        return Maybe.from_value({})
    return value


def action_from_dict(raw: dict[str, Any], *, path: str = "action", validate_primary: bool = True) -> ActionIntent:
    """解析一个显式动作，不为缺失 kind 或非法形状补默认值。"""
    raw = _object(raw, path=path)
    if "kind" not in raw:
        raise InputValidationError("缺少 kind", path=path, code="missing_action_kind")
    try:
        kind = ActionKind(raw["kind"])
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"非法动作 kind: {raw.get('kind')!r}", path=path, code="invalid_action_kind") from exc
    item_kind = raw.get("item_kind")
    if item_kind is not None:
        try:
            item_kind = ItemKind(item_kind)
        except (TypeError, ValueError) as exc:
            raise InputValidationError(f"非法 item_kind: {item_kind!r}", path=path, code="invalid_item_kind") from exc
    payload = raw.get("item_payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise InputValidationError("item_payload 必须是对象", path=f"{path}.item_payload", code="invalid_item_payload")
    action = ActionIntent(
        kind=kind,
        skill_id=raw.get("skill_id"),
        skill_name=raw.get("skill_name"),
        skill_slot=raw.get("skill_slot"),
        choice=raw.get("choice"),
        switch_index=raw.get("switch_index"),
        item_kind=item_kind,
        item_payload=dict(payload),
        source=raw.get("source", "json"),
    )
    errors = action.validate_primary() if validate_primary else []
    if errors:
        raise InputValidationError("；".join(errors), path=path, code="invalid_action")
    return action


def side_turn_from_dict(raw: dict[str, Any]) -> SideTurnInput:
    """解析一方回合，必须显式提供主动作。"""
    raw = _object(raw, path="turn")
    if "primary" not in raw or raw["primary"] is None:
        raise InputValidationError("缺少 primary 主动作", path="turn.primary", code="missing_primary")
    items = raw.get("items", [])
    if not isinstance(items, list):
        raise InputValidationError("items 必须是数组", path="turn.items", code="invalid_items")
    primary = action_from_dict(raw["primary"], path="turn.primary")
    parsed_items = [
        action_from_dict(item, path=f"turn.items[{index}]", validate_primary=False)
        for index, item in enumerate(items)
    ]
    for index, item in enumerate(parsed_items):
        if item.kind != ActionKind.ITEM or item.item_kind is None:
            raise InputValidationError(
                "items 中必须是带 item_kind 的 item 动作",
                path=f"turn.items[{index}]",
                code="invalid_item_action",
            )
    errors = SideTurnInput(primary=primary, items=parsed_items).validate()
    if errors:
        raise InputValidationError("；".join(errors), path="turn", code="invalid_turn")
    return SideTurnInput(primary=primary, items=parsed_items)


def creature_from_dict(raw: dict[str, Any], *, path: str = "creature") -> CreatureInput:
    """解析精灵输入，并对嵌套对象保留具体错误路径。"""
    raw = _object(raw, path=path)
    base = _optional_object(raw, "base", path=f"{path}.base")
    state = _optional_object(raw, "state", path=f"{path}.state")
    ability = _optional_object(raw, "ability", path=f"{path}.ability")
    ability_items = raw.get("abilities") or []
    if not isinstance(ability_items, list):
        raise InputValidationError("abilities 必须是数组", path=f"{path}.abilities", code="invalid_abilities")
    abilities = []
    for index, item in enumerate(ability_items):
        item = _object(item, path=f"{path}.abilities[{index}]")
        abilities.append(AbilityInput(
            name=_maybe(item.get("name")),
            descriptions=list(item.get("descriptions") or []),
            possible_names=list(item.get("possible_names") or []),
        ))
    raw_skills = raw.get("skills", [])
    if not isinstance(raw_skills, list):
        raise InputValidationError("skills 必须是数组", path=f"{path}.skills", code="invalid_skills")
    skill_inputs = []
    for index, slot in enumerate(raw_skills):
        slot_path = f"{path}.skills[{index}]"
        if isinstance(slot, dict):
            slot = _object(slot, path=slot_path)
            skill_inputs.append(SkillSlotInput(
                skill_id=_maybe(slot.get("skill_id")),
                name=_maybe(slot.get("name")),
                current_energy_cost=_maybe(slot.get("current_energy_cost")),
                current_power=_maybe(slot.get("current_power")),
                use_count=_maybe(slot.get("use_count", 1)),
                known_to_observer=bool(slot.get("known_to_observer", True)),
                source=slot.get("source", "json"),
            ))
        elif isinstance(slot, str):
            skill_inputs.append(SkillSlotInput(
                skill_id=_maybe(None), name=_maybe(slot), use_count=_maybe(1),
                known_to_observer=True, source="json",
            ))
        else:
            raise InputValidationError("技能槽必须是字符串或对象", path=slot_path, code="invalid_skill_slot")
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
            individual_values=_maybe(base.get("individual_values")),
            stats=_maybe(base.get("stats")),
        ),
        ability=AbilityInput(
            name=_maybe(ability.get("name")),
            descriptions=list(ability.get("descriptions") or []),
            possible_names=list(ability.get("possible_names") or []),
        ),
        abilities=abilities,
        skill_pool=_maybe(raw.get("skill_pool")),
        skills=skill_inputs,
        state=CreatureState(
            hp=_maybe(state.get("hp")),
            max_hp=_maybe(state.get("max_hp")),
            energy=_maybe(state.get("energy")),
            buffs=_maybe_dict(state.get("buffs")),
            debuffs=_maybe_dict(state.get("debuffs")),
            marks=_maybe_dict(state.get("marks")),
            statuses=_maybe(state.get("statuses")),
            status=_maybe(state.get("status")),
            fatigue_turns=_maybe(state.get("fatigue_turns")),
        ),
        evolution_stage=_maybe(raw.get("evolution_stage")),
        bossified=_maybe(raw.get("bossified")),
        entry_count=_maybe(raw.get("entry_count", 0)),
        metadata=dict(raw.get("metadata") or {}),
    )


def team_from_dict(raw: dict[str, Any], *, path: str = "team") -> TeamInput:
    """解析一方队伍输入。"""
    raw = _object(raw, path=path)
    devotion = _optional_object(raw, "devotion", path=f"{path}.devotion")
    raw_creatures = raw.get("creatures", [])
    if not isinstance(raw_creatures, list):
        raise InputValidationError("creatures 必须是数组", path=f"{path}.creatures", code="invalid_creatures")
    return TeamInput(
        creatures=[creature_from_dict(item, path=f"{path}.creatures[{index}]") for index, item in enumerate(raw_creatures)],
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
    """解析完整对战请求，不为错误嵌套结构补默认值。"""
    raw = _object(raw, path="request")
    shared = _optional_object(raw, "shared", path="shared")
    mp = _optional_object(shared, "mp", path="shared.mp")
    return BattleRequest(
        own_team=team_from_dict(raw.get("own_team") or {}, path="own_team"),
        opponent_team=team_from_dict(raw.get("opponent_team") or {}, path="opponent_team"),
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
        own_turn=side_turn_from_dict(raw["own_turn"]) if raw.get("own_turn") is not None else None,
        opponent_turn=side_turn_from_dict(raw["opponent_turn"]) if raw.get("opponent_turn") is not None else None,
        seed=raw.get("seed"),
        battle_id=raw.get("battle_id", ""),
        source=raw.get("source", "json"),
    )
