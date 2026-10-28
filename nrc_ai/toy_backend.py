"""Tiny simultaneous hidden-style game for framework smoke tests only.

This is not an NRC rules model. It verifies that the training package can run
before the in-progress nrc_core adapter exists.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import random
from typing import Any, Mapping

from nrc_core.contracts import CoreManifest, Decision, LegalAction, Observation, Transition


@dataclass
class ToyState:
    turn: int
    hp: list[int]
    energy: list[int]
    style: tuple[str, str]
    terminated: bool = False
    winner: int | None = None


class ToyBackend:
    manifest = CoreManifest("toy-1", "toy-rules-1", "toy-catalog-1", "toy-actions-1", "toy-observation-1", "toy")

    def new_game(self, setup: Mapping[str, Any], seed: int) -> ToyState:
        styles = tuple(setup.get("styles", ("aggressive", "defensive")))
        if len(styles) != 2:
            raise ValueError("toy setup requires two styles")
        return ToyState(1, [5, 5], [2, 2], styles)

    def clone(self, state: ToyState) -> ToyState:
        return copy.deepcopy(state)

    def decision(self, state: ToyState) -> Decision:
        return Decision(state.turn, state.turn, "turn_choice", () if state.terminated else (0, 1), state.terminated, state.winner)

    def observe(self, state: ToyState, player: int) -> Observation:
        other = 1 - player
        return Observation(player, state.turn, state.turn, "turn_choice", {"own": {"hp": state.hp[player], "energy": state.energy[player]}, "opponent": {"hp": state.hp[other]}, "shared": {"turn": state.turn}, "events": []})

    def legal_actions(self, state: ToyState, player: int) -> tuple[LegalAction, ...]:
        if state.terminated:
            return ()
        actions = [LegalAction("attack"), LegalAction("guard")]
        if state.energy[player] < 3:
            actions.append(LegalAction("charge"))
        return tuple(actions)

    def advance(self, state: ToyState, actions: Mapping[int, str], seed: int) -> Transition:
        if set(actions) != {0, 1}:
            raise ValueError("toy backend requires both simultaneous actions")
        legal = {player: {candidate.key for candidate in self.legal_actions(state, player)} for player in (0, 1)}
        if any(action not in legal[player] for player, action in actions.items()):
            raise ValueError("illegal toy action")
        next_state = self.clone(state)
        rng = random.Random(seed)
        for player in (0, 1):
            if actions[player] == "charge":
                next_state.energy[player] = min(3, next_state.energy[player] + 1)
        for player in (0, 1):
            other = 1 - player
            if actions[player] == "attack" and actions[other] != "guard" and next_state.energy[player] > 0:
                next_state.energy[player] -= 1
                damage = 2 if state.style[player] == "aggressive" else 1
                if rng.random() < 0.1:
                    damage += 1
                next_state.hp[other] = max(0, next_state.hp[other] - damage)
        for player in (0, 1):
            if next_state.hp[player] <= 0:
                next_state.terminated = True
                next_state.winner = 1 - player
        next_state.turn += 1
        observations = {player: self.observe(next_state, player) for player in (0, 1)}
        rewards = {0: 0.0, 1: 0.0}
        if next_state.terminated:
            rewards[next_state.winner] = 1.0
            rewards[1 - next_state.winner] = -1.0
        return Transition(next_state, observations, rewards, next_state.terminated, next_state.winner)

    def export_state(self, state: ToyState) -> Mapping[str, Any]:
        return {"turn": state.turn, "hp": state.hp, "energy": state.energy, "style": state.style, "terminated": state.terminated, "winner": state.winner}

    def import_state(self, snapshot: Mapping[str, Any]) -> ToyState:
        return ToyState(int(snapshot["turn"]), list(snapshot["hp"]), list(snapshot["energy"]), tuple(snapshot["style"]), bool(snapshot["terminated"]), snapshot.get("winner"))
