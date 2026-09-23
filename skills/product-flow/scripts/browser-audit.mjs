#!/usr/bin/env node
// ============================================================================
// 浏览器档视觉审计 —— 跑 visual-spec.md 里那些**必须真实渲染才能判**的判据。
//
// 为什么需要它：
//   `visual-spec.md` 的「每一节由谁执行」表里，有 6 条写着
//   「可量但**需真实渲染** → 浏览器档，S6 自动验收」——
//   而**浏览器档从来没有工具**。写在文档里没人跑，等于没写。
//   这与 visual-spec-gate 当初的处境一模一样（正面判据无人执行）。
//
//   静态档（visual-spec-gate.py 读 CSS）与浏览器档（本脚本读渲染结果）
//   查的是**不同的东西**，不能互相替代：
//     · 静态档看得到 `line-height: 1.5`，看不到这一行实际排了几个字
//     · 静态档看得到 `color: var(--fg)`，算不出它在实际背景上的对比度
//     · 静态档完全看不到留白占比、强调色占比、横向滚动
//
// 用法：
//   node browser-audit.mjs <file.html | http://url> [--json] [--viewport 1440x900]
//                          [--all-viewports] [--all-routes] [--all-themes]
//   node browser-audit.mjs --self-test
// 退出码：0=通过 1=不通过 2=跑不了（找不到浏览器/页面打不开，**绝不折叠成 0**）
// ============================================================================
import { existsSync, writeFileSync, mkdtempSync } from 'node:fs';
import { evalInPage, browserPreflight } from './_browser.mjs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
import { rejectUnknown } from './_argv.mjs';

// 登记册#1：--help 只显示帮助（文件头注释）并退 0
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  const _src = (await import('node:fs')).readFileSync(new URL(import.meta.url), 'utf8');
  console.log(_src.split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}


