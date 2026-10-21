/** Exercise the built page in the host's opaque-origin sandbox and real bridge. */
import { createServer } from 'node:http';
import { readFile, mkdtemp } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, expect } from '../views/node_modules/@playwright/test/index.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const host = process.env.HUMANIZATION_ASTRBOT_SOURCE || resolve(root, '../../..');
const sdk = await readFile(join(host, 'astrbot/dashboard/plugin_page_bridge.js'), 'utf8');
const schema = JSON.parse(await readFile(join(root, '_conf_schema.json'), 'utf8'));
const config = Object.fromEntries(Object.entries(schema).map(([key, section]) => [key,
  Object.fromEntries(Object.entries(section.items).map(([key, field]) => [key, field.default]))]));
for (const key of ['sessions','blacklist_sessions']) {
  schema.scope.items[key].options = ['onebot:GroupMessage:123','onebot:FriendMessage:456'];
  schema.scope.items[key].labels = ['测试群','测试私聊'];
}
const scope = JSON.stringify(['onebot', '999', 'group', '123']);
const rows = [1, 2].map(id => ({ id, key:JSON.stringify([scope,id]), scope,
  timestamp:1792346400, conversation:'onebot:GroupMessage:123', headline:`天气很好 ${id}`,
  text:`天气很好 ${id}`, sender_name:'测试用户', sender_id:'42', direction:'in',
  segments:[{type:'text',text:'<script>window.UNSAFE = true</script>'},{type:'poke',target_id:'999'}],
}));
rows[1].headline = '这是一段需要省略显示但悬停时应完整保留的内容。'.repeat(16);
const records = {
  messages:rows,
  decisions:rows.map((row,index)=>({...row, headline:'根据当前话题简短回应', outcome:index ? 'processed' : 'unconfirmed', decision_json:{reply:true,emotion:{primary:'SELF_CONSCIOUS',intensity:1},plan:{guidance:'简短接话'}}})),
  topics:rows.map(row=>({...row,day:'2026-10-19',topic:'讨论天气',interact:['测试用户分享天气'],reply:'我简短回应',reaction:'未见明确反应'})),
  diaries:rows.map(row=>({...row,day:'2026-10-19',sealed:0,topic_count:2,coverage_gap:0,topics:[]})),
};
const promptDefaults = Object.fromEntries(await Promise.all(['behavior','expression','group','private'].map(async name=>[name,(await readFile(join(root,`resource/prompts/${name}.txt`),'utf8')).trim()])));
const seed = {schema,config,prompt_defaults:promptDefaults,revision:'initial',reset_confirmation:'CLEAR_ALL_HUMANIZATION_DATA',choices:{select_provider:[{title:'DeepSeek',value:'deepseek'}],select_persona:[{title:'测试人格',value:'persona1',description:'角色片段内容'}]}};
const harness = `<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">
<iframe title="Humanization" src="/view/" sandbox="allow-scripts allow-forms allow-downloads" style="width:100%;height:100vh;border:0"></iframe>
<script>
window.calls=[]; window.saved=null; window.deleted={}; window.failSave=false; window.resetCount=0;
const settings=${JSON.stringify(seed).replaceAll('<','\\u003c')};
const records=${JSON.stringify(records).replaceAll('<','\\u003c')};
const frame=document.querySelector('iframe');
window.context = isDark => frame.contentWindow.postMessage({channel:'astrbot-plugin-page',kind:'context',context:{pluginName:'astrbot_plugin_humanization',pageName:'humanization',locale:'zh-CN',isDark}},'*');
window.addEventListener('message', event => {
  if(event.source!==frame.contentWindow || event.data.channel!=='astrbot-plugin-page') return;
  const m=event.data;
  if(m.kind==='ready') { window.context(false); return; }
  if(m.kind!=='request') return;
  window.calls.push(m); let data;
  if(m.endpoint==='overview') data={stats:{sessions:2,messages:2,topics:2,diaries:2,decisions:2,planned_replies:2},sessions:[{title:'测试群',value:'onebot:GroupMessage:123',umo:'onebot:GroupMessage:123'},{title:'测试私聊',value:'onebot:FriendMessage:456',umo:'onebot:FriendMessage:456'}],timezone:'Asia/Shanghai'};
  if(m.endpoint==='records') {const items=records[m.params.category].filter(r=>!(window.deleted[m.params.category]||[]).includes(r.key));data={items,total:items.length};}
  if(m.endpoint==='records/delete') { (window.deleted[m.body.category] ||= []).push(...m.body.keys); data={deleted:m.body.keys.length}; }
  if(m.endpoint==='settings') data=settings;
  if(m.endpoint==='prompts/diff') {
    const original=settings.prompt_defaults[m.body.name], draft=m.body.text.trim() ? m.body.text : original;
    const a=original.split(String.fromCharCode(10)), b=draft.split(String.fromCharCode(10));
    data={identical:original===draft,rows:Array.from({length:Math.max(a.length,b.length)},(_,i)=>({kind:a[i]===b[i] ? 'equal' : 'replace',left:i<b.length ? {number:i+1,text:b[i],segments:[{text:b[i],changed:a[i]!==b[i]}]} : null,right:i<a.length ? {number:i+1,text:a[i],segments:[{text:a[i],changed:a[i]!==b[i]}]} : null}))};
  }
  if(m.endpoint==='settings/save') {
    if(window.failSave) {frame.contentWindow.postMessage({channel:'astrbot-plugin-page',kind:'response',requestId:m.requestId,ok:false,error:'模拟保存失败'},'*');return;}
    window.saved=m.body; settings.config=m.body.config; settings.revision=String(Date.now()); data={saved:true,reloaded:true};
  }
  if(m.endpoint==='data/reset-all') {window.resetCount++;data={reset:true,conversations:2};}
  frame.contentWindow.postMessage({channel:'astrbot-plugin-page',kind:'response',requestId:m.requestId,ok:true,data},'*');
});
</script></body></html>`;
const server = createServer(async (req,res) => {
  try {
    const url = req.url.split('?')[0];
    const files = {'/view/app.js':'app.js','/view/style.css':'style.css','/view/assets/vendor.js':'assets/vendor.js'};
    if (url === '/') { res.setHeader('Content-Type','text/html; charset=utf-8'); res.end(harness); }
    else if (url === '/view/') {
      res.setHeader('Content-Type','text/html; charset=utf-8');
      const html = await readFile(join(root,'views/humanization/index.html'),'utf8');
      res.end(html.replace('</head>', `<script>${sdk}</script></head>`));
    } else if (files[url]) {
      res.setHeader('Access-Control-Allow-Origin','*');
      res.setHeader('Content-Type',url.endsWith('.js') ? 'text/javascript' : 'text/css');
      res.end(await readFile(join(root,'views/humanization',files[url])));
    } else {res.statusCode=404; res.end();}
  } catch(error) {res.statusCode=500; res.end(String(error));}
});
await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
const executablePath = process.env.HUMANIZATION_BROWSER || [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
].find(existsSync);
const browser = await chromium.launch({headless:true,...(executablePath ? {executablePath} : {})});
const output = await mkdtemp(join(tmpdir(),'humanization-ui-'));
let page;
const errors = [];
try {
  page = await browser.newPage({viewport:{width:1280,height:960}, reducedMotion:'reduce'});
  page.setDefaultTimeout(10000);
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  const view = page.frameLocator('iframe');
  await expect(view.getByRole('heading',{name:'Humanization'})).toBeVisible();
  if (process.argv.includes('--settings-regression')) {
    await view.getByRole('tab',{name:'设置',exact:true}).click();
    await expect(view.getByText('配置与原生插件设置共用同一份文件。保存后重载插件生效，进行中的回复可能中断。',{exact:true})).toBeVisible();
    await view.getByRole('tab',{name:'话题',exact:true}).click();
    await expect(view.getByText('配置与原生插件设置共用同一份文件。保存后重载插件生效，进行中的回复可能中断。',{exact:true})).toBeHidden();
    await view.getByRole('tab',{name:'统计',exact:true}).click();
  }
  await expect(view.getByRole('tab')).toHaveCount(7);
  await expect(view.getByRole('tab').last()).toHaveText('设置');
  await expect(view.getByRole('button',{name:'刷新数据'})).not.toHaveClass(/v-btn--loading/);
  await page.screenshot({path:join(output,'overview.png'),animations:'disabled'});
  await view.getByRole('tab',{name:'聊天',exact:true}).click();
  await expect(view.getByText('天气很好 1',{exact:true})).toBeVisible();
  await expect(view.getByRole('complementary',{name:'数据筛选'})).toBeVisible();
  if (process.argv.includes('--table-sorting')) {
    for (const category of ['聊天','最近反应','话题','日记']) {
      await view.getByRole('tab',{name:category,exact:true}).click();
      for (const [title,key] of [[category === '最近反应' ? '规划原因' : '内容','headline'],['时间','timestamp'],['会话','conversation'],[category === '聊天' ? '发送者' : '状态','state']]) {
        const header = view.locator('thead th').filter({hasText:title});
        await header.getByRole('button',{name:new RegExp(title)}).click();
        await expect.poll(()=>page.evaluate(()=>window.calls.filter(call=>call.endpoint === 'records').at(-1)?.params.sort)).toBe(key);
        await expect.poll(()=>page.evaluate(()=>window.calls.filter(call=>call.endpoint === 'records').at(-1)?.params.order)).toBe('asc');
        await expect(header).toHaveAttribute('aria-sort','ascending');
        await header.click();
        await expect.poll(()=>page.evaluate(()=>window.calls.filter(call=>call.endpoint === 'records').at(-1)?.params.order)).toBe('desc');
        await expect(header).toHaveAttribute('aria-sort','descending');
      }
    }
    await view.getByRole('tab',{name:'聊天',exact:true}).click();
    console.log('Sortable headers switch the query column and both directions.');
  }
  if (process.argv.includes('--workspace-upgrade')) {
    await expect(view.locator('.session-name').first()).toHaveText('测试群');
    await expect(view.locator('.session-name').first()).toHaveAttribute('title','onebot · 群聊 · 测试群\nonebot:GroupMessage:123');
    const wrapper = view.locator('.records-table .v-table__wrapper');
    expect(await wrapper.evaluate(el=>el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    expect(await view.locator('.record-headline').last().evaluate(el=>el.scrollWidth > el.clientWidth)).toBeTruthy();
    await expect(view.locator('.record-headline').last()).toHaveAttribute('title',rows[1].headline);
    const separator = view.getByRole('separator',{name:'调整会话列宽',exact:true});
    const box = await separator.boundingBox();
    const initialWidth = await separator.evaluate(el=>el.closest('th').getBoundingClientRect().width);
    const calls = await page.evaluate(()=>window.calls.filter(call=>call.endpoint === 'records').length);
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 + 80,box.y + box.height / 2,{steps:8}); await page.mouse.up();
    await expect(separator).toHaveAttribute('aria-valuenow',String(Math.round(initialWidth+80)));
    await separator.press('ArrowLeft'); await expect(separator).toHaveAttribute('aria-valuenow',String(Math.round(initialWidth+80)-16));
    await separator.dblclick(); await expect(separator).toHaveAttribute('aria-valuenow','172');
    expect(await page.evaluate(()=>window.calls.filter(call=>call.endpoint === 'records').length)).toBe(calls);
    const edge = await separator.boundingBox();
    await page.mouse.move(edge.x+4,edge.y+4); await page.mouse.down();
    await page.mouse.move(edge.x+504,edge.y+4,{steps:8}); await page.mouse.up();
    expect(await wrapper.evaluate(el=>el.scrollWidth > el.clientWidth)).toBeTruthy();
    const actions = view.locator('tbody td.record-actions').first();
    await expect(actions).toHaveCSS('position','sticky');
    const right = (await actions.boundingBox()).x + (await actions.boundingBox()).width;
    const visibleRight = (await wrapper.boundingBox()).x + (await wrapper.boundingBox()).width;
    expect(Math.abs(right-visibleRight)).toBeLessThan(3);
    await wrapper.evaluate(el=>el.scrollLeft=el.scrollWidth);
    expect(Math.abs((await actions.boundingBox()).x+(await actions.boundingBox()).width-visibleRight)).toBeLessThan(3);
    await separator.dblclick();
    await wrapper.evaluate(el=>el.scrollLeft=0);
    expect(await view.locator('tbody td').first().evaluate(el=>parseFloat(getComputedStyle(el).paddingTop))).toBeGreaterThanOrEqual(12);
  }
  if (process.argv.includes('--filter-regression')) {
    await page.emulateMedia({reducedMotion:'no-preference'});
    const frame = page.frames().find(f=>f.url().includes('/view/'));
    const fieldHeight = await view.getByLabel('会话',{exact:true}).evaluate(input=>input.closest('.v-field').getBoundingClientRect().height);
    const recordCalls = await page.evaluate(()=>window.calls.filter(c=>c.endpoint === 'records').length);
    async function measureToggle(button) {
      const pending = frame.evaluate(() => new Promise(resolve => {
        document.querySelector('[aria-expanded]').addEventListener('click', () => {
          const start = performance.now(), samples = [];
          function sample() {
            samples.push({ms:performance.now()-start, left:document.querySelector('.records-list').getBoundingClientRect().left});
            if (performance.now()-start < 450) requestAnimationFrame(sample);
            else resolve(samples);
          }
          requestAnimationFrame(sample);
        }, {once:true});
      }));
      await button.click();
      return pending;
    }
    const collapse = await measureToggle(view.getByRole('button',{name:'隐藏筛选',exact:true}));
    const expand = await measureToggle(view.getByRole('button',{name:'显示筛选',exact:true}));
    const moved = samples=>samples.filter(s=>s.left > 30 && s.left < 310).length;
    console.log(JSON.stringify({fieldHeight, collapseIntermediateFrames:moved(collapse), expandIntermediateFrames:moved(expand), collapseStarts:collapse.find(s=>s.left < 319)?.ms, collapseEnds:collapse.find(s=>s.left < 30)?.ms}));
    expect(fieldHeight, 'Empty session selector should stay compact').toBeLessThanOrEqual(60);
    expect(moved(collapse), 'Collapsing should move the list through intermediate positions').toBeGreaterThan(2);
    expect(moved(expand), 'Expanding should move the list through intermediate positions').toBeGreaterThan(2);
    expect(collapse.find(s=>s.left < 30)?.ms, 'Collapsed layout should settle promptly').toBeLessThan(280);
    expect(await page.evaluate(()=>window.calls.filter(c=>c.endpoint === 'records').length)).toBe(recordCalls);
  }
  await view.getByRole('button',{name:'折叠筛选栏'}).click();
  await expect(view.getByRole('complementary',{name:'数据筛选'})).toBeHidden();
  await view.getByRole('button',{name:'显示筛选',exact:true}).click();
  await view.getByLabel('会话',{exact:true}).fill('GroupMessage:123');
  await view.getByRole('option',{name:/测试群/}).click();
  await view.getByLabel('会话',{exact:true}).fill('测试私聊');
  await view.getByRole('option',{name:/测试私聊/}).click();
  await view.getByLabel('会话',{exact:true}).press('Escape');
  await expect(view.getByRole('listbox')).toBeHidden();
  expect(await view.getByLabel('会话',{exact:true}).evaluate(input=>input.closest('.v-field').getBoundingClientRect().height)).toBeLessThanOrEqual(82);
  await view.getByLabel('会话',{exact:true}).click();
  await expect(view.getByRole('listbox')).toBeVisible();
  await page.screenshot({path:join(output,'session-picker.png'),animations:'disabled'});
  await view.getByRole('button',{name:'隐藏筛选',exact:true}).click();
  await expect(view.getByRole('listbox')).toBeHidden();
  await view.getByRole('button',{name:'显示筛选',exact:true}).click();
  await expect(view.locator('.session-name').first()).toHaveText('测试群');
  await page.screenshot({path:join(output,'filters.png'),animations:'disabled'});
  await view.getByRole('button',{name:'群聊',exact:true}).click();
  await expect(view.getByRole('button',{name:'群聊',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(view.getByRole('button',{name:'私聊',exact:true})).toHaveCSS('background-color','rgb(255, 255, 255)');
  await expect(view.getByRole('button',{name:'私聊',exact:true})).toHaveCSS('height','34px');
  await view.getByRole('button',{name:'发出回复',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.sessions)).toBe(JSON.stringify(['onebot:GroupMessage:123','onebot:FriendMessage:456']));
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.kind)).toBe('out');
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.chat_type)).toBe('group');
  await view.getByRole('button',{name:'重置筛选'}).click();
  await view.getByLabel('查看详情').first().click();
  await expect(view.getByRole('dialog')).toContainText('<script>window.UNSAFE = true</script>');
  const iframe = page.frames().find(f=>f.url().includes('/view/'));
  expect(await iframe.evaluate(()=>window.UNSAFE)).toBeUndefined();
  await iframe.evaluate(async () => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    await Promise.all(document.getAnimations().filter(a=>a.effect.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})));
  });
  await page.screenshot({path:join(output,'details.png')});
  await view.getByRole('button',{name:'关闭',exact:true}).click();
  await view.getByLabel('搜索关键词',{exact:true}).fill('天气');
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.q)).toBe('天气');
  await view.locator('thead th').filter({hasText:'时间'}).click();
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.order)).toBe('asc');
  await view.getByRole('checkbox').first().check();
  await view.getByRole('button',{name:'删除所选'}).click();
  await expect(view.getByRole('dialog')).toContainText('2 条');
  await view.getByRole('button',{name:'确认删除',exact:true}).click();
  await expect(view.getByText('已删除 2 条聊天记录',{exact:true})).toBeVisible();
  await view.getByRole('tab',{name:'设置',exact:true}).click();
  await expect(view.getByRole('heading',{name:'Controller 聊天行为规划与控制',exact:true})).toBeVisible();
  if (process.argv.includes('--scope-policy')) {
    const white = view.getByRole('region',{name:'会话白名单',exact:true});
    const black = view.getByRole('region',{name:'会话黑名单',exact:true});
    await expect(white).toBeVisible();
    await expect(black).toHaveCount(0);
    await white.getByLabel('选择已知会话',{exact:true}).click();
    await view.getByRole('option',{name:'测试群',exact:true}).click();
    await white.getByLabel('选择已知会话',{exact:true}).press('Escape');
    await white.getByLabel('补充会话 UMO',{exact:true}).fill('onebot:GroupMessage:789');
    await white.getByLabel('补充会话 UMO',{exact:true}).press('Enter');
    await white.getByLabel('补充会话 UMO',{exact:true}).press('Escape');
    await white.getByLabel('范围外会话处理方式',{exact:true}).click();
    await view.getByRole('option',{name:'监听（只记录，禁止 LLM）',exact:true}).click();
    await view.getByLabel('全部会话',{exact:true}).check();
    await expect(black).toBeVisible();
    await expect(white).toHaveCount(0);
    await black.getByLabel('选择禁用会话',{exact:true}).click();
    await view.getByRole('option',{name:'测试私聊',exact:true}).click();
    await black.getByLabel('选择禁用会话',{exact:true}).press('Escape');
    await black.getByLabel('补充禁用会话 UMO',{exact:true}).fill('onebot:GroupMessage:999');
    await black.getByLabel('补充禁用会话 UMO',{exact:true}).press('Enter');
    await black.getByLabel('补充禁用会话 UMO',{exact:true}).press('Escape');
    await black.getByLabel('会话处理方式',{exact:true}).click();
    await view.getByRole('option',{name:'丢弃（停止后续处理）',exact:true}).click();
    await page.screenshot({path:join(output,'scope-blacklist.png'),animations:'disabled'});
    await view.getByLabel('全部会话',{exact:true}).uncheck();
    await expect(white).toBeVisible();
    await expect(white).toContainText('测试群');
    await expect(white).toContainText('onebot:GroupMessage:789');
    await expect(white.getByText('监听（只记录，禁止 LLM）',{exact:true})).toBeVisible();
    await page.screenshot({path:join(output,'scope-whitelist.png'),animations:'disabled'});
    await view.getByRole('tab',{name:'统计',exact:true}).click();
    await view.getByRole('button',{name:'取消',exact:true}).click();
    await view.getByRole('tab',{name:'设置',exact:true}).click();
  }
  if (process.argv.includes('--workspace-upgrade')) {
    await expect(view.getByLabel('行为风格文本',{exact:true})).toHaveCount(0);
    await expect(view.getByRole('button',{name:/切换为[单双]列/})).toHaveCount(0);
    const cards = await view.locator('.settings-grid > section').evaluateAll(elements=>elements.map(el=>{const rect=el.getBoundingClientRect();return {left:rect.left,width:rect.width};}));
    expect(new Set(cards.map(card=>card.left)).size).toBe(1);
    expect(Math.max(...cards.map(card=>card.width))).toBeLessThanOrEqual(960);
    const nav = view.getByRole('complementary',{name:'设置快速导航'});
    await nav.getByRole('button',{name:'日志设置',exact:true}).click();
    await expect(view.getByRole('heading',{name:'日志设置',exact:true})).toBeInViewport();
    await nav.getByRole('button',{name:'行为规划',exact:true}).click();
    await expect(view.getByRole('heading',{name:'Controller 聊天行为规划与控制',exact:true})).toBeInViewport();
    const current = nav.getByRole('button',{name:'行为规划',exact:true});
    await expect(current).toHaveAttribute('aria-current','location');
    await expect(current).toHaveClass(/v-list-item--active/);
    await expect(current).toHaveCSS('color','rgb(60, 150, 202)');
    await page.emulateMedia({reducedMotion:'reduce'});
    await iframe.evaluate(()=>document.getElementById('setting-danger').scrollIntoView({block:'start',behavior:'instant'}));
    await expect(nav.getByRole('button',{name:'危险操作',exact:true})).toHaveAttribute('aria-current','location');
    await expect(current).not.toHaveAttribute('aria-current','location');
    await iframe.evaluate(()=>document.getElementById('setting-controller').scrollIntoView({block:'start',behavior:'instant'}));
    await expect(current).toHaveAttribute('aria-current','location');
    await nav.getByRole('button',{name:'主动发言',exact:true}).click();
    await expect(nav.getByRole('button',{name:'主动发言',exact:true})).toHaveAttribute('aria-current','location');
    await nav.getByRole('button',{name:'行为规划',exact:true}).click();
    await page.screenshot({path:join(output,'settings-single.png'),animations:'disabled'});
    await view.getByRole('button',{name:'收起设置导航',exact:true}).click();
    await view.getByRole('button',{name:'展开设置导航',exact:true}).click();
  }
  await expect(view.locator('.v-expansion-panels')).toHaveCount(0);
  await expect(view.getByLabel('消息调度模式：最短补偿等待（秒）')).toBeVisible();
  await view.getByLabel('工作模式',{exact:true}).click();
  await view.getByRole('option',{name:'概率抽样模式',exact:true}).click();
  await expect(view.getByLabel('消息调度模式：最短补偿等待（秒）')).toHaveCount(0);
  await view.getByLabel('机器人名称',{exact:true}).fill('测试机器人');
  await expect(view.getByRole('status')).toContainText('Humanization 配置尚未保存');
  await view.getByRole('tab',{name:'统计',exact:true}).click();
  await expect(view.getByRole('dialog')).toContainText('Humanization 配置有未保存的更改');
  await iframe.evaluate(async () => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    await Promise.all(document.getAnimations().filter(a=>a.effect.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})));
  });
  await page.screenshot({path:join(output,'unsaved-confirm.png')});
  await view.getByRole('button',{name:'继续编辑',exact:true}).click();
  await expect(view.getByLabel('机器人名称',{exact:true})).toHaveValue('测试机器人');
  await view.getByRole('tab',{name:'统计',exact:true}).click();
  await page.evaluate(()=>window.failSave=true);
  await view.getByRole('button',{name:'确定',exact:true}).click();
  await expect(view.getByText('模拟保存失败',{exact:true})).toBeVisible();
  await expect(view.getByRole('tab',{name:'设置',exact:true})).toHaveAttribute('aria-selected','true');
  await page.evaluate(()=>window.failSave=false);
  await view.getByRole('tab',{name:'统计',exact:true}).click();
  await view.getByRole('button',{name:'取消',exact:true}).click();
  await expect(view.getByText('配置与原生插件设置共用同一份文件。保存后重载插件生效，进行中的回复可能中断。',{exact:true})).toHaveCount(0);
  expect(await page.evaluate(()=>window.saved)).toBeNull();
  await view.getByRole('tab',{name:'设置',exact:true}).click();
  await expect(view.getByLabel('机器人名称',{exact:true})).toHaveValue('Bot');
  await view.getByLabel('机器人名称',{exact:true}).fill('测试机器人');
  await view.getByRole('tab',{name:'话题',exact:true}).click();
  await view.getByRole('button',{name:'确定',exact:true}).click();
  await expect(view.getByLabel('参与者或参与行为',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>window.saved.config.controller.robot_name)).toBe('测试机器人');
  await view.getByLabel('参与者或参与行为',{exact:true}).fill('用户');
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.participant)).toBe('用户');
  await view.getByRole('tab',{name:'日记',exact:true}).click();
  await expect(view.getByRole('combobox').filter({hasText:'消息覆盖'})).toBeVisible();
  await view.getByRole('tab',{name:'最近反应',exact:true}).click();
  await expect(view.getByRole('combobox').filter({hasText:'规划情绪'})).toBeVisible();
  await expect(view.getByText('结果未确认',{exact:true})).toBeVisible();
  const states = await view.locator('.decision-state').evaluateAll(elements=>elements.map(e=>{const cell=e.closest('td').getBoundingClientRect(),box=e.getBoundingClientRect();return box.top >= cell.top && box.bottom <= cell.bottom;}));
  expect(states).toEqual([true,true]);
  await page.screenshot({path:join(output,'decisions.png'),animations:'disabled'});
  await view.getByRole('tab',{name:'设置',exact:true}).click();
  await view.getByLabel('机器人名称',{exact:true}).fill('再次修改');
  await view.getByRole('button',{name:'保存并重载',exact:true}).click();
  await view.getByRole('button',{name:'确认保存',exact:true}).click();
  await expect(view.getByText('配置已保存，插件已重载',{exact:true})).toBeVisible();
  await expect(view.getByRole('dialog')).toBeHidden();
  expect(await page.evaluate(()=>window.saved.config.controller.robot_name)).toBe('再次修改');
  await view.getByLabel('聊天行为规划模型',{exact:true}).click();
  await expect(view.getByRole('option',{name:'DeepSeek',exact:true})).toBeVisible();
  await view.getByRole('tab',{name:'话题',exact:true}).click();
  await expect(view.getByRole('option',{name:'DeepSeek',exact:true})).toHaveCount(0);
  await expect(view.getByRole('button',{name:'保存并重载',exact:true})).toHaveCount(0);
  await expect(view.locator('.v-tabs')).toHaveCount(0);
  await view.getByRole('tab',{name:'设置',exact:true}).click();
  const danger = view.getByRole('region',{name:'危险操作区',exact:true});
  await expect(danger).toHaveCSS('color','rgb(244, 67, 54)');
  await expect(danger.getByRole('switch')).toHaveCount(0);
  await danger.getByRole('button',{name:'清除所有会话数据',exact:true}).click();
  await expect(view.getByRole('button',{name:'确认清除',exact:true})).toBeDisabled();
  await view.getByLabel('确认信息',{exact:true}).fill('incorrect');
  await expect(view.getByRole('button',{name:'确认清除',exact:true})).toBeDisabled();
  expect(await page.evaluate(()=>window.resetCount)).toBe(0);
  await view.getByRole('button',{name:'取消',exact:true}).click();
  await danger.getByRole('button',{name:'清除所有会话数据',exact:true}).click();
  await expect(view.getByLabel('确认信息',{exact:true})).toHaveValue('');
  await view.getByLabel('确认信息',{exact:true}).fill('CLEAR_ALL_HUMANIZATION_DATA');
  await view.getByRole('button',{name:'确认清除',exact:true}).click();
  await expect(view.getByText('已清除 2 个会话的数据，并为主模型开启空白对话',{exact:true})).toBeVisible();
  await expect(view.getByRole('dialog')).toBeHidden();
  expect(await page.evaluate(()=>window.resetCount)).toBe(1);
  await page.screenshot({path:join(output,'settings-danger.png'),animations:'disabled'});
  if (process.argv.includes('--workspace-upgrade')) {
    await view.getByRole('tab',{name:'提示词',exact:true}).click();
    const behavior = view.getByRole('region',{name:'行为规划提示词',exact:true});
    const text = behavior.getByLabel('行为风格文本',{exact:true});
    await expect(text).toHaveValue(promptDefaults.behavior);
    await expect(behavior.getByLabel('行为规划字数和Tokens估计')).toContainText(`${Array.from(promptDefaults.behavior).length} 字`);
    await expect(view.getByRole('button',{name:'保存并重载',exact:true})).toBeDisabled();
    await view.getByRole('tab',{name:'设置',exact:true}).click();
    await expect(view.getByRole('dialog')).toBeHidden();
    await view.getByRole('tab',{name:'提示词',exact:true}).click();
    await expect(text).toHaveValue(promptDefaults.behavior);
    await page.screenshot({path:join(output,'prompt-defaults.png'),animations:'disabled'});
    await expect(view.getByRole('region',{name:'危险操作区',exact:true})).toHaveCount(0);
    const expression = view.getByRole('region',{name:'表达风格提示词',exact:true});
    await expression.getByLabel('表达风格文本',{exact:true}).fill('更长的用户提示词。'.repeat(200));
    expect(Math.abs((await behavior.boundingBox()).height-(await expression.boundingBox()).height)).toBeLessThan(2);
    await page.screenshot({path:join(output,'prompt-grid.png'),animations:'disabled'});
    await expression.getByRole('button',{name:'使用默认',exact:true}).click();
    await behavior.getByRole('button',{name:'对比默认',exact:true}).click();
    await expect(view.getByLabel('系统默认提示词正文',{exact:true})).toHaveValue(promptDefaults.behavior);
    await expect(view.getByLabel('系统默认提示词正文',{exact:true})).toHaveAttribute('readonly');
    await expect(view.getByLabel('自定义提示词正文',{exact:true})).toHaveValue(promptDefaults.behavior);
    await expect(view.getByLabel('默认提示词字数和Tokens估计')).toContainText('估计');
    await expect(view.getByLabel('自定义提示词字数和Tokens估计')).toContainText('Tokens');
    await iframe.evaluate(async () => {
      await Promise.all(document.getAnimations().filter(a=>a.effect.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})));
    });
    await page.screenshot({path:join(output,'prompt-compare.png'),animations:'disabled'});
    const draft = '自定义规划\n额外短评';
    await view.getByLabel('自定义提示词正文',{exact:true}).fill(draft);
    await expect(text).toHaveValue(draft);
    await expect(behavior.getByLabel('行为规划字数和Tokens估计')).toContainText(`${Array.from(draft).length} 字`);
    await view.getByRole('button',{name:'显示差异',exact:true}).click();
    await expect(view.getByRole('region',{name:'提示词差异对比'})).toContainText('自定义规划');
    await expect(view.locator('.diff-add').first()).toHaveCSS('display','flex');
    await page.screenshot({path:join(output,'prompt-diff.png'),animations:'disabled'});
    await page.evaluate(()=>window.context(true));
    await expect(view.locator('.v-application')).toHaveClass(/v-theme--dark/);
    await expect(view.locator('.diff-add code').first()).toHaveCSS('color','rgb(232, 234, 237)');
    await page.screenshot({path:join(output,'prompt-diff-dark.png'),animations:'disabled'});
    await page.evaluate(()=>window.context(false));
    await expect(view.locator('.v-application')).toHaveClass(/v-theme--light/);
    await view.getByRole('button',{name:'返回编辑',exact:true}).click();
    await expect(view.getByLabel('自定义提示词正文',{exact:true})).toHaveValue(draft);
    await view.getByRole('button',{name:'关闭',exact:true}).click();
    await behavior.getByLabel('行为风格人格片段',{exact:true}).click();
    await view.getByLabel('搜索人格',{exact:true}).fill('测试人格');
    await view.getByRole('option',{name:/测试人格/}).click();
    await expect(view.getByRole('dialog')).toContainText('角色片段内容');
    await view.getByRole('button',{name:'确定',exact:true}).click();
    await expect(behavior).toContainText('已选人格正文');
    await behavior.getByRole('button',{name:'使用默认',exact:true}).click();
    await expect(text).toHaveValue(promptDefaults.behavior);
    await expect(view.getByRole('button',{name:'保存并重载',exact:true})).toBeDisabled();
    await text.fill('');
    await text.blur();
    await expect(text).toHaveValue(promptDefaults.behavior);
    await text.fill('保存用草稿');
    await view.getByRole('tab',{name:'统计',exact:true}).click();
    await expect(view.getByRole('dialog')).toContainText('Humanization 提示词有未保存的更改');
    await view.getByRole('button',{name:'继续编辑',exact:true}).click();
    await expect(view.getByRole('dialog')).toBeHidden();
    await expect(text).toHaveValue('保存用草稿');
    await page.screenshot({path:join(output,'prompts.png'),animations:'disabled'});
    await view.getByRole('button',{name:'保存并重载',exact:true}).click();
    await view.getByRole('button',{name:'确认保存',exact:true}).click();
    await expect(view.getByText('配置已保存，插件已重载',{exact:true})).toBeVisible();
    expect(await page.evaluate(()=>window.saved.config.prompts.behavior)).toBe('保存用草稿');
    expect(await page.evaluate(()=>window.saved.config.prompts.expression)).toBe('');
    await view.getByRole('tab',{name:'设置',exact:true}).click();
    await expect(view.getByRole('heading',{name:'日志设置',exact:true})).toBeVisible();
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.context(true));
  await expect(view.locator('.v-application')).toHaveClass(/v-theme--dark/);
  await expect(view.locator('.v-application')).toHaveCSS('color','rgb(232, 234, 237)');
  await expect(view.getByRole('heading',{name:'Humanization'})).toHaveCSS('color','rgb(232, 234, 237)');
  await page.screenshot({path:join(output,'mobile-settings.png')});
  expect(await iframe.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await expect(view.getByRole('button',{name:/切换为[单双]列/})).toHaveCount(0);
  if (process.argv.includes('--workspace-upgrade')) {
    await view.getByRole('tab',{name:'提示词',exact:true}).click();
    await view.getByRole('region',{name:'行为规划提示词',exact:true}).getByRole('button',{name:'对比默认',exact:true}).click();
    await expect(view.getByLabel('系统默认提示词正文',{exact:true})).toHaveValue(promptDefaults.behavior);
    expect(await iframe.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
    await view.getByRole('button',{name:'关闭提示词对比',exact:true}).click();
    await expect(view.getByRole('dialog')).toBeHidden();
  }
  await view.getByRole('tab',{name:'聊天',exact:true}).click();
  await expect(view.getByRole('complementary',{name:'数据筛选'})).toBeVisible();
  await page.screenshot({path:join(output,'mobile-filters.png'),animations:'disabled'});
  expect(await iframe.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.emulateMedia({reducedMotion:'reduce'});
  await view.getByRole('button',{name:'隐藏筛选',exact:true}).click();
  await expect(view.getByRole('complementary',{name:'数据筛选'})).toBeHidden();
  expect(errors).toEqual([]);
  console.log(`Sandbox bridge UI checks passed. Screenshots: ${output}`);
} catch (error) {
  if (page) await page.screenshot({path:join(output,'failure.png'),animations:'disabled'});
  console.error(JSON.stringify({browserErrors:errors,screenshot:join(output,'failure.png')}));
  throw error;
} finally {
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
