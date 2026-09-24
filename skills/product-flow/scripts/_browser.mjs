// ============================================================================
// 共用的无头浏览器通道 —— findChrome + CDP 求值。
//
// 为什么单独一份：`browser-audit.mjs` 与 `dead-click-gate.mjs` 都要开无头 Chrome。
// 复制两份 findChrome 的后果是**其中一份会先过期**，而过期的那份只会安静地
// 报 UNABLE（"找不到浏览器"），看起来像环境问题，不像代码问题。
// 本 SOP 已经记过这条：复述一次就多一处会过期的副本。
//
// ⚠️ 本模块**不做任何判据**，只负责「把一段 JS 送进真实渲染的页面并把结果取回来」。
// ============================================================================
import { spawn } from 'node:child_process';
import { existsSync, readdirSync, mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { tmpdir, homedir } from 'node:os';

/** 按优先级找一个能用的 Chromium。找不到返回 null（调用方负责报 UNABLE 而不是折叠成通过）。 */
export function findChrome() {
  // 🚨 2026-09-14 CI 首次在 Linux runner 上跑才暴露：原清单里 ms-playwright 只写了
  //   **macOS 路径**（~/Library/Caches/ms-playwright），而 **Linux 上是 ~/.cache/ms-playwright**。
  //   ⭐ 本机是 macOS，所以这个可移植性缺口在本地**永远看不见**。
  //   ⚠️ 同理补上 PUPPETEER_CACHE_DIR / PLAYWRIGHT_BROWSERS_PATH 两个官方环境变量 ——
  //     CI 里改缓存位置是常规做法，写死家目录会让「装了却找不到」变成静默 UNABLE。
  const roots = [join(homedir(), '.cache/puppeteer/chrome-headless-shell'),
                 join(homedir(), '.cache/puppeteer/chrome'),
                 join(homedir(), '.cache/ms-playwright'),
                 join(homedir(), 'Library/Caches/ms-playwright')];
  for (const env of ['PUPPETEER_CACHE_DIR', 'PLAYWRIGHT_BROWSERS_PATH']) {
    const v = process.env[env];
    if (v && v !== '0') roots.unshift(v,
      join(v, 'chrome-headless-shell'), join(v, 'chrome'));
  }
  const found = [];
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const ver of readdirSync(root)) {
      const vd = join(root, ver);
      let inner; try { inner = readdirSync(vd); } catch { continue; }
      for (const d of [...inner, '.'])
        for (const bin of ['chrome-headless-shell',
                           'Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
                           'chrome', 'Chromium.app/Contents/MacOS/Chromium', 'headless_shell'])
          if (existsSync(join(vd, d, bin))) found.push({ ver, path: join(vd, d, bin) });
    }
  }
  if (found.length) {
    found.sort((a, b) => b.ver.localeCompare(a.ver, undefined, { numeric: true }));
    return found[0].path;
  }
  for (const p of ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                   '/Applications/Chromium.app/Contents/MacOS/Chromium'])
    if (existsSync(p)) return p;
  return null;
}

/** 自测/运行前的环境预检：**真起一次**无头浏览器并取回求值结果（二进制在场≠能起动——
 * Codex 三审 0.5.4：无浏览器环境里 45 个「失败」全是环境码，根因就是自测没有这一步）。
 * 返回 false=环境不可用 → 调用方打印 UNABLE 并退 2：环境缺席≠测出失败≠通过。
 * PF_FORCE_NO_BROWSER=1 恒 false：旋钮只能把结果推向 UNABLE，推不成 PASS（方向安全，不违 B20）。 */
export async function browserPreflight() {
  if (process.env.PF_FORCE_NO_BROWSER) return false;
  if (!findChrome()) return false;
  const tmp = mkdtempSync(join(tmpdir(), 'pb-pf-'));
  const f = join(tmp, 'pf.html');
  writeFileSync(f, '<title>pf</title><body>pf</body>');
  try { const [r] = await evalInPage(f, '800x600', ['1+1']); return r === 2; }
  catch { return false; }
  finally { rmSync(tmp, { recursive: true, force: true }); }
}

export function toUrl(target) {
  return /^https?:/.test(target) ? target : pathToFileURL(resolve(target)).href;
}


