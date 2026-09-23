#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`design/DESIGN.md` 的 YAML front matter → `design/tokens.json`（生成，不手写）。

═══ 为什么改成生成 ═══
原来的契约是：`DESIGN.md`（给人看的正本）+ `tokens.json`（**机器可读镜像**，逐条带 source）。
⛔ 「镜像」就是**手工同步的第二个源** —— 本 SOP 今天已经在文案、校验规则、元素身份
三处修过同一个病：**两处各写一遍必然分叉，而分叉那天两边都还是绿的**。
⇒ 令牌也一样：`DESIGN.md` 的 front matter 是**唯一源**，`tokens.json` 由本脚本生成。

═══ 为什么用这个格式 ═══
front matter 采用 **google-labs-code/design.md**（27k★，给编码 agent 的视觉身份格式规范）
的 schema：typed token groups（colors / typography / rounded / spacing / components）
+ `{path.to.token}` 引用语法，本身**脱胎自 W3C DTCG**（design-tokens/community-group）。
⭐ 好处不只是少一个文件：这个格式**可被别的 agent 直接读**，也能被
`npx @google/design.md lint` 校验（token 引用是否断链、对比度是否达标），
并且能双向转换到 Figma variables / Tailwind theme / Style Dictionary。

⭐ 本 SOP 在标准之上加了一件它没有的东西：**逐条 `source` 出处**
（写在 front matter 的 `sources:` 段）。理由见 `token-provenance-gate.py`：
整体声称会掩盖逐条编造。

用法:
  design-to-tokens.py <DESIGN.md> <tokens.json>            # 生成
  design-to-tokens.py <DESIGN.md> <tokens.json> --check    # 只校验一致（不写）
  design-to-tokens.py --self-test
