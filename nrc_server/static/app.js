import { createRosterEditor } from './roster.js';
import { createBattleSync } from './battle.js';
/** 对局界面的交互与渲染编排。 */
import { state } from './state.js';
import { api } from './api.js';
import { SESSION_KEY, saveSession, clearSession } from './session.js';
import { RELATION_NAMES, relationLabel, effectName, eventText } from './presentation.js';

const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

const { aptitudeField, aptitudeName, natureBonusText, editorFieldMarkup, choiceMatches, editorChoices, renderEditorSuggestions, applyEditorOption, editorPosition, renderCreatureEditor, closeCreatureEditor, updateCreatureBase, setForm, selectedAptitudes, aptitudeEditorMarkup, selectedSkills, normalizedBase, skillEditorMarkup, addAptitude, removeAptitude, addSkill, removeSkill, previewPosition, previewPayload, renderCreaturePreview, previewForms, loadCreaturePreview, showCreaturePreview, cyclePreviewForm, hideCreaturePreview } = createRosterEditor({ $, esc, formFor, pokemonRow, baseName, renderTeamCard, toast });
const { fetchMatchups, syncEvents, refreshBattle, submitAction } = createBattleSync({ renderEvents, setResolving, playResolution, renderSetup, updateBattleMeta, mergeObservation, renderSide, reset, toast, updateBattleLock, closeDrawer });

function toast(message) {
  const element = $('#toast');
  if (!element) return;
  element.textContent = message;
  element.classList.add('show');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => element.classList.remove('show'), 2600);
}

function baseName(name) { return String(name || '').split('（', 1)[0]; }
function pokemonRow(name) {
  return state.catalog.pokemon.find((row) => row.name === name) || state.catalog.pokemon.find((row) => row.name === baseName(name));
}
function formFor(name) {
  const row = pokemonRow(name);
  return row?.forms?.find((form) => form.name === name) || row?.forms?.[0] || null;
}
function skillMeta(name) { return state.catalog.skills.find((skill) => skill.name === name) || { name, power: '-', energy_cost: '-', element_key: 'normal' }; }
function asset(name, kind) { return formFor(name)?.[kind] || ''; }
const TYPE_NAMES = { normal: '普通', fire: '火', water: '水', electric: '电', grass: '草', ice: '冰', fighting: '武', poison: '毒', ground: '地', flying: '翼', psychic: '幻', bug: '虫', ghost: '幽', dragon: '龙', dark: '恶', steel: '机械', fairy: '萌', light: '光' };
const BUFF_ICONS = { atk_up: '物攻.png', def_up: '物防.png', spatk_up: '魔攻.png', spdef_up: '魔防.png', speed_up: '速度.png', atk_down: '物攻.png', def_down: '物防.png', spatk_down: '魔攻.png', spdef_down: '魔防.png', speed_down: '速度.png', poison: '中毒.png', burn: '灼烧.png', freeze: '冻结.png', leech: '寄生.png', electric: '引电.png', meteor: '星陨印记.png', cute: '萌化.png' };
function typeKey(value) { const text = String(value || '').toLowerCase(); return TYPE_NAMES[text] || text.replace('系', '') || '普通'; }
function typeIcon(value) { return `/assets/dept_icons/${encodeURIComponent(typeKey(value))}.png`; }
function buffIcon(name) { const filename = BUFF_ICONS[name]; return filename ? `/assets/icon_buff/${encodeURIComponent(filename)}` : ''; }
function relationIcon(value) {
  if (typeof value === 'string' && value.startsWith('/assets/')) return value;
  const key = String(value || 'unknown');
  return `/assets/icon_dept_relation/${encodeURIComponent(RELATION_NAMES[key] || key)}.svg`;
}
function battleLocked() {
  state.locked = state.pending || state.submitting || state.syncing || state.resolving || Boolean(state.battle?.terminal);
  return state.locked;
}
function isLegalAction(key) {
  if (battleLocked()) return false;
  return state.actions.some((action) => action.key === key || action.key.startsWith(`${key}|`) || action.key.startsWith(`${key}:`));
}
function actionsOfKind(kind) { return state.actions.filter((action) => action.payload?.primary?.kind === kind); }
function relationBadge(index) {
  const indicator = state.relations.find((item) => item.index === index)?.indicator;
  if (!indicator) return '';
  return `<img class="relation-badge" src="${esc(relationIcon(indicator))}" alt="${esc(relationLabel(indicator))}" title="${esc(relationLabel(indicator))}">`;
}
function freezeState(item) {
  const freeze = Number((item.statuses || []).find((entry) => entry.name === 'freeze')?.stacks ?? 0);
  return { freeze, visible: Number.isFinite(freeze) && freeze > 0, percent: Math.max(0, Math.min(100, freeze * 5)) };
}
function hydrateTeamItem(item, previous = {}) {
  const name = item?.name || previous.name || '';
  const form = formFor(name) || previous.form || item?.form || null;
  const result = { ...previous, ...item, name, base_name: item?.base_name || previous.base_name || form?.base_name || baseName(name), form };
  ensureDefaultCustomization(result);
  return result;
}

function ensureDefaultCustomization(item) {
  if (!item || !item.form) return item;
  const customization = item.form.customization || {};
  item.base = { ...(item.base || {}) };
  if (!item.base.bloodline_attributes?.length && customization.bloodlines?.[0]?.name) {
    item.base.bloodline_attributes = [customization.bloodlines[0].name];
  }
  if (!Object.keys(item.base.individual_values || {}).length) {
    const aptitudes = (customization.aptitudes || []).slice(0, 3);
    if (aptitudes.length) item.base.individual_values = Object.fromEntries(aptitudes.map((aptitude) => [aptitudeField(aptitude.name), 8]));
  }
  return item;
}

