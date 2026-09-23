// ============================================================================
// 端形态对账门（S6 出场）—— 判据见 references/platform-parity.md
//
// 用户要求：「PC 端的样式和 PC 最后完成 app 一致，移动端和移动端最后完成的 app 一致」。
// 机器验不了「像不像那一端的原生应用」，但能验两件此前**全流程没人查**的事：
//
//   ① 形式必须不同 —— 两端渲染出的结构若雷同，说明只是把同一张稿子拉宽拉窄。
//      实证：桌面组件工具箱 15 个组件、移动框架 97 个，**两边都有的只有 6 个**
//      （全是最原子的控件；导航/覆盖层/列表/手势没有一个共用）。
//      一套 DOM 两个断点，不可能同时像两端的原生应用。
//
//   ② 实质必须相同 —— 两端呈现的字段/文案/状态若不同，那是规格缺口。
//      ⭐ 移动端少一个字段有三种可能：刻意分层 / 放不下砍了 / 忘了。
//      **三种在产物上长得一模一样**，只有显式登记能把它们分开。
//
// ⚠️ 诚实边界：绿了只说明「不是同一张稿子拉宽拉窄」且「两端讲的不是两件事」。
//    像不像，仍然只能人打开那一端的真实应用对着看（见规格第四节铁律）。
// 退出码：0=通过  1=有缺口  2=跑不了
// ============================================================================
import { existsSync, readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { evalInPage, browserPreflight } from './_browser.mjs';
import { HELPERS } from './_page-helpers.mjs';
import { rejectUnknown } from './_argv.mjs';

// 登记册#1：--help 只显示帮助（文件头注释）并退 0
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  const _src = (await import('node:fs')).readFileSync(new URL(import.meta.url), 'utf8');
  console.log(_src.split('\n').filter(l => l.startsWith('//')).slice(0, 40).join('\n'));
  process.exit(0);
}

const PROBE = `(async (ROUTES) => {
${HELPERS}
  const out = [];
  for (const r of ROUTES) {
    location.hash = '/__pp_reset__'; await sleep(30);
    location.hash = r; await settle(8000); await sleep(120);
    const vis = el => el.checkVisibility ? el.checkVisibility({ contentVisibilityAuto: true })
                                         : !!el.getClientRects().length;
    // 结构指纹：可见元素的「标签+角色」序列。**不含文本** ——
    // 文本相同是我们要求的（实质），结构相同才是问题（形式）。
    const nodes = [...document.querySelectorAll('body *')].filter(vis);
    const fp = nodes.map(e => e.tagName.toLowerCase() +
      (e.getAttribute('role') ? ':' + e.getAttribute('role') : '')).join('>');
    // 可见文本集合：用于实质对账。
    // ⭐ 只取**内容区**：导航外壳（nav/header/footer 及对应 role）按规格第二节
    //   本来就必须两端不同，把它算进实质对账 = 用一条判据惩罚另一条判据要求的事。
    //   （第一版就是这么错的：它把 PC 的「侧栏」二字报成「移动端缺了这个字段」。）
    //   「data-demo-chrome」属性是给**交互稿自己的评审外壳**留的显式出口
    //   🚨 这一行原本用反引号包属性名 —— 而它在模板字面量**内部**，
    //      第一个反引号直接把 PROBE 提前闭合，后面被当成 JS 求值。
    //      ⛔ 「node --check」**查不出这一类**：它语法上完全合法，只是语义错了。
    //      ⭐ 我在**解释这个坑的那句注释里又踩了一次**（第七次）——
    //        说明「知道这条规则」完全挡不住它，能挡住的只有工具。
    //      本轮是第六次踩同一个坑 —— 模板字面量里一律用「」，不用反引号。
    //   （场景导航、端切换器这类东西不是产品内容，两端不一致完全正常）。
    //   ⛔ 必须是显式标记而不是「看起来像工具栏就跳过」—— 后者会把真内容也吞掉。
    const CHROME = 'nav,header,footer,aside,[role=navigation],[role=banner],' +
      '[role=contentinfo],[role=complementary],[data-demo-chrome]';
    const inChrome = e => !!e.closest(CHROME);
    // ⚠️ 2026-09-04：「aria-hidden=true」的子树**按定义就不是内容** ——
    //    它对读屏不存在。把装饰字符（如返回键前的「←」）算进实质对账，
    //    会把「PC 有装饰、移动端没有」报成内容缺口。
    //    ⛔ 这是我自己修 a11y 时引入的假阳性：把箭头从可访问名里摘出来做成
    //      aria-hidden 的 span 之后，这道门当场红了两条。
    //   🚨 本注释第一版又把属性名用反引号包了 —— 第八次踩同一个坑，
    //      而这次是我自己建的元规则 template-literal-backtick 抓到的（工具起作用了）。
    //    ⭐ 判据要与它自己主张的语义一致：既然认可访问名，就得认 aria-hidden。
    const isDecor = e => !!(e.closest && e.closest('[aria-hidden="true"]'));
    const texts = new Set(), allTexts = new Set();
    nodes.forEach(e => {
      if (isDecor(e)) return;               // 装饰不进实质对账
      const chrome = inChrome(e);
      [...e.childNodes].forEach(n => {
        if (n.nodeType !== 3) return;
        const tx = n.textContent.replace(/\\s+/g, ' ').trim();
        if (!tx || /^[\\d\\s.,:%-]+$/.test(tx)) return;
        allTexts.add(tx);
        if (!chrome) texts.add(tx);
      });
    });
    // 可访问名称也收进 allTexts：移动端的返回是「‹」而可访问名是「返回列表」，
    // 只比可见文本会把它判成「PC 有而移动端没有」。
    nodes.forEach(e => {
      const an = e.getAttribute && (e.getAttribute('aria-label') || e.getAttribute('title'));
      if (an && an.trim()) allTexts.add(an.trim());
    });
    // 命中区最小值（只看真正可交互的）
    const CLICKABLE = 'a[href],button,input,select,textarea,[role=button],[role=link],[tabindex]';
    let minHit = 1e9;
    [...document.querySelectorAll(CLICKABLE)].filter(vis).forEach(e => {
      if (e.disabled || e.getAttribute('aria-disabled') === 'true') return;
      const b = e.getBoundingClientRect();
      if (b.width && b.height) minHit = Math.min(minHit, Math.min(b.width, b.height));
    });
    out.push({
      route: r,
      scene: document.body.getAttribute('data-scene') || '',
      fr: document.body.getAttribute('data-fr') || '',
      fp, texts: [...texts], allTexts: [...allTexts],
      minHit: minHit === 1e9 ? null : Math.round(minHit),
    });
  }
  return out;
})(__ROUTES__)`;