// ---------------------------------------------------------------- 审计负载
// 这段在页面里跑。**只读，不改页面**（探针会弄脏被测对象，见 M8 教训）。
const MEASURE = `(() => {
  const R = [];
  const add = (id, sec, desc, status, ev) => R.push({id, sec, desc, status, ev});
  // ⚠️ Chrome 152 起，折叠的 <details> 内容用 content-visibility:hidden 实现，
  //    getBoundingClientRect() 仍返回非零尺寸 —— 只按宽高判可见，
  //    会把**收起来的**内容当成可见的。实测：一个正确折叠的场景导航
  //    被判出 21 个「无焦点环」，留白被算成 6%。
  //    ⭐ checkVisibility() 正是为这件事存在的，能用就用它。
  const vis = el => {
    if (el.checkVisibility && !el.checkVisibility({ contentVisibilityAuto: true,
        opacityProperty: true, visibilityProperty: true })) return false;
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.01; };
  const all = [...document.querySelectorAll('*')].filter(vis);
  const lum = c => { const m = c.match(/\\d+/g); if (!m || m.length < 3) return null;
    const f = x => { x/=255; return x <= 0.03928 ? x/12.92 : Math.pow((x+0.055)/1.055, 2.4); };
    return 0.2126*f(+m[0]) + 0.7152*f(+m[1]) + 0.0722*f(+m[2]); };
  // ⛔ 遇到**渐变/背景图**要报「量不了」，不许继续往上找。
  //   🚨 2026-09-06 独立样本实测：祖先是渐变色块时 backgroundColor 是透明，
  //   本函数会一路走到 body ⇒ 渐变上的白字被算成「白底白字 **1.00:1**」⇒ 报成违规。
  //   ⭐ 1.00:1 是**量不出来**的信号 —— 没有人会在成品里放白底白字。
  //   **测量失败必须报成「量不了」，不许报成「有发现」**（本仓一整天在治的同一个区分）。
  const bgOf = el => { let n = el; while (n && n !== document.documentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;   // 量不了
      const b = cs.backgroundColor;
      if (b && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(b)) return b; n = n.parentElement; }
    const bs = getComputedStyle(document.body);
    if (bs.backgroundImage && bs.backgroundImage !== 'none') return null;
    return bs.backgroundColor || 'rgb(255,255,255)'; };
  const ratio = (a, b) => { const la = lum(a), lb = lum(b); if (la == null || lb == null) return null;
    const hi = Math.max(la, lb), lo = Math.min(la, lb); return (hi + .05) / (lo + .05); };

  // 1 行长（真实排版才算得出）
  const paras = all.filter(e => /^(P|LI|DD|BLOCKQUOTE)$/.test(e.tagName) && (e.innerText||'').trim().length > 40);
  if (!paras.length) add('line-length','1.4','行长 45–75 字符（中文 25–40）','NA','页面没有足够长的正文段落');
  else {
    const bad = [];
    for (const p of paras.slice(0, 60)) {
      const t = (p.innerText||'').trim(); const cjk = (t.match(/[\\u4e00-\\u9fa5]/g)||[]).length / t.length > 0.3;
      const fs = parseFloat(getComputedStyle(p).fontSize);
      const w = p.getBoundingClientRect().width;
      const per = cjk ? w / fs : w / (fs * 0.5);       // 中文按 1 字宽=字号，拉丁按 0.5em 均宽
      const [lo, hi] = cjk ? [25, 40] : [45, 75];
      // ⚠️ 窄屏上**下限不适用**。390px 视口减去两侧内边距约 342px，
      //   15px 中文字符 ≈ 15px 宽 → 一行最多约 22 字，**永远达不到 25 的下限** ——
      //   一条在该视口下物理上无法满足的判据，只会逼人把正文字号调小去迁就门禁。
      //   下限本来防的是「宽容器里排出细长一条」，那是桌面构图问题；
      //   上限（一行太长跟丢）在手机上依然成立，保留。
      const narrow = innerWidth <= 480 || document.body.getAttribute('data-end') === 'mobile';
      if ((!narrow && per < lo) || per > hi) bad.push(Math.round(per) + (cjk?'字':'字符') + ' @' + p.tagName);
    }
    add('line-length','1.4','行长 45–75 字符（中文 25–40）', bad.length ? 'FAIL':'PASS',
        bad.length ? bad.slice(0,6).join(' · ') : paras.length + ' 段全部达标');
  }

  // ⚠️ 留白占比与强调色占比是**整页构图**指标：页面元素太少时它们没有意义。
  //    前置条件不成立时必须记 N/A —— 记 PASS 会让报告显示「全部通过」而它什么都没量，
  //    记 FAIL 则是拿构图判据去打一个还没有构图的页面。
  const COMPOSED = all.length >= 20;

  // 2 留白占比（内容像素 / 视口面积）
  const vw = innerWidth, vh = innerHeight;
  let ink = 0;
  for (const e of all) { if (e.children.length) continue;
    const r = e.getBoundingClientRect();
    if (r.bottom < 0 || r.top > vh) continue;
    ink += Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0)); }
  const white = 1 - Math.min(1, ink / (vw * vh));
  add('whitespace','2.3','留白占比 ≥40%', COMPOSED ? (white >= 0.4 ? 'PASS':'FAIL') : 'NA',
      COMPOSED ? (white*100).toFixed(0) + '%' : '可见元素仅 '+all.length+' 个，构图判据前置条件不成立');

  // 3 强调色占比 5–10%
  const areaBy = {};
  for (const e of all) { const r = e.getBoundingClientRect(); if (r.width<=0||r.height<=0) continue;
    const b = getComputedStyle(e).backgroundColor; const m = b.match(/\\d+/g); if (!m||m.length<3) continue;
    if (b.includes('rgba') && parseFloat(b.split(',')[3]) < 0.05) continue;
    const [r1,g1,b1] = m.map(Number); if (Math.max(r1,g1,b1)-Math.min(r1,g1,b1) < 30) continue; // 灰不算
    areaBy[b] = (areaBy[b]||0) + r.width*r.height; }
  const totalArea = vw*vh;
  const accent = Object.entries(areaBy).sort((a,b)=>b[1]-a[1])[0];
  if (!accent || !COMPOSED)
    add('accent-ratio','3.2','强调色占界面 5–10%','NA',
        !accent ? '页面没有非灰背景色' : '可见元素仅 '+all.length+' 个，构图判据前置条件不成立');
  else { const pct = accent[1]/totalArea*100;
    // ⛔ C 层（品牌方向）：强调色占比 5–10% 是**落地页/营销页**的构图惯例。
  //   拿它去判应用 UI 是判错了层 —— 本 SOP 自己的规则集写着「应用 UI 要被忘记：
  //   安静的表面层级、少颜色」，一个内部工具只有一处主 CTA、强调色占 1% 完全正确。
  //   判据（design-rulesets 三之二）：「金融终端 / 开发者工具 / 内部后台违反它合理吗？
  //   合理 → 最多 B 层」。答案是合理，所以它**报出但不阻断**（铁律 49）。
  //   ⚠️ 不阻断 ≠ 不检查：数值照样打印，营销页评审时人来看这条。
  add('accent-ratio','3.2','[C] 强调色占界面 5–10%（营销页构图惯例，应用 UI 不阻断）',
      (pct>=2&&pct<=15)?'PASS':'INFO',
        accent[0]+' 占 '+pct.toFixed(1)+'%（宽松档 2–15%）'); }

  // 4 实测对比度（渲染后的真实前景/背景）
  const texts = all.filter(e => e.children.length===0 && (e.textContent||'').trim().length>1).slice(0,300);
  const worst = [];
  let unmeasured = 0; const identical = [];
  for (const e of texts) { const s = getComputedStyle(e);
    const bg = bgOf(e);
    if (bg == null) { unmeasured++; continue; }        // 背景是渐变/图，量不了
    const cr = ratio(s.color, bg); if (cr == null) { unmeasured++; continue; }
    // ⛔ **恰好 1.00:1 = 前景与背景完全相同**。两种可能，本门分不出：
    //   ① 采样没取到真实背景（伪元素 / 绝对定位兄弟给的底色，getComputedStyle 看不见）
    //   ② 真的是隐形文字（那是另一种 bug，不是「对比度不足」）
    //   ⇒ 单独归一类，**不混进「对比度不足」** —— 2026-09-06 独立样本实测：
    //   渐变色块上的白字被算成「白底白字」，报成违规会把人送去调一个不存在的颜色。
    if (Math.abs(cr - 1) < 0.001) { identical.push((e.textContent||'').trim().slice(0,24)); continue; }
    const fs = parseFloat(s.fontSize), bold = +s.fontWeight >= 700;
    const need = (fs>=18 || (bold && fs>=14)) ? 3 : 4.5;
    if (cr < need) worst.push({t:(e.textContent||'').trim().slice(0,24), cr:cr.toFixed(2), need}); }
  worst.sort((a,b)=>a.cr-b.cr);
  if (identical.length)
    add('contrast-identical','3.1','前景与背景**完全相同**（1.00:1）—— 本门分不出是哪种','NA',
        identical.length + ' 处：' + identical.slice(0,5).join(' · ')
        + '　⇒ 要么采样没取到真实背景（伪元素/绝对定位兄弟），要么真是隐形文字。'
        + '**两者都要人打开看**，但都不是「对比度不足」');
  if (unmeasured)
    add('contrast-unmeasured','3.1','对比度**量不了**的元素（背景是渐变/图）','NA',
        unmeasured + ' 处 —— **这不是「通过」**：'
        + '它们的对比度本门根本没测到，要人打开看');
  add('contrast','3.1','实测对比度（正文 4.5:1 / 大字 3:1）', worst.length?'FAIL':'PASS',
      worst.length ? worst.slice(0,5).map(w=>w.cr+':1 需'+w.need+' 「'+w.t+'」').join(' · ') : texts.length+' 处文本全部达标');

  // 5 字体族数 / 非灰色数
  // ⚠️ 只统计**会渲染的**元素。原来把 html/head/meta/title/style/script 一并算进去，
  //   它们从不渲染却各自带着 UA 默认的 Times New Roman ——
  //   于是每个页面都白得一个不存在的字体族。本骨架里它只是让 ✅ 里多印一行，
  //   但真实项目正好用了 3 个字体族时，这一个幽灵就会把**合规页面判成不合规**。
  //   ⛔ 第 10 个「门禁自己制造的假阳性」：判据的采样面比它声称的范围大。
  //   第一版我按「有 box」过滤，Times New Roman 还在 —— 因为 <html> 自己就有 box。
  //   ⭐ 这暴露了判据本身没想清楚：要问的不是「这个元素渲染了吗」，
  //     而是**「用户看得见几种字体」** —— 只有直接承载文字的元素才算数。
  //     把 font-family 设在 body 上（最常见的写法）时 <html> 永远是 UA 默认值，
  //     按「有 box」过滤会让**每个正常页面**都多出一个幽灵字体族。
  const RENDERS = e => e.getClientRects().length > 0 &&
    [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  const fams = new Set(all.slice(0,800).filter(RENDERS)
      .map(e=>getComputedStyle(e).fontFamily.split(',')[0].trim().replace(/["']/g,'')));
  // ⛔ C 层（品牌方向）：字体族数量换个产品类型就该被推翻 → 报 INFO 不报 FAIL（铁律 49）
  add('font-count','1.5','[C] 首选字体族 ≤3（品牌方向，不阻断）', fams.size<=3?'PASS':'INFO', [...fams].join(' · '));
  const cols = new Set();
  for (const e of all.slice(0,800)) { for (const k of ['color','backgroundColor','borderTopColor']) {
    const c = getComputedStyle(e)[k]; const m = c && c.match(/\\d+/g); if (!m||m.length<3) continue;
    const [r1,g1,b1]=m.map(Number); if (Math.max(r1,g1,b1)-Math.min(r1,g1,b1)<30) continue;
    cols.add(r1+','+g1+','+b1); } }
  // ⛔ C 层：数据可视化产品合理地有几十种非灰色
  add('palette','3.2','[C] 非灰颜色 ≤12（品牌方向，不阻断）', cols.size<=12?'PASS':'INFO', cols.size+' 种');

  // 6 触控目标（按输入方式，桌面 24 / 触屏 44）
  // ⚠️ 仅把窗口调窄**不会**让 matchMedia('(pointer: coarse)') 变真——
  //    于是跑 390 宽也仍按桌面 24px 判触控目标。⭐ 窗口宽度不是输入方式。
  //    这里按宽度兜底：≤480 视为触屏，用 44px 门槛。
  // ⭐ 交互稿常常是**在桌面屏幕上展示一个手机外框** —— 视口是 1600，
  //   指针是 fine，但那一屏的目标输入方式就是触屏。
  //   窗口宽度判不出来，媒体查询也判不出来，**只有页面自己知道** ——
  //   所以让它声明：body 上的 data-end="mobile"。
  //   📌 这是「窗口宽度不是输入方式」再往前一步：既然推断不出来，就别推断，让它说。
  const declaredEnd = document.body.getAttribute('data-end');
  const coarse = declaredEnd === 'mobile' ||
                 matchMedia('(pointer: coarse)').matches || innerWidth <= 480;
  const min = coarse ? 44 : 24;
  const small = [...document.querySelectorAll('a,button,input,select,[role=button],[onclick]')].filter(vis)
    .map(e=>({e, r:e.getBoundingClientRect()})).filter(x=>x.r.width<min||x.r.height<min);
  add('hit-target','交互','命中区 ≥'+min+'px（'+(coarse?'触屏':'桌面指针')+'）', small.length?'FAIL':'PASS',
      small.length ? small.slice(0,5).map(x=>Math.round(x.r.width)+'×'+Math.round(x.r.height)+' 「'+(x.e.textContent||x.e.tagName).trim().slice(0,16)+'」').join(' · ')
                   : '全部达标');

  // 7 焦点指示 —— ⚠️ **必须真的聚焦再量**。
  //    首版在**默认态**读 outline，而 :focus-visible 的样式只在聚焦时才生效，
  //    于是一个焦点环做得完全正确的页面被判成不合格 —— 判据在构造上就是错的。
  //    这正是浏览器档存在的理由：静态档看得到规则，看不到「规则真的生效了没有」。
  // ⚠️ 2026-09-02：必须排除**根本聚不上焦**的元素。
  //   「<button disabled>」不在 tab 序列里，focus() 对它无效，于是量不到焦点环 ——
  //   这道判据就把「正确实现的禁用按钮」判成「缺焦点指示」。
  //   ⭐ 实测：原型骨架的「无权限」那一屏 1/2 被判无焦点环，那 1 个正是 disabled 的按钮。
  //   ⛔ 一道会把正确实现判红的门，最后一定会被人加豁免清单绕过去。
  const focusables = [...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')]
    .filter(vis)
    .filter(e => !e.disabled && e.getAttribute('aria-disabled') !== 'true' && e.getAttribute('tabindex') !== '-1');
  const prevFocus = document.activeElement;
  const noRing = focusables.filter(e=>{
    try { e.focus({preventScroll:true}); } catch(_) { return false; }
    const s = getComputedStyle(e);
    const hasOutline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0;
    const hasShadow = s.boxShadow && s.boxShadow !== 'none';
    return !hasOutline && !hasShadow; });
  try { if (prevFocus && prevFocus.focus) prevFocus.focus({preventScroll:true}); else document.activeElement.blur(); } catch(_) {}
  add('focus-ring','交互','可聚焦元素有焦点指示', focusables.length? (noRing.length?'FAIL':'PASS') : 'NA',
      focusables.length ? (noRing.length? noRing.length+'/'+focusables.length+' 个无焦点环且无替代' : focusables.length+' 个全部有')
                        : '页面没有可聚焦元素');

  // 8 横向滚动
  add('no-hscroll','布局','无横向滚动',
      document.documentElement.scrollWidth <= vw + 1 ? 'PASS':'FAIL',
      'scrollWidth '+document.documentElement.scrollWidth+' vs 视口 '+vw);

  // 9 标题层级不跳级
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map(h=>+h.tagName[1]);
  let skip = null;
  for (let i=1;i<hs.length;i++) if (hs[i]-hs[i-1] > 1) { skip = 'h'+hs[i-1]+' → h'+hs[i]; break; }
  add('heading-order','1.2','标题层级不跳级', hs.length? (skip?'FAIL':'PASS') : 'NA',
      hs.length ? (skip || hs.length+' 个标题顺序正确') : '页面没有标题');

  return R;
})`;
const PAYLOAD = MEASURE + '()';

