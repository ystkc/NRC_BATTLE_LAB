const failures = [];
window.addEventListener('error', event => failures.push(event.message));
const pixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
const testPokemon = {id:1, name:'测试精灵', base_name:'测试精灵', element:'水', icon_url:pixel,
  forms:[{id:1, name:'测试精灵', element:'水', icon_url:pixel, portrait_url:pixel},
    {id:2, name:'测试精灵（战斗型）', element:'火', icon_url:pixel, portrait_url:pixel},
    {id:3, name:'测试精灵（第三型）', element:'草', icon_url:pixel, portrait_url:pixel}]};
const testSkill = {id:100, name:'火球', element:'火', icon_url:pixel, energy_cost:2, power:90};
let savedBattle = {battle_id:'test-battle', rounds:[]};
let checkpointCalls = 0;
let rejectCheckpoint = false;
let simulationCalls = 0;
let simulationError = false;
let holdSimulation = false;
const simulationWaiters = [];
function mockResult(request) {
  const snapshot = (side, after=false) => ({active_index:request[side + '_team'].active_index.value,
    creatures:request[side + '_team'].creatures.map((creature, index) => ({index, name:creature.name.value || '未知精灵',
      hp:(creature.state.hp.value ?? 100) - (after ? 10 : 0), max_hp:creature.state.max_hp.value ?? 100,
      energy:(creature.state.energy.value ?? 10) - (after ? 2 : 0),
      modifiers:Object.fromEntries(['atk', 'def', 'spatk', 'spdef', 'speed'].flatMap(key => [[key + '_up', creature.state.buffs.value[key] || 0], [key + '_down', creature.state.debuffs.value[key] || 0]])),
      statuses:creature.metadata.status_stacks,
      skills:creature.skills.map(skill => ({name:skill.name.value || '__unknown_skill', current_power:skill.current_power.value, current_energy_cost:skill.current_energy_cost.value})),
    }))});
  const shared = {weather:request.shared.weather.value, weather_turns:request.shared.weather_turns.value, mp:{own:request.shared.mp.own.value, opponent:request.shared.mp.opponent.value}};
  return {own:{before:snapshot('own'), after:snapshot('own', true)}, opponent:{before:snapshot('opponent'), after:snapshot('opponent', true)},
    shared_before:shared, shared_after:shared, warnings:['测试警告'], input_unknowns:['opponent.ability'], possible_branches:[], events:[]};
}
window.fetch = async (url, options={}) => {
  const target = new URL(url, 'http://localhost');
  let data; let ok = true;
  if (target.pathname === '/api/catalog') {
    data = target.searchParams.get('kind') === 'weather' ? [{id:'rain', name:'雨天'}] : target.searchParams.get('kind') === 'skill' ? [testSkill] : target.searchParams.get('q').includes('测试') ? [testPokemon] : [];
  } else if (target.pathname === '/api/simulate') {
    simulationCalls++; data = simulationError ? {error:'测试核心失败'} : mockResult(JSON.parse(options.body)); ok = !simulationError;
    if (holdSimulation) await new Promise(resolve => simulationWaiters.push(resolve));
  } else if (target.pathname === '/api/new-battle') data = savedBattle;
  else if (target.pathname === '/api/save-initial') {
    checkpointCalls++;
    if (rejectCheckpoint) { ok = false; data = {error:'测试保存失败'}; }
    else { savedBattle.initial_state = {round:1, request:JSON.parse(options.body).request}; data = savedBattle; }
  } else if (target.pathname === '/api/save-round') {
    savedBattle.rounds.push({round:savedBattle.rounds.length + 1, ...JSON.parse(options.body)}); data = savedBattle;
  } else if (target.pathname === '/api/battle') data = savedBattle;
  else if (target.pathname === '/api/battles') data = savedBattle.initial_state ? [{...savedBattle, label:'测试战斗', has_initial_state:true}] : [];
  else throw new Error('Unexpected request ' + url);
  return {ok, json:async () => structuredClone(data)};
};
void 'BROWSER_CHECKS';
(async () => {
  const completed = [];
  const assert = (condition, label) => { if (!condition) throw new Error(label); completed.push(label); };
  const settle = () => new Promise(resolve => setTimeout(resolve, 120));
  const key = (target, name, extras={}) => {
    const event = new KeyboardEvent('keydown', {key:name, code:name === ' ' ? 'Space' : name, bubbles:true, cancelable:true, ...extras});
    target.dispatchEvent(event); return event;
  };
  const type = (input, value) => { input.focus(); input.value = value; input.dispatchEvent(new Event('input', {bubbles:true})); };
  const report = document.createElement('pre'); report.id = 'test-result'; report.style.display = 'none';
  try {
    await settle();
    assert(document.querySelectorAll('.setup-row').length === 12, 'opening rows render without startup errors');
    const firstInput = el('#ownSetup .suggest input'); firstInput.focus(); key(firstInput, '/'); await settle();
    assert(el('#commandInput').value === '/' && el('#commandInput').selectionStart === 1 && el('#commandInput').selectionEnd === 1, 'slash remains with caret at end');
    type(el('#commandInput'), '/start');
    assert(!key(el('#commandInput'), ' ').defaultPrevented, 'space after start is accepted for command arguments');
    key(el('#commandInput'), 'Escape');
    type(firstInput, '测试'); await settle(); key(firstInput, 'Tab');
    assert(state.teams.own.creatures[0].id === 1 && document.activeElement === el('#ownSetup .setup-row input[type=number]'), 'one Tab accepts basic creature and advances');
    key(document.activeElement, 'Tab', {shiftKey:true}); assert(document.activeElement === firstInput, 'Shift Tab returns to previous input');
    const setupAvatar = el('#ownSetup .avatar-wrap'); setupAvatar.dispatchEvent(new MouseEvent('mouseenter'));
    key(firstInput, ' ');
    assert(state.teams.own.creatures[0].id === 2 && firstInput.value === '测试精灵', 'opening Space switches form without changing basic input');
    assert(el('#ownSetup .avatar-form-tooltip strong').textContent.includes('战斗型'), 'form tooltip updates immediately');
    key(firstInput, ' ', {shiftKey:true}); assert(state.teams.own.creatures[0].id === 1, 'Shift Space returns to previous form');
    key(firstInput, ' '); key(firstInput, ' '); key(firstInput, ' '); assert(state.teams.own.creatures[0].id === 1, 'consecutive Space cycles forms');
    key(firstInput, 'Escape');
    skipOpponentSetup();
    state.teams.own.creatures.forEach((creature, index) => { if (index) creature.name = '未收录' + index; creature.maxHp = 100; creature.hp = 100; });
    renderSetup();
    const unknownInput = el('#ownSetup').children[1].querySelector('.suggest input');
    type(unknownInput, '未收录1'); await settle(); key(unknownInput, 'Tab');
    assert(el('#unknownModal').classList.contains('hidden'), 'unknown input does not open a modal');
    await startBattle('own');
    assert(!el('#unknownModal').classList.contains('hidden') && checkpointCalls === 0, 'only start prompts for unknown creatures');
    key(el('#unknownContinue'), 'Escape');
    assert(state.phase === 'setup' && checkpointCalls === 0 && el('#unknownModal').classList.contains('hidden'), 'Escape cancels unknown start');
    rejectCheckpoint = true; await startBattle('own'); key(el('#unknownContinue'), 'Enter'); await settle();
    assert(state.phase === 'setup' && !savedBattle.initial_state, 'failed checkpoint does not enter battle');
    rejectCheckpoint = false; await startBattle('opponent'); key(el('#unknownContinue'), ' '); await settle();
    assert(state.phase === 'battle' && state.round === 1 && savedBattle.rounds.length === 0, 'Space confirms and saves independent opening checkpoint');
    assert(savedBattle.initial_state.request.shared.metadata.first_side === 'opponent', 'opening checkpoint records first side');
    assert(savedBattle.initial_state.request.own_team.creatures[0].state.energy.value === 10, 'opening energy starts at ten');
    assert([...document.querySelectorAll('.fighter.opponent .skill-card input')].every(input => input.disabled), 'opponent skills are read only');
    el('.fighter.opponent .fighter-name').click();
    const opponentName = el('.fighter.opponent .fighter-name-input');
    type(opponentName, '测试'); await settle(); key(opponentName, 'Tab');
    assert(activeCreature('opponent').id === 1 && document.activeElement.title === '当前 HP', 'unknown opponent can be recorded during battle');
    activeCreature('opponent').hp = 100; activeCreature('opponent').maxHp = 100;
    clearCurrentFocus();
    const ownRow = () => el('.fighter.own.active');
    assert(key(document.body, 'k').defaultPrevented && state.focus.index === 0 && document.activeElement.value === '', 'k shortcut prevents inserted k');
    const skillInput = document.activeElement; type(skillInput, 'hq'); await settle(); key(skillInput, 'Tab');
    assert(activeCreature('own').skills[0].name === '火球' && state.focus.index === 1 && document.activeElement.closest('.skill-card').dataset.skill === '1', 'one Tab completes skill and immediately edits next');
    key(document.activeElement, 'Tab', {shiftKey:true}); assert(state.focus.index === 0, 'skill Shift Tab edits previous slot');
    const power = ownRow().querySelector('.power-input');
    assert(power.type === 'text' && power.value === '90', 'power is a plain input without spinner');
    key(document.activeElement, 'ArrowUp');
    assert(power.value === '90' && activeCreature('own').skills[0].effectOverride === .75, 'arrows change effect not power');
    activeCreature('own').skills[0].effectOverride = .5;
    const levels = [];
    for (let index = 0; index < 5; index++) { levels.push(activeCreature('own').skills[0].effectOverride); cycleEffectHint('own', 0, 1); }
    assert(JSON.stringify(levels) === JSON.stringify([.5, .75, 1, 1.5, 2]), 'all five effect levels are reachable');
    assert(ownRow().querySelectorAll('.effect polygon').length === 2 && getComputedStyle(ownRow().querySelector('.effect svg')).fill === 'none', 'double effect uses two hollow SVG triangles');
    const centroids = [...ownRow().querySelectorAll('.effect polygon')].map(polygon => polygon.getAttribute('points').split(' ').map(point => point.split(',').map(Number)).reduce((center, point) => [center[0] + point[0] / 3, center[1] + point[1] / 3], [0, 0]));
    assert(Math.abs(centroids[0][0] - centroids[1][0]) < .001 && Math.abs(centroids[0][1] - centroids[1][1]) < .001, 'nested equilateral triangles share a center');
    cycleEffectHint('own', 0, -1); assert(ownRow().querySelectorAll('.effect polygon').length === 1, 'single upper effect uses one triangle');
    cycleEffectHint('own', 0, -1); assert(ownRow().querySelector('.effect circle'), 'neutral effect is a hollow circle');
    const visual = ownRow().querySelector('.skill-visual').getBoundingClientRect();
    const powerBox = power.getBoundingClientRect(); const typeBox = ownRow().querySelector('.skill-type').getBoundingClientRect();
    assert(powerBox.left > typeBox.left && Math.abs(powerBox.bottom - visual.bottom) <= 2 && Math.abs(typeBox.bottom - visual.bottom) <= 2, 'power bottom right and type bottom left');
    assert(ownRow().querySelector('.skill-type img').getAttribute('src') === '/assets/dept_icons/火.png', 'skill element uses actual element icon');
    focusSkill('own', 3); key(document.activeElement, 'Tab');
    assert(state.focus === null && document.activeElement === document.body && el('#prompt').textContent === DEFAULT_BATTLE_PROMPT, 'fourth Tab behaves like Escape');
    key(document.body, 'l'); assert(state.focus === null, 'removed opponent skill shortcut does nothing');
    assert(ownRow().classList.contains('active'), 'active creature is highlighted');
    state.actions.own = {kind:'skill', slot:0}; refreshFocusHighlight();
    assert(ownRow().querySelector('.skill-card').classList.contains('selected'), 'selected action skill is highlighted');
    el('.footer-cell').scrollIntoView({block:'center'}); await settle();
    const footerBox = el('.footer-cell').getBoundingClientRect();
    assert(footerBox.bottom <= el('#prompt').getBoundingClientRect().top, 'footer is not covered by prompt ' + footerBox.bottom + '/' + el('#prompt').getBoundingClientRect().top);
    assert(ownRow().querySelector('.fighter-meta').children[0].getBoundingClientRect().top === ownRow().querySelector('.fighter-meta').children[1].getBoundingClientRect().top, 'HP and energy inputs share one row');
    assert([...el('.battle-status-row').children].map(panel => panel.classList[1]).join(',') === 'own,shared,opponent', 'status panels use own shared opponent columns');
    const beforeEnterPrompt = el('#prompt').textContent; key(document.body, 'Enter');
    assert(el('#prompt').textContent === beforeEnterPrompt && state.round === 1, 'first Enter does not show countdown prompt');
    lastEnter = 0; key(document.body, 'n'); assert(el('#buffer').textContent === 'n', 'n shortcut displays n');
    key(document.body, 'k'); key(document.body, '1'); assert(state.actions.own.kind === 'skill' && state.actions.own.slot === 0, 'nk1 selects own skill');
    clearCurrentFocus(); key(document.body, 'w'); assert(document.activeElement === el('#weatherInput'), 'w edits weather without inserting w');
    type(el('#weatherInput'), 'yt'); await settle(); key(el('#weatherInput'), 'Tab');
    assert(state.weather === 'rain' && el('#weatherInput').value === '雨天', 'weather autocomplete updates shared state');
    const buff = el('.status-panel.own .buffs input'); type(buff, '2');
    assert(buildRequest().own_team.creatures[0].state.buffs.value.atk === '2', 'status layer input is sent to core');
    scheduleSimulation(0); await settle();
    assert(comparison.result && !comparison.pending && el('#comparison .prediction-creature'), 'automatic simulation renders predicted creatures');
    assert(el('#comparison .uncertainty-note').textContent.includes('占位值'), 'unknown-input warnings are visible');
    const mainHp = activeCreature('own').hp;
    const actualHp = el('#comparison [data-compare-side=own] .observed-field input');
    type(actualHp, String(comparison.result.own.after.creatures[0].hp + 3));
    assert(actualHp.closest('label').classList.contains('differs') && activeCreature('own').hp === mainHp, 'actual values show differences without overwriting starting state');
    const callCount = simulationCalls; type(actualHp, '80'); await settle(); assert(simulationCalls === callCount, 'actual comparison edits do not trigger core calculation');
    holdSimulation = true; activeCreature('own').hp = 97; scheduleSimulation(0); await settle();
    activeCreature('own').hp = 93; scheduleSimulation(0); await settle();
    holdSimulation = false; simulationWaiters[1](); await settle(); simulationWaiters[0](); await settle();
    assert(comparison.result.own.after.creatures[0].hp === 83 && comparison.observed.own[0].hp === '80', 'stale simulation response is discarded and actual input is retained');
    simulationError = true; scheduleSimulation(0); await settle();
    assert(comparison.result === null && comparison.error === '测试核心失败', 'core errors clear stale predictions');
    simulationError = false; scheduleSimulation(0); await settle();
    rememberBattle('test-battle'); state.teams.own.creatures[0].name = '临时变化'; await restoreSavedBattle();
    assert(activeCreature('own').name === '测试精灵' && state.round === 1 && activeCreature('own').forms.length === 3, 'refresh restores opening names and forms');
    scheduleSimulation(0); await settle(); comparison.observed.own[0].hp = '80';
    await nextRound(); assert(state.round === 2 && savedBattle.rounds[0].round === 1, 'first submitted round remains round one');
    assert(activeCreature('own').hp === 80 && savedBattle.rounds[0].observed_after.actual.own[0].hp === '80', 'only entered actual results advance to next-round state');
    assert(savedBattle.rounds[0].observed_after.prediction.own.after.creatures[0].hp === 90, 'saved comparison retains separate core prediction');
    el('.sidebar').style.transition = 'none'; toggleMenu();
    if (matchMedia('(max-width:900px)').matches) {
      await new Promise(resolve => setTimeout(resolve, 400));
      assert(getComputedStyle(el('.sidebar-overlay')).display === 'block' && el('.sidebar').getBoundingClientRect().left === 0, 'small screen sidebar opens with overlay');
    }
    key(document.body, 'Escape'); assert(!el('.sidebar').classList.contains('active') && !el('.sidebar-overlay').classList.contains('active'), 'Escape closes sidebar and overlay');
    assert(failures.length === 0, 'no runtime errors');
    report.textContent = JSON.stringify({passed:true, checks:completed.length});
  } catch (error) { report.textContent = JSON.stringify({passed:false, error:error.message, completed, failures}); }
  document.body.appendChild(report);
})();
