// ── 端外壳：PC 与移动端是**两种形式**，不是同一套布局换个宽度 ──────────────
// ⛔ 「两端同一套交互」（endMode: same）说的是**交互**同一套，
//   不是**形式**同一套：桌面是侧栏 + 主区的常驻导航，
//   移动端是全屏单列 + 顶部返回 —— 信息架构本来就不同。
//   📌 此前这里只有一套居中单列，「移动端」只是 URL 上的一个参数 ——
//      锚点、门禁、降级都真了，唯独**形式**是假的。
(function (P) {
  'use strict';

  var NAV = [
    { path: 'inbox',  key: 'listTitle' },
    { path: 'create', key: 'createTitle' }
  ];

  /** 桌面端：常驻侧栏导航（移动端不出现，由顶部返回承担） */
  function renderSideNav(end, route) {
    var el = document.getElementById('sidenav');
    if (end !== 'pc') { el.innerHTML = ''; el.hidden = true; return; }
    el.hidden = false;
    // ⛔ 品牌位不要复用页面标题 —— 截图里「任务列表」在侧栏品牌、侧栏导航、
    //   主区 h1 上出现了三次，读起来像没做完。
    el.innerHTML = '<p class="brand">' + P.esc(P.copy.appName) + '</p>' +
      NAV.map(function (n) {
        var on = route && route.path === n.path;
        return '<a href="#/' + n.path + P.scnQs() + '"' + (on ? ' aria-current="page"' : '') + '>' +
          P.esc(P.copy[n.key]) + '</a>';
      }).join('');
  }

  /** 移动端：顶部 app bar（标题 + 返回）。桌面端不需要——侧栏已经在那儿了。 */
  function renderAppBar(end, route) {
    var el = document.getElementById('appbar');
    if (end !== 'mobile' || !route) { el.innerHTML = ''; el.hidden = true; return; }
    el.hidden = false;
    var titleKey = route.path === 'inbox' ? 'listTitle' : route.path === 'task' ? 'detailTitle' : 'createTitle';
    var back = route.path === 'inbox' ? '' :
      '<a class="bar-back" data-el="btn-back" href="#/inbox' + P.scnQs() + '" aria-label="' +
      P.esc(P.copy.back) + '">‹</a>';
    el.innerHTML = back + '<h2>' + P.esc(P.copy[titleKey]) + '</h2>';
  }

  /** 移动端：底部 tab bar。
   *  ⭐ 这不是「侧栏的窄屏版」——它是移动应用的**主要**导航形态：
   *    常驻、拇指可及、切换不离开当前上下文。桌面端没有这个东西
   *    （桌面工具箱里根本没有 tab-bar 组件，见 references/platform-parity.md）。 */
  function renderTabBar(end, route) {
    var el = document.getElementById('tabbar');
    if (!el) return;
    if (end !== 'mobile') { el.innerHTML = ''; el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = NAV.map(function (n) {
      var on = route && route.path === n.path;
      return '<a href="#/' + n.path + P.scnQs() + '"' + (on ? ' aria-current="page"' : '') +
        ' data-el="tab-' + n.path + '"><span aria-hidden="true">' +
        (n.path === 'inbox' ? '☰' : '＋') + '</span>' + P.esc(P.copy[n.key]) + '</a>';
    }).join('');
  }

  /** 桌面端的双栏并置：列表与详情同屏。
   *  ⭐ 这是桌面应用最显著的形态特征，而移动端**做不到** —— 它只能 push/pop。
   *    因此这不是「宽屏下的优化」，是两端信息架构本来就不同。 */
  function applySplit(end, route) {
    var pane = document.getElementById('pane');
    if (!pane) return;
    var split = end === 'pc' && route && (route.path === 'inbox' || route.path === 'task');
    pane.setAttribute('data-split', split ? '1' : '0');
  }

  function renderThemeBar(theme) {
    ['light', 'dark'].forEach(function (x) {
      var a = document.querySelector('[data-theme-to="' + x + '"]');
      if (a) a.setAttribute('aria-current', String(x === theme));
    });
  }

  function renderEndBar(end) {
    ['pc', 'mobile'].forEach(function (e) {
      var a = document.querySelector('[data-end-to="' + e + '"]');
      if (a) a.setAttribute('aria-current', String(e === end));
    });
  }

  /** 评审用的场景导航：由**路由 × 场景矩阵**生成，不是手写清单。
   *  ⭐ 保留 demo-html 最要紧的那条价值：**对方点不出来的交互等于不存在**。
   *  ⛔ 但不再像老模型那样「把每个状态画成一屏挂进导航」——
   *     这里每一项只是一次带 `scn=` 的导航，界面自己走到那个状态。
   *     于是导航是**评审入口**，不是**画面清单**。 */
  function renderSceneNav(end, route) {
    var el = document.getElementById('scenenav');
    if (!el) return;
    // ⭐ `P.scenarios` 只在 mock 层存在。**换成真实现后它没了** ——
    //   评审外壳必须自己消失，而不是把整个 app 拖崩。
    //   🚨 2026-09-04 实测：此前 `Object.keys(P.scenarios)` 直接抛
    //   「Cannot convert undefined or null to object」，boot 整个挂掉，
    //   页面上只剩演示外壳、**产品内容一个字都不渲染** ——
    //   而 README 里写着「把 api.js 整体换成真 fetch，其余三层一行都不用改」。
    //   ⛔ 那句话是这个模型存在的理由（deviation-free），而它当时是假的。
    var SCN = P.scenarios || {};
    if (!Object.keys(SCN).length) { el.innerHTML = ''; el.hidden = true; return; }
    var cur = P.currentScenario().name;
    var visible = P.router.ROUTES.filter(function (r) {
      return (r.ends || ['pc']).indexOf(end) > -1;
    });
    // 只在另一端存在的界面不在本端的导航里凭空出现 —— 那会让评审的人以为它这端也有
    var hidden = P.router.ROUTES.length - visible.length;
    var groups = visible.map(function (r) {
      var items = Object.keys(SCN).map(function (scn) {
        var path = r.path === 'task' ? 'task/T-1000' : r.path;
        var qs = [];
        if (scn !== 'default') qs.push('scn=' + scn);
        if (end !== 'pc') qs.push('end=' + end);
        var on = route && route.path === r.path && cur === scn;
        return '<a href="#/' + path + (qs.length ? '?' + qs.join('&') : '') + '"' +
          (on ? ' aria-current="true"' : '') + '>' +
          P.esc(SCN[scn].desc) + '</a>';
      }).join('');
      return '<div class="grp">' + P.esc(r.title) + '</div>' + items;
    }).join('');
    // ⛔ 数字要诚实：这里数的是**当前端**的场景数，不是全部
    // 窄屏折叠：默认收起，点标题展开。⛔ 不是删掉它（可达性是交付质量），是别挡路。
    var narrow = window.innerWidth <= 900;
    var head = '<summary class="navtitle">场景导航<span>评审用 · ' +
      (end === 'pc' ? '桌面端' : '移动端') + ' ' +
      (visible.length * Object.keys(SCN).length) + ' 个' +
      (hidden ? '（另有 ' + hidden + ' 个界面仅在桌面端）' : '') + '</span></summary>';
    // ⚠️ 折叠内容必须包一层 div。
    //   直接把 <a> 放在 <details> 下、又给它设了 display，
    //   会**覆盖掉浏览器对折叠内容的隐藏** —— 实测 details.open=false
    //   而 21 条链接照样渲染出来，焦点环与留白两条判据同时变红。
    //   ⭐ 「收起来了」和「看起来收起来了」是两回事，只有真跑才发现。
    el.innerHTML = '<details' + (narrow ? '' : ' open') + '>' + head +
      '<div class="navbody">' + groups + '</div></details>';
  }

  P.shell = {
    render: function (end, route) {
      renderTabBar(end, route);
      applySplit(end, route);
      var theme = P.currentTheme();
      // ⚠️ 主题**不进场景 ID**：它是呈现模式，不是业务状态。
      //   把它塞进锚点会让矩阵从 23 项炸到 46 项，而多出来的一半问的是同一件事。
      //   ⭐ 但**视觉门禁必须两个主题都跑** —— 对比度是随主题变的，
      //   浅色下 4.5:1 达标不代表深色下也达标。
      document.documentElement.setAttribute('data-theme', theme);
      renderThemeBar(theme);
      document.body.setAttribute('data-end', end);
      renderSideNav(end, route);
      renderSceneNav(end, route);
      renderAppBar(end, route);
      renderEndBar(end);
    },
    /** 端切换：写进 URL（端是状态，状态就该进地址栏） */
    bindEndSwitch: function (onChange) {
      document.addEventListener('click', function (ev) {
        var a = ev.target.closest('[data-end-to],[data-theme-to]');
        if (!a) return;
        ev.preventDefault();
        var r = P.router.parse();
        var q = {};
        Object.keys(r.query).forEach(function (k) { q[k] = r.query[k]; });
        if (a.hasAttribute('data-end-to')) {
          var to = a.getAttribute('data-end-to');
          if (to === 'pc') delete q.end; else q.end = to;
        } else {
          var th = a.getAttribute('data-theme-to');
          if (th === 'light') delete q.theme; else q.theme = th;
        }
        P.router.go(r.path + (r.param ? '/' + r.param : ''), q);
        onChange();
      });
    }
  };
})(window.PROTO = window.PROTO || {});