// ⭐ 2026-09-02：逐路由审计。此前本档只审**打开时那一屏** ——
//    实测 agent-workbench 的 S6 产物 28 个场景里 27 个默认 hidden，
//    **96% 的产物从未进过任何门禁**，而报告只写「通过 9 失败 1」，看不出它只看了 1/28。
//    ⛔ 「只审了首屏」和「全审过了」在产物上长得一模一样 —— 这正是本 SOP 说的
//    「被裁掉的环节和跑了但没发现问题的环节，在产物上没有区别」。
const PAYLOAD_ALL_ROUTES = `(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const measure = ${MEASURE};
  // ⭐ 主题必须两个都审：**对比度是随主题变的**。
  //   浅色下 4.5:1 达标，深色下同一对颜色可能只有 1.1:1。
  //   实测本骨架：选中态用 background:var(--text) + color:#fff，
  //   浅色下是深底白字（对），**深色下 --text 接近纯白 → 白底白字**，肉眼几乎看不见。
  const themes = (Array.isArray(window.__PROTO_THEMES__) && window.__PROTO_THEMES__.length && ALL_THEMES)
    ? window.__PROTO_THEMES__ : [null];
  const routes = Array.isArray(window.__PROTO_ROUTES__) && window.__PROTO_ROUTES__.length
    ? window.__PROTO_ROUTES__.slice(0, 40) : null;
  const scenes = routes ? null
    : [...document.querySelectorAll(':not(body)[data-scene]')].map(e => e.dataset.scene).filter(Boolean);
  const model = routes ? 'route' : (scenes && scenes.length ? 'scene' : 'single');
  const stops = routes || (scenes && scenes.length ? scenes : [null]);
  const out = [];
  const auditedScenes = new Set();
  let skippedStops = 0;
  for (const theme of themes) {
  // ⚠️ 直接 setAttribute 会被应用自己的 render 立刻覆盖（它按 URL 里的 ?theme= 求值）——
  //    首版就是这么写的，于是「跑了两个主题」实际上两遍都在浅色下测，**报 0 失败**。
  //    ⭐ 主题和端一样是**状态**，状态就走 URL。
  for (const stop of stops) {
    if (stop !== null) {
      if (model === 'route') {
        let h = String(stop).replace(/^#/, '');
        if (theme) h += (h.indexOf('?') > -1 ? '&' : '?') + 'theme=' + theme;
        location.hash = h;
      }
      else { location.hash = stop;
             if (theme) document.documentElement.setAttribute('data-theme', theme);
             document.querySelectorAll(':not(body)[data-scene]').forEach(x => { x.hidden = x.dataset.scene !== stop; }); }
      await sleep(120);
    }
    // ⭐ 视觉档关心的是**渲染出来的状态**，不是 URL。
    //   同一个 data-scene 已经审过就不再审第二遍 ——
    //   scn=default 与 scn=slow 落定后是同一屏，重审只增加时长。
    //   ⛔ 「没人愿意跑的门禁等于没有门禁」，但省的必须是重复，不是覆盖：
    //   状态不同就一定会重新审，因为 data-scene 不同。
    const key = (theme || 'default') + '|' + (document.body.getAttribute('data-scene') || String(stop));
    if (auditedScenes.has(key)) { skippedStops++; continue; }
    auditedScenes.add(key);
    out.push({ stop: (theme ? '[' + theme + '] ' : '') + (stop || '-'), scene: key, rows: measure() });
  }
  }
  return { model, out, skippedStops };
})()`;


