#!/usr/bin/env node
// ============================================================================
// 关键路径门禁 —— 把 spec/flows.json 里的每条关键路径在真实浏览器里走一遍。
//
// ═══ 它补的是哪个洞 ═══
// `dead-click-gate` 只回答「点了有没有反应」，回答不了「点了以后对不对」。
// SKILL.md 的 S6 自动验收表第 4 项「关键路径可达」此前没有实现，
// 出场条件里只有一句「关键路径**真的点通**（读代码不算）」—— 靠人自觉。
// ⭐ 而这条恰恰是**演示现场最容易翻车**的一条：老板不会挨个点按钮，
//    他会顺着一条路走到底，中间断在哪儿就当场断在哪儿。
//
// ═══ 为什么用 role + 可访问名称定位，不用 CSS 类 ═══
// 来自 testing-library / Storybook 的明确建议：「用真人使用界面的方式去找元素，
// `data-testid` 是最后手段」。好处是同一个选择器**同时**是无障碍契约、
// 测试选择器、研发的语义命名 —— 改一个按钮的类名不会让用例静默失效，
// 而**改掉它的可访问名称本来就该让用例失效**（那是真的改了行为）。
//
// 用法：
//   node flow-walk-gate.mjs <demo.html> --flows <flows.json> [--json] [--only FLOW-01]
//   node flow-walk-gate.mjs --self-test
// 退出码：0=全部走通  1=有走不通的  2=跑不了（找不到浏览器/文件/flows 解析失败）
// ============================================================================
import { existsSync, readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
import { evalInPage, browserPreflight } from './_browser.mjs';
import { HELPERS } from './_page-helpers.mjs';
import { rejectUnknown } from './_argv.mjs';

// 登记册#1：--help 只显示帮助（文件头注释）并退 0
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  const _src = readFileSync(new URL(import.meta.url), 'utf8');
  console.log(_src.split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}

// ---------------------------------------------------------------- 页面内走查器
const WALKER = `(async (FLOWS) => {
${HELPERS}
  const results = [];
  for (const flow of FLOWS) {
    const rec = { id: flow.id, name: flow.name, ok: true, failedStep: null, why: null };
    try {
      location.hash = '/__flow_reset__'; await sleep(30);
      location.hash = String(flow.start || '#/').replace(/^#/, ''); await sleep(140);
      await settle(8000);
      for (let i = 0; i < flow.steps.length; i++) {
        const s = flow.steps[i];
        const desc = '步骤 ' + (i + 1) + ' ' + JSON.stringify(s);
        if (s.do === 'fill' || s.do === 'click' || s.do === 'clickFirst') {
          await doStep(s);
        } else if (s.do === 'key') {
          // 键盘路径：interaction-criteria 里「Enter 提交聚焦的输入框」「Tab 顺序」
          // 「Esc 关闭弹层」都是 MUST，而此前一条都没被自动验过。
          const k = s.key;
          const target = s.role ? (() => { const f = byRole(s.role, s.name, s.namePrefix);
            if (f.err) throw new Error(f.err); return f.el; })() : (document.activeElement || document.body);
          if (s.role) target.focus();
          const opts = { key: k, code: k.length === 1 ? 'Key' + k.toUpperCase() : k,
                         bubbles: true, cancelable: true,
                         shiftKey: !!s.shift, metaKey: !!s.meta, ctrlKey: !!s.ctrl };
          target.dispatchEvent(new KeyboardEvent('keydown', opts));
          // Enter 落在表单控件上时浏览器会隐式提交 —— 合成事件不会，这里补上，
          // 否则「Enter 提交」这条 MUST 永远验不出来（而它恰恰是最常漏做的一条）
          if (k === 'Enter' && target.form && !s.noImplicitSubmit) {
            const btn = target.form.querySelector('button[type="submit"],input[type="submit"]');
            if (btn) btn.click();
            else target.form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
          }
          target.dispatchEvent(new KeyboardEvent('keyup', opts));
          await sleep(60); await settle(8000);
        } else if (s.do === 'tab') {
          // Tab 只能近似：合成事件不移动焦点，按 tabindex/文档序取下一个可聚焦元素
          const F = [...document.querySelectorAll(
            'a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])')]
            .filter(e => !e.disabled && e.getBoundingClientRect().width > 0);
          const i = F.indexOf(document.activeElement);
          const next = F[(i + (s.shift ? -1 : 1) + F.length) % F.length];
          if (next) next.focus();
          await sleep(40);
        } else if (s.do === 'expect') {
          if (s.urlContains && location.hash.indexOf(s.urlContains.replace(/^#/, '#')) === -1
              && location.href.indexOf(s.urlContains) === -1)
            throw new Error('期望 URL 含「' + s.urlContains + '」，实际 ' + location.hash);
          if (s.textContains && (document.body.innerText || '').indexOf(s.textContains) === -1)
            throw new Error('期望页面出现「' + s.textContains + '」，没找到');
          if (s.textAbsent && (document.body.innerText || '').indexOf(s.textAbsent) !== -1)
            throw new Error('期望页面不出现「' + s.textAbsent + '」，但它在');
          if (s.focusedName) {
            const fn = document.activeElement ? accName(document.activeElement) : '';
            if (fn !== s.focusedName)
              throw new Error('期望焦点在「' + s.focusedName + '」，实际在「' + fn + '」');
          }
          if (s.roleExists) {
            const f = byRole(s.roleExists, s.name, s.namePrefix);
            if (f.err) throw new Error(f.err);
          }
        } else {
          throw new Error('不认识的步骤类型：' + s.do);
        }
        rec.lastOk = i + 1;
      }
    } catch (e) {
      rec.ok = false;
      rec.failedStep = (rec.lastOk || 0) + 1;
      rec.why = String(e.message || e).slice(0, 240);
    }
    results.push(rec);
  }
  return results;
})(__FLOWS__)`;

// ---------------------------------------------------------------- 报告
function report(rows, asJson) {
  if (asJson) { console.log(JSON.stringify(rows, null, 1)); return rows.some(r => !r.ok) ? 1 : 0; }
  for (const r of rows) {
    if (r.ok) console.log(`✅ ${r.id} ${r.name}`);
    else {
      console.log(`❌ ${r.id} ${r.name}`);
      console.log(`     断在第 ${r.failedStep} 步：${r.why}`);
    }
  }
  const bad = rows.filter(r => !r.ok).length;
  console.log(`\n关键路径 ${rows.length} 条 · 走通 ${rows.length - bad} · 断掉 ${bad}`);
  if (!bad) console.log('⚠️ 走通 ≠ 交互做对了。这道门只验「路径可达 + 断言成立」，观感与手感仍要人走一遍。');
  return bad ? 1 : 0;
}

async function walk(file, flows, only) {
  const list = only ? flows.filter(f => f.id === only) : flows;
  if (!list.length) throw new Error('没有可走的关键路径（--only 没匹配到？）');
  // ⭐ 一条路径一条表达式 + reloadBetween：**每条路径都跑在干净页面上**。
  //    2026-09-04 之前所有路径塞在一次求值里、只换 hash，前一条点出来的 DOM 会留给后一条。
  //    实录：FLOW-29 单跑绿、批量红。⛔ 反方向更危险 —— 一条路径可能靠前面留下的状态
  //    「走通」，那是一条从没真正走通过的路径在报绿。
  //    ⚠️ 代价是每条多一次重载（约 0.5s）。宁可慢，不要一份不可信的绿。
  // ⚠️ 2026-09-04：`flows.json` 里每条路径都声明了 `end`，而本门禁**从来没读过它** ——
  //    恒定跑 1440x900。于是**移动端的关键路径根本走不了**：
  //    就算写了 `end: "mobile"` 的路径，它也会在桌面视口上跑。
  //    ⛔ 一个声明了但没人消费的字段，比没有这个字段更糟 ——
  //      它让人以为覆盖到了。（本骨架 6 条路径全是 pc，移动端一条都没有，
  //      而用户明确要求了双端形态。）
  //    ⭐ 按端分组跑：每端一个视口，并把 `end=` 拼进起点 URL。
  const byEnd = new Map();
  for (const f of list) {
    const e = f.end || 'pc';
    if (!byEnd.has(e)) byEnd.set(e, []);
    byEnd.get(e).push(f);
  }
  const VIEWPORT = { pc: '1440x900', mobile: '390x844' };
  const out = [];
  for (const [end, fs] of byEnd) {
    const vp = VIEWPORT[end] || VIEWPORT.pc;
    // 起点带上 end= —— 骨架靠它切端形态（见 40-router.js currentEnd）
    const withEnd = fs.map(f => {
      if (end === 'pc') return f;
      const s = String(f.start || '#/');
      // ⚠️ 只对**路由模型**形式（`#/f01?scn=…`）拼 `end=`。
      //    🔴 2026-09-05 实测：扁平写法（`#f08-mobile-revoke`）把端**编码在场景名里**，
      //    再拼 `?end=mobile` 会让路由的 `names.indexOf(h)` 查不到
      //    ⇒ 回落到场景 0，并把 hash 改写成第一屏 ——
      //    表现是「移动端路径稳定失败」，而 dbg 显示 `hash=#f01-pc-partial vis=["f01-pc-partial"]`。
      //    ⭐ 两种寻址写法都要支持：拼 `end=` 对一种是必需的，对另一种是破坏性的。
      if (!/^#?\//.test(s)) return f;
      const sep = s.includes('?') ? '&' : '?';
      return { ...f, start: s.includes('end=') ? s : s + sep + 'end=' + end };
    });
    const exprs = withEnd.map(f => WALKER.replace('__FLOWS__', JSON.stringify([f])));
    const o = await evalInPage(file, vp, exprs, { reloadBetween: true });
    out.push(...o.flat().map(r => ({ ...r, end })));
  }
  return out;
}

// ---------------------------------------------------------------- 自证（M8）
const APP = `<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>t</title></head><body>
<main id="app"></main><div id="toast" hidden aria-live="polite"></div>
<script>
var state={page:'create',err:'',items:[]};
// 端形态的两个来源**分开**渲染 —— 这样单点变异也能红,不会互相兜底。
var NARROW = window.innerWidth <= 560;
var ENDQ   = /[?&]end=mobile/.test(location.search + location.hash);

function accApp(){
  var a=document.getElementById('app');
  if(state.page==='create'){
    a.innerHTML='<h1>新建任务</h1><form id="f" novalidate>'+
      '<label for="title">标题</label><input id="title">'+
      (state.err?'<p id="e" role="alert">标题不能为空</p>':'')+
      '<button type="submit">__SUBMIT__</button></form>';
    document.getElementById('f').onsubmit=function(ev){ev.preventDefault();
      var v=document.getElementById('title').value.trim();
      if(!v){ state.err='x'; accApp(); __FOCUS__ return; }
      state.items.push(v); state.page='inbox'; location.hash='/inbox'; accApp(); };
  } else if(state.page==='flatmobile'){
    /* 扁平写法：端**编码在场景名里**（m-mobile-home），⛔ 不看 end= 参数。
       给它拼 ?end=mobile 会让下面的精确匹配落空 ⇒ 回落到第一屏。 */
    a.innerHTML='<h1>扁平移动端场景</h1><p>端来自场景名，不来自查询串</p>';
  } else {
    a.innerHTML='<h1>任务列表</h1><ul>'+state.items.map(function(t){return '<li>'+t+'</li>';}).join('')+'</ul>'
      +(NARROW?'<p>窄视口才有的底部栏</p>':'')+(ENDQ?'<p>端参数才有的返回键</p>':'');
  }
}
// 自证夹具也必须响应 hashchange —— 真实应用都会。
// 📌 首版漏了它，于是第一条路径跑完停在 #/inbox，第二条设了 hash 却没重渲染，
//    正例被判红。**是夹具坏了，不是门禁坏了** —— 这正是「反例必须真的制造出那个缺口、
//    正例必须真的成立」要靠跑一遍才知道的原因。
window.addEventListener('hashchange', function(){
  /* ⚠️ 扁平写法用**精确相等**匹配（真实 demo 就是 names.indexOf(h)）——
     所以 hash 上多一个 ?end=mobile 就查不到，这正是要守的那个缺口。 */
  var h = location.hash.slice(1);
  if (h === 'm-mobile-home') { state.page='flatmobile'; state.err=''; accApp(); return; }
  state.page = location.hash.indexOf('inbox') > -1 ? 'inbox' : 'create';
  state.err = ''; accApp();
});
accApp();
</script></body></html>`;
const GOOD = APP.replace('__SUBMIT__', '提交').replace('__FOCUS__', "document.getElementById('title').focus();");
const BAD_NAME = APP.replace('__SUBMIT__', '确定').replace('__FOCUS__', "document.getElementById('title').focus();");
const BAD_FOCUS = APP.replace('__SUBMIT__', '提交').replace('__FOCUS__', '');
// 反例：表单不响应隐式提交（把 <form> 换成 <div>，Enter 就没有提交对象了）
const BAD_ENTER = GOOD.replace('<form id="f" novalidate>', '<div id="f">')
                      .replace("'</form>'", "'</div>'")
                      .replace('<button type="submit">', '<button type="button" onclick="submitIt()">');
for (const [n, s] of [['name', BAD_NAME], ['focus', BAD_FOCUS], ['enter', BAD_ENTER]])
  if (s === GOOD) throw new Error('自证用例坏了：反例 ' + n + ' 与正例逐字相同');

const ST_FLOWS = [
  { id: 'FLOW-K', name: '在标题框里按 Enter 就能提交', start: '#/create',
    steps: [{ do: 'fill', role: 'textbox', name: '标题', value: '键盘' },
            { do: 'key', key: 'Enter', role: 'textbox', name: '标题' },
            { do: 'expect', urlContains: '#/inbox' },
            { do: 'expect', textContains: '键盘' }] },
  { id: 'FLOW-A', name: '填了标题能提交', start: '#/create',
    steps: [{ do: 'fill', role: 'textbox', name: '标题', value: '甲' },
            { do: 'click', role: 'button', name: '提交' },
            { do: 'expect', urlContains: '#/inbox' },
            { do: 'expect', textContains: '甲' }] },
  { id: 'FLOW-B', name: '不填被拦住且焦点回到标题', start: '#/create',
    steps: [{ do: 'click', role: 'button', name: '提交' },
            { do: 'expect', textContains: '标题不能为空' },
            { do: 'expect', focusedName: '标题' }] },
  // ⭐ 下面两条是**门禁自己的守卫**,不是在测夹具:
  //    2026-09-05 实测,把「移动端用 390x844 视口」和「起始 URL 带 end=」分别拆掉,
  //    真实 demo 的三条移动端路径**一条都没红** —— 因为 currentEnd() 两个来源互为兜底,
  //    单点变异总有另一路接住。只有同时打掉两路才红。
  //    所以这里把两个来源**分开**各立一条:任一半失效,正例立刻变红,不必等双重变异。
  { id: 'FLOW-MV', name: '移动端路径要真的跑在窄视口上', start: '#/inbox', end: 'mobile',
    steps: [{ do: 'expect', textContains: '窄视口才有的底部栏' }] },
  { id: 'FLOW-MU', name: '移动端路径的起始 URL 要真的带上 end=', start: '#/inbox', end: 'mobile',
    steps: [{ do: 'expect', textContains: '端参数才有的返回键' }] },
  // 🔴 2026-09-05 补：此前**只有路由模型形式**（`#/inbox`）的移动端用例，
  //    扁平写法（端编码在场景名里）**一条都没有** —— 于是「给移动端起点拼 `end=`」
  //    这个改动**全绿地破坏了扁平形态**：拼上 `?end=mobile` 后路由查不到场景，
  //    回落到第一屏，表现是两条移动端路径稳定失败。
  //    ⭐ 两种寻址写法都得有正例，否则「只支持其中一种」不会被任何东西发现。
  { id: 'FLOW-MF', name: '扁平写法的移动端路径（端编码在场景名里，⛔ 不许拼 end=）',
    start: '#m-mobile-home', end: 'mobile',
    steps: [{ do: 'expect', textContains: '扁平移动端场景' }] }
];

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
  const t = mkdtempSync(join(tmpdir(), 'fw-st-'));
  const me = resolve(process.argv[1]);
  const fp = join(t, 'flows.json');
  writeFileSync(fp, JSON.stringify({ flows: ST_FLOWS }));
  const w = (n, c) => { const p = join(t, n); writeFileSync(p, c); return p; };
  const run = (p, ...extra) => {
    try { execFileSync(process.execPath, [me, p, '--flows', fp, ...extra], { stdio: 'pipe' }); return 0; }
    catch (e) { return e.status; }
  };
  console.log('M8 自证 —— 正例全绿 / 每类反例必红 / 无效输入报 2\n');
  const cases = [
    ['正例：6 条路径都走得通（Enter 提交 + 两种寻址写法的移动端各一条）', run(w('good.html', GOOD)), 0],
    ['反例①：按钮可访问名称改了（用例必须失效）', run(w('bad1.html', BAD_NAME)), 1],
    ['反例②：校验拦住了但焦点没移到第一个错误', run(w('bad2.html', BAD_FOCUS)), 1],
    ['反例③：Enter 提交不成立时 FLOW-K 必须红', run(w('bad3.html', BAD_ENTER), '--only', 'FLOW-K'), 1],
    ['反例④：demo 文件不存在 → 报 2', run(join(t, 'nope.html')), 2],
  ];
  let ok = true;
  // 反例④：flows.json 不存在 → 2
  let rc4;
  try { execFileSync(process.execPath, [me, w('g2.html', GOOD), '--flows', join(t, 'nope.json')], { stdio: 'pipe' }); rc4 = 0; }
  catch (e) { rc4 = e.status; }
  cases.push(['反例⑤：flows.json 不存在 → 报 2', rc4, 2]);
  for (const [name, got, want] of cases) {
    const g = got === want; ok &&= g;
    console.log(`  ${g ? '✅' : '❌'} ${name.padEnd(40)} 期望 ${want} 实得 ${got}`);
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
  rejectUnknown(argv, ['--flows','--only','--json','--self-test'],
    '用法: flow-walk-gate.mjs <demo.html> --flows <flows.json> [--json] [--only FLOW-01]');
  const files = argv.filter((a, i) => !a.startsWith('--') && argv[i - 1] !== '--flows' && argv[i - 1] !== '--only');
  const fi = argv.indexOf('--flows');
  const onlyI = argv.indexOf('--only');
  if (!files.length || fi < 0) {
    console.log('用法: flow-walk-gate.mjs <demo.html> --flows <flows.json> [--json] [--only FLOW-01]');
    process.exit(2);
  }
  const demo = files[0], flowsPath = argv[fi + 1];
  if (!existsSync(demo)) { console.error('UNABLE: demo 不存在 ' + demo); process.exit(2); }
  if (!flowsPath || !existsSync(flowsPath)) { console.error('UNABLE: flows.json 不存在 ' + flowsPath); process.exit(2); }
  let flows;
  try {
    const j = JSON.parse(readFileSync(flowsPath, 'utf8'));
    flows = Array.isArray(j) ? j : j.flows;
    if (!Array.isArray(flows) || !flows.length) throw new Error('flows 为空');
  } catch (e) { console.error('UNABLE: flows.json 解析失败：' + e.message); process.exit(2); }
  let rows;
  try { rows = await walk(demo, flows, onlyI > -1 ? argv[onlyI + 1] : null); }
  catch (e) { console.error('UNABLE: ' + e.message); process.exit(2); }
  process.exit(report(rows, argv.includes('--json')));
}