// 端特征探针：这些是**声明性**的（CSS 里有没有写），与上面的渲染实测互补。
// 🔴 2026-09-05 endForked 此前只认属性约定 [data-end=…] 这一种写法。
//    而**容器类**是同样合法的分叉约定（形如 .app.mobile{...}）——
//    云端办公 Agent 项目**有意**选它：它的 demo 是「桌面外壳里嵌一个移动机框」，
//    在 body 上挂端声明会连 demo 自己的导航按钮都被按触屏判。
//    ⇒ 判据只认一种写法 ⇒ 那个项目实得 0 条，而它其实有分叉。
//    ⭐ 现在两种都认：属性约定 + 端令牌类选择器（mobile/phone/handset/pc/desktop/tablet）。
// ⚠️ 本块是**模板字面量**：反斜杠要双写，且⛔ 注释里不许出现反引号（会提前闭合）。
// 🔴🔴 2026-09-06：此前这里只读**内联 `<style>`** —— `<link rel=stylesheet>` 一张不看。
//   后果：任何把 CSS 放外部文件的真实项目（也就是绝大多数），
//   都会被判「没有 safe-area / 没有 hover 护栏 / 端分叉 0 条」**三条假阳性**。
//   本仓自己的参考产物 templates/proto 就是这样：app.css 里 safe-area 有 4 处、
//   hover 护栏 2 处，门禁却报 0。
//   ⭐ 自证一直没抓到，因为**所有夹具都是内联样式** —— 判据只盖住了我造的那一半世界。
//   ⛔ 不能改成在页面里读 cssRules：file:// 下外链样式表跨源，读会抛 SecurityError，
//     那样只会把「读不到」变成另一种静默的 0。
//   ⇒ 探针只负责把**内联 CSS + 所有 link 的 href** 交回来，由 Node 侧按磁盘读。
const FEATURES = `(() => {
  const inline = [...document.querySelectorAll('style')].map(s => s.textContent).join('\\n');
  const links = [...document.querySelectorAll('link[rel~="stylesheet"][href]')]
    .map(l => l.getAttribute('href'));
  return { inline, links };
})()`;

