// ── ① 数据层 · 场景开关 ──────────────────────────────────────────────────
// ⭐ 本文件是「全流程闭环」与「场景稿」的分界线。
//   场景稿：空态/加载/失败各画一屏静态图。
//   闭环稿：**只换输入**（数据条数、时延、失败注入、权限），界面自己走到那个状态。
//   → 状态是**跑**出来的，不是**画**出来的；这也是「与真实实现一致」唯一可能成立的形态。
//
// 借自 Pact 的 provider state：一个场景名 = 一次「假设服务端处于某状态」的声明，
// 日后可以拿同一个名字去真后端回验。
(function (P) {
  'use strict';

  // 每个场景写清：它假设服务端处于什么状态。**名字要能拿去问后端**。
  P.scenarios = {
    'default':       { desc: '正常：有 12 条任务',        seed: 12, latency: 180, fail: null,  canWrite: true },
    'empty':         { desc: '空：一条都没有',            seed: 0,  latency: 180, fail: null,  canWrite: true },
    'slow':          { desc: '慢：接口 2.5s 才回',        seed: 12, latency: 2500, fail: null, canWrite: true },
    'api-500':       { desc: '失败：列表接口 500',        seed: 12, latency: 300, fail: 'list', canWrite: true },
    'save-failed':   { desc: '失败：保存时 500',          seed: 12, latency: 300, fail: 'save', canWrite: true },
    'no-permission': { desc: '无权限：只读账号',          seed: 12, latency: 180, fail: null,  canWrite: false },
    'huge':          { desc: '极值：600 条 + 超长标题',   seed: 600, latency: 400, fail: null, canWrite: true }
  };

  P.currentScenario = function () {
    var m = /[?&]scn=([\w-]+)/.exec(location.hash + location.search);
    var name = (m && P.scenarios[m[1]]) ? m[1] : 'default';
    return { name: name, cfg: P.scenarios[name] };
  };
})(window.PROTO = window.PROTO || {});
