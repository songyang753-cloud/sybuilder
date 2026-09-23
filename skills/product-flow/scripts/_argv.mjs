// ============================================================================
// 命令行参数守卫（.mjs 版）—— 未知 `--flag` 必须报错，⛔ 不许静默丢弃。
//
// ═══ 为什么要有它 ═══
// 本 skill 的四道浏览器门禁各自写着：
//     const files = argv.filter(a => !a.startsWith('--'));
// 它把**任何**以 `--` 开头的东西当成「选项」滤掉 —— 包括**写错的选项**。
// 于是 `--all-route`（少个 s）这种笔误会被静默忽略，
// 门禁只审打开时那一屏却照常打印通过率。
//
// ⭐ 实测同族事故（Python 侧）：`element-identity-gate.py --spec X --demo Y`
//    正确写法是 `X --html Y` ⇒ `--html` 不存在 ⇒ demo 侧检查从没跑过，
//    而门禁一路报「✅ 通过」；改用正确参数后当场暴露 32 处缺口。
//
// ⭐⭐ **「跑不了」和「跑了没问题」折叠成同一个状态，就是 fail-open。**
//     这一类 fail-open 不在判据里，在**参数解析**里 —— 判据写得再好也救不回来。
//
// 用法：
//     import { rejectUnknown } from './_argv.mjs';
//     rejectUnknown(argv, ['--json','--viewport'], '用法: gate.mjs <file.html> [--json]');
// ============================================================================

/**
 * @param {string[]} argv   process.argv.slice(2)
 * @param {string[]} known  认得的 --flag 全集
 * @param {string}   usage  用法提示（会打进错误信息）
 */
export function rejectUnknown(argv, known, usage = '') {
  const set = new Set(known);
  const bad = argv.filter(a => a.startsWith('--') && !set.has(a.split('=')[0]));
  if (!bad.length) return;
  console.error(
    `UNABLE: 不认识的参数 ${bad.join(' ')}` +
    (usage ? `；${usage}` : '') +
    '（⛔ 静默忽略错误参数会让门禁只跑一半而照样报绿）');
  process.exit(2);
}

// ---------------------------------------------------------------- 自证（M8）
if (process.argv[1] && process.argv[1].endsWith('_argv.mjs')) {
  const { execFileSync } = await import('node:child_process');
  const { fileURLToPath } = await import('node:url');
  const { writeFileSync, mkdtempSync } = await import('node:fs');
  const { join } = await import('node:path');
  const { tmpdir } = await import('node:os');
  const me = fileURLToPath(import.meta.url);
  // ⚠️ 必须写成**真实脚本文件**再跑：`node -e` 下 process.argv 没有 argv[1]（脚本路径），
  //    `slice(2)` 会把第一个参数吞掉 —— 自证的接线与被测对象的接线必须一致，
  //    否则测的是另一种调用形态（第一版就栽在这里，3/5 假红）。
  const dir = mkdtempSync(join(tmpdir(), 'argv-'));
  const probe = join(dir, 'probe.mjs');
  writeFileSync(probe,
    `import {rejectUnknown} from ${JSON.stringify(me)};\n` +
    `rejectUnknown(process.argv.slice(2), ['--json'], '用法提示');\n` +
    `console.log('OK');\n`);
  const run = (args) => {
    try { execFileSync(process.execPath, [probe, ...args], { stdio: 'pipe' });
          return { code: 0, out: '' }; }
    catch (e) { return { code: e.status, out: String(e.stderr || '') }; }
  };
  let ok = true;
  const chk = (n, c) => { console.log((c ? '  ✓ ' : '  ✗ ') + n); ok = ok && c; };
  chk('已知参数放行', run(['--json', 'x.html']).code === 0);
  chk('位置参数放行', run(['x.html']).code === 0);
  chk('未知参数 → 退 2（⛔ 不许静默通过）', run(['--nope', 'x.html']).code === 2);
  chk('错误信息里带用法提示', run(['--nope']).out.includes('用法提示'));
  chk('`--json=1` 带等号的已知参数放行', run(['--json=1']).code === 0);
  chk('少写一个字母的笔误也要拦（--jso）', run(['--jso', 'x.html']).code === 2);
  console.log('\n' + (ok ? '✅ 自证通过：这道守卫会出声' : '❌ 自证失败'));
  process.exit(ok ? 0 : 1);
}
