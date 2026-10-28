"""效果引擎稳定入口；实现按上下文、过滤、处理器、分发和执行器分层。"""

from nrc_core.engine.context import (
    Ctx,
)
from nrc_core.engine.dispatch import (
    _apply_tag,
)
from nrc_core.engine.executor import (
    EffectExecutor,
)
from nrc_core.engine.filters import (
    _check_runtime_condition,
    _check_skill_filter,
)
from nrc_core.engine.handlers_skill import (
    _apply_weather_damage,
    _h_weather,
)
from nrc_core.engine.helpers import (
    _apply_buff,
    _apply_debuff,
    _clear_buffs,
    _clear_debuffs,
    _ability_name,
    _get_ability_name,
    _find_skill_index,
    _adjust_cost_delta,
    _iter_flat_tags_static,
    _apply_permanent_mod,
    _execute_agility_old,
)
from nrc_core.engine.registry import (
    _HANDLERS,
    _ABILITY_HANDLER_OVERRIDES,
)

__all__ = ['Ctx', 'EffectExecutor', '_HANDLERS', '_ABILITY_HANDLER_OVERRIDES', '_apply_tag', '_apply_buff', '_apply_debuff', '_clear_buffs', '_clear_debuffs', '_ability_name', '_get_ability_name', '_find_skill_index', '_adjust_cost_delta', '_iter_flat_tags_static', '_apply_permanent_mod', '_execute_agility_old', '_apply_weather_damage', '_check_runtime_condition', '_check_skill_filter', '_h_weather']