function hydrateOwnRoster(roster) {
  const old = state.teams.own || [];
  state.teams.own = (roster || []).map((item, index) => hydrateTeamItem(item, old[index]));
  normalizeSelectedStart();
}

function normalizeSelectedStart() {
  if (!state.teams.own.length) {
    state.selectedStart = 0;
    return;
  }
  const selected = Number(state.selectedStart);
  state.selectedStart = Number.isInteger(selected) && selected >= 0 && selected < state.teams.own.length ? selected : 0;
}

function searchRows(value, category = 'pokemon') {
  const parsed = category === 'pokemon' ? parseCreatureQuery(value) : { name: String(value || '').trim(), invalid: false };
  if (parsed.invalid) return [];
  const query = parsed.name.toLowerCase();
  if (!query) return [];
  if (category === 'pokemon') {
    const pokemon = choiceMatches(state.catalog.pokemon, query).map((row) => ({ ...row, kind: 'pokemon' }));
    return pokemon;
  }
  if (category === 'skill') {
    const skills = choiceMatches(state.catalog.skills, query).map((row) => ({ ...row, kind: 'skill' }));
    return skills;
  }
  if (category === 'all') return [...searchRows(value, 'pokemon'), ...searchRows(value, 'skill')]
}

function parseCreatureQuery(value) {
  const tokens = String(value || '').trim().split(/[\s,\uFF0C]+/).filter(Boolean);
  let numberStart = tokens.length;
  while (numberStart && /^\d+$/.test(tokens[numberStart - 1])) numberStart -= 1;
  const numbers = tokens.slice(numberStart);
  if (numbers.length && ![1, 6].includes(numbers.length)) return { name: '', stats: null, invalid: true };
  const fields = ['hp', 'atk', 'def', 'spatk', 'spdef', 'speed'];
  const stats = {};
  (numbers.length === 1 ? ['hp'] : fields).forEach((field, index) => { if (numbers[index] != null) stats[field] = Number(numbers[index]); });
  return { name: tokens.slice(0, numberStart).join(' '), stats, invalid: false };
}

function renderSuggestions(inputId, boxId) {
  const input = $(inputId);
  const box = $(boxId);
  if (!input || !box) return;
  const rows = searchRows(input.value, input.dataset.suggestCategory || 'pokemon');
  box.innerHTML = rows.map((row) => `<button type="button" class="suggestion" data-suggest-kind="${row.kind}" data-suggest-name="${esc(row.name)}">${row.kind === 'pokemon' ? '精灵' : '技能'} ${esc(row.name)}</button>`).join('');
  box.classList.toggle('hidden', !rows.length);
}

function getTeamCard(side, item, index) {
  const selected = side === 'own' && index === state.selectedStart;
  return `<div class="team-card ${selected ? 'selected-start' : ''}" id="team-card-${index}" data-select-index="${side === 'own' ? index : ''}"><img data-edit-index="${side === 'own' ? index : ''}" src="${esc(asset(item.name, 'art'))}" alt=""><div><b>${esc(item.name)}</b><small>${selected ? '首发 · ' : ''}${esc(item.form?.ability || '')}</small></div><button type="button" class="remove" data-remove-index="${index}">×</button></div>`;
}

function renderTeamCard(side, index, item) {
  const card = $(`#team-card-${index}`);
  if (!card) return;
  card.outerHTML = getTeamCard(side, item, index);
}

function renderTeam(side) {
  const team = state.teams[side] || [];
  const list = $(`#${side}-team`);
  const count = $(`#${side}-count`);
  if (!list || !count) return;
  count.textContent = `${team.length}/6`;
  const signature = JSON.stringify(team.map((item, index) => [item.name, item.form?.ability || '', side === 'own' && index === state.selectedStart]));
  if (list.dataset.renderSignature === signature) return;
  list.dataset.renderSignature = signature;
  list.innerHTML = team.length ? team.map((item, index) => getTeamCard(side, item, index)).join('') : '<div class="team-empty">暂无精灵</div>';
}

function renderSetup() {
  const battle = state.battle;
  normalizeSelectedStart();
  const ownerNeedsSubmit = battle && !battle.roster_submitted;
  const needsConfirmation = Boolean(battle && !battle.confirmed && !ownerNeedsSubmit);
  $('#start').disabled = !state.teams.own.length || (needsConfirmation && state.selectedStart == null) || Boolean(battle?.confirmed);
  $('#start').textContent = !battle ? '创建并提交阵容' : battle.confirmed ? '已确认首发' : needsConfirmation ? '确认首发' : '提交阵容';
  $('#battle-code').value = battle?.battle_id || '';
  $('#battle-code').disabled = Boolean(battle);
  $('#join').disabled = Boolean(battle);
  $('#opponent-search').disabled = true;
  const status = $('#match-status');
  if (!battle) status.textContent = '创建对局后复制 ID，另一位用户输入 ID 加入';
  else if (!battle.joined) status.textContent = battle.confirmed ? '首发已确认，等待对手加入' : '对局已创建，等待对手加入';
  else if (battle.initialized) status.textContent = '对战进行中';
  else if (state.side === 'opponent' && !battle.roster_submitted) status.textContent = '已加入，请编辑阵容并确认首发';
  else if (!battle.confirmed) status.textContent = '双方已加入，请各自编辑阵容并确认首发';
  else status.textContent = '我方首发已确认，等待对方确认';
}