退出码: 0=一致/已生成  1=不一致或缺 source  2=跑不了
"""
import io, json, os, re, sys

try:
    import yaml
except ImportError:
    yaml = None

FM = re.compile(r'\A---\s*\n(.*?)\n---\s*\n', re.S)
GROUPS = ('colors', 'typography', 'rounded', 'spacing', 'components')


def die(m):
    print("UNABLE: %s" % m, file=sys.stderr); sys.exit(2)


def parse_front_matter(md):
    m = FM.match(md)
    if not m:
        return None, "DESIGN.md 开头没有 YAML front matter（--- 包起来的那段）"
    if yaml is None:
        return None, "本机没有 PyYAML，解析不了 front matter"
    try:
        d = yaml.safe_load(m.group(1))
    except Exception as e:
        return None, "front matter YAML 解析失败：%s" % e
    if not isinstance(d, dict):
        return None, "front matter 不是一个映射"
    return d, None


def flatten(fm):
    """把 typed groups 摊平成 `组.名[.子键]` → 值。"""
    out = {}
    for g in GROUPS:
        grp = fm.get(g)
        if not isinstance(grp, dict):
            continue
        for name, val in grp.items():
            if isinstance(val, dict):
                for k, v in val.items():
                    out["%s.%s.%s" % (g, name, k)] = v
            else:
                out["%s.%s" % (g, name)] = val
    return out


def build(fm):
    """front matter → tokens.json 结构（逐条带 source）。"""
    flat = flatten(fm)
    sources = fm.get('sources') or {}
    tokens, missing = {}, []
    for k, v in flat.items():
        # source 支持三种粒度：整条 `colors.primary.x` / 该组名 `colors.primary` / 该组 `colors`
        src = sources.get(k) or sources.get(k.rsplit('.', 1)[0]) or sources.get(k.split('.')[0])
        if not src:
            missing.append(k)
        tokens[k] = {"value": v, "source": src}
    meta = {"name": fm.get('name'), "version": fm.get('version'),
            "generatedFrom": "DESIGN.md front matter",
            "_": "⛔ 本文件由 scripts/design-to-tokens.py 生成，不许手改。改 DESIGN.md 的 front matter。"}
    # `omitted` 是 DESIGN.md 规范里的「刻意不做」声明 —— 与本 SOP 的诚实缺口是同一件事，原样带过来
    if fm.get('omitted'):
        meta['omitted'] = fm['omitted']
    return {"_meta": meta, "tokens": tokens}, missing


REQUIRED_SECTIONS = [
    ("Known Gaps", "诚实缺口", "43/74 个真实品牌的 DESIGN.md 里有这一节 —— 这不是我发明的规矩，是实践者收敛出来的"),
    ("Iteration Guide", "怎么往下扩", "50/74 有 —— 它回答的是 agent 最先撞上的那个问题：「我要一个这里没有的值，怎么办」"),
]


def check_sections(md):
    """DESIGN.md 正文必须有两节（大小写与中文标题都认）。

    ⭐ 来源：`VoltAgent/awesome-design-md` 里 74 个真实品牌的 DESIGN.md
       （linear / stripe / notion / vercel / figma / shopify …）的章节分布实测。
    ⭐⭐ `Known Gaps` 的**写法**也值得抄：真实文件里每一条都说清
       **为什么缺**（「inspected pages 上看不到」「营销站根本没有浅色主题」）
       **和怎么办**（「字体是专有的，用开源替代可以」）——
       比只写「本轮不做」高一档。
    """
    miss = []
    for en, zh, why in REQUIRED_SECTIONS:
        pat = re.compile(r'^#{1,3}\s*(?:\d+[.、]\s*)?(%s|%s)\s*$' % (re.escape(en), re.escape(zh)),
                         re.M | re.I)
        if not pat.search(md):
            miss.append("缺 `## %s`（%s）—— %s" % (en, zh, why))
    return miss


def run(md_path, out_path, check):
    if not os.path.isfile(md_path): die("找不到 %s" % md_path)
    md = io.open(md_path, encoding='utf-8', errors='replace').read()
    fm, err = parse_front_matter(md)
    if err: die(err)
    sec_miss = check_sections(md)
    data, missing = build(fm)
    if not data['tokens']:
        print("❌ front matter 里一个令牌都没有（colors / typography / rounded / spacing / components 全空）")
        return 1
    if sec_miss:
        print("❌ DESIGN.md 正文缺必需章节：")
        for m in sec_miss: print("   · " + m)
        return 1
    if missing:
        print("❌ %d 条令牌没有 source（在 front matter 的 sources: 段里补）：" % len(missing))
        for k in missing[:8]: print("   · " + k)
        if len(missing) > 8: print("   …… 还有 %d 条" % (len(missing) - 8))
        print("\n⭐ 整体声称会掩盖逐条编造 —— 见 token-provenance-gate.py 的实测教训。")
        return 1
    want = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if check:
        cur = io.open(out_path, encoding='utf-8').read() if os.path.isfile(out_path) else None
        if cur != want:
            print("❌ tokens.json 与 DESIGN.md 不一致（有人手改了产物，或 front matter 改了没重新生成）")
            return 1
        print("✅ tokens.json 与 DESIGN.md 一致（%d 条令牌）" % len(data['tokens']))
        return 0
    io.open(out_path, 'w', encoding='utf-8').write(want)
    print("✅ 已生成 %s（%d 条令牌）" % (os.path.basename(out_path), len(data['tokens'])))
    return 0


# --------------------------------------------------------------- 自证（M8）
_GOOD = """---
version: alpha
name: 示例
colors:
  primary: "#1A1C1E"
  surface: "#FFFFFF"
typography:
  h1:
    fontFamily: Public Sans
    fontSize: 48px
spacing:
  md: 16px
sources:
  colors: "measured:design/screenshots/home.png:1"
  typography.h1: "recipe:broadsheet"
  spacing: "derived:8 的倍数"
---

## Overview
正文。

## Known Gaps
- 深色主题没做：本轮只交付浅色，深色留到 v2（届时按同一套语义令牌加一层）。

## Iteration Guide
1. 一次只动一个组件，按 `components:` 里的令牌名引用它。
2. 需要新值时先问它属于哪一组，⛔ 不要直接写字面量。
"""
_NO_SOURCE = _GOOD.replace('sources:\n  colors: "measured:design/screenshots/home.png:1"\n', 'sources:\n')
_NO_GAPS = _GOOD.replace("## Known Gaps\n- 深色主题没做：本轮只交付浅色，深色留到 v2（届时按同一套语义令牌加一层）。\n\n", "")
_NO_ITER = _GOOD.replace("## Iteration Guide\n1. 一次只动一个组件，按 `components:` 里的令牌名引用它。\n2. 需要新值时先问它属于哪一组，⛔ 不要直接写字面量。\n", "")
_NO_FM = "## Overview\n没有 front matter。\n"
_EMPTY = """---
name: 空的
---

