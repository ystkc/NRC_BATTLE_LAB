"""双人房间管理与展示适配。"""
from __future__ import annotations
import copy
import re
import uuid
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Mapping
from pypinyin import Style, lazy_pinyin
from nrc_platform import BattlePlatform
from nrc_platform.platform import PlatformResult
from nrc_platform.input import merge_creature_spec
from nrc_platform.state import _ABILITY_STATUSES
from nrc_core.pokemon_nature_table import NATURE_BONUSES
TYPE_NAMES = {'normal': '普通', 'fire': '火', 'water': '水', 'electric': '电', 'grass': '草', 'ice': '冰', 'fighting': '武', 'poison': '毒', 'ground': '地', 'flying': '翼', 'psychic': '幻', 'bug': '虫', 'ghost': '幽', 'dragon': '龙', 'dark': '恶', 'steel': '机械', 'fairy': '萌', 'light': '光'}
HIDDEN_EVENT_TYPES = {'display_power', 'ability_candidate', 'weather_candidate', 'counter_candidate'}
MANUAL_LOADOUTS = {'画间沉铁兽': ['连续爪击', '反击拳', '幻象', '鼓劲'], '蹦蹦花': ['毒誓', '见招拆招', '反击拳', '蜡质膜'], '尖嘴狐仙': ['火焰箭', '暴风雪', '晒太阳', '防御'], '深渊蛙': ['沉溺', '叠浪', '网缚', '三连破'], '晶石蜗': ['震击', '跺地', '锐利眼神', '蓄势待发'], '巨灵石': ['跺地', '穿膛', '晒太阳', '吓退'], '恶魔狼': ['力量增效', '贪婪', '一拳', '斩断'], '海豹船长': ['一拳', '水幕冲击', '反击拳', '斩断'], '银月狼王': ['月蚀', '叠加态', '反击拳', '斩断'], '魔力猫': ['孢子', '斩断', '光合作用', '月蚀']}

def _swap_team_code(event: dict[str, Any], side: str) -> dict[str, Any]:
    """把核心队伍编号转换为当前玩家视角。"""
    if side != 'opponent':
        return event
    if event.get('team') in {'a', 'b'}:
        event['team'] = 'b' if event['team'] == 'a' else 'a'
    for key in ('owner_team', 'target_team'):
        if event.get(key) in {'a', 'b'}:
            event[key] = 'b' if event[key] == 'a' else 'a'
    for change in event.get('resource_changes', []):
        if change.get('team') in {'a', 'b'}:
            change['team'] = 'b' if change['team'] == 'a' else 'a'
    for key in ('active', 'hp', 'mp', 'actions'):
        value = event.get(key)
        if isinstance(value, dict) and 'a' in value and ('b' in value):
            event[key] = {'a': value['b'], 'b': value['a']}
    for key in ('before', 'after'):
        if isinstance(event.get(key), dict):
            event[key] = _swap_team_code(event[key], side)
    return event