function addCreature(name, stats = {}) {
  const row = pokemonRow(name);
  if (!row || state.teams.own.length >= 6 || state.teams.own.some((item) => item.base_name === row.name)) return false;
  const form = row.forms[0];
  const base = Object.keys(stats).length ? { stats: { ...stats } } : {};
  const item = { name: form.name, base_name: row.name, form, base, skills: (form.default_skills || form.skills || []).slice(0, 4).map((skill) => ({ name: typeof skill === 'string' ? skill : skill.name })) };
  ensureDefaultCustomization(item);
  state.teams.own.push(item);
  saveSession();
  renderSetup();
  renderTeam('own');
  return true;
}

function updateSelectedStart(index) {
  state.selectedStart = Number(index);
  document.querySelectorAll('#own-team .team-card').forEach((card, cardIndex) => {
    const selected = cardIndex === state.selectedStart;
    card.classList.toggle('selected-start', selected);
    const subtitle = card.querySelector('small');
    const item = state.teams.own[cardIndex];
    if (subtitle && item) subtitle.textContent = `${selected ? '首发 · ' : ''}${item.form?.ability || ''}`;
  });
  saveSession();
}

function rosterPayload() {
  return state.teams.own.map((item) => ({ name: item.name, base: normalizedBase(item), skills: selectedSkills(item) }));
}

async function exportRoster() {
  if (!state.teams.own.length) return toast('请先添加至少一只精灵');
  const payload = {
    format: 'nrc-roster-v1',
    selectedStart: state.selectedStart ?? 0,
    roster: rosterPayload(),
  };
  const code = JSON.stringify(payload);
  const field = $('#roster-code');
  field.value = code;
  field.focus();
  field.select();
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(code);
    toast('阵容 Base64 已生成并复制');
  } catch {
    toast('阵容 Base64 已生成');
  }
}

function importRoster() {
  if (state.battle && (state.battle.initialized || state.battle.confirmed || state.battle.roster_submitted)) {
    return toast('当前对局已提交阵容，无法导入');
  }
  const code = $('#roster-code').value.trim();
  if (!code) return toast('请先粘贴阵容 Base64');
  try {
    const decoded = JSON.parse(code);
    const payload = Array.isArray(decoded) ? { roster: decoded, selectedStart: 0 } : decoded;
    if (payload?.format && payload.format !== 'nrc-roster-v1') {
      throw new Error('不支持的阵容格式');
    }
    if (!payload || !Array.isArray(payload.roster) || payload.roster.length < 1 || payload.roster.length > 6) {
      throw new Error('阵容数量必须为 1-6 只');
    }
    const rosterNames = new Set();
    const imported = payload.roster.map((entry, index) => {
      if (!entry || typeof entry !== 'object' || typeof entry.name !== 'string') {
        throw new Error(`第 ${index + 1} 项精灵数据无效`);
      }
      const row = pokemonRow(entry.name);
      const form = formFor(entry.name) || row?.forms?.[0];
      if (!row || !form) throw new Error(`找不到精灵：${entry.name}`);
      if (rosterNames.has(row.name)) throw new Error(`阵容重复选择：${row.name}`);
      rosterNames.add(row.name);
      const skills = Array.isArray(entry.skills) ? entry.skills.map((skill) => ({ name: typeof skill === 'string' ? skill : skill?.name })).filter((skill) => skill.name) : [];
      if (skills.length > 4) throw new Error(`精灵 ${entry.name} 的技能超过 4 个`);
      const item = { name: form.name, base_name: row.name, form, base: entry.base && typeof entry.base === 'object' ? entry.base : {}, skills };
      ensureDefaultCustomization(item);
      return item;
    });
    state.teams.own = imported;
    state.selectedStart = Math.max(0, Math.min(imported.length - 1, Number(payload.selectedStart) || 0));
    closeCreatureEditor();
    saveSession();
    renderSetup();
    renderTeam('own');
    toast('阵容导入成功');
  } catch (error) {
    toast(`导入失败：${error.message || '无效的 Base64'}`);
  }
}

function storeAuth(data) {
  state.playerToken = data.player_token || state.playerToken;
  state.side = data.side || state.side;
  state.battle = { ...state.battle, ...data };
  saveSession();
}

async function createBattle() {
  const created = await api('/api/battles', { method: 'POST', body: JSON.stringify({ mode: 'full', seed: Number($('#seed').value) || 1002 }) });
  storeAuth(created);
  renderSetup();
  copyBattleId();
  toast(`对局已创建，对战 id 已复制`);
}

async function joinBattle() {
  const battleId = $('#battle-code').value.trim();
  if (!battleId) return toast('请输入对战 ID');
  const localRoster = state.teams.own;
  const switchingBattle = Boolean(state.battle?.battle_id && state.battle.battle_id !== battleId);
  clearTimeout(state.pollTimer);
  state.pollTimer = null;
  if (switchingBattle) {
    state.battle = null;
    state.playerToken = '';
    state.side = '';
    state.pending = false;
    state.opponentPending = false;
    state.resolving = false;
    state.submitting = false;
    state.syncing = false;
    state.events = [];
    state.eventCursor = null;
    state.actions = [];
    state.relations = [];
    state.display = { skills: [] };
    state.resolutionToken += 1;
  }
  const joined = await api(`/api/battles/${encodeURIComponent(battleId)}/join`, { method: 'POST', body: '{}' });
  storeAuth(joined);
  state.teams.own = localRoster;
  state.teams.opponent = [];
  normalizeSelectedStart();
  renderSetup();
  renderTeam('own');
  renderTeam('opponent');
  if (state.teams.own.length && !joined.initialized && !joined.roster_submitted) await submitRoster(false);
  await refreshLobby();
}

