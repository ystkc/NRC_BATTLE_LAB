/** 按 1007.md 验证前三回合，停在第四回合待选状态。 */
const { chromium } = require('playwright');
const rosterA = require('./1007A.json');
const rosterB = require('./1007B.json');
const failures = [];

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
    // if (field === 'damage') console.log(name + '：伤害 ' + actual + '，文档 ' + value + '，允许误差 1');
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
    await page.goto('http://127.0.0.1:8767/', { waitUntil: 'domcontentloaded' });
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

/** 等待双方回合号和操作按钮同步就绪。 */
async function ready(pages, turn) {
  for (const page of pages) {
    await page.locator('#turn').filter({ hasText: new RegExp('^' + turn + '$') }).waitFor();
    await page.locator('#skills button:not([disabled])').first().waitFor();
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

/** 执行前三回合并保留第四回合页面供人工检查。 */
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
    console.log('前三回合操作完成，双方已进入第4回合待选状态。');
    if (failures.length) throw new Error('共 ' + failures.length + ' 项验证失败。');
    console.log('全部验证通过。');
  } finally {
    await Promise.all(browsers.map(browser => browser.close()));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
