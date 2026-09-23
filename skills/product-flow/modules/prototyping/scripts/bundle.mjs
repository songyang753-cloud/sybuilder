#!/usr/bin/env node
// 把可迭代目录版（index.html + css/js/图片）合成零外链单文件。
// 用法: node bundle.mjs <目录> <输出.html>
//
// 退出码（与同目录 selftest.mjs 保持同一套约定，2026-09-05 统一）：
//   0 = 零外链且素材全部内联成功
//   1 = **不合格**：仍有外链，或有素材没能内联（产物里是断链/缺图）
//   3 = **没能测**：用法错 / 找不到 index.html
// ⚠️ 此前这里用 2 表示「没能测」，而 selftest.mjs 用 3 —— 同一个 skill 的两个脚本
//    对同一件事给出不同编码。调用方要么记两套，要么记错一套。

import { readFileSync, writeFileSync, existsSync, statSync, realpathSync } from 'node:fs';
import { join, resolve, extname, relative, isAbsolute, dirname, sep } from 'node:path';

const MIME = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.ico': 'image/x-icon',
};

const BIG_ASSET_BYTES = 200 * 1024;
const BIG_OUTPUT_BYTES = 5 * 1024 * 1024;

// 素材必须落在 demo 目录内（2026-09-05 加）。
// 实测：CSS 里写 `url(../secret.txt)` ⇒ **目录外的文件被 base64 内联进产物**，
// 退出码 0、零警告。而这个产物是**要发给别人的单文件 HTML** —— 等于把本机文件一起发出去。
// 相对路径写错（多一层 ../）就够触发，不需要恶意。
function withinDir(dir, p) {
  if (!existsSync(p)) return false;
  const rel = relative(realpathSync(dir), realpathSync(p));
  return rel !== '' && rel !== '..' && !rel.startsWith('..' + sep) && !isAbsolute(rel);
}