async function submitRoster(confirm) {
  if (!state.battle || !state.teams.own.length) return;
  if (confirm && state.selectedStart == null) return toast('请先选择一只首发精灵');
  const result = await api(`/api/battles/${state.battle.battle_id}/rosters`, { method: 'POST', body: JSON.stringify({ roster: rosterPayload(), active_index: state.selectedStart ?? 0, confirm }) });
  state.battle = { ...state.battle, ...result };
  saveSession();
  if (result.initialized) await enterBattle();
  else { renderSetup(); startLobbyPolling(); }
}

async function startBattle() {
  try {
    if (!state.teams.own.length) return toast('至少选择一只己方精灵');
    if (!state.battle) { await createBattle(); await submitRoster(false); return; }
    await submitRoster(Boolean(state.battle.roster_submitted));
  } catch (error) { toast(error.message); }
}

async function enterBattle() {
  clearTimeout(state.pollTimer);
  $('#setup').classList.add('hidden');
  $('#battle').classList.remove('hidden');
  $('#battle-id').textContent = state.battle.battle_id;
  await refreshBattle({ refreshDisplay: true });
  startBattlePolling();
}

async function refreshLobby() {
  if (!state.battle || state.pollInFlight) return;
  state.pollInFlight = true;
  try {
    const summary = await api(`/api/battles/${state.battle.battle_id}`);
    state.battle = { ...state.battle, ...summary };
    if (!state.teams.own.length && summary.roster?.length) {
      hydrateOwnRoster(summary.roster);
      saveSession();
    }
    if (!summary.initialized && summary.joined) await refreshOpponentRoster();
    if (summary.initialized) await enterBattle();
    else { renderSetup(); startLobbyPolling(); }
  } catch (error) {
    if (error.status === 404 || error.status === 401) {
      reset();
      toast('对局已失效，请重新创建或加入');
    } else toast(error.message);
  }
  finally { state.pollInFlight = false; }
}

async function refreshOpponentRoster() {
  if (!state.battle) return;
  const data = await api(`/api/battles/${state.battle.battle_id}/opponent-roster`);
  const old = state.teams.opponent || [];
  state.teams.opponent = (data.roster || []).map((item, index) => hydrateTeamItem(item, old[index]));
  renderSetup();
  renderTeam('opponent');
}

function startLobbyPolling() {
  clearTimeout(state.pollTimer);
  if (!state.battle || state.battle.initialized) return;
  state.pollTimer = setTimeout(() => refreshLobby(), 1500);
}

function startBattlePolling() {
  clearTimeout(state.pollTimer);
  if (!state.battle?.initialized || state.battle.terminal) return;
  state.pollTimer = setTimeout(async () => {
    if (state.pollInFlight) return startBattlePolling();
    state.pollInFlight = true;
    try {
      if (state.submitting || state.syncing || state.resolving) return;
      const battleId = state.battle.battle_id;
      const decision = state.battle.decision_index ?? -1;
      const operation = await api(`/api/battles/${battleId}/operation?since=${decision}`);
      // 请求途中可能已完成提交或换回合，旧响应不得覆盖新锁定状态。
      if (state.submitting || state.syncing || state.resolving || state.battle?.battle_id !== battleId || (state.battle.decision_index ?? -1) !== decision) return;
      if (operation.resolved || operation.terminal) {
        await refreshBattle({ refreshDisplay: true, animateEvents: true });
        return;
      }
      const pendingChanged = state.pending !== Boolean(operation.own_pending)
        || state.opponentPending !== Boolean(operation.opponent_pending);
      state.pending = Boolean(operation.own_pending);
      state.opponentPending = Boolean(operation.opponent_pending);
      if (pendingChanged) updateBattleLock();
    } catch (error) {
      if (error.status === 401 || error.status === 404) {toast('对局已失效，请重新创建或加入'); reset();}
      else toast(error.message);
    } finally {
      state.pollInFlight = false;
      startBattlePolling();
    }
  }, 1200);
}

function mergeObservation(data) {
  state.shared = data?.shared || {};
  const own = data?.own_team || [];
  const old = state.teams.own || [];
  state.teams.own = own.map((item, index) => ({ ...old[index], ...item, form: old[index]?.form || formFor(item.name) }));
  state.teams.own.activeIndex = own.findIndex((item) => item.active);
  if (state.teams.own.activeIndex < 0) state.teams.own.activeIndex = 0;
  const opponent = data?.opponent_team || [];
  const oldOpponent = state.teams.opponent || [];
  state.teams.opponent = opponent.map((item, index) => ({ ...oldOpponent[index], ...item, form: oldOpponent[index]?.form || formFor(item.name) }));
  state.teams.opponent.activeIndex = opponent.findIndex((item) => item.active);
  if (state.teams.opponent.activeIndex < 0) state.teams.opponent.activeIndex = 0;
}

function stateEffects(item, side = 'own') {
  const effects = [];
  const add = (name, value, unit = '层') => { if (Number.isFinite(Number(value)) && Number(value) !== 0) effects.push({ name: effectName(name), value, unit }); };
  (item.modifiers || []).forEach((entry) => add(entry.name, entry.stacks, entry.unit));
  (item.statuses || []).forEach((entry) => add(entry.name, entry.stacks, entry.unit));
  (item.skills || []).forEach((skill) => {
    add(`${skill.name} 冷却`, skill.skill_states?.cooldown, '回合');
  });
  Object.entries(state.shared?.marks?.[side] || {}).forEach(([name, value]) => add(`印记 ${name}`, value));
  const devotion = state.shared?.devotion?.[side];
  add('奉献', devotion?.total);
  Object.entries(devotion?.distribution || {}).forEach(([name, value]) => add(`奉献 ${name}`, value));
  return effects;
}

