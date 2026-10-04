const UNKNOWN = () => ({known:false, exists:true, value:null, reason:'not_observed'});
const MAYBE = value => ({known:true, exists:true, value});
const state = {battleId:null, round:1, phase:'setup', skipOpponent:false, teams:{own:makeTeam(), opponent:makeTeam()}, actions:{own:{kind:'pass'}, opponent:{kind:'pass'}}, mp:{own:4, opponent:4}, weather:'', weatherTurns:0, seed:1};
let lastEnter = 0;

function makeSkill() { return {name:'', id:'', element:'', icon:'', cost:0, baseCost:0, power:0, effectOverride:null}; }
function makeCreature() { return {name:'', baseName:'', id:'', element:'', icon:'', maxHp:'', hp:'', energy:10, buffs:{}, debuffs:{}, statuses:{}, marks:{}, forms:[], formIndex:0, skills:Array.from({length:4}, makeSkill)}; }
function makeTeam() { return {creatures:Array.from({length:6}, makeCreature), active:0}; }
function el(selector) { return document.querySelector(selector); }
function esc(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }
function setPrompt(text, kind='') { el('#prompt').textContent = text; el('#prompt').dataset.kind = kind; }
function activeCreature(side) { return state.teams[side].creatures[state.teams[side].active]; }
async function fetchCatalog(kind, query) {
  const response = await fetch('/api/catalog?kind=' + kind + '&q=' + encodeURIComponent(query));
  const data = await response.json(); if (!response.ok) throw new Error(data.error || '目录数据不可用');
  return data;
}

function numInput(value, onChange, placeholder='') {
  const input = document.createElement('input');
  input.type = 'number'; input.value = value ?? ''; input.placeholder = placeholder;
  input.oninput = () => onChange(input.value);
  return input;
}
function typeKey(value) {
  const text = String(value || '');
  const aliases = {normal:['普通'], fire:['火'], water:['水'], grass:['草'], ice:['冰'], fighting:['格斗','武'], poison:['毒'], ground:['地面','地'], flying:['飞行','飞','翼'], psychic:['超能','超','幻'], bug:['虫'], ghost:['幽灵','幽'], dragon:['龙'], dark:['恶'], steel:['钢','机械','机'], fairy:['妖精','妖','萌'], light:['光'], electric:['电']};
  for (const [key, values] of Object.entries(aliases)) if (values.some(alias => text.includes(alias))) return key;
  return '';
}

