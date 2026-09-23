// ============================================================================
// 两道行为门禁共用的**页面内**工具源码（以字符串形式注入页面求值）。
//
// 为什么单独一份：`flow-walk-gate` 与 `scenario-matrix-gate` 都要
// 「按 role + 可访问名称找元素」和「等异步落定」。各写一份的结果是
// **其中一份的 role 表会先过期**，而过期只会表现为「找不到元素」，
// 看起来像 demo 的问题，不像门禁的问题。
// ============================================================================

/** 注入页面的公共前缀：sleep / settle / accName / byRole。 */
export const HELPERS = `
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const settle = async (max) => { const t0 = Date.now();
    while (document.body.hasAttribute('data-busy') && Date.now() - t0 < max) await sleep(50);
    await sleep(80); };
  const ROLE_SEL = {
    button:    'button,[role="button"],input[type="submit"],input[type="button"]',
    link:      'a[href],[role="link"]',
    textbox:   'input[type="text"],input:not([type]),textarea,[role="textbox"]',
    searchbox: 'input[type="search"],[role="searchbox"]',
    heading:   'h1,h2,h3,h4,h5,h6,[role="heading"]',
    checkbox:  'input[type="checkbox"],[role="checkbox"]',
    alert:     '[role="alert"]',
    status:    '[role="status"],[aria-live]',
    // 🔴 2026-09-04 补：input[type=number]（spinbutton）与 select（combobox）
    //    是最常见的两种表单控件，此前**都没有 role** —— 写不了针对它们的断言。
    //    ⚠️ 本块整个在**模板字符串**里，注释里**一个反引号都不能有**，
    //       否则会当场截断 HELPERS，报成不知所云的 SyntaxError（我刚踩过）。
    //    ⭐ 后果不是报错，是**作者绕过去**：改用 textbox（定位不到）或干脆不写这条断言，
    //      于是「阈值可配置」这类 AC 永远只停留在文字描述上。
    spinbutton: 'input[type="number"],[role="spinbutton"]',
    combobox:   'select,[role="combobox"]',
    radio:      'input[type="radio"],[role="radio"]',
    slider:     'input[type="range"],[role="slider"]',
    switch:     '[role="switch"]'
  };
  function accName(el) {
    const al = el.getAttribute('aria-label');
    if (al) return al.trim();
    const lb = el.getAttribute('aria-labelledby');
    if (lb) { const n = document.getElementById(lb); if (n) return (n.textContent || '').trim(); }
    if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                 if (l) return (l.textContent || '').trim(); }
    const wrap = el.closest && el.closest('label');
    if (wrap) return (wrap.textContent || '').trim();
    const t = (el.textContent || '').trim();
    if (t) return t.replace(/\\s+/g, ' ');
    return (el.getAttribute('title') || el.getAttribute('placeholder') || el.value || '').trim();
  }
  const visible = el => {
    // 折叠的 <details> 内容在 Chrome 152 仍有非零尺寸 —— 用 checkVisibility 才判得准
    if (el.checkVisibility && !el.checkVisibility({ contentVisibilityAuto: true,
        opacityProperty: true, visibilityProperty: true })) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  function byRole(role, name, prefix) {
    const sel = ROLE_SEL[role];
    if (!sel) return { err: '不认识的 role：' + role };
    const all = [...document.querySelectorAll(sel)].filter(visible);
    const hit = all.filter(el => {
      const n = accName(el);
      return prefix ? n.indexOf(prefix) === 0 : n === name;
    });
    if (!hit.length) return { err: 'role=' + role + ' 名称=' + (name || prefix + '…') +
      ' 找不到。当前该 role 下可见的名称：' + JSON.stringify(all.slice(0, 8).map(accName)) };
    return { el: hit[0], count: hit.length };
  }
  /** 执行一步（fill / click / clickFirst）。expect 由各门禁自己判。 */
  async function doStep(s) {
    const f = byRole(s.role, s.name, s.namePrefix);
    if (f.err) throw new Error(f.err);
    if (s.do === 'fill') {
      const el = f.el;
      const setter = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value');
      setter && setter.set ? setter.set.call(el, s.value) : (el.value = s.value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      await sleep(40);
    } else {
      f.el.click();
      await sleep(60); await settle(8000);
    }
  }
`;