function effectsMarkup(item, side = 'own') {
  return stateEffects(item, side).map(({ name, value, unit }) => `<span class="field-effect" title="${esc(name)}"><span class="field-effect-name">${esc(name)}</span><small>${esc(value)} ${esc(unit)}</small></span>`).join('');
}

function renderSide(side) {
  const enemy = side === 'opponent';
  const team = state.teams[side] || [];
  const activeIndex = team.activeIndex || 0;
  const activeItem = team[activeIndex] || {};
  const item = enemy && activeItem.fainted ? (team.find((candidate) => !candidate.fainted) || activeItem) : activeItem;
  const prefix = enemy ? 'enemy' : 'own';
  const percent = item.max_hp ? Math.max(0, Math.min(100, Math.round(item.hp / item.max_hp * 100))) : item.hp_percent ?? 0;
  $(`#${prefix}-active-name`).textContent = item.name || '-';
  $(`#${prefix}-hp-text`).textContent = item.hp == null ? `${percent ?? '?'}%` : `${item.hp} / ${item.max_hp}`;
  $(`#${prefix}-hp-bar`).style.width = `${percent || 0}%`;
  $(`#${prefix}-energy`).textContent = `能量 ${item.energy == null ? '?' : item.energy}`;
  $(`#${prefix}-active-art`).src = item.portrait || asset(item.name, 'portrait') || asset(item.name, 'art');
  $(`#${prefix}-active-types`).innerHTML = (item.types || []).map((type) => `<img class="field-type" src="${esc(typeIcon(type))}" alt="${esc(typeKey(type))}" title="${esc(typeKey(type))}">`).join('');
  $(`#${prefix}-effects`).innerHTML = effectsMarkup(item, side);
  const frozen = freezeState(item);
  $(`#${prefix}-freeze-bar`).classList.toggle('hidden', !frozen.visible);
  $(`#${prefix}-freeze-bar`).style.width = `${frozen.percent}%`;
  $(`#${prefix}-freeze-text`).classList.toggle('hidden', !frozen.visible);
  $(`#${prefix}-freeze-text`).textContent = `冻结 ${frozen.freeze || 0} 层（${frozen.freeze * 5}%）`;
  $(`#${prefix}-pips`).innerHTML = Array.from({ length: 6 }, (_, index) => {
    const member = team[index];
    const known = Boolean(member) && (!enemy || Boolean(member?.known) || Boolean(member?.name && !['?', '未知精灵'].includes(member.name)));
    const pipClass = !member ? 'empty-pip' : known ? 'known-pip' : 'unknown-pip';
    return `<i class="pip ${pipClass} ${known && member?.fainted ? 'fainted' : ''} ${index === activeIndex ? 'active-pip' : ''}"></i>`;
  }).join('');
}
function switchCardMarkup(action) {
  const index = Number(action.payload?.primary?.switch_index);
  const item = state.teams.own[index] || {};
  const hp = item.hp == null ? '' : `${item.hp} / ${item.max_hp}`;
  return `<button class="skill-card switch-card" data-battle-action="${esc(action.key)}" ${state.pending || state.resolving ? 'disabled' : ''}><span class="skill-icon-wrap"><img class="skill-icon" src="${esc(item.portrait || asset(item.name, 'portrait') || asset(item.name, 'art'))}" alt=""></span><span class="skill-copy"><b class="skill-name">${esc(item.name || `第 ${index + 1} 只`)}</b><small class="skill-kind">第 ${index + 1} 只${hp ? ` · ${esc(hp)}` : ''}</small></span>${relationBadge(index)}</button>`;
}

function renderSkills() {
  if (state.locked == battleLocked()) return; // 锁定状态相同时，反复渲染技能导致频闪
  const container = $('#skills');
  if (state.battle?.phase === 'replacement') {
    const switches = actionsOfKind('switch');
    container.innerHTML = switches.length ? switches.map(switchCardMarkup).join('') : '<div class="event-empty">等待对方选择替换精灵</div>';
    if (battleLocked()) container.querySelectorAll('button').forEach((button) => { button.disabled = true; });
    return;
  }
  container.innerHTML = (state.display.skills || []).map((skill, index) => {
    const meta = skillMeta(skill.name);
    const key = `skill:slot=${skill.skill_slot ?? index}`;
    const disabled = state.pending || state.resolving || !isLegalAction(key);
    const type = skill.element || meta.element || meta.element_key || 'normal';
    const relation = skill.effect_indicator || (skill.type_effectiveness == null ? 'unknown' : skill.type_effectiveness > 2 ? 'super_effective' : skill.type_effectiveness > 1 ? 'effective' : skill.type_effectiveness < 0.5 ? 'very_resistant' : skill.type_effectiveness < 1 ? 'resistant' : 'normal');
    const own = state.teams.own || [];
    const active = own[own.activeIndex || 0];
    const local = active?.skills?.find((entry) => entry.index === (skill.skill_slot ?? index));
    const labels = { power_delta: '威力', energy_cost_delta: '能耗', hit_count_delta: '连击', priority_mod_delta: '先手' };
    const changes = Object.entries(local?.skill_states || {}).filter(([field]) => labels[field]).map(([field, value]) => `${labels[field]}${Number(value) > 0 ? '+' : ''}${value}`);
    const detail = [`连击 ${skill.display_hits ?? meta.hit_count ?? 1}`, `先手 ${skill.display_priority ?? meta.priority_mod ?? 0}`];
    return `<button class="skill-card" title="${esc(changes.join('，'))}" data-skill-name="${esc(skill.name)}" data-battle-action="${esc(key)}" ${disabled ? 'disabled' : ''}><span class="skill-icon-wrap"><img class="skill-icon" src="${esc(skill.icon || meta.icon || '')}" alt=""><span class="skill-cost-badge">${esc(skill.display_energy_cost ?? meta.energy_cost)}</span><span class="skill-power-badge">${skill.display_power > 0 ? skill.display_power : '-'}</span><img class="skill-type-badge" src="${esc(skill.type_icon || typeIcon(type))}" alt="${esc(typeKey(type))}"><img class="skill-relation-badge" src="${esc(relationIcon(skill.effect_icon || relation))}" alt="${esc(relationLabel(relation))}" title="${esc(relationLabel(relation))}"></span><span class="skill-copy"><b class="skill-name">${esc(skill.name)}</b><small class="skill-kind">${esc(meta.category || '技能')} · ${esc(detail.join(' · '))}</small></span></button>`;
  }).join('');
}

