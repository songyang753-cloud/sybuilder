#!/usr/bin/env node
/* 深度遍历引擎 —— 满足验收四条:
 *   ① 点遍每一个可点元素(全局 sig 去重,不设每屏预算上限)
 *   ② 每个可滚动容器 + window 滚到底(暴露懒加载项)再枚举
 *   ③ 进新页面就递归下钻,深度无上限(受 MAX_DEPTH/MAX_ACTIONS 安全阀保护)
 *   ④ reload + 路径重放复位,点完能回到原处不丢位
 * cursor 安全:全程 el.click()/scrollIntoView(纯 DOM 合成,连鼠标坐标都不用,绝不碰物理鼠标)。
 * 隐私:userContent(会话历史等)只记不点、文本已在 _cdp 判为 [user-content]。
 * 用法: node deep-walk.cjs <port> <outdir> [--depth 6] [--max 200] [--pick <s>] [--actions policy.json]
 */
const fs = require('fs');
const { connect, clickExpression, actionBlockReason, loadActionPolicy } = require('./_cdp.js');

const PORT = parseInt(process.argv[2]);
const OUT = process.argv[3];
const argN = (k, d) => { const i = process.argv.indexOf(k); return i >= 0 ? parseInt(process.argv[i + 1]) : d; };
const argS = (k, d) => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : d; };
const MAX_DEPTH = argN('--depth', 6);
const MAX_ACTIONS = argN('--max', 200);
const PICK = argS('--pick', '');
const policy = loadActionPolicy(argS('--actions', ''));

fs.mkdirSync(OUT + '/shots', { recursive: true });

// 滚到底:每个可滚容器 + window 反复滚到 scrollHeight 直到稳定,再滚回顶(便于后续 enumerate/截图)
const SCROLL_JS = `(async()=>{
  const sc=[...document.querySelectorAll('*')].filter(e=>{const cs=getComputedStyle(e);return (cs.overflowY==='auto'||cs.overflowY==='scroll')&&e.scrollHeight>e.clientHeight+20;});
  for(const el of sc){let l=-1,g=0;while(g++<40){el.scrollTop=el.scrollHeight;await new Promise(r=>setTimeout(r,180));if(el.scrollTop===l)break;l=el.scrollTop;}el.scrollTop=0;}
  let l=-1,g=0;while(g++<40){window.scrollTo(0,document.body.scrollHeight);await new Promise(r=>setTimeout(r,180));if(scrollY===l)break;l=scrollY;}window.scrollTo(0,0);
  return true;})()`;

// 按 sig 点击:找到 sig 匹配的可点元素 → scrollIntoView → click。返回是否找到。
const clickJS = sig => clickExpression(sig, policy);

const stateSig = els => els.map(e => e.sig).sort().join('¦');
const pageState = snap => JSON.stringify([snap.url, snap.title, stateSig(snap.els)]);
const safe = s => (s || 'x').replace(/[^\w一-龥-]/g, '_').slice(0, 24);

let cdp, actions = 0, shotN = 0;
const visited = new Set();
const nodes = [];       // 每到达一个页面记一条:{depth,path,url,title,shot,els}
const transitions = []; // 每次导航记一条:{depth,fromPath,clickedSig,clickedTxt,newShot}
const skipped = [];     // ⭐ 覆盖回执:每次因上限/阈值没走的都登记,绝不静默(治"撞上限静默停")

async function reEnum() { await cdp.evalJS(SCROLL_JS); return cdp.enumerate(); }

async function home() {
  await cdp.evalJS('location.reload()');
  for (let i = 0; i < 20; i++) { await cdp.sleep(600); const r = await cdp.enumerate(); if (r && r.n >= 3) return r; }
  return cdp.enumerate();
}

async function replay(pathSigs) {
  await home();
  for (const sig of pathSigs) {
    if (!await cdp.evalJS(clickJS(sig))) throw new Error('replay-target-unavailable');
    await cdp.sleep(800);
  }
}

async function capture(depth, label, atPathTxt) {
  const f = `${OUT}/shots/${String(shotN + 1).padStart(3, '0')}-L${depth}-${safe(label)}.png`;
  try {
    await cdp.shot(f);
    if (!fs.existsSync(f) || !fs.statSync(f).size) throw new Error('empty screenshot');
    shotN++;
    return f.split('/').pop();
  } catch (_) {
    skipped.push({reason: 'screenshot-failure', atPathTxt});
    return null;
  }
}

// 非导航(chip/模式/下拉)最多再钻 MAX_INPAGE 级(防 chip 兔子洞);MAX_PAGES 页数上限
const MAX_INPAGE = argN('--inpage', 2);
const MAX_PAGES = argN('--pages', 70);

