/** 用独立服务和 Chrome 验证特性战报、换宠隐私和已知阵容弹窗。 */
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const { chromium } = require('playwright');
const rosterA = require('../1007A.json');
const rosterB = require('../1007B.json');

/** 等待服务启动，失败时给出明确错误。 */
async function waitForServer(url, server) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode != null) throw new Error('测试服务提前退出：' + server.exitCode);
    try { if ((await fetch(url)).ok) return; } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('测试服务启动超时');
}

/** 等待结算动画结束并解锁下一回合。 */
async function ready(pages, turn) {
  for (const page of pages) {
    await page.waitForFunction(value => document.querySelector('#turn').textContent === String(value), turn);
    await page.locator('#skills button:not([disabled])').first().waitFor();
  }
}

/** 检查弹窗仅包含已知精灵，且能从圆点移入弹窗。 */
async function verifyPopup(page, names) {
  await page.locator('#enemy-pips').hover();
  const popup = page.locator('#opponent-roster-popup');
  await popup.waitFor({ state: 'visible' });
  assert.equal(await popup.locator('.opponent-roster-member').count(), names.length);
  for (const name of names) assert.ok((await popup.innerText()).includes(name));
  assert.ok(!(await popup.innerText()).includes('乌拉塔'));
  assert.equal(await popup.locator('[data-battle-action], [data-drawer-switch]').count(), 0);
  await popup.hover();
  await page.waitForTimeout(180);
  assert.ok(await popup.isVisible());
  const box = await popup.boundingBox();
  assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= 1440 && box.y + box.height <= 950);
  await page.keyboard.press('Escape');
  await popup.waitFor({ state: 'hidden' });
}

/** 从导入阵容到第三回合验证真实页面行为。 */
async function main() {
  const root = path.resolve(__dirname, '..');
  const server = spawn('python', ['-c', "from nrc_core.debug import configure_core_logging; configure_core_logging(''); from nrc_server.server import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8769, log_level='warning')"], { cwd: root, windowsHide: true, stdio: 'inherit' });
  let browser;
  try {
    await waitForServer('http://127.0.0.1:8769/', server);
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const contexts = await Promise.all([browser.newContext({ viewport: { width: 1440, height: 950 } }), browser.newContext({ viewport: { width: 1440, height: 950 } })]);
    const pages = await Promise.all(contexts.map(context => context.newPage()));
    const errors = [];
    for (const [index, page] of pages.entries()) {
      page.on('pageerror', error => errors.push(error.message));
      await page.goto('http://127.0.0.1:8769/');
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
    await ready(pages, 1);
    await verifyPopup(a, ['大耳帽兜']);
    await a.locator('[data-skill-name="火焰箭"]').click();
    await b.locator('[data-skill-name="霜降"]').click();
    await ready(pages, 2);
    for (const page of pages) {
      const abilities = await page.locator('[id^="ability-"] span').allTextContents();
      assert.ok(abilities.length >= 2);
      assert.ok(abilities.every(text => text.startsWith('[特性：')));
      const partner = page.locator('[id^="ability-"]').filter({ hasText: '最好的伙伴' });
      assert.match(await partner.innerText(), /最好的伙伴\+1层/);
      assert.doesNotMatch(await partner.innerText(), /物攻提升/);
    }
    await b.locator('[data-action="creature"]').click();
    await b.locator('[data-drawer-switch="1"]').click();
    await b.waitForFunction(() => document.querySelector('#lock-state').textContent.includes('已锁定'));
    await a.locator('[data-skill-name="闪光冲击"]').click();
    await ready(pages, 3);
    assert.match(await b.locator('#selection-2-a').innerText(), /我方选择切换精灵.*尖嘴狐仙/);
    assert.doesNotMatch(await a.locator('#selection-2-b').innerText(), /尖嘴狐仙/);
    await verifyPopup(a, ['大耳帽兜', '尖嘴狐仙']);
    await a.setViewportSize({ width: 560, height: 800 });
    await a.locator('#enemy-pips').hover();
    const mobileBox = await a.locator('#opponent-roster-popup').boundingBox();
    assert.ok(mobileBox.x >= 0 && mobileBox.x + mobileBox.width <= 560);
    await a.keyboard.press('Escape');
    await a.setViewportSize({ width: 1440, height: 950 });
    await a.locator('[data-skill-name="火焰箭"]').click();
    await b.locator('[data-skill-name="爆裂飞弹"]').click();
    await ready(pages, 4);
    for (const [index, page] of pages.entries()) {
      const sideA = index === 0 ? 'a' : 'b';
      const sideB = index === 0 ? 'b' : 'a';
      assert.match(await page.locator('#ability-4-' + sideB).innerText(), /特性：灵魂灼伤.*冻结\+2/);
      assert.match(await page.locator('#state_change-4-' + sideA).innerText(), /冻结 4→6/);
      assert.match(await page.locator('#' + (index === 0 ? 'own' : 'enemy') + '-freeze-text').innerText(), /^冻结 6 层/);
    }
    assert.deepEqual(errors, []);
    console.log('通过：Chrome 真实对局、特性标题、完整状态战报、己方换宠名、对手选择遮蔽、已知阵容弹窗、窄屏布局、灵魂灼伤及冻结4→6。');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
