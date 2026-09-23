// ============================================================================
// mock 接缝门禁（S6 出场）—— 验可运行原型的**唯一存在理由**
//
// 骨架 README 与 `20-api.js` 头部都写着：
//   「把 api.js 整体换成真 fetch，其余三层**一行都不用改**。」
// 这句话是 deviation-free 的全部内容 —— 交互稿之所以能声称「和真实实现一致」，
// 靠的就是它。⛔ 而它是一句**声称**，此前没有任何东西验过。
//
// 🚨 2026-09-04 实测：那句话**当时是假的**。
//    `P.scenarios` 与 `P.currentScenario` 都定义在 mock 层，
//    删掉 mock 层后 `boot` 直接抛「Cannot convert undefined or null to object」，
//    页面上只剩演示外壳（端切换器/主题切换器），**产品内容一个字都不渲染**。
//    ⭐ 一份「换上真接口就散架」的交互稿，不能声称与真实实现一致。
//
// 判据：把 mock 三件套（fixtures/scenarios）删掉、api 换成 fetch 桩，
//       然后要求 ①boot 不抛 ②`body[data-scene]` 非空 ③内容区渲染出了服务端数据。
// 退出码：0=接缝成立  1=换上真接口就散架  2=跑不了
// ============================================================================
import { existsSync, readFileSync, writeFileSync, mkdtempSync, mkdirSync } from 'node:fs';
import { join, resolve, basename } from 'node:path';
import { tmpdir } from 'node:os';
import { evalInPage, browserPreflight } from './_browser.mjs';
import { rejectUnknown } from './_argv.mjs';

// 登记册#1：--help 只显示帮助（文件头注释）并退 0
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  const _src = (await import('node:fs')).readFileSync(new URL(import.meta.url), 'utf8');
  console.log(_src.split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}

// mock 层的文件名约定，见 templates/proto/README.md
const MOCK = ['00-fixtures.js', '10-scenarios.js'];
const API = '20-api.js';

const FETCH_API = `<script>
(function (P) { 'use strict';
  var n = 0;
  function busy(d){ n += d; document.body.setAttribute('data-busy', n > 0 ? '1' : ''); }
  function req(u, o){
    busy(1);
    return fetch(u, o).then(function(r){
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    }).finally(function(){ busy(-1); });
  }
  P.api = {
    listTasks:  function(){ return req('/api/list'); },
    getTask:    function(i){ return req('/api/item/' + i); },
    createTask: function(){ return req('/api/create', {method:'POST'}); },
    updateTask: function(i){ return req('/api/item/' + i, {method:'PATCH'}); },
    deleteTask: function(i){ return req('/api/item/' + i, {method:'DELETE'}); },
    can: function(){ return true; }
  };
})(window.PROTO = window.PROTO || {});
window.fetch = function (u) {
  var db = [{ id:'seam-1', title:'接缝校验用数据甲', status:'todo', owner:'甲' },
            { id:'seam-2', title:'接缝校验用数据乙', status:'doing', owner:'乙' }];
  var b = /\\/api\\/item\\//.test(u) ? db[0] : { items: db, total: db.length };
  return Promise.resolve({ ok:true, status:200, json:function(){ return Promise.resolve(b); } });
};
</script>`;