// ---------------------------------------------------------------- 降级实测
// ⭐ `interaction-gate` 查的是「有没有写 prefers-reduced-motion 分支」；
//    这一条查的是**降级之后到底长什么样** —— 两者不是一回事：
//    分支可以存在却漏掉某些元素（只写了 .btn 没写 .card），
//    或者写成 animation-duration:0.01ms 但 transition 还在跑。
//    motion-spec.md 一直把这条标成「人工，查不了」；模拟媒体特性之后它查得了。
const REDUCED_PROBE = `(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const stops = (Array.isArray(window.__PROTO_ROUTES__) && window.__PROTO_ROUTES__.length)
    ? window.__PROTO_ROUTES__.slice(0, 12) : [null];
  const bad = [];
  const dur = v => Math.max(...String(v || '0s').split(',')
    .map(x => parseFloat(x) * (x.indexOf('ms') > -1 ? 1 : 1000) || 0));
  for (const stop of stops) {
    if (stop !== null) { location.hash = String(stop).replace(/^#/, ''); await sleep(120); }
    for (const el of document.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      if (el.checkVisibility && !el.checkVisibility({ contentVisibilityAuto: true })) continue;
      const s = getComputedStyle(el);
      const td = dur(s.transitionDuration), ad = dur(s.animationDuration);
      // 允许 <=10ms 的「几乎为零」写法（animation-duration:0.01ms 是社区常见做法）
      if (td > 10 || ad > 10) {
        const tag = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
          ? '.' + el.className.trim().split(/\\s+/)[0] : '');
        const k = tag + ' ' + Math.round(Math.max(td, ad)) + 'ms';
        if (bad.indexOf(k) < 0) bad.push(k);
      }
    }
    if (bad.length >= 6) break;
  }
  return bad;
})()`;

