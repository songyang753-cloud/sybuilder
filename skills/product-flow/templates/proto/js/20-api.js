// ── ② 契约层 ────────────────────────────────────────────────────────────
// ⭐⭐ 这是整份 demo 与「真实实现」之间**唯一**的接触面。
//   借自 MSW 的 Deviation-free：上层代码不知道自己是不是被 mock 了 ——
//   把本文件整体换成真 fetch，其余三层**一行都不用改**。
//
// ⛔ 硬约束：
//   · 每个函数都返回 Promise（真接口是异步的，同步的 demo 到研发手里必然重写）
//   · 函数名 / 入参 / 返回形状 / 错误码 = 交给研发的接口草案（对应 spec/operations.json）
//   · 失败是**抛出**，不是返回 null —— 上层必须真的写 catch，才会真的有失败态
(function (P) {
  'use strict';

  function delay(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // ⭐ 就绪标记的**唯一归属**：只要还有请求在飞，body 上就挂 data-busy。
  //   ⛔ 别把它放在视图层按「加载态」写 —— 那样只覆盖「首屏取数」，
  //   点击触发的写请求（删除/保存）不在其中，探针会在异步落定前就量，
  //   把**正确实现的异步按钮**判成死按钮。（本骨架当场撞过这一次。）
  var inflight = 0;
  function track(p) {
    inflight++; document.body.setAttribute('data-busy', '1');
    var done = function () { if (--inflight <= 0) { inflight = 0; document.body.removeAttribute('data-busy'); } };
    return p.then(function (v) { done(); return v; }, function (e) { done(); throw e; });
  }

  function ApiError(code, message) {
    var e = new Error(message); e.code = code; e.name = 'ApiError'; return e;
  }

  var db = null;   // 进程内「服务端」。场景切换时重建。
  function ensureDb() {
    var s = P.currentScenario();
    if (!db || db._scn !== s.name) {
      db = { _scn: s.name, tasks: P.fixtures.seedTasks(s.cfg.seed) };
      if (s.name === 'huge') db.tasks[0].title = '超长标题压力测试'.repeat(12);
    }
    return db;
  }

  P.api = {
    /** GET /tasks → {items, total} */
    listTasks: function (query) {
      var s = P.currentScenario();
      return track(delay(s.cfg.latency).then(function () {
        if (s.cfg.fail === 'list') throw ApiError(500, '服务暂时不可用');
        var items = ensureDb().tasks.slice();
        var kw = (query && query.keyword || '').trim();
        if (kw) items = items.filter(function (t) { return t.title.indexOf(kw) > -1; });
        if (query && query.status) items = items.filter(function (t) { return t.status === query.status; });
        return { items: items, total: items.length };
      }));
    },

    /** GET /tasks/:id */
    getTask: function (id) {
      var s = P.currentScenario();
      return track(delay(s.cfg.latency / 2).then(function () {
        var t = ensureDb().tasks.filter(function (x) { return x.id === id; })[0];
        if (!t) throw ApiError(404, '这条任务不存在或已被删除');
        return t;
      }));
    },

    /** POST /tasks */
    createTask: function (payload) {
      var s = P.currentScenario();
      return track(delay(s.cfg.latency).then(function () {
        if (!s.cfg.canWrite) throw ApiError(403, '当前账号只读，无法新建');
        if (s.cfg.fail === 'save') throw ApiError(500, '保存失败，请重试');
        var d = ensureDb();
        var t = P.fixtures.makeTask(d.tasks.length, { title: payload.title, owner: payload.owner, status: 'todo' });
        d.tasks.unshift(t);
        return t;
      }));
    },

    /** PATCH /tasks/:id */
    updateTask: function (id, patch) {
      var s = P.currentScenario();
      return track(delay(s.cfg.latency).then(function () {
        if (!s.cfg.canWrite) throw ApiError(403, '当前账号只读，无法修改');
        if (s.cfg.fail === 'save') throw ApiError(500, '保存失败，请重试');
        var t = ensureDb().tasks.filter(function (x) { return x.id === id; })[0];
        if (!t) throw ApiError(404, '这条任务不存在或已被删除');
        for (var k in patch) t[k] = patch[k];
        return t;
      }));
    },

    /** DELETE /tasks/:id */
    deleteTask: function (id) {
      var s = P.currentScenario();
      return track(delay(s.cfg.latency).then(function () {
        if (!s.cfg.canWrite) throw ApiError(403, '当前账号只读，无法删除');
        var d = ensureDb();
        var before = d.tasks.length;
        d.tasks = d.tasks.filter(function (x) { return x.id !== id; });
        if (d.tasks.length === before) throw ApiError(404, '这条任务不存在或已被删除');
        return { ok: true };
      }));
    },

    /** 权限查询：视图靠它区分 disabled（差条件）与 no-permission（没权限） */
    can: function (action) {
      return P.currentScenario().cfg.canWrite || action === 'read';
    }
  };
})(window.PROTO = window.PROTO || {});