function bundle(srcDir, swap) {
  const idx = join(srcDir, 'index.html');
  if (!existsSync(idx)) return null;
  let html = readFileSync(idx, 'utf8');
  // ⚠️ 2026-09-05：探针的 out.threw 只在**读 DOM 时**抛才会被设置 ——
  //    它**根本看不见页面加载期的异常**。于是「mock 层一删就炸」这一类
  //    只能靠「没锚点/没数据」间接红，报出来的是「boot 没跑完」，
  //    而**真正的异常原文丢了** —— 判据在，诊断指错方向。
  //    ⇒ 在所有脚本之前注入收集器，让「页面抛异常」这条判据真正可达。
  const COLLECTOR = '<script>window.__seamErr=[];'
    + 'addEventListener("error",function(e){__seamErr.push(String((e.error&&e.error.message)||e.message||e));});'
    + 'addEventListener("unhandledrejection",function(e){__seamErr.push("unhandled rejection: "+String((e.reason&&e.reason.message)||e.reason));});'
    + '</script>';
  html = /<body[^>]*>/i.test(html)
    ? html.replace(/(<body[^>]*>)/i, '$1' + COLLECTOR)
    : COLLECTOR + html;
  html = html.replace(/<link rel="stylesheet" href="([^"]+)">/g, (_, f) => {
    const p = join(srcDir, f);
    return existsSync(p) ? '<style>\n' + readFileSync(p, 'utf8') + '\n</style>' : '';
  });
  html = html.replace(/<script src="([^"]+)"><\/script>/g, (_, f) => {
    const name = basename(f), p = join(srcDir, f);
    if (swap && MOCK.includes(name)) return '<script>/* mock 层已删除 */</script>';
    if (swap && name === API) return FETCH_API;
    return existsSync(p) ? '<script>\n' + readFileSync(p, 'utf8') + '\n</script>' : '';
  });
  return html;
}

const PROBE = `(function () {
  var out = { threw: null, scene: null, text: '' };
  try {
    var errs = window.__seamErr || [];
    if (errs.length) out.threw = errs.join(' | ');
    out.scene = document.body.getAttribute('data-scene');
    var main = document.getElementById('app') || document.body;
    out.text = (main.innerText || '').replace(/\\s+/g, ' ').slice(0, 400);
  } catch (e) { out.threw = String(e && e.message || e); }
  return JSON.stringify(out);
})()`;

async function check(srcDir, marker) {
  const html = bundle(srcDir, true);
  if (html === null) return { rc: 2, why: '找不到 ' + join(srcDir, 'index.html') };
  const d = mkdtempSync(join(tmpdir(), 'seam-'));
  const f = join(d, 'seam.html');
  writeFileSync(f, html);
  let raw;
  try { [raw] = await evalInPage(f, '1440x900', [PROBE]); }
  catch (e) {
    // ⛔ 不许把**环境起不来**说成**产品崩了**。
    // 2026-09-05 实测：连跑 30 道门时本机已有 12 个 Chrome（别的会话），
    // 这里 catch 到「CDP 端口没起来」，却报成「换上真接口后页面直接崩了」——
    // 一次不可复现的红，读起来像产品缺陷。_browser.mjs 的契约是基建失败要冒泡成 2。
    const m = String((e && e.message) || e);
    const INFRA = /找不到无头 Chrome|CDP 端口没起来|目标不存在|ETIMEDOUT|EADDRINUSE|socket hang up|WebSocket/;
    if (INFRA.test(m)) return { rc: 2, why: '浏览器起不来（环境问题，不是产品问题）：' + m.slice(0, 120) };
    return { rc: 1, why: '换上真接口后页面直接崩了：' + m.slice(0, 120) };
  }
  let r;
  try { r = JSON.parse(raw); } catch { return { rc: 2, why: '探针返回不是 JSON' }; }
  const bad = [];
  if (r.threw) bad.push('页面抛异常：' + r.threw);
  // ⚠️ 这道门**不该**把空白页判成「没量到」：它验的就是 boot 有没有真跑起来，
  //   空白页正是它要抓的缺陷。（同日 browser-audit / platform-parity 改成了 UNABLE，
  //   因为那两道验的是「渲染出来的东西怎么样」和「两端对不对得上」—— 没东西就没得判。
  //   ⛔ 一致性不是目标：**判据该说什么，取决于它验的是什么**。）
  //   只补一句降低误诊成本的提示：传错目录和 boot 挂了，在产物上长得一模一样。
  if (!r.scene) bad.push('`body[data-scene]` 为空 —— boot 没跑完（锚点是 boot 写的）。'
                         + '若整页空白，先确认目录传对了：传错目录与 boot 挂掉在产物上一模一样');
  if (!r.text.includes(marker))
    bad.push('内容区没有渲染出服务端数据（找不到「' + marker + '」）—— ' +
             '实得：' + (r.text.slice(0, 90) || '（空）'));
  return { rc: bad.length ? 1 : 0, bad, scene: r.scene, text: r.text.slice(0, 90) };
}

