"""对照迁移前实现，检查固定种子的三回合推进和快照。"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nrc_core.runtime import BattleRuntime
from nrc_platform.catalog import load_catalog
from nrc_platform.builder import BattleBuilder


def main() -> None:
    """从版本库临时加载旧实现，比较同一目录与输入的结果。"""
    source = subprocess.check_output(
        ["git", "show", "aa377947e00e947b415b0caf094b15ad9591ad70:nrc_core/training.py"]
    ).decode("utf-8-sig")
    source = source.replace("from nrc_ai.contracts import", "from nrc_core.contracts import")
    source = source.replace("from nrc_core.engine._monolith import", "from nrc_core.engine import")
    source = source.replace("from .simulator import BattleSimulator", "from nrc_platform.builder import BattleBuilder as BattleSimulator")
    legacy = types.ModuleType("nrc_core._migration_baseline")
    sys.modules[legacy.__name__] = legacy
    exec(compile(source, "<migration-baseline>", "exec"), legacy.__dict__)
    catalog = load_catalog()
    teams = []
    for name, record in catalog.pokemon.items():
        skills = [skill for skill in record.get("skills", ()) if skill in catalog.skills]
        if len(skills) < 4:
            continue
        teams.append({"creatures": [{"name": name, "ability": {"name": ""}, "skills": [{"name": skill} for skill in skills[:4]]}]})
        if len(teams) == 2:
            break
    setup = {"own_team": teams[0], "opponent_team": teams[1]}
    old = legacy.NRCTrainingBackend(catalog=catalog)
    new = BattleRuntime(catalog=catalog)
    states = [old.new_game(setup, 17), new.new_game(BattleBuilder(catalog=catalog).build(setup, 17), 17)]
    for index in range(4):
        assert old.decision(states[0]) == new.decision(states[1])
        for player in (0, 1):
            assert old.observe(states[0], player) == new.observe(states[1], player)
            assert old.legal_actions(states[0], player) == new.legal_actions(states[1], player)
        if index < 3:
            results = [runtime.advance(state, {0: "charge", 1: "charge"}, 17 + index) for runtime, state in zip((old, new), states)]
            assert results[0].events == results[1].events
            states = [result.state for result in results]
    restored = new.import_state(new.export_state(states[1]))
    assert new.observe(restored, 0) == new.observe(states[1], 0)
    before = new.export_state(restored)
    display = new.display(restored, 0)
    assert new.preview_damage(restored, 0, 0) == display["skills"][0]
    assert new.export_state(restored) == before
    active = restored.battle.team_a[restored.battle.current_a]
    active.skill_cost_mod = 100
    assert all(row["display_energy_cost"] >= 100 for row in new.display(restored, 0)["skills"])
    assert not any(action.key.startswith("skill:") for action in new.legal_actions(restored, 0))
    print(json.dumps({"rounds": 3, "seed": 17, "observations_actions_events": "equal", "snapshot": "passed"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
