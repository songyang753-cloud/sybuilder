#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec/*.json → 原型骨架的 js 产物（文案与校验规则）。

═══ 为什么要生成而不是两边各写一份 ═══
`copy.json` / `validators.json` 是**交给研发的物料**；
`js/60-copy.js` / `js/70-validators.js` 是 demo 的运行时。
两份手写就是两份会分叉的副本 —— 而分叉的那一天没人会发现，
因为**两边都能正常跑**，只是文案/规则不一样了。

⭐ 这是本 SOP 反复记的「令牌单一真源」在交互层的同一件事：
   色值从 tokens.json 生成，文案与校验规则也该从 spec 生成。

用法:
  spec-to-js.py <spec目录> <js输出目录>        # 生成
  spec-to-js.py <spec目录> <js输出目录> --check # 只校验产物是否与 spec 一致（不写文件）
  spec-to-js.py --self-test
退出码: 0=一致/已生成  1=产物与 spec 不一致（有人手改了产物）  2=跑不了
"""
import io, json, os, sys

HEAD = ("// ⛔ 本文件由 scripts/spec-to-js.py 从 %s 生成，**不许手改**。\n"
        "//    手改的后果不是「改错一个字」，是 demo 与交给研发的物料**从此分叉**，\n"
        "//    而两边都还能正常跑，所以没人会发现。\n"
        "//    要改文案/规则，改 spec 里的 json，然后重新生成。\n")


def die(m):
    print("UNABLE: %s" % m, file=sys.stderr); sys.exit(2)


def _nest(flat):
    """把 'status.todo' 这样的点号键还原成嵌套对象。"""
    out = {}
    for k, v in flat.items():
        cur = out
        parts = k.split('.')
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return out


def gen_copy(spec):
    strings = spec.get('strings') or {}
    limits = spec.get('limits') or {}
    flat = {k: v['text'] for k, v in strings.items()}
    # 控件字数上限**在生成时就核一遍**：写在文档里的上限没人核，才有了
    # 「Toast 硬上限 18 字、PRD 规定 30 字」长期打架那次教训。
    over = []
    for k, v in strings.items():
        lim = v.get('limit')
        if lim and lim in limits and len(v['text']) > limits[lim]:
            over.append("%s: %d 字 > 上限 %s=%d" % (k, len(v['text']), lim, limits[lim]))
    body = json.dumps(_nest(flat), ensure_ascii=False, indent=2)
    lim_body = json.dumps(limits, ensure_ascii=False)
    js = (HEAD % 'templates/spec/copy.json') + \
         "(function (P) {\n  'use strict';\n  P.copy = Object.assign(%s, %s);\n})(window.PROTO = window.PROTO || {});\n" % (body, lim_body)
    return js, over


def gen_validators(spec):
    fields = spec.get('fields') or {}
    rules = json.dumps(fields, ensure_ascii=False, indent=2)
    js = (HEAD % 'templates/spec/validators.json') + """(function (P) {
  'use strict';
  // 声明式规则 + 一个极小解释器。规则是数据 —— 研发照着 validators.json 实现同一套。
  var RULES = %s;
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
""" % rules
    return js


def run(spec_dir, js_dir, check):
    if not os.path.isdir(spec_dir): die("spec 目录不存在: %s" % spec_dir)
    if not os.path.isdir(js_dir): die("js 目录不存在: %s" % js_dir)
    try:
        copy_spec = json.load(io.open(os.path.join(spec_dir, 'copy.json'), encoding='utf-8'))
        val_spec = json.load(io.open(os.path.join(spec_dir, 'validators.json'), encoding='utf-8'))
    except Exception as e:
        die("读不了 spec: %s" % e)

    copy_js, over = gen_copy(copy_spec)
    val_js = gen_validators(val_spec)
    if over:
        for o in over: print("❌ 文案超出控件上限：%s" % o)
        return 1

    targets = [(os.path.join(js_dir, '60-copy.js'), copy_js),
               (os.path.join(js_dir, '70-validators.js'), val_js)]
    bad = []
    for path, want in targets:
        cur = io.open(path, encoding='utf-8').read() if os.path.exists(path) else None
        if check:
            if cur != want:
                bad.append("%s 与 spec 不一致（有人手改了产物，或 spec 改了没重新生成）" % os.path.basename(path))
        else:
            io.open(path, 'w', encoding='utf-8').write(want)
    if check:
        for b in bad: print("❌ " + b)
        print("✅ 产物与 spec 一致" if not bad else "")
        return 1 if bad else 0
    print("✅ 已生成 %s" % "、".join(os.path.basename(p) for p, _ in targets))
    return 0


# --------------------------------------------------------------- 自证（M8）
_GOOD_COPY = {"limits": {"toastMax": 6}, "strings": {"a": {"text": "确定"}, "b": {"text": "已删除", "limit": "toastMax"}}}
_BAD_COPY = {"limits": {"toastMax": 3}, "strings": {"a": {"text": "确定"}, "b": {"text": "已删除啦啦啦", "limit": "toastMax"}}}
_GOOD_VAL = {"fields": {"t": [{"type": "required", "msg": "必填"}]}}


def _self_test():
    import tempfile, subprocess
    me = os.path.abspath(__file__)
    ok = True
    print("M8 自证 —— 生成/校验/超限/手改产物 各自必须出声\n")

    def mk(copy_spec):
        d = tempfile.mkdtemp(prefix='s2j-')
        sd, jd = os.path.join(d, 'spec'), os.path.join(d, 'js')
        os.makedirs(sd); os.makedirs(jd)
        json.dump(copy_spec, io.open(os.path.join(sd, 'copy.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        json.dump(_GOOD_VAL, io.open(os.path.join(sd, 'validators.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        return sd, jd

    def call(sd, jd, *extra):
        return subprocess.call([sys.executable, me, sd, jd] + list(extra),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    sd, jd = mk(_GOOD_COPY)
    cases = []
    cases.append(("正例：生成成功", call(sd, jd), 0))
    cases.append(("正例：刚生成完 --check 必须一致", call(sd, jd, '--check'), 0))
    # 反例①：手改产物 → --check 必须红（否则这道门只是摆设）
    p = os.path.join(jd, '60-copy.js')
    io.open(p, 'a', encoding='utf-8').write("\n// 有人手改了\n")
    cases.append(("反例①：手改产物后 --check 必须红", call(sd, jd, '--check'), 1))
    # 反例②：文案超出控件上限 → 生成阶段就必须红
    sd2, jd2 = mk(_BAD_COPY)
    cases.append(("反例②：文案超控件字数上限必须红", call(sd2, jd2), 1))
    # 反例③：spec 目录不存在 → 2，不许折叠成 0
    cases.append(("反例③：spec 目录不存在 → 报 2", call(os.path.join(sd, 'nope'), jd), 2))
    for name, got, want in cases:
        g = got == want; ok &= g
        print("  %s %-40s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修"))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    if '--self-test' in sys.argv: sys.exit(_self_test())
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        print(__doc__); sys.exit(2)
    sys.exit(run(args[0], args[1], '--check' in sys.argv))
