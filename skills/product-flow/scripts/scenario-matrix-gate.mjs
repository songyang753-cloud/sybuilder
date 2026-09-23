#!/usr/bin/env node
// ============================================================================
// 状态矩阵门禁 —— spec/states.json 里每个「适用」的状态，必须**真的能被触发出来**。
//
// ═══ 它补的是哪个洞 ═══
// 交互规格里的状态清单长期只是一张表。表里写着「空态 / 失败 / 无权限」，
// 没有任何东西检查这些状态**在 demo 里点得到**。
// ⭐ 本 SOP 自己写过：「状态写在代码里 ≠ 用户点得到」，
//    而 S6 自动验收表的第 5 项「状态可触发」此前没有实现。
//
// 判据三条（都会红）：
//   ① 标了「适用」却没写 trigger  → 只写在文档里，等于没定义
//   ② 写了 trigger 但触发不出那个状态 → 规格与实现对不上
//   ③ demo 里出现了 states.json 没登记的状态 → 无需求发挥，后面不会有人测
//
// ⚠️ 依赖运行时把当前状态写在 `body[data-scene]`（`<界面id>-<端>-<状态>`），
//    并暴露 `window.__PROTO_SURFACES__`（界面 id → 路由路径）。
//    `templates/proto/` 的骨架自带这两样。
//
// 用法：
//   node scenario-matrix-gate.mjs <demo.html> --states <states.json> [--json]
//   node scenario-matrix-gate.mjs --self-test
// 退出码：0=矩阵齐全  1=有缺口  2=跑不了
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
  const _src = (await import('node:fs')).readFileSync(new URL(import.meta.url), 'utf8');
  console.log(_src.split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}

const PROBE = `(async (PLAN) => {
${HELPERS}
  const surfaces = window.__PROTO_SURFACES__ || null;
  if (!surfaces) return { err: '页面没有暴露 window.__PROTO_SURFACES__（界面 id → 路由路径）' };
  const out = [];
  for (const item of PLAN) {
    const path = surfaces[item.surface];
    if (!path) { out.push({ ...item, seen: [], note: '界面 id 在 __PROTO_SURFACES__ 里没有对应路由' }); continue; }
    location.hash = '/__matrix_reset__'; await sleep(30);
    location.hash = '/' + path + '?scn=' + item.trigger + (item.end && item.end !== 'pc' ? '&end=' + item.end : '');
    // ⚠️ 必须**在过渡过程中也采样**。只在落定后读，\`loading\` 永远观测不到 ——
    //    那会让门禁把「加载态做对了」判成「触发不出来」，
    //    ⛔ 而一道会把正确实现判红的门，最后一定会被人加豁免绕过去。
    const seen = [], comps = [], anch = {};
    const snap = () => {
      const v = document.body.getAttribute('data-scene'); if (v && seen.indexOf(v) < 0) seen.push(v);
      // 顺手把**实测到的**「场景 → 需求」锚点收下来（--dump 用）。
      // ⭐ 可运行原型的 data-scene/data-fr 是运行时写的，静态扫 HTML 一个也看不到 ——
      //   G2/G3 此前只会 UNABLE。锚点在这里是「走到了才记下」，
      //   与另写一张声明表不同：**它不可能与实现漂移，因为它就是实现吐出来的**。
      if (v) anch[v] = document.body.getAttribute('data-fr') || '';
      // 组件级状态：元素自己挂 data-el + data-state。
      // ⭐ 页面级 data-scene 表达不了它 —— 真实项目里组件级状态才是大多数
      //   （云端办公 Agent 22 个界面全部有业务状态，只有 8 个有页面级数据状态）。
      document.querySelectorAll('[data-el][data-state]').forEach(el => {
        const k = el.getAttribute('data-el') + ':' + el.getAttribute('data-state');
        if (comps.indexOf(k) < 0) comps.push(k);
      });
    };
    for (let i = 0; i < 12; i++) { await sleep(40); snap(); }
    await settle(8000); snap();
    let err = null;
    // 有些状态靠导航到不了（比如「保存失败」要先真的提交一次）。
    // 允许 states.json 写几步操作来把它逼出来 —— 步骤格式与 flows.json 一致。
    if (item.steps && item.steps.length) {
      try { for (const st of item.steps) { await doStep(st); snap(); } }
      catch (e) { err = String(e.message || e).slice(0, 200); }
      await settle(8000); snap();
    }
    out.push({ ...item, seen, comps, anch, note: err });
  }
  return { rows: out };
})(__PLAN__)`;