function formatDisplayNumber(value) {
  if (value == null || value === '') return '-';
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : String(value);
}

function updateBattleMeta() {
  const summary = state.battle || {};
  $('#turn').textContent = summary.turn || 1;
  $('#phase').textContent = String(summary.phase || 'turn_choice').replaceAll('_', ' ').toUpperCase();
  updateBattleLock();
}

function actionLabel(action) {
  const primary = action.payload?.primary || {};
  if (primary.kind === 'switch') return `切换至第 ${Number(primary.switch_index) + 1} 只精灵`;
  if (primary.kind === 'charge') return '聚能';
  return primary.skill_name || action.key;
}

function renderDrawer(title, html) { $('#drawer-title').textContent = title; $('#drawer-body').innerHTML = html; $('#drawer').classList.remove('hidden'); }
function closeDrawer() { $('#drawer').classList.add('hidden'); }
function drawerEffects(item) {
  const side = (state.teams.opponent || []).includes(item) ? 'opponent' : 'own';
  return stateEffects(item, side).map(({ name, value, unit }) => `<span class="field-effect"><span class="field-effect-name">${esc(name)}</span><small>${esc(value)} ${esc(unit)}</small></span>`).join('');
}

function renderSpiritDrawer() {
  const team = state.teams.own || [];
  const active = team.activeIndex || 0;
  const cards = team.map((item, index) => {
    const maxHp = Number(item.max_hp);
    const hp = Number(item.hp || 0);
    const hpPercent = maxHp > 0 ? Math.max(0, Math.min(100, Math.round(hp / maxHp * 100))) : Number(item.hp_percent || 0);
    const frozen = freezeState(item);
    const types = (item.types || []).map((type) => `<img class="field-type" src="${esc(typeIcon(type))}" alt="${esc(typeKey(type))}">`).join('');
    const switchable = index !== active && !item.fainted && !state.pending && !state.resolving && isLegalAction(`switch:index=${index}`);
    return `<button class="drawer-spirit side-state ${index === active ? 'drawer-state-active' : ''}" data-drawer-switch="${index}" ${switchable ? '' : 'disabled'}>${relationBadge(index)}<div class="spirit-inline"><div class="field-avatar"><img src="${esc(item.portrait || asset(item.name, 'portrait') || asset(item.name, 'art'))}" alt=""><div class="field-types">${types}</div></div><div class="spirit-copy"><div class="side-name"><span>第 ${index + 1} 只</span><b>${esc(item.name || '未知精灵')}</b></div><div class="hp-line"><span>${item.hp == null ? `${hpPercent}%` : `${item.hp} / ${item.max_hp}`}</span><div class="hp-track"><i style="width:${hpPercent}%"></i>${frozen.visible ? `<i class="freeze-overlay" style="width:${frozen.percent}%"></i>` : ''}</div></div>${frozen.visible ? `<div class="freeze-tag">冻结 ${frozen.freeze} 层（${frozen.freeze * 5}%）</div>` : ''}<div class="energy-line">能量 ${item.energy ?? '?'}</div><div class="field-effects">${drawerEffects(item)}</div></div></div></button>`;
  }).join('');
  renderDrawer('精灵', cards);
}
function renderBagDrawer() {
  const actions = state.actions.filter((action) => action.key.includes('resonance'));
  renderDrawer('共鸣魔法', actions.map((action) => `<button class="drawer-action" data-battle-action="${esc(action.key)}">${esc(actionLabel(action))}</button>`).join('') || '<div class="event-empty">暂无可用共鸣魔法</div>');
}

function renderEvents() {
  const events = $('#events');
  events.innerHTML = state.events.length ? state.events.map((event) => `<div class="event-row"><b>R${event.turn || ''}</b><span>${esc(eventText(event))}</span></div>`).join('') : '<div class="event-empty">等待双方选择行动</div>';
  events.scrollTop = events.scrollHeight;
}

function appendEvent(event) {
  const container = $('#events');
  container.querySelector('.event-empty')?.remove();
  container.insertAdjacentHTML('beforeend', `<div class="event-row" data-event-index="${event.event_index ?? ''}"><b>R${event.turn || ''}</b><span>${esc(eventText(event))}</span></div>`);
  container.scrollTop = container.scrollHeight;
}

function setResolving(value) {
  state.resolving = value;
  renderSkills();
  updateBattleLock();
}

function sleep(milliseconds) { return new Promise((resolve) => setTimeout(resolve, milliseconds)); }

async function playResolution(events, data, token) {
  for (const event of events || []) {
    if (token !== state.resolutionToken) return false;
    state.events.push(event);
    appendEvent(event);
    updateBattleMeta();
    await sleep(500);
  }
  if (token !== state.resolutionToken) return false;
  mergeObservation(data);
  renderSide('own');
  renderSide('opponent');
  updateBattleMeta();
  return true;
}

