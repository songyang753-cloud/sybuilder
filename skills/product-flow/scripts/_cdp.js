// CDP 落地契约 —— **可复用资产,不是纪律**。
//
// ═══ 为什么它必须是代码而不是文档 ═══
// `references/competitive-research.md:503` 早就一字不差写着「⛔ 别取 /json/list 的 t[0]」,
// 连 QClaw 的 #/sandbox-guard-bar 都点名了。2026-09-17 我重写遍历器时**照样踩进去**。
// 不是不够认真——写代码时我读的是任务和记忆,不会去检索一份 1300 行文档的第 503 行。
// ⭐ 同一次实测里,我抄 grab.sh 的部分(启动/挪虚拟屏/pkill)**一次通过**,
//    凭记忆重写的部分(WebSocket 处理/target 选择)**全踩坑**。
// ⇒ 落地细节以**可 require 的模块**存在才有约束力;以散文存在等于不存在。
//
// 用法: const {connect, enumerate, shot, KILL_HINT} = require('_cdp.js')
'use strict';

// 可点击元素枚举 —— **唯一正本**。probe 与真实枚举必须用它,⛔ 不许另写选择器：
// 实测用别的选择器探活会「probe 绿而枚举为 0」(loading 页有 3 个 [tabindex] 元素).
const ELEMENT_JS = `function __element(e) {
  const r=e.getBoundingClientRect(), cs=getComputedStyle(e);
  if(r.width<4||r.height<4||cs.visibility==='hidden'||cs.display==='none'||parseFloat(cs.opacity)===0) return null;
  const inHistory=!!e.closest('[class*=history],[class*=conversation],[class*=session],[class*=chat-list],'
    +'[class*=recent],[class*=thread],[class*=inbox],[class*=doc-list],[class*=file-list],[data-testid*=history],ul>li>a');
  const input=/^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName)||e.isContentEditable||e.getAttribute('role')==='textbox'||e.getAttribute('contenteditable')==='true';
  const label=(e.getAttribute('aria-label')||e.getAttribute('placeholder')||'');
  const raw=(input?label:(e.innerText||label)).trim().replace(/\\s+/g,' ');
  const txt=inHistory?'[user-content]':raw.slice(0,40);
  const sig=[e.tagName,e.id||'',txt,inHistory?'':label,
    typeof e.className==='string'?e.className.split(' ')[0]:''].join('|');
  const role=e.getAttribute('role')||'';
  const href=e.getAttribute('href')||'';
  return {sig,txt,tag:e.tagName,role,userContent:inHistory,disabled:!!e.disabled,
    safeNavigation:!input&&(role==='tab'||(e.tagName==='A'&&href.startsWith('#/'))),
    x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),
    nav:!inHistory&&!!e.closest('nav,[role=navigation],aside,[class*=sidebar],[class*=side-bar],[class*=menu]')};
}`;
const ENUM_JS = `(()=>{${ELEMENT_JS}
  const sel='a,button,[role=button],[role=tab],[role=menuitem],[onclick],[tabindex],input,select,textarea';
  const out=[],seen=new Set();
  for(const e of document.querySelectorAll(sel)){
    // 🚨 会话历史/文档列表/收件箱**长得像导航项**，抓进来就是把用户的私人内容落盘。
    //    实测：WorkBuddy 侧栏 42 个「导航项」里有 30 个是用户真实对话标题。
    //    ⇒ 在**取文本之前**就判定容器，落在历史/列表容器里的一律记为 [user-content]。
    const meta=__element(e); if(!meta) continue;
    const {sig}=meta;
    if(seen.has(sig)) continue; seen.add(sig);
    // ⛔ 历史项不算「导航项」：它是**用户数据**，不是产品自己宣告的能力。
    //    算进导航分母会让覆盖率被用户数据稀释（实测 42 个里 30 个是对话标题）。
    out.push(meta);
  }
  return {url:location.href,title:document.title,n:out.length,els:out};
})()`;

const sleep = ms => new Promise(r => setTimeout(r, ms));

/** 挪窗口到虚拟屏前**必须先确认虚拟屏存在**。
 *  🚨 2026-09-17 实测：DeskPad 没开时把窗口挪到 x=1500 ＝ 挪到**不存在的屏**上
 *     ⇒ 窗口不可见 ⇒ Electron 渲染节流 ⇒ DOM 枚举为 0。
 *  ⭐ 最危险的地方：它**伪装成产品结论**——「这个竞品界面是空的」。
 *     两家竞品连续 UNABLE 我才去查显示器数，差一点写进报告。
 *  ⇒ 先数屏，屏不够就**报 UNABLE 或退回主屏**，⛔ 不许挪到屏外继续采。 */
