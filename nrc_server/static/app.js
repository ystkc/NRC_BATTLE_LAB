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
  eventCursor: null,
  pending: false,
  opponentPending: false,
  resolving: false,
  resolutionToken: 0,
  pollTimer: null,
  pollInFlight: false,
  previewAnchor: null,
  previewRequest: 0,
  previewFormIndex: 0,
};

const SESSION_KEY = 'nrc-battle-session';

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
  if (!response.ok) {
    const error = new Error(data.message || data.error || '请求失败');
    error.status = response.status;
    throw error;
  }
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
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({ battleId: state.battle.battle_id, playerToken: state.playerToken, side: state.side, selectedStart: state.selectedStart, teams: state.teams.own }));
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(SESSION_KEY);
  state.battle = null;
  state.playerToken = '';
  state.side = '';
  state.teams = { own: [], opponent: [] };
  state.selectedStart = 0;
  state.events = [];
  state.eventCursor = null;
  state.resolutionToken += 1;
  state.pending = false;
  state.opponentPending = false;
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
const TYPE_NAMES = { normal: '普通', fire: '火', water: '水', electric: '电', grass: '草', ice: '冰', fighting: '武', poison: '毒', ground: '地', flying: '翼', psychic: '幻', bug: '虫', ghost: '幽', dragon: '龙', dark: '恶', steel: '机械', fairy: '萌', light: '光' };
const BUFF_ICONS = { atk_up: '物攻.png', def_up: '物防.png', spatk_up: '魔攻.png', spdef_up: '魔防.png', speed_up: '速度.png', atk_down: '物攻.png', def_down: '物防.png', spatk_down: '魔攻.png', spdef_down: '魔防.png', speed_down: '速度.png', poison: '中毒.png', burn: '灼烧.png', freeze: '冻结.png', leech: '寄生.png', electric: '引电.png', meteor: '星陨印记.png', cute: '萌化.png' };
function typeKey(value) { const text = String(value || '').toLowerCase(); return TYPE_NAMES[text] || text.replace('系', '') || '普通'; }
function typeIcon(value) { return `/assets/dept_icons/${encodeURIComponent(typeKey(value))}.png`; }
function buffIcon(name) { const filename = BUFF_ICONS[name]; return filename ? `/assets/icon_buff/${encodeURIComponent(filename)}` : ''; }

function hydrateTeamItem(item, previous = {}) {
  const name = item?.name || previous.name || '';
  const form = formFor(name) || previous.form || item?.form || null;
  return { ...previous, ...item, name, base_name: item?.base_name || previous.base_name || form?.base_name || baseName(name), form };
}

function hydrateOwnRoster(roster) {
  const old = state.teams.own || [];
  state.teams.own = (roster || []).map((item, index) => hydrateTeamItem(item, old[index]));
  if (!state.teams.own.length) state.selectedStart = 0;
  else if (state.selectedStart >= state.teams.own.length) state.selectedStart = state.teams.own.length - 1;
}

function searchRows(value, category = 'pokemon') {
  const query = String(value || '').trim().toLowerCase();
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
  if (!row || state.teams.own.length >= 6 || state.teams.own.some((item) => item.base_name === row.name)) return false;
  const form = row.forms[0];
  state.teams.own.push({ name: form.name, base_name: row.name, form, skills: (form.default_skills || form.skills || []).slice(0, 4).map((skill) => ({ name: typeof skill === 'string' ? skill : skill.name })) });
  saveSession();
  renderSetup();
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
    if (error.status === 404) {
      clearSession();
      renderSetup();
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
      const operation = await api(`/api/battles/${state.battle.battle_id}/operation?since=${state.battle.decision_index ?? -1}`);
      const pendingChanged = state.pending !== Boolean(operation.own_pending)
        || state.opponentPending !== Boolean(operation.opponent_pending);
      state.pending = Boolean(operation.own_pending);
      state.opponentPending = Boolean(operation.opponent_pending);
      if (pendingChanged) updateBattleLock();
      if (operation.resolved || operation.terminal) await refreshBattle({ refreshDisplay: true });
    } catch (error) {
      if (error.status !== 404) toast(error.message);
    } finally {
      state.pollInFlight = false;
      startBattlePolling();
    }
  }, 1200);
}

