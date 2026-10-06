const state = {
  catalog: { pokemon: [], skills: [] },
  battle: null,
  playerToken: '',
  side: '',
  teams: { own: [], opponent: [] },
  selectedStart: 0,
  actions: [],
  display: { skills: [] },
  events: [],
  pending: false,
  pollTimer: null,
  pollInFlight: false,
};

const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

function headers() {
  const result = { 'Content-Type': 'application/json' };
  if (state.playerToken) result['X-Player-Token'] = state.playerToken;
  return result;
}

async function api(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.error || '请求失败');
  return data;
}

function toast(message) {
  const element = $('#toast');
  if (!element) return;
  element.textContent = message;
  element.classList.add('show');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => element.classList.remove('show'), 2600);
}

function saveSession() {
  if (!state.battle?.battle_id || !state.playerToken) return;
  localStorage.setItem('nrc-battle-session', JSON.stringify({ battleId: state.battle.battle_id, playerToken: state.playerToken, side: state.side, selectedStart: state.selectedStart, teams: state.teams.own }));
}

function clearSession() {
  localStorage.removeItem('nrc-battle-session');
  state.battle = null;
  state.playerToken = '';
  state.side = '';
  state.teams = { own: [], opponent: [] };
  state.selectedStart = 0;
  state.events = [];
  state.pending = false;
  clearTimeout(state.pollTimer);
  state.pollTimer = null;
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

function searchRows(value) {
  const query = String(value || '').trim().toLowerCase();
  if (!query) return [];
  const pokemon = state.catalog.pokemon.filter((row) => [row.name, row.pinyin, row.initials].some((item) => String(item || '').toLowerCase().includes(query))).map((row) => ({ ...row, kind: 'pokemon' }));
  const skills = state.catalog.skills.filter((row) => [row.name, row.pinyin, row.initials].some((item) => String(item || '').toLowerCase().includes(query))).map((row) => ({ ...row, kind: 'skill' }));
  return [...pokemon, ...skills].slice(0, 8);
}

function renderSuggestions(inputId, boxId) {
  const input = $(inputId);
  const box = $(boxId);
  if (!input || !box) return;
  const rows = searchRows(input.value);
  box.innerHTML = rows.map((row) => `<button type="button" class="suggestion" data-suggest-kind="${row.kind}" data-suggest-name="${esc(row.name)}">${row.kind === 'pokemon' ? '精灵' : '技能'} ${esc(row.name)}</button>`).join('');
  box.classList.toggle('hidden', !rows.length);
}

function renderTeam(side) {
  const team = state.teams[side] || [];
  const list = $(`#${side}-team`);
  const count = $(`#${side}-count`);
  if (!list || !count) return;
  count.textContent = `${team.length}/6`;
  list.innerHTML = team.length ? team.map((item, index) => {
    const selected = side === 'own' && index === state.selectedStart;
    return `<div class="team-card ${selected ? 'selected-start' : ''}" data-select-index="${side === 'own' ? index : ''}"><img src="${esc(asset(item.name, 'portrait'))}" alt=""><div><b>${esc(item.name)}</b><small>${selected ? '首发 · ' : ''}${esc(item.form?.ability || '')}</small></div><button type="button" class="remove" data-remove-index="${index}">×</button></div>`;
  }).join('') : '<div class="team-empty">暂无精灵</div>';
}

function renderSetup() {
  renderTeam('own');
  renderTeam('opponent');
  const battle = state.battle;
  const ownerNeedsSubmit = battle && state.side === 'own' && !battle.roster_submitted;
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

function addCreature(name) {
  const row = pokemonRow(name);
  if (!row || state.teams.own.length >= 6 || state.teams.own.some((item) => item.base_name === row.name)) return;
  const form = row.forms[0];
  state.teams.own.push({ name: form.name, base_name: row.name, form, skills: (form.default_skills || form.skills || []).slice(0, 4).map((skill) => ({ name: typeof skill === 'string' ? skill : skill.name })) });
  saveSession();
  renderSetup();
}

function rosterPayload() {
  return state.teams.own.map((item) => ({ name: item.name, base: item.base || {}, skills: (item.skills || []).map((skill) => typeof skill === 'string' ? skill : skill.name).filter(Boolean) }));
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
  toast(`对局已创建：${created.battle_id}`);
}

async function joinBattle() {
  const battleId = $('#battle-code').value.trim();
  if (!battleId) return toast('请输入对战 ID');
  const joined = await api(`/api/battles/${encodeURIComponent(battleId)}/join`, { method: 'POST', body: '{}' });
  storeAuth(joined);
  state.teams.own = [];
  state.selectedStart = 0;
  renderSetup();
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
    const initialOwnerSubmit = state.side === 'own' && !state.battle.roster_submitted;
    await submitRoster(!initialOwnerSubmit);
  } catch (error) { toast(error.message); }
}

async function enterBattle() {
  clearTimeout(state.pollTimer);
  $('#setup').classList.add('hidden');
  $('#battle').classList.remove('hidden');
  $('#battle-id').textContent = state.battle.battle_id;
  await refreshBattle();
  startBattlePolling();
}

async function refreshLobby() {
  if (!state.battle || state.pollInFlight) return;
  state.pollInFlight = true;
  try {
    const summary = await api(`/api/battles/${state.battle.battle_id}`);
    state.battle = { ...state.battle, ...summary };
    if (summary.initialized) await enterBattle();
    else { renderSetup(); startLobbyPolling(); }
  } catch (error) { toast(error.message); }
  finally { state.pollInFlight = false; }
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
    await refreshBattle();
    startBattlePolling();
  }, 1200);
}