// 访问一个页面(path=[{sig,nav,txt}...]):重放到达 → 滚+截图+枚举+记录 → 点每个子元素发现导航,返回子路径清单(不递归,交给 BFS 队列)
async function visitPage(path) {
  await replay(path.map(p => p.sig));
  const snap = await reEnum();
  const depth = path.length + 1;
  const lastTxt = path.length ? path[path.length - 1].txt : 'home';
  const shot = await capture(depth, lastTxt, path.map(p => p.txt));
  nodes.push({ depth, path: path.map(p => p.sig), pathTxt: path.map(p => p.txt), url: snap.url, title: snap.title,
    shot, els: snap.els.map(e => ({ sig: e.sig, txt: e.txt, nav: e.nav, userContent: e.userContent })) });
  let baseState = pageState(snap);
  const inPageHops = path.filter(p => !p.nav).length;
  const children = [];
  const targets = snap.els.slice().sort((a, b) => (b.nav ? 1 : 0) - (a.nav ? 1 : 0)); // 导航优先
  let _seen = 0;
  for (const el of targets) {
    _seen++;
    if (actions >= MAX_ACTIONS) { skipped.push({ reason: 'action-cap', atPathTxt: path.map(p => p.txt), unprocessedSiblings: targets.length - _seen + 1 }); break; }
    if (el.userContent) continue;
    const key = snap.url + '|' + stateSig(snap.els) + '|' + el.sig;
    if (visited.has(key)) continue;
    const blocked = actionBlockReason(el, snap.url, policy);
    if (blocked) { skipped.push({reason: blocked, atPathTxt: path.map(p => p.txt), clickedTxt: el.txt}); continue; }
    visited.add(key); actions++;
    let ok = false; try { ok = await cdp.evalJS(clickJS(el.sig)); } catch (_) {}
    if (!ok) { skipped.push({reason: 'click-failure', atPathTxt: path.map(p => p.txt), clickedTxt: el.txt}); continue; }
    await cdp.sleep(900);
    let cur; try { cur = await cdp.enumerate(); } catch (_) {
      skipped.push({reason: 'enumeration-failure', atPathTxt: path.map(p => p.txt)}); continue;
    }
    const changed = pageState(cur) !== baseState;
    if (changed) {
      const newShot = await capture(depth + 1, el.txt, path.map(p => p.txt));
      transitions.push({ depth, fromPathTxt: path.map(p => p.txt), clickedTxt: el.txt, nav: el.nav, newShot });
      if (depth < MAX_DEPTH && (el.nav || inPageHops < MAX_INPAGE)) children.push({ sig: el.sig, nav: el.nav, txt: el.txt });
      else skipped.push({ reason: depth >= MAX_DEPTH ? 'depth-cap' : 'inpage-cap', atPathTxt: path.map(p => p.txt), clickedTxt: el.txt }); // 有新态但因深度/inpage上限没入队
      await replay(path.map(p => p.sig));                 // 回到本页继续枚举兄弟
      const re = await reEnum(); baseState = pageState(re);
    }
  }
  return children;
}

(async () => {
  cdp = await connect(PORT, { pick: PICK, minEls: 3 });
  const queue = [[]];                                     // BFS:逐层;先铺满 L1 再 L2…
  while (queue.length && actions < MAX_ACTIONS && nodes.length < MAX_PAGES) {
    const path = queue.shift();
    let children = [];
    try { children = await visitPage(path); } catch (_) {
      skipped.push({reason: 'page-failure', atPathTxt: path.map(p => p.txt)}); continue;
    }
    for (const c of children) queue.push(path.concat([c]));
  }
  // ⭐ 撞上限而未走完:队列里还剩的节点=没走的前沿,显式登记,绝不静默
  const hitAction = actions >= MAX_ACTIONS, hitPages = nodes.length >= MAX_PAGES;
  if (queue.length) for (const p of queue) skipped.push({ reason: hitAction ? 'action-cap' : hitPages ? 'page-cap' : 'queue-left', atPathTxt: p.map(x => x.txt) });
  const coverage = {
    pagesFound: nodes.length, transitions: transitions.length, actions, maxDepthReached: Math.max(0, ...nodes.map(n => n.depth)),
    frontierLeftUnexplored: queue.length, skipped: skipped.length,
    skippedByReason: skipped.reduce((a, s) => (a[s.reason] = (a[s.reason] || 0) + 1, a), {}),
    hitActionCap: hitAction, hitPageCap: hitPages, hitDepthCap: skipped.some(s => s.reason === 'depth-cap'),
    // 仅证明本次可枚举范围收敛，不证明产品全部功能已发现；正文覆盖仍需独立入口盘点。
    complete: nodes.length > 0 && !hitAction && !hitPages && queue.length === 0 && skipped.length === 0,
  };
  fs.writeFileSync(`${OUT}/deep-tree.json`, JSON.stringify({ nodes, transitions, skipped, coverage,
    stat: { pages: nodes.length, transitions: transitions.length, actions, shots: shotN, maxDepth: coverage.maxDepthReached } }, null, 2));
  console.log(JSON.stringify(coverage));
  cdp.close();
  process.exit(coverage.complete ? 0 : nodes.length ? 1 : 2);
})().catch(e => { console.error('ERR', e.message); process.exit(e.unable ? 2 : 1); });
