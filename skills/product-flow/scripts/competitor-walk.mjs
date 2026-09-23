// 竞品遍历器 —— S2 的标准工具。广度按 AppCrawler 模型,深度按 GUI-explorer 的 transition 模型。
//
// ⛔ 落地细节一律走 _cdp.js(M11:以散文存在的教训等于不存在)。
// 🚨 光标安全:只用 CDP 合成事件(Input.dispatchMouseEvent),⛔ 绝不物理鼠标——不劫用户光标。
// 用法: node competitor-walk.mjs <port> <outdir> [--pick <s>] [--steps 40] [--sub 4]
// 退出码: 0=遍历完成 2=UNABLE(连不上/没有能干活的 target)
//
// 2026-09-17 深化(治 v8「只到一级导航」浅层):
//   ① 每次点击前**重新枚举**拿当前坐标(旧版点完用基线旧坐标→点空)
//   ② nav 逐屏遍历 + 每屏再点若干**新子元素**(depth-2,走进多步旅程)
//   ③ 预算加大;barren 只由子元素触发,nav 必逐个走完
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const require = createRequire(import.meta.url);
const { connect, DESTRUCTIVE, NOISE } = require('./_cdp.js');

const A = process.argv.slice(2);
const PORT = A[0], OUT = A[1];
const pick = A.includes('--pick') ? A[A.indexOf('--pick') + 1] : '';
const steps = A.includes('--steps') ? parseInt(A[A.indexOf('--steps') + 1]) : 40;
const subK = A.includes('--sub') ? parseInt(A[A.indexOf('--sub') + 1]) : 4;

// --help：只显示帮助（文件头注释）并退 0，⛔ 必须在 connect() 之前——求助不该去连浏览器
if (A.includes('--help') || A.includes('-h')) {
  console.log(fs.readFileSync(new URL(import.meta.url), 'utf8').split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}

const c = await connect(PORT, { pick }).catch(e => { console.error(e.message); process.exit(2); });
fs.mkdirSync(path.join(OUT, 'shots'), { recursive: true });

const base = await c.enumerate();
fs.writeFileSync(path.join(OUT, 'dom-base.json'), JSON.stringify(base, null, 1));
await c.shot(path.join(OUT, 'shots', '00-base.png'));
process.stderr.write(`  基线: ${base.n} 控件 (导航 ${base.els.filter(e => e.nav).length}) @ ${base.url.slice(-34)}\n`);

const clicked = new Set(), transitions = [], routes = new Set([base.url]);
let step = 0;
const sig3 = e => e.sig.split('|').slice(0, 3).join('|');
const clickable = els => els.filter(e => e.txt && !DESTRUCTIVE.test(e.txt) && !NOISE.test(e.txt));

// 合成点击 + 前后差 = 这个控件真正做了什么(GUI-explorer 核心)。⛔ 只用 Input.dispatchMouseEvent。
async function clickAndDiff(el, tag) {
  const before = await c.enumerate();
  try {
    await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: el.x, y: el.y, button: 'left', clickCount: 1 });
    await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: el.x, y: el.y, button: 'left', clickCount: 1 });
  } catch (e) { return null; }
  await c.sleep(1400);
  const after = await c.enumerate();
  const bs = new Set(before.els.map(e => e.sig)), as = new Set(after.els.map(e => e.sig));
  const appeared = [...as].filter(x => !bs.has(x)), gone = [...bs].filter(x => !as.has(x));
  routes.add(after.url);
  const changed = appeared.length || gone.length || after.url !== before.url || after.title !== before.title;
  step++;
  const f = `${String(step).padStart(2, '0')}-${tag}-${el.txt.replace(/[^\w一-龥]/g, '_').slice(0, 16)}.png`;
  await c.shot(path.join(OUT, 'shots', f));
  transitions.push({ step, depth: tag, clicked: el.txt, nav: !!el.nav, shot: f,
    urlBefore: before.url, urlAfter: after.url, titleAfter: after.title,
    appeared: appeared.slice(0, 20), gone: gone.slice(0, 8),
    counts: { before: before.n, after: after.n, appeared: appeared.length, gone: gone.length } });
  process.stderr.write(`  ${step}.[${tag}] ${el.txt.slice(0, 18)} → +${appeared.length}/-${gone.length}${after.url !== before.url ? ' [路由变]' : ''}\n`);
  return { after, changed };
}

// ① nav 逐屏(导航是产品自己宣告的能力清单,漏一个=漏一块产品)——必逐个走完,不受 barren 限制
const navQueue = clickable(base.els).sort((a, b) => (b.nav ? 1 : 0) - (a.nav ? 1 : 0));
for (const navEl of navQueue) {
  if (step >= steps) break;
  const key = sig3(navEl);
  if (clicked.has(key)) continue;
  clicked.add(key);
  // ② 点 nav 前重新枚举拿当前坐标 + 定位同一控件(旧版用基线旧坐标是浅层主因)
  const cur = await c.enumerate();
  const fresh = clickable(cur.els).find(e => sig3(e) === key) || navEl;
  const r = await clickAndDiff(fresh, navEl.nav ? 'nav' : 'top');
  if (!r || !r.changed) continue;                 // 这一屏没变化,不深挖
  // ③ depth-2:进了新屏 → 点该屏里若干**新出现**的子元素,走进多步旅程
  let sub = 0, barren = 0;
  for (const subEl of clickable(r.after.els)) {
    if (step >= steps || sub >= subK || barren >= 2) break;
    const sk = sig3(subEl);
    if (clicked.has(sk)) continue;                // 全局去重(nav 已点过的不重复)
    clicked.add(sk); sub++;
    const rr = await clickAndDiff(subEl, 'sub');
    barren = (rr && rr.changed) ? 0 : barren + 1;
  }
}

const navTotal = base.els.filter(e => e.nav).length;
const cov = { navTotal, clickTotal: base.n, visited: step, routes: routes.size,
  navVisited: transitions.filter(t => t.nav).length,
  subVisited: transitions.filter(t => t.depth === 'sub').length,
  navCoverage: +(transitions.filter(t => t.nav).length / Math.max(navTotal, 1)).toFixed(2),
  productive: transitions.filter(t => t.counts.appeared || t.counts.gone || t.urlAfter !== t.urlBefore).length };
fs.writeFileSync(path.join(OUT, 'transitions.json'), JSON.stringify({ coverage: cov, transitions }, null, 1));
console.log(JSON.stringify(cov));
c.close();