function assertVirtualScreen(minScreens = 2) {
  const { execFileSync } = require('child_process');
  let n = 1;
  try {
    const displays = execFileSync('system_profiler', ['SPDisplaysDataType'],
      { encoding: 'utf8', timeout: 10000 });
    n = (displays.match(/Resolution:/g) || []).length || 1;
  } catch (e) { /* 数不出来按 1 算，宁可报错也不静默挪到屏外 */ }
  if (n < minScreens) {
    const e = new Error(
      `UNABLE: 只检测到 ${n} 个显示器，虚拟屏未就绪。挪窗到屏外会让 Electron 节流、` +
      `DOM 枚举为 0，而那会**伪装成「竞品界面是空的」这个产品结论**。` +
      `⇒ 先 open -a DeskPad，或改为不挪窗（会占用户物理屏）。`);
    e.unable = true; throw e;
  }
  return n;
}

function rpc(getWs) {
  let id = 0;
  return (method, params = {}) => new Promise((res, rej) => {
    const i = ++id, ws = getWs();
    const cleanup = () => { clearTimeout(timer); ws.removeEventListener('message', h); ws.removeEventListener('close', closed); ws.removeEventListener('error', closed); };
    const closed = () => { cleanup(); rej(new Error('CDP connection closed: ' + method)); };
    // ⚠️ Node 原生 WebSocket 的 message 事件是 **MessageEvent**,要取 .data。
    //    直接 JSON.parse(事件对象) 得到 "[object MessageEvent]"。
    const h = ev => {
      let r;
      try { r = JSON.parse(ev.data); } catch (e) { cleanup(); rej(e); return; }
      if (r.id === i) { cleanup(); r.error ? rej(new Error(r.error.message)) : res(r.result); }
    };
    const timer = setTimeout(() => { cleanup(); rej(new Error('timeout ' + method)); }, 15000);
    ws.addEventListener('message', h);
    ws.addEventListener('close', closed); ws.addEventListener('error', closed);
    try { ws.send(JSON.stringify({ id: i, method, params })); } catch (e) { cleanup(); rej(e); }
  });
}

/** 连上**能干活**的 target。
 *  ⛔ 不按形态选(type==='page' / t[0])——那会选中守卫栏/加载页 overlay,
 *     枚举出 0 个元素,而脚本正常退出 0 ⇒ 得出「这个产品界面是空的」这个**错误结论**。
 *  ✅ 按能力选：能枚举到 ≥ minEls 个可点击控件的才算主窗口。轮询到超时就报 UNABLE。
 *  ⚠️ Electron 应用启动有路由序列(实测 QClaw: #/sandbox-guard-bar → #/init-loading → 主界面),
 *     所以必须**轮询**,不是连上第一个就用。 */
async function connect(port, { pick = '', minEls = 3, tries = 25, waitMs = 1500 } = {}) {
  let ws = null, target = null, send = rpc(() => ws), n = 0;
  const evalJS = async x => (await send('Runtime.evaluate',
    { expression: x, returnByValue: true, awaitPromise: true })).result.value;
  while (!target && n++ < tries) {
    let list = [];
    try { list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); } catch (e) { await sleep(waitMs); continue; }
    for (const c of list) {
      if (!c.webSocketDebuggerUrl) continue;
      if (pick && !((c.url || '').includes(pick) || (c.title || '').includes(pick))) continue;
      try {
        const w = new WebSocket(c.webSocketDebuggerUrl);
        await new Promise((r, j) => { w.addEventListener('open', r); w.addEventListener('error', j); setTimeout(() => j(new Error('open timeout')), 3000); });
        ws = w; await send('Runtime.enable');
        const probe = await evalJS(ENUM_JS);          // ⭐ 与真实枚举同源
        if (probe && probe.n >= minEls) { target = c; await send('Page.enable'); break; }
        w.close(); ws = null;
      } catch (e) { ws = null; }
    }
    if (!target) await sleep(waitMs);
  }
  if (!target) {
    const e = new Error(`UNABLE: ${tries} 次轮询未找到能枚举到 ≥${minEls} 个控件的 target —— 这是「没能测」,不是「测出来是空的」`);
    e.unable = true; throw e;
  }
  return { ws, target, send, evalJS, sleep,
           enumerate: () => evalJS(ENUM_JS),
           shot: async f => { const r = await send('Page.captureScreenshot', { format: 'png' });
                              require('fs').writeFileSync(f, Buffer.from(r.data, 'base64')); },
           close: () => ws && ws.close() };
}

/** 从 Info.plist 读**真实**可执行名。⛔ 不许拿 .app 的名字当二进制名。
 *  🚨 2026-09-17 实测：WorkBuddy 的 CFBundleExecutable 是 **`Electron`**，不是 `WorkBuddy`。
 *  拿应用名去起 ⇒ 起的是不存在的路径或 stub ⇒ `--remote-debugging-port` **没传给主进程**
 *  ⇒ 端口从没开过 ⇒ 连不上。而错误现象看起来像「这家竞品把调试端口关了」。 */