function buildPlan(states) {
  const plan = [], missing = [];
  // 组件级：绑在元素 slug 上，导航到它所在的界面 + 指定 scn 后，
  // 该元素必须真的出现在那个 data-state 上。
  for (const c of states.components || []) {
    for (const st of c.states || []) {
      if (!st.applicable) continue;
      if (!st.trigger) { missing.push(`元素 ${c.el} 的 ${st.state} 标了「适用」却没写 trigger`); continue; }
      if (!st.surface) { missing.push(`元素 ${c.el} 的 ${st.state} 没写 surface —— 不知道该导航到哪一屏去验它`); continue; }
      plan.push({ surface: st.surface, end: st.end || 'pc', comp: `${c.el}:${st.state}`,
                  trigger: st.trigger, steps: st.steps || null });
    }
  }
  for (const s of states.surfaces || []) {
    for (const st of s.states || []) {
      if (!st.applicable) continue;
      if (!st.trigger) { missing.push(`${s.id} 的 ${st.state} 标了「适用」却没写 trigger —— 只写在文档里，没有触发入口`); continue; }
      const ends = st.end ? [st.end] : (s.ends && s.ends.length ? s.ends : ['pc']);
      for (const end of ends)
        plan.push({ surface: s.id, end, state: st.state, trigger: st.trigger, steps: st.steps || null });
      // ⛔ 三选一没回答 = 到 S7 必然返工，这里当场报出来
      if (!s.endMode) missing.push(`界面 ${s.id} 没写 endMode（same / degraded / pc-only 三选一）`);
    }
  }
  return { plan, missing };
}

function judge(states, rows, missing) {
  const bad = [...missing];
  const declared = new Set();
  for (const s of states.surfaces || [])
    for (const st of s.states || [])
      for (const end of (s.ends && s.ends.length ? s.ends : ['pc']))
        declared.add(`${s.id}-${end}-${st.state}`);
  const seen = new Set();
  for (const r of rows) {
    if (r.comp) {                       // 组件级
      if (r.note) { bad.push(`${r.comp}：${r.note}`); continue; }
      if (!(r.comps || []).includes(r.comp))
        bad.push(`组件状态 ${r.comp}：scn=${r.trigger} 在 ${r.surface} 上只观测到 ` +
                 `${JSON.stringify(r.comps || [])} —— 规格与实现对不上`);
      continue;
    }
    const want = `${r.surface}-${r.end}-${r.state}`;
    (r.seen || []).forEach(v => seen.add(v));
    if (r.note) { bad.push(`${want}：${r.note}`); continue; }
    if (!(r.seen || []).includes(want))
      bad.push(`${want}：scn=${r.trigger}${r.steps ? ' + ' + r.steps.length + ' 步操作' : ''} 全程只出现过 ` +
               `${JSON.stringify(r.seen)} —— 规格与实现对不上`);
  }
  // ③ 反向：demo 里冒出来的状态，states.json 得登记过
  for (const o of seen)
    if (!declared.has(o)) bad.push(`demo 出现了未登记的状态「${o}」—— 无需求发挥，后面不会有人测它`);
  return bad;
}

function report(bad, total, asJson) {
  if (asJson) { console.log(JSON.stringify({ total, bad }, null, 1)); return bad.length ? 1 : 0; }
  console.log(`状态矩阵：需要触发 ${total} 项`);
  for (const b of bad) console.log('❌ ' + b);
  if (!bad.length)
    console.log('⚠️ 本门只验「适用的状态**触发得出来**」——'
      + '**不验触发出来的那一屏画得对不对**，也不验它是不是那个状态该有的样子。');
  console.log(bad.length ? `\n❌ ${bad.length} 项对不上` : '\n✅ 每个「适用」的状态都真的触发出来了');
  return bad.length ? 1 : 0;
}

// ---------------------------------------------------------------- 自证（M8）
const APP = `<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>t</title></head><body>
<main id="app">x</main>
<button data-el="btn-x" data-state="__COMPSTATE__">按钮</button>
<script>
window.__PROTO_SURFACES__ = { f01: 'inbox' };
function render(){
  var m=/scn=([\\w-]+)/.exec(location.hash); var scn=m?m[1]:'default';
  var map={ 'default':'success', 'empty':'empty', 'api-500':'__ERRSTATE__' };
  document.body.setAttribute('data-scene','f01-pc-'+(map[scn]||'success'));
  document.getElementById('app').textContent=scn;
}
window.addEventListener('hashchange',render); render();
</script></body></html>`;
const APP2 = APP.replace('__COMPSTATE__', 'default');
const GOOD = APP2.replace('__ERRSTATE__', 'error');
const BAD_WRONG = APP2.replace('__ERRSTATE__', 'success');     // 触发不出 error
const BAD_EXTRA = APP2.replace('__ERRSTATE__', 'weird-state'); // 冒出未登记的状态
for (const [n, s] of [['wrong', BAD_WRONG], ['extra', BAD_EXTRA]])
  if (s === GOOD) throw new Error('自证用例坏了：反例 ' + n + ' 与正例逐字相同');

