#!/usr/bin/env node
// ============================================================================
// 从「已上线的真实程序」抓取界面规格 + 截图，作为 Figma 高精度设计稿的还原基准。
// 用于 product-flow S7：有程序就别凭空画稿，先量真实的。
//
// 用法（Electron 应用）：
//   node capture-live-ui.js --root <目标仓库路径> [--out <新产物目录>] [--target-url <精确页面>] [--actions <策略.json>]
//   也可用环境变量：CAPTURE_ROOT / CAPTURE_OUT
//   产物：<out>/spec-*.json（尺寸/颜色/字号/间距）+ <out>/*.png（截图）
//
// ⚠️ 路径必须由参数给。**旧版把 ROOT 与 OUT 都写死在源码里**（OUT 还指向另一个会话的
//    临时目录），而文件头只提醒了改 ROOT —— 换个项目跑，产物会静默落进一个死目录。
//    「本机专属」的东西不许藏在源码常量里，要么是参数，要么在文件头显式声明。
//
// ⚠️ 两条实战教训：
//   1) **只信 DOM 规格会翻车**——规格显示一切正常，画面可能被首启弹窗/遮罩整个盖住。
//      所以遇到引导/授权弹窗必须停下交由用户处理，且人眼看真实截图，不改 DOM。
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
if (process.platform === 'win32') { console.error('UNABLE: capture cleanup requires POSIX'); process.exit(2); }
if (!ROOT) {
  console.error('UNABLE: 必须给 --root <目标仓库路径>（或设 CAPTURE_ROOT）。');
  console.error('  跑不了 ≠ 跑了没问题 —— 这里必须非零退出，不许静默用一个默认路径。');
  process.exit(2);
}
if (!fs.existsSync(path.join(ROOT, 'package.json'))) {
  console.error('UNABLE: ' + ROOT + ' 下没有 package.json，不像一个 Electron 仓库。');
  process.exit(2);
}
const OUT = arg('out', 'CAPTURE_OUT', path.join(ROOT, 'capture'));
const PORT = 0; // OS-assigned, private profile; never attach to an arbitrary fixed listener.
const { ELEMENT_JS, clickExpression, loadActionPolicy } = require('./_cdp.js');
let WebSocket, policy;
try {
  WebSocket = require(path.join(path.resolve(ROOT), 'node_modules', 'ws'));
  policy = loadActionPolicy(arg('actions', 'CAPTURE_ACTIONS', ''));
  fs.mkdirSync(OUT, { mode: 0o700 }); // Refuse existing evidence; never overwrite prior capture.
} catch (error) { console.error('UNABLE: capture preflight: ' + error.message); process.exit(2); }
const sleep = ms => new Promise(r => setTimeout(r, ms));
let msgId = 0;
function cmd(ws, method, params, sid) {
  const id = ++msgId;
  return new Promise((res, rej) => {
    if (ws.readyState !== WebSocket.OPEN) return rej(new Error('UNABLE: CDP is not open'));
    const cleanup = () => { ws.off('message', on); ws.off('close', close); clearTimeout(to); };
    const close = () => { cleanup(); rej(new Error('UNABLE: CDP disconnected')); };
    const to = setTimeout(() => { cleanup(); rej(new Error('timeout ' + method)); }, 30000);
    const on = d => {
      try { const m = JSON.parse(d); if (m.id === id) { cleanup(); m.error ? rej(new Error('CDP request failed')) : res(m.result); } }
      catch { cleanup(); rej(new Error('UNABLE: invalid CDP response')); }
    };
    ws.on('message', on);
    ws.once('close', close);
    const msg = { id, method, params: params || {} }; if (sid) msg.sessionId = sid;
    try { ws.send(JSON.stringify(msg)); }
    catch (error) { cleanup(); rej(error); }
  });
}
const ev = (ws, sid, e) => cmd(ws, 'Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }, sid).then(r => {
  if (!r?.result || r.exceptionDetails || r.result.subtype === 'error') throw new Error('UNABLE: page evaluation failed');
  return r.result.value;
});

