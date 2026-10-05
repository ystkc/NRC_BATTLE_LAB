"""对外输入输出 schema。

该层只承载协议和 JSON 序列化，不依赖旧模拟器的 Pokemon/BattleState 内部字段。
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from .actions import SideTurnInput
from .branching import AuditStatus, BranchOption
from .devotion import DevotionInput
from .unknown import Maybe


@dataclass
class CreatureBaseInfo:
    color: Maybe[str] = field(default_factory=Maybe.unknown)
    height: Maybe[float] = field(default_factory=Maybe.unknown)
    gender: Maybe[str] = field(default_factory=Maybe.unknown)
    attributes: Maybe[list[str]] = field(default_factory=Maybe.unknown)
    bloodline_attributes: Maybe[list[str]] = field(default_factory=Maybe.unknown)
    shiny: Maybe[bool] = field(default_factory=Maybe.unknown)
    speed_range: Maybe[dict[str, float]] = field(default_factory=Maybe.unknown)
    nature: Maybe[str] = field(default_factory=Maybe.unknown)
    nature_modifiers: Maybe[dict[str, float]] = field(default_factory=Maybe.unknown)
    stats: Maybe[dict[str, float]] = field(default_factory=Maybe.unknown)

    def to_json(self) -> dict:
        return {name: value.to_json() for name, value in self.__dict__.items()}


@dataclass
class CreatureState:
    hp: Maybe[float] = field(default_factory=Maybe.unknown)
    max_hp: Maybe[float] = field(default_factory=Maybe.unknown)
    energy: Maybe[float] = field(default_factory=Maybe.unknown)
    buffs: Maybe[dict[str, Any]] = field(default_factory=Maybe.unknown)
    debuffs: Maybe[dict[str, Any]] = field(default_factory=Maybe.unknown)
    marks: Maybe[dict[str, Any]] = field(default_factory=Maybe.unknown)
    status: Maybe[str] = field(default_factory=Maybe.unknown)
    fatigue_turns: Maybe[int] = field(default_factory=Maybe.unknown)

    def to_json(self) -> dict:
        return {name: value.to_json() for name, value in self.__dict__.items()}


@dataclass
class SkillSlotInput:
    skill_id: Maybe[str] = field(default_factory=Maybe.unknown)
    name: Maybe[str] = field(default_factory=Maybe.unknown)
    current_energy_cost: Maybe[int] = field(default_factory=Maybe.unknown)
    current_power: Maybe[int] = field(default_factory=Maybe.unknown)
    use_count: Maybe[int] = field(default_factory=lambda: Maybe.from_value(1))
    known_to_observer: bool = True
    source: str = "team_input"

    def to_json(self) -> dict:
        return {
            "skill_id": self.skill_id.to_json(),
            "name": self.name.to_json(),
            "current_energy_cost": self.current_energy_cost.to_json(),
            "current_power": self.current_power.to_json(),
            "use_count": self.use_count.to_json(),
            "known_to_observer": self.known_to_observer,
            "source": self.source,
        }


@dataclass
class AbilityInput:
    name: Maybe[str] = field(default_factory=Maybe.unknown)
    descriptions: list[str] = field(default_factory=list)
    possible_names: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "name": self.name.to_json(),
            "descriptions": self.descriptions,
            "possible_names": self.possible_names,
        }


@dataclass
class CreatureInput:
    creature_id: Maybe[str] = field(default_factory=Maybe.unknown)
    name: Maybe[str] = field(default_factory=Maybe.unknown)
    display_name: Maybe[str] = field(default_factory=Maybe.unknown)
    base: CreatureBaseInfo = field(default_factory=CreatureBaseInfo)
    ability: AbilityInput = field(default_factory=AbilityInput)
    abilities: list[AbilityInput] = field(default_factory=list)
    skill_pool: Maybe[list[str]] = field(default_factory=Maybe.unknown)
    skills: list[SkillSlotInput] = field(default_factory=list)
    state: CreatureState = field(default_factory=CreatureState)
    evolution_stage: Maybe[str] = field(default_factory=Maybe.unknown)
    bossified: Maybe[bool] = field(default_factory=Maybe.unknown)
    entry_count: Maybe[int] = field(default_factory=lambda: Maybe.from_value(0))
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_name(self, fallback: str) -> str:
        return self.display_name.or_default(self.name.or_default(fallback))

    def to_json(self) -> dict:
        return {
            "creature_id": self.creature_id.to_json(),
            "name": self.name.to_json(),
            "display_name": self.display_name.to_json(),
            "base": self.base.to_json(),
            "ability": self.ability.to_json(),
            "abilities": [ability.to_json() for ability in self.abilities],
            "skill_pool": self.skill_pool.to_json(),
            "skills": [slot.to_json() for slot in self.skills],
            "state": self.state.to_json(),
            "evolution_stage": self.evolution_stage.to_json(),
            "bossified": self.bossified.to_json(),
            "entry_count": self.entry_count.to_json(),
            "metadata": self.metadata,
        }


@dataclass
class TeamInput:
    creatures: list[CreatureInput] = field(default_factory=list)
    active_index: Maybe[int] = field(default_factory=lambda: Maybe.from_value(0))
    team_name: str = ""
    resonance_magic: Maybe[str] = field(default_factory=Maybe.unknown)
    devotion: DevotionInput = field(default_factory=DevotionInput)

    def to_json(self) -> dict:
        return {
            "team_name": self.team_name,
            "resonance_magic": self.resonance_magic.to_json(),
            "devotion": self.devotion.to_json(),
            "active_index": self.active_index.to_json(),
            "creatures": [creature.to_json() for creature in self.creatures],
        }


@dataclass
class SharedBattleState:
    turn: Maybe[int] = field(default_factory=lambda: Maybe.from_value(1))
    weather: Maybe[str] = field(default_factory=Maybe.unknown)
    weather_turns: Maybe[int] = field(default_factory=Maybe.unknown)
    system_time: Maybe[str] = field(default_factory=Maybe.unknown)
    weekend: Maybe[bool] = field(default_factory=Maybe.unknown)
    bypass: Maybe[bool] = field(default_factory=Maybe.unknown)
    mp: dict[str, Maybe[float]] = field(default_factory=lambda: {
        "own": Maybe.unknown(),
        "opponent": Maybe.unknown(),
    })
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "turn": self.turn.to_json(),
            "weather": self.weather.to_json(),
            "weather_turns": self.weather_turns.to_json(),
            "system_time": self.system_time.to_json(),
            "weekend": self.weekend.to_json(),
            "bypass": self.bypass.to_json(),
            "mp": {key: value.to_json() for key, value in self.mp.items()},
            "metadata": self.metadata,
        }


@dataclass
class BattleRequest:
    own_team: TeamInput
    opponent_team: TeamInput
    shared: SharedBattleState = field(default_factory=SharedBattleState)
    own_turn: Optional[SideTurnInput] = None
    opponent_turn: Optional[SideTurnInput] = None
    seed: Optional[int] = None
    battle_id: str = ""
    source: str = "manual"

    def to_json(self) -> dict:
        return {
            "own_team": self.own_team.to_json(),
            "opponent_team": self.opponent_team.to_json(),
            "shared": self.shared.to_json(),
            "own_turn": {
                "primary": self.own_turn.primary.to_json(),
                "items": [item.to_json() for item in self.own_turn.items],
            } if self.own_turn else None,
            "opponent_turn": {
                "primary": self.opponent_turn.primary.to_json(),
                "items": [item.to_json() for item in self.opponent_turn.items],
            } if self.opponent_turn else None,
            "seed": self.seed,
            "battle_id": self.battle_id,
            "source": self.source,
        }


@dataclass
class SideResult:
    before: dict[str, Any]
    after: dict[str, Any]
    triggered_abilities: list[str] = field(default_factory=list)
    triggered_weather: list[str] = field(default_factory=list)
    triggered_counters: list[str] = field(default_factory=list)
    effectiveness: list[dict[str, Any]] = field(default_factory=list)
    unsupported_actions: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ResolutionBranch:
    branch_id: str
    probability: Optional[float]
    options: list[BranchOption] = field(default_factory=list)
    status: AuditStatus = AuditStatus.PARSED
    note: str = ""

    def to_json(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "probability": self.probability,
            "options": [option.to_json() for option in self.options],
            "status": self.status.value,
            "note": self.note,
        }


@dataclass
class BattleResult:
    own: SideResult
    opponent: SideResult
    shared_before: dict[str, Any]
    shared_after: dict[str, Any]
    possible_branches: list[ResolutionBranch] = field(default_factory=list)
    observed_branch_id: Optional[str] = None
    events: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    input_unknowns: list[str] = field(default_factory=list)
    latent_uncertainties: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "own": self.own.to_json(),
            "opponent": self.opponent.to_json(),
            "shared_before": self.shared_before,
            "shared_after": self.shared_after,
            "possible_branches": [branch.to_json() for branch in self.possible_branches],
            "observed_branch_id": self.observed_branch_id,
            "events": self.events,
            "warnings": self.warnings,
            "input_unknowns": self.input_unknowns,
            "latent_uncertainties": self.latent_uncertainties,
        }
