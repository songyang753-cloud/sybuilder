#!/usr/bin/env node
// 把断言注入 demo 的临时副本，用 headless Chrome 真实渲染后执行，输出 PASS/FAIL。
// 用法: node selftest.mjs <产物.html> <断言文件.js>
// 交付件本身不会被修改，也不会留下任何测试代码。
//
// 退出码（2026-09-05 定并写下来；此前**从没写在任何地方**，只被 process.exit 强制执行）：
//   0 = 全部断言通过
//   1 = 有断言失败（失败条数在 stdout 里给，不再编码进退出码）
//   3 = **没能测**：用法错 / 文件不存在 / 找不到或跑不起来 Chrome / 拿不到结果 / 零断言
// ⚠️ 为什么不再用 `exit(failed.length)`：它和「没能测」的 exit 2 **会撞码** ——
//    「恰好 2 条断言失败」与「Chrome 没装」返回同一个数字，调用方无法区分（A19）。
//    失败**条数**属于报告内容，不属于状态码；状态码只回答三个问题之一。

import { readFileSync, writeFileSync, existsSync, readdirSync, mkdtempSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir, homedir } from 'node:os';
import { execFileSync } from 'node:child_process';

const RESULT_ID = '__DEMO_SELFTEST_RESULT__';

function findChrome() {
  if (process.env.CHROME_BIN) {
    if (!existsSync(process.env.CHROME_BIN)) throw new Error('CHROME_BIN does not exist');
    return process.env.CHROME_BIN;
  }
  for (const folder of (process.env.PATH || '').split(':')) {
    for (const name of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
      const candidate = join(folder, name);
      if (existsSync(candidate)) return candidate;
    }
  }
  const roots = [
    join(homedir(), '.cache/puppeteer/chrome-headless-shell'),
    join(homedir(), '.cache/puppeteer/chrome'),
  ];
  const found = [];
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const ver of readdirSync(root)) {
      const verDir = join(root, ver);
      let inner;
      try { inner = readdirSync(verDir); } catch { continue; }
      for (const d of inner) {
        const candidates = [
          'chrome-headless-shell',
          'Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
          'chrome',
        ];
        for (const bin of candidates) {
          const p = join(verDir, d, bin);
          if (existsSync(p)) found.push({ ver, path: p });
        }
      }
    }
  }
  if (found.length) {
    found.sort((a, b) => b.ver.localeCompare(a.ver, undefined, { numeric: true }));
    return found[0].path;
  }
  const system = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if (existsSync(system)) return system;
  throw new Error('找不到 headless Chrome。装一个：npx @puppeteer/browsers install chrome-headless-shell@stable');
}

const HARNESS = `
(function(){
  var __r = [];
  function rec(name, ok, detail){
    __r.push({name:name, ok:!!ok, detail:detail||''});
    var pre=document.getElementById('${RESULT_ID}');
    if(pre) pre.textContent=JSON.stringify(__r);
  }
  window.check = function(name, ok){ rec(name, ok); };
  window.addEventListener('error', function(e){ rec('page error', false, e.message); });
  window.addEventListener('unhandledrejection', function(e){ rec('unhandled rejection', false, String(e.reason)); });
  window.addEventListener('securitypolicyviolation', function(e){ rec('offline resource violation', false, e.blockedURI); });
  var __consoleError = console.error;
  console.error = function(){ rec('console.error', false, Array.from(arguments).join(' ')); __consoleError.apply(console, arguments); };
  window.eq = function(name, actual, expected, tol){
    tol = tol || 0;
    var ok = Math.abs(actual - expected) <= tol;
    rec(name, ok, ok ? '' : ('实际 ' + actual + ' / 期望 ' + expected + (tol ? ' ±' + tol : '')));
  };
  window.$  = function(s){ return document.querySelector(s); };
  window.$$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };
  window.px = function(sel, prop){
    var el = document.querySelector(sel);
    if(!el) return NaN;
    return parseFloat(getComputedStyle(el)[prop]);
  };
  window.rect = function(sel){
    var el = document.querySelector(sel);
    return el ? el.getBoundingClientRect()
              : {top:NaN,left:NaN,width:NaN,height:NaN,right:NaN,bottom:NaN};
  };
  window.text = function(sel){
    var el = document.querySelector(sel);
    return el ? el.textContent.trim() : '';
  };
  window.__emit = function(){
    var pre = document.createElement('pre');
    pre.id = '${RESULT_ID}';
    pre.textContent = JSON.stringify(__r);
    document.body.appendChild(pre);
  };
})();
`;

