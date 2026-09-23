#!/usr/bin/env python3
"""
令牌来源门禁 —— 治「整体声称掩盖逐条编造」。

为什么需要它：
  M2 三来源原则要求「每个事实标出处」，但没规定标注粒度。
  实测 验证项目 的 tokens.json 在 _meta 里整体声称「浅色值取自真实程序 CDP 实测」，
  逐条查下去 10 条色值只有 4 条能在真实程序里找到，另外 6 条无出处——
  真的那 4 条替编的那 6 条背了书。

判据（全部要过）：
  1. 每条令牌必须有 source 字段
  2. source 格式必须可解析：
       measured:<路径>[:<行号>]   —— 且该值必须真能在该文件里 grep 到
       recipe:<食谱名>            —— 且该食谱文件必须存在
       derived:<推导规则>         —— 规则文字非空
       ASM-###                    —— 已登记的假设编号
  3. measured 类必须**实际可验证**：拿令牌值回被测文件里搜，搜不到即红
     （这一条是关键——它把「声称量过」变成「真的量过」）

用法：
  token-provenance-gate.py <tokens.json> [--asm <assumptions.md>] [--json]
退出码：0=通过  1=不通过  2=跑不了
"""
import argparse, json, os, re, sys

HEX = re.compile(r'^#[0-9A-Fa-f]{3,8}$')


def die_unable(msg):
    print(f"UNABLE: {msg}", file=sys.stderr)
    sys.exit(2)


def walk_tokens(node, path=""):
    """产出 (令牌路径, 值对象)。令牌 = 含 value/Light/Dark 或为标量的叶子。"""
    if isinstance(node, dict):
        if "_meta" in node:
            node = {k: v for k, v in node.items() if k != "_meta"}
        # 叶子判定：有 value 字段，或有 Light/Dark 模式
        if "value" in node or ("Light" in node and isinstance(node.get("Light"), (str, int, float))):
            yield path, node
            return
        for k, v in node.items():
            if k.startswith("_"):
                continue
            yield from walk_tokens(v, f"{path}.{k}" if path else k)
    elif isinstance(node, (str, int, float)):
        yield path, {"value": node}


def literal_values(tok):
    """取出该令牌里所有字面值（跳过 {alias} 引用）。"""
    out = []
    for k in ("value", "Light", "Dark"):
        v = tok.get(k)
        if isinstance(v, str) and not (v.startswith("{") and v.endswith("}")):
            out.append(v)
        elif isinstance(v, (int, float)):
            out.append(str(v))
    return out


