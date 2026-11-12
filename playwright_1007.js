/** 按 1007.md 验证十一回合，记录差异供人工确认。 */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const rosterA = require('./1007A.json');
const rosterB = require('./1007B.json');
const failures = [];
const snapshots = [];
const resultPath = path.join(__dirname, '1007-results.json');
const baseUrl = process.env.NRC_TEST_URL || 'http://127.0.0.1:8767';

/** 保存双方界面数据和原始事件，不包含身份令牌。 */
async function snapshot(pages, label) {
  const sides = [];
  for (const page of pages) {
    sides.push(await page.evaluate(async () => {
      const { state } = await import('/static/state.js');
      const { battle_id, turn, phase, decision_index, terminal, winner } = state.battle;
      const fields = ['name', 'index', 'active', 'types', 'hp', 'max_hp', 'energy', 'fainted', 'ability', 'statuses', 'stats', 'modifiers', 'skills'];
      const teams = Object.fromEntries(['own', 'opponent'].map(side => [side,
        state.teams[side].map(item => Object.fromEntries(fields.filter(key => key in item).map(key => [key, item[key]])))]));
      return {
        battle: { battle_id, turn, phase, decision_index, terminal, winner }, teams, shared: state.shared,
        events: state.events, display: state.display,
        log: document.querySelector('#events').innerText,
      };
    }));
  }
  snapshots.push({ label, sides });
  fs.writeFileSync(resultPath, JSON.stringify({ failures, snapshots }, null, 2), 'utf8');
  return sides;
}

/** 记录失败，全部回合执行后统一设置失败退出码。 */
function check(condition, message) {
  if (!condition) {
    failures.push(message);
    console.error(message);
  }
}

/** 验证战报必有和隐藏的内容。 */
function assertText(text, patterns, name, hidden = []) {
  for (const pattern of patterns) check(pattern.test(text), name + ' 缺少 ' + pattern + '；实际：' + text);
  for (const pattern of hidden) check(!pattern.test(text), name + ' 应隐藏 ' + pattern + '；实际：' + text);
}

/** 沿用原脚本的伤害误差 1，其余数值精确比较，并检查字段缺失。 */
function assertSkillDetail(text, expected, name) {
  const labels = { power: '威力', damage: '造成', consume: '能耗', rest: '剩余能量' };
  for (const [field, value] of Object.entries(expected)) {
    const match = text.match(new RegExp(labels[field] + '\\s*(\\d+(?:\\.\\d+)?)'));
    const actual = match ? Number(match[1]) : NaN;
    const tolerance = field === 'damage' ? 1 : 0;
    check(Number.isFinite(actual) && Math.abs(actual - value) <= tolerance,
      name + ' ' + labels[field] + '异常：实际 ' + actual + '，期望 ' + value);
  }
}

/** 验证完整状态变化列表。 */
function assertState(text, patterns, name) {
  assertText(text, patterns, name);
  check(text.split('→').length - 1 === patterns.length, name + ' 状态变化数量异常；实际：' + text);
}

/** 连接已打开的两个浏览器；结束时仅断开连接。 */
async function connectExisting() {
  const browsers = [];
  try {
    for (const port of [9222, 9223]) {
      browsers.push(await chromium.connectOverCDP('http://127.0.0.1:' + port, { channel: 'chrome', timeout: 5000 }));
    }
    return browsers;
  } catch (error) {
    await Promise.all(browsers.map(browser => browser.close()));
    throw error;
  }
}

/** 通过页面导入阵容并创建、加入对局。 */
async function prepare(pages) {
  for (const [index, page] of pages.entries()) {
    page.setDefaultTimeout(15000);
    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.locator('#rstBtn').click();
    await page.locator('#roster-code').fill(JSON.stringify(index === 0 ? rosterA : rosterB));
    await page.locator('#import-roster').click();
    await page.getByText('阵容导入成功', { exact: true }).waitFor();
  }
  const [a, b] = pages;
  await a.locator('#start').click();
  await a.getByRole('button', { name: '确认首发', exact: true }).waitFor();
  await b.locator('#battle-code').fill(await a.locator('#battle-code').inputValue());
  await b.locator('#join').click();
  await b.getByRole('button', { name: '确认首发', exact: true }).waitFor();
  await a.locator('#start').click();
  await b.locator('#start').click();
}

