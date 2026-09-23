#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读者分区门禁 —— 交付文档的**正文**是给人看的，⛔ 不装我的工作日志。

═══ 为什么 ═══
2026-09-17 用户看 v8 竞品报告：「做的太差了」。拆开看，正文里写满了
门禁条数、收敛轨迹 23→0、需求编号、`cNN.md` 内部路径、我自己的错误清单——
**那是我的工作日志，不是竞品分析**。读者（产品总监）一条都用不上。

口径（用户原话）：
  · 正文部分就是给人看的
  · 附件部分是给人和 AI 编程看的
⇒ 不是「不许有技术细节」，而是**技术细节归附件，正文归人**；
  而**过程日志两边都不进**——它属于 .proposals / commit message。

═══ 这道门能做什么、不能做什么 ═══
✅ 能查**机械可判的混入**：内部文件路径、过程数字、自检编号、把读者支出去的指路。
⛔ 查不了「写得好不好读」「结论站不站得住」——那一层只有人读得出来。
   ⚠️ 判据说明里必须带上这句，否则它会被当成「已经有门在管文风了」。

口径真源：`spec/_audience.json`，⛔ 本脚本不硬编码规则。

用法:
  audience-gate.py <交付文档.md> [--attachments-from '## 附件']
  audience-gate.py --self-test
