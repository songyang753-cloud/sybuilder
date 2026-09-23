// ── ③ 状态层 · URL 即状态（约 45 行）──────────────────────────────────────
// 借自 TanStack Router：**筛选 / 选中 / 分页 / 场景都进 URL**，于是
//   · 每一屏都能深链、能刷新、能前进后退
//   · 场景锚点从路由「长出来」，不再手贴 data-scene（G2/G3 的输入照旧成立）
// ⛔ 导航必须能被 ⌘/中键点开 → 视图层用 <a href="#/..."> 而不是 <div onclick>
(function (P) {
  'use strict';

  // ends 与 spec/states.json 的三选一保持一致：
  //   same → ['pc','mobile'] · degraded → ['pc','mobile'] · pc-only → ['pc']
  var ROUTES = [
    { id: 'f01', path: 'inbox',  title: '任务列表', ends: ['pc', 'mobile'] },
    { id: 'f02', path: 'task',   title: '任务详情', ends: ['pc', 'mobile'] },   // #/task/T-1000
    { id: 'f03', path: 'create', title: '新建任务', ends: ['pc'] }              // pc-only
  ];

  function parse() {
    var raw = location.hash.replace(/^#\/?/, '') || 'inbox';
    var qi = raw.indexOf('?');
    var qs = qi > -1 ? raw.slice(qi + 1) : '';
    var segs = (qi > -1 ? raw.slice(0, qi) : raw).split('/').filter(Boolean);
    var q = {};
    qs.split('&').filter(Boolean).forEach(function (kv) {
      var i = kv.indexOf('='); q[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
    });
    var def = ROUTES.filter(function (r) { return r.path === segs[0]; })[0] || ROUTES[0];
    return { id: def.id, path: def.path, title: def.title, param: segs[1] || null, query: q };
  }

  function go(path, query) {
    var qs = Object.keys(query || {}).filter(function (k) { return query[k] !== '' && query[k] != null; })
      .map(function (k) { return k + '=' + encodeURIComponent(query[k]); }).join('&');
    location.hash = '/' + path + (qs ? '?' + qs : '');
  }

  P.router = { ROUTES: ROUTES, parse: parse, go: go };

  // ⭐ 门禁的输入：路由 × 场景的全展开。
  //   `dead-click-gate.mjs` 与 `browser-audit.mjs --all-routes` 都读它。
  //   ⛔ 别手写这张表 —— 手写的表会漏掉后加的场景，而漏掉的那个正是没人验过的那个。
  P.buildRouteMatrix = function () {
    var out = [];
    ROUTES.forEach(function (r) {
      (r.ends || ['pc']).forEach(function (end) {
        Object.keys(P.scenarios || {}).forEach(function (scn) {
          var p = r.path === 'task' ? 'task/T-1000' : r.path;
          out.push('#/' + p + '?scn=' + scn + (end === 'pc' ? '' : '&end=' + end));
        });
      });
    });
    return out;
  };

  /** 当前主题：URL 里的 ?theme= 优先，否则跟随系统 */
  P.currentTheme = function () {
    var m = /[?&]theme=(light|dark)/.exec(location.hash + location.search);
    if (m) return m[1];
    return (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  };

  /** 当前端：URL 里的 ?end= 优先，否则按视口宽度兜底 */
  P.currentEnd = function () {
    var m = /[?&]end=(pc|mobile)/.exec(location.hash + location.search);
    if (m) return m[1];
    return window.innerWidth <= 560 ? 'mobile' : 'pc';
  };
})(window.PROTO = window.PROTO || {});
