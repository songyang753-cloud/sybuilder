#!/usr/bin/env node
/* 深度遍历引擎 —— 满足验收四条:
 *   ① 点遍每一个可点元素(全局 sig 去重,不设每屏预算上限)
 *   ② 每个可滚动容器 + window 滚到底(暴露懒加载项)再枚举
 *   ③ 进新页面就递归下钻,深度无上限(受 MAX_DEPTH/MAX_ACTIONS 安全阀保护)
 *   ④ reload + 路径重放复位,点完能回到原处不丢位
 * cursor 安全:全程 el.click()/scrollIntoView(纯 DOM 合成,连鼠标坐标都不用,绝不碰物理鼠标)。
 * 隐私:userContent(会话历史等)只记不点、文本已在 _cdp 判为 [user-content]。
 * 用法: node deep-walk.mjs <port> <outdir> [--depth 6] [--max 200] [--pick <s>]
 */
const fs = require('fs');
const { connect } = require('./_cdp.js');

const PORT = parseInt(process.argv[2]);
const OUT = process.argv[3];
const argN = (k, d) => { const i = process.argv.indexOf(k); return i >= 0 ? parseInt(process.argv[i + 1]) : d; };
const argS = (k, d) => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : d; };
const MAX_DEPTH = argN('--depth', 6);
const MAX_ACTIONS = argN('--max', 200);
const PICK = argS('--pick', '');

fs.mkdirSync(OUT + '/shots', { recursive: true });

// ⛔ 破坏性/会登出/外跳的标签,遍历时跳过(别在遍历里把用户登出/删数据)
const DESTRUCTIVE = /退出登录|登出|注销|退出账号|删除|卸载|清空|logout|sign ?out|delete|注销账号|解绑/i;

// 与 _cdp ENUM_JS 同源的 sig 计算(内联,供 click-by-sig 用)
const SIG_FN = `function __sig(e){
  const inH=!!e.closest('[class*=history],[class*=conversation],[class*=session],[class*=chat-list],[class*=recent],[class*=thread],[class*=inbox],[class*=doc-list],[class*=file-list],[data-testid*=history],ul>li>a');
  const raw=(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('placeholder')||'').trim().replace(/\\s+/g,' ');
  const txt=inH?'[user-content]':raw.slice(0,40);
  return [e.tagName,e.id||'',txt,inH?'':(e.getAttribute('aria-label')||''),(e.className&&typeof e.className==='string')?e.className.split(' ')[0]:''].join('|');
}`;

// 滚到底:每个可滚容器 + window 反复滚到 scrollHeight 直到稳定,再滚回顶(便于后续 enumerate/截图)
const SCROLL_JS = `(async()=>{
  const sc=[...document.querySelectorAll('*')].filter(e=>{const cs=getComputedStyle(e);return (cs.overflowY==='auto'||cs.overflowY==='scroll')&&e.scrollHeight>e.clientHeight+20;});
  for(const el of sc){let l=-1,g=0;while(g++<40){el.scrollTop=el.scrollHeight;await new Promise(r=>setTimeout(r,180));if(el.scrollTop===l)break;l=el.scrollTop;}el.scrollTop=0;}
  let l=-1,g=0;while(g++<40){window.scrollTo(0,document.body.scrollHeight);await new Promise(r=>setTimeout(r,180));if(scrollY===l)break;l=scrollY;}window.scrollTo(0,0);
  return true;})()`;

// 按 sig 点击:找到 sig 匹配的可点元素 → scrollIntoView → click。返回是否找到。
const clickJS = sig => `(()=>{${SIG_FN}
  const sel='a,button,[role=button],[role=tab],[role=menuitem],[onclick],[tabindex],input,select,textarea';
  for(const e of document.querySelectorAll(sel)){
    const r=e.getBoundingClientRect(); if(r.width<4||r.height<4)continue;
    if(__sig(e)===${JSON.stringify(sig)}){ try{e.scrollIntoView({block:'center'});}catch(_){}} else continue;
    try{e.click();}catch(_){return false;} return true;
  }
  return false;})()`;

