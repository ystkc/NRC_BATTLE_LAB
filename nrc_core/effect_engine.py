"""效果引擎旧导入路径的兼容入口。"""

from nrc_core.engine import (
    # Classes
    Ctx,
    EffectExecutor,
    # Registries
    _HANDLERS,
    _ABILITY_HANDLER_OVERRIDES,
    _apply_tag,
    # Utility functions (used by battle.py top-level import)
    _apply_permanent_mod,
    _adjust_cost_delta,
    _apply_buff,
    _apply_debuff,
    _clear_buffs,
    _clear_debuffs,
    _ability_name,
    _get_ability_name,
    _find_skill_index,
    _iter_flat_tags_static,
    _execute_agility_old,
    _apply_weather_damage,
    # Handlers (used by tests)
    _h_weather,
    # Filters
    _check_runtime_condition,
    _check_skill_filter,
)