(async () => {
  const ud = fs.mkdtempSync(path.join(os.tmpdir(), 'pf-capture-'));
  const proc = spawn(path.join(ROOT, 'node_modules/.bin/electron'),
    ['.', `--remote-debugging-port=${PORT}`, '--remote-debugging-address=127.0.0.1', '--remote-allow-origins=http://localhost', `--user-data-dir=${ud}`],
    { cwd: ROOT, env: { ...process.env }, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] });
  let ws, launchError;
  proc.on('error', error => { launchError = error; });
  const stop = () => { launchError = new Error('UNABLE: capture interrupted or deadline exceeded'); ws?.terminate(); };
  process.once('SIGTERM', stop); process.once('SIGINT', stop);
  const deadline = setTimeout(stop, 180000);
  try {
  let bws = null;
  const grab = s => { const m = s.match(/ws:\/\/[^\s]+\/devtools\/browser\/[a-f0-9-]+/i); if (m && !bws) bws = m[0]; };
  proc.stdout.on('data', d => grab(d.toString()));
  proc.stderr.on('data', d => grab(d.toString()));
  for (let i = 0; i < 60 && !bws; i++) { if (launchError) throw launchError; await sleep(300); }
  if (launchError) throw launchError;
  if (!bws) { proc.kill(); throw new Error('未拿到 ws endpoint'); }
  const endpoint = new URL(bws);
  if (endpoint.protocol !== 'ws:' || endpoint.hostname !== '127.0.0.1') throw new Error('UNABLE: non-loopback CDP endpoint');
  ws = new WebSocket(bws, { origin: 'http://localhost', headers: { Host: 'localhost' } });
  ws.on('error', error => { launchError = error; ws.terminate(); });
  await new Promise((r, j) => {
    const timer = setTimeout(() => j(new Error('UNABLE: CDP connection timed out')), 15000);
    ws.once('open', () => { clearTimeout(timer); r(); });
    ws.once('error', e => { clearTimeout(timer); j(e); });
    ws.once('close', () => { clearTimeout(timer); j(new Error('UNABLE: connection closed')); });
  });
  await cmd(ws, 'Target.setDiscoverTargets', { discover: true }); await sleep(1500);
  const { targetInfos } = await cmd(ws, 'Target.getTargets');
  const targetUrl = arg('target-url', 'CAPTURE_TARGET_URL', '');
  const pages = targetInfos.filter(t => t.type === 'page' && (!targetUrl || t.url === targetUrl));
  if (pages.length !== 1) throw new Error('UNABLE: ambiguous page; specify --target-url');
  const page = pages[0];
  const { sessionId: sid } = await cmd(ws, 'Target.attachToTarget', { targetId: page.targetId, flatten: true });
  await cmd(ws, 'Runtime.enable', {}, sid); await cmd(ws, 'Page.enable', {}, sid);
  await sleep(7000); // 首屏 + 插件 + 照片加载

  // Preserve real UI. Login, permission, policy and onboarding walls require user action.
  const blocked = await ev(ws, sid, `Array.from(document.querySelectorAll('[role=dialog],.modal,.privacy-modal,.onboarding')).some(e=>e.getBoundingClientRect().width>0)`);
  if (blocked) throw new Error('UNABLE: visible dialog; user must resolve authorization/onboarding before capture');
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
  console.log('Specifications saved privately; review before export.');

  const shot = async name => {
    const r = await cmd(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, sid);
    fs.writeFileSync(path.join(OUT, name + '.png'), Buffer.from(r.data, 'base64'));
    console.log('  shot ->', name + '.png');
  };
  await shot('01-library');

  // 切到几个核心视图
  const click = async sel => {
    const sig = await ev(ws, sid, `(()=>{${ELEMENT_JS}; const e=document.querySelector(${JSON.stringify(sel)}); return e ? __element(e)?.sig : null;})()`);
    return sig ? ev(ws, sid, clickExpression(sig, policy)) : 0;
  };
  const views = [['.nav-item[data-view="library"]','01b-library'],['.nav-item[data-plugin="search"]','02-search'],['.nav-item[data-plugin="discover"]','03-discover']];
  for (const [sel,name] of views) { const ok = await click(sel); if (ok) { await sleep(2500); await shot(name); } else console.log('  跳过(无此项):', sel); }

  const navList = await ev(ws, sid, `JSON.stringify(Array.from(document.querySelectorAll('.nav-item')).map(e=>({t:(e.textContent||'').trim().slice(0,16),p:e.dataset.plugin||'',v:e.dataset.view||''})))`);
  fs.writeFileSync(path.join(OUT, 'navlist.json'), navList || '[]');
  console.log('Navigation evidence saved privately; review before any upload.');

  console.log('DONE ->', OUT);
  } finally {
    clearTimeout(deadline); process.off('SIGTERM', stop); process.off('SIGINT', stop);
    try { ws?.close(); } catch {}
    if (proc.pid) {
      try { process.platform === 'win32' ? proc.kill() : process.kill(-proc.pid, 'SIGTERM'); } catch {}
      await sleep(150);
      try { process.platform === 'win32' ? proc.kill('SIGKILL') : process.kill(-proc.pid, 'SIGKILL'); } catch {}
    }
    fs.rmSync(ud, { recursive: true, force: true });
  }
})().catch(e => { console.error('UNABLE:', e.message); process.exit(2); });