const chart = {normal:{ground:.5,ghost:.5,steel:.5},grass:{fire:.5,water:2,light:2,ground:2,dragon:.5,poison:.5,bug:.5,flying:.5,steel:.5},fire:{grass:2,water:.5,ground:.5,ice:2,dragon:.5,bug:2,steel:2},water:{grass:.5,fire:2,ground:2,ice:.5,dragon:.5,steel:2},light:{grass:.5,ice:.5,ghost:2,dark:2},ground:{grass:.5,fire:2,ice:2,electric:2,poison:2,fighting:.5},ice:{grass:2,fire:.5,ground:2,ice:.5,dragon:2,flying:2,steel:.5},dragon:{dragon:2,steel:.5},electric:{grass:.5,water:2,ground:0,dragon:.5,electric:.5,flying:2},poison:{grass:2,ground:.5,poison:.5,ghost:.5,steel:.5},bug:{grass:2,fire:.5,poison:.5,fighting:.5,flying:.5,ghost:.5,dark:2,steel:.5,psychic:2},fighting:{normal:2,ground:2,ice:2,poison:.5,bug:.5,flying:.5,fairy:2,ghost:0,dark:2,steel:2,psychic:.5},flying:{grass:2,ground:0,dragon:.5,electric:.5,bug:2,fighting:2,steel:.5},fairy:{fire:.5,dragon:2,poison:.5,fighting:2,dark:2,steel:.5},ghost:{normal:0,light:2,ghost:2,dark:.5,psychic:2},dark:{light:.5,poison:2,fighting:.5,fairy:2,ghost:2,dark:.5},steel:{fire:.5,water:.5,ground:2,ice:2,electric:.5,fairy:2,steel:.5},psychic:{light:.5,poison:2,fighting:2,steel:.5,psychic:.5}};
function effectiveness(skill, defender) { const attack=typeKey(skill.element), defense=typeKey(defender.element); if (!attack || !defense) return 1; return chart[attack]?.[defense] ?? 1; }
function effectData(value) {
  if (value >= 2) return {className:'weak', level:2, label:'双上'};
  if (value > 1) return {className:'weak', level:1, label:'单上'};
  if (value <= .5) return {className:'resist', level:-2, label:'双下'};
  if (value < 1) return {className:'resist', level:-1, label:'单下'};
  return {className:'neutral', level:0, label:'中性'};
}
function effectShape(value) {
  const data = effectData(value);
  const shape = data.level === 0 ? '<circle cx="12" cy="12" r="7"></circle>'
    : '<polygon points="12,2 3.339746,17 20.660254,17"></polygon>' + (Math.abs(data.level) === 2 ? '<polygon points="12,6.5 7.23686,14.75 16.76314,14.75"></polygon>' : '');
  return '<svg viewBox="0 0 24 24" aria-label="' + data.label + '" class="effect-shape' + (data.level < 0 ? ' down' : '') + '">' + shape + '</svg>';
}
function maybeText(value) { return value ? MAYBE(value) : UNKNOWN(); }
function maybeNumber(value) { return value !== '' && value !== null && value !== undefined ? MAYBE(Number(value)) : UNKNOWN(); }
function skillJson(skill) { if (!skill.name) return {skill_id:UNKNOWN(),name:UNKNOWN(),current_energy_cost:UNKNOWN(),current_power:UNKNOWN(),use_count:UNKNOWN(),known_to_observer:false,source:'manual_browser'}; return {skill_id:maybeText(skill.id || skill.name),name:maybeText(skill.name),current_energy_cost:maybeNumber(skill.cost),current_power:maybeNumber(skill.power),use_count:UNKNOWN(),known_to_observer:true,source:'manual_browser'}; }
function creatureJson(side, creature) { const unknown=side==='opponent' && state.skipOpponent && !creature.name; return {creature_id:unknown?UNKNOWN():maybeText(creature.id || creature.name),name:unknown?UNKNOWN():maybeText(creature.name),display_name:unknown?UNKNOWN():maybeText(creature.name),base:{color:UNKNOWN(),height:UNKNOWN(),gender:UNKNOWN(),attributes:unknown?UNKNOWN():MAYBE([creature.element]),bloodline_attributes:UNKNOWN(),shiny:UNKNOWN(),speed_range:UNKNOWN(),nature:UNKNOWN(),nature_modifiers:UNKNOWN(),stats:UNKNOWN()},ability:{name:UNKNOWN(),descriptions:[],possible_names:[]},abilities:[],skill_pool:UNKNOWN(),skills:creature.skills.map(skillJson),state:{hp:unknown?UNKNOWN():maybeNumber(creature.hp),max_hp:unknown?UNKNOWN():maybeNumber(creature.maxHp),energy:unknown?UNKNOWN():maybeNumber(creature.energy),buffs:MAYBE(creature.buffs || {}),debuffs:MAYBE(creature.debuffs || {}),marks:MAYBE(creature.marks || {}),status:UNKNOWN(),fatigue_turns:MAYBE(0)},evolution_stage:UNKNOWN(),bossified:UNKNOWN(),entry_count:MAYBE(0),metadata:{source:'manual_browser',unknown,status_stacks:structuredClone(creature.statuses || {})}}; }
function actionJson(side) { const action=state.actions[side]; if(action.kind==='skill'){const skill=activeCreature(side).skills[Number(action.slot)||0]; return {kind:'skill',skill_id:skill.id||skill.name||null,skill_name:skill.name||null,skill_slot:Number(action.slot)||0,source:'manual_browser'};} if(action.kind==='switch')return {kind:'switch',switch_index:Number(action.index)||0,source:'manual_browser'}; return {kind:action.kind,source:'manual_browser'}; }
function buildRequest() {
  const team = side => ({
    team_name:side, active_index:MAYBE(state.teams[side].active),
    devotion:{specified_counts:MAYBE({}), random_draws:MAYBE(0), random_counts:side === 'own' ? MAYBE({}) : UNKNOWN(), visible_to_observer:side === 'own'},
    creatures:state.teams[side].creatures.map(creature => creatureJson(side, creature)),
  });
  return {
    own_team:team('own'), opponent_team:team('opponent'),
    shared:{turn:MAYBE(state.round), weather:MAYBE(state.weather || null), weather_turns:MAYBE(Number(state.weatherTurns)),
      mp:{own:MAYBE(Number(state.mp.own)), opponent:MAYBE(Number(state.mp.opponent))},
      metadata:{source:'manual_browser', skip_opponent_lineup:state.skipOpponent, first_side:state.firstSide,
        ui_state:{teams:structuredClone(state.teams), actions:structuredClone(state.actions), seed:state.seed}}},
    own_turn:{primary:actionJson('own'), items:[]}, opponent_turn:{primary:actionJson('opponent'), items:[]},
    seed:Number(state.seed), battle_id:state.battleId || '', source:'manual_browser',
  };
}
async function nextRound() {
  if (state.saving || state.phase !== 'battle') return;
  if (comparison.pending || !comparison.result) { setPrompt('请先完成当前输入的核心计算，再提交对比。', 'error'); return; }
  const issue = observedIssue(); if (issue) { setPrompt(issue, 'error'); return; }
  const request = buildRequest(); const observed = comparisonObserved();
  state.saving = true;
  try {
    const response = await fetch('/api/save-round', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({battle_id:state.battleId, request, observed_after:observed, note:''})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '保存失败');
    applyObservedState(observed.actual); resetComparison();
    state.round = data.rounds.length + 1;
    state.actions = {own:{kind:'pass'}, opponent:{kind:'pass'}};
    clearCurrentFocus();
    el('#roundLabel').textContent = '第 ' + state.round + ' 回合';
    renderBoard();
    await refreshTree();
    setPrompt('第 ' + (state.round - 1) + ' 回合对比已提交，仅实测值带入下一回合；请确认起始状态。', 'ok');
  } catch (error) { setPrompt(error.message, 'error'); }
  finally { state.saving = false; }
}
function readMaybe(field, fallback='') { return field?.known && field.exists ? field.value : fallback; }

async function loadBattle(id, initialOnly=false) {
  const response = await fetch('/api/battle?id=' + encodeURIComponent(id));
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '读取战斗失败');
  const item = !initialOnly && data.rounds.length ? data.rounds[data.rounds.length - 1] : data.initial_state;
  if (!item) return;
  state.battleId = id;
  loadRoundData(item, item !== data.initial_state);
  rememberBattle(id);
}
async function loadRound(id, round) {
  const response = await fetch('/api/battle?id=' + encodeURIComponent(id));
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '读取回合失败');
  const item = data.rounds.find(entry => entry.round === round);
  if (!item) return;
  state.battleId = id; loadRoundData(item); rememberBattle(id);
}


Object.assign(state, {firstSide:'own', focus:null, formHover:null, actionMode:null, actionBuffer:''});

