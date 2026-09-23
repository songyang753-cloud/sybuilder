// ⛔ 本文件由 scripts/spec-to-js.py 从 templates/spec/validators.json 生成，**不许手改**。
//    手改的后果不是「改错一个字」，是 demo 与交给研发的物料**从此分叉**，
//    而两边都还能正常跑，所以没人会发现。
//    要改文案/规则，改 spec 里的 json，然后重新生成。
(function (P) {
  'use strict';
  // 声明式规则 + 一个极小解释器。规则是数据 —— 研发照着 validators.json 实现同一套。
  var RULES = {
  "title": [
    {
      "type": "required",
      "msg": "标题不能为空"
    },
    {
      "type": "maxlen",
      "n": 30,
      "msg": "标题不超过 30 个字"
    }
  ],
  "owner": [
    {
      "type": "required",
      "msg": "请填写负责人"
    }
  ]
};
  var TESTS = {
    required: function (v) { return v.trim().length > 0; },
    maxlen:   function (v, r) { return v.trim().length <= r.n; },
    minlen:   function (v, r) { return v.trim().length >= r.n; },
    pattern:  function (v, r) { return new RegExp(r.re).test(v); }
  };
  P.validators = {
    RULES: RULES,
    /** 返回 {field: msg}；空对象表示通过 */
    validate: function (values) {
      var errs = {};
      Object.keys(RULES).forEach(function (f) {
        var v = String(values[f] == null ? '' : values[f]);
        for (var i = 0; i < RULES[f].length; i++) {
          var r = RULES[f][i], t = TESTS[r.type];
          // ⛔ 不认识的规则类型必须炸，不许静默跳过 ——
          //    静默跳过 = spec 里写了一条没人执行的规则，比没写更糟。
          if (!t) throw new Error('未知校验类型: ' + r.type);
          if (!t(v, r)) { errs[f] = r.msg; break; }
        }
      });
      return errs;
    }
  };
})(window.PROTO = window.PROTO || {});
