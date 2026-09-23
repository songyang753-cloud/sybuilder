#!/usr/bin/env node
// ============================================================================
// 死按钮门禁 —— 「这份 demo 到底点不点得动」的机器判据。
//
// ═══ 为什么需要它 ═══
// SKILL.md 的 S6「自动验收」表把**死按钮列在第一条**，理由写得很清楚：
//   「演示时没人会把每个按钮都点一遍，恰恰是没点的那个在评审现场被点」。
// 而这张表的 5 项（死按钮 · 控制台 · 资源 · 关键路径 · 状态可触发）
// **一项都没有可执行实现**，全是散文。`browser-audit.mjs` 的 10 项检查
// 全是排版/对比度/命中区/焦点环/溢出 —— **零行为检查**。
//
// ⭐ 2026-09-02 实测代价：`agent-workbench` 的 S6 产物
//   28 场景 / 75 个可点元素 / **70 个点了毫无反应（93%）**，
//   而 `browser-audit.mjs` 对同一份文件判 **9 通过 / 1 失败**，
//   唯一的失败是「强调色占界面 1.1%」。**门禁全绿，产物点不动。**
//
// ═══ 诚实边界（这道门证明不了什么）═══
// ⚠️ 程序化 `.click()` **只能证伪，不能证真**。它派发的是非可信事件，
//    不触发浏览器的默认交互链（真实点击才暴露过「授权弹窗从未渲染」那类问题）。
//    所以本门是**下界**：它红了一定有问题；它绿了**不等于**关键路径真的走得通。
//    关键路径仍必须真人点一遍，两者不互相替代。
// ⚠️ 本门不判「点了以后对不对」，只判「点了以后有没有发生任何事」。
//
// 用法：
//   node dead-click-gate.mjs <file.html> [--json] [--max-dead-pct 0]
//                            [--viewport 1440x900] [--min-elements 3] [--list] [--exhaustive]
//   node dead-click-gate.mjs --self-test
// 退出码：0=通过  1=不通过  2=跑不了（找不到浏览器/文件不存在/**页面上根本没有可交互元素**）
// ============================================================================
import { existsSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
import { evalInPage, browserPreflight } from './_browser.mjs';
import { rejectUnknown } from './_argv.mjs';

// 登记册#1：--help 只显示帮助（文件头注释）并退 0
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  const _src = (await import('node:fs')).readFileSync(new URL(import.meta.url), 'utf8');
  console.log(_src.split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}

// ---------------------------------------------------------------- 页面内探针
// 三种遍历模型，按优先级：
//   ① 路由模型（新形态）：页面自己暴露 window.__PROTO_ROUTES__ = ['#/a','#/b?scn=empty']
//   ② 场景模型（旧 demo-scaffold）：[data-scene] 分节
//   ③ 都没有：就地审当前页面
const PROBE_TPL = `(async () => {
  const EXHAUSTIVE = __EXHAUSTIVE__;
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 弹原生对话框会把探针卡死；同时「弹了框」本身就是一种可观测变化
  let nativeDialogs = 0;
  window.alert = window.confirm = window.prompt = function () { nativeDialogs++; return true; };

  // ⭐ 控制台报错 —— SKILL.md 的 S6 自动验收表第 2 项，此前同样没有任何实现。
  //   它当场抓到了本 SOP 自己的原型骨架里一个 null.slice 崩溃：
  //   **页面整片空白时，死按钮率反而是 0%**（没有元素就没有死元素）——
  //   ⛔ 只有死按钮这一项的门，对「整页崩掉」报绿。
  const consoleErrors = [];
  const _err = console.error;
  console.error = function () { consoleErrors.push([].slice.call(arguments).join(' ').slice(0, 160)); return _err.apply(console, arguments); };
  window.addEventListener('error', e => consoleErrors.push('Uncaught: ' + (e.message || '').slice(0, 160)));
  window.addEventListener('unhandledrejection', e => consoleErrors.push('UnhandledRejection: ' + String(e.reason && e.reason.message || e.reason).slice(0, 160)));

  let mutations = 0;
  new MutationObserver(ms => { mutations += ms.length; })
    .observe(document.documentElement, { childList: true, subtree: true, attributes: true, characterData: true });

  const sig = () => [mutations, location.href, document.activeElement && document.activeElement.tagName,
                     document.activeElement && document.activeElement.id,
                     nativeDialogs, window.scrollY,
                     document.querySelectorAll('dialog[open],[aria-expanded="true"]').length].join('|');

  const routes = Array.isArray(window.__PROTO_ROUTES__) && window.__PROTO_ROUTES__.length
    ? window.__PROTO_ROUTES__.slice(0, 60) : null;
  const scenes = routes ? null
    : ([...document.querySelectorAll(':not(body)[data-scene]')].map(e => e.dataset.scene).filter(Boolean));
  const model = routes ? 'route' : (scenes && scenes.length ? 'scene' : 'single');
  const stops = routes || (scenes && scenes.length ? scenes : [null]);

  // ⚠️ 必须能把页面**恢复到停靠点的初始状态**。
  //    一份会重渲染的原型（innerHTML 整段替换）在第一次点击之后，
  //    先前抓到的元素引用**全部脱离文档**；对脱离文档的节点点击当然毫无反应 ——
  //    于是这道门会把「正确实现的应用」整片判成死按钮。
  //    ⭐ 这是我自己写的骨架当场撞出来的：不复位就重测，测的是**上一次点击的残骸**。
  // 等「异步落定」而不是等一个猜出来的毫秒数。
  // 产品挂 body[data-busy] 时按标记等；没挂标记的（旧 demo）退回固定 sleep。
  async function settle(maxMs) {
    const t0 = Date.now();
    while (document.body.hasAttribute('data-busy') && Date.now() - t0 < maxMs) await sleep(50);
    await sleep(60);
  }
  async function enter(stop) {
    if (stop === null) { await settle(4000); return; }
    if (model === 'route') {
      location.hash = '/__probe_reset__';            // 先跳开，逼出一次 hashchange
      await sleep(25);
      location.hash = String(stop).replace(/^#/, '');
      await sleep(120);
      await settle(6000);
    } else {
      location.hash = stop;
      document.querySelectorAll(':not(body)[data-scene]').forEach(x => { x.hidden = x.dataset.scene !== stop; });
      await sleep(90);
      await settle(3000);
    }
  }

  // ⭐ 只探「点一下就该有反应」的元素。
  //   ⛔ 文本框 / textarea / select **不属于**这一类：\`el.click()\` 不会移动焦点
  //      （焦点来自浏览器对真实 mousedown 的默认处理，合成 click 不触发），
  //      把它们算进来会稳定制造假阳性 —— 而假阳性会让人给门加豁免清单，最后没人看它。
  //      文本框该由 flow-walk（填了值再断言）来验，不是这道门的活。
  const SEL = 'button,[role="button"],a[href],summary,[onclick],' +
              'input[type="checkbox"],input[type="radio"],input[type="submit"],input[type="button"]';
  // ⚠️ Chrome 152 起，折叠的 <details> 内容用 content-visibility:hidden 实现，
  //    getBoundingClientRect() 仍返回非零尺寸 —— 只按宽高判可见，
  //    会把**收起来的**内容当成可见的。实测：一个正确折叠的场景导航
  //    被判出 21 个「无焦点环」，留白被算成 6%。
  //    ⭐ checkVisibility() 正是为这件事存在的，能用就用它。
  const vis = el => {
    if (el.checkVisibility && !el.checkVisibility({ contentVisibilityAuto: true,
        opacityProperty: true, visibilityProperty: true })) return false;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && s.pointerEvents !== 'none';
  };
  // ⚠️ 两类「本来就该没反应」的元素必须排除，否则这道门会**惩罚正确实现**：
  //   · disabled / aria-disabled：不可用是它的正确行为
  //   · 指向当前地址的导航链接：真实产品点它同样什么都不发生
  const exempt = el => el.disabled === true || el.getAttribute('aria-disabled') === 'true' ||
    (el.tagName === 'A' && el.getAttribute('href') &&
     new URL(el.href, location.href).href.replace(/#$/, '') === location.href.replace(/#$/, ''));
  // 会离开本文档的链接不点：点了整个探针就没了，而且那不是「交互」是「跳走」
  const leaves = el => el.tagName === 'A' && el.getAttribute('href') &&
                       !/^(#|javascript:)/.test(el.getAttribute('href')) &&
                       new URL(el.href, location.href).pathname !== location.pathname;
  const label = el => (el.getAttribute('aria-label') || el.textContent || el.value ||
                       el.getAttribute('title') || el.name || '').trim().replace(/\\s+/g, ' ').slice(0, 24)
                       || ('<' + el.tagName.toLowerCase() + '>');

  // ⚠️ 瞬态区域（toast / 状态播报）不进点击探针。
  //   不是因为它不重要，而是因为**它按定时消失、且探针每探一个元素都要复位状态**，
  //   两件事凑在一起会稳定产生假阳性。实测：撤销按钮单独点是好的（htmlDelta 158），
  //   在复位式探针里却次次判死。
  //   ⛔ 但绝不许把它折叠进「通过」—— 单独计数、单独打印，交给 flow-walk 覆盖。
  //   （M6 诚实缺口：「没测」和「测过了」必须能分辨。）
  const transient = el => el.closest('[aria-live],[role="status"],[role="alert"]') !== null;

  function collect(stop) {
    const root = (model === 'scene' && stop) ? document.querySelector('[data-scene="' + stop + '"]') : document.body;
    if (!root) return [];
    return [...root.querySelectorAll(SEL)].filter(vis).filter(el => !leaves(el) && !exempt(el));
  }
  // 同一停靠点里**长得一样的控件只探一个**：列表里 12 个「删除」是同一个控件的 12 个实例，
  // 逐个点 12 次不会多发现任何东西，只会让这道门慢到没人愿意跑（而没人跑的门等于没有门）。
  const keyOf = el => el.tagName + '|' + (el.getAttribute('role') || '') + '|' + label(el);

  const rows = [];
  let skipped = 0, crossSkipped = 0;
  let budget = 300;
  // ⚠️ 跨停靠点去重：「#/inbox?scn=default」 与 「?scn=slow」 的控件集合通常一模一样，
  //   逐个再点一遍不增加发现，只增加时长。**没人愿意跑的门禁等于没有门禁。**
  //   ⛔ 代价要说清楚：这会漏掉「同一个控件在 A 场景好、在 B 场景坏」。
  //   要全量就加 --exhaustive；本行为与耗时都会打印出来，不许沉默地少跑。
  const globalSeen = new Set();
  // ⚠️ 端必须进去重键。「?end=mobile」与桌面是**两套渲染**：
  //   移动端的推进按钮是 disabled、新建页根本没有表单。
  //   只按路径去重，移动端那一半会被整片跳过 —— 而那正是双端产品最容易丢的一半。
  const routeOf = s => { const str = String(s || '-');
    const m = /[?&]end=(\w+)/.exec(str);
    return str.split('?')[0] + '@' + (m ? m[1] : 'pc'); };
  for (const stop of stops) {
    await enter(stop);
    const first = collect(stop);
    skipped += first.filter(transient).length;
    // 先按「长得一样」去重，得到本停靠点要探的**下标清单**
    const seen = new Set();
    const idxs = [];
    first.forEach((el, i) => {
      if (transient(el)) return;
      const k = keyOf(el);
      if (seen.has(k)) return;
      seen.add(k);
      const gk = routeOf(stop) + '#' + k;
      if (!EXHAUSTIVE && globalSeen.has(gk)) { crossSkipped++; return; }
      globalSeen.add(gk); idxs.push(i);
    });
    let els = first, fresh = true;
    for (const i of idxs) {
      if (budget-- <= 0) break;
      if (!fresh) { await enter(stop); els = collect(stop); }   // 上一次点击改动了页面才需要复位
      fresh = false;
      if (i >= els.length) break;        // 复位后元素变少（如上一轮删掉了一行）
      const el = els[i];
      if (transient(el)) { skipped++; continue; }
      const meta = { stop: stop || '-', label: label(el), tag: el.tagName.toLowerCase(),
                     critical: el.closest('[data-critical]') !== null };
      const probe = async (node) => {
        const before = sig();
        try { node.click(); } catch (e) { /* 点不动本身就是死 */ }
        await sleep(60);
        await settle(6000);         // 点击引发的异步也要等它落定，否则「慢接口」会被判成死
        return before === sig();
      };
      let dead = await probe(el);
      // ⭐ 判死之前复测一次。理由不是保险起见 ——
      //   瞬态 UI（toast / 提示条）与刚落定的异步会让**单次点击的结果本身带抖动**，
      //   而「对会波动的量只测一次就下结论」是这台机器上反复栽过的坑。
      //   连续两次都毫无反应才算死；只要有一次动了，它就不是死的。
      if (dead) {
        await enter(stop);
        const again = collect(stop);
        if (i < again.length && again[i] && label(again[i]) === meta.label) dead = await probe(again[i]);
      }
      meta.dead = dead;
      fresh = dead;                      // 毫无变化 ⇒ 页面还是干净的，下一个不用重进
      rows.push(meta);
    }
  }
  return { model, stops: stops.length, rows, skipped, crossSkipped, consoleErrors: consoleErrors.slice(0, 20) };
})()`;

// ---------------------------------------------------------------- 判定
function judge(data, maxPct, minEls) {
  const rows = data.rows;
  const total = rows.length;
  if (total === 0)
    return { unable: '页面上找不到任何可见的可交互元素 —— 这不是一份可点的 demo。' +
                     '（0/0 不算通过：分母为零的绿是假绿）' };
  if (total < minEls)
    return { unable: `只有 ${total} 个可交互元素（阈值 ${minEls}）—— 这份产物不具备「可点 demo」的形态，` +
                     '判它「死按钮率 0%」没有意义' };
  const errs = data.consoleErrors || [];
  const dead = rows.filter(r => r.dead);
  const deadCritical = dead.filter(r => r.critical);
  const pct = Math.round(dead.length / total * 1000) / 10;
  const fail = pct > maxPct || deadCritical.length > 0 || errs.length > 0;
  return { total, dead, deadCritical, pct, fail, errs, skipped: data.skipped || 0,
           crossSkipped: data.crossSkipped || 0, model: data.model, stops: data.stops };
}

function report(v, asJson, list) {
  if (v.unable) { console.error('UNABLE: ' + v.unable); return 2; }
  if (asJson) { console.log(JSON.stringify(v, null, 1)); return v.fail ? 1 : 0; }
  const modelName = { route: '路由模型', scene: '场景模型（旧 demo-scaffold 形态）', single: '单页' }[v.model];
  console.log(`遍历模型：${modelName}　停靠点 ${v.stops} 个`);
  console.log(`探测了 ${v.total} 个不同控件（同一停靠点内同名同类只探一个）　·　点后毫无可观测变化 ${v.dead.length} 个（${v.pct}%）`);
  if (v.crossSkipped) console.log(`（跨停靠点去重跳过 ${v.crossSkipped} 个同名控件；要全量点一遍加 --exhaustive）`);
  if (v.skipped) console.log(`⚠️ 另有 ${v.skipped} 个在瞬态区域（toast/aria-live）内**未探测** —— 不计入通过，由 flow-walk 覆盖`);
  if (v.errs.length) {
    console.log(`❌ 控制台报错 ${v.errs.length} 条（未捕获异常 / console.error，零容忍）`);
    v.errs.slice(0, 6).forEach(e => console.log('   · ' + e));
  }
  if (v.deadCritical.length)
    console.log(`❌ 关键路径上有 ${v.deadCritical.length} 个死元素（data-critical，零容忍）`);
  const show = list ? v.dead : v.dead.slice(0, 12);
  for (const d of show) console.log(`   · [${d.stop}] <${d.tag}> ${d.label}${d.critical ? '  ⚠️关键' : ''}`);
  if (!list && v.dead.length > show.length) console.log(`   …… 还有 ${v.dead.length - show.length} 个（加 --list 看全部）`);
  console.log(v.fail ? '\n❌ 不通过' : '\n✅ 通过');
  if (!v.fail) console.log('⚠️ 绿不代表关键路径走得通 —— 程序化 click 只能证伪。真人仍要点一遍。');
  return v.fail ? 1 : 0;
}

// ---------------------------------------------------------------- 自证（M8）
// ⭐ 三个反例分别打三种失效形态，其中第三个是这道门**最容易做成装饰**的地方：
//    「挂了 handler」≠「点了有反应」。只查 onclick 属性存不存在的门，对它报绿。
const GOOD = `<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>t</title></head><body>
<main id="m"><p id="out">0</p>
<button id="a">加一</button><button id="b">减一</button><button id="c">清零</button>
<button id="d">切换</button><button id="e">追加</button><button id="f">删除</button></main>
<script>
var n=0,r=0,out=document.getElementById('out');
function set(v){n=v;out.textContent=String(n);}
/* 🚨 2026-09-15 Linux CI 揪出的**夹具缺陷**：原来 #c「清零」是 set(0) ——
   计数器**已经是 0 时点它什么都不变**，于是被正确判为「点后毫无可观测变化」。
   macOS 上探测顺序恰好让它非 0，Linux 上是 0 ⇒ 同一份正例两个平台两种结果。
   ⭐ 门禁没错，错的是正例夹具：它含一个**可观测性依赖先前状态**的按钮。
   ⛔ 修法不是放宽门禁，是让清零**总是**产生可观测变化 ——
     真实产品里也该如此：「已经空了再点毫无反馈」的清零按钮本就是体验缺陷。 */
function reset(){n=0;r++;out.textContent='0（已清零'+r+'次）';}
document.getElementById('a').onclick=function(){set(n+1)};
document.getElementById('b').onclick=function(){set(n-1)};
document.getElementById('c').onclick=function(){reset()};
document.getElementById('d').onclick=function(){document.body.classList.toggle('on')};
document.getElementById('e').onclick=function(){var p=document.createElement('p');p.textContent='x';document.getElementById('m').appendChild(p)};
document.getElementById('f').onclick=function(){out.setAttribute('data-t',Date.now())};
</script></body></html>`;

// 反例①：一半按钮完全没接线
const BAD_UNWIRED = GOOD
  .replace("document.getElementById('a').onclick=function(){set(n+1)};", '')
  .replace("document.getElementById('b').onclick=function(){set(n-1)};", '')
  .replace("document.getElementById('c').onclick=function(){reset()};", '')
  .replace("document.getElementById('d').onclick=function(){document.body.classList.toggle('on')};", '');
// 反例②：**挂了 handler 但什么都不做** —— 静态扫描（查 onclick 是否存在）对它无能为力
const BAD_NOOP = GOOD
  .replace('{set(n+1)}', '{/* TODO */}').replace('{set(n-1)}', '{void 0}')
  .replace('{set(0)}', '{return false}').replace("{document.body.classList.toggle('on')}", '{}');
// 正例②：**正确实现的 disabled 按钮不许被判死** —— 反向测试这道门会不会误伤对的实现
const GOOD_DISABLED = GOOD.replace('<button id="f">删除</button>',
  '<button id="f">删除</button><button disabled>不可用</button><button aria-disabled="true">无权限</button>');
// 反例④：**界面看起来正常、点了抛异常** —— 死按钮率是 0%，只有控制台在报错
const BAD_THROWS = GOOD.replace('{set(n+1)}', '{set(n+1); null.x}');
// 反例③：页面上根本没有可交互元素 → 必须 UNABLE(2)，不许折叠成「0% 死，通过」
const BAD_EMPTY = `<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>t</title></head>
<body><main><h1>只有文字</h1><p>没有任何可点的东西</p></main></body></html>`;

for (const [n, s] of [['unwired', BAD_UNWIRED], ['noop', BAD_NOOP], ['throws', BAD_THROWS]])
  if (s === GOOD) throw new Error(`自证用例坏了：反例 ${n} 与正例逐字相同，变异是 no-op`);

async function selfTest() {
  // 环境预检（Codex 三审 0.5.4）：起不了真浏览器 → 整体 UNABLE 退 2，不冒充用例失败
  if (!(await browserPreflight())) {
    console.log('UNABLE: 起不了无头浏览器 —— 本门自证需要真实渲染，全部用例记 UNABLE（不是失败，也不是通过）');
    process.exit(2);
  }
  // 反例：旋钮强制无浏览器 → 子进程自测必须整体 UNABLE(2)。旋钮只能让结果更红，方向安全。
  {
    const { execFileSync: _ex } = await import('node:child_process');
    let _rc; try { _ex(process.execPath, [process.argv[1], '--self-test'],
      { stdio: 'pipe', env: { ...process.env, PF_FORCE_NO_BROWSER: '1' } }); _rc = 0; }
    catch (e) { _rc = e.status; }
    console.log(`  ${_rc === 2 ? '✅' : '❌'} 反例：强制无浏览器 → 自测整体 UNABLE（环境缺席≠失败）　期望 2 实得 ${_rc}`);
    if (_rc !== 2) process.exit(1);
  }
  const t = mkdtempSync(join(tmpdir(), 'dc-st-'));
  const me = resolve(process.argv[1]);
  const w = (n, c) => { const p = join(t, n); writeFileSync(p, c); return p; };
  // 🚨 2026-09-15 CI 实测后改：原来 `stdio:'pipe'` 把门禁输出**整个丢掉**，
  //   失败时只剩一个退出码。3 个正例在 Linux CI 上红，连查 2 轮都不知道它判了谁死 ——
  //   ⭐ 与 selftest-all 吞子进程 stderr 是**同一个毛病**：
  //     把失败原因藏起来的聚合器，会让排查停在第一步。
  //   ⇒ 捕获输出，**只在用例失败时**打印（成功时保持安静，不淹没名册）。
  const lastOut = { text: '' };
  const run = (p, ...extra) => {
    try {
      const o = execFileSync(process.execPath, [me, p, ...extra],
                             { stdio: 'pipe', encoding: 'utf8' });
      lastOut.text = String(o || ''); return 0;
    } catch (e) {
      lastOut.text = String(e.stdout || '') + String(e.stderr || '');
      return e.status;
    }
  };
  console.log('M8 自证 —— 正例绿 / 三类反例各自必红 / 无效输入报 2 不报 0\n');
  const cases = [
    ['正例：6 个按钮全部接线且有可观测变化', w('good.html', GOOD), [], 0],
    ['反例①：4/6 没接线（死按钮率 67%）', w('bad1.html', BAD_UNWIRED), [], 1],
    ['反例②：挂了 handler 但什么都不做', w('bad2.html', BAD_NOOP), [], 1],
    ['反例③：页面无可交互元素 → 必须 UNABLE', w('bad3.html', BAD_EMPTY), [], 2],
    ['反例④：点了抛异常（死按钮率 0% 也必须红）', w('bad4.html', BAD_THROWS), [], 1],
    ['阈值可调：正例在 --max-dead-pct 0 下仍绿', w('good2.html', GOOD), ['--max-dead-pct', '0'], 0],
    // 🆕 2026-09-06：默认值必须是**严的那个**（0，与 S6 出场条件一致）。
    //    原默认是 5 ⇒ 不带参数跑会以为达标了。这条用例锁住「不带参数 = 严档」。
    ['不带参数时按最严档判（默认 0，不是 5）', w('dead1.html', BAD_UNWIRED), [], 1],
    ['正例②：disabled/aria-disabled 不许被误判为死', w('good3.html', GOOD_DISABLED), ['--max-dead-pct', '0'], 0],
    ['输入不存在', join(t, 'nope.html'), [], 2],
  ];
  let ok = true;
  for (const [name, path, extra, want] of cases) {
    const rc = run(path, ...extra);
    const g = rc === want; ok &&= g;
    console.log(`  ${g ? '✅' : '❌'} ${name.padEnd(40)} 期望 ${want} 实得 ${rc}`);
    if (!g) {
      // ⛔ 只在失败时打印：排查要的是**它判了什么**，不是退出码
      const body = lastOut.text.trim().split('\n').slice(0, 14).map(l => '       │ ' + l).join('\n');
      if (body) console.log(body);
    }
  }
  console.log(`\n${ok ? '✅ 自证通过：这道门会出声' : '❌ 自证失败：先修门禁'}`);
  process.exit(ok ? 0 : 1);
}

// ---------------------------------------------------------------- main
const argv = process.argv.slice(2);
if (argv.includes('--self-test')) { await selfTest(); }
else {
  // ⚠️ 未知 `--flag` 必须报错：静默丢弃会让门禁只跑一半而照样报绿（见 _argv.mjs）
  //    本门禁尤其危险 —— `--all-route`（少个 s）会让它只审打开时那一屏。
  rejectUnknown(argv, ['--json','--max-dead-pct','--viewport','--min-elements','--list','--exhaustive','--self-test'],
    '用法: dead-click-gate.mjs <file.html> [--json] [--max-dead-pct 5] [--viewport 1440x900] [--min-elements 3] [--list]');
  const files = argv.filter(a => !a.startsWith('--') && !/^\d+$/.test(a) && !/^\d+x\d+$/.test(a));
  if (!files.length) {
    console.log('用法: dead-click-gate.mjs <file.html> [--json] [--max-dead-pct 5] [--viewport 1440x900] [--min-elements 3] [--list]');
    process.exit(2);
  }
  const num = (flag, dflt) => { const i = argv.indexOf(flag); return i > -1 && argv[i + 1] ? Number(argv[i + 1]) : dflt; };
  const vi = argv.indexOf('--viewport');
  const vp = vi > -1 && argv[vi + 1] ? argv[vi + 1] : '1440x900';
  if (!/^https?:/.test(files[0]) && !existsSync(files[0])) { console.error('UNABLE: 文件不存在 ' + files[0]); process.exit(2); }
  const probe = PROBE_TPL.replace('__EXHAUSTIVE__', argv.includes('--exhaustive') ? 'true' : 'false');
  const t0 = Date.now();
  let data;
  try { [data] = await evalInPage(files[0], vp, [probe]); }
  catch (e) { console.error('UNABLE: ' + e.message); process.exit(2); }
  // ── 两个默认阈值的出处（⛔ 没有出处的阈值长着权威的样子却是编的）──
  //  · `--max-dead-pct` 默认 **0** —— 与 SKILL.md 的 S6 出场条件一致。
  //    🚨 2026-09-06 改：原默认是 **5**，而 SOP 要求 0 ⇒ **不带参数跑会以为达标了**。
  //    ⭐ 默认值必须是**严的那个**，放宽要是**主动行为**：
  //    「悄悄放宽」和「没有这道门」在产物上一模一样。
  //    带了非 0 容忍时本门会**明说**（见下），不许静默放行。
  //  · `--min-elements 3` —— 少于 3 个可探控件时死按钮率没有统计意义，
  //    报出来只会是噪音（实测：单控件页面 1 个装饰性 div 就是 100%）。
  const tol = num('--max-dead-pct', 0);
  if (tol > 0)
    console.log(`⚠️ 本次带了 --max-dead-pct ${tol} —— **放宽了验收线**（S6 出场条件是 0）。`
      + '这一行是刻意打印的：悄悄放宽和没有这道门在产物上一模一样。');
  const rc = report(judge(data, tol, num('--min-elements', 3)),
                    argv.includes('--json'), argv.includes('--list'));
  if (!argv.includes('--json')) console.log(`耗时 ${Math.round((Date.now() - t0) / 1000)}s`);
  process.exit(rc);
}