const DEFAULT_SETUP_PROMPT='准备开始。Tab 下一个；Shift+Tab 上一个；Space 确认。按 / 打开命令弹窗。';
const DEFAULT_BATTLE_PROMPT='实时对比：k 编辑技能，o 编辑阵容，n 我方行动，w 天气；Space/Shift+Space 下一/上一形态。';
let commandSelection=0; let unknownContinuation=null;
function restoreDefaultPrompt(){setPrompt(state.phase==='battle'?DEFAULT_BATTLE_PROMPT:DEFAULT_SETUP_PROMPT);}
function visibleFocusables(){return [...document.querySelectorAll('input:not([disabled]),select:not([disabled]),button:not([disabled]),[role="button"][tabindex]')].filter(node=>node.offsetParent!==null);}
function focusRelative(current,direction){const items=visibleFocusables();const index=items.indexOf(current);const next=items[index+direction];if(!next)return;next.focus();if(typeof next.select==='function')next.select();}
function closeSuggestions(){document.querySelectorAll('.choices').forEach(node=>{node.hidden=true;});}
function commandOptions(query=''){const all=state.phase==='setup'?[{command:'/start 1',description:'我方先手并开始战斗'},{command:'/start 2',description:'对手先手并开始战斗'},{command:'/nc',description:'跳过对手阵容，记录为未知'}]:[{command:'/nc',description:'将未记录的对手阵容标记为未知'}];const normalized=query.trim().toLowerCase();return normalized&&normalized!=='/'?all.filter(item=>item.command.includes(normalized)):all;}
function drawCommandChoices(){const host=el('#commandChoices');const options=commandOptions(el('#commandInput').value);if(!options.length){host.innerHTML='<div class="choice no-results">没有匹配的命令</div>';return;}commandSelection=Math.min(commandSelection,options.length-1);host.innerHTML=options.map((item,index)=>'<button type="button" class="command-option '+(index===commandSelection?'active':'')+'" data-command="'+esc(item.command)+'"><span>'+esc(item.command)+'</span><small>'+esc(item.description)+'</small></button>').join('');host.querySelectorAll('[data-command]').forEach(button=>button.onclick=()=>executeCommand(button.dataset.command));}
function openCommandModal(seed='/'){const input=el('#commandInput');el('#commandModal').classList.remove('hidden');input.value=seed;commandSelection=0;drawCommandChoices();setPrompt('命令弹窗：↑↓ 选择，Enter 或 Space 确认，Esc 关闭。','ok');requestAnimationFrame(()=>{input.focus();input.setSelectionRange(input.value.length,input.value.length);});}
function closeCommandModal(){el('#commandModal').classList.add('hidden');closeSuggestions();restoreDefaultPrompt();}
function executeCommand(command){const value=String(command||'').trim().toLowerCase();if(value==='/nc'){closeCommandModal();skipOpponentSetup();return;}const match=value.match(/^\/start\s+([12])$/);if(match){startBattle(match[1]==='1'?'own':'opponent');return;}setPrompt('无法识别该命令，请选择 /start 1、/start 2 或 /nc。','error');}
function suggestInput(kind, value, onPick, options={}) {
  const wrap = document.createElement('div'); wrap.className = 'suggest';
  const input = document.createElement('input'); input.value = value || ''; input.placeholder = options.placeholder || '首字母 / 拼音'; wrap.appendChild(input);
  const choices = document.createElement('div'); choices.className = 'choices'; choices.hidden = true; wrap.appendChild(choices);
  let items = [], selected = 0, timer = null, requestId = 0;
  function draw() {
    choices.innerHTML = items.map((item, index) => item.noResults
      ? '<div class="choice no-results"><span>没有搜索结果</span><small>可以继续手动输入</small></div>'
      : '<div class="choice ' + (index === selected ? 'active' : '') + '" data-index="' + index + '"><span>' + (index + 1) + '. ' + esc(item.name) + '</span><small>' + esc(item.element || '') + '</small></div>').join('');
    choices.hidden = !items.length;
    choices.querySelectorAll('.choice:not(.no-results)').forEach(node => node.onclick = () => pick(Number(node.dataset.index), false, 1));
  }
  function pick(index, fromTab, direction) {
    const item = items[index];
    if (!item || item.noResults) { if (fromTab) options.onTab?.(input, direction); return; }
    clearTimeout(timer); requestId++;
    input.value = item.name; items = []; choices.hidden = true;
    onPick(item, {fromTab, direction});
    if (fromTab) options.onTab?.(input, direction);
  }
  async function search() {
    const query = input.value.trim(); const id = ++requestId;
    if (!query) { items = []; draw(); return; }
    try {
      const result = await fetchCatalog(kind, query);
      if (id !== requestId || document.activeElement !== input) return;
      items = options.transformItems ? options.transformItems(result) : result;
      if (!items.length) items = [{noResults:true}];
      selected = 0; draw();
    } catch (error) { if (id === requestId) setPrompt('搜索失败：' + error.message, 'error'); }
  }
  input.addEventListener('input', () => {
    clearTimeout(timer); requestId++; items = []; choices.hidden = true;
    timer = setTimeout(search, 60); options.onInput?.(input.value);
  });
  input.addEventListener('focus', () => { if (options.hint) setPrompt(options.hint); });
  input.addEventListener('blur', () => setTimeout(() => { choices.hidden = true; }, 160));
  input.addEventListener('keydown', event => {
    if (event.isComposing) return;
    if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && !choices.hidden && items.length) {
      event.preventDefault(); event.stopPropagation();
      selected = (selected + (event.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length;
      draw(); return;
    }
    if (event.code === 'Space' && !choices.hidden && items.length) { event.preventDefault(); pick(selected, false, 1); return; }
    if (event.key === 'Tab') {
      event.preventDefault(); event.stopPropagation();
      const direction = event.shiftKey ? -1 : 1;
      if (!event.shiftKey && !choices.hidden && items.length) pick(selected, true, direction);
      else options.onTab?.(input, direction);
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      if (!choices.hidden && items.length) pick(selected, false, 1);
      else options.onEnter?.(input);
    }
  });
  return {wrap, input};
}
function applyCreatureChoice(creature, choice) {
  Object.assign(creature, {name:choice.name, baseName:choice.base_name || choice.name, id:choice.id,
    element:choice.element || '', icon:choice.icon_url || '', forms:choice.forms || [], formIndex:0});
}
function renderSetupTeam(side) {
  const host = el('#' + side + 'Setup'); host.innerHTML = '';
  if (side === 'opponent' && state.skipOpponent) { host.innerHTML = '<div class="setup-note">对手阵容暂未观察，按未知记录。</div>'; return; }
  state.teams[side].creatures.forEach((creature, index) => {
    const row = document.createElement('div'); row.className = 'setup-row';
    row.appendChild(createAvatar(side, index, creature, true));
    const number = document.createElement('span'); number.className = 'num'; number.textContent = index + 1; row.appendChild(number);
    const editor = suggestInput('pokemon', creature.baseName || creature.name, choice => {
      applyCreatureChoice(creature, choice); editor.input.value = creature.baseName;
      row.querySelector('.avatar-wrap').replaceWith(createAvatar(side, index, creature, true)); renderSetupStatus();
    }, {placeholder:'输入基本型名称', hint:'输入基本型；悬浮头像后按 Space 切换形态。',
      onInput:value => {
        Object.assign(creature, {name:value, baseName:value, id:'', forms:[], formIndex:0, icon:'', element:''});
        state.formHover = null; row.querySelector('.avatar-wrap').replaceWith(createAvatar(side, index, creature, true)); renderSetupStatus();
      }, onTab:(input, direction) => focusRelative(input, direction)});
    row.appendChild(editor.wrap);
    const hp = numInput(creature.maxHp, value => { creature.maxHp = value; creature.hp = value; renderSetupStatus(); }, '最大 HP');
    hp.min = '1'; row.appendChild(hp); host.appendChild(row);
  });
}
function renderSetupStatus() {
  const count = side => state.teams[side].creatures.filter(creature => creature.name.trim() && Number(creature.maxHp) > 0).length;
  el('#setupStatus').textContent = '我方 ' + count('own') + '/6；' + (state.skipOpponent ? '对手未知' : '对手 ' + count('opponent') + '/6');
}
function renderSetup() { renderSetupTeam('own'); renderSetupTeam('opponent'); renderSetupStatus(); }
function skipOpponentSetup() {
  state.skipOpponent = true; state.teams.opponent = makeTeam();
  if (state.phase === 'setup') renderSetup(); else renderBoard();
  clearCurrentFocus(); setPrompt('对手阵容已标记为未知。', 'ok');
}
function closeUnknown() { el('#unknownModal').classList.add('hidden'); unknownContinuation = null; }
async function startBattle(firstSide='own', allowUnknown=false) {
  if (state.phase !== 'setup' || state.starting) return;
  const sides = state.skipOpponent ? ['own'] : ['own', 'opponent'];
  if (sides.some(side => state.teams[side].creatures.some(creature => !creature.name.trim() || !(Number(creature.maxHp) > 0)))) {
    setPrompt('请先录入完整阵容和有效的最大 HP；对手未知时可使用 /nc。', 'error'); return;
  }
  state.starting = true;
  try {
    if (!allowUnknown) {
      for (const side of sides) for (const creature of state.teams[side].creatures) {
        if (creature.id) continue;
        const choices = await fetchCatalog('pokemon', creature.name.trim());
        const exact = choices.find(choice => choice.name === creature.name.trim());
        if (exact) applyCreatureChoice(creature, exact);
      }
      const unknown = sides.flatMap(side => state.teams[side].creatures.filter(creature => !creature.id).map(creature => creature.name));
      if (unknown.length) {
        closeCommandModal(); unknownContinuation = () => startBattle(firstSide, true);
        el('#unknownText').textContent = '未找到：' + [...new Set(unknown)].join('、') + '。是否按手动名称继续？';
        el('#unknownModal').classList.remove('hidden'); el('#unknownContinue').focus(); return;
      }
    }
    if (!state.battleId) {
      const response = await fetch('/api/new-battle', {method:'POST'}); const data = await response.json();
      if (!response.ok) throw new Error(data.error || '创建战斗失败'); state.battleId = data.battle_id;
    }
    state.firstSide = firstSide; state.round = 1;
    sides.forEach(side => state.teams[side].creatures.forEach(creature => { creature.hp = creature.maxHp; creature.energy = 10; }));
    const response = await fetch('/api/save-initial', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({battle_id:state.battleId, request:buildRequest()})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || '开场保存失败');
    rememberBattle(state.battleId); state.phase = 'battle'; closeCommandModal();
    el('#setup').classList.add('hidden'); el('#board').classList.remove('hidden'); el('#roundLabel').textContent = '第 1 回合'; resetComparison();
    clearCurrentFocus(); renderBoard(); await refreshTree(); setPrompt('开场信息已保存。修改起始状态与行动后自动预测，在下方录入实测结果进行对比。', 'ok');
  } catch (error) { setPrompt(error.message, 'error'); }
  finally { state.starting = false; }
}
function createAvatar(side, index, creature, setup=false) {
  const wrap = document.createElement('div'); wrap.className = 'avatar-wrap' + (setup ? ' setup-avatar-wrap' : '');
  const avatar = document.createElement('div'); avatar.className = 'avatar'; avatar.title = creature.name || '未知精灵';
  avatar.innerHTML = creature.icon ? '<img src="' + esc(creature.icon) + '" alt="' + esc(creature.name) + '">' : esc(creature.name ? creature.name.slice(0, 1) : '?');
  wrap.appendChild(avatar);
  if (!setup) avatar.onclick = () => { state.teams[side].active = index; clearCurrentFocus(); renderBoard(); };
  if (creature.forms.length) {
    const form = creature.forms[creature.formIndex];
    const tooltip = document.createElement('div'); tooltip.className = 'avatar-form-tooltip';
    const portrait = form?.portrait_url || creature.icon;
    tooltip.innerHTML = (portrait ? '<img src="' + esc(portrait) + '" alt="立绘">' : '') + '<strong>' + esc(creature.name) + '</strong><span>Space 下一形态<br>Shift+Space 上一形态</span>';
    wrap.appendChild(tooltip);
  }
  wrap.onmouseenter = () => { state.formHover = {side, index}; };
  wrap.onmouseleave = () => { if (state.formHover?.side === side && state.formHover?.index === index) state.formHover = null; };
  return wrap;
}
function switchCreatureForm(side, index, direction=1) {
  const creature = state.teams[side].creatures[index]; if (creature.forms.length < 2) return;
  creature.formIndex = (creature.formIndex + direction + creature.forms.length) % creature.forms.length;
  const form = creature.forms[creature.formIndex];
  Object.assign(creature, {name:form.name, id:form.id, element:form.element || '', icon:form.icon_url || ''});
  if (state.phase === 'battle') renderBoard();
  else el('#' + side + 'Setup').children[index].querySelector('.avatar-wrap').replaceWith(createAvatar(side, index, creature, true));
  state.formHover = {side, index}; setPrompt('已切换为 ' + creature.name + '，Space 下一形态，Esc 取消聚焦。', 'ok');
}

function refreshFocusHighlight() {
  document.querySelectorAll('.skill-card').forEach(card => {
    const selected = state.focus?.side === card.dataset.side && state.focus?.index === Number(card.dataset.skill)
      && Number(card.dataset.fighter) === state.teams[card.dataset.side].active;
    const action = state.actions[card.dataset.side];
    card.classList.toggle('selected', selected || (action.kind === 'skill' && Number(action.slot) === Number(card.dataset.skill)
      && Number(card.dataset.fighter) === state.teams[card.dataset.side].active));
  });
}
function clearCurrentFocus() {
  state.focus = null; state.formHover = null; state.actionMode = null; state.actionBuffer = ''; lastEnter = 0;
  closeSuggestions(); el('#buffer').classList.add('hidden'); document.activeElement?.blur(); refreshFocusHighlight(); restoreDefaultPrompt();
}
function setSkillFocus(side, index) {
  if (side !== 'own') return;
  state.focus = {side, index}; refreshFocusHighlight(); setPrompt('技能 ' + (index + 1) + '：Tab 下一个，Shift+Tab 上一个；↑↓ 调整效果提示，Esc 结束编辑。');
}
function focusSkill(side, index) {
  if (side !== 'own') return;
  const row = el('[data-side="own"][data-fighter="' + state.teams.own.active + '"]');
  const input = row?.querySelector('[data-skill="' + index + '"] .skill-name-input');
  if (input) { setSkillFocus(side, index); input.focus(); input.select(); }
}
function cycleEffectHint(side, index, direction) {
  const skill = activeCreature(side).skills[index]; const levels = [.5, .75, 1, 1.5, 2];
  const current = skill.effectOverride ?? effectiveness(skill, activeCreature(side === 'own' ? 'opponent' : 'own'));
  const normalized = effectData(current).level;
  const position = normalized + 2;
  skill.effectOverride = levels[Math.max(0, Math.min(levels.length - 1, position + direction))];
  const row = el('[data-side="' + side + '"][data-fighter="' + state.teams[side].active + '"]');
  const effect = row?.querySelector('[data-skill="' + index + '"] .effect');
  const data = effectData(skill.effectOverride);
  if (effect) { effect.className = 'effect ' + data.className; effect.innerHTML = effectShape(skill.effectOverride); effect.title = '效果倍率 ' + skill.effectOverride; }
}
function skillCard(side, fighterIndex, index, skill) {
  const disabled = side === 'opponent' || fighterIndex !== state.teams[side].active;
  const card = document.createElement('div'); card.className = 'skill-card' + (!skill.name ? ' unknown' : '') + (disabled ? ' disabled' : '');
  Object.assign(card.dataset, {side, fighter:fighterIndex, skill:index});
  const visual = document.createElement('div'); visual.className = 'skill-visual';
  const icon = document.createElement('div'); icon.className = 'skill-icon';
  icon.innerHTML = skill.icon ? '<img src="' + esc(skill.icon) + '" alt="">' : esc(skill.name ? skill.name.slice(0, 1) : '?'); visual.appendChild(icon);
  const cost = numInput(skill.name ? skill.cost : '', value => { skill.cost = value; }, '−');
  cost.className = 'badge badge-input cost-input'; cost.disabled = disabled; cost.title = '能耗'; cost.min = '0';
  cost.onfocus = () => setSkillFocus(side, index); visual.appendChild(cost);
  const effect = document.createElement('span'); const hint = effectData(skill.effectOverride ?? effectiveness(skill, activeCreature(side === 'own' ? 'opponent' : 'own')));
  effect.className = 'effect ' + hint.className; effect.innerHTML = effectShape(skill.effectOverride ?? effectiveness(skill, activeCreature(side === 'own' ? 'opponent' : 'own'))); effect.title = '效果提示（↑↓ 调整）'; visual.appendChild(effect);
  const power = document.createElement('input'); power.type = 'text'; power.inputMode = 'numeric'; power.value = skill.name ? skill.power : '';
  power.placeholder = '−'; power.className = 'badge badge-input power-input'; power.disabled = disabled; power.title = '威力';
  power.oninput = () => { skill.power = power.value; }; power.onfocus = () => setSkillFocus(side, index); visual.appendChild(power);
  const type = document.createElement('span'); type.className = 'skill-type'; type.title = skill.element || '系别未知';
  type.innerHTML = skill.element ? '<img src="/assets/dept_icons/' + skill.element + '.png" alt="' + esc(skill.element) + '">' : '?';
  visual.appendChild(type); card.appendChild(visual);
  if (disabled) {
    const name = document.createElement('input'); name.className = 'skill-name-input'; name.value = skill.name; name.placeholder = '未知技能'; name.disabled = true; card.appendChild(name);
  } else {
    const editor = suggestInput('skill', skill.name, (choice, selection) => {
      Object.assign(skill, {name:choice.name, id:choice.id, element:choice.element || '', icon:choice.icon_url || '', cost:choice.energy_cost ?? 0, baseCost:choice.energy_cost ?? 0, power:choice.power ?? 0, effectOverride:null});
      renderBoard(); if (!selection.fromTab) focusSkill('own', index);
    }, {placeholder:'未知技能',
      onInput:value => { skill.name = value; skill.id = ''; skill.element = ''; skill.icon = ''; },
      onTab:(input, direction) => { const next = index + direction; if (next > 3) clearCurrentFocus(); else focusSkill('own', Math.max(0, next)); }});
    editor.input.className = 'skill-name-input'; editor.input.onfocus = () => setSkillFocus(side, index); card.appendChild(editor.wrap);
  }
  return card;
}
function fighterCell(side, index) {
  const creature = state.teams[side].creatures[index];
  const row = document.createElement('div'); row.className = 'fighter ' + side + (index === state.teams[side].active ? ' active' : '') + (creature.hp !== '' && Number(creature.hp) <= 0 ? ' fainted' : '');
  Object.assign(row.dataset, {side, fighter:index}); row.appendChild(createAvatar(side, index, creature));
  const info = document.createElement('div'); info.className = 'fighter-info';
  const name = document.createElement('div'); name.className = 'fighter-name'; name.textContent = (index + 1) + '. ' + (creature.name || '未知精灵');
  name.title = '点击录入或更换精灵';
  const editor = suggestInput('pokemon', creature.baseName || creature.name, (choice, selection) => {
    applyCreatureChoice(creature, choice); renderBoard();
    if (!selection.fromTab) clearCurrentFocus();
  }, {placeholder:'输入基本型名称', onInput:value => {
    Object.assign(creature, {name:value, baseName:value, id:'', element:'', icon:'', forms:[], formIndex:0});
    name.textContent = (index + 1) + '. ' + (value || '未知精灵');
  }, onTab:(input, direction) => {
    const current = input.isConnected ? input : el('[data-side="' + side + '"][data-fighter="' + index + '"] .fighter-name');
    focusRelative(current, direction);
  }});
  editor.input.className = 'fighter-name-input'; editor.wrap.classList.add('hidden');
  name.tabIndex = 0; name.setAttribute('role', 'button');
  name.onclick = () => { name.classList.add('hidden'); editor.wrap.classList.remove('hidden'); editor.input.focus(); editor.input.select(); };
  editor.input.addEventListener('blur', () => setTimeout(() => { editor.wrap.classList.add('hidden'); name.classList.remove('hidden'); }, 160));
  info.append(name, editor.wrap);
  const hpLine = document.createElement('div'); hpLine.className = 'hp-line';
  const meter = document.createElement('div'); meter.className = 'hp-meter';
  const fill = document.createElement('div'); fill.className = 'hp-fill';
  const ratio = Number(creature.maxHp) > 0 ? Math.max(0, Math.min(100, Number(creature.hp) / Number(creature.maxHp) * 100)) : 0;
  fill.style.width = ratio + '%'; meter.appendChild(fill); hpLine.appendChild(meter);
  const hpText = document.createElement('span'); hpText.className = 'hp-text'; hpText.textContent = (creature.hp === '' ? '?' : creature.hp) + '/' + (creature.maxHp || '?'); hpLine.appendChild(hpText); info.appendChild(hpLine);
  const meta = document.createElement('div'); meta.className = 'fighter-meta';
  const hp = numInput(creature.hp, value => { creature.hp = value; hpText.textContent = (value || '?') + '/' + (creature.maxHp || '?'); fill.style.width = (Number(creature.maxHp) > 0 ? Math.max(0, Math.min(100, Number(value) / Number(creature.maxHp) * 100)) : 0) + '%'; row.classList.toggle('fainted', value !== '' && Number(value) <= 0); }, 'HP');
  hp.min = '0'; hp.title = '当前 HP';
  const energy = numInput(creature.energy, value => { creature.energy = value; }, '能量'); energy.min = '0'; energy.title = '能量';
  const energyLine = document.createElement('div'); energyLine.className = 'energy-line'; energyLine.innerHTML = '<span>能量</span>'; energyLine.appendChild(energy);
  const hpEditor = document.createElement('div'); hpEditor.className = 'energy-line'; hpEditor.innerHTML = '<span>HP</span>'; hpEditor.appendChild(hp);
  const separator = document.createElement('span'); separator.textContent = '/';
  const maxHp = numInput(creature.maxHp, value => { creature.maxHp = value; hpText.textContent = (creature.hp === '' ? '?' : creature.hp) + '/' + (value || '?'); fill.style.width = (Number(value) > 0 ? Math.max(0, Math.min(100, Number(creature.hp) / Number(value) * 100)) : 0) + '%'; }, '上限'); maxHp.title = '最大 HP'; maxHp.min = '1';
  hpEditor.append(separator, maxHp); hpEditor.classList.add('hp-editor');
  meta.append(hpEditor, energyLine); info.appendChild(meta); row.appendChild(info);
  const skills = document.createElement('div'); skills.className = 'skills'; creature.skills.forEach((skill, skillIndex) => skills.appendChild(skillCard(side, index, skillIndex, skill))); row.appendChild(skills);
  return row;
}
function renderBoard() {
  const board = el('#board'); board.innerHTML = '';
  for (let index = 0; index < 6; index++) { board.appendChild(fighterCell('own', index)); board.appendChild(fighterCell('opponent', index)); }
  renderStateRow(board);
  const footer = document.createElement('div'); footer.className = 'footer-cell';
  const status = document.createElement('span'); status.id = 'simulationStatus'; status.textContent = '准备计算'; footer.appendChild(status);
  const calculate = document.createElement('button'); calculate.textContent = '重新计算'; calculate.onclick = () => scheduleSimulation(0); footer.appendChild(calculate);
  const next = document.createElement('button'); next.className = 'secondary'; next.id = 'submitComparison'; next.textContent = '提交对比并下一回合'; next.onclick = nextRound; footer.appendChild(next); board.appendChild(footer);
  refreshFocusHighlight(); scheduleSimulation();
}

function toggleMenu() {
  const active = !el('.sidebar').classList.contains('active');
  el('.sidebar').classList.toggle('active', active);
  el('.sidebar-overlay').classList.toggle('active', active);
}

function bindEvents() {
  el('#commandInput').addEventListener('input', () => { commandSelection = 0; drawCommandChoices(); });
  el('#commandModal').addEventListener('click', event => { if (event.target.id === 'commandModal') closeCommandModal(); });
  el('#unknownContinue').onclick = continueUnknownStart;
  el('#startBattle').onclick = () => openCommandModal('/start ');
  el('#newBattle').onclick = () => { rememberBattle(null); location.reload(); };
  el('.menu-toggle').onclick = toggleMenu;
  el('.sidebar-overlay').onclick = toggleMenu;
  for (const eventName of ['input', 'change']) el('#board').addEventListener(eventName, () => scheduleSimulation());
}
function continueUnknownStart(){const next=unknownContinuation;closeUnknown();next?.();}
document.addEventListener('keydown', event => {
  if (event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
  const target = event.target;
  const typing = ['INPUT', 'SELECT', 'TEXTAREA'].includes(target?.tagName);
  if (!el('#unknownModal').classList.contains('hidden')) {
    if (event.key === 'Escape' || event.key === 'Enter' || event.code === 'Space') {
      event.preventDefault(); event.stopImmediatePropagation();
      if (event.key === 'Escape') { closeUnknown(); clearCurrentFocus(); }
      else continueUnknownStart();
    }
    return;
  }
  if (!el('#commandModal').classList.contains('hidden')) {
    if (event.key === 'Escape') { event.preventDefault(); closeCommandModal(); clearCurrentFocus(); return; }
    const options = commandOptions(el('#commandInput').value);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      commandSelection = event.key === 'ArrowDown' ? Math.min(options.length - 1, commandSelection + 1) : Math.max(0, commandSelection - 1);
      drawCommandChoices(); return;
    }
    const value = el('#commandInput').value.trim();
    if (options[commandSelection] && (event.key === 'Enter' || (event.code === 'Space' && /^(\/start\s+[12]|\/nc|\/)$/.test(value)))) {
      event.preventDefault(); executeCommand(options[commandSelection].command);
    }
    return;
  }
  if (event.key === '/') { event.preventDefault(); openCommandModal('/'); return; }
  if (event.key === 'Escape') {
    event.preventDefault();
    el('.sidebar').classList.remove('active'); el('.sidebar-overlay').classList.remove('active');
    clearCurrentFocus(); return;
  }
  if (target?.classList.contains('fighter-name') && (event.key === 'Enter' || event.code === 'Space')) {
    event.preventDefault(); target.click(); return;
  }
  if (state.formHover && event.code === 'Space') {
    event.preventDefault(); event.stopImmediatePropagation();
switchCreatureForm(state.formHover.side, state.formHover.index, event.shiftKey ? -1 : 1); return;
  }
  if (event.key === 'Tab' && !target?.closest('.suggest')) {
    event.preventDefault();
    if (state.phase === 'battle' && target?.closest('.skill-card') && state.focus) {
      const next = state.focus.index + (event.shiftKey ? -1 : 1);
      if (next > 3) clearCurrentFocus(); else focusSkill('own', Math.max(0, next));
    } else focusRelative(target, event.shiftKey ? -1 : 1);
    return;
  }
  if (state.actionMode && !typing && event.key.length === 1) {
    event.preventDefault();
    state.actionBuffer += event.key;
    el('#buffer').textContent = state.actionBuffer;
    const text = state.actionBuffer.toLowerCase();
    const match = text.match(/^[mn]([ks])([1-6])$/);
    if (/^[mn]e$/.test(text)) { state.actions[state.actionMode] = {kind:'charge', label:'聚能'}; state.actionMode = null; }
    else if (/^[mn]p$/.test(text)) { state.actions[state.actionMode] = {kind:'pass', label:'道具'}; state.actionMode = null; }
    else if (match && (match[1] === 's' || Number(match[2]) <= 4)) {
      const value = Number(match[2]) - 1;
      state.actions[state.actionMode] = match[1] === 'k' ? {kind:'skill', slot:value, label:'技能 ' + (value + 1)} : {kind:'switch', index:value, label:'切换 ' + (value + 1)};
      state.actionMode = null;
    }
    if (!state.actionMode) { state.actionBuffer = ''; el('#buffer').classList.add('hidden'); renderBoard(); }
    return;
  }
  if (state.phase !== 'battle') return;
  if (event.key === 'o' && !typing) { event.preventDefault(); el('.fighter.own.active .fighter-name')?.click(); return; }
  if (event.key === 'w' && !typing) { event.preventDefault(); const input = el('#weatherInput'); input?.focus(); input?.select(); return; }
  const skillTarget = target?.closest('.skill-card');
  const suggestionsOpen = target?.closest('.suggest')?.querySelector('.choices')?.hidden === false;
  if ((event.key === 'ArrowUp' || event.key === 'ArrowDown') && state.focus && skillTarget && !suggestionsOpen) {
    event.preventDefault(); cycleEffectHint('own', state.focus.index, event.key === 'ArrowUp' ? 1 : -1); return;
  }
  if (event.key === 'k' && !typing) {
    event.preventDefault(); event.stopPropagation();
    focusSkill('own', ((state.focus?.index ?? -1) + 1) % 4); return;
  }
  if ((event.key === 'e' || event.key === 'p') && state.focus && !typing) {
    event.preventDefault();
    const row = el('[data-side="own"][data-fighter="' + state.teams.own.active + '"]');
    const input = row?.querySelector('.skill-card:nth-child(' + (state.focus.index + 1) + ') ' + (event.key === 'e' ? '.cost-input' : '.power-input'));
    input?.focus(); input?.select(); return;
  }
  if ((event.key === 'm' || event.key === 'n') && !typing) {
    event.preventDefault();
    state.actionMode = event.key === 'm' ? 'opponent' : 'own'; state.actionBuffer = event.key;
    el('#buffer').textContent = event.key; el('#buffer').classList.remove('hidden');
    setPrompt((state.actionMode === 'own' ? '我方' : '对手') + '行动：' + event.key + 'k+数字、' + event.key + 's+数字、' + event.key + 'e 或 ' + event.key + 'p。', 'ok'); return;
  }
  if (event.key === 'Enter' && !typing) {
    const now = Date.now();
    if (now - lastEnter < 1000) { event.preventDefault(); lastEnter = 0; nextRound(); }
    else { lastEnter = now; }
  }
}, true);
function loadRoundData(item, review=true) {
  const request = item.request;
  if (!request) return;
  state.round = item.round;
  state.teams = {own:makeTeam(), opponent:makeTeam()};
  const ui = request.shared?.metadata?.ui_state;
  for (const side of ['own', 'opponent']) {
    const team = request[side + '_team'];
    if (!team) continue;
    state.teams[side].active = Number(readMaybe(team.active_index, 0));
    (team.creatures || []).slice(0, 6).forEach((raw, index) => {
      const creature = state.teams[side].creatures[index];
      creature.name = readMaybe(raw.name, ''); creature.id = readMaybe(raw.creature_id, '');
      const attributes = readMaybe(raw.base?.attributes, []);
      creature.element = Array.isArray(attributes) ? attributes[0] || '' : attributes;
      creature.maxHp = readMaybe(raw.state?.max_hp, ''); creature.hp = readMaybe(raw.state?.hp, '');
      creature.energy = readMaybe(raw.state?.energy, 10);
      creature.buffs = readMaybe(raw.state?.buffs, {}); creature.debuffs = readMaybe(raw.state?.debuffs, {}); creature.marks = readMaybe(raw.state?.marks, {});
      creature.statuses = raw.metadata?.status_stacks || {};
      (raw.skills || []).slice(0, 4).forEach((slot, skillIndex) => {
        const skill = creature.skills[skillIndex];
        skill.name = readMaybe(slot.name, ''); skill.id = readMaybe(slot.skill_id, '');
        skill.cost = Number(readMaybe(slot.current_energy_cost, 0)); skill.baseCost = skill.cost;
        skill.power = Number(readMaybe(slot.current_power, 0));
      });
      const saved = ui?.teams?.[side]?.creatures?.[index];
      if (saved) {
        Object.assign(creature, structuredClone(saved));
        creature.skills = Array.from({length:4}, (_, skillIndex) => ({...makeSkill(), ...saved.skills?.[skillIndex]}));
      }
    });
    state.mp[side] = Number(readMaybe(request.shared?.mp?.[side], 4));
    state.actions[side] = ui?.actions?.[side] || {kind:'pass'};
  }
  state.weather = readMaybe(request.shared?.weather, '') || '';
  state.weatherTurns = Number(readMaybe(request.shared?.weather_turns, 0));
  state.seed = request.seed ?? ui?.seed ?? 1;
  state.firstSide = request.shared?.metadata?.first_side || 'own';
  state.skipOpponent = Boolean(request.shared?.metadata?.skip_opponent_lineup);
  state.phase = 'battle'; state.focus = null; state.formHover = null; resetComparison();
  if (item.observed_after?.actual) comparison.observed = structuredClone(item.observed_after.actual);
  el('#setup').classList.add('hidden'); el('#board').classList.remove('hidden');
  el('#roundLabel').textContent = '第 ' + state.round + ' 回合' + (review ? '（回顾）' : '');
  renderBoard();
  setPrompt(review ? '当前显示已保存输入状态；下一回合会继续追加，不会覆盖历史。' : '开场保存点已恢复，可继续第 1 回合。', 'ok');
}
async function refreshTree() {
  const response = await fetch('/api/battles');
  const battles = await response.json();
  if (!response.ok) throw new Error(battles.error || '读取战斗列表失败');
  const tree = el('#tree'); tree.innerHTML = '';
  battles.forEach(battle => {
    const group = document.createElement('div'); group.className = 'tree-battle';
    const title = document.createElement('button');
    title.innerHTML = '<span>' + esc(battle.label || '战斗') + '</span><span>' + battle.rounds.length + ' 回合</span>';
    title.onclick = () => loadBattle(battle.battle_id).catch(error => setPrompt(error.message, 'error'));
    group.appendChild(title);
    if (battle.has_initial_state) {
      const initial = document.createElement('button'); initial.className = 'tree-round';
      initial.textContent = '开场保存点';
      initial.onclick = () => loadBattle(battle.battle_id, true).catch(error => setPrompt(error.message, 'error'));
      group.appendChild(initial);
    }
    battle.rounds.forEach(item => {
      const round = document.createElement('button'); round.className = 'tree-round';
      round.textContent = '第 ' + item.round + ' 回合';
      round.onclick = () => loadRound(battle.battle_id, item.round).catch(error => setPrompt(error.message, 'error'));
      group.appendChild(round);
    });
    tree.appendChild(group);
  });
}
function rememberBattle(id) {
  try {
    if (id) localStorage.setItem('nrc_manual_battle', id);
    else localStorage.removeItem('nrc_manual_battle');
  } catch {}
}

async function restoreSavedBattle() {
  try {
    const id = localStorage.getItem('nrc_manual_battle');
    if (id) await loadBattle(id);
  } catch (error) { setPrompt('无法自动恢复，请从侧栏选择保存点：' + error.message, 'error'); }
}

bindEvents();
renderSetup();
restoreDefaultPrompt();
refreshTree().catch(error => setPrompt(error.message, 'error'));
restoreSavedBattle();