// ═══ 起跑自清（2026-09-08 凌晨 fd 危机后立）═══
// 本机常有会话按「ppid=1/无 tty」无差别清后台，浏览器门禁被杀后 chrome 孤儿会留下 ——
// 一晚累计 297 个，把内核文件表吃光（errno 23），全机测量瘫痪。
// 约定（与 验证项目 会话对齐）：各工具只认领**自己前缀**的孤儿。本 skill 的实例
// 历史上按前缀清理不构成所有权证明，已停止自动扫描/杀孤儿。
// 以下函数仅供诊断兼容；实际清理只处理本次创建的 ChildProcess/进程组。
export function isOurOrphan(psLine) {
  // psLine 形如 "  PID  PPID COMMAND…"；返回 [pid] 或 null
  const m = psLine.match(/^\s*(\d+)\s+1\s+(.*)$/);
  if (!m) return null;
  const arg = m[2].match(/--user-data-dir=(\S+)/)?.[1];
  return arg && resolve(arg).startsWith(resolve(tmpdir()) + '/pb-') && /\/pb-[^/]+\/ud$/.test(arg) ? m[1] : null;
}

/**
 * 开一个页面，依次求值若干段表达式，返回结果数组。
 * @param {string} target        文件路径或 http(s) URL
 * @param {string} viewport      '1440x900'
 * @param {string[]} expressions 每段都当作**表达式**求值；返回 Promise 时会被 await
 * @param {{coarsePointer?: boolean, reducedMotion?: boolean}} opts
 *        coarsePointer=true 时真的模拟触屏指针；reducedMotion=true 时真的模拟
 *        prefers-reduced-motion: reduce（**这样才量得到「降级之后长什么样」**，
 *        而不是只查「有没有写那个 @media 分支」——有分支不等于降级到位）
 *        （⚠️ 仅把窗口调窄**不会**让 matchMedia('(pointer: coarse)') 变真 ——
 *          门禁若按宽度就套触屏阈值，而页面的 @media (pointer: coarse) 不生效，
 *          就会出现「门禁要求 44px，而正确写法根本没机会生效」的死结）
 * @returns {Promise<any[]>}
 * ⚠️ 任何一步失败都 throw，调用方必须让它冒泡成退出码 2 —— 不许 catch 成「通过」。
 */
