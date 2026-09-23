// ── ④ 视图层 ────────────────────────────────────────────────────────────
// ⛔ 三条红线：
//   1. 不许直接读 fixtures / scenarios —— 一律走 P.api（换真接口时这层不动）
//   2. 状态一律用 P.deriveDataState 推导，不许手写 if (scene === 'empty')
//   3. 文案一律取 P.copy（对应 spec/copy.json），不许在这里硬写字符串
//      —— 控件字数上限要能被机器核，硬写的文案核不了
(function (P) {
  'use strict';
  // ⭐ 箭头是**视觉装饰**，不进可访问名 —— `P.copy.back` 同时被移动端 app bar
  //   当作 aria-label 用，把「←」写进文案会让读屏念出「左箭头」。
  //   2026-09-04 实测：可访问名曾是「← 返回列表」，flow-walk 的移动端路径当场断在这里。
  var BACK_ARROW = '<span aria-hidden="true">← </span>';
  'use strict';
  var h = function (html) { var d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); };

  // 每个状态一段渲染，**共用同一个容器** —— 这就是「不另画一屏」的落点
  function dataState(st, opt) {
    // ⛔ 'default'（还没发起过请求）必须也有渲染分支。
    //   漏掉它的后果不是「少一个状态」，是 items 为 null 时直接抛异常、整页空白 ——
    //   而**页面空白时死按钮门反而是绿的**（没有元素就没有死元素）。
    //   这个 bug 是本骨架自己撞出来的，也正是「控制台报错」必须进门禁的理由。
    if (st === 'loading' || st === 'default')
      return '<div class="skel" role="status" aria-live="polite">' + esc(P.copy.loading) + '</div>';
    if (st === 'empty') return '<div class="state"><p>' + esc(P.copy.emptyTitle) + '</p>' +
      '<p class="muted">' + esc(P.copy.emptyHint) + '</p>' +
      '<a class="btn primary" data-el="btn-create" href="#/create' + opt.scnQs + '">' + esc(P.copy.createCta) + '</a></div>';
    if (st === 'no-permission') return '<div class="state err"><p>' + esc(P.copy.noPermTitle) + '</p>' +
      '<p class="muted">' + esc(P.copy.noPermHint) + '</p></div>';
    // ⛔ 不要拿接口的原始错误文案**顶掉**界面自己的标题。
    //   「服务暂时不可用」是服务端在说话；用户要先知道**是什么没成功**，再看细节。
    //   📌 这条是 flow-walk-gate 走 FLOW-05 时揪出来的：
    //      spec 里写着应出现「没能加载任务列表」，界面上只有接口那句话。
    if (st === 'error') return '<div class="state err" role="alert"><p>' + esc(P.copy.errTitle) + '</p>' +
      (opt.errMsg ? '<p class="muted">' + esc(opt.errMsg) + '</p>' : '') +
      '<button class="btn" data-el="btn-retry" data-act="retry">' + esc(P.copy.retry) + '</button></div>';
    return null;
  }

  function listView(s) {
    var st = P.deriveDataState(s.list);
    var scnQs = P.scnQs();
    var body = dataState(st, { scnQs: scnQs, errMsg: s.list.error && s.list.error.message });
    if (body == null) {
      body = '<ul class="rows" data-el="task-list">' + s.list.items.slice(0, 50).map(function (t) {
        return '<li data-el="task-row" data-state="default"><a href="#/task/' + esc(t.id) + scnQs + '">' + esc(t.title) + '</a>' +
          '<span class="muted">' + esc(t.owner) + ' · ' + esc(P.copy.status[t.status]) + '</span>' +
          '<button class="btn tiny" data-el="btn-delete-row" data-act="del" data-id="' + esc(t.id) + '">' + esc(P.copy.del) + '</button></li>';
      }).join('') + '</ul><p class="muted">' + s.list.items.length + ' 条（示例数据）</p>';
    }
    return '<h1>' + esc(P.copy.listTitle) + '</h1>' +
      '<form class="bar" data-act="search"><label for="kw">' + esc(P.copy.searchLabel) + '</label>' +
      '<input id="kw" data-el="task-search" name="kw" type="search" autocomplete="off" value="' + esc(s.list.keyword) + '" placeholder="' + esc(P.copy.searchPh) + '">' +
      '<button class="btn" data-el="btn-search" type="submit">' + esc(P.copy.search) + '</button>' +
      '<a class="btn primary" data-el="btn-create" href="#/create' + scnQs + '">' + esc(P.copy.createCta) + '</a></form>' + body;
  }

  // ⭐ 移动端降级是**实现**，不是在规格里写一句「移动端只读」就完事。
  //   states.json 声明 f02 是 degraded，这里必须真的降级，
  //   否则「声称 ≠ 实际」——而这正是这整轮改造要治的病。
  function advanceBtn() {
    var ro = !P.api.can('write') || P.currentEnd() === 'mobile';
    var why = P.currentEnd() === 'mobile' ? P.copy.mobileReadOnly : P.copy.noPermHint;
    return '<button class="btn primary" data-el="btn-advance" data-state="' + (ro ? 'disabled' : 'default') +
      '" data-act="advance"' + (ro ? ' disabled title="' + esc(why) + '"' : '') + '>' +
      esc(P.copy.advance) + '</button>' +
      (ro ? '<p class="muted">' + esc(why) + '</p>' : '');
  }

  function detailView(s) {
    var st = P.deriveDataState({ loading: s.detail.loading, items: s.detail.item ? [s.detail.item] : null, error: s.detail.error });
    var body = dataState(st, { scnQs: P.scnQs(), errMsg: s.detail.error && s.detail.error.message });
    if (body == null) {
      var t = s.detail.item;
      body = '<dl><dt>ID</dt><dd>' + esc(t.id) + '</dd><dt>' + esc(P.copy.owner) + '</dt><dd>' + esc(t.owner) + '</dd>' +
        '<dt>' + esc(P.copy.statusLabel) + '</dt><dd>' + esc(P.copy.status[t.status]) + '</dd></dl>' +
        advanceBtn();
    }
    return '<div data-el="task-detail">' + '<h1>' + esc(P.copy.detailTitle) + '</h1><a class="back" data-el="btn-back" href="#/inbox' + P.scnQs() + '">' + BACK_ARROW + esc(P.copy.back) + '</a>' + body + '</div>';
  }

  function createView(s) {
    if (P.currentEnd() === 'mobile')
      return '<h1>' + esc(P.copy.createTitle) + '</h1>' +
        '<a class="back" data-el="btn-back" href="#/inbox' + P.scnQs() + '">' + BACK_ARROW + esc(P.copy.back) + '</a>' +
        '<div class="state" data-el="form-create"><p>' + esc(P.copy.pcOnly) + '</p>' +
        '<p class="muted">' + esc(P.copy.pcOnlyHint) + '</p>' +
        '<a class="btn" data-el="btn-back-to-list" href="#/inbox' + P.scnQs() + '">' + esc(P.copy.backToList) + '</a></div>';
    var e = s.form.errors;
    return '<h1>' + esc(P.copy.createTitle) + '</h1><a class="back" data-el="btn-back" href="#/inbox' + P.scnQs() + '">' + BACK_ARROW + esc(P.copy.back) + '</a>' +
      '<form data-el="form-create" data-act="create" novalidate>' +
      '<label for="title">' + esc(P.copy.titleLabel) + '</label>' +
      '<input id="title" data-el="input-title" name="title" value="' + esc(s.form.title) + '" autocomplete="off"' +
        (e.title ? ' aria-invalid="true" aria-describedby="e-title"' : '') + '>' +
      (e.title ? '<p class="err" id="e-title">' + esc(e.title) + '</p>' : '') +
      '<label for="owner">' + esc(P.copy.ownerLabel) + '</label>' +
      '<input id="owner" data-el="input-owner" name="owner" value="' + esc(s.form.owner) + '" autocomplete="off"' +
        (e.owner ? ' aria-invalid="true" aria-describedby="e-owner"' : '') + '>' +
      (e.owner ? '<p class="err" id="e-owner">' + esc(e.owner) + '</p>' : '') +
      (e._form ? '<p class="err" role="alert">' + esc(e._form) + '</p>' : '') +
      '<button class="btn primary" data-el="btn-submit" data-state="' + (s.form.submitting ? 'submitting' : 'default') + '" type="submit">' +
        esc(s.form.submitting ? P.copy.submitting : P.copy.submit) + '</button></form>';
  }

  P.views = { inbox: listView, task: detailView, create: createView };
  P.esc = esc; P.h = h;
})(window.PROTO = window.PROTO || {});