// ---------------------------------------------------------------- 运行
async function run(target, viewport, allRoutes = false, allThemes = false) {
  // ⚠️ 旧版在这里先用 `--dump-dom` 启动一次 Chrome、把输出整个丢掉，再走 CDP 启动第二次
  //    （还写了一个从没被读过的 h.js）。逐路由审计后这会变成双倍开销，一并清掉。
  //    findChrome / CDP 已移到 `_browser.mjs`，两个门禁共用一份，避免其中一份先过期。
  // ⭐ 窄视口**真的**模拟触屏指针，而不是只把窗口调窄。
  //   否则页面里的 @media (pointer: coarse) 永远不生效，
  //   而本档又按宽度套 44px 阈值 —— **门禁要求的东西，正确写法没有机会满足**。
  const [w] = viewport.split('x').map(Number);
  const expr = (allRoutes ? PAYLOAD_ALL_ROUTES : PAYLOAD).replace('ALL_THEMES', String(!!allThemes));
  const [res] = await evalInPage(target, viewport, [expr], { coarsePointer: w <= 480 });
  if (!allRoutes) return { rows: res, stops: 1, model: 'single' };
  // 逐路由：同一条判据在多个停靠点各有结论，取**最差**并把出问题的停靠点写进证据
  const byId = new Map();
  for (const { stop, rows } of res.out)
    for (const r of rows) {
      const cur = byId.get(r.id);
      const worse = s => ({ FAIL: 3, PASS: 2, INFO: 1, NA: 0 })[s];
      if (!cur || worse(r.status) > worse(cur.status))
        byId.set(r.id, { ...r, ev: `[${stop}] ${r.ev}` });
    }
  return { rows: [...byId.values()], stops: res.out.length, model: res.model,
           skipped: res.skippedStops || 0 };
}

// ---------------------------------------------------------------- 输出
function report(rows, asJson, tv) {
  if (asJson) { console.log(JSON.stringify({ rows }, null, 1)); return rows.some(r => r.status === 'FAIL') ? 1 : 0; }
  const icon = { PASS: '✅', FAIL: '❌', NA: '➖', INFO: 'ℹ️' };
  for (const r of rows) {
    console.log(`${icon[r.status]} [${r.sec}] ${r.desc}`);
    console.log(`      ${r.ev}`);
  }
  const p = rows.filter(r => r.status === 'PASS').length;
  if (tv)
    console.log(`遍历：${tv.model === 'route' ? '路由模型' : tv.model === 'scene' ? '场景模型' : '单页'}　停靠点 ${tv.stops} 个` +
                (tv.stops > 1 ? '（同一判据取最差，证据里标出是哪个停靠点）' : '') +
                (tv.skipped ? `　（另有 ${tv.skipped} 个停靠点渲染出的状态与已审过的相同，跳过）` : '') +
                (tv.stops === 1 && tv.model === 'single' ? '　⚠️ 只审了当前这一屏' : ''));
  const f = rows.filter(r => r.status === 'FAIL').length;
  const n = rows.filter(r => r.status === 'NA').length;
  const i = rows.filter(r => r.status === 'INFO').length;
  console.log(`\n通过 ${p} · 失败 ${f} · 不适用 ${n} · 提示 ${i}（分母只算通过+失败 = ${p + f}）`);
  if (i) console.log('ℹ️ [C] 层是品牌与设计方向——**与默认风格不同 ≠ 质量不合格**（铁律 49），不阻断。');
  console.log('⚠️ 浏览器档只覆盖「必须真实渲染才能判」的那几条。');
  console.log('   静态档（visual-spec-gate.py）与本档查的是不同的东西，**不能互相替代**。');
  console.log('   质感/景深/光影仍然不可自动验，只能人按 visual-spec 第六节走查。');
  return f ? 1 : 0;
}

