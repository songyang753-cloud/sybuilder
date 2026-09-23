// 竞品遍历编排器 —— S2 的唯一串行入口。
//
// ⛔ 为什么存在(2026-09-17 用户当场点名):竞品遍历会各自起一个浏览器 + node 进程,
//    并发跑会把内存打爆。此前「一次只跑一件」只是 CLAUDE.md 里的一句散文,我照样并发,
//    照样爆。M11 的判决:以散文存在的纪律等于不存在 ⇒ 把「串行」变成这个编排器的**行为**。
//
// ⛔ 本文件**故意不提供并发旋钮**:用户明确说内存受不了,给个 --concurrency 就是埋雷(YAGNI)。
//    想并发的人得自己另写脚本——而那会被 serial-orchestration-gate 判红。
//
// 用法: node competitor-sweep.mjs <manifest.json> <outdir> [--steps 30]
//   manifest.json = [{ "name": "chatgpt", "port": 9222 }, { "name": "kimi", "port": 9223 }, ...]
// 退出码: 0=全部跑完(单个竞品失败不致命,记进 summary) 2=UNABLE(清单读不了/为空)
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WALK = path.join(HERE, 'competitor-walk.mjs');
const A = process.argv.slice(2);
// --help：只显示帮助（文件头注释）并退 0，不触发一次全量编排
if (A.includes('--help') || A.includes('-h')) {
  console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}
const [manifestPath, outdir] = A;
const steps = A.includes('--steps') ? A[A.indexOf('--steps') + 1] : '30';

if (!manifestPath || !outdir) { console.error('用法: competitor-sweep.mjs <manifest.json> <outdir> [--steps N]'); process.exit(2); }
let list;
try { list = JSON.parse(fs.readFileSync(manifestPath, 'utf8')); }
catch (e) { console.error(`清单读不了: ${e.message}`); process.exit(2); }
if (!Array.isArray(list) || list.length === 0) { console.error('清单为空'); process.exit(2); }

// 串行跑一个竞品:起子进程,等它退出,resolve。⛔ 绝不同时起下一个。
function runOne(name, port) {
  return new Promise((resolve) => {
    const dst = path.join(outdir, name);
    fs.mkdirSync(dst, { recursive: true });
    process.stderr.write(`\n▶ ${name} (port ${port}) —— 串行,前一个已退出才起本个\n`);
    const child = spawn('node', [WALK, String(port), dst, '--steps', String(steps)], { stdio: 'inherit' });
    child.on('close', (code) => resolve({ name, port, code, ok: code === 0 }));
    child.on('error', (e) => resolve({ name, port, code: -1, ok: false, err: e.message }));
  });
}

const summary = [];
// ⭐ 串行的核心:for...of + await,上一个 await 完(子进程 close)才进下一轮。
//    ⛔ 不许改成 Promise.all(list.map(...)) —— 那会同时起 N 个浏览器,正是要防的事。
for (const { name, port } of list) {
  const r = await runOne(name, port);
  summary.push(r);
  process.stderr.write(`  ${r.ok ? '✅' : '🔴'} ${name} 退出码 ${r.code}${r.err ? ' · ' + r.err : ''}\n`);
}

fs.writeFileSync(path.join(outdir, 'sweep-summary.json'), JSON.stringify({ total: list.length, ok: summary.filter(s => s.ok).length, results: summary }, null, 1));
console.log(JSON.stringify({ total: list.length, ok: summary.filter(s => s.ok).length, failed: summary.filter(s => !s.ok).map(s => s.name) }));
