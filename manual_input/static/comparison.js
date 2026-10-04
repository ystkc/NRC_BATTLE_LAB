const WEATHER_CHOICES = [
  {id:'', name:'无天气'}, {id:'rain', name:'雨天'}, {id:'snow', name:'雪天'},
  {id:'sandstorm', name:'沙暴'}, {id:'sunny', name:'晴天'}, {id:'hail', name:'冰雹'},
];
const STATUS_FIELDS = [
  ...['atk', 'def', 'spatk', 'spdef', 'speed'].flatMap(key => {
    const names = {atk:'物攻', def:'物防', spatk:'魔攻', spdef:'魔防', speed:'速度'};
    const icon = key === 'speed' ? 'shoe-prints' : key.includes('def') ? 'shield-halved' : 'khanda';
    return ['buffs', 'debuffs'].map(group => ({key, group, icon, name:names[key] + (group === 'buffs' ? '增益' : '减益')}));
  }),
  {key:'combo', group:'statuses', icon:'star', name:'连击加成'},
  {key:'poison', group:'statuses', icon:'skull-crossbones', name:'中毒'},
  {key:'burn', group:'statuses', icon:'fire', name:'燃烧'},
  {key:'freeze', group:'statuses', icon:'snowflake', name:'冻结'},
  {key:'leech', group:'statuses', icon:'seedling', name:'寄生'},
  {key:'meteor', group:'statuses', icon:'star', name:'星陨'},
  {key:'cute', group:'statuses', icon:'star', name:'萌化'},
];
const comparison = {revision:0, timer:null, controller:null, result:null, pending:false, observed:null, error:''};
function emptyObserved() {
  return {own:Array.from({length:6}, () => ({hp:'', energy:'', buffs:{}, debuffs:{}, statuses:{}})),
    opponent:Array.from({length:6}, () => ({hp:'', energy:'', buffs:{}, debuffs:{}, statuses:{}})),
    shared:{weather:undefined, weather_turns:'', mp:{own:'', opponent:''}}};
}
function resetComparison() {
  comparison.revision++; clearTimeout(comparison.timer); comparison.controller?.abort();
  comparison.result = null; comparison.pending = false; comparison.error = ''; comparison.observed = emptyObserved();
  el('#comparison')?.classList.remove('hidden'); renderComparison();
}
function weatherName(value) { return WEATHER_CHOICES.find(item => item.id === (value || ''))?.name || String(value); }
function statusIcon(name) {
  const icon = STATUS_ICONS[name] || STATUS_ICONS.star;
  return '<svg viewBox="' + icon.viewBox + '" aria-hidden="true"><path d="' + icon.path + '"></path></svg>';
}
function statusEditor(creature, field, onChange, observed=false) {
  const label = document.createElement('label');
  const value = creature[field.group]?.[field.key] ?? (observed ? '' : 0);
  label.className = 'status-icon ' + field.group + (field.key === 'combo' ? ' combo' : '') + (Number(value) ? ' populated' : '');
  label.title = field.name + '（右下角输入层数）'; label.innerHTML = statusIcon(field.icon);
  const input = numInput(value, value => {
    creature[field.group] ||= {}; creature[field.group][field.key] = value;
    label.classList.toggle('populated', Number(value) > 0); onChange?.();
  }, observed ? '?' : '0');
  input.min = '0'; input.step = '1'; input.setAttribute('aria-label', field.name + (observed ? '实测层数' : '层数'));
  label.appendChild(input); return label;
}
function statusDisplay(snapshot) {
  const container = document.createElement('div'); container.className = 'status-icons predicted-status';
  for (const field of STATUS_FIELDS) {
    const value = field.group === 'statuses' ? snapshot.statuses?.[field.key]
      : snapshot.modifiers?.[field.key + (field.group === 'buffs' ? '_up' : '_down')];
    if (!Number(value)) continue;
    const icon = document.createElement('span'); icon.className = 'status-icon populated ' + field.group + (field.key === 'combo' ? ' combo' : '');
    icon.title = field.name; icon.innerHTML = statusIcon(field.icon) + '<span class="stack-count">' + esc(value) + '</span>'; container.appendChild(icon);
  }
  return container;
}
function actionSelect(side) {
  const select = document.createElement('select'); select.setAttribute('aria-label', side === 'own' ? '我方行动' : '对手行动');
  const choices = [{value:'pass', name:'等待 / 道具'}, {value:'charge', name:'聚能'},
    ...activeCreature(side).skills.map((skill, index) => ({value:'skill:' + index, name:'技能 ' + (index + 1) + ' ' + (skill.name || '未知')})),
    ...state.teams[side].creatures.map((creature, index) => ({value:'switch:' + index, name:'切换 ' + (index + 1) + ' ' + (creature.name || '未知')}))];
  choices.forEach(choice => { const option = document.createElement('option'); option.value = choice.value; option.textContent = choice.name; select.appendChild(option); });
  const current = state.actions[side]; select.value = current.kind + (current.kind === 'skill' ? ':' + current.slot : current.kind === 'switch' ? ':' + current.index : '');
  select.onchange = () => { const [kind, value] = select.value.split(':'); state.actions[side] = kind === 'skill' ? {kind, slot:Number(value)} : kind === 'switch' ? {kind, index:Number(value)} : {kind}; refreshFocusHighlight(); scheduleSimulation(); };
  return select;
}
function renderStateRow(board) {
  const row = document.createElement('section'); row.className = 'battle-status-row';
  for (const side of ['own', 'shared', 'opponent']) {
    const panel = document.createElement('section'); panel.className = 'status-panel ' + side;
    const heading = document.createElement('h3'); heading.textContent = side === 'shared' ? '共享状态' : (side === 'own' ? '我方状态' : '对方状态'); panel.appendChild(heading);
    if (side === 'shared') {
      const weather = suggestInput('weather', weatherName(state.weather), choice => {
        state.weather = choice.id; if (!state.weather) state.weatherTurns = 0;
        weather.input.value = choice.name; scheduleSimulation();
      }, {placeholder:'无天气', hint:'输入天气名称、拼音或首字母，Tab/Space 确认。',
        onInput:value => { const exact = WEATHER_CHOICES.find(choice => choice.name === value.trim() || choice.id === value.trim()); state.weather = exact ? exact.id : value; },
        onTab:(input, direction) => focusRelative(input, direction)});
      weather.input.id = 'weatherInput'; panel.appendChild(weather.wrap);
      const duration = document.createElement('label'); duration.textContent = '剩余回合 '; const turns = numInput(state.weatherTurns, value => { state.weatherTurns = value; }); turns.min = '0'; duration.appendChild(turns); panel.appendChild(duration);
      const seedLabel = document.createElement('label'); seedLabel.textContent = '随机种子 '; const seed = numInput(state.seed, value => { state.seed = value; }); seed.min = '0'; seedLabel.appendChild(seed); panel.appendChild(seedLabel);
    } else {
      const action = document.createElement('div'); action.className = 'status-action'; action.appendChild(actionSelect(side));
      const mp = numInput(state.mp[side], value => { state.mp[side] = value; }); mp.min = '0'; mp.title = 'MP'; action.appendChild(mp); panel.appendChild(action);
      const icons = document.createElement('div'); icons.className = 'status-icons';
      STATUS_FIELDS.forEach(field => icons.appendChild(statusEditor(activeCreature(side), field, () => scheduleSimulation()))); panel.appendChild(icons);
    }
    row.appendChild(panel);
  }
  board.appendChild(row);
}
function simulationIssue() {
  if (!WEATHER_CHOICES.some(choice => choice.id === state.weather)) return '请从候选中确认天气';
  if (![state.weatherTurns, state.seed, state.mp.own, state.mp.opponent].every(value => value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0)) return '共享数值必须为非负数字';
  for (const side of ['own', 'opponent']) {
    for (const creature of state.teams[side].creatures) {
      if (side === 'opponent' && state.skipOpponent && !creature.name) continue;
      if (!creature.name || creature.hp === '' || creature.energy === '' || !(Number(creature.maxHp) > 0) || ![creature.hp, creature.energy].every(value => Number.isFinite(Number(value)) && Number(value) >= 0)) return '请完整录入精灵名称、HP 和能量';
      for (const skill of creature.skills) if (skill.name && ![skill.cost, skill.power].every(value => value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0)) return '技能能耗和威力必须为非负数字';
      for (const group of ['buffs', 'debuffs', 'statuses']) if (Object.values(creature[group] || {}).some(value => value === '' || !Number.isFinite(Number(value)) || Number(value) < 0)) return '状态层数必须为非负数字';
    }
    const action = state.actions[side];
    if (action.kind === 'skill' && !activeCreature(side).skills[action.slot]?.name) return '请先录入所选择的技能';
  }
  return '';
}
function simulationLabel(text, kind='') {
  const label = el('#simulationStatus'); if (label) { label.textContent = text; label.dataset.kind = kind; }
  const submit = el('#submitComparison'); if (submit) submit.disabled = comparison.pending || !comparison.result;
}
function scheduleSimulation(delay=240) {
  if (state.phase !== 'battle') return;
  const revision = ++comparison.revision; clearTimeout(comparison.timer); comparison.controller?.abort();
  comparison.pending = true; comparison.error = ''; simulationLabel('输入已更新，等待计算…');
  el('#comparison')?.classList.remove('hidden'); el('#comparison')?.classList.add('pending');
  comparison.timer = setTimeout(() => runSimulation(revision), delay);
}
async function runSimulation(revision) {
  const issue = simulationIssue();
  if (issue) { if (revision !== comparison.revision) return; comparison.pending = false; comparison.result = null; comparison.error = issue; simulationLabel(issue, 'error'); renderComparison(); return; }
  comparison.controller = new AbortController(); simulationLabel('核心计算中…');
  try {
    const response = await fetch('/api/simulate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildRequest()), signal:comparison.controller.signal});
    const result = await response.json(); if (revision !== comparison.revision) return;
    if (!response.ok) throw new Error(result.error || '核心计算失败');
    if (!result.own?.after?.creatures || !result.opponent?.after?.creatures || !result.shared_after) throw new Error('核心返回结果不完整');
    comparison.result = result; comparison.pending = false;
    simulationLabel((result.warnings?.length || result.input_unknowns?.length) ? '计算完成（含未知/警告）' : '计算完成', 'ok'); renderComparison();
  } catch (error) {
    if (revision !== comparison.revision || error.name === 'AbortError') return;
    comparison.pending = false; comparison.result = null; comparison.error = error.message; simulationLabel('计算失败：' + error.message, 'error'); renderComparison();
  }
}
function snapshotValue(value) { return value == null ? '?' : String(value); }
function compareInput(observed, key, predicted, label) {
  const wrap = document.createElement('label'); wrap.className = 'observed-field'; wrap.textContent = label + ' ';
  const input = numInput(observed[key] ?? '', value => { observed[key] = value; updateDifference(); }, '实测'); input.min = '0';
  input.dataset.compareKey = label;
  const result = document.createElement('span'); result.className = 'difference';
  function updateDifference() {
    const value = observed[key]; const known = value !== '' && value != null && Number.isFinite(Number(value));
    wrap.classList.toggle('matches', known && Number(value) === Number(predicted)); wrap.classList.toggle('differs', known && Number(value) !== Number(predicted));
    result.textContent = !known ? '待录入' : Number(value) === Number(predicted) ? '一致' : '差 ' + (Number(value) - Number(predicted));
  }
  updateDifference(); wrap.append(input, result); return wrap;
}
function predictedCreature(side, snapshot, index) {
  const card = document.createElement('article'); card.className = 'prediction-creature'; card.dataset.index = index;
  const source = state.teams[side].creatures[index];
  const heading = document.createElement('div'); heading.className = 'prediction-name';
  heading.innerHTML = (source?.icon ? '<img src="' + esc(source.icon) + '" alt="">' : '') + '<strong>' + (index + 1) + '. ' + esc(snapshot.name || '未知精灵') + '</strong>';
  card.appendChild(heading);
  const values = document.createElement('div'); values.className = 'predicted-values';
  values.innerHTML = '预测 HP <b>' + esc(snapshotValue(snapshot.hp)) + '</b>/' + esc(snapshotValue(snapshot.max_hp)) + ' · 能量 <b>' + esc(snapshotValue(snapshot.energy)) + '</b>';
  const meter = document.createElement('div'); meter.className = 'hp-meter'; const fill = document.createElement('div'); fill.className = 'hp-fill'; fill.style.width = (snapshot.max_hp > 0 ? Math.max(0, Math.min(100, snapshot.hp / snapshot.max_hp * 100)) : 0) + '%'; meter.appendChild(fill); values.appendChild(meter); card.appendChild(values);
  card.appendChild(statusDisplay(snapshot));
  const actual = comparison.observed[side][index]; const inputs = document.createElement('div'); inputs.className = 'observed-values';
  inputs.append(compareInput(actual, 'hp', snapshot.hp, 'HP'), compareInput(actual, 'energy', snapshot.energy, '能量')); card.appendChild(inputs);
  const details = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = '技能与实测状态'; details.appendChild(summary);
  const skills = document.createElement('div'); skills.className = 'predicted-skills';
  (snapshot.skills || []).filter(skill => !String(skill.name).startsWith('__unknown')).forEach(skill => {
    const item = document.createElement('div'); item.textContent = skill.name + ' · 能耗 ' + snapshotValue(skill.current_energy_cost) + ' · 威力 ' + snapshotValue(skill.current_power); skills.appendChild(item);
  }); details.appendChild(skills);
  const statuses = document.createElement('div'); statuses.className = 'status-icons observed-statuses';
  STATUS_FIELDS.forEach(field => {
    const expected = field.group === 'statuses' ? snapshot.statuses?.[field.key] ?? 0 : snapshot.modifiers?.[field.key + (field.group === 'buffs' ? '_up' : '_down')] ?? 0;
    const icon = statusEditor(actual, field, () => {
      const value = actual[field.group][field.key]; icon.classList.toggle('differs', value !== '' && Number(value) !== Number(expected)); icon.classList.toggle('matches', value !== '' && Number(value) === Number(expected));
    }, true); statuses.appendChild(icon);
  }); details.appendChild(statuses); card.appendChild(details); return card;
}
function renderComparison() {
  const host = el('#comparison'); if (!host) return;
  const focused = document.activeElement; const side = focused?.closest('[data-compare-side]')?.dataset.compareSide; const index = focused?.closest('[data-index]')?.dataset.index; const key = focused?.dataset.compareKey;
  host.innerHTML = ''; host.classList.toggle('pending', comparison.pending);
  const title = document.createElement('h2'); title.textContent = '核心预测 ↔ 实测对比'; host.appendChild(title);
  if (!comparison.result) { const message = document.createElement('p'); message.className = 'muted'; message.textContent = comparison.error || '修改起始状态或行动后自动计算；预测不会覆盖实测输入。'; host.appendChild(message); return; }
  comparison.observed ||= emptyObserved();
  const result = comparison.result; const grid = document.createElement('div'); grid.className = 'comparison-grid';
  for (const side of ['own', 'shared', 'opponent']) {
    const panel = document.createElement('section'); panel.className = 'comparison-panel'; panel.dataset.compareSide = side;
    const heading = document.createElement('h3'); heading.textContent = side === 'shared' ? '共享结果与不确定性' : side === 'own' ? '我方结算结果' : '对方结算结果'; panel.appendChild(heading);
    if (side !== 'shared') result[side].after.creatures.forEach((snapshot, index) => {
      const card = predictedCreature(side, snapshot, index); card.classList.toggle('active', index === result[side].after.active_index); panel.appendChild(card);
    });
    else {
      const weather = document.createElement('p'); weather.className = 'predicted-weather'; weather.innerHTML = statusIcon('cloud') + '预测：' + esc(weatherName(result.shared_after.weather)) + ' · 剩余 ' + esc(result.shared_after.weather_turns ?? 0) + ' 回合'; panel.appendChild(weather);
      const weatherObserved = document.createElement('select'); weatherObserved.setAttribute('aria-label', '实测天气');
      weatherObserved.innerHTML = '<option value="__unknown">实测天气待录入</option>' + WEATHER_CHOICES.map(choice => '<option value="' + choice.id + '">' + choice.name + '</option>').join('');
      weatherObserved.value = comparison.observed.shared.weather ?? '__unknown';
      const weatherDifference = document.createElement('span'); weatherDifference.className = 'weather-difference';
      function updateWeatherDifference() {
        const value = comparison.observed.shared.weather;
        const matches = value !== undefined && value === (result.shared_after.weather || '');
        weatherObserved.classList.toggle('differs', value !== undefined && !matches);
        weatherDifference.textContent = value === undefined ? '待录入' : matches ? '天气一致' : '天气不一致';
        weatherDifference.classList.toggle('matches', matches); weatherDifference.classList.toggle('differs', value !== undefined && !matches);
      }
      weatherObserved.onchange = () => { comparison.observed.shared.weather = weatherObserved.value === '__unknown' ? undefined : weatherObserved.value; updateWeatherDifference(); };
      updateWeatherDifference(); panel.append(weatherObserved, weatherDifference);
      panel.appendChild(compareInput(comparison.observed.shared, 'weather_turns', result.shared_after.weather_turns ?? 0, '天气回合'));
      for (const side of ['own', 'opponent']) panel.appendChild(compareInput(comparison.observed.shared.mp, side, result.shared_after.mp?.[side], side === 'own' ? '我方 MP' : '对方 MP'));
      const warnings = [...(result.warnings || []), ...(result.input_unknowns || []).map(field => '未知输入：' + field)];
      const note = document.createElement('p'); note.className = 'uncertainty-note'; note.textContent = warnings.length ? '以下预测包含占位值或未观测信息，不应视作确定结论。' : '相同输入与种子对应相同计算结果。'; panel.appendChild(note);
      const audit = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = '查看警告 / 分支 / 事件'; audit.appendChild(summary);
      const list = document.createElement('ul'); warnings.forEach(text => { const item = document.createElement('li'); item.textContent = text; list.appendChild(item); });
      (result.possible_branches || []).forEach(branch => { const item = document.createElement('li'); item.textContent = '分支 ' + branch.branch_id + '：' + (branch.note || branch.status || '概率未知'); list.appendChild(item); });
      (result.events || []).forEach(event => { const item = document.createElement('li'); item.textContent = event.message || [event.type, event.id].filter(Boolean).join(' · ') || JSON.stringify(event); list.appendChild(item); });
      (result.latent_uncertainties || []).forEach(uncertainty => { const item = document.createElement('li'); item.textContent = '潜在不确定性：' + JSON.stringify(uncertainty); list.appendChild(item); });
      audit.appendChild(list); panel.appendChild(audit);
    }
    grid.appendChild(panel);
  }
  host.appendChild(grid);
  if (side && index != null && key) {
    const panel = [...host.querySelectorAll('[data-compare-side]')].find(panel => panel.dataset.compareSide === side);
    const card = [...(panel?.querySelectorAll('[data-index]') || [])].find(card => card.dataset.index === index);
    const input = [...(card?.querySelectorAll('[data-compare-key]') || [])].find(input => input.dataset.compareKey === key); input?.focus();
  }
}
function observedIssue() {
  const actual = comparison.observed; if (!actual) return '';
  const values = [actual.shared.weather_turns, ...Object.values(actual.shared.mp)];
  for (const side of ['own', 'opponent']) for (const creature of actual[side]) {
    values.push(creature.hp, creature.energy);
    for (const group of ['buffs', 'debuffs', 'statuses']) values.push(...Object.values(creature[group]));
  }
  return values.some(value => value !== '' && value != null && (!Number.isFinite(Number(value)) || Number(value) < 0)) ? '实测数值必须为非负数字' : '';
}
function comparisonObserved() {
  return {source:'manual_browser', actual:structuredClone(comparison.observed || emptyObserved()),
    prediction:comparison.pending ? null : structuredClone(comparison.result), calculation_error:comparison.error || null, seed:state.seed};
}
function applyObservedState(observed=comparison.observed) {
  if (!observed) return;
  for (const side of ['own', 'opponent']) {
    state.teams[side].creatures.forEach((creature, index) => {
      const actual = observed[side][index]; for (const key of ['hp', 'energy']) if (actual[key] !== '' && Number.isFinite(Number(actual[key]))) creature[key] = Number(actual[key]);
      for (const group of ['buffs', 'debuffs', 'statuses']) for (const [key, value] of Object.entries(actual[group])) if (value !== '' && Number.isFinite(Number(value))) { creature[group] ||= {}; creature[group][key] = Number(value); }
    });
    const mp = observed.shared.mp[side]; if (mp !== '' && Number.isFinite(Number(mp))) state.mp[side] = Number(mp);
  }
  if (observed.shared.weather !== undefined) state.weather = observed.shared.weather;
  if (observed.shared.weather_turns !== '') state.weatherTurns = Number(observed.shared.weather_turns);
}