// ---------------------------------------------------------------- M8 自证
const GOOD_HTML = `<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>t</title><style>
:root{--fg:#1a1a1a;--bg:#fafafa;--accent:#1F6F5C}
body{background:var(--bg);color:var(--fg);font-family:Georgia,serif;margin:0;padding:64px}
main{max-width:34em;margin:0 auto}
h1{font-size:34px;line-height:1.25;margin:0 0 24px}
h2{font-size:20px;line-height:1.35;margin:32px 0 12px}
p{font-size:17px;line-height:1.7;margin:0 0 16px}
button{min-width:120px;min-height:44px;background:var(--accent);color:#fff;border:0;border-radius:6px}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card{transition:transform .24s cubic-bezier(.2,0,0,1);padding:8px}
@media (prefers-reduced-motion: reduce){ *{transition:none !important;animation:none !important} }
</style></head><body><main>
<div class="card">带动效的卡片</div>
<h1>标题</h1>
<h2>小节</h2>
<p>这是一段用于测量行长的正文内容，它的长度经过控制，确保每行落在二十五到四十个汉字之间的合理区间内部。</p>
<p>第二段同样受控，用来验证行长判据能在多段情况下稳定给出结论而不产生波动或者误差。</p>
<button>确定</button>
<details><summary>折叠区</summary><div><a href="#x" style="outline:none">收起来的链接</a></div></details>
</main></body></html>`;

// ⚠️ 每条变异都必须真的改到文件。首版写成 `.replace('color:#1a1a1a', …)`，
//    而 CSS 里是 `--fg:#1a1a1a`，变异是 **no-op**，于是「对比度」那条反例失效、
//    自证却看不出来。这与元门禁里踩过的坑同源：**变异没改到东西，就不是被杀死，是用例坏了。**
// 反例：写了 reduced-motion 分支，但它**只覆盖 button、漏掉 .card** ——
// ⭐ 这正是「有分支 ≠ 降级到位」：静态查分支存在与否的门对它完全无感。
const REDUCED_BAD = GOOD_HTML.replace(
  '@media (prefers-reduced-motion: reduce){ *{transition:none !important;animation:none !important} }',
  '@media (prefers-reduced-motion: reduce){ button{transition:none} }');