退出码: 0=正文干净 1=正文混入了机器味内容 2=跑不了
"""
import io, os, re, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import _iter_headings   # noqa: E402  —— 标题解析的唯一正本

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, 'spec', '_audience.json')


def _read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except Exception as e:
        print("UNABLE: 读不到 %s (%s)" % (p, e), file=sys.stderr)
        sys.exit(2)


def split_zones(text, marker=None):
    """切成（正文, 附件）。

    ⚠️ 起点不一定是文件开头：模板类文档前面有一整段**写作指引**（「动笔前先判断」
    「写作铁律」「目录」），那是给**写文档的人**看的，引用 skill 内部路径完全正当。
    拿它去查「正文有没有机器味」是**量错了对象**——实测：本门第一次跑 PRD 模板就
    因为指引段里的 `references/…` 报红，连它自己新加的那条规则都被自己抓了。
    ⇒ 文档若有显式 `# 正文` 标记，正文从那里起算；没有才从头算。
    """
    # ⛔ 标题解析只许有一个正本（`_section.py`）——手写一份就多一份要单独修的量程。
    #    它认围栏、setext、引用块里的 ATX，这些我手写时一个都想不到。
    lines = text.split('\n')
    body_line = 0
    for ln, _lvl, title in _iter_headings(text):
        if title.strip() in ('正文', '正文部分'):
            body_line = ln + 1
            break
    att_line = None
    for ln, _lvl, title in _iter_headings(text):
        if ln < body_line:
            continue
        t = title.strip()
        hit = (t.startswith(marker.lstrip('# ').strip()) if marker
               else re.match(r'^(?:附件|附录|Appendix)\b', t))
        if hit:
            att_line = ln
            break
    body = '\n'.join(lines[body_line:att_line if att_line is not None else len(lines)])
    att = '' if att_line is None else '\n'.join(lines[att_line:])
    return body, att


# 每条：(键, 正则, 人话说明)。⚠️ 只放**机械可判且低误报**的形状。
def _rules():
    return [
        ('internal-path',
         # ⚠️ 斜杠段必须是**纯 ASCII** 才算路径：`成本/规模` 是中文列名，不是路径。
         #    首版用 `[\w-]+/` —— Python 的 \w 含中文 ⇒ 把列名判成了路径（门在惩罚正确内容）。
         re.compile(r'`[\w./-]*\.md(?:#[^`]*)?`|\bc\d{2}\.md\b'
                    r'|`[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+`'),
         '正文里出现内部文件路径/锚点——读者点不开，这是给我自己看的索引'),
        ('process-log',
         re.compile(r'门禁[^。\n]{0,6}(?:条|道|全绿|退出码)|判据[^。\n]{0,4}条|'
                    r'退出码\s*\d|收敛轨迹|自证用例|第\s*\d+\s*轮|'
                    r'\d+\s*→\s*\d+\s*→\s*\d+'),
         '正文里出现过程日志（门禁条数/收敛轨迹/第几轮）——那是我的工作记录，不是交付内容'),
        ('requirement-numbering',
         re.compile(r'[（(]\s*需求\s*\d+(?:\s*[、,，]\s*\d+)*\s*[）)]'),
         '标题/正文里写了「需求 N」自检编号——那是我对着清单打勾用的'),
        ('deferral',
         re.compile(r'见文末|详见语料|见\s*`[^`]+\.md`|完整.{0,6}清单见'),
         '把读者支出去看别处——正文要自足，图表证据直接放进来'),
    ]


def check(path, marker=None, spec_path=None):
    spec = json.loads(_read(spec_path or SPEC))
    body, att = split_zones(_read(path), marker)
    # ⛔ 三类不算混入：代码块（示例）、HTML 注释（给填写者的提示，渲染后不可见）、
    #    以及模板占位尖括号。⚠️ 模板里给填写者的指引**本来就该是注释**——
    #    它若以正文形态留着，填写者交付时会把它一起交出去。
    scrub = re.sub(r'```.*?```', '', body, flags=re.S)
    scrub = re.sub(r'<!--.*?-->', '', scrub, flags=re.S)
    hits = []
    for key, rx, why in _rules():
        found = [m.group(0)[:40] for m in rx.finditer(scrub)]
        if found:
            hits.append((key, len(found), why, found[:3]))
    print("# 读者分区校验　%s" % os.path.basename(path))
    print("正文 %d 字 ｜ 附件 %d 字（附件是给人 + AI 编程看的，本门只查正文）"
          % (len(body), len(att)))
    if not att:
        print("ℹ️ 没找到附件分节 —— 整篇按正文查")
    for key, n, why, sample in hits:
        print("❌ [%s] %s" % (key, why))
        print("   %d 处，例：%s" % (n, ' ｜ '.join(sample)))
    if not hits:
        print("✅ 正文没有机械可判的机器味混入")
    print("⚠️ 本门**只查机械可判的混入**（内部路径 / 过程数字 / 自检编号 / 把读者支出去）。")
    print("   ⛔ 查不了「写得好不好读、结论站不站得住」——那一层只有人读得出来。")
    print("   口径真源：spec/_audience.json；过程日志的去处：%s"
          % spec.get('processLogGoesTo', {}).get('where', '.proposals/'))
    return 1 if hits else 0


def self_test():
    import tempfile, shutil
    t = tempfile.mkdtemp(prefix='aud-'); ok = True

    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-46s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    def w(name, s):
        p = os.path.join(t, name)
        io.open(p, 'w', encoding='utf-8').write(s); return p

    clean = ("# 竞品分析\n\n## 市场格局\n\nWorkBuddy 功能面最宽，16/20 个功能有实现。\n"
             "它把工作空间放在输入框正下方。\n\n## 附件 A 字段规格\n\n见 `c02.md#功能清单` 的 CAF-001。\n")
    case("正例 正文干净、内部路径只在附件里", check(w('a.md', clean)), 0)

    case("反例 正文引用内部文件路径",
         check(w('b.md', "# 报告\n\n每家的模块图见 `c01.md#产品模块图`。\n")), 1)
    case("反例 正文写门禁条数",
         check(w('c.md', "# 报告\n\n本轮门禁 52 条判据全绿，退出码 0。\n")), 1)
    case("反例 正文写收敛轨迹",
         check(w('d.md', "# 报告\n\n收敛轨迹 23 → 16 → 0，一共跑了 17 轮。\n")), 1)
    case("反例 标题里写需求自检编号",
         check(w('e.md', "# 报告\n\n## 三 与 PRD 同构的图与表（需求 4、11）\n\n内容。\n")), 1)
    case("反例 把读者支去看别处",
         check(w('f.md', "# 报告\n\n完整的 DIFF 清单见 `differentiation.md`。\n")), 1)

    # ⭐ 附件里出现这些**不算**——附件是给人 + AI 编程看的
    case("正例 同样的内部路径写在附件里 → 放行",
         check(w('g.md', "# 报告\n\n正文一句话结论。\n\n## 附件 D 字段规格\n\n"
                         "字段来源 `c01.md#功能清单`，见 AF-001 行。\n")), 0)
    # 代码块里的路径是示例
    case("正例 中文列名含斜杠 → 不当成路径（门不许惩罚正确内容）",
         check(w('j.md', "# 报告\n\n| ID | `成本/规模` |\n|---|---|\n| F-001 | 中 |\n")), 0)
    case("正例 HTML 注释里的填写提示 → 不误伤（渲染后不可见）",
         check(w('i.md', "# 报告\n\n结论。\n\n<!-- 填写提示：语义见 `delivery-pipeline.md` -->\n")), 0)
    case("正例 代码块里的路径是示例 → 不误伤",
         check(w('h.md', "# 报告\n\n结论。\n\n```\ncat c01.md\n```\n")), 0)

    shutil.rmtree(t, ignore_errors=True)
    print("\n%s" % ("✅ 读者分区门禁自证通过" if ok else "❌ 自证失败"))
    return 0 if ok else 1


def _main_guarded(fn):
    """崩溃 ≠ 有发现：意外异常一律退 2，⛔ 不许和「有发现」共用退出码 1。"""
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 工具自身异常（不是「有发现」）：%s: %s"
              % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print(__doc__); sys.exit(2)
    mk = None
    if '--attachments-from' in sys.argv:
        mk = sys.argv[sys.argv.index('--attachments-from') + 1]
    def _entry():
        sys.exit(check(args[0], mk))

    _main_guarded(_entry)