function mergeObservation(data) {
  const own = data?.own_team || [];
  const old = state.teams.own || [];
  state.teams.own = own.map((item, index) => ({ ...old[index], ...item, form: old[index]?.form || formFor(item.name) }));
  state.teams.own.activeIndex = own.findIndex((item) => item.active);
  if (state.teams.own.activeIndex < 0) state.teams.own.activeIndex = 0;
  const opponent = data?.opponent_team || [];
  state.teams.opponent = opponent.map((item) => ({ ...item }));
  state.teams.opponent.activeIndex = opponent.findIndex((item) => item.active);
  if (state.teams.opponent.activeIndex < 0) state.teams.opponent.activeIndex = 0;
}

function renderSide(side) {
  const enemy = side === 'opponent';
  const team = state.teams[side] || [];
  const item = team[team.activeIndex || 0] || {};
  const prefix = enemy ? 'enemy' : 'own';
  const percent = enemy ? item.hp_percent : item.max_hp ? Math.max(0, Math.round(item.hp / item.max_hp * 100)) : 0;
  $(`#${prefix}-active-name`).textContent = enemy ? '未知' : (item.name || '-');
  $(`#${prefix}-hp-text`).textContent = enemy ? `${percent ?? '?'}%` : item.hp == null ? '?' : `${item.hp} / ${item.max_hp}`;
  $(`#${prefix}-hp-bar`).style.width = `${percent || 0}%`;
  $(`#${prefix}-energy`).textContent = `能量 ${item.energy == null ? '?' : item.energy}`;
  if (!enemy) $(`#${prefix}-active-art`).src = asset(item.name, 'portrait');
  if (!enemy) {
    const box = $('#own-pips');
    box.innerHTML = Array.from({ length: 6 }, (_, index) => `<i class="pip ${team[index] ? 'owned' : ''} ${team[index]?.fainted ? 'fainted' : ''} ${index === (team.activeIndex || 0) ? 'active-pip' : ''}></i>`).join('');
  }
}

function renderSkills() {
  $('#skills').innerHTML = (state.display.skills || []).map((skill, index) => {
    const meta = skillMeta(skill.name);
    return `<button class="skill-card" data-battle-action="skill:slot=${skill.skill_slot ?? index}" ${state.pending ? 'disabled' : ''}><span class="skill-icon-wrap"><span class="skill-cost-badge">${esc(skill.display_energy_cost ?? meta.energy_cost)}</span><span class="skill-power-badge">${skill.display_power > 0 ? skill.display_power : '-'}</span></span><span class="skill-copy"><b class="skill-name">${esc(skill.name)}</b><small class="skill-kind">${esc(meta.category || '技能')}</small></span></button>`;
  }).join('');
}