function report(res) {
  if (res.rc === 2) { console.error('UNABLE: ' + res.why); return 2; }
  if (res.rc === 1) {
    console.log('❌ mock 接缝不成立 —— **换上真接口这份稿子就散架**');
    (res.bad || [res.why]).forEach(b => console.log('   · ' + b));
    console.log('\n⛔ 骨架声称「把 api.js 整体换成真 fetch，其余三层一行都不用改」。' +
      '\n   这句话是 deviation-free 的全部内容 —— 它不成立，' +
      '交互稿就不能声称与真实实现一致。' +
      '\n⭐ 常见病因：视图/路由/外壳直接读了 `P.scenarios` 或 `P.fixtures`（它们只在 mock 层存在）。');
    return 1;
  }
  console.log('✅ mock 接缝成立：删掉 mock 层、api 换成真 fetch 之后，');
  console.log('   场景锚点仍在（' + res.scene + '），内容区渲染的是**服务端来的数据**');
  console.log('⚠️ 绿只说明这条接缝没断，不说明 api.js 的方法签名与后端真的对得上 ——');
  console.log('   那要靠 `spec/operations.json` 与研发对一遍。');
  return 0;
}

// ─────────────────────────── 自证 ───────────────────────────
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
  const d = mkdtempSync(join(tmpdir(), 'seam-st-'));
  const mk = (name, extra) => {
    const dir = join(d, name);
    mkdirSync(join(dir, 'js'), { recursive: true });
    writeFileSync(join(dir, 'index.html'),
      '<body><main id="app"></main>' +
      '<script src="js/00-fixtures.js"></script>' +
      '<script src="js/10-scenarios.js"></script>' +
      '<script src="js/20-api.js"></script>' +
      '<script src="js/90-boot.js"></script></body>');
    writeFileSync(join(dir, 'js/00-fixtures.js'),
      'window.PROTO=window.PROTO||{};PROTO.fixtures={tasks:[{id:"m1",title:"mock 数据"}]};');
    writeFileSync(join(dir, 'js/10-scenarios.js'),
      'PROTO.scenarios={default:{desc:"正常"}};PROTO.currentScenario=function(){return{name:"default",cfg:{}}};');
    writeFileSync(join(dir, 'js/20-api.js'),
      'PROTO.api={listTasks:function(){return Promise.resolve({items:PROTO.fixtures.tasks});}};');
    writeFileSync(join(dir, 'js/90-boot.js'), extra);
    return dir;
  };
  // 正例：boot 对 mock 层做了兜底
  const OK = mk('ok', `
    PROTO.currentScenario = PROTO.currentScenario || function(){ return {name:'default',cfg:{}}; };
    PROTO.api.listTasks().then(function(r){
      document.getElementById('app').textContent = r.items.map(function(t){return t.title;}).join(' ');
      document.body.setAttribute('data-scene','f01-pc-success');
    });`);
  // 反例①：直接读 PROTO.scenarios（mock 层删掉后必炸）
  const BAD1 = mk('bad1', `
    var n = Object.keys(PROTO.scenarios).length;
    PROTO.api.listTasks().then(function(r){
      document.getElementById('app').textContent = r.items.map(function(t){return t.title;}).join(' ');
      document.body.setAttribute('data-scene','f01-pc-success');
    });`);
  // 反例④：**渲染都成功了**，之后才抛 —— 用来隔离「页面抛异常」这一条。
  //   ⚠️ 2026-09-05 变异实测：这条判据此前**没有任何反例守着** ——
  //   反例①（mock 层一删就炸）是靠「没锚点/没数据」红的，抛不抛无关。
  //   一个判据可以整条删掉而自证全绿，正是因为别的判据把它遮住了。
  const BAD4 = mk('bad4', `
    PROTO.currentScenario = PROTO.currentScenario || function(){ return {name:'default',cfg:{}}; };
    PROTO.api.listTasks().then(function(r){
      document.getElementById('app').textContent = r.items.map(function(t){return t.title;}).join(' ');
      document.body.setAttribute('data-scene','f01-pc-success');
      throw new Error('渲染完成之后才抛');
    });`);
  // 反例②：不抛，但锚点没写（boot 没跑完）
  const BAD2 = mk('bad2', `
    PROTO.currentScenario = PROTO.currentScenario || function(){ return {name:'default',cfg:{}}; };
    PROTO.api.listTasks().then(function(r){
      document.getElementById('app').textContent = r.items.map(function(t){return t.title;}).join(' ');
    });`);
  // 反例③：渲染的是**写死的 mock 文案**而不是接口返回的数据
  const BAD3 = mk('bad3', `
    PROTO.currentScenario = PROTO.currentScenario || function(){ return {name:'default',cfg:{}}; };
    document.getElementById('app').textContent = '写死的示例数据';
    document.body.setAttribute('data-scene','f01-pc-success');`);

  const cases = [
    ['正例 boot 对 mock 层有兜底，换上真接口仍渲染服务端数据', OK, 0],
    ['反例① 直接读 PROTO.scenarios（mock 层一删就抛）', BAD1, 1],
    ['反例④ 渲染成功但事后抛（隔离「页面抛异常」这一条）', BAD4, 1],
    ['反例② 不抛但没写场景锚点（boot 没跑完）', BAD2, 1],
    ['反例③ 渲染的是写死文案，不是接口返回的数据', BAD3, 1],
  ];
  let ok = true;
  console.log('M8 自证 —— 正例绿 / 三类反例各自必红\n');
  for (const [name, dir, want] of cases) {
    let got;
    try { got = (await check(dir, '接缝校验用数据甲')).rc; } catch { got = 2; }
    const g = got === want; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${name.padEnd(44)} 期望 ${want} 实得 ${got}`);
  }
  // 无效输入
  let rc; try { rc = (await check(join(d, 'nope'), 'x')).rc; } catch { rc = 2; }
  const g = rc === 2; ok = ok && g;
  console.log(`  ${g ? '✅' : '❌'} ${'目录不存在 → 报 2（不许折叠成 0）'.padEnd(44)} 期望 2 实得 ${rc}`);
  // 🆕 2026-09-05 `--unable` 实测：`report()` 里「透传内层 rc=2」那一行从没执行过 ——
  //    上面这条用例**直接调 check() 读 .rc**，绕过了 report()。
  //    ⭐ 「内部函数返回对了」不等于「命令行跑出来是对的」：中间那层可能把它丢了。
  //    ⇒ 走一次真正的命令行路径。
  {
    const { execFileSync } = await import('node:child_process');
    let sub = 0;
    try {
      execFileSync(process.execPath, [resolve(process.argv[1]), join(d, 'nope')],
                   { stdio: 'pipe' });
    } catch (e) { sub = e.status; }
    const g2 = sub === 2; ok = ok && g2;
    console.log(`  ${g2 ? '✅' : '❌'} ${'命令行跑：目录不存在 → 退出码 2'.padEnd(44)} 期望 2 实得 ${sub}`);
  }
  console.log(`\n${ok ? '✅ 自证通过：这道门会出声' : '❌ 自证失败：先修门禁'}`);
  process.exit(ok ? 0 : 1);
}

const argv = process.argv.slice(2);
if (argv.includes('--self-test')) { await selfTest(); }
else {
  rejectUnknown(argv, ['--marker', '--self-test'],
    '用法: mock-seam-gate.mjs <骨架源码目录> [--marker <期望出现的服务端数据文案>]');
  const files = argv.filter((a, i) => !a.startsWith('--') && argv[i - 1] !== '--marker');
  if (!files.length) { console.error('UNABLE: 没给骨架源码目录（含 index.html 与 js/）'); process.exit(2); }
  const mi = argv.indexOf('--marker');
  const marker = mi >= 0 ? argv[mi + 1] : '接缝校验用数据';
  try { process.exit(report(await check(resolve(files[0]), marker))); }
  catch (e) { console.error('UNABLE: ' + e.message); process.exit(2); }
}