const stateSig = els => els.map(e => e.sig).sort().join('¦');
const diffCount = (a, b) => { const A = new Set(a.split('¦')), B = new Set(b.split('¦')); let d = 0; for (const x of B) if (!A.has(x)) d++; for (const x of A) if (!B.has(x)) d++; return d; };
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
  for (const sig of pathSigs) { await cdp.evalJS(clickJS(sig)); await cdp.sleep(800); }
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
  const f = `${OUT}/shots/${String(++shotN).padStart(3, '0')}-L${depth}-${safe(lastTxt)}.png`;
  try { await cdp.shot(f); } catch (_) {}
  nodes.push({ depth, path: path.map(p => p.sig), pathTxt: path.map(p => p.txt), url: snap.url, title: snap.title,
    shot: f.split('/').pop(), els: snap.els.map(e => ({ sig: e.sig, txt: e.txt, nav: e.nav, userContent: e.userContent })) });
  let baseState = stateSig(snap.els);
  const inPageHops = path.filter(p => !p.nav).length;
  const children = [];
  const targets = snap.els.slice().sort((a, b) => (b.nav ? 1 : 0) - (a.nav ? 1 : 0)); // 导航优先
  let _seen = 0;
  for (const el of targets) {
    _seen++;
    if (actions >= MAX_ACTIONS) { skipped.push({ reason: 'action-cap', atPathTxt: path.map(p => p.txt), unprocessedSiblings: targets.length - _seen + 1 }); break; }
    if (el.userContent || DESTRUCTIVE.test(el.txt) || visited.has(el.sig)) continue;
    visited.add(el.sig); actions++;
    let ok = false; try { ok = await cdp.evalJS(clickJS(el.sig)); } catch (_) {}
    if (!ok) continue;
    await cdp.sleep(900);
    let cur; try { cur = await cdp.enumerate(); } catch (_) { continue; }
    const changed = stateSig(cur.els) !== baseState;
    const diff = changed ? diffCount(baseState, stateSig(cur.els)) : 0;
    if (changed && diff >= 4) {
      const nf = `${OUT}/shots/${String(++shotN).padStart(3, '0')}-L${depth + 1}-${safe(el.txt)}.png`;
      try { await cdp.shot(nf); } catch (_) {}
      transitions.push({ depth, fromPathTxt: path.map(p => p.txt), clickedTxt: el.txt, nav: el.nav, newShot: nf.split('/').pop() });
      if (depth < MAX_DEPTH && (el.nav || inPageHops < MAX_INPAGE)) children.push({ sig: el.sig, nav: el.nav, txt: el.txt });
      else skipped.push({ reason: depth >= MAX_DEPTH ? 'depth-cap' : 'inpage-cap', atPathTxt: path.map(p => p.txt), clickedTxt: el.txt }); // 有新态但因深度/inpage上限没入队
      await replay(path.map(p => p.sig));                 // 回到本页继续枚举兄弟
      try { const re = await reEnum(); baseState = stateSig(re.els); } catch (_) {}
    } else if (changed && diff > 0) {
      skipped.push({ reason: 'subthreshold-change', atPathTxt: path.map(p => p.txt), clickedTxt: el.txt, diff }); // 变了但<4阈值被当无变化,登记以防漏真页
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
    try { children = await visitPage(path); } catch (_) { continue; }
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
    // ⭐ 能不能声称"走全了":没撞任何上限 + 前沿清空 + 没有深度/子阈值丢弃。false=报告里必须写明未走全
    complete: !hitAction && !hitPages && queue.length === 0 && !skipped.some(s => ['depth-cap', 'subthreshold-change'].includes(s.reason)),
  };
  fs.writeFileSync(`${OUT}/deep-tree.json`, JSON.stringify({ nodes, transitions, skipped, coverage,
    stat: { pages: nodes.length, transitions: transitions.length, actions, shots: shotN, maxDepth: coverage.maxDepthReached } }, null, 2));
  console.log(JSON.stringify(coverage));
  cdp.close();
  process.exit(0);
})().catch(e => { console.error('ERR', e.message); process.exit(e.unable ? 2 : 1); });