export async function evalInPage(target, viewport, expressions, opts = {}) {
  // ⛔ 本地文件必须先确认存在：Chrome 对不存在的路径会**正常加载一张错误页**，
  //    页面里的求值照常成功 —— 于是上层门禁会去测量那张错误页并得出结论。
  //    四道门禁目前各自都做了 existsSync 前置检查，但守卫应当在**取数通道本身**：
  //    上层漏一次，就会把「没量到」当成「量到了 0」。
  if (!/^https?:/i.test(String(target)) && !existsSync(target))
    throw new Error('目标不存在：' + target + '（⛔ 不许对错误页取数）');
  // 🚨 2026-09-14 CI 连查 4 轮才定位到：Node 20 上**没有 `WebSocket` 全局**
  //   （它 Node 21 才加入、22 稳定），于是下面 `new WebSocket(ws)` 直接 ReferenceError，
  //   被上层折成一句「起不了无头浏览器」——**浏览器其实好好的，是 Node 版本不够**。
  //   ⭐ 本机是 Node 26，所以这一条在本地**永远看不见**。
  //   ⇒ 提前检查并给出**能照做**的错误，⛔ 不要把版本问题伪装成浏览器问题。
  if (typeof WebSocket === 'undefined')
    throw new Error('Node ' + process.versions.node
      + ' 没有 WebSocket 全局（需 Node ≥21，建议 ≥22）—— ⛔ 这不是浏览器的问题，是运行时版本');
  if (process.platform === 'win32') throw new Error('UNABLE: browser process-group cleanup requires POSIX');
  for (const key of ['requestTimeoutMs', 'timeoutMs']) {
    if (opts[key] !== undefined && (!Number.isFinite(opts[key]) || opts[key] <= 0))
      throw new Error('UNABLE: invalid ' + key);
  }
  const chrome = findChrome();
  if (!chrome) throw new Error('找不到无头 Chrome（~/.cache/puppeteer、~/.cache/ms-playwright、~/Library/Caches/ms-playwright 或 /Applications）');
  // Never kill processes found by name/profile heuristics: PPID/path is not ownership.
  const [w, h] = viewport.split('x').map(Number);
  if (![w, h].every(n => Number.isInteger(n) && n > 0)) throw new Error('UNABLE: invalid viewport');
  const tmp = mkdtempSync(join(tmpdir(), 'pb-'));
  const proc = spawn(chrome, ['--headless=new', '--disable-gpu',
    '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1', `--window-size=${w},${h}`, '--no-first-run',
    `--user-data-dir=${tmp}/ud`, toUrl(target)], { stdio: 'ignore', detached: process.platform !== 'win32' });
  let launchError, sock, overall;
  proc.on('error', error => { launchError = error; });
  const pend = new Map();
  let interrupt;
  const stop = () => {
    launchError = new Error('UNABLE: browser interrupted or deadline exceeded');
    interrupt?.(launchError);
    try { sock?.close(); } catch {}
  };
  process.once('SIGINT', stop); process.once('SIGTERM', stop);
  overall = setTimeout(stop, opts.timeoutMs ?? 90000);
  try {
  let ws = null;
  for (let i = 0; i < 80 && !ws; i++) {
    if (launchError) throw launchError;
    if (proc.exitCode !== null) throw new Error('Browser exited before CDP was ready');
    await new Promise(r => setTimeout(r, 250));
    try {
      const [port, browserPath] = readFileSync(join(tmp, 'ud/DevToolsActivePort'), 'utf8').trim().split('\n');
      if (!/^\d+$/.test(port) || !browserPath?.startsWith('/devtools/browser/')) continue;
      const endpoint = `http://127.0.0.1:${port}`;
      const version = await (await fetch(endpoint + '/json/version', { signal: AbortSignal.timeout(1000) })).json();
      const ownedEndpoint = url => { const u = new URL(url); return u.protocol === 'ws:' && u.hostname === '127.0.0.1' && u.port === port; };
      if (!ownedEndpoint(version.webSocketDebuggerUrl) || new URL(version.webSocketDebuggerUrl).pathname !== browserPath) continue;
      const list = await (await fetch(endpoint + '/json/list', { signal: AbortSignal.timeout(1000) })).json();
      const pg = list.find(t => t.type === 'page' && t.url === toUrl(target) && t.webSocketDebuggerUrl);
      if (pg && ownedEndpoint(pg.webSocketDebuggerUrl)) ws = pg.webSocketDebuggerUrl;
    } catch { /* 端口还没起来 */ }
  }
  if (launchError) throw launchError;
  if (!ws) throw new Error('Owned CDP target unavailable');
  sock = new WebSocket(ws);
  let id = 0;
  const rejectPending = error => { for (const p of pend.values()) { clearTimeout(p.timer); p.reject(error); } pend.clear(); };
  const send = (method, params) => new Promise((resolve, reject) => {
    if (sock.readyState !== WebSocket.OPEN) return reject(new Error('CDP is not open'));
    const i = ++id;
    const timer = setTimeout(() => { pend.delete(i); reject(new Error('CDP timeout: ' + method)); }, opts.requestTimeoutMs ?? 15000);
    pend.set(i, { resolve, reject, timer });
    try { sock.send(JSON.stringify({ id: i, method, params })); }
    catch (error) { clearTimeout(timer); pend.delete(i); reject(error); }
  });
  sock.onmessage = ev => {
    try { const m = JSON.parse(ev.data); const p = pend.get(m.id); if (p) {
      clearTimeout(p.timer); pend.delete(m.id); m.error ? p.reject(new Error('CDP request failed')) : p.resolve(m);
    } } catch { rejectPending(new Error('Invalid CDP response')); }
  };
  const done = new Promise((res, rej) => {
    const fail = error => { rejectPending(error); rej(error); };
    interrupt = fail;
    sock.onerror = () => fail(new Error('CDP 连接失败'));
    sock.onclose = () => fail(new Error('CDP disconnected'));
    sock.onopen = async () => {
      try {
        await send('Runtime.enable', {});
        await send('Page.enable', {});
        // 🚨🚨 2026-09-04：`--window-size` 在 macOS 上有**最小宽度限制**（实测约 500px）——
        //    请求 390x844 实得 innerWidth = **500**，请求 414 也是 500。
        //    ⛔ 后果极重：**所有「移动端」测量其实都跑在 500px 上** ——
        //      端形态门、browser-audit 的移动视口、flow-walk 的移动端路径，全部如此。
        //    ⭐ 这是「量具本身错了」那一类：所有基于它的结论都要重估，
        //      而它一直安静地报着看起来正常的数字。
        //    ⇒ 改用 CDP 的 `Emulation.setDeviceMetricsOverride`（无最小值限制）。
        //      `mobile:true` 顺带让触屏语义成立，与 coarsePointer 不冲突。
        await send('Emulation.setDeviceMetricsOverride', {
          // ⚠️ `mobile: true` 会启用移动端**布局视口**：页面若没有 viewport meta，
          //    CSS 宽度会退回 980 的默认值（实测 390 请求实得 980）。
          //    触屏语义由 `coarsePointer` 单独管，这里只要 CSS 像素宽等于请求宽。
          width: w, height: h, deviceScaleFactor: 1, mobile: false,
        });
        const feats = [];
        if (opts.coarsePointer) feats.push(
          { name: 'pointer', value: 'coarse' }, { name: 'any-pointer', value: 'coarse' },
          { name: 'hover', value: 'none' }, { name: 'any-hover', value: 'none' });
        if (opts.reducedMotion) feats.push({ name: 'prefers-reduced-motion', value: 'reduce' });
        if (feats.length) {
          await send('Emulation.setEmulatedMedia', { features: feats });
          if (opts.coarsePointer)
            await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
          await send('Page.reload', {});          // 媒体特性要在重新求值前生效
          await new Promise(r => setTimeout(r, 800));
        }
        await new Promise(r => setTimeout(r, 900));
        // ⚠️ 不等字体就量，量到的是回退字体
        await send('Runtime.evaluate', { expression: 'document.fonts && document.fonts.ready', awaitPromise: true });
        const out = [];
        // ⭐ reloadBetween：每条表达式跑在一张**干净的页面**上。
        //    2026-09-04 实录：flow-walk-gate 把 30 条关键路径塞进一次求值、只换 hash，
        //    于是前一条路径点出来的 DOM 会留给后一条。FLOW-29 单跑绿、批量红 ——
        //    ⛔ 而**反方向才是真危险**：一条路径可能靠前面留下的状态「走通」，
        //    那是一条从没真正走通过的路径在报绿，没有任何东西会说出来。
        let first = true;
        for (const expr of expressions) {
          if (opts.reloadBetween && !first) {
            await send('Page.reload', {});
            await new Promise(r => setTimeout(r, opts.reloadWaitMs || 500));
            await send('Runtime.evaluate', { expression: 'document.fonts && document.fonts.ready', awaitPromise: true });
          }
          first = false;
          const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
          if (!r.result || !r.result.result || r.result.exceptionDetails || r.result.result.subtype === 'error')
            throw new Error('页面里求值失败：' + (r.result?.exceptionDetails?.text || r.result?.result?.description || '未知'));
          out.push(r.result.result.value);
        }
        res(out);
      } catch (e) { rej(e); }
    };
  });
  return await done;
  } finally {
    clearTimeout(overall);
    process.off('SIGINT', stop); process.off('SIGTERM', stop);
    for (const p of pend.values()) { clearTimeout(p.timer); p.reject(new Error('Browser closed')); }
    pend.clear();
    try { sock?.close(); } catch {}
    if (proc.pid) {
      try { process.platform === 'win32' ? proc.kill() : process.kill(-proc.pid, 'SIGTERM'); } catch {}
      await new Promise(r => setTimeout(r, 150));
      try { process.platform === 'win32' ? proc.kill('SIGKILL') : process.kill(-proc.pid, 'SIGKILL'); } catch {}
    }
    rmSync(tmp, { recursive: true, force: true });
  }
}