function actionLabel(action) {
  const primary = action.payload?.primary || {};
  if (primary.kind === 'switch') return `切换至第 ${Number(primary.switch_index) + 1} 只精灵`;
  if (primary.kind === 'charge') return '聚能';
  return primary.skill_name || action.key;
}

function renderDrawer(title, html) { $('#drawer-title').textContent = title; $('#drawer-body').innerHTML = html; $('#drawer').classList.remove('hidden'); }
function closeDrawer() { $('#drawer').classList.add('hidden'); }
function renderSpiritDrawer() {
  const team = state.teams.own || [];
  const active = team.activeIndex || 0;
  renderDrawer('精灵', team.map((item, index) => `<button class="drawer-spirit" data-drawer-switch="${index}" ${index === active || item.fainted ? 'disabled' : ''}>${esc(item.name)} · HP ${item.hp ?? '?'} · 能量 ${item.energy ?? '?'}</button>`).join(''));
}
function renderBagDrawer() {
  const actions = state.actions.filter((action) => action.key.includes('resonance'));
  renderDrawer('共鸣魔法', actions.map((action) => `<button class="drawer-action" data-battle-action="${esc(action.key)}">${esc(actionLabel(action))}</button>`).join('') || '<div class="event-empty">暂无可用共鸣魔法</div>');
}

function eventText(event) {
  const actor = event.team === 'a' ? '我方' : event.team === 'b' ? '敌方' : '';
  if (event.type === 'round_start') return `## 第${event.turn || '?'}回合`;
  if (event.type === 'battle_start') return '[对战开始] 双方选择行动';
  if (event.type === 'selection') {
    if (event.resonance) {
      const names = { boss: '进化之力', willpower: '愿力强化', solar_heal: '光合治疗' };
      return `[${actor}使用共鸣魔法] ${names[event.resonance] || event.resonance}`;
    }
    if (event.status === 'locked') return event.skill ? `[${actor}选择技能] ${event.skill}，选择了技能` : `[${actor}选择技能] 完成`;
    if (event.kind === 'switch') return `[${actor}选择切换精灵] 完成`;
    return `[${actor}选择技能] ${event.skill || event.action_key || '完成'}`;
  }
  if (event.type === 'skill') {
    const details = [];
    if (event.final_power != null) details.push(`威力 ${event.final_power}`);
    if (event.final_damage != null) details.push(`造成 ${event.final_damage} 伤害`);
    if (event.remaining_energy != null) details.push(`剩余能量 ${event.remaining_energy}`);
    return `[${actor}使用技能] ${event.team === 'b' ? '完成' : (event.skill || '技能')}${details.length ? `，${details.join('，')}` : ''}`;
  }
  if (event.type === 'switch' || event.switched_to || event.target_switched_to) return `[${actor}切换精灵] ${event.switched_to || event.target_switched_to || '未知精灵'}`;
  if (event.type === 'turn') return `[回合结束] 第${event.after?.turn || event.turn || '?'}回合`;
  if (event.type === 'status') return `[状态结算] ${event.status || event.message || '状态变化'}`;
  return event.message || event.text || `[${event.type || '战斗事件'}]`;
}

function renderEvents() {
  $('#events').innerHTML = state.events.length ? state.events.map((event) => `<div class="event-row"><b>R${event.turn || ''}</b><span>${esc(eventText(event))}</span></div>`).join('') : '<div class="event-empty">等待双方选择行动</div>';
}

function renderBattle() {
  const summary = state.battle || {};
  $('#turn').textContent = summary.turn || 1;
  $('#phase').textContent = String(summary.phase || 'turn_choice').replaceAll('_', ' ').toUpperCase();
  $('#lock-state').textContent = summary.pending ? '已锁定，等待对手' : '选择操作';
  renderSide('own');
  renderSide('opponent');
  renderSkills();
  renderEvents();
}