function mergeObservation(data) {
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

function renderSide(side) {
  const enemy = side === 'opponent';
  const team = state.teams[side] || [];
  const activeIndex = team.activeIndex || 0;
  const activeItem = team[activeIndex] || {};
  const item = enemy && activeItem.fainted ? (team.find((candidate) => !candidate.fainted) || activeItem) : activeItem;
  const prefix = enemy ? 'enemy' : 'own';
  const percent = item.max_hp ? Math.max(0, Math.round(item.hp / item.max_hp * 100)) : item.hp_percent ?? 0;
  $(`#${prefix}-active-name`).textContent = item.name || '-';
  $(`#${prefix}-hp-text`).textContent = item.hp == null ? `${percent ?? '?'}%` : `${item.hp} / ${item.max_hp}`;
  $(`#${prefix}-hp-bar`).style.width = `${percent || 0}%`;
  $(`#${prefix}-energy`).textContent = `能量 ${item.energy == null ? '?' : item.energy}`;
  $(`#${prefix}-active-art`).src = item.portrait || asset(item.name, 'portrait') || asset(item.name, 'art');
  $(`#${prefix}-active-types`).innerHTML = (item.types || []).map((type) => `<img class="field-type" src="${esc(typeIcon(type))}" alt="${esc(typeKey(type))}" title="${esc(typeKey(type))}">`).join('');
  const effects = [];
  const conditions = item.conditions || {
    poison: item.poison_stacks,
    burn: item.burn_stacks,
    freeze: item.freeze_stacks,
    electric: item.electric_stacks,
    cute: item.cute_stacks,
  };
  Object.entries(conditions).forEach(([name, value]) => { if (Number(value) > 0) effects.push({ name, value }); });
  const boosts = item.boosts || {};
  Object.entries(boosts).forEach(([name, value]) => {
    const iconName = name.includes('攻击') ? (name.includes('魔') ? 'spatk_up' : 'atk_up') : name.includes('物防') ? 'def_up' : name.includes('魔防') ? 'spdef_up' : 'speed_up';
    effects.push({ name, value, icon: buffIcon(iconName) });
  });
  if (item.status && item.status !== 'normal' && item.status !== '正常') effects.push({ name: item.status, value: 1 });
  $(`#${prefix}-effects`).innerHTML = effects.map(({ name, value, icon }) => `<span class="field-effect"><img src="${esc(icon || buffIcon(name))}" alt="${esc(name)}" title="${esc(name)}"><small>${esc(value)}</small></span>`).join('');
  const box = $(`#${prefix}-pips`);
  box.innerHTML = Array.from({ length: 6 }, (_, index) => `<i class="pip ${team[index] ? 'owned' : ''} ${team[index]?.fainted ? 'fainted' : ''} ${index === (team.activeIndex || 0) ? 'active-pip' : ''}></i>`).join('');
}

function renderSkills() {
  $('#skills').innerHTML = (state.display.skills || []).map((skill, index) => {
    const meta = skillMeta(skill.name);
    const type = skill.element || meta.element || meta.element_key || 'normal';
    return `<button class="skill-card" data-skill-name="${esc(skill.name)}" data-battle-action="skill:slot=${skill.skill_slot ?? index}" ${state.pending || state.resolving ? 'disabled' : ''}><span class="skill-icon-wrap"><img class="skill-icon" src="${esc(skill.icon || meta.icon || '')}" alt=""><span class="skill-cost-badge">${esc(skill.display_energy_cost ?? meta.energy_cost)}</span><span class="skill-power-badge">${skill.display_power > 0 ? skill.display_power : '-'}</span><img class="skill-type-badge" src="${esc(skill.type_icon || typeIcon(type))}" alt="${esc(typeKey(type))}">${skill.effect_icon ? `<img class="skill-relation-badge" src="${esc(skill.effect_icon)}" alt="效果">` : ''}</span><span class="skill-copy"><b class="skill-name">${esc(skill.name)}</b><small class="skill-kind">${esc(meta.category || '技能')}</small></span></button>`;
  }).join('');
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
  $('.battle-main')?.classList.toggle('resolving', value);
  renderSkills();
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
  setResolving(false);
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
  const lock = $('#lock-state');
  if (lock) lock.textContent = state.pending ? '已锁定，等待对手' : state.opponentPending ? '对手已锁定，等待我方' : '选择操作';
}

async function syncEvents({ animate = false, data = null } = {}) {
  const since = state.eventCursor ?? 0;
  const payload = await api(`/api/battles/${state.battle.battle_id}/events?since=${since}`);
  const incoming = payload.events || [];
  state.eventCursor = payload.cursor ?? since + incoming.length;
  if (!incoming.length) return false;
  if (animate) {
    setResolving(true);
    const token = ++state.resolutionToken;
    return playResolution(incoming, data, token);
  }
  state.events.push(...incoming);
  renderEvents();
  return false;
}

async function refreshBattle({ refreshDisplay = false, animateEvents = false } = {}) {
  if (!state.battle) return;
  try {
    const id = state.battle.battle_id;
    const previous = state.battle;
    const previousPending = state.pending;
    const summary = await api(`/api/battles/${id}`);
    const statusChanged = summary.turn !== previous.turn
      || summary.phase !== previous.phase
      || summary.decision_index !== previous.decision_index
      || Boolean(summary.pending) !== Boolean(previousPending);
    state.battle = { ...state.battle, ...summary };
    if (!summary.initialized) return renderSetup();
    const firstLoad = state.eventCursor === null;
    const nextData = (await api(`/api/battles/${id}/state?side=own`)).data;
    const displayChanged = refreshDisplay || statusChanged || !state.display.skills?.length;
    if (displayChanged) {
      state.display = await api(`/api/battles/${id}/display?side=own`);
      state.actions = (await api(`/api/battles/${id}/actions?side=own`)).actions || [];
    }
    state.pending = Boolean(summary.pending);
    updateBattleMeta();
    const animated = await syncEvents({ animate: animateEvents && !firstLoad && statusChanged, data: nextData });
    if (!animated) {
      mergeObservation(nextData);
      renderSide('own');
      renderSide('opponent');
      if (displayChanged) renderSkills();
    }
  } catch (error) {
    if (error.status === 404) {
      clearSession();
      closeDrawer();
      $('#battle').classList.add('hidden');
      $('#setup').classList.remove('hidden');
      renderSetup();
      toast('对局已失效，请重新创建或加入');
    } else toast(error.message);
  }
}

async function submitAction(key) {
  if (!key || state.pending || !state.battle) return;
  try {
    const result = await api(`/api/battles/${state.battle.battle_id}/selection`, { method: 'POST', body: JSON.stringify({ action_key: key }) });
    state.pending = !result.resolved;
    state.opponentPending = false;
    updateBattleLock();
    if (!result.resolved) {
      setResolving(true);
      document.querySelectorAll('#skills .skill-card').forEach((card) => card.classList.add('skill-picked'));
    }
    if (result.resolved) await refreshBattle({ refreshDisplay: true, animateEvents: true });
    closeDrawer();
    if (result.terminated) toast(result.winner === 0 ? '我方获胜' : result.winner === 1 ? '敌方获胜' : '对局结束');
  } catch (error) { toast(error.message); }
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

function reset() {
  clearSession();
  closeDrawer();
  $('#battle').classList.add('hidden');
  $('#setup').classList.remove('hidden');
  renderSetup();
}

async function restoreSession() {
  localStorage.removeItem(SESSION_KEY);
  const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
  if (!saved?.battleId || !saved?.playerToken) return;
  state.playerToken = saved.playerToken;
  state.side = saved.side || '';
  state.battle = { battle_id: saved.battleId };
  hydrateOwnRoster(saved.teams || []);
  state.selectedStart = saved.selectedStart ?? 0;
  renderSetup();
  await refreshLobby();
}

const aptitudeFieldDict = {'生命': 'hp', '物攻': 'atk', '魔攻': 'spatk', '物防': 'def', '魔防': 'spdef', '速度': 'speed'}
const aptitudeNamesDict = {'hp': '生命', 'atk': '物攻', 'spatk': '魔攻', 'def': '物防', 'spdef': '魔防', 'speed': '速度'}
function aptitudeField(name) {
  return aptitudeFieldDict[name] || 'unknown';
}

function aptitudeName(field) {
  return aptitudeNamesDict[field] || '未知';
}

function editorFieldMarkup(field, value, choices) {
  const options = choices.map((choice) => `<button type="button" data-editor-option="${esc(choice.name)}" data-editor-option-field="${field}">${esc(choice.name)}${choice.percentage ? ` <small>(${choice.percentage}%)</small>` : ''}</button>`).join('');
  return `<div class="editor-autocomplete"><input type="text" autocomplete="off" data-editor-autocomplete data-editor-field="${field}" value="${esc(value)}"><div class="editor-suggest hidden" data-editor-suggest="${field}">${options}</div></div>`;
}

function choiceMatches(choices, query) {
  const text = String(query || '').trim().toLowerCase();
  if (!text) return choices;
  let result = choices.filter((choice) => [choice.name, choice.initials].some((value) => value.includes(text)));
  if (result.length < 5) {
    result = [...result, ...choices.filter((choice) => choice.pinyin.includes(text))];
  }
  return result.sort((a, b) => a.name.length - b.name.length).slice(0, 5);
}

function editorChoices(index, field) {
  const item = state.teams.own[index];
  const form = item ? formFor(item.name) || item.form || {} : {};
  const customization = form.customization || {};
  if (field === 'nature') return customization.natures || [];
  if (field === 'bloodline') return customization.bloodlines || [];
  if (field === 'aptitude')
  {
      const aptitudes = customization.aptitudes || [];
      const values = selectedAptitudes(item, customization).map((aptitude) => aptitude.name);
      return aptitudes.filter((aptitude) => !values.includes(aptitude.name));
  }
  if (field === 'skill') {
    const skills = state.catalog.skills || [];
    const values = selectedSkills(item);
    return skills.filter((skill) => !values.includes(skill.name) || skill.name === '借用');
  }
  return [];
}

function renderEditorSuggestions(input) {
  const box = input?.parentElement?.querySelector('[data-editor-suggest]');
  if (!input || !box) return;
  const query = String(input.value || '').trim().toLowerCase();
  const index = Number($('#hover-card')?.dataset.floatingEditIndex);
  const choices = editorChoices(index, input.dataset.editorField);
  const rows = choiceMatches(choices, query);
  box.innerHTML = rows.map((choice) => `<button type="button" data-editor-option="${esc(choice.name)}" data-editor-option-field="${esc(input.dataset.editorField)}">${esc(choice.name)}${choice.percentage ? ` <small>(${choice.percentage}%)</small>` : ''}</button>`).join('');
  box.classList.toggle('hidden', !rows.length);
}

function applyEditorOption(button) {
  const field = button.dataset.editorOptionField;
  const value = button.dataset.editorOption;
  const index = Number($('#hover-card')?.dataset.floatingEditIndex);
  if (!field || !Number.isInteger(index) || index < 0) return false;
  if (field === 'aptitude') return addAptitude(index, value);
  if (field === 'skill') return addSkill(index, value);
  updateCreatureBase(index, field, value);
  const anchor = document.querySelector(`#own-team [data-edit-index="${index}"]`);
  renderCreatureEditor(index, anchor);
  return true;
}

function editorPosition(anchor) {
  const card = $('#hover-card');
  if (!card || !anchor) return;
  const rect = anchor.getBoundingClientRect();
  const gap = 10;
  const left = Math.min(window.innerWidth - card.offsetWidth - 12, Math.max(12, rect.right + gap));
  const top = Math.min(window.innerHeight - card.offsetHeight - 12, Math.max(12, rect.top));
  card.style.left = `${left}px`;
  card.style.top = `${top}px`;
}

function renderCreatureEditor(index, anchor=null) {
  if (!anchor) anchor = document.querySelector(`#own-team [data-edit-index="${index}"]`);
  const item = state.teams.own[index];
  if (!item) return;
  const form = formFor(item.name) || item.form || {};
  console.log(item.name, item.form, formFor(item.name));
  const customization = form.customization || {};
  const base = item.base || {};
  const nature = base.nature || customization.natures?.[0]?.name || '';
  const bloodline = Array.isArray(base.bloodline_attributes) ? base.bloodline_attributes[0] || '' : base.bloodline_attributes || '';
  const natureBonus = customization.nature_bonus?.[nature] || {};
  const bonusText = Object.entries(natureBonus).map(([key, value]) => `${key} ${Number(value) > 0 ? '+' : ''}${value}`).join(' / ');
  const forms = (pokemonRow(item.name)?.forms || []).map((choice) => `<button type="button" class="form-choice ${choice.name === item.name ? 'active' : ''}" data-editor-form="${esc(choice.name)}">${esc(choice.name)}</button>`).join('');
  const natures = editorFieldMarkup('nature', nature, customization.natures || []);
  const bloodlines = editorFieldMarkup('bloodline', bloodline, customization.bloodlines || []);
  const aptitudes = aptitudeEditorMarkup(item, customization);
  const skills = skillEditorMarkup(item);
  const card = $('#hover-card');
  card.innerHTML = `<div class="hover-title"><b>${esc(item.name)}</b><button type="button" data-editor-close>×</button></div><img class="art" src="${esc(form.portrait || form.art || '')}" alt=""><label class="editor-label">Form</label><div class="form-list">${forms}</div><label class="editor-label">Nature</label><div class="editor-field">${natures}<span class="nature-bonus">${esc(bonusText)}</span></div><label class="editor-label">Bloodline</label><div class="editor-field">${bloodlines}</div><label class="editor-label">Aptitudes</label><div class="editor-field">${aptitudes}</div><label class="editor-label">Skills</label><div class="editor-field">${skills}</div><small class="hover-help">Changes are saved to this roster.</small>`;
  card.dataset.floatingEditIndex = String(index);
  card.classList.remove('hidden');
  editorPosition(anchor);
}

function closeCreatureEditor() {
  const card = $('#hover-card');
  card.classList.add('hidden');
  card.removeAttribute('data-floating-edit-index');
}

function updateCreatureBase(index, field, value) {
  const item = state.teams.own[index];
  if (!item) return;
  item.base = { ...(item.base || {}) };
  if (field === 'bloodline') item.base.bloodline_attributes = value ? [value] : [];
  else item.base[field] = value;
  saveSession();
}

function setForm(index, formName) {
  const item = state.teams.own[index];
  if (!item) return;
  item.name = formName;
  item.base_name = baseName(item.name);
  item.form = formFor(item.name) || item.form;
  saveSession();
  renderTeamCard('own', index, item);
}

function selectedAptitudes(item, customization) {
  const values = item.base?.individual_values || {};
  const result = Object.entries(values).map(([field, value]) => {
    return { field, name: aptitudeName(field) || field, value: Math.min(10, Math.max(1, Number(value) || 8)) };
  }).slice(0, 3);
  return result;
}

function aptitudeEditorMarkup(item, customization) {
  const selected = selectedAptitudes(item, customization);
  const rows = selected.map((entry) => `<div class="editor-entry aptitude-entry"><span>${esc(entry.name)}</span><input type="number" min="1" max="10" step="1" value="${entry.value}" data-aptitude-value="${esc(entry.field)}"><button type="button" data-remove-aptitude="${esc(entry.field)}">×</button></div>`).join('');
  const input = `<div class="editor-autocomplete"><input type="text" autocomplete="off" placeholder="输入资质名称 / 拼音 / 首字母" data-editor-autocomplete data-editor-field="aptitude"><div class="editor-suggest hidden" data-editor-suggest="aptitude"></div></div>`;
  return `${rows}${input}<small class="hover-help">最多选择 3 项，新增资质默认 8</small>`;
}

function selectedSkills(item) {
  return (item.skills || []).map((skill) => skill.name);
}

function normalizedBase(item) {
  const base = { ...(item.base || {}) };
  const values = Object.entries(base.individual_values || {})
    .filter(([, value]) => Number(value) > 0)
    .slice(0, 3)
    .reduce((result, [field, value]) => {
      result[field] = Math.min(10, Math.max(1, Number(value) || 8));
      return result;
    }, {});
  base.individual_values = values;
  return base;
}

function skillEditorMarkup(item) {
  const selected = selectedSkills(item);
  const rows = selected.map((name, index) => `<div class="editor-entry skill-entry"><span>${index + 1}. ${esc(name)}</span><button type="button" data-remove-skill="${index}">×</button></div>`).join('');
  const input = `<div class="editor-autocomplete"><input type="text" autocomplete="off" placeholder="输入技能名称 / 拼音 / 首字母" data-editor-autocomplete data-editor-field="skill"><div class="editor-suggest hidden" data-editor-suggest="skill"></div></div>`;
  return `${rows}${input}<small class="hover-help">最多选择 4 个技能</small>`;
}

function addAptitude(index, name) {
  const item = state.teams.own[index];
  if (!item) return false;
  const field = aptitudeField(name);
  item.base = { ...(item.base || {}), individual_values: { ...(item.base?.individual_values || {}) } };
  const values = item.base.individual_values;
  if (values[field] != null) return false;
  if (Object.keys(values).length >= 3) {
    toast('最多添加 3 项资质');
    renderCreatureEditor(index);
    return false;
  }
  values[field] = 8;
  saveSession();
  renderCreatureEditor(index);
  return true;
}

function removeAptitude(index, field) {
  const item = state.teams.own[index];
  if (!item) return;
  item.base = { ...(item.base || {}), individual_values: { ...(item.base?.individual_values || {}) } };
  delete item.base.individual_values[field];
  saveSession();
  renderCreatureEditor(index);
}

function addSkill(index, name) {
  const item = state.teams.own[index];
  if (!item) return false;
  const skills = selectedSkills(item);
  if (skills.includes(name) && name !== '借用') return false;
  if (skills.length >= 4) {
    toast('最多添加 4 个技能');
    renderCreatureEditor(index);
    return false;
  }
  item.skills = [...skills, name].map((skill) => ({ name: skill }));
  saveSession();
  renderCreatureEditor(index);
  return true;
}

function removeSkill(index, skillIndex) {
  const item = state.teams.own[index];
  if (!item) return;
  item.skills = selectedSkills(item).filter((_, currentIndex) => currentIndex !== Number(skillIndex)).map((name) => ({ name }));
  saveSession();
  renderCreatureEditor(index);
}

function previewPosition(anchor) {
  const card = $('#preview-card');
  if (!card || !anchor) return;
  const rect = anchor.getBoundingClientRect();
  const gap = 10;
  const left = Math.min(window.innerWidth - card.offsetWidth - 12, Math.max(12, rect.right + gap));
  const top = Math.min(window.innerHeight - card.offsetHeight - 12, Math.max(12, rect.top));
  card.style.left = `${left}px`;
  card.style.top = `${top}px`;
}

function previewPayload(item) {
  return {
    name: item.name,
    base: normalizedBase(item),
    skills: selectedSkills(item),
  };
}

function renderCreaturePreview(data) {
  const stats = data.stats || {};
  const stat_icons = data.stat_icons || {};
  const entries = [
    ['hp', 'HP'], ['atk', 'ATK'], ['def', 'DEF'],
    ['spatk', 'M.ATK'], ['spdef', 'M.DEF'], ['speed', 'SPD'],
  ];
  const statHtml = entries.map(([key, label]) => `<div class="preview-stat"><img src="${esc(stat_icons[key] || '')}" alt="${label}"><b>${label}</b><span>${esc(stats[key] ?? '-')}</span></div>`).join('');
  const bloodline = (data.bloodline_attributes || []).join(' / ');
  $('#preview-card').innerHTML = `<img class="preview-art" src="${esc(data.portrait || '')}" alt=""><div class="preview-title"><b>${esc(data.name || '')}</b><span>${esc(data.nature || '')}</span></div><div class="preview-bloodline">${data.bloodline_icon ? `<img src="${esc(data.bloodline_icon)}" alt="">` : ''}<span>${esc(bloodline || '-')}</span></div><div class="preview-stats">${statHtml}</div>`;
}

function previewForms(index) {
  const item = state.teams.own[index];
  return item ? (pokemonRow(item.name)?.forms || []) : [];
}

async function loadCreaturePreview(index, anchor, name) {
  const item = state.teams.own[index];
  const card = $('#preview-card');
  if (!item || !card) return;
  const requestId = ++state.previewRequest;
  state.previewAnchor = anchor;
  card.dataset.previewIndex = String(index);
  card.innerHTML = '<div class="preview-loading">Loading…</div>';
  card.classList.remove('hidden');
  previewPosition(anchor);
  try {
    const data = await api('/api/pokemon/preview', { method: 'POST', body: JSON.stringify({ ...previewPayload(item), name }) });
    if (requestId !== state.previewRequest || state.previewAnchor !== anchor) return;
    renderCreaturePreview(data);
    previewPosition(anchor);
  } catch (error) {
    if (requestId === state.previewRequest) card.innerHTML = `<div class="preview-loading">${esc(error.message)}</div>`;
  }
}

async function showCreaturePreview(index, anchor) {
  const item = state.teams.own[index];
  if (!item) return;
  const forms = previewForms(index);
  state.previewFormIndex = Math.max(0, forms.findIndex((form) => form.name === item.name));
  await loadCreaturePreview(index, anchor, forms[state.previewFormIndex]?.name || item.name);
}

function cyclePreviewForm(delta) {
  const card = $('#preview-card');
  const index = Number(card?.dataset.previewIndex);
  if (!card || card.classList.contains('hidden') || !Number.isInteger(index) || !state.previewAnchor) return;
  const forms = previewForms(index);
  if (forms.length < 2) return;
  state.previewFormIndex = (state.previewFormIndex + delta + forms.length) % forms.length;
  loadCreaturePreview(index, state.previewAnchor, forms[state.previewFormIndex].name);
  setForm(index, forms[state.previewFormIndex].name);
}

function hideCreaturePreview() {
  state.previewRequest += 1;
  state.previewAnchor = null;
  state.previewFormIndex = 0;
  $('#preview-card')?.classList.add('hidden');
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
  if (event.key !== 'Tab') return;
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
  if (!searchInput) return;
  const box = $(searchInput.id === 'own-search' ? '#own-suggest' : '#quick-suggest');
  const first = box?.querySelector('[data-suggest-kind]');
  if (first) {
    event.preventDefault();
    if (first.dataset.suggestKind === 'pokemon') {
      addCreature(first.dataset.suggestName);
      searchInput.value = '';
      renderSuggestions(`#${searchInput.id}`, searchInput.id === 'own-search' ? '#own-suggest' : '#quick-suggest');
    } else {
      searchInput.value = first.dataset.suggestName;
      box.classList.add('hidden');
    }
  }
});

document.addEventListener('click', (event) => {
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
    addCreature(suggestion.dataset.suggestName);
    renderSetup();
    $('#own-search').value = '';
    $('#quick-search').value = '';
    renderSuggestions('#own-search', '#own-suggest');
    renderSuggestions('#quick-search', '#quick-suggest');
    return;
  }
  const remove = event.target.closest('[data-remove-index]');
  if (remove) { state.teams.own.splice(Number(remove.dataset.removeIndex), 1); if (state.selectedStart >= state.teams.own.length) state.selectedStart = Math.max(0, state.teams.own.length - 1); closeCreatureEditor(); saveSession(); renderSetup(); return; }
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