// ---------------------------------------------------------------- 自证（M8）
// ⭐ 2026-09-04 补。本模块此前**零测试**，而四道浏览器门禁全靠它取数：
//    它若静默返回错的东西（求值失败被吞、媒体特性没生效、字体没就绪就量），
//    上层门禁会拿着错数据得出「通过」。
// ⛔ 尤其要守的是：**页面里求值抛错时必须抛出来**，不许变成 undefined 往上传 ——
//    那样门禁会把「没量到」当成「量到了 0」。
if (process.argv[1] && process.argv[1].endsWith('_browser.mjs')) {
  const { writeFileSync, mkdtempSync } = await import('node:fs');
  const { join } = await import('node:path');
  const { tmpdir } = await import('node:os');
  const dir = mkdtempSync(join(tmpdir(), 'br-'));
  const f = join(dir, 'fx.html');
  writeFileSync(f, `<!doctype html><meta charset="utf-8">
    <style>@media (prefers-reduced-motion: reduce){#m{--rm:1}}
           @media (pointer: coarse){#p{--cp:1}}</style>
    <body><div id="m"></div><div id="p"></div><div id="t">你好</div></body>`);

  let ok = true;
  try {
  const chk = (n, c) => { console.log((c ? '  ✓ ' : '  ✗ ') + n); ok = ok && c; };

  const [a, b] = await evalInPage(f, '900x700',
    ['document.getElementById("t").textContent', '1 + 1']);
  chk('能取回页面里的值', a === '你好');
  chk('多个表达式按顺序返回', b === 2);

  // ⛔ 核心反例：页面里抛错必须**抛出来**，不许静默变成 undefined
  let threw = false;
  try { await evalInPage(f, '900x700', ['(() => { throw new Error("boom") })()']); }
  catch { threw = true; }
  chk('⛔ 页面内抛错必须冒泡（不许静默返回 undefined）', threw);

  const [rm] = await evalInPage(f, '900x700',
    ['getComputedStyle(document.getElementById("m")).getPropertyValue("--rm").trim()'],
    { reducedMotion: true });
  chk('reducedMotion 选项真的让 @media 生效', rm === '1');

  const [cp] = await evalInPage(f, '900x700',
    ['getComputedStyle(document.getElementById("p")).getPropertyValue("--cp").trim()'],
    { coarsePointer: true });
  chk('coarsePointer 选项真的让 @media 生效', cp === '1');

  const [w] = await evalInPage(f, '414x900', ['innerWidth']);
  chk('viewport 参数真的改变了 innerWidth', w === 414);

  let died = false;
  try { await evalInPage(join(dir, 'nope.html'), '900x700', ['1']); }
  catch { died = true; }
  chk('文件不存在时抛错，不返回空结果', died);

  // ⭐ reloadBetween 的自证：必须**两个方向都验**。
  //    只验「加了以后干净」不够 —— 若这个夹具本身就不会串，那条断言恒绿。
  //    所以先证明**不加就真的会串**，再证明加了不串。
  const leakHtml = '<!doctype html><body><div id="box">A</div>';
  writeFileSync(join(dir, 'leak.html'), leakHtml);
  const mutate = `(()=>{document.getElementById('box').textContent += 'X';
                        return document.getElementById('box').textContent;})()`;
  const noIso = await evalInPage(join(dir, 'leak.html'), '900x700', [mutate, mutate, mutate]);
  chk('对照组：不加 reloadBetween 时 DOM 真的会串（AX / AXX / AXXX）',
      noIso[0] === 'AX' && noIso[1] === 'AXX' && noIso[2] === 'AXXX');
  const iso = await evalInPage(join(dir, 'leak.html'), '900x700', [mutate, mutate, mutate],
                               { reloadBetween: true });
  chk('reloadBetween 让每条表达式都跑在干净页面上（三次都是 AX）',
      iso[0] === 'AX' && iso[1] === 'AX' && iso[2] === 'AX');

  // 仅验证历史诊断匹配器，不以此授权杀进程；清理只用本次 ChildProcess。
  chk('诊断匹配器：ppid=1 且带 pb- 前缀 → 列为候选（不是杀进程授权）',
      isOurOrphan(`  123     1 /App/Chrome --user-data-dir=${join(tmpdir(), 'pb-ab/ud')} u`) === '123');
  chk('孤儿匹配器：父进程活着（ppid≠1）→ 不杀',
      isOurOrphan('  124   567 /App/Chrome --user-data-dir=/tmp/x/pb-ab/ud') === null);
  chk('孤儿匹配器：别家前缀 → 属主不明不代杀',
      isOurOrphan('  125     1 /App/Chrome --user-data-dir=/tmp/other/ud') === null);

  console.log('\n' + (ok ? '✅ 自证通过：取数通道可信' : '❌ 自证失败：门禁拿到的数不可信'));
  process.exitCode = ok ? 0 : 1;
  } finally { rmSync(dir, { recursive: true, force: true }); }
}