function showSkillTooltip(card) {
  const name = card?.dataset.skillName;
  if (!name) return;
  const meta = skillMeta(name);
  const skill = (state.display.skills || []).find((item) => item.name === name) || {};
  const tooltip = $('#skill-tooltip');
  tooltip.innerHTML = `<b>${esc(name)}</b><p>${esc(skill.description || meta.description || '暂无技能描述')}</p>`;
  tooltip.classList.remove('hidden');
  const rect = card.getBoundingClientRect();
  tooltip.style.left = `${Math.min(window.innerWidth - tooltip.offsetWidth - 12, Math.max(12, rect.left))}px`;
  tooltip.style.top = `${Math.max(12, rect.top - tooltip.offsetHeight - 8)}px`;
}
function hideSkillTooltip() { $('#skill-tooltip')?.classList.add('hidden'); }

function updateBattleLock() {
  renderSkills();
  const lock = $('#lock-state');
  if (lock) lock.textContent = state.resolving || state.syncing ? '正在结算' : state.submitting ? '正在提交' : state.pending ? '已锁定，等待对手' : state.battle?.terminal ? '对局结束' : state.opponentPending ? '对手已锁定，等待我方' : '选择操作';
  const charge = $('#charge');
  if (charge) charge.disabled = state.pending || state.resolving || !isLegalAction('charge');
}

document.addEventListener('mouseover', (event) => {
  const card = event.target.closest('#skills .skill-card');
  if (card) showSkillTooltip(card);
});
document.addEventListener('mouseout', (event) => {
  const card = event.target.closest('#skills .skill-card');
  if (card && !card.contains(event.relatedTarget)) hideSkillTooltip();
});
window.addEventListener('scroll', hideSkillTooltip, true);

function reset(reserve_team = true) {
  let team = null;
  if (reserve_team) team = state.teams, team.opponent = [];
  clearSession();
  if (reserve_team) state.teams = team;
  closeDrawer();
  $('#battle').classList.add('hidden');
  $('#setup').classList.remove('hidden');
  renderSetup();
  renderTeam('own');
  renderTeam('opponent');
}

async function restoreSession() {
  const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
  if (!saved?.battleId || !saved?.playerToken) return;
  state.playerToken = saved.playerToken;
  state.side = saved.side || '';
  state.battle = { battle_id: saved.battleId };
  hydrateOwnRoster(saved.teams || []);
  state.selectedStart = saved.selectedStart ?? 0;
  renderSetup();
  renderTeam('own');
  renderTeam('opponent');
  await refreshLobby();
}

document.addEventListener('input', (event) => {
  if (event.target.id === 'own-search') renderSuggestions('#own-search', '#own-suggest');
  if (event.target.id === 'quick-search') renderSuggestions('#quick-search', '#quick-suggest');
  if (event.target.matches('[data-editor-autocomplete]')) renderEditorSuggestions(event.target);
});

document.addEventListener('focusin', (event) => {
  if (event.target.matches('[data-editor-autocomplete]')) renderEditorSuggestions(event.target);
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !$('#hover-card')?.classList.contains('hidden')) {
    closeCreatureEditor();
    return;
  }
  if (event.code === 'Space' && !$('#preview-card')?.classList.contains('hidden') && !event.target.closest('#hover-card')) {
    event.preventDefault();
    cyclePreviewForm(event.shiftKey ? -1 : 1);
    return;
  }
  if (event.key !== 'Tab' && event.key !== 'Enter') return;
  const editorInput = event.target.closest('[data-editor-autocomplete]');
  if (editorInput) {
    const box = editorInput.parentElement.querySelector('[data-editor-suggest]');
    const first = box?.querySelector('button');
    if (first && !box.classList.contains('hidden')) {
      event.preventDefault();
      applyEditorOption(first, box);
    }
    return;
  }
  const searchInput = event.target.closest('#own-search, #quick-search');
  if (searchInput) handleSearchInput(searchInput, event);
});

function handleSearchInput(searchInput, event = null) {
  const box = $(searchInput.id === 'own-search' ? '#own-suggest' : '#quick-suggest');
  const first = box?.querySelector('[data-suggest-kind]');
  if (first) {
    event?.preventDefault();
    if (first.dataset.suggestKind === 'pokemon') {
      addCreature(first.dataset.suggestName, parseCreatureQuery(searchInput.value).stats || {});
      searchInput.value = '';
      renderSuggestions(`#${searchInput.id}`, searchInput.id === 'own-search' ? '#own-suggest' : '#quick-suggest');
    } else {
      searchInput.value = first.dataset.suggestName;
      box.classList.add('hidden');
    }
  }
}

