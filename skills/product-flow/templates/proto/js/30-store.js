// ── ③ 状态层 · 极小 store（约 40 行，零依赖，零外链）───────────────────────
// ⛔ 状态**由数据推导**，不是手工挑一个 'empty' 字符串挂上去。
//   `deriveDataState()` 是这整套东西成立的关键：同一段渲染代码，
//   喂 0 条数据它就是空态、喂错误它就是失败态 —— 不需要另画一屏。
(function (P) {
  'use strict';

  function createStore(initial) {
    var state = initial, subs = [];
    return {
      get: function () { return state; },
      set: function (patch) {
        var next = {}; var k;
        for (k in state) next[k] = state[k];
        for (k in patch) next[k] = patch[k];
        state = next;                      // 不改旧对象：便于「前后对比」与回放
        for (var i = 0; i < subs.length; i++) subs[i](state);
      },
      subscribe: function (fn) { subs.push(fn); return function () { subs = subs.filter(function (f) { return f !== fn; }); }; }
    };
  }

  /**
   * ① 数据/流程状态：从「请求进行中 / 出错了 / 拿到几条」推导，不许外部直接指定。
   * 判据见 references/interaction-patterns.md（四类状态的唯一权威源）。
   */
  function deriveDataState(slice) {
    if (slice.error) return slice.error.code === 403 ? 'no-permission' : 'error';
    if (slice.loading) return 'loading';
    if (!slice.items) return 'default';
    return slice.items.length === 0 ? 'empty' : 'success';
  }

  P.createStore = createStore;
  P.deriveDataState = deriveDataState;

  P.store = createStore({
    route: null,
    list: { loading: false, items: null, error: null, keyword: '', status: '' },
    detail: { loading: false, item: null, error: null },
    form: { title: '', owner: '', errors: {}, submitting: false },
    toast: null
  });
})(window.PROTO = window.PROTO || {});