/** 等待双方回合号同步且结算结束，力竭换宠时无需技能按钮。 */
async function ready(pages, turn) {
  for (const page of pages) {
    await page.locator('#turn').filter({ hasText: new RegExp('^' + turn + '$') }).waitFor();
    await page.waitForFunction(() => {
      const lock = document.querySelector('#lock-state');
      return lock && lock.textContent.trim() !== '正在结算';
    });
  }
}

/** 读取指定事件行，避免历史战报误命中或缺失事件等待超时。 */
async function eventText(page, type, turn, side) {
  const id = type + '-' + turn + '-' + side;
  const row = page.locator('#' + id);
  const count = await row.count();
  check(count === 1, '缺少或重复战报：' + id);
  return count === 1 ? row.innerText() : '';
}

/** 验证特性状态使用真实描述，普通状态不会产生重复名称悬浮窗。 */
async function verifyEffectTip(page, prefix, name, description) {
  const badge = page.locator('#' + prefix + '-effects .field-effect').filter({ hasText: name });
  const actual = await badge.getAttribute('data-effect-description');
  check(Boolean(actual) && description.test(actual), name + ' 特性描述异常：' + actual);
  await badge.hover();
  assertText(await page.locator('#skill-tooltip').innerText(), [description], name + ' 悬浮描述');
  await page.locator('#turn').hover();
}

/** 按双方视角验证技能选择隐藏和结算数值。 */
async function verifySkills(pages, round, skills, details) {
  for (const [index, page] of pages.entries()) {
    const name = '第' + round + '回合' + (index === 0 ? 'A' : 'B') + '视角';
    assertText(await eventText(page, 'selection', round, 'a'), [new RegExp(skills[index])], name);
    assertText(await eventText(page, 'selection', round, 'b'), [/完成/], name, [new RegExp(skills[1 - index])]);
    // 核心结算事件使用下一回合号，双方页面均将自己映射为 a。
    for (const skillIndex of [0, 1]) {
      const side = index === skillIndex ? 'a' : 'b';
      const text = await eventText(page, 'skill', round + 1, side);
      assertText(text, [new RegExp(skills[skillIndex])], name);
      assertSkillDetail(text, details[skillIndex], name + ' ' + skills[skillIndex]);
    }
  }
}

