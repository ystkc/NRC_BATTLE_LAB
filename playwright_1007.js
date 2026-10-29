const { chromium } = require('playwright');
const fs = require('fs');

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: false });
  const a = await browser.newPage();
  const b = await browser.newPage();
  const base = 'http://127.0.0.1:8767';
  await a.goto(base);
  await b.goto(base);
  // 直接读取案例阵容，所有对局操作均经页面完成。
  const document = fs.readFileSync(require('path').join(__dirname, '1007.md'), 'utf8');
  for (const [page, side] of [[a, 'A'], [b, 'B']]) {
    page.setDefaultTimeout(60000);
    const roster = JSON.parse(document.match(new RegExp(`side${side}\\s*\\r?\\n([^\\r\\n]+)`))[1]);
    await page.locator('#roster-code').fill(JSON.stringify(roster));
    await page.locator('#import-roster').click();
    await page.getByText('阵容导入成功', { exact: true }).waitFor();
  }
  await a.locator('#start').click();
  await a.getByRole('button', { name: '确认首发', exact: true }).waitFor();
  const id = await a.locator('#battle-code').inputValue();
  await b.locator('#battle-code').fill(id);
  await b.locator('#join').click();
  await b.getByRole('button', { name: '确认首发', exact: true }).waitFor();
  await a.locator('#start').click();
  await b.locator('#start').click();
  /** 等待双方进入下一回合并解锁操作。 */
  async function ready(turn) {
    for (const page of [a, b]) {
      await page.locator('#turn').filter({ hasText: new RegExp(`^${turn}$`) }).waitFor();
      await page.locator('#skills button:not([disabled])').first().waitFor();
    }
  }
  function assertEvent(text, pattern, label) {
    if (!pattern.test(text)) throw new Error(`${label} 未找到: ${pattern}; 实际战报:\n${text}`);
  }
  async function assertRound(round, checks) {
    const text = `${await a.locator('#events').innerText()}\n${await b.locator('#events').innerText()}`;
    for (const [pattern, label] of checks) assertEvent(text, pattern, `第${round}回合 ${label}`);
    return text;
  }
  for (const [index, skills] of [['火焰箭', '霜降'], ['闪光冲击', null], ['火焰箭', '爆裂飞弹']].entries()) {
    await ready(index + 1);
    await a.locator(`[data-skill-name="${skills[0]}"]`).click();
    if (skills[1]) await b.locator(`[data-skill-name="${skills[1]}"]`).click();
    else {
      await b.locator('[data-action="creature"]').click();
      await b.locator('[data-drawer-switch="1"]').click();
    }
    await ready(index + 2);
    const round = index + 1;
    const checks = round === 1
      ? [[/火焰箭/, '技能'], [/192/, '伤害192'], [/能量|能耗/, '能量变化'], [/冻结.*0.*4|冻结.*4/, '冻结状态']]
      : round === 2
        ? [[/闪光冲击/, '技能'], [/80/, '伤害80'], [/尖嘴狐仙/, '换入状态']]
        : [[/火焰箭/, '技能'], [/206/, '伤害206'], [/爆裂飞弹/, '技能'], [/冻结.*4.*6|冻结.*6/, '冻结由4到6（灵魂灼伤）']];
    const text = await assertRound(round, checks);
    console.log(`回合 ${round}`, text);
  }
  await browser.close();
}
main().catch(error => { console.error(error); process.exitCode = 1; });