// 远程地址（破坏零外链契约，要警告）；data: 是已内联的结果，跳过但不警告
function isRemote(url) { return /^(https?:)?\/\//i.test(url); }
function isInlined(url) { return url.startsWith('data:'); }
function isExternal(url) { return isRemote(url) || isInlined(url); }

function dataUri(dir, url, warn, base = dir) {
  const clean = url.split('?')[0].split('#')[0];
  const p = resolve(base, clean);
  if (!existsSync(p) || !statSync(p).isFile()) { warn.push('找不到素材: ' + url); return null; }
  if (!withinDir(dir, p)) { warn.push('⛔ 素材在 demo 目录之外，已拒绝内联（会把本机文件打进要发出去的产物）: ' + url); return null; }
  const buf = readFileSync(p);
  if (buf.length > BIG_ASSET_BYTES) {
    warn.push('素材偏大 ' + (buf.length / 1024).toFixed(0) + 'KB: ' + url + '（建议先压到显示尺寸）');
  }
  const mime = MIME[extname(clean).toLowerCase()] || 'application/octet-stream';
  return 'data:' + mime + ';base64,' + buf.toString('base64');
}

function inlineCssUrls(css, dir, warn, base = dir) {
  return css.replace(/url\(\s*(['"]?)([^'")]+)\1\s*\)/g, (m, q, url) => {
    if (isInlined(url)) return m;                       // 已内联，二次扫描时跳过
    if (isRemote(url)) { warn.push('CSS 里有外链，已保留（破坏零外链契约）: ' + url); return m; }
    const uri = dataUri(dir, url, warn, base);
    return uri ? 'url(' + uri + ')' : m;
  });
}

function main() {
  const [dirArg, outArg] = process.argv.slice(2);
  if (!dirArg || !outArg) {
    console.error('用法: node bundle.mjs <目录> <输出.html>');
    process.exit(3);
  }
  const dir = resolve(dirArg);
  const indexPath = join(dir, 'index.html');
  if (!existsSync(indexPath)) { console.error('找不到 ' + indexPath); process.exit(3); }
  if (!withinDir(dir, indexPath)) { console.error('⛔ 入口文件指向 demo 目录之外'); process.exit(1); }

  const warn = [];
  const loadedScripts = [];
  let html = readFileSync(indexPath, 'utf8');
  html = html.replace(/(<[^>]+>)/g, tag => tag.replace(/\b(src|href|poster|srcset|rel)\s*=\s*/gi, '$1='));
  // Normalize legal unquoted resource attributes before applying the inliner.
  html = html.replace(/(<[^>]+>)/g, tag => tag.replace(
    /\b(src|href|poster|srcset)\s*=\s*([^\s"'=`<>]+)/gi, '$1="$2"'));

  // <link rel=stylesheet href="x.css">  →  <style>…</style>
  html = html.replace(/<link\b[^>]*?rel=["']?stylesheet["']?[^>]*?>/gi, (tag) => {
    const m = tag.match(/href=["']([^"']+)["']/i);
    if (!m || isExternal(m[1])) { if (m) warn.push('外链样式已保留: ' + m[1]); return tag; }
    const p = resolve(dir, m[1]);
    if (!existsSync(p)) { warn.push('找不到样式: ' + m[1]); return tag; }
    if (!withinDir(dir, p)) { warn.push('⛔ 样式在 demo 目录之外，已拒绝内联: ' + m[1]); return tag; }
    return '<style>\n' + inlineCssUrls(readFileSync(p, 'utf8'), dir, warn, dirname(p)) + '\n</style>';
  });

  // <script src="x.js"></script>  →  <script>…</script>
  html = html.replace(/<script\b[^>]*?\bsrc=["']([^"']+)["'][^>]*>\s*<\/script>/gi, (tag, src) => {
    if (isExternal(src)) { warn.push('外链脚本已保留: ' + src); return tag; }
    const p = resolve(dir, src);
    if (!existsSync(p)) { warn.push('找不到脚本: ' + src); return tag; }
    if (!withinDir(dir, p)) { warn.push('⛔ 脚本在 demo 目录之外，已拒绝内联: ' + src); return tag; }
    const script = readFileSync(p, 'utf8');
    loadedScripts.push(script);
    // Inline classic defer/async loses loading semantics. A local data URL keeps
    // the browser's scheduling behavior without an external dependency.
    if (/\b(?:defer|async)\b/i.test(tag))
      return tag.replace(/\bsrc=["'][^"']+["']/i,
        'src="data:text/javascript;base64,' + Buffer.from(script).toString('base64') + '"');
    // </script> 出现在字符串里会提前闭合，必须转义
    const attrs = tag.slice(0, tag.indexOf('>')).replace(/\s+src=["'][^"']+["']/i, '');
    return attrs + '>\n' + readFileSync(p, 'utf8').replace(/<\/script>/gi, '<\\/script>') + '\n</script>';
  });

  html = html.replace(/\bsrcset=["']([^"']+)["']/gi, (m, value) => {
    // Inline local responsive images. Mixed data-URI lists need a full HTML parser;
    // reject that unsupported form rather than silently claiming a portable file.
    if (value.includes('data:')) { warn.push('⛔ 暂不支持含 data URI 的 srcset，请先合并为 src'); return m; }
    const items = value.split(',').map(item => {
      const parts = item.trim().match(/^(\S+)(\s+\d+(?:\.\d+)?[wx])?$/);
      if (!parts || isRemote(parts[1])) { warn.push('⛔ 无法内联 srcset 项: ' + item); return item; }
      const uri = dataUri(dir, parts[1], warn);
      return uri ? uri + (parts[2] || '') : item;
    });
    return 'srcset="' + items.join(', ') + '"';
  });

  // <img src>, <source src>, <video poster>
  html = html.replace(/\b(src|poster)=["']([^"']+)["']/gi, (m, attr, url) => {
    if (isExternal(url)) return m;
    const uri = dataUri(dir, url, warn);
    return uri ? attr + '="' + uri + '"' : m;
  });

  // 内联 <style> 块里的 url()
  html = html.replace(/<style\b[^>]*>([\s\S]*?)<\/style>/gi,
    (m, css) => m.replace(css, inlineCssUrls(css, dir, warn)));
  html = html.replace(/\bstyle=(["'])(.*?)\1/gi,
    (m, quote, css) => 'style=' + quote + inlineCssUrls(css, dir, warn) + quote);
  if (/<(?:object|embed|iframe)\b/i.test(html))
    warn.push('⛔ 内嵌文档/插件资源不属于离线打包支持范围，请替换为本地可交互内容');

  const decodedCss = html.replace(/\\([0-9a-f]{1,6})\s?/gi, (_, hex) => String.fromCodePoint(parseInt(hex,16)));
  if (/@import\b/i.test(decodedCss)) warn.push('⛔ CSS @import 必须先在开发态展开，不能声称已自包含');
  for (const tag of html.match(/<(?:use|image|link)\b[^>]*>/gi) || []) {
    const ref = tag.match(/\b(?:xlink:)?href=["']([^"']+)["']/i);
    if (ref && !ref[1].startsWith('#') && !isInlined(ref[1]))
      warn.push('⛔ 尚未内联的 href 资源: ' + ref[1]);
  }
  const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
    .map(m => m[1]).concat(loadedScripts).map(s=>s.replace(/\/\*[\s\S]*?\*\/|^\s*\/\/.*$/gm, '')).join('\n');
  if (/\bimport\s*(?:\(|[{"'*])|\bfrom\s*["']/m.test(scripts))
    warn.push('⛔ ES module/import 需先由项目构建器打包；此打包器不能丢弃模块语义');
  if (/\b(?:fetch|WebSocket|EventSource|XMLHttpRequest|sendBeacon)\b/.test(scripts))
    warn.push('⛔ 存在运行期网络调用；离线交互稿必须先接入本地模拟数据');
  // Static scanning cannot prove arbitrary JavaScript free of dynamic networking.
  // Enforce the offline boundary in the delivered file, not only in the test copy.
  const policy = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\' data:; style-src \'unsafe-inline\'; img-src data:; font-src data:; media-src data:; connect-src \'none\'; form-action \'none\'; base-uri \'none\'">';
  html = /<head\b[^>]*>/i.test(html) ? html.replace(/<head\b[^>]*>/i, tag => tag + policy) : policy + html;
  const out = resolve(outArg);
  writeFileSync(out, html, 'utf8');

  const size = statSync(out).size;
  const remaining = (html.match(/["'(](https?:)?\/\/[^"')]+/gi) || []).length;

  console.log('已生成 ' + out + '  (' + (size / 1024).toFixed(0) + 'KB)');
  if (size > BIG_OUTPUT_BYTES) console.log('⚠️  文件超过 5MB，建议压缩素材');
  // ⚠️ 2026-09-05：此前退出码只看 remaining（远程外链数），
  //    而「找不到素材/样式/脚本」和「素材在目录外被拒」**一个都不计入** ——
  //    于是素材缺失时它照打「✅ 零外链」并 **exit 0**，而产物里留着断链的 <img>。
  //    交付契约不是「没有 http:// 链接」，是「**这个文件双击打开是完整的**」。
  const broken = warn.filter(w => w.startsWith('找不到') || w.startsWith('⛔')).length;
  console.log(remaining === 0 ? '✅ 零外链' : '❌ 仍有 ' + remaining + ' 处外链，不满足交付契约');
  if (broken) console.log('❌ 有 ' + broken + ' 处素材没能内联（产物里是断链/缺图），不满足交付契约');
  for (const w of warn) console.log('   ⚠️  ' + w);
  process.exit(remaining === 0 && broken === 0 ? 0 : 1);
}

main();