function resolveBinary(appName) {
  const { execFileSync } = require('child_process');
  try {
    const b = execFileSync('defaults', ['read', `/Applications/${appName}.app/Contents/Info.plist`, 'CFBundleExecutable'],
                       { encoding: 'utf8' }).trim();
    if (b) return b;
  } catch (e) { /* 读不到就退回目录扫描 */ }
  const fs2 = require('fs');
  const d = `/Applications/${appName}.app/Contents/MacOS`;
  const f = fs2.existsSync(d) ? fs2.readdirSync(d) : [];
  if (!f.length) { const e = new Error(`UNABLE: 找不到 ${appName} 的可执行文件`); e.unable = true; throw e; }
  return f[0];
}

/** 按 **pid** 回收，⛔ 不按名字模式。
 *  两个理由：① `pkill -f WorkBuddy` 杀不掉真名叫 `Electron` 的进程；
 *  ② `pkill -f Electron` 会**误杀用户正在用的所有 Electron 应用**。
 *  🚨 并且：验证「端口关了」之前必须先确认**端口开过**——
 *     端口从没开过时 curl 同样失败，会被读成「已回收」这个**假绿**。 */
async function reclaim(child, port, everOpened) {
  // Accept the actual ChildProcess returned by this run's spawn, never an arbitrary PID.
  const { ChildProcess } = require('child_process');
  if (!(child instanceof ChildProcess) || !child.pid)
    return {ok:false, why:'UNABLE: cleanup requires the owned ChildProcess handle'};
  if (child.exitCode === null) child.kill('SIGTERM');
  await sleep(1200);
  if (child.exitCode === null && child.signalCode === null)
    return {ok:false, why:'UNABLE: owned process has not exited after SIGTERM; port closure alone is not cleanup'};
  let alive = false;
  try { const r = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(1200) }); alive = r.ok; }
  catch (e) { alive = false; }
  if (!everOpened) return { ok: false, why: `端口 ${port} **从未开过** —— 「curl 失败」在这里不证明回收成功，是假绿` };
  return alive ? { ok: false, why: `端口 ${port} 仍在监听 —— 回收失败` } : { ok: true, why: `端口 ${port} 已关闭（开过且现已关）` };
}

// 回收：⛔ 只 open -a 重开会**复用旧实例**,调试端口关不掉。必须精确杀持有端口的 pid,
// 杀完还要验证端口真的没了——「声称清理」不等于「清理了」。
const KILL_HINT = '仅用本轮 spawn 返回的 ChildProcess 调用 reclaim；既有用户进程不自动回收。核验已打开过的端口已关闭。';

// 破坏性动作黑名单：⛔ **靠机器拦,不靠执行者记得避开**。
const DESTRUCTIVE = /(退出|登出|注销|删除|移除|清空|卸载|安装|付费|购买|升级|订阅|充值|发送|提交|支付|解绑|授权|保存|确认|sign\s*out|log\s*out|delete|remove|purchase|subscribe|upgrade|pay|send|submit|install|save|confirm|authorize)/i;
// AppCrawler 默认排噪：含 ≥2 位连续数字的文本(时间戳/计数/价格)每次看都像新状态。
const NOISE = /\d{2,}/;

function loadActionPolicy(file) {
  if (!file) return [];
  const raw = JSON.parse(require('fs').readFileSync(file, 'utf8'));
  if (!Array.isArray(raw.actions) || raw.actions.some(a => !a.url || !a.sig ||
      !a.authorizationRef || !['navigation', 'side-effect'].includes(a.kind)))
    throw new Error('UNABLE: action policy requires exact url/sig, kind and authorizationRef');
  return raw.actions;
}
function actionBlockReason(el, url, policy = []) {
  if (!el || el.userContent || el.disabled || !el.txt) return 'private-or-unavailable';
  const approval = policy.find(a => a.url === url && a.sig === el.sig && a.authorizationRef);
  if (DESTRUCTIVE.test(el.txt)) return approval?.kind === 'side-effect' ? '' : 'side-effect-needs-approval';
  return el.safeNavigation || approval ? '' : 'unclassified-action-needs-approval';
}
// DOM synthetic click rechecks identity, visibility and permission atomically; no stale coordinates.
function clickExpression(sig, policy = []) {
  return `(()=>{${ELEMENT_JS}
    const DESTRUCTIVE=${DESTRUCTIVE.toString()};
    const actionBlockReason=${actionBlockReason.toString()};
    const hits=[...document.querySelectorAll('a,button,[role=button],[role=tab],[role=menuitem],[onclick],[tabindex],input,select,textarea')]
      .filter(e=>{const m=__element(e);return m&&m.sig===${JSON.stringify(sig)}&&!actionBlockReason(m,location.href,${JSON.stringify(policy)});});
    if(hits.length!==1)return false;
    const e=hits[0];e.scrollIntoView({block:'center'});e.click();return true;
  })()`;
}

module.exports = { ENUM_JS, ELEMENT_JS, clickExpression, actionBlockReason, loadActionPolicy,
  connect, rpc, sleep, assertVirtualScreen, resolveBinary, reclaim, KILL_HINT, DESTRUCTIVE, NOISE };