// ---------------------------------------------------------------- 自证（M8）
// ⭐ 2026-09-04 补。本模块此前**零测试**，而它是四道浏览器门禁的定位基础：
//    `byRole` / `accName` 一旦搞错优先级，门禁会**静默定位到另一个元素**并照常报绿。
//    最危险的具体形态：一个 `aria-label="删除全部"` 而正文写着「删除」的按钮 ——
//    若 accName 先取 textContent，`byRole('button','删除')` 就会命中它，
//    于是「点了删除这一项」的用例实际点了「删除全部」，**而没有任何东西会报错**。
if (process.argv[1] && process.argv[1].endsWith('_page-helpers.mjs')) {
  const { evalInPage } = await import('./_browser.mjs');
  const { writeFileSync, mkdtempSync } = await import('node:fs');
  const { join } = await import('node:path');
  const { tmpdir } = await import('node:os');

  const FIXTURE = `<!doctype html><meta charset="utf-8"><body>
    <button aria-label="删除全部">删除</button>
    <button>删除这一项</button>
    <span id="lb">来自 labelledby</span><button aria-labelledby="lb">别用我的正文</button>
    <label for="i1">用户名</label><input id="i1" type="text">
    <label>包着的标签<input id="i2" type="text"></label>
    <input id="i3" type="text" placeholder="占位符兜底">
    <button style="display:none">看不见的按钮</button>
    <button title="标题兜底"></button>
    <a href="#x">一个链接</a>
    <label for="n1">熔断次数</label><input id="n1" type="number" value="3">
    <label for="s1">主题</label><select id="s1"><option>浅色</option></select>
    <label for="r1">每次询问</label><input id="r1" type="radio" name="g">
    <label for="g1">音量</label><input id="g1" type="range" min="0" max="10">
  </body>`;
  const dir = mkdtempSync(join(tmpdir(), 'ph-'));
  const f = join(dir, 'fx.html');
  writeFileSync(f, FIXTURE);

  const PROBE = `(() => {
${HELPERS}
  const R = {};
  const nm = (sel) => accName(document.querySelector(sel));
  R.ariaLabelWins   = nm('button[aria-label]');
  R.labelledbyWins  = nm('button[aria-labelledby]');
  R.labelForWins    = nm('#i1');
  R.wrappingLabel   = nm('#i2');
  R.placeholderLast = nm('#i3');
  R.titleFallback   = nm('button[title]');
  R.exactMatch      = (() => { const r = byRole('button', '删除这一项');
                               return r.el ? accName(r.el) : r.err; })();
  R.aliasNotStolen  = (() => { const r = byRole('button', '删除');
                               return r.el ? accName(r.el) : 'NOTFOUND'; })();
  R.prefix          = (() => { const r = byRole('button', null, '删除这');
                               return r.el ? accName(r.el) : r.err; })();
  // 🔴 表单控件的四个 role 此前一个都没有 —— 写不了断言，作者只能绕过去
  R.spin  = (() => { const r = byRole('spinbutton', '熔断次数'); return r.el ? r.el.id : r.err; })();
  R.combo = (() => { const r = byRole('combobox', '主题');     return r.el ? r.el.id : r.err; })();
  R.radio = (() => { const r = byRole('radio', '每次询问');     return r.el ? r.el.id : r.err; })();
  R.slide = (() => { const r = byRole('slider', '音量');       return r.el ? r.el.id : r.err; })();
  R.invisibleSkipped = !JSON.stringify(byRole('button', '看不见的按钮')).includes('"el"');
  R.unknownRole     = !!byRole('nosuchrole', 'x').err;
  R.linkRole        = (() => { const r = byRole('link', '一个链接');
                               return r.el ? 'ok' : r.err; })();
  return R;
})()`;

  let ok = true;
  const chk = (n, c) => { console.log((c ? '  ✓ ' : '  ✗ ') + n); ok = ok && c; };
  const [R] = await evalInPage(f, '1200x800', [PROBE]);

  chk('aria-label 优先于正文（否则会定位到「删除全部」）', R.ariaLabelWins === '删除全部');
  chk('spinbutton 认得 input[type=number]（阈值这类 AC 靠它才验得了）', R.spin === 'n1');
  chk('combobox 认得 <select>', R.combo === 's1');
  chk('radio 认得 input[type=radio]', R.radio === 'r1');
  chk('slider 认得 input[type=range]', R.slide === 'g1');
  chk('aria-labelledby 优先于正文', R.labelledbyWins === '来自 labelledby');
  chk('label[for] 给输入框命名', R.labelForWins === '用户名');
  chk('被 <label> 包裹的输入框取包裹文字', R.wrappingLabel === '包着的标签');
  chk('都没有时才退到 placeholder', R.placeholderLast === '占位符兜底');
  chk('空按钮退到 title', R.titleFallback === '标题兜底');
  chk('byRole 精确匹配命中正确的那个', R.exactMatch === '删除这一项');
  // ⭐ 这条是本自证的核心反例：aria-label 已把那个按钮改名为「删除全部」，
  //    所以按「删除」找**应当找不到** —— 找得到就说明 accName 的优先级反了。
  chk('⛔ 按「删除」找不到（aria-label 已改名，找到就是优先级反了）', R.aliasNotStolen === 'NOTFOUND');
  chk('前缀匹配可用', R.prefix === '删除这一项');
  chk('不可见元素被排除', R.invisibleSkipped === true);
  chk('不认识的 role 返回 err 而不是空结果', R.unknownRole === true);
  chk('link role 可用', R.linkRole === 'ok');
  console.log('\n' + (ok ? '✅ 自证通过：定位基础可信' : '❌ 自证失败：门禁的元素定位不可信'));
  process.exit(ok ? 0 : 1);
}
