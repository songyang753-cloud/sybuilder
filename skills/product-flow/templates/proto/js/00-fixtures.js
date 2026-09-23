// ── ① 数据层 · 种子与工厂 ────────────────────────────────────────────────
// 这一层是 demo 里**唯一**允许出现假数据的地方。
// ⛔ 视图层不许直接读它，必须走 api（否则「换成真接口」时要改的地方遍布全文件）。
// 借自 MirageJS 的 factories / fixtures：数据是**造**出来的，不是抄一份 JSON 贴死。
(function (P) {
  'use strict';

  // 明显是样例的数据。⛔ 不要用看起来像真实统计的数字（会被下游当真）
  var NAMES = ['季度对账单', '供应商合同（示例）', '出差报销单', '设备验收表', '培训签到表'];
  var OWNERS = ['示例·张', '示例·李', '示例·王'];

  function makeTask(i, over) {
    var t = {
      id: 'T-' + (1000 + i),
      title: NAMES[i % NAMES.length] + ' ' + (i + 1),
      owner: OWNERS[i % OWNERS.length],
      status: ['todo', 'doing', 'done'][i % 3],
      updatedAt: '2026-09-0' + ((i % 9) + 1),
      note: ''
    };
    for (var k in (over || {})) t[k] = over[k];
    return t;
  }

  P.fixtures = {
    makeTask: makeTask,
    /** 造 n 条。scenario 想要空列表就传 0 —— **空态是数据造出来的，不是另画一屏** */
    seedTasks: function (n) {
      var out = [];
      for (var i = 0; i < n; i++) out.push(makeTask(i));
      return out;
    }
  };
})(window.PROTO = window.PROTO || {});