if (REDUCED_BAD === GOOD_HTML) throw new Error('自证用例坏了：reduced-motion 反例是 no-op');
const MUTATIONS = [
  ['max-width:34em', 'max-width:none'],                 // 行长爆掉
  ['--fg:#1a1a1a', '--fg:#bbbbbb'],                     // 对比度不足
  ['min-width:120px;min-height:44px', 'width:16px;height:16px'],  // 命中区过小
  ['<h2>小节</h2>', '<h4>跳级</h4>'],                    // 标题跳级
];
const BAD_HTML = MUTATIONS.reduce((acc, [a, b]) => {
  if (!acc.includes(a)) throw new Error('自证用例坏了：变异目标不存在 → ' + a);
  return acc.replace(a, b);
}, GOOD_HTML);

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
  const t = mkdtempSync(join(tmpdir(), 'ba-st-'));
  const g = join(t, 'good.html'), b = join(t, 'bad.html');
  writeFileSync(g, GOOD_HTML); writeFileSync(b, BAD_HTML);
  console.log('M8 自证 —— 正例绿 / 反例每类必红 / 无效输入报 2 不报 0\n');
  let ok = true;
  const rg = (await run(g, '1440x900')).rows;
  const gf = rg.filter(r => r.status === 'FAIL');
  const p1 = gf.length === 0; ok &&= p1;
  console.log(`  ${p1 ? '✅' : '❌'} 正例（受控页面）                 失败项 ${gf.length}${gf.length ? '：' + gf.map(x => x.id).join(',') : ''}`);
  const rb = (await run(b, '1440x900')).rows;
  for (const id of ['line-length', 'contrast', 'hit-target', 'heading-order']) {
    const hit = rb.find(r => r.id === id && r.status === 'FAIL');
    ok &&= !!hit;
    console.log(`  ${hit ? '✅' : '❌'} 反例 ${id.padEnd(28)} 必须被抓到`);
  }
  // 🆕 2026-09-06 独立样本实测（经授权脱敏的真实交互稿，**不是照着本门做的**）：
  //   渐变色块上的白字，`bgOf` 找不到非透明 backgroundColor 会一路走到 body
  //   ⇒ 被算成「白底白字 1.00:1」⇒ **报成对比度违规**，把人送去调一个不存在的颜色。
  //   ⭐ 测量失败必须报成「量不了」，不许报成「有发现」。
  {
    const grad = join(t, 'grad.html');
    writeFileSync(grad, GOOD_HTML.replace('</style>',
      '.chip{background-image:linear-gradient(90deg,#2b6cb0,#4299e1);color:#fff;padding:8px}</style>')
      .replace('</body>', '<div class="chip">渐变上的白字</div></body>'));
    const rr = (await run(grad, '1440x900')).rows;
    const viol = rr.find(r => r.id === 'contrast' && r.status === 'FAIL');
    const na = rr.find(r => r.id === 'contrast-unmeasured');
    const c1 = !viol && !!na; ok &&= c1;
    console.log(`  ${c1 ? '✅' : '❌'} 渐变背景上的文字 → 归「量不了」，不报成对比度违规`);
  }
  // 降级实测：正例（分支覆盖全部）必须绿，反例（分支漏掉 .card）必须红
  const rg2 = await run(g, '1440x900', false, false);
  const [goodBad] = await evalInPage(g, '1440x900', [REDUCED_PROBE], { reducedMotion: true });
  const p2 = goodBad.length === 0; ok &&= p2;
  console.log(`  ${p2 ? '✅' : '❌'} 正例 reduced-motion 降级到位        ${p2 ? '无残留动效' : '实得 ' + JSON.stringify(goodBad)}`);
  const rb2 = join(t, 'rmbad.html'); writeFileSync(rb2, REDUCED_BAD);
  const [badBad] = await evalInPage(rb2, '1440x900', [REDUCED_PROBE], { reducedMotion: true });
  const p3 = badBad.length > 0; ok &&= p3;
  console.log(`  ${p3 ? '✅' : '❌'} 反例 分支漏掉 .card 必须被抓到      ${p3 ? badBad[0] : '没抓到'}`);

  // ⭐⭐ 已知答案检验（2026-09-04 立）：**量具本身准不准**。
  //    判据可以是对的、门禁可以是绿的，而量具在骗你 —— 同一天实测到
  //    `--window-size` 被 macOS 钳到最小 500px，于是所有「390 移动端」测量
  //    其实跑在 500px 上，而它一直报着看起来正常的数字。
  //    ⇒ 凡是产出**绝对数值**的判据，都要有一条「拿已知答案的输入验一遍」。
  //    ⭐ 这类断言看起来像废话（#000 on #fff 就该是 21），**正因为是废话才没人写**。
  const KA = join(t, 'known.html');
  writeFileSync(KA, '<style>body{margin:0}p{font-size:16px;padding:4px}</style>' +
    '<p style="color:#000;background:#fff">黑白 21.00</p>' +
    '<p style="color:#767676;background:#fff">767676 4.54 刚过线</p>' +
    '<p style="color:#777;background:#fff">777 4.48 刚不过</p>' +
    '<p style="color:#949494;background:#fff">949494 3.03</p>');
  const rk = (await run(KA, '1440x900')).rows;
  const ck = rk.find(r => r.id === 'contrast');
  const ev = String(ck && (ck.ev || ck.evidence) || '');
  const p4 = !!ck && ck.status === 'FAIL' && ev.includes('3.03') && ev.includes('4.48')
             && !ev.includes('21.0') && !ev.includes('4.54');
  ok &&= p4;
  console.log(`  ${p4 ? '✅' : '❌'} 已知答案：对比度算得准（3.03/4.48 抓到，21.00/4.54 放行）` +
              `${p4 ? '' : '　实得 ' + ev.slice(0, 90)}`);
  // 已知答案：viewport 真的是请求的那个宽度（`--window-size` 曾被钳到 500）
  const [iw] = await evalInPage(KA, '390x844', ['innerWidth']);
  const p5 = iw === 390; ok &&= p5;
  console.log(`  ${p5 ? '✅' : '❌'} 已知答案：请求 390 实得 ${iw}（量具被钳过，见 _browser.mjs）`);

  try {
    execFileSync(process.execPath, [resolve(process.argv[1]), join(t, 'nope.html')], { stdio: 'pipe' });
    console.log('  ❌ 不存在的文件               期望非 0'); ok = false;
  } catch (e) {
    const g2 = e.status === 2; ok &&= g2;
    console.log(`  ${g2 ? '✅' : '❌'} 不存在的文件                 期望 2 实得 ${e.status}`);
  }
  // 🚨 空页必须报 2（没量到），**不许报 0（全部通过）**。
  //   2026-09-06 实测：修之前喂 `<body></body>` 得到「通过 5 · 失败 0」并退 0 ——
  //   那 5 条全是「不许出现 X」型判据在真空里成立。⭐ 分母为零的绿是假绿。
  {
    const e0 = join(t, 'empty.html');
    writeFileSync(e0, '<!doctype html><html><body></body></html>');
    let st = 0;
    try { execFileSync(process.execPath, [resolve(process.argv[1]), e0], { stdio: 'pipe' }); }
    catch (e) { st = e.status; }
    const g3 = st === 2; ok &&= g3;
    console.log(`  ${g3 ? '✅' : '❌'} 空页 → 没量到(2)，不是全过(0)   期望 2 实得 ${st}`);
  }
  console.log(`\n${ok ? '✅ 浏览器档会出声' : '❌ 自证失败'}`);
  process.exit(ok ? 0 : 1);
}