async function refreshBattle() {
  if (!state.battle) return;
  try {
    const id = state.battle.battle_id;
    const summary = await api(`/api/battles/${id}`);
    state.battle = { ...state.battle, ...summary };
    if (!summary.initialized) return renderSetup();
    mergeObservation((await api(`/api/battles/${id}/state?side=own`)).data);
    state.display = await api(`/api/battles/${id}/display?side=own`);
    state.actions = (await api(`/api/battles/${id}/actions?side=own`)).actions || [];
    state.pending = Boolean(summary.pending);
    state.events = summary.events || [];
    renderBattle();
  } catch (error) { toast(error.message); }
}

async function submitAction(key) {
  if (!key || state.pending || !state.battle) return;
  try {
    const result = await api(`/api/battles/${state.battle.battle_id}/selection`, { method: 'POST', body: JSON.stringify({ action_key: key }) });
    state.pending = !result.resolved;
    await refreshBattle();
    closeDrawer();
    if (result.terminated) toast(result.winner === 0 ? '我方获胜' : result.winner === 1 ? '敌方获胜' : '对局结束');
  } catch (error) { toast(error.message); }
}

function reset() {
  clearSession();
  closeDrawer();
  $('#battle').classList.add('hidden');
  $('#setup').classList.remove('hidden');
  renderSetup();
}

async function restoreSession() {
  const saved = JSON.parse(localStorage.getItem('nrc-battle-session') || 'null');
  if (!saved?.battleId || !saved?.playerToken) return;
  state.playerToken = saved.playerToken;
  state.side = saved.side || '';
  state.battle = { battle_id: saved.battleId };
  state.teams.own = (saved.teams || []).map((item) => ({ ...item, form: formFor(item.name) || item.form }));
  state.selectedStart = saved.selectedStart ?? 0;
  await refreshLobby();
}

document.addEventListener('input', (event) => {
  if (event.target.id === 'own-search') renderSuggestions('#own-search', '#own-suggest');
  if (event.target.id === 'quick-search') renderSuggestions('#quick-search', '#quick-suggest');
});

document.addEventListener('click', (event) => {
  const suggestion = event.target.closest('[data-suggest-kind]');
  if (suggestion && suggestion.dataset.suggestKind === 'pokemon') {
    addCreature(suggestion.dataset.suggestName);
    $('#own-search').value = '';
    $('#quick-search').value = '';
    renderSuggestions('#own-search', '#own-suggest');
    renderSuggestions('#quick-search', '#quick-suggest');
    return;
  }
  const remove = event.target.closest('[data-remove-index]');
  if (remove) { state.teams.own.splice(Number(remove.dataset.removeIndex), 1); if (state.selectedStart >= state.teams.own.length) state.selectedStart = Math.max(0, state.teams.own.length - 1); saveSession(); renderSetup(); return; }
  const select = event.target.closest('[data-select-index]');
  if (select && select.dataset.selectIndex !== '') { state.selectedStart = Number(select.dataset.selectIndex); saveSession(); renderSetup(); return; }
  const action = event.target.closest('[data-battle-action]');
  if (action) { submitAction(action.dataset.battleAction); return; }
  const drawerSwitch = event.target.closest('[data-drawer-switch]');
  if (drawerSwitch) { submitAction(`switch:index=${drawerSwitch.dataset.drawerSwitch}`); return; }
  const menu = event.target.closest('[data-action]');
  if (menu?.dataset.action === 'creature') renderSpiritDrawer();
  else if (menu?.dataset.action === 'bag') renderBagDrawer();
});

$('#start').addEventListener('click', startBattle);
$('#join').addEventListener('click', () => joinBattle().catch((error) => toast(error.message)));
$('#copy-id').addEventListener('click', async () => { if (state.battle?.battle_id) { await navigator.clipboard?.writeText(state.battle.battle_id); toast('对战 ID 已复制'); } });
$('#reset').addEventListener('click', reset);
$('#drawer-close').addEventListener('click', closeDrawer);
$('#charge').addEventListener('click', () => submitAction('charge'));

(async () => {
  try {
    state.catalog = await api('/api/catalog/index');
    $('#catalog-status').textContent = `${state.catalog.pokemon.length} 精灵 · ${state.catalog.skills.length} 技能`;
    renderSetup();
    await restoreSession();
  } catch (error) {
    $('#catalog-status').textContent = 'INDEX ERROR';
    toast(error.message);
  }
})();