def check_measured(target, values, base=None):
    """measured:<路径>[:<行>] —— 文件要存在，且值要真能在里面找到。
    给了行号就**只查那一行**——否则纯数字令牌（如 8）在任何文件里都能命中，
    等于没验。数字型令牌因此强制要求行号。

    ⚠️ 2026-09-04：相对路径此前按**当前工作目录**解析 —— 于是
    **同一份 tokens.json，在它自己的目录里跑是 PASS，换个目录跑就 6 条全红**。
    ⭐ 判据依赖 cwd，等于同一份物料有两个结论；而报出来的又是
    「文件不存在」，会让人以为出处写错了（第五次「诊断指向不存在的问题」）。
    改为**相对 tokens 文件所在目录**解析，cwd 作为兜底。
    """
    m = re.match(r'^(.*?)(?::(\d+))?$', target)
    rel = os.path.expanduser(m.group(1))
    lineno = int(m.group(2)) if m.group(2) else None
    cands = [rel] if os.path.isabs(rel) else (
        [os.path.join(base, rel), rel] if base else [rel])
    fpath = next((c for c in cands if os.path.isfile(c)), None)
    if fpath is None:
        return False, ("measured 指向的文件不存在：%s（找过：%s）"
                       % (rel, "、".join(cands)))
    try:
        raw = open(fpath, encoding="utf8", errors="replace").read()
    except Exception as e:
        return False, f"读不了 {fpath}：{e}"
    if lineno is not None:
        lines = raw.splitlines()
        if lineno < 1 or lineno > len(lines):
            return False, f"{os.path.basename(fpath)} 只有 {len(lines)} 行，指向第 {lineno} 行"
        text = lines[lineno - 1]
    else:
        # 没给行号时，纯数字值不予采信——搜 "8" 谁都能中
        if all(re.fullmatch(r'[\d.]+', v) for v in values):
            return False, ("数字型令牌的 measured 必须带行号（写成 `measured:路径:行号`），"
                           "否则搜一个数字在任何文件里都能命中，等于没验")
        text = raw
    for v in values:
        needle = v.lower()
        hay = text.lower()
        if needle in hay:
            return True, ""
        # 十六进制容忍缩写：#FFFFFF ↔ #fff
        if HEX.match(v) and len(v) == 7:
            short = "#" + v[1] + v[3] + v[5]
            if short.lower() in hay:
                return True, ""
    return False, f"值 {values} 在 {os.path.basename(fpath)} 里搜不到（声称量过，实际没有）"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tokens")
    p.add_argument("--asm", help="假设登记文件，用于校验 ASM-### 是否真的登记过")
    p.add_argument("--recipe-dir",
                   default=os.path.expanduser("~/.claude/skills/web-design-engineer/references/style-recipes"))
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.tokens):
        die_unable(f"令牌文件不存在：{a.tokens}")
    # measured 的相对路径按**令牌文件所在目录**解析，不按 cwd（见 check_measured）
    BASE_DIR = os.path.dirname(os.path.abspath(a.tokens))
    try:
        data = json.load(open(a.tokens, encoding="utf8"))
    except Exception as e:
        die_unable(f"令牌文件不是合法 JSON：{e}")

    asm_ids = set()
    if a.asm:
        if not os.path.isfile(a.asm):
            die_unable(f"--asm 指向的文件不存在：{a.asm}")
        asm_ids = set(re.findall(r'ASM-\d+', open(a.asm, encoding="utf8").read()))

    toks = list(walk_tokens(data))
    if not toks:
        die_unable("没解析出任何令牌（文件结构是不是不对？）")

    rows = []
    for tpath, tok in toks:
        src = tok.get("source") if isinstance(tok, dict) else None
        vals = literal_values(tok) if isinstance(tok, dict) else []
        if not vals:                      # 纯别名引用，来源由被引用者负责
            rows.append((tpath, src or "(alias)", True, "别名引用，来源随被引方"))
            continue
        if not src:
            rows.append((tpath, "—", False, "缺 source 字段"))
            continue
        if src.startswith("measured:"):
            ok, why = check_measured(src[len("measured:"):], vals, base=BASE_DIR)
            rows.append((tpath, src, ok, why))
        elif src.startswith("recipe:"):
            name = src[len("recipe:"):].strip()
            f = os.path.join(a.recipe_dir, f"{name}.md")
            ok = os.path.isfile(f)
            rows.append((tpath, src, ok, "" if ok else f"食谱文件不存在：{f}"))
        elif src.startswith("derived:"):
            rule = src[len("derived:"):].strip()
            ok = len(rule) >= 4
            rows.append((tpath, src, ok, "" if ok else "derived 的推导规则为空或过短"))
        elif re.fullmatch(r'ASM-\d+', src):
            ok = (not a.asm) or (src in asm_ids)
            rows.append((tpath, src, ok, "" if ok else f"{src} 未在假设登记表里出现"))
        else:
            rows.append((tpath, src, False,
                         "source 格式不可解析（只允许 measured:/recipe:/derived:/ASM-###）"))

    bad = [r for r in rows if not r[2]]
    passed = not bad

    if a.json:
        print(json.dumps({"file": a.tokens, "total": len(rows), "failed": len(bad),
                          "rows": [{"token": t, "source": s, "pass": ok, "why": w}
                                   for t, s, ok, w in rows], "passed": passed},
                         ensure_ascii=False, indent=2))
    else:
        print(f"令牌文件：{a.tokens}")
        print(f"令牌总数：{len(rows)}　不合格：{len(bad)}\n")
        for t, s, ok, w in rows:
            if not ok:
                print(f"  ❌ {t:<28} source={s:<40} {w}")
        if passed:
            print("  （全部令牌来源可追）")
            print("⚠️ 本门只验来源**写了、且格式可解析、且 measured 指到的文件存在** ——\n      **不验那个来源说的是不是真的**：一句 `derived:...` 没有任何东西核对它，\n      而 `measured:` 只核到「文件存在」，不核「文件里真有这个数」。")
        print(f"\n结论：{'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)




# ------------------------------------------------------------------ M8 自证
def _self_test():
    """⚠️ 2026-08-31 补 —— 此前文档声称「全部门禁均自带 --self-test」而本脚本没有。"""
    import os, sys, json as _j, tempfile, subprocess, io as _io
    t = tempfile.mkdtemp(prefix="tpg-")
    me = os.path.abspath(__file__)
    src = os.path.join(t, "real.css")
    _io.open(src, "w", encoding="utf-8").write("body{background:#fafafa;color:#171717}")
    def w(n, obj):
        p = os.path.join(t, n); _io.open(p, "w", encoding="utf-8").write(_j.dumps(obj, ensure_ascii=False)); return p
    def run(p, *x):
        return subprocess.call([sys.executable, me, p] + list(x),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    good = {"color": {"bg": {"value": "#fafafa", "source": "measured:%s" % src},
                      "fg": {"value": "#171717", "source": "measured:%s" % src},
                      "alias": {"value": "{color.bg}"}},
            "space": {"md": {"value": "16px", "source": "derived:4 的倍数阶梯"}}}
    import copy
    no_src = copy.deepcopy(good); del no_src["space"]["md"]["source"]
    fake = copy.deepcopy(good); fake["color"]["bg"]["value"] = "#123456"   # measured 但搜不到
    badfmt = copy.deepcopy(good); badfmt["space"]["md"]["source"] = "我量的"
    # ⭐ 2026-09-02 变异审计补：四种来源类型里,recipe/derived/ASM 三条的**失败路径**
    #    此前一个用例都没有 —— 变异后自证照样全绿，等于这三条从没被证明会工作。
    no_recipe = copy.deepcopy(good)
    no_recipe["space"]["md"]["source"] = "recipe:根本不存在的食谱"
    empty_derived = copy.deepcopy(good)
    empty_derived["space"]["md"]["source"] = "derived:"          # 推导规则为空
    bad_asm = copy.deepcopy(good)
    bad_asm["space"]["md"]["source"] = "ASM-999"                  # 未在假设表里登记
    cases = [("正例", good, 0), ("反例 缺 source", no_src, 1),
             ("反例 measured 但值搜不到", fake, 1), ("反例 source 格式非法", badfmt, 1),
             ("反例 recipe 食谱文件不存在", no_recipe, 1),
             ("反例 derived 推导规则为空", empty_derived, 1)]
    # ⭐ 2026-09-04：measured 的相对路径此前按 **cwd** 解析 ——
    #    同一份 tokens.json 在它自己的目录里跑是 PASS，换个目录跑 6 条全红，
    #    且报的是「文件不存在」，会让人以为出处写错了。
    #    判据依赖 cwd ＝ 同一份物料有两个结论。
    import os as _os, json as _json, tempfile as _tf, subprocess as _sp, sys as _sys
    _d = _tf.mkdtemp(prefix="tp-cwd-")
    import io as _io_mod
    _io_open = _io_mod.open
    _io_open(_os.path.join(_d, "src.css"), "w", encoding="utf-8").write(":root{--a:#123456}\n")
    _tok = _os.path.join(_d, "t.json")
    _io_open(_tok, "w", encoding="utf-8").write(_json.dumps(
        {"tokens": {"colors.a": {"value": "#123456", "source": "measured:src.css:1"}}},
        ensure_ascii=False))
    _me = _os.path.abspath(__file__)
    _rc_other = _sp.call([_sys.executable, _me, _tok], cwd=_os.path.expanduser("~"),
                         stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    ok = True
    print("M8 自证 —— 正例绿 / 每类反例红 / 无效输入报错不返绿\n")
    # ⚠️ 这一条**不能进 cases 循环**：循环会把第二个元素当 JSON 对象写进文件再跑，
    #    而这里要断言的是「换个 cwd 跑同一份文件」——它已经跑过了，手上只有退出码。
    _g = (_rc_other == 0); ok = ok and _g
    print("  %s %-46s 期望 0 实得 %d"
          % ("✅" if _g else "❌",
             "从别的目录跑同一份 tokens 结论一致（判据不许依赖 cwd）", _rc_other))
    for n, obj, want in cases:
        rc = run(w(n.replace(" ", "_") + ".json", obj))
        g = rc == want; ok &= g
        print("  %s %-28s 期望 %d 实得 %d" % ("✅" if g else "❌", n, want, rc))

    # ⭐ ASM 分支只有传 --asm 时才判 —— 不传就整条不执行，
    #    此前所有用例都没传，于是**这条判据一次都没被跑过而自证照样全绿**。
    asm_ok = os.path.join(t, "asm_ok.md")
    _io.open(asm_ok, "w", encoding="utf-8").write("| ASM-101 | 状态色暂定 | 待否决 |\n")
    asm_case = copy.deepcopy(good); asm_case["space"]["md"]["source"] = "ASM-101"
    rc = run(w("asm_good.json", asm_case), "--asm", asm_ok)
    g = rc == 0; ok &= g
    print("  %s %-28s 期望 0 实得 %d" % ("✅" if g else "❌", "正例 ASM 已登记", rc))
    asm_bad = copy.deepcopy(good); asm_bad["space"]["md"]["source"] = "ASM-999"
    rc = run(w("asm_bad.json", asm_bad), "--asm", asm_ok)
    g = rc == 1; ok &= g
    print("  %s %-28s 期望 1 实得 %d" % ("✅" if g else "❌", "反例 ASM 未登记", rc))
    rc = run(os.path.join(t, "nope.json")); g = rc == 2; ok &= g
    print("  %s %-28s 期望 2 实得 %d" % ("✅" if g else "❌", "输入不存在", rc))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败"))
    return 0 if ok else 1


# ── 意外异常必须报「跑不了」，不许和「有发现」共用退出码 ────────────────
# 🚨 2026-09-05：本门原有针对**特定读操作**的 `except`，但意外异常出现在别处仍会 rc=1
#    —— **与「有发现」同码**。后果：① 报告里长成「有发现」，把人送去查不存在的缺陷；
#    ② 自证里只看退出码的反例，**崩溃会被读成「反例红了」**。
# ⛔ `except Exception` 不捕获 `SystemExit`，门禁自己的 exit(0/1/2) 不受影响。
def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb, sys as _sys
        print("UNABLE: 门禁自身异常（不是「有发现」）：%s: %s"
              % (type(_e).__name__, _e), file=_sys.stderr)
        _tb.print_exc(file=_sys.stderr)
        _sys.exit(2)


if __name__ == '__main__':
    def _entry():
        if "--self-test" in sys.argv:
            sys.exit(_self_test())
        main()
    _main_guarded(_entry)