const ST_SURFACES_PLACEHOLDER = [{ id: 'f01', name: '列表', ends: ['pc'], endMode: 'pc-only', states: [] }];
// ⭐ 新增「endMode 必填」这条要求时，**正例夹具也必须同时补上** ——
//   否则自证会把「门禁开始要求一件新东西」误报成「门禁坏了」。
//   这是本轮第三次踩「新增能力没同步正例」，所以写在这里当路标。
const ST_STATES = { surfaces: [{ id: 'f01', name: '列表', ends: ['pc'], endMode: 'pc-only', states: [
  { state: 'success', applicable: true, trigger: 'default' },
  { state: 'empty', applicable: true, trigger: 'empty' },
  { state: 'error', applicable: true, trigger: 'api-500' },
  { state: 'no-permission', applicable: false, why: '列表只读' }] }] };
// ⭐ 新增能力必须同时新增用例 —— 否则自证覆盖的是「加这个能力之前的那个程序」。
const BAD_COMP = APP.replace('__COMPSTATE__', 'somethingelse').replace('__ERRSTATE__', 'error');
if (BAD_COMP === GOOD) throw new Error('自证用例坏了：组件级反例与正例逐字相同');
const ST_COMP = { surfaces: ST_SURFACES_PLACEHOLDER, components: [
  { el: 'btn-x', states: [{ class: 'component', state: 'default', applicable: true,
                            trigger: 'default', surface: 'f01' }] }] };
const ST_COMP_NO_SURFACE = { surfaces: ST_SURFACES_PLACEHOLDER, components: [
  { el: 'btn-x', states: [{ class: 'component', state: 'default', applicable: true, trigger: 'default' }] }] };
// 反例：界面没回答双端三选一 —— ⛔ 不回答＝到 S7 必然返工
// 🆕 2026-09-05 `unexecuted-check` 实测：**界面状态**那一路的 `note` 分支
//    （`if (r.note) { bad.push(...) }`，L122）自证期间一次都没执行过 ——
//    组件那一路（L114）有用例，界面这一路没有。**同一形状的两条路，只测了一条。**
//    note 来自「界面 id 在 __PROTO_SURFACES__ 里没有对应路由」。
const ST_GHOST_SURFACE = { surfaces: [{ id: 'f99-不存在的界面', name: '幽灵', ends: ['pc'],
  endMode: 'pc-only', states: [{ state: 'success', applicable: true, trigger: 'default' }] }] };
const ST_NO_ENDMODE = { surfaces: [{ id: 'f01', name: '列表', ends: ['pc'], states: [
  { state: 'success', applicable: true, trigger: 'default' }] }] };