def _visible_events(session: Mapping[str, Any], side: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in session.get('history', []):
        turn = entry.get('turn', '')
        for raw in entry.get('events', []):
            if raw.get('type') in HIDDEN_EVENT_TYPES:
                continue
            event = _swap_team_code(copy.deepcopy(dict(raw)), side)
            event.setdefault('turn', turn)
            if event.get('private') and event.get('owner_team', event.get('team')) != 'a':
                continue
            if event.get('type') == 'selection':
                if event.get('team') == 'b':
                    event['status'] = 'locked'
                    for field in ('skill', 'action_key', 'kind', 'switch_index', 'resonance'):
                        event.pop(field, None)
                else:
                    event['status'] = 'locked'
            if event.get('type') == 'state_change':
                event['changes'] = [change for change in event.get('changes', []) if change.get('kind') not in {'hp', 'energy'} and (not (event.get('team') == 'b' and (change.get('private') or change.get('kind') == 'skill' or str(change.get('name', '')).startswith(('skill_cost:', 'skill_power:', 'skill_hits:', 'skill_priority:'))))) and (event.get('team') != 'b' or change.get('kind') != 'ability' or str(change.get('name', '')).removesuffix('_negative') in _ABILITY_STATUSES)]
                if not event['changes']:
                    continue
            if event.get('type') == 'turn':
                for phase in ('before', 'after'):
                    state = event.get(phase)
                    if isinstance(state, dict):
                        actions = state.get('actions')
                        if isinstance(actions, dict) and 'b' in actions:
                            actions['b'] = {'kind': actions['b'].get('kind', 'unknown')}
            event['event_index'] = len(result)
            result.append(event)
    return result

def _visible_event_count(session: Mapping[str, Any], side: str='own') -> int:
    return len(_visible_events(session, side))

def _selection_event(platform: BattlePlatform, battle_id: str, side: str, action_key: str, turn: int) -> dict[str, Any]:
    event: dict[str, Any] = {'type': 'selection', 'team': 'a' if side == 'own' else 'b', 'action_key': action_key, 'turn': turn}
    try:
        actions = platform.get_legal_actions(battle_id, side).get('actions', [])
        selected = next((item for item in actions if item.get('key') == action_key), None)
        primary = (selected or {}).get('payload', {}).get('primary', {})
        event['kind'] = primary.get('kind', 'unknown')
        if primary.get('skill_name'):
            event['skill'] = primary['skill_name']
        if primary.get('switch_index') is not None:
            event['switch_index'] = primary['switch_index']
        if '|resonance=' in action_key:
            event['resonance'] = action_key.rsplit('|resonance=', 1)[1]
    except Exception:
        event['kind'] = 'unknown'
    return event

def _public_summary(session: Mapping[str, Any], side: str | None=None) -> dict[str, Any]:
    players = session.get('players') or {}
    teams = session.get('teams') or {}
    confirmed = session.get('confirmed') or {'own': False, 'opponent': False}
    submitted = session.get('roster_submitted') or {'own': False, 'opponent': False}
    ready = [name for name, roster in teams.items() if roster]
    pending = set(session.get('pending') or [])
    own_side = side if side in {'own', 'opponent'} else None
    winner = session.get('winner')
    if own_side and winner is not None:
        winner = int(winner) if own_side == 'own' else 1 - int(winner)
    if session.get('initialized'):
        waiting_for = 'battle'
    elif len(players) < 2:
        waiting_for = 'opponent'
    elif own_side and (not submitted.get(own_side)):
        waiting_for = 'roster'
    elif own_side and (not confirmed.get(own_side)):
        waiting_for = 'first_choice'
    else:
        waiting_for = 'opponent_first_choice' if not all(confirmed.values()) else 'battle'
    return {'battle_id': session['battle_id'], 'mode': session.get('mode', 'full'), 'turn': session.get('turn', 1), 'phase': session.get('phase', 'waiting_for_players'), 'decision_index': session.get('decision_index', 0), 'status': 'finished' if session.get('terminal') else 'active' if session.get('initialized') else 'waiting', 'players': len(players), 'joined': len(players) >= 2, 'ready': ready, 'initialized': bool(session.get('initialized')), 'roster_submitted': bool(own_side and submitted.get(own_side)), 'confirmed': bool(own_side and confirmed.get(own_side)), 'confirmed_sides': [name for name, value in confirmed.items() if value], 'waiting_for': waiting_for, 'pending': bool(own_side and own_side in pending), 'terminal': bool(session.get('terminal')), 'winner': winner, 'event_count': _visible_event_count(session, own_side or 'own'), 'roster': copy.deepcopy(teams.get(own_side) or []) if own_side else []}

def _base_name(name: str) -> str:
    return re.split('[（(]', str(name), maxsplit=1)[0].strip()

def _pinyin(value: str) -> tuple[str, str]:
    syllables = lazy_pinyin(value)
    return (''.join(syllables), ''.join(lazy_pinyin(value, style=Style.FIRST_LETTER)))

def _distribution_options(catalog: Any, name: str, kind: str) -> list[dict[str, Any]]:
    rows = catalog.get_distribution(name, kind)
    return [{'name': str(row.get('item', '')), 'percentage': float(row.get('percentage', 0))} for row in rows if row.get('item')]

def _customization_options(catalog: Any, name: str) -> dict[str, Any]:
    nature_rows = _distribution_options(catalog, name, 'nature')
    bloodline_rows = _distribution_options(catalog, name, 'blood')
    aptitude_rows = _distribution_options(catalog, name, 'talent')
    if not nature_rows:
        nature_rows = [{'name': nature, 'percentage': 0} for nature in NATURE_BONUSES]
    if not bloodline_rows:
        all_bloodlines = sorted({str(row.get('item')) for (spirit, kind), rows in catalog.distributions.items() if kind == 'blood' for row in rows if row.get('item')})
        bloodline_rows = [{'name': bloodline, 'percentage': 0} for bloodline in all_bloodlines]
    bonus = {nature: {key: float(value) for key, value in values.items() if float(value)} for nature, values in NATURE_BONUSES.items()}

    def enrich(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            item = dict(row)
            pinyin, initials = _pinyin(str(item.get('name', '')))
            item.update({'pinyin': pinyin, 'initials': initials})
            result.append(item)
        return result
    return {'natures': enrich(nature_rows), 'nature_bonus': bonus, 'bloodlines': enrich(bloodline_rows), 'aptitudes': enrich(aptitude_rows)}

def _catalog_index(platform: BattlePlatform) -> dict[str, Any]:
    catalog = platform._catalog.catalog
    forms: dict[str, list[dict[str, Any]]] = {}
    for name, record in catalog.pokemon.items():
        pinyin, initials = _pinyin(_base_name(name))
        forms.setdefault(_base_name(name), []).append({'name': name, 'base_name': _base_name(name), 'types': list(record.get('types', ())), 'ability': record.get('ability', ''), 'skills': list(record.get('skills', ())), 'default_skills': list(MANUAL_LOADOUTS.get(_base_name(name), record.get('skills', ()))[:4]), 'pinyin': pinyin, 'initials': initials, 'customization': _customization_options(catalog, name), 'aliases': ['bbh'] if _pinyin(_base_name(name))[1].casefold() == 'bbh' else []})
    pokemon = [{'name': base, 'pinyin': _pinyin(base)[0], 'initials': _pinyin(base)[1], 'aliases': sorted({alias for form in values for alias in form.get('aliases', [])}), 'forms': values} for base, values in sorted(forms.items())]
    skills = []
    for name, skill in catalog.skills.items():
        element = getattr(getattr(skill, 'skill_type', None), 'value', 'normal')
        skills.append({'name': name, 'pinyin': _pinyin(name)[0], 'initials': _pinyin(name)[1], 'element': TYPE_NAMES.get(element, element), 'element_key': element, 'category': getattr(getattr(skill, 'category', None), 'value', '状态'), 'energy_cost': int(skill.energy_cost), 'power': int(skill.power), 'description': str(getattr(skill, 'description', '') or catalog.skill_descriptions.get(name, ''))})
    return {'pokemon': pokemon, 'skills': sorted(skills, key=lambda row: row['name'])}

def _resolve_record(platform: BattlePlatform, name: str) -> Mapping[str, Any] | None:
    parsed = merge_creature_spec({'name': name})
    direct = platform.resolve_pokemon(parsed.get('name', ''))
    if direct:
        return direct
    catalog = platform._catalog.catalog
    direct = catalog.get_pokemon(name)
    if direct:
        return direct
    normalized = name.replace('(', '（').replace(')', '）').replace('（短毛球）', '（短毛球形态）').replace('（火山琉璃）', '（火山琉璃的样子）')
    direct = catalog.get_pokemon(normalized)
    if direct:
        return direct
    base = _base_name(name)
    return next((record for key, record in catalog.pokemon.items() if _base_name(key) == base), None)

def _creature_preview(platform: BattlePlatform, name: str) -> dict[str, Any]:
    record = _resolve_record(platform, name) or {}
    base = _base_name(name)
    pinyin, initials = _pinyin(base)
    return {'name': record.get('name', name), 'base_name': base, 'types': list(record.get('types', ())), 'ability': record.get('ability', ''), 'skills': list(record.get('skills', ())), 'pinyin': pinyin, 'initials': initials}

def _normalize_roster(platform: BattlePlatform, raw: Any, *, allow_empty: bool) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError('invalid roster')
    result = []
    for item in raw:
        if isinstance(item, str):
            item = {'name': item}
        if not isinstance(item, dict):
            continue
        item = merge_creature_spec(item)
        record = _resolve_record(platform, str(item.get('name', '')).strip())
        if record is None:
            raise ValueError(f"unknown creature: {item.get('name')}")
        name = str(record['name'])
        base = _base_name(name)
        skill_names = [skill.get('name') if isinstance(skill, dict) else skill for skill in item.get('skills') or MANUAL_LOADOUTS.get(base) or list(record.get('skills', ()))[:4]]
        if len(skill_names) < 4:
            raise ValueError(f'{name} must provide all skill slots')
        creature = copy.deepcopy(item)
        creature.update({'name': name, 'skills': [{'name': skill} for skill in skill_names[:4]]})
        result.append(creature)
    if not result and (not allow_empty):
        raise ValueError('each team needs at least one creature')
    return result

def _room_operation(method):
    """让房间准备、核心推进和展示事件共用同一事务锁。"""

    @wraps(method)
    def call(self, battle_id, *args, **kwargs):
        """执行操作并在写入失败时恢复整场状态。"""
        battle = self.platform._get_battle(battle_id)
        with battle.lock:
            mutable = method.__name__ in {'join_battle', 'set_rosters', 'select_action'}
            if mutable:
                before_room = copy.deepcopy(self.rooms.get(battle_id))
                before = {key: copy.deepcopy(value) for key, value in vars(battle).items() if key not in {'lock', 'episode'}}
                before['episode'] = self.platform._backend.clone(battle.episode) if battle.episode else None
            try:
                return method(self, battle_id, *args, **kwargs)
            except Exception:
                if mutable:
                    self.rooms[battle_id] = before_room
                    for key, value in before.items():
                        setattr(battle, key, value)
                raise
    return call

class RoomService:
    """双人房间管理与展示适配。"""

    def __init__(self, platform: BattlePlatform | None=None):
        """双人房间管理与展示适配。"""
        self.platform = platform or BattlePlatform()
        self.rooms: dict[str, dict[str, Any]] = {}
        self.catalog_cache = None

    def _room(self, battle_id: str) -> dict[str, Any]:
        """双人房间管理与展示适配。"""
        if battle_id not in self.rooms:
            raise ValueError('battle not found')
        room = dict(self.rooms[battle_id])
        room.update(self.platform.get_battle_status(battle_id))
        room['history'] = self.platform._get_battle(battle_id).history
        if not room['initialized'] and any(room['roster_submitted'].values()):
            room['phase'] = 'waiting_for_first_choice'
        return room

    def _member(self, room: Mapping[str, Any], identity: str) -> tuple[str, str]:
        """双人房间管理与展示适配。"""
        side = room.get('players', {}).get(identity)
        if side is None:
            raise ValueError('player is not a member of this battle')
        return (identity, str(side))

    def catalog_index(self) -> Any:
        """双人房间管理与展示适配。"""
        if self.catalog_cache is None:
            self.catalog_cache = _catalog_index(self.platform)
        return self.catalog_cache

    def catalog(self, kind: str='pokemon', q: str='') -> Any:
        """双人房间管理与展示适配。"""
        index = self.catalog_index()
        rows = index.get('pokemon' if kind == 'pokemon' else 'skills', [])
        text = q.strip().casefold()
        if not text:
            return rows
        return [row for row in rows if text in row['name'].casefold() or text in row['pinyin'] or text in row['initials']][:30]

    def pokemon_detail(self, name: str) -> Any:
        """双人房间管理与展示适配。"""
        record = _resolve_record(self.platform, name)
        if record is None:
            raise ValueError('pokemon not found')
        return _creature_preview(self.platform, record['name'])

    def pokemon_preview(self, payload: Mapping[str, Any]) -> Any:
        """双人房间管理与展示适配。"""
        name = str(payload.get('name') or '').strip()
        record = _resolve_record(self.platform, name)
        if record is None:
            raise ValueError('pokemon not found')
        creature = merge_creature_spec({'name': name, 'base': copy.deepcopy(payload.get('base') or {}), 'skills': copy.deepcopy(payload.get('skills') or [])})
        creature['name'] = record['name']
        result = self.platform.preview_creature(creature)
        result.update({})
        return result

    def create_battle(self, identity: str, payload: Mapping[str, Any]) -> Any:
        """双人房间管理与展示适配。"""
        mode = str(payload.get('mode', 'full'))
        result = self.platform.create_battle(mode=mode, seed=payload.get('seed'))
        player_token = identity
        self.rooms[result.battle_id] = {'battle_id': result.battle_id, 'mode': mode, 'teams': {'own': None, 'opponent': None}, 'players': {player_token: 'own'}, 'confirmed': {'own': False, 'opponent': False}, 'roster_submitted': {'own': False, 'opponent': False}, 'active_index': {'own': None, 'opponent': None}}
        response = result.to_dict()
        response.update({'player_token': player_token, 'side': 'own', 'status': 'waiting'})
        return response

    @_room_operation
    def join_battle(self, battle_id: str, identity: str) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = (identity, session['players'][identity]) if identity in session['players'] else None
        if current:
            token, side = current
            return {'player_token': token, 'side': side, **_public_summary(self._room(battle_id), side)}
        players = session.setdefault('players', {})
        if len(players) >= 2:
            raise ValueError('battle already has two players')
        player_token = identity
        players[player_token] = 'opponent'
        return {'player_token': player_token, 'side': 'opponent', **_public_summary(session, 'opponent')}

    @_room_operation
    def battle_summary(self, battle_id: str, identity: str) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        return _public_summary(session, current[1] if current else None)

    @_room_operation
    def opponent_roster(self, battle_id: str, identity: str) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        if not current:
            raise ValueError('player token is required')
        side = current[1]
        other_side = 'opponent' if side == 'own' else 'own'
        observation = self.platform.get_public_observation(battle_id, side)
        return {'battle_id': battle_id, 'side': side, 'opponent_side': other_side, 'submitted': bool(session['roster_submitted'].get(other_side)), 'confirmed': bool(session['confirmed'].get(other_side)), 'roster': observation.get('data', {}).get('opponent_team', [])}

    @_room_operation
    def set_rosters(self, battle_id: str, identity: str, payload: Mapping[str, Any]) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        if 'teams' in payload or 'side' in payload:
            raise ValueError('submit only the authenticated player roster')
        if session.get('initialized'):
            raise ValueError('battle has already started')
        side = current[1]
        raw = payload.get('roster')
        roster = _normalize_roster(self.platform, raw, allow_empty=False)
        active_index = int(payload.get('active_index', 0))
        if active_index < 0 or active_index >= len(roster):
            raise ValueError('active_index must point to a creature in the roster')
        session['teams'][side] = roster
        session['active_index'][side] = active_index
        session['roster_submitted'][side] = True
        session['confirmed'][side] = bool(payload.get('confirm', False))
        initialized = False
        if all(session['confirmed'].values()) and all(session['teams'].values()):
            own_result = self.platform.set_roster(battle_id, 'own', {'creatures': session['teams']['own'], 'active_index': session['active_index']['own']}, request_id=f'{uuid.uuid4().hex}-own-team')
            result = self.platform.set_roster(battle_id, 'opponent', {'creatures': session['teams']['opponent'], 'active_index': session['active_index']['opponent']}, request_id=f'{uuid.uuid4().hex}-opponent-team')
            initialized = bool(result.initialized or own_result.initialized)
            if initialized:
                session.setdefault('history', []).append({'turn': 1, 'events': [{'type': 'round_start', 'turn': 1}]})
                session['history'].append({'turn': 1, 'events': [{'type': 'battle_start', 'message': '对战开始，双方选择行动'}]})
                session['history'].append({'turn': 1, 'events': list(result.events or own_result.events or [])})
        return {'accepted': True, 'initialized': initialized, 'phase': self._room(battle_id)['phase'], 'side': side, 'active_index': active_index, **_public_summary(self._room(battle_id), side)}

    @_room_operation
    def display(self, battle_id: str, identity: str) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        actual_side = current[1]
        result = self.platform.get_display_info(battle_id, actual_side)
        for skill in result.get('skills', []):
            name = str(skill.get('name') or '')
            meta = self.platform._catalog.catalog.skills.get(name)
            element = getattr(getattr(meta, 'skill_type', None), 'value', 'normal')
            skill.update({'description': str(getattr(meta, 'description', '') or ''), 'element': TYPE_NAMES.get(element, element)})
        return result

    @_room_operation
    def matchups(self, battle_id: str, identity: str) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        actual_side = current[1]
        return self.platform.get_matchup_relations(battle_id, actual_side)

    @_room_operation
    def actions(self, battle_id: str, identity: str) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        actual_side = current[1]
        return self.platform.get_legal_actions(battle_id, actual_side)

    @_room_operation
    def public_state(self, battle_id: str, identity: str) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        actual_side = current[1]
        result = self.platform.get_public_observation(battle_id, actual_side)
        return result

    @_room_operation
    def operation(self, battle_id: str, identity: str, since: int=-1) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        if not current:
            raise ValueError('player token is required')
        side = current[1]
        opponent = 'opponent' if side == 'own' else 'own'
        pending = set(session.get('pending') or [])
        decision_index = int(session.get('decision_index', 0))
        return {'battle_id': battle_id, 'side': side, 'own_pending': side in pending, 'opponent_pending': opponent in pending, 'resolved': since >= 0 and decision_index != since, 'decision_index': decision_index, 'turn': session.get('turn', 1), 'phase': session.get('phase', 'waiting_for_players'), 'terminal': bool(session.get('terminal'))}

    @_room_operation
    def battle_events(self, battle_id: str, identity: str, since: int=0) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        current = self._member(session, identity)
        if not current:
            raise ValueError('player token is required')
        events = _visible_events(session, current[1])
        cursor = max(0, min(int(since), len(events)))
        return {'battle_id': battle_id, 'side': current[1], 'events': events[cursor:], 'cursor': len(events), 'total': len(events)}

    @_room_operation
    def select_action(self, battle_id: str, identity: str, payload: Mapping[str, Any]) -> Any:
        """双人房间管理与展示适配。"""
        session = self._room(battle_id)
        side = self._member(session, identity)[1]
        key = str(payload.get('action_key', ''))
        if not key:
            raise ValueError('action_key is required')
        request_id = str(payload.get('request_id') or uuid.uuid4())
        battle = self.platform._get_battle(battle_id)
        response_key = f'room-response:{side}:{request_id}'
        if response_key in battle.requests:
            return battle.requests[response_key].to_dict()
        replay = f'{side}:{request_id}' in battle.requests
        selection = None if replay else _selection_event(self.platform, battle_id, side, key, session['turn'])
        result = self.platform.submit_selection(battle_id, side, key, request_id=request_id, decision_index=payload.get('decision_index'))
        if not replay:
            entry = {'turn': session['turn'], 'events': [selection], 'source': 'room'}
            if result.resolved:
                battle.history.insert(len(battle.history) - 1, entry)
                status = self.platform.get_battle_status(battle_id)
                if not status['terminal']:
                    battle.history.append({'turn': status['turn'], 'events': [{'type': 'round_start', 'turn': status['turn']}], 'source': 'room'})
            else:
                battle.history.append(entry)
        response = result.to_dict()
        response['side'] = side
        response['event_count'] = _visible_event_count(self._room(battle_id), side)
        if response.get('result'):
            core_entry = next((entry for entry in reversed(battle.history)
                               if entry.get('source') == 'core' and entry.get('decision_index') == result.decision_index), {})
            response['result'] = {'events': _visible_events({'history': [{'turn': core_entry.get('turn', session['turn']), 'events': response['result'].get('events', [])}]}, side)}
        if response.get('winner') is not None and side == 'opponent':
            response['winner'] = 1 - int(response['winner'])
        battle.requests[response_key] = PlatformResult(copy.deepcopy(response))
        return response


