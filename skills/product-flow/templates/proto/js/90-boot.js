// ── 启动：路由 → 取数 → 渲染 → 事件委托 ──────────────────────────────────
(function (P) {
  'use strict';
  var app, toastEl;

  P.scnQs = function () {
    var n = P.currentScenario().name, e = P.currentEnd();
    var parts = [];
    if (n !== 'default') parts.push('scn=' + n);
    if (e !== 'pc') parts.push('end=' + e);
    return parts.length ? '?' + parts.join('&') : '';
  };

  function toast(msg, undoFn) {
    // ⛔ 文案硬上限在这里真的执行，不是写在文档里
    var text = msg.length > P.copy.toastMax ? msg.slice(0, P.copy.toastMax - 1) + '…' : msg;
    toastEl.innerHTML = P.esc(text) + (undoFn ? ' <button class="btn tiny" data-el="btn-undo" data-act="undo">' + P.esc(P.copy.undo) + '</button>' : '');
    toastEl.hidden = false;
    toastEl._undo = undoFn || null;
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(function () { toastEl.hidden = true; toastEl._undo = null; }, 6000);
  }

  function loadRoute() {
    // 瞬态提示不跨导航存活 —— 用户已经离开那个上下文，「撤销」也就没有对象了
    if (toastEl) { toastEl.hidden = true; toastEl._undo = null; clearTimeout(toastEl._t); }
    var r = P.router.parse();
    P.store.set({ route: r });
    if (r.path === 'inbox') {
      P.store.set({ list: Object.assign({}, P.store.get().list, { loading: true, error: null, keyword: r.query.kw || '' }) });
      P.api.listTasks({ keyword: r.query.kw || '' }).then(function (res) {
        P.store.set({ list: Object.assign({}, P.store.get().list, { loading: false, items: res.items, error: null }) });
      })['catch'](function (e) {
        P.store.set({ list: Object.assign({}, P.store.get().list, { loading: false, items: null, error: e }) });
      });
    } else if (r.path === 'task') {
      P.store.set({ detail: { loading: true, item: null, error: null } });
      P.api.getTask(r.param).then(function (t) { P.store.set({ detail: { loading: false, item: t, error: null } }); })
        ['catch'](function (e) { P.store.set({ detail: { loading: false, item: null, error: e } }); });
    } else if (r.path === 'create') {
      P.store.set({ form: { title: '', owner: '', errors: {}, submitting: false } });
    }
  }

  // 新建页没有「取数」，但它**确实有状态**：默认 / 校验或保存失败 / 无权限。
  // ⛔ 早先这里恒定返回 success，于是 data-scene 对这一屏毫无信息量 ——
  //   状态矩阵门禁当场把它揪了出来（f03 的三个状态全部触发不出来）。
  function createSlice(form) {
    if (form.errors && form.errors._code === 403)
      return { loading: false, items: null, error: { code: 403 } };   // → no-permission
    if (form.errors && Object.keys(form.errors).length)
      return { loading: false, items: null, error: { code: 400 } };   // → error
    return { loading: false, items: [1], error: null };               // → default 由下方改名
  }

  function render(s) {
    if (!s.route) return;
    var v = P.views[s.route.path];
    app.innerHTML = v ? v(s) : '';
    // ⭐ 锚点由 runtime 自动写入 —— 契约不废，但不再靠人手贴 data-scene。
    //   G2/G3 与 demo-anchor-gate 的输入照旧成立。
    var dataSlice = s.route.path === 'inbox' ? s.list
      : s.route.path === 'task' ? { loading: s.detail.loading, items: s.detail.item ? [s.detail.item] : null, error: s.detail.error }
      : createSlice(s.form);
    // 端进场景 ID —— 双端产品最容易丢的就是移动端那一半，
    // 因为没人导航到那儿去看。让它进锚点，矩阵门就会逐端真跑一遍。
    P.END = P.currentEnd();
    P.shell.render(P.END, s.route);     // 端外壳：桌面侧栏 / 移动 app bar
    var st = P.deriveDataState(dataSlice);
    // 表单页的「正常态」在规格里叫 default（它没有「查到了数据」这回事）
    if (s.route.path === 'create' && st === 'success') st = 'default';
    // 仅桌面的界面在移动端要给出**可登记的状态**，而不是假装它跟桌面一样正常
    if (s.route.path === 'create' && P.currentEnd() === 'mobile') st = 'pc-only';
    document.body.setAttribute('data-scene', s.route.id + '-' + P.END + '-' + st);
    // 就绪标记 data-busy 由 api 层统一维护（busy = 有请求在飞），此处不重复设置 ——
    // 两处各设一遍必然分叉，而分叉的那一次就是探针量错的那一次。
    // 需求锚点按三层合并：界面级 → 状态级 → 端+状态级。
    // ⭐ 起因（2026-09-04 真跑 G2 时才暴露）：原来只取界面级，于是 f01 的
    //   empty/loading/error/success **四个状态挂同一串 AC**。而像
    //   「接口失败时要给出原因与重试入口」这类验收标准本身就是**状态级**主张 ——
    //   界面级锚点表达不了它，G2 只能报「这条 AC 没有 demo 场景」。
    // ⛔ 当时的诱惑是去 frMap 里给 f01 补上 AC-4 —— 那会让 empty 态也宣称
    //   「我演示了失败重试」，**锚点一旦说谎，对账门就变成了盖章机**。
    //   正确的解法是让锚点的粒度追上验收标准的粒度。
    document.body.setAttribute('data-fr', frFor(s.route.id, P.END, st));
    document.title = P.copy[s.route.path === 'inbox' ? 'listTitle' : s.route.path === 'task' ? 'detailTitle' : 'createTitle'];
  }

  // 三层键合并，去重保序。端级键（f01-mobile-error）留给「只在某一端成立」的 AC。
  function frFor(id, end, st) {
    var keys = [id, id + '-' + st, id + '-' + end + '-' + st], out = [];
    for (var i = 0; i < keys.length; i++) {
      var v = P.FR_MAP[keys[i]];
      if (!v) continue;
      v.split(',').forEach(function (x) {
        x = x.trim();
        if (x && out.indexOf(x) < 0) out.push(x);
      });
    }
    return out.join(',');
  }

  function onClick(ev) {
    var el = ev.target.closest('[data-act]');
    if (!el) return;
    var act = el.getAttribute('data-act');
    if (act === 'retry') { loadRoute(); }
    else if (act === 'undo') { if (toastEl._undo) { var f = toastEl._undo; toastEl._undo = null; toastEl.hidden = true; f(); } }
    else if (act === 'del') {
      var id = el.getAttribute('data-id');
      P.api.getTask(id).then(function (snapshot) {
        return P.api.deleteTask(id).then(function () {
          loadRoute();
          // ⛔ 撤销本身也会失败（save-failed 场景）。少写这个 catch 的后果不是「少个提示」，
          //   是**未捕获 rejection**：用户点了撤销、什么都没发生、也没有任何解释。
          //   这条是 dead-click-gate 的控制台判据当场抓出来的。
          toast(P.copy.deleted, function () {
            P.api.createTask(snapshot).then(loadRoute)['catch'](function (e) { toast(e.message); });
          });
        });
      })['catch'](function (e) { toast(e.message); });
    } else if (act === 'advance') {
      var s = P.store.get(); if (!s.detail.item) return;
      var next = { todo: 'doing', doing: 'done', done: 'todo' }[s.detail.item.status];
      P.api.updateTask(s.detail.item.id, { status: next })
        .then(function (t) { P.store.set({ detail: { loading: false, item: t, error: null } }); })
        ['catch'](function (e) { toast(e.message); });
    }
  }

  function onSubmit(ev) {
    var f = ev.target.closest('form[data-act]'); if (!f) return;
    ev.preventDefault();
    var act = f.getAttribute('data-act');
    if (act === 'search') { P.router.go('inbox', { kw: f.kw.value, scn: P.currentScenario().name }); loadRoute(); return; }
    if (act === 'create') {
      var values = { title: f.title.value, owner: f.owner.value };
      var errs = P.validators.validate(values);
      P.store.set({ form: Object.assign({}, P.store.get().form, values, { errors: errs }) });
      if (Object.keys(errs).length) {                    // 焦点移到第一个错误（interaction-criteria）
        var first = document.querySelector('[aria-invalid="true"]'); if (first) first.focus();
        return;
      }
      P.store.set({ form: Object.assign({}, P.store.get().form, { submitting: true }) });
      P.api.createTask(values).then(function () {
        P.router.go('inbox', { scn: P.currentScenario().name }); loadRoute();
      })['catch'](function (e) {
        P.store.set({ form: Object.assign({}, P.store.get().form,
          { submitting: false, errors: { _form: e.message, _code: e.code } }) });
      });
    }
  }

  P.boot = function (opt) {
    // ⭐⭐ mock 层（`00-fixtures` / `10-scenarios`）在**换成真实现时会被整个删掉**。
    //   本骨架的核心声称是「把 api.js 整体换成真 fetch，其余三层一行都不用改」——
    //   🚨 2026-09-04 实测那句话当时是**假的**：`P.currentScenario` 与 `P.scenarios`
    //   都定义在 mock 层，删掉后 boot 直接抛，页面上只剩演示外壳、
    //   **产品内容一个字都不渲染**。
    //   ⛔ 这不是小瑕疵：deviation-free 是这个模型存在的**唯一理由**。
    //   兜底放在这一处，而不是每个调用点各写一遍（分叉必然发生在其中一处）。
    P.currentScenario = P.currentScenario || function () {
      return { name: 'default', cfg: {} };
    };
    P.END = (opt && opt.end) || P.currentEnd();
    P.FR_MAP = (opt && opt.frMap) || {};
    app = document.getElementById('app');
    toastEl = document.getElementById('toast');
    // 门禁的输入：路由 × 场景全展开
    window.__PROTO_ROUTES__ = P.buildRouteMatrix();
    // 界面 id → 路由路径。`scenario-matrix-gate` 靠它把 states.json 里的
    // 「f02 的 no-permission 由 scn=no-permission 触发」翻译成一次真实导航。
    window.__PROTO_SURFACES__ = P.router.ROUTES.reduce(function (m, r) {
      m[r.id] = r.path === 'task' ? 'task/T-1000' : r.path; return m;
    }, {});
    // 各界面支持哪些端 —— 矩阵门按它决定要不要去验移动端那一半
    // 视觉门禁据此把每一屏在两个主题下各审一遍
    window.__PROTO_THEMES__ = ['light', 'dark'];
    window.__PROTO_ENDS__ = P.router.ROUTES.reduce(function (m, r) {
      m[r.id] = r.ends || ['pc']; return m;
    }, {});
    P.store.subscribe(render);
    document.addEventListener('click', onClick);
    document.addEventListener('submit', onSubmit);
    window.addEventListener('hashchange', loadRoute);
    P.shell.bindEndSwitch(loadRoute);
    // 窗口尺寸变化会改变兜底端（无 ?end= 时按视口判），要跟着重渲染
    window.addEventListener('resize', function () { render(P.store.get()); });
    loadRoute();
  };
})(window.PROTO = window.PROTO || {});