## Overview
一个令牌都没有。
"""
for n, s in (('no-source', _NO_SOURCE), ('no-fm', _NO_FM), ('empty', _EMPTY),
             ('no-gaps', _NO_GAPS), ('no-iter', _NO_ITER)):
    if s == _GOOD: raise SystemExit("自证用例坏了：反例 %s 与正例逐字相同" % n)


def _self_test():
    import tempfile, subprocess
    me = os.path.abspath(__file__)
    t = tempfile.mkdtemp(prefix='d2t-')
    ok = True
    def w(n, c):
        p = os.path.join(t, n); io.open(p, 'w', encoding='utf-8').write(c); return p
    def call(md, out, *extra):
        return subprocess.call([sys.executable, me, md, out] + list(extra),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("M8 自证 —— 生成 / --check / 缺 source / 无 front matter / 手改产物\n")
    # 🚨 2026-09-14 CI 首次在**干净 runner** 上跑就揪出来的：
    #   本脚本按 ADR-0008（运行时零第三方依赖）把「没有 PyYAML」正确降级为 UNABLE(rc=2)，
    #   **但自证不认这个降级**——它对正例一律「期望 0」，于是在没装 PyYAML 的环境里
    #   7 个用例全红。⭐ 这正是 ADR-0013 那条老教训的复发：**跳过被当成了失败**。
    #   ⛔ 「跑不了」证明不了任何事，既不算通过，也不该算失败。
    #   ⚠️ 本机装了 PyYAML，所以这一形状**在本地永远看不见** —— 它只在干净环境暴露。
    if yaml is None:
        print("  ⊘ 跳过 7 条依赖 PyYAML 的用例：本环境无 PyYAML（ADR-0008 允许降级为 UNABLE）")
        print("     ⛔ 跳过不是通过 —— 这 7 条在本环境**证明不了任何事**；")
        print("     ⭐ 要覆盖它们，请在装有 PyYAML 的环境或 CI 里跑。")
        print("\n✅ 自证通过（含 7 条因缺 PyYAML 而跳过；⛔ 跳过≠通过）")
        return 0
    g = w('DESIGN.md', _GOOD); out = os.path.join(t, 'tokens.json')
    cases = [("正例：生成成功", call(g, out), 0),
             ("正例：刚生成完 --check 必须一致", call(g, out, '--check'), 0)]
    io.open(out, 'a', encoding='utf-8').write("\n")
    cases.append(("反例①：手改产物后 --check 必须红", call(g, out, '--check'), 1))
    cases.append(("反例②：有令牌但缺 source", call(w('ns.md', _NO_SOURCE), os.path.join(t, 'b.json')), 1))
    cases.append(("反例③：没有 front matter → 报 2", call(w('nf.md', _NO_FM), os.path.join(t, 'c.json')), 2))
    cases.append(("反例④：front matter 里一个令牌都没有", call(w('em.md', _EMPTY), os.path.join(t, 'd.json')), 1))
    cases.append(("反例⑤：缺 ## Known Gaps（诚实缺口）", call(w('ng.md', _NO_GAPS), os.path.join(t, 'e.json')), 1))
    cases.append(("反例⑥：缺 ## Iteration Guide（怎么往下扩）", call(w('ni.md', _NO_ITER), os.path.join(t, 'f.json')), 1))
    cases.append(("反例⑦：DESIGN.md 不存在 → 报 2", call(os.path.join(t, 'nope.md'), out), 2))
    for name, got, want in cases:
        gd = got == want; ok &= gd
        print("  %s %-38s 期望 %d 实得 %d" % ("✅" if gd else "❌", name, want, got))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修"))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    if '--self-test' in sys.argv: sys.exit(_self_test())
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2: print(__doc__); sys.exit(2)
    sys.exit(run(args[0], args[1], '--check' in sys.argv))