// 端特征的判定放在 Node 侧：这里能真的打开外链 CSS 文件。
function featuresFrom(raw, demoPath) {
  const dir = dirname(resolve(demoPath));
  let css = raw.inline || '';
  const unread = [];
  for (const href of (raw.links || [])) {
    if (/^(https?:|data:|\/\/)/i.test(href)) { unread.push(href); continue; }
    const f = resolve(dir, href.split('?')[0].split('#')[0]);
    try { css += '\n' + readFileSync(f, 'utf8'); }
    catch { unread.push(href); }
  }
  return {
    safeArea: /env\(\s*safe-area-inset/.test(css),
    hoverGuard: /@media[^{]*\(\s*hover\s*:\s*hover/.test(css),
    coarseRule: /@media[^{]*\(\s*pointer\s*:\s*coarse/.test(css),
    endForked: (css.match(/\[data-end\s*=/g) || []).length +
               (css.match(/\.[\w-]*\b(?:mobile|phone|handset|pc|desktop|tablet)\b[\w-]*(?=[\s,.>{:])/g) || []).length,
    unread,        // ⚠️ 读不到的样式表：它们里面有什么，这道门**不知道**
  };
}

function routesFor(end, base) {
  // 🔴 2026-09-06：此前只会**拼查询串** `?end=<端>`，那假定产品用查询参数切端。
  //    而场景式 demo 的端写在**锚点的中间一段**（`#f01-pc-partial` / `#f01-mobile-partial`），
  //    拼 `?end=mobile` 对它没有任何作用 ⇒ **两端拿到的是同一个场景**，
  //    相似度必然 ~93%，而它被报成「端形态太薄」。
  //    ⭐⭐ 这是**判据与产物模型不匹配**，不是产品缺陷 —— 门禁给出的是
  //    「确定的、专业的、错误的」答案（云端办公 Agent 项目实测撞到）。
  //    ⇒ 锚点里出现 `-pc-` / `-mobile-` 这类端段时，**按段替换**；否则退回拼查询串。
  const END_SEG = /-(pc|mobile|desktop|phone|tablet)-/;
  return base.map(r => END_SEG.test(r)
    ? r.replace(END_SEG, '-' + end + '-')
    : r + (r.includes('?') ? '&' : '?') + 'end=' + end);
}

function jaccard(a, b) {
  const A = new Set(a), B = new Set(b);
  const inter = [...A].filter(x => B.has(x)).length;
  const uni = new Set([...A, ...B]).size;
  return uni === 0 ? 1 : inter / uni;
}

// ⛔⛔ 全部路由都登记了差异 ⇒ 这道判据被**整体静音**。
//   ⭐ 形状由并行会话 fm-agent 提出：「**能让它闭嘴，但不能悄悄让它闭嘴**」——
//   豁免出口本身要有上限，否则它会变成往里塞东西的地方。
//   这里不设魔数：**「每一条被比对的路由都被登记」** 本身就是那条线。
function checkFullySilenced(routes, declared, bad, info) {
  const keys = routes.map(r => String(r).replace(/[?&]end=\w+/, ''));
  const covered = keys.filter(k =>
    Object.prototype.hasOwnProperty.call(declared, k));
  // ⚠️ 单条路由时「全部登记」＝「唯一那条被登记」，那是豁免的**合法用法**，不是静音。
  //    「整体静音」这个概念要 ≥2 条路由才成立。这不是魔数，是这个概念自己的下限。
  if (keys.length >= 2 && covered.length === keys.length) {
    // ⭐ 2026-09-06 云端办公 Agent 实测：有一类产品**每一条路由的差异都是拍过板的定位**
    //   （移动端＝遥控器，非目标明写「不追求移动端功能完整」⇒ 每一屏都刻意有差）——
    //   「不许全登记」会惩罚这种正确用法（门禁不许惩罚正确实现）。
    //   出口必须**大声**，不是后门：① 顶层 `_full_coverage_reason` 写清定位；
    //   ② `_full_coverage_anchor` 引规格原文（≥12 字，⚠️ 门禁拿不到规格文件，
    //   长度是最低门槛，⛔ 引文是否真实要靠评审的人顺着去查）；
    //   ③ 即便放行也把这行**打印出来** —— 能让它闭嘴，不能悄悄让它闭嘴。
    const fr = declared._full_coverage_reason, fa = declared._full_coverage_anchor;
    if (typeof fr === 'string' && fr.trim().length >= 8 &&
        typeof fa === 'string' && fa.trim().length >= 12) {
      (info || bad).push(`[登记] ⚠️ 全部 ${keys.length} 条路由都登记了端差异，由显式定位声明放行：` +
        `${fr.trim()}（规格锚:「${fa.trim().slice(0, 48)}」）—— ⛔ 这条声明本身是评审对象，不是免检章`);
    } else {
      bad.push(`[登记] **每一条路由（${keys.length} 条）都登记了端差异** —— ` +
               '实质对账这一半已被整体静音。豁免可以有，但不能覆盖全部；' +
               '若差异确实是产品定位（每屏刻意有差），用顶层 `_full_coverage_reason` + ' +
               '`_full_coverage_anchor`（引规格原文）**显式**声明 —— 堆满逐条豁免不算声明');
    }
  }
}

function judge(pc, mo, feat, opts) {
  const bad = [], info = [];
  // ── ① 形式必须不同 ──
  const pairs = [];
  for (const p of pc) {
    // ⚠️ 配对要把**两种端标记**都归一化掉：查询串 `?end=x` 与锚点里的端段 `-x-`。
    //    只剥前者的话，锚点段式的两端永远配不上 ⇒ 报「一个可比路由都没有」(UNABLE)。
    const norm = r => r.replace(/[?&]end=\w+/, '')
                       .replace(/-(pc|mobile|desktop|phone|tablet)-/, '-@-');
    const m = mo.find(x => norm(x.route) === norm(p.route));
    if (m) pairs.push([p, m]);
  }
  if (!pairs.length) return { bad: ['UNABLE'], info: ['两端一个可比路由都没有'] };
  // ⚠️ 2026-09-05：空页面此前报 FAIL「两端结构指纹完全相同」——
  //    那句话等于说「你没做端形态」，而真相是**这个页面没有可比的东西**。
  //    ⛔ 有人传错文件时，FAIL 会把他送去修一个不存在的问题
  //      （本轮第 5 次「错误诊断把人引向不存在的问题」）。
  //    ⭐ 判据：两端**都**没有任何内容区文本，就不是「端形态没做」，是没得判 → UNABLE。
  const noContent = pairs.every(([p, m]) =>
    (p.texts || []).length === 0 && (m.texts || []).length === 0);
  if (noContent)
    return { bad: ['UNABLE'],
             info: ['两端的内容区都是空的 —— 页面上没有可比的东西，无从判断端形态。' +
                    '是不是传错文件了，或者 demo 需要先导航到某个路由？'] };
  // ⚠️ **一端整页(含外壳)一个字都没渲染出来** ≠ 「这一端没做」。
  //   分层要分清：内容区空、外壳有东西 ⇒ 照常判（那可能是真发现）；
  //   **连外壳都空** ⇒ 这一端根本没渲染成功，多半是加载超时/路由没就绪/取值取早了。
  //   把它判成「实质对不上」，会把人送去修一个不存在的端形态问题。
  //   ⭐ 2026-09-06：最终自证里这道门无故红过一次，**成因至今未证实**（并发 6 份复现不出、
  //   夹具目录是 mkdtemp 唯一前缀也排除了碰撞）。这条守卫不是那次的确诊，
  //   而是让下次的红能自己说清楚：要么变成 UNABLE，要么把逐路由字数打出来。
  const blankSide = ([p, m]) =>
    ((p.allTexts || []).length === 0) !== ((m.allTexts || []).length === 0);
  const blanks = pairs.filter(blankSide);
  const usable = pairs.filter(x => !blankSide(x));
  const counts = ps => JSON.stringify(ps.map(([p, m]) =>
    [p.route, (p.allTexts || []).length, (m.allTexts || []).length]));
  if (!usable.length)
    return { bad: ['UNABLE'],
             info: ['有一端整页(含外壳)一个字都没渲染出来，另一端正常 —— 这是**没量到**，' +
                    '不是端形态缺陷。逐路由 [路由, PC字数, 移动字数]：' + counts(blanks)] };
  if (blanks.length)
    info.push('这些路由有一端整页没渲染出来，已从对账中排除（没量到 ≠ 没做）：' + counts(blanks));
  for (const [p, m] of usable) {
    const sim = jaccard(p.fp.split('>'), m.fp.split('>'));
    if (p.fp === m.fp)
      bad.push(`[形式] ${p.route}：两端结构指纹**完全相同** —— 这不是端形态，是同一张稿子换了个宽度`);
    else if (sim > opts.fpMax)
      bad.push(`[形式] ${p.route}：两端结构相似度 ${(sim * 100).toFixed(0)}% > ${opts.fpMax * 100}% —— 端形态太薄`);
  }
  // ⛔ 有样式表读不到时，「没找到」**不等于**「不存在」。
  //   这三条都是**断言缺席**的判据 —— 而缺席只有在「全都读到了」的前提下才成立。
  //   读不到还照常报红，就是把「没量到」写成「有缺陷」（今天第 3 次同型）。
  if ((feat.unread || []).length &&
      (!feat.safeArea || !feat.hoverGuard || feat.endForked < opts.minForks))
    return { bad: ['UNABLE'],
             info: ['这些样式表读不到，CSS 类判据没量到：' + feat.unread.join('、') +
                    '。它们里面有没有 safe-area / hover 护栏 / 端分叉，这道门**不知道** —— ' +
                    '所以既不报通过也不报缺陷。（远程 CDN 样式表请先落到本地再验）'] };
  // 端特征（声明层）
  if (!feat.safeArea) bad.push('[形式] CSS 里没有 env(safe-area-inset-*) —— 移动形态没处理刘海/Home 条');
  if (!feat.hoverGuard) bad.push('[形式] CSS 里没有 @media (hover: hover) 护栏 —— hover 态会漏到触屏上');
  if (feat.endForked < opts.minForks)
    bad.push(`[形式] 按端分叉的 CSS 规则只有 ${feat.endForked} 条（阈值 ${opts.minForks}）—— ` +
             '端形态停留在外壳层。实证：移动端框架 67/68 个组件都按平台分叉');
  // 命中区
  for (const m of mo)
    if (m.minHit !== null && m.minHit < 44)
      bad.push(`[形式] 移动形态 ${m.route} 最小命中区 ${m.minHit}px < 44px`);
  // ── ② 实质必须相同 ──
  for (const [p, m] of usable) {
    // ⭐ 两个方向都要查。第一版只查「PC 有而移动没有」，
    //   移动端独有的一律放行 —— 那是个没有理由的单边豁免：
    //   移动端多出一个内容字段，同样是「以哪份为准」的规格缺口。
    const key = p.route.replace(/[?&]end=\w+/, '');
    // 登记项支持两种写法：数组（只登记文本）或 {texts, anchors}（还登记锚点可以不同）。
    const raw = opts.declared[key] || [];
    const declared = Array.isArray(raw) ? raw : (raw.texts || []);
    const anchorsMayDiffer = !Array.isArray(raw) && raw.anchors === true;
    // ⛔⛔ 登记必须写理由。**不要求理由的登记出口就只是个静音开关** ——
    //   而「刻意的信息分层 / 放不下砍了 / 忘了」这三种情况，
    //   在产物上本来就长得一模一样，理由是唯一能把它们分开的东西。
    //   ⭐ 一个能一键静音的判据，最终会被用来静音所有东西。
    const hasEntry = Object.prototype.hasOwnProperty.call(opts.declared, key);
    if (hasEntry && (Array.isArray(raw) || !String(raw.reason || '').trim()))
      bad.push(`[登记] ${key}：登记了端差异却没写 reason —— ` +
               '不写理由的登记＝静音开关。「刻意分层 / 放不下砍了 / 忘了」三种情况产物上一模一样');
    // ⛔ 理由不许是占位符 —— 「TODO / 待定 / 暂时 / 先这样」等于没写。
    if (hasEntry && !Array.isArray(raw) &&
        /^(todo|tbd|待定|暂时|先这样|后面再说|\?+|-+)\s*$/i.test(String(raw.reason || '').trim()))
      bad.push(`[登记] ${key}：reason 是占位符「${raw.reason}」—— ` +
               '占位符理由和不写理由是同一件事，只是看起来像写过了');
    // ⭐ 「内容挪进外壳」不是「内容没了」：移动端把标题挪到 app bar、
    //   把返回做成 app bar 上的「‹」，都是规格 P1/P2 **要求**的形态差异。
    //   判据因此分两层：**缺不缺**看对端的「内容 + 外壳 + 可访问名」全集；
    //   **在不在内容区**只记 ℹ️。⛔ 只比内容区会把正确的端形态判成信息丢失 ——
    //   而那正是这道门自己要求做出来的东西。
    const gonePC = p.texts.filter(x => !m.allTexts.includes(x) && !declared.includes(x));
    const goneMO = m.texts.filter(x => !p.allTexts.includes(x) && !declared.includes(x));
    const movedPC = p.texts.filter(x => !m.texts.includes(x) && m.allTexts.includes(x));
    if (gonePC.length)
      bad.push(`[实质] ${key}：PC 有而移动端**整个页面都没有**，且未登记理由 → ${JSON.stringify(gonePC.slice(0, 6))}`);
    if (goneMO.length)
      bad.push(`[实质] ${key}：移动端有而 PC **整个页面都没有**，且未登记理由 → ${JSON.stringify(goneMO.slice(0, 6))}`);
    if (movedPC.length)
      info.push(`${key}：这些在移动端从内容区挪到了外壳（合规形态差异）→ ${JSON.stringify(movedPC.slice(0, 4))}`);
    // ⭐ 锚点两端不同**不总是缺陷**：功能本就仅在某一端提供时
    //   （如「只用键盘完成新建」这条 AC 在移动端不成立），差异是正确的。
    //   但它必须被登记 —— 未登记的差异与「忘了」长得一模一样。
    if (p.scene && m.scene && p.fr !== m.fr && !anchorsMayDiffer)
      bad.push(`[实质] ${key}：两端需求锚点不同（PC=${p.fr} / 移动=${m.fr}）——` +
               '若是刻意的端差异，在 --declared 里给这条路由写 {"anchors":true} 并说明理由');
  }
  // ⚠️ pairs 的元素是 [pc, mobile] 二元组，不是 {p, m} —— 首版写成 `x.p.route`
  //    ⇒ 全部路由都变成 undefined ⇒ **每条用例都返 2**。接线时要照着数据的真实形状写。
  checkFullySilenced(pairs.map(([pp]) => pp.route), opts.declared || {}, bad, info);
  return { bad, info };
}

function report(res, n, asJson) {
  // ⭐ 同上：只说「对不上」会让人去改判据；说清后果才会让人去看两端。
  if (!asJson && res && res.bad && res.bad.length)
    console.log('⚠️ 两端对不上意味着**其中一端的用户会拿到一个不完整的产品** —— '
      + '形式该不同（导航/返回/触摸目标），实质不许不同（字段/文案/可达状态）；'
      + '实质少了一块，那一端的人根本不知道自己少了什么。');
  if (res.bad[0] === 'UNABLE') { console.error('UNABLE: ' + res.info[0]); return 2; }
  if (asJson) { console.log(JSON.stringify(res, null, 1)); return res.bad.length ? 1 : 0; }
  console.log(`端形态对账：比了 ${n} 组同路由的两端渲染`);
  for (const b of res.bad) console.log('❌ ' + b);
  for (const i of res.info) console.log('ℹ️ ' + i);
  console.log(res.bad.length ? `\n❌ ${res.bad.length} 项对不上`
    : '\n✅ 形式确有分叉，实质两端一致');
  console.log('⚠️ 绿只说明「不是同一张稿拉宽拉窄」且「两端讲的不是两件事」——\n' +
    '   像不像那一端的原生应用，仍要人打开真实应用对着看（规格第四节铁律）。');
  return res.bad.length ? 1 : 0;
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
  const { mkdtempSync, writeFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  const { tmpdir } = await import('node:os');
  const d = mkdtempSync(join(tmpdir(), 'pp-'));
  const w = (n, s) => { const p = join(d, n); writeFileSync(p, s); return p; };

  // 端形态做对了的最小页：结构按端分叉 + safe-area + hover 护栏 + 44px
  const OK = `<style>
  body{margin:0;font:14px system-ui}
  .btn{min-height:44px;min-width:44px;display:inline-flex;align-items:center}
  @media (hover: hover){ .btn:hover{opacity:.9} }
  @media (pointer: coarse){ .btn{min-height:44px} }
  body[data-end="mobile"] #side{display:none}
  body[data-end="mobile"] #tabbar{display:flex;padding-bottom:env(safe-area-inset-bottom)}
  body[data-end="mobile"] #appbar{display:block}
  body[data-end="pc"] #tabbar{display:none}
  body[data-end="pc"] #appbar{display:none}
  body[data-end="pc"] #side{display:block}
  </style>
  <body><nav id="side">侧栏</nav><header id="appbar">标题栏</header>
  <main><p>任务名称</p><button class="btn">保存</button></main>
  <nav id="tabbar"><button class="btn">首页</button></nav>
  <script>
  function render(){var q=new URLSearchParams(location.hash.split('?')[1]||'');
    var e=q.get('end')||'pc';document.body.setAttribute('data-end',e);
    document.body.setAttribute('data-scene','f01-'+e+'-success');
    document.body.setAttribute('data-fr','FR-011');}
  addEventListener('hashchange',render);render();
  </script></body>`;
  // 反例①：两端结构完全一样（只是宽度不同）
  const SAME = OK.replace(/body\[data-end="mobile"\] #side\{display:none\}/, '')
                 .replace(/body\[data-end="pc"\] #tabbar\{display:none\}/, '')
                 .replace(/body\[data-end="pc"\] #appbar\{display:none\}/, '');
  // 反例②：没有 safe-area
  const NOSAFE = OK.replace('padding-bottom:env(safe-area-inset-bottom)', 'padding-bottom:8px');
  // 反例③：移动端命中区不足
  const SMALL = OK.replace('.btn{min-height:44px;min-width:44px', '.btn{min-height:28px;min-width:28px');
  // 反例④：PC 多一个字段而移动端没有，且没登记
  const EXTRA = OK.replace('<p>任务名称</p>',
    '<p>任务名称</p><p id="only">负责人</p><style>body[data-end="mobile"] #only{display:none}</style>');

  // 反例⑤：移动端多一个内容字段而 PC 没有 —— 与反例④同等，方向相反。
  //   第一版只查了 PC→移动 一个方向，移动端独有的一律放行（无理由的单边豁免）。
  const EXTRA_M = OK.replace('<p>任务名称</p>',
    '<p>任务名称</p><p id="onlym">同步状态</p><style>body[data-end="pc"] #onlym{display:none}</style>');

  // ⚠️⚠️ 2026-09-05 变异扫描实测：下面四条判据**没有任何反例守着** ——
  //    整条删掉，自证照样全绿。真因是反例①（两端结构完全相同）**同时触发了
  //    相似度 / 分叉数 / safe-area 三条**，彼此遮蔽；而 hover 护栏与需求锚点
  //    **连一条反例都没有**。⇒ 每条各补一个「其余全对、只违反这一条」的反例。

  // 反例⑦：只拆掉 hover 护栏（分叉数、safe-area、44px 全部保留）
  const NOHOVER = OK.replace('@media (hover: hover){ .btn:hover{opacity:.9} }',
                             '.btn:hover{opacity:.9}');
  // 反例⑧：分叉规则**只留一条**，但两端结构仍明显不同（隔离「分叉太少」这一条）
  //   —— 用 hidden 属性造出结构差异，绕开 CSS 分叉计数。
  const FEWFORK = OK.replace('body[data-end="mobile"] #tabbar{display:flex;padding-bottom:env(safe-area-inset-bottom)}\n  body[data-end="mobile"] #appbar{display:block}\n  body[data-end="pc"] #tabbar{display:none}\n  body[data-end="pc"] #appbar{display:none}\n  body[data-end="pc"] #side{display:block}',
                             'body[data-end="mobile"] #tabbar{padding-bottom:env(safe-area-inset-bottom)}')
                   .replace("document.body.setAttribute('data-end',e);",
                            "document.body.setAttribute('data-end',e);" +
                            "document.getElementById('side').hidden=(e!=='pc');" +
                            "document.getElementById('tabbar').hidden=(e==='pc');" +
                            "document.getElementById('appbar').hidden=(e==='pc');");
  // 反例⑩：两端结构**只差一点点** —— 指纹不完全相同（绕开「完全相同」那条），
  //   但 Jaccard 相似度仍 > 0.9（阈值），用来隔离「相似度太高」这一条。
  //   ⚠️ 此前 SAME 让两端指纹**完全相同**，于是「完全相同」先红，
  //      「相似度超阈值」这条**永远轮不到** —— 一条永远轮不到的判据等于不存在。
  //   ⭐ 指纹是**标签名集合**，所以要让相似度高又不相等，得让两端只差**一种标签**。
  //   ⭐ 指纹 = **标签名有序串**，相似度 = **标签名集合**的 Jaccard。
  //      所以要「不相等但极相似」，就得让两端**标签集合完全相同、只有顺序不同**：
  //      去掉 appbar（唯一的 <header>），只留 side / tabbar 两个 <nav> 互斥显示 ——
  //      PC 是 nav>main>…，移动是 main>…>nav，串不同而集合相同 ⇒ Jaccard = 1.0。
  //      ⚠️ 第一版我加了个 <button> 又让 tabbar 两端都显示，
  //      集合仍差一个 <header> ⇒ 相似度 0.8，够不到 0.9 阈值，反例根本没红。
  const NEARSAME = OK.replace('<header id="appbar">标题栏</header>', '')
                     .replace('body[data-end="mobile"] #appbar{display:block}', '')
                     .replace('body[data-end="pc"] #appbar{display:none}', '');
  // 反例⑨：两端 data-fr 不同且未登记（隔离「需求锚点不同」这一条）
  const FRDIFF = OK.replace("document.body.setAttribute('data-fr','FR-011');",
                            "document.body.setAttribute('data-fr', e==='pc' ? 'FR-011' : 'FR-999');");

  // ⭐ 2026-09-05：空页面此前报 FAIL「两端结构指纹完全相同」——
  //    那等于说「你没做端形态」，而真相是没得判。传错文件的人会被送去修不存在的问题。
  const EMPTY = '<body><main id="app"></main></body>';
  const cases = [
    ['正例 端形态确有分叉且实质一致', OK, 0],
    ['边界 内容区全空 → 报 2（没得判），不许报 1（说人家没做端形态）', EMPTY, 2],
    ['反例⑤ 移动端多出字段且未登记（与④方向相反，同样是缺口）', EXTRA_M, 1],
    ['反例① 两端结构完全相同（同一张稿拉宽拉窄）', SAME, 1],
    ['反例② 移动端没有 safe-area', NOSAFE, 1],
    ['反例③ 移动端命中区 < 44px', SMALL, 1],
    ['反例⑦ 只拆掉 hover 护栏（此前这条零反例）', NOHOVER, 1],
    ['反例⑧ 分叉规则只剩一条但结构仍不同（隔离「分叉太少」）', FEWFORK, 1],
    ['反例⑨ 两端需求锚点不同且未登记（此前这条零反例）', FRDIFF, 1],
    ['反例⑩ 指纹不相等但相似度超阈值（隔离「相似度太高」）', NEARSAME, 1],
    ['反例④ PC 多出字段且未登记（三种可能长得一模一样）', EXTRA, 1],
  ];
  let ok = true;
  console.log('M8 自证 —— 正例绿 / 四类反例各自必红\n');
  for (const [name, html, want] of cases) {
    const f = w(name.slice(0, 6).replace(/\W/g, '') + '.html', html);
    let got;
    try { got = await run(f, ['#/'], { fpMax: 0.9, minForks: 3, declared: {} }, true); }
    catch (e) { got = 2; }
    const g = got === want;
    ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${name.padEnd(38)} 期望 ${want} 实得 ${got}`);
  }
  // 正例②：同一份反例④，把差异**显式登记**后必须放行 ——
  //   ⭐ 这条证明「登记」这个出口真的存在。若没有它，作者面对合理的信息分层
  //     只能靠关掉门禁绕过去，那这道门迟早会被整条注释掉。
  {
    const f = w('declared.html', EXTRA);
    let got;
    try {
      got = await run(f, ['#/'], { fpMax: 0.9, minForks: 3,
        declared: { '#/': { texts: ['负责人'], reason: '移动端不展示负责人：列表页信息分层，详情页可见' } } }, true);
    } catch (e) { got = 2; }
    const g = got === 0;
    ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'正例② 差异登记后放行（登记出口必须真的存在）'.padEnd(38)} 期望 0 实得 ${got}`);
  }
  // 🚨 反例⑥：登记了但没写理由 —— 必须红。
  //   若这条不红，`--declared` 就退化成「把门关掉」的开关。
  {
    const f = w('noreason.html', EXTRA);
    let got;
    try {
      got = await run(f, ['#/'], { fpMax: 0.9, minForks: 3,
        declared: { '#/': ['负责人'] } }, true);      // 数组形态＝没有 reason
    } catch (e) { got = 2; }
    const g = got === 1;
    ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'反例⑥ 登记了却不写理由（静音开关必须红）'.padEnd(38)} 期望 1 实得 ${got}`);
  }
  // 🆕 2026-09-05 `--unable` 实测：`report()` 里「内容区全空 ⇒ 报 2」那一行从没执行过 ——
  //    自证全部走 `run(..., quiet=true)`，而 quiet 分支**在到达 report() 之前就短路返回了**。
  //    ⭐ 也就是说**整个报告层从没被自证覆盖过**：report() 里的错，自证一个都看不见。
  // 🆕 2026-09-06 豁免出口的两条上限（形状由并行会话 fm-agent 提出：
  //    「**能让它闭嘴，但不能悄悄让它闭嘴**」）
  {
    const f2 = w('ph.html', EXTRA);
    let got = 1;
    try {
      got = await run(f2, ['#/'], { fpMax: 0.9, minForks: 3,
        declared: { '#/': { texts: ['负责人'], reason: 'TODO' } } }, true);
    } catch { got = 9; }
    const g = got === 1; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'反例⑪ reason 是占位符「TODO」⇒ 不算登记'.padEnd(38)} 期望 1 实得 ${got}`);
  }
  {
    // 两条路由**都**登记 ⇒ 实质对账被整体静音
    const f3 = w('sil.html', EXTRA);
    let got = 0;
    try {
      got = await run(f3, ['#/', '#/b'], { fpMax: 0.9, minForks: 3,
        declared: { '#/': { texts: ['负责人'], reason: '桌面独有的批量操作面板' },
                    '#/b': { texts: [], reason: '同上' } } }, true);
    } catch { got = 9; }
    const g = got === 1; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'反例⑫ 每条路由都登记 ⇒ 整体静音必须红'.padEnd(38)} 期望 1 实得 ${got}`);
  }
  {
    // ⑬ 全登记 + 显式定位声明（reason+规格锚）⇒ 大声放行
    const f3 = w('sil2.html', EXTRA);
    let got = 9;
    try {
      got = await run(f3, ['#/', '#/b'], { fpMax: 0.9, minForks: 3,
        declared: { _full_coverage_reason: '移动端定位为遥控器，每屏刻意降级',
                    _full_coverage_anchor: '5.3 非目标：不追求移动端功能完整（定位为遥控器）',
                    '#/': { texts: ['负责人'], reason: '桌面独有的批量操作面板' },
                    '#/b': { texts: ['负责人'], reason: '同上（两条路由共用该面板）' } } }, true);
    } catch { got = 9; }
    const g = got === 0; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'正例⑬ 全登记+显式定位声明(带规格锚) ⇒ 放行'.padEnd(38)} 期望 0 实得 ${got}`);
  }
  {
    // ⑭ 声明字段在而规格锚太短 ⇒ 不算声明，照红
    const f3 = w('sil3.html', EXTRA);
    let got = 9;
    try {
      got = await run(f3, ['#/', '#/b'], { fpMax: 0.9, minForks: 3,
        declared: { _full_coverage_reason: '移动端定位为遥控器，每屏刻意降级',
                    _full_coverage_anchor: '5.3',
                    '#/': { texts: ['负责人'], reason: '桌面独有的批量操作面板' },
                    '#/b': { texts: ['负责人'], reason: '同上（两条路由共用该面板）' } } }, true);
    } catch { got = 9; }
    const g = got === 1; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'反例⑭ 定位声明缺规格锚 ⇒ 照红'.padEnd(38)} 期望 1 实得 ${got}`);
  }
  {
    const { execFileSync } = await import('node:child_process');
    const f = w('cli_empty.html', EMPTY);
    let sub = 0;
    try {
      execFileSync(process.execPath, [resolve(process.argv[1]), f, '--routes', '#/'],
                   { stdio: 'pipe' });
    } catch (e) { sub = e.status; }
    const g = sub === 2; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'命令行跑：内容区全空 → 退出码 2'.padEnd(38)} 期望 2 实得 ${sub}`);
  }
  {
    // 🚨 正例：**一端整页没渲染出来 ⇒ 必须报「没量到」(2)，不许报成端形态缺陷(1)**。
    //   移动视口(390)下整页 display:none，PC(1440) 正常。
    //   ⛔ 这条要是判成 1，门禁就会把「加载超时」写成「移动端把内容弄丢了」，
    //   把人送去修一个不存在的问题。
    const f = w('blank_mobile.html',
      OK + '<style>@media (max-width:500px){html,body{display:none}}</style>');
    let got;
    try { got = await run(f, ['#/'], { fpMax: 0.9, minForks: 3, declared: {} }, true); }
    catch { got = 9; }
    const g = got === 2; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'正例 一端整页没渲染 → 没量到(2) 不是缺陷(1)'.padEnd(38)} 期望 2 实得 ${got}`);
  }
  {
    // 🚨 反例：**外壳还在、只有内容区空了 ⇒ 必须照常红(1)，守卫不许把它一起吃掉**。
    //   上一条让「整页没渲染」变成 2；这条守住它**不过界** ——
    //   ⭐ 判据最爱长成「我发现问题时那个场景」的形状，旁边结构相同的场景就看不见了。
    //   这里两条一起才说明白：allTexts 空 = 没量到；texts 空而 allTexts 有 = 真发现。
    const f = w('shell_only.html',
      OK + '<style>body[data-end="mobile"] main{display:none}</style>');
    let got;
    try { got = await run(f, ['#/'], { fpMax: 0.9, minForks: 3, declared: {} }, true); }
    catch { got = 9; }
    const g = got === 1; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'反例 外壳在但内容区空 → 照常红(1) 不许当没量到'.padEnd(38)} 期望 1 实得 ${got}`);
  }
  {
    // 🚨🚨 **外链 CSS**：此前所有夹具都是内联 `<style>`，
    //   于是「link 一张不看」这个缺陷在自证里**永远不会出现**。
    //   2026-09-06 实测：本仓自己的 templates/proto 因此被报 3 条假阳性。
    //   ⭐ 判据只盖住了我造的那一半世界 —— 补上另一半。
    const cssBody = OK.slice(OK.indexOf('<style>') + 7, OK.indexOf('</style>'));
    writeFileSync(join(d, 'ext.css'), cssBody);
    const f = w('ext.html',
      '<link rel="stylesheet" href="ext.css">' + OK.slice(OK.indexOf('</style>') + 8));
    let got;
    try { got = await run(f, ['#/'], { fpMax: 0.9, minForks: 3, declared: {} }, true); }
    catch { got = 9; }
    const g = got === 0; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'正例 CSS 在外链文件里也要读到（不是内联才算）'.padEnd(38)} 期望 0 实得 ${got}`);
  }
  {
    // 🚨 读不到的样式表（远程 CDN）⇒ **没量到(2)**，不许当成「没有 safe-area」报红(1)。
    const f = w('remote.html',
      '<link rel="stylesheet" href="https://example.invalid/x.css">' +
      OK.slice(OK.indexOf('</style>') + 8));
    let got;
    try { got = await run(f, ['#/'], { fpMax: 0.9, minForks: 3, declared: {} }, true); }
    catch { got = 9; }
    const g = got === 2; ok = ok && g;
    console.log(`  ${g ? '✅' : '❌'} ${'反例 样式表读不到 → 没量到(2) 不是缺陷(1)'.padEnd(38)} 期望 2 实得 ${got}`);
  }
  console.log(`\n${ok ? '✅ 自证通过：这道门会出声' : '❌ 自证失败：先修门禁'}`);
  process.exit(ok ? 0 : 1);
}

async function run(demo, base, opts, quiet) {
  const probe = PROBE.replace('__ROUTES__', JSON.stringify(routesFor('pc', base)));
  const probeM = PROBE.replace('__ROUTES__', JSON.stringify(routesFor('mobile', base)));
  const [pc] = await evalInPage(demo, '1440x900', [probe]);
  const [mo, rawFeat] = await evalInPage(demo, '390x844', [probeM, FEATURES]);
  const feat = featuresFrom(rawFeat, demo);   // 外链 CSS 由 Node 侧按磁盘读
  const res = judge(pc, mo, feat, opts);
  if (quiet) return res.bad[0] === 'UNABLE' ? 2 : (res.bad.length ? 1 : 0);
  return report(res, pc.length, opts.json);
}

const argv = process.argv.slice(2);
if (argv.includes('--self-test')) { await selfTest(); }
else {
  rejectUnknown(argv, ['--routes', '--declared', '--fp-max', '--min-forks', '--json', '--self-test'],
    '用法: platform-parity-gate.mjs <demo.html> [--routes "#/a,#/b"] [--declared f.json] [--fp-max 0.9] [--min-forks 8] [--json]');
  const files = argv.filter((a, i) => !a.startsWith('--') &&
    !['--routes', '--declared', '--fp-max', '--min-forks'].includes(argv[i - 1]));
  if (!files.length) { console.error('UNABLE: 没给 demo'); process.exit(2); }
  const demo = resolve(files[0]);
  if (!existsSync(demo)) { console.error('UNABLE: demo 不存在 ' + demo); process.exit(2); }
  const ri = argv.indexOf('--routes');
  const base = ri >= 0 ? argv[ri + 1].split(',').map(s => s.trim()).filter(Boolean) : ['#/'];
  const di = argv.indexOf('--declared');
  let declared = {};
  if (di >= 0) {
    if (!existsSync(argv[di + 1])) { console.error('UNABLE: --declared 文件不存在'); process.exit(2); }
    declared = JSON.parse(readFileSync(argv[di + 1], 'utf8'));
  }
  const fi = argv.indexOf('--fp-max'), mi = argv.indexOf('--min-forks');
  // ── 两个默认阈值的出处（⛔ 不许只留一个数字：没有出处的阈值长着权威的样子却是编的）──
  //  · `minForks: 8` —— **实证**：移动端框架 67/68 个组件都按平台分叉
  //    （见 references/platform-parity.md）。8 是「一份真做了端形态的稿子」的下限，
  //    不是上限；桌面工具箱 15 个组件 vs 移动端 97 个、只重合 6 个，也是同一份实证。
  //  · `fpMax: 0.9` —— ⚠️ **这是判断，不是实证**，如实说明：
  //    指纹是**标签名集合**，两端共用 >90% 的标签种类，意味着差异只剩外壳那一两个节点。
  //    没有外部数据支持 0.9 这个具体数；它可调（`--fp-max`），
  //    调它的人应该知道自己在调一个**约定**而不是一条实证结论。
  const opts = {
    fpMax: fi >= 0 ? Number(argv[fi + 1]) : 0.9,
    minForks: mi >= 0 ? Number(argv[mi + 1]) : 8,
    declared, json: argv.includes('--json'),
  };
  try { process.exit(await run(demo, base, opts, false)); }
  catch (e) { console.error('UNABLE: ' + e.message); process.exit(2); }
}
