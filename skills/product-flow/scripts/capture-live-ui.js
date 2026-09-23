#!/usr/bin/env node
// ============================================================================
// 从「已上线的真实程序」抓取界面规格 + 截图，作为 Figma 高精度设计稿的还原基准。
// 用于 product-flow S7：有程序就别凭空画稿，先量真实的。
//
// 用法（Electron 应用）：
//   node capture-live-ui.js --root <目标仓库路径> [--out <产物目录>] [--port 9223] [--wait 7000]
//   也可用环境变量：CAPTURE_ROOT / CAPTURE_OUT
//   产物：<out>/spec-*.json（尺寸/颜色/字号/间距）+ <out>/*.png（截图）
//
// ⚠️ 路径必须由参数给。**旧版把 ROOT 与 OUT 都写死在源码里**（OUT 还指向另一个会话的
//    临时目录），而文件头只提醒了改 ROOT —— 换个项目跑，产物会静默落进一个死目录。
//    「本机专属」的东西不许藏在源码常量里，要么是参数，要么在文件头显式声明。
//
// ⚠️ 两条实战教训：
//   1) **只信 DOM 规格会翻车**——规格显示一切正常，画面可能被首启弹窗/遮罩整个盖住。
//      所以本脚本先关引导弹窗，且**必须人眼看一遍截图**再动手画。
//   2) 独立 --user-data-dir，否则和用户正在用的 app 撞单实例锁，端口不监听。
//
// 非 Electron 应用：把启动方式换成 Playwright/CDP 连到目标页面，
// 中间那段 SPEC 提取表达式可以原样复用。
// ============================================================================
'use strict';
const { spawn } = require('child_process');
const path = require('path'); const fs = require('fs'); const os = require('os');
function arg(name, envName, dflt) {
  const i = process.argv.indexOf('--' + name);
  if (i > -1 && process.argv[i + 1]) return process.argv[i + 1];
  if (envName && process.env[envName]) return process.env[envName];
  return dflt;
}
const ROOT = arg('root', 'CAPTURE_ROOT', null);
if (!ROOT) {
  console.error('UNABLE: 必须给 --root <目标仓库路径>（或设 CAPTURE_ROOT）。');
  console.error('  跑不了 ≠ 跑了没问题 —— 这里必须非零退出，不许静默用一个默认路径。');
  process.exit(2);
}
if (!fs.existsSync(path.join(ROOT, 'package.json'))) {
  console.error('UNABLE: ' + ROOT + ' 下没有 package.json，不像一个 Electron 仓库。');
  process.exit(2);
}
const WebSocket = require(path.join(ROOT, 'node_modules', 'ws'));
const OUT = arg('out', 'CAPTURE_OUT', path.join(ROOT, 'capture'));
fs.mkdirSync(OUT, { recursive: true });
const PORT = parseInt(arg('port', 'CAPTURE_PORT', '9223'), 10);
const sleep = ms => new Promise(r => setTimeout(r, ms));
let msgId = 0;
function cmd(ws, method, params, sid) {
  const id = ++msgId;
  return new Promise((res, rej) => {
    const to = setTimeout(() => { ws.off('message', on); rej(new Error('timeout ' + method)); }, 30000);
    const on = d => { const m = JSON.parse(d); if (m.id === id) { ws.off('message', on); clearTimeout(to); m.error ? rej(new Error(m.error.message)) : res(m.result); } };
    ws.on('message', on);
    const msg = { id, method, params: params || {} }; if (sid) msg.sessionId = sid;
    ws.send(JSON.stringify(msg));
  });
}
const ev = (ws, sid, e) => cmd(ws, 'Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }, sid).then(r => r.result && r.result.value);

(async () => {
  const ud = path.join(os.tmpdir(), 'pf-capture-userdata-' + path.basename(ROOT));
  const proc = spawn(path.join(ROOT, 'node_modules/.bin/electron'),
    ['.', `--remote-debugging-port=${PORT}`, '--remote-allow-origins=*', `--user-data-dir=${ud}`],
    { cwd: ROOT, env: { ...process.env }, stdio: ['ignore', 'pipe', 'pipe'] });
  let bws = null;
  const grab = s => { const m = s.match(/ws:\/\/[^\s]+\/devtools\/browser\/[a-f0-9-]+/i); if (m && !bws) bws = m[0]; };
  proc.stdout.on('data', d => grab(d.toString()));
  proc.stderr.on('data', d => grab(d.toString()));
  for (let i = 0; i < 60 && !bws; i++) await sleep(300);
  if (!bws) { proc.kill(); throw new Error('未拿到 ws endpoint'); }
  const ws = new WebSocket(bws, { origin: 'http://localhost', headers: { Host: 'localhost' } });
  await new Promise((r, j) => { ws.on('open', r); ws.on('error', j); });
  await cmd(ws, 'Target.setDiscoverTargets', { discover: true }); await sleep(1500);
  const { targetInfos } = await cmd(ws, 'Target.getTargets');
  const page = targetInfos.find(t => t.type === 'page');
  const { sessionId: sid } = await cmd(ws, 'Target.attachToTarget', { targetId: page.targetId, flatten: true });
  await cmd(ws, 'Runtime.enable', {}, sid); await cmd(ws, 'Page.enable', {}, sid);
  await sleep(7000); // 首屏 + 插件 + 照片加载

  // ---- 关掉首启引导/隐私弹窗（不关会盖住整个界面）----
  const dismiss = `(function(){
    var hit=0;
    var btns=Array.from(document.querySelectorAll('button,.btn,[role=button],a'));
    var t=btns.find(b=>/开始使用|知道了|继续|Get Started|Continue/.test((b.textContent||'').trim()));
    if(t){t.click();hit++;}
    document.querySelectorAll('.modal,.overlay,.onboarding,.privacy-modal,[class*=onboard],[class*=welcome]').forEach(function(e){
      var cs=getComputedStyle(e);
      if(cs.display!=='none'&&cs.visibility!=='hidden'&&e.getBoundingClientRect().width>300){e.remove();hit++;}
    });
    return hit;
  })()`;
  for (let i=0;i<3;i++){ const n = await ev(ws, sid, dismiss); console.log('  dismiss pass',i,'->',n); await sleep(1200); if(!n) break; }
  await sleep(2500);

  // ---- 提取设计规格（供 Figma 重建）----
  const SPEC = `(function(){
    const cs = el => el ? getComputedStyle(el) : null;
    const box = el => { if(!el) return null; const r = el.getBoundingClientRect(); return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}; };
    const pick = el => { const c = cs(el); if(!c) return null; return {
      bg:c.backgroundColor, color:c.color, font:c.fontFamily, size:c.fontSize, weight:c.fontWeight,
      radius:c.borderRadius, border:c.border, pad:c.padding, gap:c.gap, shadow:c.boxShadow }; };
    const q = s => document.querySelector(s);
    const out = { viewport:{w:innerWidth,h:innerHeight, dpr:devicePixelRatio},
      body: pick(document.body),
      regions:{}, samples:{} };
    const R = {sidebar:'.sidebar,#sidebar,nav.sidebar', header:'.titlebar,.header,header', content:'.content,#content,main,.grid-container', grid:'.photo-grid,.grid,#grid'};
    for (const [k,sel] of Object.entries(R)) { const el=q(sel); if(el){ out.regions[k]={box:box(el),style:pick(el)}; } }
    const navs = Array.from(document.querySelectorAll('.nav-item')).slice(0,14).map(e=>({text:(e.textContent||'').trim().slice(0,20), box:box(e), style:pick(e), plugin:e.dataset.plugin||e.dataset.view||''}));
    out.nav = navs;
    const cards = Array.from(document.querySelectorAll('.photo-card,.grid img,.thumb,.photo-item')).slice(0,6).map(e=>({tag:e.tagName, box:box(e), style:pick(e)}));
    out.cards = cards;
    out.title = document.title;
    out.counts = { photos: document.querySelectorAll('.photo-card,.grid img,.thumb,.photo-item').length, navItems: document.querySelectorAll('.nav-item').length };
    return JSON.stringify(out);
  })()`;
  const spec = await ev(ws, sid, SPEC);
  fs.writeFileSync(path.join(OUT, 'spec-library.json'), spec || '{}');
  console.log('SPEC:', (spec || '').slice(0, 400));

  const shot = async name => {
    const r = await cmd(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, sid);
    fs.writeFileSync(path.join(OUT, name + '.png'), Buffer.from(r.data, 'base64'));
    console.log('  shot ->', name + '.png');
  };
  await shot('01-library');

  // 切到几个核心视图
  const click = sel => ev(ws, sid, `(function(){var e=document.querySelector(${JSON.stringify(sel)}); if(e){e.click();return 1} return 0})()`);
  const views = [['.nav-item[data-view="library"]','01b-library'],['.nav-item[data-plugin="search"]','02-search'],['.nav-item[data-plugin="discover"]','03-discover']];
  for (const [sel,name] of views) { const ok = await click(sel); if (ok) { await sleep(2500); await shot(name); } else console.log('  跳过(无此项):', sel); }

  const navList = await ev(ws, sid, `JSON.stringify(Array.from(document.querySelectorAll('.nav-item')).map(e=>({t:(e.textContent||'').trim().slice(0,16),p:e.dataset.plugin||'',v:e.dataset.view||''})))`);
  fs.writeFileSync(path.join(OUT, 'navlist.json'), navList || '[]');
  console.log('NAV:', (navList||'').slice(0,500));

  ws.close(); proc.kill('SIGTERM');
  console.log('DONE ->', OUT);
  process.exit(0);
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