function main() {
  const [htmlArg, assertArg] = process.argv.slice(2);
  if (!htmlArg || !assertArg) {
    console.error('用法: node selftest.mjs <产物.html> <断言文件.js>');
    process.exit(3);
  }
  const htmlPath = resolve(htmlArg);
  const assertPath = resolve(assertArg);
  for (const p of [htmlPath, assertPath]) {
    if (!existsSync(p)) { console.error('文件不存在: ' + p); process.exit(3); }
  }

  const html = readFileSync(htmlPath, 'utf8');
  const asserts = readFileSync(assertPath, 'utf8');

  // 关过渡：不关会量到动画起始值，产生大量假 fail
  const killMotion = '<style id="__no_motion__">*,*::before,*::after'
    + '{transition:none!important;animation:none!important}</style>';
  // 断言文件里若出现字面 </script>（哪怕在字符串或注释里）会提前闭合注入的 script 标签
  const safeAsserts = asserts.replace(/<\/script>/gi, '<\\/script>');
  const injected = '<script>\n(async function(){'
    + 'if(document.readyState==="loading") await new Promise(r=>document.addEventListener("DOMContentLoaded",r,{once:true}));'
    + 'try{\n'
    + safeAsserts + '\n}catch(e){ check("断言脚本抛异常: " + e.message, false); }'
    + '\nawait new Promise(r=>setTimeout(r, 100)); __emit();})();\n</script>';
  const setup = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
    + 'script-src \'unsafe-inline\' data:; style-src \'unsafe-inline\'; img-src data:; font-src data:; media-src data:; connect-src \'none\'">'
    + '<script>' + HARNESS + '</script>';

  // 必须用替换函数：替换串里的 $$ / $& 会被 String.replace 当特殊记号解释，
  // 会把 harness 里的 window.$$ 悄悄改写成 window.$，制造假绿。
  let out = html.includes('</head>')
    ? html.replace('</head>', () => killMotion + '\n</head>')
    : killMotion + '\n' + html;
  out = /<head\b[^>]*>/i.test(out)
    ? out.replace(/<head\b[^>]*>/i, m => m + setup)
    : setup + out;
  out = /<\/body>/i.test(out)
    ? out.replace(/<\/body>/i, () => injected + '\n</body>')
    : out + injected;

  const folder = mkdtempSync(join(tmpdir(), 'sybuilder-demo-test-'));
  process.on('exit', () => rmSync(folder, {recursive:true, force:true}));
  const tmp = join(folder, 'demo.html');
  writeFileSync(tmp, out, 'utf8');

  let dom = '';
  try {
    const chrome = findChrome();
    // 默认视口 800×600 会让固定宽 demo 假性横向溢出，故给足宽度；可用 DEMO_VIEWPORT 覆盖
    const viewport = process.env.DEMO_VIEWPORT || '1600,1000';
    dom = execFileSync(chrome, [
      '--headless', '--disable-gpu', '--no-first-run',
      '--user-data-dir=' + join(folder, 'profile'),
      '--window-size=' + viewport,
      '--virtual-time-budget=3000',
      '--dump-dom', 'file://' + tmp,
    ], { timeout: 20000, encoding: 'utf8', maxBuffer: 128 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) {
    console.error('UNABLE: Chrome 执行失败或超时，部分 stdout 不能作为 PASS: ' + e.message);
    process.exit(3);
  }

  const m = dom.match(new RegExp('<pre id="' + RESULT_ID + '">([\\s\\S]*?)</pre>'));
  if (!m) {
    console.error('没拿到断言结果。两种可能：(1) 断言文件有语法错（解析期失败，try/catch 抓不到）；'
      + '(2) 页面 JS 在断言前就抛异常。用浏览器打开下面的临时副本看 console 即可分辨。');
    console.error('输入产物未修改；断言没有完整完成，临时会话将在退出时清理。');
    process.exit(3);
  }

  const decoded = m[1]
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&');
  const results = JSON.parse(decoded);
  const failed = results.filter(r => !r.ok);

  for (const r of results) {
    console.log((r.ok ? '  PASS  ' : '  FAIL  ') + r.name + (r.detail ? '  → ' + r.detail : ''));
  }
  if (!results.length) { console.error('断言文件一条都没跑到，检查语法。'); process.exit(3); }
  console.log('\n' + (failed.length ? 'FAIL' : 'PASS') + '  '
    + (results.length - failed.length) + '/' + results.length);
  process.exit(failed.length ? 1 : 0);
}

main();
