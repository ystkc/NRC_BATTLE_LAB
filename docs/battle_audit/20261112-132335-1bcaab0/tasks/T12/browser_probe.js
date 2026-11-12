/** T12 独立 HTTP 与双 context 页面审计，业务文件只读。 */
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../../../../..');
const base = 'http://127.0.0.1:8774';
const output = {checks: [], requests: [], pageErrors: [], consoleErrors: []};
const rosterA = JSON.parse(fs.readFileSync(path.join(root, '1007A.json'), 'utf8'));
const rosterB = JSON.parse(fs.readFileSync(path.join(root, '1007B.json'), 'utf8'));
function redact(value) {if(Array.isArray(value))return value.map(redact);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,['player_token','token','ta','tb'].includes(k)?'<audit-token-redacted>':redact(v)]));return value;}
function save() {fs.writeFileSync(path.join(__dirname, 'browser_output.json'), JSON.stringify(redact(output), null, 2));}
function check(name, pass, details) {output.checks.push({name, pass:!!pass, details}); save();}
async function req(url, token='', method='GET', body) {
  const response = await fetch(base+url, {method, headers:{'Content-Type':'application/json', ...(token?{'X-Player-Token':token}:{})}, ...(body===undefined?{}:{body:typeof body==='string'?body:JSON.stringify(body)})});
  const text=await response.text(); let data; try {data=JSON.parse(text);} catch {data=text.slice(0,250);}
  const result={status:response.status,data}; output.requests.push({url,method,body,...result}); save(); return result;
}
async function identity(page) {return page.evaluate(async()=>{const {state}=await import('/static/state.js'); return {token:state.playerToken,battle:state.battle,actions:state.actions,display:state.display,shared:state.shared};});}
async function ready(pages, turn) {for(const p of pages) {await p.waitForFunction(t=>!document.querySelector('#battle').classList.contains('hidden')&&document.querySelector('#turn').textContent===String(t)&&document.querySelector('#lock-state').textContent==='选择操作'&&document.querySelector('#skills button:not([disabled])'),turn,{timeout:30000});}}
async function capture(page,name) {await page.screenshot({path:path.join(__dirname,name+'.png'),fullPage:true});}
async function fixture(a,b) {
 const ca=await req('/api/battles','','POST',{mode:'full',seed:1007}); const id=ca.data.battle_id,ta=ca.data.player_token;
 const cb=await req(`/api/battles/${id}/join`,'','POST',{}); const tb=cb.data.player_token;
 await req(`/api/battles/${id}/rosters`,ta,'POST',{roster:a,active_index:0,confirm:true});
 const initialized=await req(`/api/battles/${id}/rosters`,tb,'POST',{roster:b,active_index:0,confirm:true});
 return {id,ta,tb,initialized};
}
async function openFixture(page, f, token, side, roster) {
 await page.goto(base); await page.evaluate(v=>sessionStorage.setItem('nrc-battle-session',JSON.stringify(v)),{battleId:f.id,playerToken:token,side,selectedStart:0,teams:roster}); await page.reload();
 await page.waitForFunction(()=>!document.querySelector('#battle').classList.contains('hidden'));
}
async function main() {
 await new Promise((resolve,reject)=>{const probe=net.createServer();probe.once('error',reject);probe.listen(8774,'127.0.0.1',()=>probe.close(resolve));});
 output.portCheck='8774 free before launch';
 const log=fs.openSync(path.join(__dirname,'server.log'),'w');
 const server=spawn('python',['-c',"from nrc_core.debug import configure_core_logging; configure_core_logging(''); from nrc_server.server import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8774, log_level='warning')"],{cwd:root,windowsHide:true,stdio:['ignore',log,log],env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONUTF8:'1',PYTHONDONTWRITEBYTECODE:'1'}});
 output.serverPid=server.pid; let browser;
 try {
  for(let i=0;i<100;i++){try{if((await fetch(base)).ok)break;}catch{} if(server.exitCode!==null)throw Error('server exited');await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({channel:'chrome',headless:true});output.chromeVersion=browser.version();
  const contexts=await Promise.all([browser.newContext({viewport:{width:1440,height:950}}),browser.newContext({viewport:{width:1440,height:950}})]);
  const pages=await Promise.all(contexts.map(c=>c.newPage())); const [a,b]=pages;
  for(const [i,p] of pages.entries()){p.on('pageerror',e=>{output.pageErrors.push({i,message:e.message});save();});p.on('console',m=>{if(m.type()==='error')output.consoleErrors.push({i,message:m.text()});});}
  for(const [i,p]of pages.entries()){await p.goto(base);await p.locator('#roster-code').fill(JSON.stringify(i?rosterB:rosterA));await p.locator('#import-roster').click();await p.getByText('阵容导入成功',{exact:true}).waitFor();}
  await a.locator('#start').click();await a.getByRole('button',{name:'确认首发',exact:true}).waitFor();
  const id=await a.locator('#battle-code').inputValue();await b.locator('#battle-code').fill(id);await b.locator('#join').click();await b.getByRole('button',{name:'确认首发',exact:true}).waitFor();
  await a.locator('#start').click();await b.locator('#start').click();await ready(pages,1);
  let ia=await identity(a),ib=await identity(b); output.main={id,sideA:ia.battle.side,sideB:ib.battle.side};
  check('isolated seats',ia.token!==ib.token&&ia.battle.side==='own'&&ib.battle.side==='opponent',output.main);
  await a.locator('#enemy-pips').hover();await a.locator('#opponent-roster-popup').waitFor({state:'visible'});
  const firstPopup=await a.locator('#opponent-roster-popup').innerText();check('unknown bench hidden in popup',firstPopup.includes('大耳帽兜')&&!firstPopup.includes('尖嘴狐仙')&&!firstPopup.includes('乌拉塔'),firstPopup);await capture(a,'01_initial_known');await a.keyboard.press('Escape');
  const shown=await a.locator('#skills button').evaluateAll(nodes=>nodes.map(n=>({name:n.dataset.skillName,disabled:n.disabled,cost:n.querySelector('.skill-cost-badge')?.textContent,power:n.querySelector('.skill-power-badge')?.textContent})));
  check('initial buttons and values match display/legal actions',shown.every(s=>{const d=ia.display.skills.find(x=>x.name===s.name);return d&&s.cost===String(d.display_energy_cost)&&s.power===String(d.display_power>0?d.display_power:'-')&&s.disabled===!ia.actions.some(x=>x.key.startsWith('skill:slot='+d.skill_slot));}),{shown,display:ia.display,actions:ia.actions});
  await a.locator('[data-skill-name="火焰箭"]').click();await a.waitForFunction(()=>document.querySelector('#lock-state').textContent.includes('已锁定'));
  const pendingId=await identity(a);await a.reload();await a.waitForFunction(()=>document.querySelector('#lock-state').textContent.includes('已锁定'));
  const restored=await identity(a);check('reload preserves pending identity and disables all skills',restored.token===pendingId.token&&(await a.locator('#skills button:not([disabled])').count())===0,{before:pendingId.battle,after:restored.battle});
  await b.locator('[data-skill-name="霜降"]').click();await ready(pages,2);await capture(a,'02_after_turn');
  const beforeReload=await a.locator('#events .event-row').count();await a.reload();await ready([a],2);const afterReload=await a.locator('#events .event-row').count();check('reload replays no duplicate history rows',beforeReload===afterReload,{beforeReload,afterReload});
  await b.locator('[data-action="creature"]').click();await b.locator('[data-drawer-switch="1"]').click();await a.locator('[data-skill-name="闪光冲击"]').click();await ready(pages,3);
  await a.locator('#enemy-pips').hover();const secondPopup=await a.locator('#opponent-roster-popup').innerText();check('revealed bench retained',secondPopup.includes('大耳帽兜')&&secondPopup.includes('尖嘴狐仙')&&!secondPopup.includes('乌拉塔'),secondPopup);await capture(a,'03_revealed_bench');
  await a.setViewportSize({width:560,height:800});await a.locator('#enemy-pips').hover();const box=await a.locator('#opponent-roster-popup').boundingBox();check('narrow popup inside viewport',box.x>=0&&box.x+box.width<=560,box);await capture(a,'04_narrow');await a.keyboard.press('Escape');await a.setViewportSize({width:1440,height:950});
  const routes=['','/opponent-roster','/display','/matchups','/actions','/state','/operation?since=-1','/events?since=0'];
  const outsider=(await req('/api/battles','','POST',{mode:'full'})).data.player_token;
  for(const route of routes){const unauth=await req(`/api/battles/${id}${route}`);const foreign=await req(`/api/battles/${id}${route}`,outsider);check('auth '+route,unauth.status===401&&foreign.status===403,{unauth:unauth.status,foreign:foreign.status});}
  check('same token rejoins fixed seat',(await req(`/api/battles/${id}/join`,ia.token,'POST',{})).data.side==='own');
  check('third seat rejected',(await req(`/api/battles/${id}/join`,outsider,'POST',{})).status===422);
  check('malformed top-level JSON rejected',(await req('/api/pokemon/preview','','POST',[])).status===422);
  check('invalid JSON rejected',(await req('/api/pokemon/preview','','POST','{')).status===422);
  check('missing detail 404',(await req('/api/pokemon/T12不存在')).status===404);
  await req('/api/catalog?kind=skills&q=huoyan');await req('/api/catalog?kind=bad');await req('/api/pokemon/迪莫');await req('/api/pokemon/preview','','POST',{name:'迪莫'});
  check('side spoof roster rejected',(await req(`/api/battles/${id}/rosters`,ia.token,'POST',{side:'opponent',roster:rosterA.roster})).status===422);
  const index=(await req(`/api/battles/${id}`,ia.token)).data.decision_index;
  const selection={action_key:'charge',request_id:'T12-idempotent',decision_index:index};const r1=await req(`/api/battles/${id}/selection`,ia.token,'POST',selection);const r2=await req(`/api/battles/${id}/selection`,ia.token,'POST',selection);
  check('duplicate request id preserves response',JSON.stringify(r1)===JSON.stringify(r2),{r1,r2});
  check('second distinct pending submission rejected',(await req(`/api/battles/${id}/selection`,ia.token,'POST',{...selection,request_id:'T12-other'})).status===409);
  await req(`/api/battles/${id}/selection`,ib.token,'POST',{...selection,request_id:'T12-b'});
  check('stale decision rejected',(await req(`/api/battles/${id}/selection`,ia.token,'POST',{...selection,request_id:'T12-stale'})).status===409);
  const evA=await req(`/api/battles/${id}/events`,ia.token);const evB=await req(`/api/battles/${id}/events`,ib.token);const empty=await req(`/api/battles/${id}/events?since=${evA.data.cursor}`,ia.token);
  check('event cursor no duplicates',empty.data.events.length===0&&empty.data.cursor===evA.data.cursor,{cursorA:evA.data.cursor,cursorB:evB.data.cursor});
  output.twoViewEvents={a:evA.data,b:evB.data};
  // 人为极低 HP 只用于强制进入补位阶段，不作为战斗规则预期。
  const low=JSON.parse(JSON.stringify(rosterA.roster.slice(0,2)));low[0].base={stats:{hp:1,atk:10,def:10,spatk:10,spdef:10,speed:1}};
  const strong=JSON.parse(JSON.stringify(rosterB.roster.slice(0,2)));strong[0].name='迪莫';strong[0].skills=['猛烈撞击','火焰箭','棘突','超导'];strong[0].base={stats:{hp:1000,atk:10000,def:100,spatk:100,spdef:100,speed:1000}};
  const f=await fixture(low,strong);output.replacementFixture=f;
  await req(`/api/battles/${f.id}/selection`,f.ta,'POST',{action_key:'charge',request_id:'replace-a',decision_index:0});
  const kill=await req(`/api/battles/${f.id}/selection`,f.tb,'POST',{action_key:'skill:slot=0',request_id:'replace-b',decision_index:0});
  output.replacementResult=kill;
  await openFixture(a,f,f.ta,'own',low);await openFixture(b,f,f.tb,'opponent',strong);await a.waitForFunction(()=>document.querySelector('#phase').textContent==='REPLACEMENT');
  await a.locator('#skills .switch-card').waitFor();check('replacement only switch cards, opponent waits',(await a.locator('#skills .switch-card').count())>0&&(await b.locator('#skills button').count())===0,{a:await a.locator('#skills').innerText(),b:await b.locator('#skills').innerText()});await capture(a,'05_replacement');
  await a.reload();await a.locator('#skills .switch-card').waitFor();await a.locator('#skills .switch-card').first().click();await ready(pages,2);check('replacement refresh and resume',true,{a:(await identity(a)).battle,b:(await identity(b)).battle});
  // 直接输入与编辑器随机池中的本地分支。
  const edit=await contexts[0].newPage();await edit.goto(base);await edit.locator('#own-search').fill('迪莫 420');await edit.locator('[data-search-confirm="own-search"]').click();await edit.locator('#export-roster').click();output.directStatExport=JSON.parse(await edit.locator('#roster-code').inputValue());check('direct HP does not add aptitudes',Object.keys(output.directStatExport.roster[0].base.individual_values||{}).length===0,output.directStatExport);
  await edit.locator('[data-edit-index="0"]').click();await edit.locator('[data-editor-field="aptitude"]').fill('速度');await edit.waitForTimeout(100);output.aptitudeSuggestions=await edit.locator('[data-editor-suggest="aptitude"]').innerText();
  await capture(edit,'06_editor');
  check('no uncaught page exceptions',output.pageErrors.length===0,output.pageErrors);
 } catch(error) {output.fatal={message:error.message,stack:error.stack};save();process.exitCode=1;}
 finally {if(browser)await browser.close();server.kill();fs.closeSync(log);output.finished=true;save();}
}
main().catch(error=>{output.fatal={message:error.message,stack:error.stack};save();process.exitCode=1;});