/** 执行十一回合并保留最终页面供人工检查。 */
async function main() {
  const browsers = await connectExisting();
  try {
    const pages = browsers.map(browser => browser.contexts()[0].pages()[0]);
    const [a, b] = pages;
    await prepare(pages);
    await ready(pages, 1);
    await a.locator('[data-skill-name="火焰箭"]').click();
    await b.locator('[data-skill-name="霜降"]').click();
    await ready(pages, 2);
    await verifySkills(pages, 1, ['火焰箭', '霜降'], [{ power: 160, damage: 192, consume: 2, rest: 10 }, { consume: 1, rest: 9 }]);
    assertText(await eventText(a, 'ability', 2, 'a'), [/特性：最好的伙伴/, /迪莫/, /能量\+2/, /最好的伙伴\+1层/], '第1回合最好的伙伴');
    assertText(await eventText(a, 'ability', 2, 'b'), [/迪莫/, /捉迷藏/, /全部技能能耗\+1/], '第1回合捉迷藏');
    assertState(await eventText(a, 'state_change', 2, 'a'), [/全技能能耗 0→1/, /冻结 0→4/, /最好的伙伴 0→1/], '第1回合迪莫状态');
    check(await a.locator('#state_change-2-b').count() === 0, '第1回合大耳帽兜不应有状态变化记录');

    await b.locator('[data-action="creature"]').click();
    await b.locator('[data-drawer-switch="1"]').click();
    await a.locator('[data-skill-name="闪光冲击"]').click();
    await ready(pages, 3);
    for (const [index, page] of pages.entries()) {
      const sideA = index === 0 ? 'a' : 'b';
      const prefixB = index === 0 ? 'enemy' : 'own';
      assertText(await page.locator('#' + prefixB + '-active-name').innerText(), [/^尖嘴狐仙$/], '第2回合换宠');
      const skill = await eventText(page, 'skill', 3, sideA);
      assertText(skill, [/闪光冲击/, /抵抗/, /尖嘴狐仙生命/], '第2回合闪光冲击');
      assertSkillDetail(skill, { damage: 80, consume: 4 }, '第2回合闪光冲击');
    }

    await a.locator('[data-skill-name="火焰箭"]').click();
    await b.locator('[data-skill-name="爆裂飞弹"]').click();
    await ready(pages, 4);
    await verifySkills(pages, 3, ['火焰箭', '爆裂飞弹'], [{ damage: 206, consume: 3 }, { damage: 124, consume: 7 }]);
    for (const [index, page] of pages.entries()) {
      const sideA = index === 0 ? 'a' : 'b';
      const sideB = index === 0 ? 'b' : 'a';
      assertText(await eventText(page, 'skill', 4, sideA), [/克制/, /尖嘴狐仙生命/], '第3回合火焰箭');
      assertText(await eventText(page, 'skill', 4, sideB), [/迪莫生命/], '第3回合爆裂飞弹');
      assertText(await eventText(page, 'state_change', 4, sideA), [/迪莫/, /冻结 4→6/], '第3回合冻结');
      const prefixA = index === 0 ? 'own' : 'enemy';
      assertText(await page.locator('#' + prefixA + '-freeze-text').innerText(), [/^冻结 6 层/], '第4回合迪莫冻结显示');
    }
    /** 通过阵容抽屉换宠，也用于力竭后的召唤。 */
    async function switchTo(page, index) {
      const replacement = (await page.locator('#phase').innerText()) === 'REPLACEMENT';
      await page.locator('[data-action="creature"]').click();
      await page.locator('[data-drawer-switch="' + index + '"]').click();
      if (replacement) {
        // 替换不增加回合号，单等 ready 会在提交请求完成前返回。
        for (const target of pages) {
          await target.waitForFunction(() => document.querySelector('#phase').textContent !== 'REPLACEMENT');
        }
        await ready(pages, Number(await page.locator('#turn').innerText()));
      }
    }
    /** 执行一回合并保存双方完整战报，断言失败仍继续后续回合。 */
    async function round(turn, actionA, actionB, expected) {
      await actionA();
      await actionB();
      await ready(pages, turn + 1);
      const logs = [];
      for (const [index, page] of pages.entries()) {
        const text = await page.locator('#events .event-row').evaluateAll((nodes, eventTurn) => nodes.filter(n => n.id.split('-')[1] === String(eventTurn)).map(n => n.id + ': ' + n.innerText).join('\n'), turn + 1);
        logs.push(text);
        console.log('第' + turn + '回合' + (index ? 'B' : 'A') + '视角\n' + text);
      }
      for (const [index, page] of pages.entries()) {
        for (const [side, detail] of expected.skills || []) {
          const visibleSide = index === 0 ? side : side === 'a' ? 'b' : 'a';
          assertSkillDetail(await eventText(page, 'skill', turn + 1, visibleSide), detail, '第' + turn + '回合' + side + '（' + (index ? 'B' : 'A') + '视角）');
        }
        assertText(logs[index], expected.patterns || [], '第' + turn + '回合' + (index ? 'B' : 'A') + '视角');
      }
      const sides = await snapshot(pages, '第' + turn + '回合结算');
      if (expected.mpA != null) {
        check(sides[0].shared.mp.own === expected.mpA && sides[1].shared.mp.opponent === expected.mpA,
          '第' + turn + '回合A方MP异常：实际 ' + sides[0].shared.mp.own + '，期望 ' + expected.mpA);
      }
      return sides;
    }
    const skill = (page, name) => () => page.locator('[data-skill-name="' + name + '"]').click();
    const charge = page => () => page.locator('#charge').click();
    await round(4, skill(a, '火焰箭'), () => switchTo(b, 4), { skills: [['a', { damage: 95, consume: 3 }]], patterns: [/冻土/, /2层/] });
    await verifyEffectTip(b, 'own', '冻土', /地系技能威力/);
    await ready(pages, 5);
    await round(5, charge(a), skill(b, '霜冻'), { skills: [['b', { consume: 1 }]], patterns: [/魔防降低 0→10/] });
    assertText(await a.locator('#own-energy').innerText(), [/^能量 7$/], '第5回合聚能');
    assertText(await a.locator('#own-effects').innerText(), [/魔防\s*-10\s*10%/], '第5回合魔防降低显示');
    await ready(pages, 6);
    await round(6, skill(a, '棘突'), skill(b, '冰雹'), { skills: [['a', { damage: 267, consume: 4 }], ['b', { damage: 80, consume: 4 }]], patterns: [/最好的伙伴/, /能量\+2/, /最好的伙伴 2→3/] });
    await ready(pages, 7);
    await round(7, skill(a, '棘突'), () => switchTo(b, 3), { skills: [['a', { damage: 320, consume: 4 }]], patterns: [/克制/, /能量\+2/, /最好的伙伴 3→4/] });
    await ready(pages, 8);
    // 四层最好的伙伴参与防御，按伤害文档计算为 96；108 对应漏算一层。
    await round(8, charge(a), skill(b, '超导'), { skills: [['b', { damage: 96, consume: 1 }]], patterns: [/力竭/], mpA: 3 });
    assertText(await b.locator('#enemy-active-name').innerText(), [/^迪莫$/], '第8回合对手保持力竭迪莫');
    assertText(await a.locator('#own-energy').innerText(), [/^能量 8$/], '第8回合聚能');
    await switchTo(a, 2);
    await snapshot(pages, '第9回合召唤蹦蹦花');
    await ready(pages, 9);
    await round(9, skill(a, '针刺射击'), () => switchTo(b, 2), { skills: [['a', { damage: 90, consume: 3 }]], patterns: [/中毒 0→2/] });
    assertText(await a.locator('#own-energy').innerText(), [/^能量 10$/], '第9回合换宠回能');
    assertText(await b.locator('#own-hp-text').innerText(), [/^374 \/ 493$/], '第9回合中毒扣血');
    await ready(pages, 10);
    await round(10, skill(a, '剧毒'), skill(b, '暗突袭'), { skills: [['b', { damage: 486, consume: 4 }]], patterns: [/生命 374→493/, /恶魔的晚宴\+5层/], mpA: 2 });
    check(await a.locator('#skill-11-a').count() === 0, '第10回合剧毒应被应对且不执行');
    assertText(await b.locator('#own-hp-text').innerText(), [/^464 \/ 493$/], '第10回合中毒扣血');
    assertText(await b.locator('#own-effects').innerText(), [/中毒\s*2 层/], '第10回合中毒保持2层');
    assertText(await a.locator('#enemy-active-name').innerText(), [/乌拉塔/], '第10回合敌方在场');
    assertText(await b.locator('#enemy-active-name').innerText(), [/蹦蹦花/], '第10回合对手保持力竭蹦蹦花');
    for (const [page, prefix] of [[a, 'enemy'], [b, 'own']]) {
      const text = await page.locator('#' + prefix + '-effects').innerText();
      assertText(text, [/恶魔的晚宴\s*5 层/], '恶魔的晚宴完整状态', [/攻击\s*5/, /魔攻\s*5/]);
      await verifyEffectTip(page, prefix, '恶魔的晚宴', /击败/);
      check(await page.locator('#' + prefix + '-effects .field-effect').filter({ hasText: '中毒' }).getAttribute('data-effect-tip') === null,
        '中毒普通状态不应显示描述');
    }
    await switchTo(a, 4);
    await ready(pages, 11);
    await snapshot(pages, '第11回合召唤寒音蛇');
    assertText(await a.locator('#own-effects').innerText(), [/拨浪鼓\s*2 层/], '第11回合入场');
    await round(11, skill(a, '撒娇'), skill(b, '极限撕裂'), { skills: [['a', { damage: 429, consume: 3 }], ['b', { damage: 1021 }]], patterns: [/143\/段 × 3/, /古钟蛇/, /萌化/, /恶魔的晚宴/, /力竭/], mpA: 1 });
    assertText(await a.locator('#own-effects').innerText(), [/全技能威力\s*10/], '第11回合撒娇全技能威力');
    assertText(await a.locator('#own-active-name').innerText(), [/^古钟蛇$/], '第11回合退化');
    assertText(await a.locator('#own-hp-text').innerText(), [/^0 \//], '第11回合力竭');
    assertText(await b.locator('#enemy-active-name').innerText(), [/^古钟蛇$/], '第11回合对手保持力竭古钟蛇');
    assertText(await b.locator('#own-effects').innerText(), [/恶魔的晚宴\s*10 层/], '恶魔的晚宴累计10层');
    assertText(await b.locator('#own-hp-text').innerText(), [/^6 \/ 493$/], '第11回合中毒扣血');
    console.log('十一回合执行完成。文档最后要求召唤古拉多，但输入阵容没有古拉多，未执行该步。');
    if (failures.length) throw new Error('共 ' + failures.length + ' 项验证失败。');
    console.log('全部验证通过。');
  } finally {
    fs.writeFileSync(resultPath, JSON.stringify({ failures, snapshots }, null, 2), 'utf8');
    await Promise.all(browsers.map(browser => browser.close()));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
