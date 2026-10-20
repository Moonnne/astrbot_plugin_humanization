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
const seed = {schema,config,revision:'initial',choices:{select_provider:[{title:'DeepSeek',value:'deepseek'}]}};
const harness = `<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">
<iframe title="Humanization" src="/view/" sandbox="allow-scripts allow-forms allow-downloads" style="width:100%;height:100vh;border:0"></iframe>
<script>
window.calls=[]; window.saved=null; window.deleted=[];
const settings=${JSON.stringify(seed).replaceAll('<','\\u003c')};
const rows=${JSON.stringify(rows).replaceAll('<','\\u003c')};
const frame=document.querySelector('iframe');
window.context = isDark => frame.contentWindow.postMessage({channel:'astrbot-plugin-page',kind:'context',context:{pluginName:'astrbot_plugin_humanization',pageName:'humanization',locale:'zh-CN',isDark}},'*');
window.addEventListener('message', event => {
  if(event.source!==frame.contentWindow || event.data.channel!=='astrbot-plugin-page') return;
  const m=event.data;
  if(m.kind==='ready') { window.context(false); return; }
  if(m.kind!=='request') return;
  window.calls.push(m); let data;
  if(m.endpoint==='overview') data={stats:{sessions:1,messages:2,topics:1,diaries:1,decisions:2,planned_replies:1},sessions:[{title:'onebot:GroupMessage:123',value:${JSON.stringify(scope)}}],timezone:'Asia/Shanghai'};
  if(m.endpoint==='records') data={items:rows.filter(r=>!window.deleted.includes(r.key)),total:rows.length-window.deleted.length};
  if(m.endpoint==='records/delete') { window.deleted.push(...m.body.keys); data={deleted:m.body.keys.length}; }
  if(m.endpoint==='settings') data=settings;
  if(m.endpoint==='settings/save') { window.saved=m.body; settings.config=m.body.config; settings.revision='saved'; data={saved:true,reloaded:true}; }
  frame.contentWindow.postMessage({channel:'astrbot-plugin-page',kind:'response',requestId:m.requestId,ok:true,data},'*');
});
</script></body></html>`;
const server = createServer(async (req,res) => {
  try {
    const url = req.url.split('?')[0];
    const files = {'/view/app.js':'app.js','/view/style.css':'style.css'};
    if (url === '/') { res.setHeader('Content-Type','text/html; charset=utf-8'); res.end(harness); }
    else if (url === '/view/') {
      res.setHeader('Content-Type','text/html; charset=utf-8');
      const html = await readFile(join(root,'views/humanization/index.html'),'utf8');
      res.end(html.replace('</head>', `<script>${sdk}</script></head>`));
    } else if (files[url]) {
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
  await expect(view.getByRole('tab')).toHaveCount(6);
  await expect(view.getByRole('button',{name:'刷新数据'})).not.toHaveClass(/v-btn--loading/);
  await page.screenshot({path:join(output,'overview.png'),animations:'disabled'});
  await view.getByRole('tab',{name:'聊天',exact:true}).click();
  await expect(view.getByText('天气很好 1',{exact:true})).toBeVisible();
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
  await view.getByLabel('搜索正文、用户或规划内容',{exact:true}).fill('天气');
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.q)).toBe('天气');
  await view.locator('thead th').filter({hasText:'时间'}).click();
  await expect.poll(()=>page.evaluate(()=>window.calls.at(-1)?.params?.order)).toBe('asc');
  await view.getByRole('checkbox').first().check();
  await view.getByRole('button',{name:'删除所选'}).click();
  await expect(view.getByRole('dialog')).toContainText('2 条');
  await view.getByRole('button',{name:'确认删除',exact:true}).click();
  await expect(view.getByText('已删除 2 条聊天记录',{exact:true})).toBeVisible();
  await view.getByRole('tab',{name:'设置',exact:true}).click();
  await view.getByRole('button',{name:'Controller 聊天行为规划与控制',exact:true}).click();
  await expect(view.getByLabel('消息调度模式：最短补偿等待（秒）')).toBeVisible();
  await view.getByLabel('工作模式',{exact:true}).click();
  await view.getByRole('option',{name:'概率抽样模式',exact:true}).click();
  await expect(view.getByLabel('消息调度模式：最短补偿等待（秒）')).toHaveCount(0);
  await view.getByLabel('机器人名称',{exact:true}).fill('测试机器人');
  await view.getByRole('tab',{name:'统计',exact:true}).click();
  await view.getByRole('tab',{name:'设置',exact:true}).click();
  await expect(view.getByLabel('机器人名称',{exact:true})).toHaveValue('测试机器人');
  await view.getByRole('button',{name:'保存并重载',exact:true}).click();
  await view.getByRole('button',{name:'确认保存',exact:true}).click();
  await expect(view.getByText('配置已保存，插件已重载',{exact:true})).toBeVisible();
  await expect(view.getByRole('dialog')).toBeHidden();
  expect(await page.evaluate(()=>window.saved.config.controller.robot_name)).toBe('测试机器人');
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.context(true));
  await expect(view.locator('.v-application')).toHaveClass(/v-theme--dark/);
  await expect(view.locator('.v-application')).toHaveCSS('color','rgb(232, 234, 237)');
  await expect(view.getByRole('heading',{name:'Humanization'})).toHaveCSS('color','rgb(232, 234, 237)');
  await page.screenshot({path:join(output,'mobile-settings.png')});
  expect(await iframe.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
  console.log(`Sandbox bridge UI checks passed. Screenshots: ${output}`);
} finally {
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
