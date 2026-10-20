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
const scope = JSON.stringify(['onebot', '999', 'group', '123']);
const rows = [1, 2].map(id => ({ id, key:JSON.stringify([scope,id]), scope,
  timestamp:1792346400, conversation:'onebot:GroupMessage:123', headline:`天气很好 ${id}`,
  text:`天气很好 ${id}`, sender_name:'测试用户', sender_id:'42', direction:'in',
  segments:[{type:'text',text:'<script>window.UNSAFE = true</script>'},{type:'poke',target_id:'999'}],
}));
const records = {
  messages:rows,
  decisions:rows.map((row,index)=>({...row, headline:'根据当前话题简短回应', outcome:index ? 'processed' : 'unconfirmed', decision_json:{reply:true,emotion:{primary:'SELF_CONSCIOUS',intensity:1},plan:{guidance:'简短接话'}}})),
  topics:rows.map(row=>({...row,day:'2026-10-19',topic:'讨论天气',interact:['测试用户分享天气'],reply:'我简短回应',reaction:'未见明确反应'})),
  diaries:rows.map(row=>({...row,day:'2026-10-19',sealed:0,topic_count:2,coverage_gap:0,topics:[]})),
};
const seed = {schema,config,revision:'initial',reset_confirmation:'CLEAR_ALL_HUMANIZATION_DATA',choices:{select_provider:[{title:'DeepSeek',value:'deepseek'}]}};
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
try {
  const page = await browser.newPage({viewport:{width:1280,height:960}, reducedMotion:'reduce'});
  const errors = [];
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
  await expect(view.getByRole('tab')).toHaveCount(6);
  await expect(view.getByRole('button',{name:'刷新数据'})).not.toHaveClass(/v-btn--loading/);
  await page.screenshot({path:join(output,'overview.png'),animations:'disabled'});
  await view.getByRole('tab',{name:'聊天',exact:true}).click();
  await expect(view.getByText('天气很好 1',{exact:true})).toBeVisible();
  await expect(view.getByRole('complementary',{name:'数据筛选'})).toBeVisible();
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
  await expect(view.getByText('测试群',{exact:true}).first()).toBeVisible();
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
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.context(true));
  await expect(view.locator('.v-application')).toHaveClass(/v-theme--dark/);
  await expect(view.locator('.v-application')).toHaveCSS('color','rgb(232, 234, 237)');
  await expect(view.getByRole('heading',{name:'Humanization'})).toHaveCSS('color','rgb(232, 234, 237)');
  await page.screenshot({path:join(output,'mobile-settings.png')});
  expect(await iframe.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await view.getByRole('tab',{name:'聊天',exact:true}).click();
  await expect(view.getByRole('complementary',{name:'数据筛选'})).toBeVisible();
  await page.screenshot({path:join(output,'mobile-filters.png'),animations:'disabled'});
  expect(await iframe.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.emulateMedia({reducedMotion:'reduce'});
  await view.getByRole('button',{name:'隐藏筛选',exact:true}).click();
  await expect(view.getByRole('complementary',{name:'数据筛选'})).toBeHidden();
  expect(errors).toEqual([]);
  console.log(`Sandbox bridge UI checks passed. Screenshots: ${output}`);
} finally {
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