document.addEventListener('click', (event) => {
  const searchConfirm = event.target.closest('[data-search-confirm]');
  if (searchConfirm) {
    const input = $(`#${searchConfirm.dataset.searchConfirm}`);
    if (input) handleSearchInput(input, event);
    return;
  }
  const removeAptitudeButton = event.target.closest('[data-remove-aptitude]');
  if (removeAptitudeButton) {
    const index = Number($('#hover-card')?.dataset.floatingEditIndex);
    removeAptitude(index, removeAptitudeButton.dataset.removeAptitude);
    return;
  }
  const removeSkillButton = event.target.closest('[data-remove-skill]');
  if (removeSkillButton) {
    const index = Number($('#hover-card')?.dataset.floatingEditIndex);
    removeSkill(index, removeSkillButton.dataset.removeSkill);
    return;
  }
  const editorOption = event.target.closest('[data-editor-option]');
  if (editorOption) {
    applyEditorOption(editorOption);
    return;
  }
  const suggestion = event.target.closest('[data-suggest-kind]');
  if (suggestion && suggestion.dataset.suggestKind === 'pokemon') {
    const searchInput = suggestion.parentElement?.parentElement?.querySelector('input');
    addCreature(suggestion.dataset.suggestName, parseCreatureQuery(searchInput?.value || '').stats || {});
    $('#own-search').value = '';
    $('#quick-search').value = '';
    renderSuggestions('#own-search', '#own-suggest');
    renderSuggestions('#quick-search', '#quick-suggest');
    return;
  }
  const remove = event.target.closest('[data-remove-index]');
  if (remove) { state.teams.own.splice(Number(remove.dataset.removeIndex), 1); if (state.selectedStart >= state.teams.own.length) state.selectedStart = Math.max(0, state.teams.own.length - 1); closeCreatureEditor(); saveSession(); renderSetup(); renderTeam('own'); return; }
  const editorForm = event.target.closest('[data-editor-form]');
  if (editorForm) {
    const index = Number($('#hover-card').dataset.floatingEditIndex);
    const item = state.teams.own[index];
    if (item) {
      setForm(index, editorForm.dataset.editorForm)
      renderCreatureEditor(index);
    }
    return;
  }
  if (event.target.closest('[data-editor-close]')) { closeCreatureEditor(); return; }
  const edit = event.target.closest('[data-edit-index]');
  if (edit && edit.dataset.editIndex !== '') {
    renderCreatureEditor(Number(edit.dataset.editIndex), edit);
    return;
  }
  const select = event.target.closest('[data-select-index]');
  if (select && select.dataset.selectIndex !== '') { updateSelectedStart(select.dataset.selectIndex); return; }
  const action = event.target.closest('[data-battle-action]');
  if (action) { submitAction(action.dataset.battleAction); return; }
  const drawerSwitch = event.target.closest('[data-drawer-switch]');
  if (drawerSwitch) { submitAction(`switch:index=${drawerSwitch.dataset.drawerSwitch}`); return; }
  const menu = event.target.closest('[data-action]');
  if (menu?.dataset.action === 'creature') renderSpiritDrawer();
  else if (menu?.dataset.action === 'bag') renderBagDrawer();
  else if (menu?.dataset.action === 'exit') reset(true);
  else if (menu?.dataset.action === 'reset') reset(false);
});

function onInputChange(event) {
  const index = Number($('#hover-card')?.dataset.floatingEditIndex);
  if (!Number.isInteger(index) || index < 0) return;
  const aptitude = event.target.closest('[data-aptitude-value]');
  if (aptitude) {
    const item = state.teams.own[index];
    if (!item) return;
    item.base = { ...(item.base || {}), individual_values: { ...(item.base?.individual_values || {}) } };
    const value = Math.min(10, Math.max(1, Number(aptitude.value) || 8));
    if (value) item.base.individual_values[aptitude.dataset.aptitudeValue] = value;
    saveSession();
  }
}

document.addEventListener('change', (event) => {
  onInputChange(event);
});


document.addEventListener('input', (event) => {
  onInputChange(event);
});

document.addEventListener('mouseover', (event) => {
  const avatar = event.target.closest('#own-team [data-edit-index]');
  if (!avatar || avatar === state.previewAnchor) return;
  showCreaturePreview(Number(avatar.dataset.editIndex), avatar);
});

document.addEventListener('mouseout', (event) => {
  const avatar = event.target.closest('#own-team [data-edit-index]');
  if (avatar && !avatar.contains(event.relatedTarget)) hideCreaturePreview();
});

window.addEventListener('resize', () => {
  const card = $('#hover-card');
  const index = Number(card?.dataset.floatingEditIndex);
  const anchor = Number.isInteger(index) ? document.querySelector(`#own-team [data-edit-index="${index}"]`) : null;
  if (card && !card.classList.contains('hidden') && anchor) editorPosition(anchor);
  const preview = $('#preview-card');
  if (preview && !preview.classList.contains('hidden') && state.previewAnchor) previewPosition(state.previewAnchor);
});

for (const inputId of ['quick-search', 'own-search']) {
  const input = $(`#${inputId}`);
  if (!input || input.parentElement.querySelector('[data-search-confirm]')) continue;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'search-confirm';
  button.dataset.searchConfirm = inputId;
  button.textContent = '确认';
  button.setAttribute('aria-label', '确认搜索');
  input.parentElement.classList.add('search-with-confirm');
  input.parentElement.append(button);
}
function copyBattleId() {
  if (state.battle?.battle_id) { navigator.clipboard?.writeText(state.battle.battle_id); toast('对战 ID 已复制'); }
}

$('#start').addEventListener('click', startBattle);
$('#export-roster').addEventListener('click', () => exportRoster());
$('#import-roster').addEventListener('click', () => importRoster());
$('#join').addEventListener('click', () => joinBattle().catch((error) => toast(error.message)));
$('#copy-id').addEventListener('click', async () => copyBattleId());
$('#drawer-close').addEventListener('click', closeDrawer);
$('#charge').addEventListener('click', () => submitAction('charge'));

(async () => {
  try {
    state.catalog = await api('/api/catalog/index');
    $('#catalog-status').textContent = `${state.catalog.pokemon.length} 精灵 · ${state.catalog.skills.length} 技能`;
    renderSetup();
    await restoreSession();
    $('#quick-search').disabled = false;
    $('#quick-search').placeholder = "快速索引：精灵 / 技能 / 拼音";
    $('#own-search').disabled = false;
    $('#own-search').placeholder = "精灵名称 / 拼音 / 首字母";
    $('#roster-code').disabled = false;
    $('#roster-code').placeholder = "粘贴阵容代码一键导入";
  } catch (error) {
    $('#catalog-status').textContent = 'INDEX ERROR';
    toast(error.message);
  }
})();