const ST_NO_TRIGGER = { surfaces: [{ id: 'f01', ends: ['pc'], endMode: 'pc-only', states: [
  { state: 'success', applicable: true, trigger: 'default' },
  { state: 'error', applicable: true }] }] };   // 适用却没 trigger

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
  const t = mkdtempSync(join(tmpdir(), 'sm-st-'));
  const me = resolve(process.argv[1]);
  const w = (n, c) => { const p = join(t, n); writeFileSync(p, c); return p; };
  const j = (n, o) => { const p = join(t, n); writeFileSync(p, JSON.stringify(o)); return p; };
  const run = (html, states) => {
    try { execFileSync(process.execPath, [me, html, '--states', states], { stdio: 'pipe' }); return 0; }
    catch (e) { return e.status; }
  };
  const okStates = j('ok.json', ST_STATES);
  console.log('M8 自证 —— 正例绿 / 三类反例各自必红 / 无效输入报 2\n');
  const cases = [
    ['正例：三个适用状态都触发得出来', run(w('good.html', GOOD), okStates), 0],
    ['反例①：适用却没写 trigger', run(w('g2.html', GOOD), j('nt.json', ST_NO_TRIGGER)), 1],
    ['反例②：trigger 触发不出那个状态', run(w('bad1.html', BAD_WRONG), okStates), 1],
    ['反例③：demo 冒出未登记的状态', run(w('bad2.html', BAD_EXTRA), okStates), 1],
    ['正例②：组件级状态观测得到', run(w('g4.html', GOOD), j('comp.json', ST_COMP)), 0],
    ['反例⑥：组件处在别的 data-state', run(w('bad3.html', BAD_COMP), j('comp2.json', ST_COMP)), 1],
    ['反例⑦：组件级没写 surface（不知道去哪验）', run(w('g5.html', GOOD), j('comp3.json', ST_COMP_NO_SURFACE)), 1],
    ['反例⑧：界面没回答双端三选一 endMode', run(w('g6.html', GOOD), j('nem.json', ST_NO_ENDMODE)), 1],
    ['反例⑨：界面 id 没有对应路由（界面路的 note 分支）',
     run(w('g7.html', GOOD), j('ghost.json', ST_GHOST_SURFACE)), 1],
    ['反例④：demo 不存在 → 报 2', run(join(t, 'nope.html'), okStates), 2],
    ['反例⑤：states.json 不存在 → 报 2', run(w('g3.html', GOOD), join(t, 'nope.json')), 2],
  ];
  let ok = true;
  for (const [name, got, want] of cases) {
    const g = got === want; ok &&= g;
    console.log(`  ${g ? '✅' : '❌'} ${name.padEnd(38)} 期望 ${want} 实得 ${got}`);
  }
  console.log(`\n${ok ? '✅ 自证通过：这道门会出声' : '❌ 自证失败：先修门禁'}`);
  process.exit(ok ? 0 : 1);
}

// ---------------------------------------------------------------- main
const argv = process.argv.slice(2);
if (argv.includes('--self-test')) { await selfTest(); }
else {
  const si = argv.indexOf('--states');
  // ⚠️ 未知 `--flag` 必须报错：静默丢弃会让门禁只跑一半而照样报绿（见 _argv.mjs）
  //    本门禁尤其危险 —— `--all-route`（少个 s）会让它只审打开时那一屏。
  rejectUnknown(argv, ['--states','--json','--dump','--self-test'],
    '用法: scenario-matrix-gate.mjs <demo.html> --states <states.json> [--json]');
  const files = argv.filter((a, i) => !a.startsWith('--') && argv[i - 1] !== '--states' && argv[i - 1] !== '--dump');
  if (!files.length || si < 0) {
    console.log('用法: scenario-matrix-gate.mjs <demo.html> --states <states.json> [--json]');
    process.exit(2);
  }
  const demo = files[0], sp = argv[si + 1];
  if (!existsSync(demo)) { console.error('UNABLE: demo 不存在 ' + demo); process.exit(2); }
  if (!sp || !existsSync(sp)) { console.error('UNABLE: states.json 不存在 ' + sp); process.exit(2); }
  let states;
  try { states = JSON.parse(readFileSync(sp, 'utf8')); if (!states.surfaces) throw new Error('缺 surfaces'); }
  catch (e) { console.error('UNABLE: states.json 解析失败：' + e.message); process.exit(2); }
  const { plan, missing } = buildPlan(states);
  let res;
  try { [res] = await evalInPage(demo, '1440x900', [PROBE.replace('__PLAN__', JSON.stringify(plan))]); }
  catch (e) { console.error('UNABLE: ' + e.message); process.exit(2); }
  if (res && res.err) { console.error('UNABLE: ' + res.err); process.exit(2); }
  const di = argv.indexOf('--dump');
  if (di >= 0) {
    // 实测锚点导出：给 G2/G3 当输入。**只导出真的走到过的场景**，
    // 走不到的不会出现在这里 —— 于是「没走到」在下游表现为「没有这个场景」，
    // 而不是被一张手写表补成「有」。⛔ 声明式的场景表正是这么变成家具的。
    const map = {};
    for (const r of res.rows) for (const k of Object.keys(r.anch || {})) map[k] = r.anch[k];
    const rows = Object.keys(map).sort().map(k => ({ scene: k, fr: map[k] }));
    writeFileSync(argv[di + 1], JSON.stringify({ measuredBy: 'scenario-matrix-gate', scenes: rows }, null, 1));
    console.log('已导出实测锚点 ' + rows.length + ' 条 → ' + argv[di + 1]);
  }
  process.exit(report(judge(states, res.rows, missing), plan.length, argv.includes('--json')));
}