// ---------------------------------------------------------------- main
const argv = process.argv.slice(2);
if (argv.includes('--self-test')) { await selfTest(); }
else {
  // ⚠️ 未知 `--flag` 必须报错：静默丢弃会让门禁只跑一半而照样报绿（见 _argv.mjs）
  //    本门禁尤其危险 —— `--all-route`（少个 s）会让它只审打开时那一屏。
  rejectUnknown(argv, ['--json','--viewport','--all-viewports','--all-routes','--all-themes','--reduced-motion','--self-test'],
    '用法: browser-audit.mjs <file.html|url> [--json] [--viewport WxH] [--all-viewports] [--all-routes] [--all-themes]');
  const files = argv.filter(a => !a.startsWith('--'));
  if (!files.length) { console.log(`用法: browser-audit.mjs <file.html|url> [--json] [--viewport 1440x900]`); process.exit(2); }
  const vi = argv.indexOf('--viewport');
  // ⚠️⚠️ 2026-08-31：此前一次只跑一个视口、默认 1440x900——
  //    而文档声称「四视口全覆盖」。**移动端布局从未真正进过这道门。**
  //    ⭐ 说明层写了四个，执行层跑一个，等于没跑。
  const vpArg = vi > -1 && argv[vi + 1] ? argv[vi + 1] : null;
  const vps = vpArg ? vpArg.split(',') : (argv.includes('--all-viewports')
      ? ['1600x900', '1280x800', '820x1180', '390x844'] : ['1440x900']);
  // ⚠️ 同 --all-viewports 的教训：不带 --all-routes 时**只审打开时那一屏**。
  //    多场景/多路由的 demo 不带这个参数，等于只审了 1/N。
  const allRoutes = argv.includes('--all-routes');
  // ⛔ 深色主题从来没进过这道门 —— 而对比度恰恰是随主题变的那一类
  const allThemes = argv.includes('--all-themes');
  if (!/^https?:/.test(files[0]) && !existsSync(files[0])) { console.error('UNABLE: 文件不存在 ' + files[0]); process.exit(2); }
  let rows = []; let traversal = null;
  for (const v of vps) {
    let r;
    try { r = await run(files[0], v, allRoutes, allThemes); }
    catch (e) { console.error('UNABLE: ' + e.message); process.exit(2); }
    traversal = { stops: r.stops, model: r.model, skipped: r.skipped };
    r = r.rows;
    // 多视口时给每条结论打上视口标签，否则 390 的失败会被误读成桌面的
    rows = rows.concat(vps.length > 1 ? r.map(x => ({ ...x, desc: `[${v}] ${x.desc}` })) : r);
  }
  // 降级实测：只跑一遍（动效降级与视口无关），成本约 15s
  if (argv.includes('--reduced-motion') || allRoutes) {
    try {
      const [bad] = await evalInPage(files[0], vps[0], [REDUCED_PROBE], { reducedMotion: true });
      rows.push({ id: 'reduced-motion-honored', sec: '动效',
        desc: 'prefers-reduced-motion 下动效真的降到零（不是只写了分支）',
        status: bad.length ? 'FAIL' : 'PASS',
        ev: bad.length ? bad.slice(0, 5).join(' · ') : '降级后无元素仍有 >10ms 的过渡/动画' });
    } catch (e) {
      rows.push({ id: 'reduced-motion-honored', sec: '动效',
        desc: 'prefers-reduced-motion 下动效真的降到零', status: 'NA',
        ev: '跑不了：' + String(e.message).slice(0, 60) + '（**没测**，不折叠进通过）' });
    }
  }
  // ⛔ **分母为零的绿是假绿** —— dead-click-gate 早就这么判，这道门一直没有。
  //   2026-09-06 实测：喂一张 `<body></body>` 的空页，它报「通过 5 · 失败 0」并退 0。
  //   那 5 条「通过」全是「不许出现 X」型判据在**真空里成立**：
  //   页面上什么都没有，当然什么都没违反。
  //   ⭐ 这是横扫兄弟门禁时抓到的第二例（第一例是 platform-parity 的「一端没渲染」）——
  //     同一个盲点不会只长在我碰巧发现的那一道门上。
  try {
    // ⚠️ evalInPage 的 expressions 是**字符串**（Runtime.evaluate 求值），不是函数。
    //   第一版我传了箭头函数 ⇒ 页面里求值得到一个函数对象、拿不到值 ⇒ 探针静默失败。
    const EMPTY_PROBE = `(() => {
      const vis = [...document.querySelectorAll('body *')].filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
      });
      return { els: vis.length, text: (document.body.innerText || '').trim().length };
    })()`;
    const [cnt] = await evalInPage(files[0], vps[0], [EMPTY_PROBE]);
    if (cnt && !cnt.els && !cnt.text) {
      console.error('UNABLE: 页面上没有任何可见元素或文本 —— 这不是「全部通过」，是**没量到**。' +
                    '空页上「不许出现 X」的判据会真空成立，通过数没有意义。' +
                    '（是不是传错文件，或者 demo 需要先导航到某个路由？）');
      process.exit(2);
    }
  } catch (e) {
    // ⚠️ 探针自己失败不许改写既有结论 —— 那会把「量不了空不空」变成「有缺陷」。
    console.error('（空页探针没跑成：' + String(e.message).slice(0, 60) + '，不影响上面的结论）');
  }
  process.exit(report(rows, argv.includes('--json'), traversal));
}
