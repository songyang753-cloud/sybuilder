# -*- coding: utf-8 -*-
"""附件 A 的 FR/NFR 解析 —— reconcile-gate 与 prd_completeness_check **共用**。

═══ 为什么必须共用 ═══
2026-08-31 拿真 PRD（`docs/PRD-v2.md`，115 条 FR）实跑，两处各写各的正则，
对**同一段落**给出互相矛盾的结论：

  · `prd_completeness_check`：`re.findall(r'F-\\d+', seg)` —— **太松**。
    附件 A 里随便有一句「本功能与 F-20 无关」也算 F-20 有验收标准。判 25/25 全齐。
  · `reconcile-gate.frs()`：`^##\\s*(N?FR)` —— **太紧**。只认二级标题，
    而模板里 FR 虽写作 `##`、真 PRD 写在 `###`，于是判 25 个功能**全部没有验收标准**。

用户同时拿到「齐全」和「全缺」两个结论，谁都没提对方可能不同意 ——
**这正是本 SOP 自己反复批判的「两处各写各的」，出现在它自己的门禁之间。**

═══ 统一判据 ═══
「某功能有验收标准」= 附件 A 里存在一条 **FR/NFR 标题**（`##`~`####` 任意层级），
且其「所属」字段指向该功能。松紧都不取，取**契约本身**。
"""
import re

# ⭐ 判据锚在**结构**上，不锚在 markdown 层级上。
# 起因：同一个 skill 里 FR 有三种写法并存 ——
#   模板 `prd-complete.md`：`## FR-011　所属 F-01　MUST`
#   真 PRD      ：`### FR-101　所属 F-01　MUST`
#   本 skill 自证夹具     ：`FR-011 所属 F-01。`（纯文本，连 # 都没有）
# 锁死任一层级都会把另外两种合规写法判成不合规。真正的契约是
# 「**有一条带编号的 FR，并声明了它所属哪个功能**」，与排版无关。
FR_DECL = re.compile(r'^[\s>#*\-|]*((?:N?FR)-[\w-]*\d+)([^\n]*)$', re.M)
# 所属值优先按已知形态取，取不到再退回「第一个非空白串」并剥掉尾随标点
# （夹具里写的是 `所属 F-01。`，直接 \S+ 会把句号一起吃进去 → 'F-01。' ≠ 'F-01'）。
OWNER = re.compile(r'所属\s*(F-\d+|全局|\S+)')
PUNCT = '。，、；：!！?？.,;:)）]】》'
# ⚠️ 必须容忍装饰：真 PRD 写的是 `- **AC-1** …`，而原正则要求 `- AC-1` 紧邻。
#    结果 `ac_ids` 在真文档上**返回空列表** —— 于是 G2 那道名为
#    「验收标准 → demo」的对账门，**从来没有对过一条验收标准**，还一直报绿。
#    ⭐ 本模块的自证有 6 项，没有一项测 AC 解析：**没被测到的解析器会安静地返回空**。
AC_ITEM = re.compile(r'^\s*[-*]\s*[`*_]{0,2}(AC-\d+)', re.M)


def appendix(text, start='# 附件 A', end='# 附件 B'):
    """截出附件段。**起始**标记不存在才返回 None（≠ 空段，调用方要能分辨）。

    ⚠️ 2026-09-04 修：原实现要求**结束标记也存在**，否则整段返回 None。
    于是「附件 A 是最后一节」（小项目、`--only` 单跑、或只交了附件 A 的 PRD）
    → `appendix()` 恒 None → `ac_ids()` 把 None 塌成 `[]`
    → **G2 的 AC 集合恒空，那道名为「验收标准 → demo」的门一条 AC 都没对过，还报绿**。

    ⭐ 这与 09-03 修的 `AC_ITEM` 装饰问题是**同一形态、低一层**：
    **解析器在"找不到"时安静地返回空，而空在下游看起来就是"没有缺口"。**
    ⭐⭐ 更值得记的是：本函数的 docstring 从第一天就写着
    「None ≠ 空段，调用方要能分辨」，而调用方第一行就是 `appendix(text) or ''`
    ——**契约写对了，执行方立刻把它抹平了**。
    """
    try:
        i = text.index(start)
    except ValueError:
        return None                      # 连附件 A 都没有 —— 这才是真的「没有」
    try:
        j = text.index(end, i)
    except ValueError:
        j = len(text)                    # 附件 A 是最后一节，合法
    return text[i:j]


def fr_owners(text, seg=None):
    """→ {FR编号: 所属(F-xx / 全局 / None)}。seg 给了就只在该段里找。

    两趟：先认编号（不因为没写「所属」就丢掉这条 FR —— 下游 G2 要用全量编号），
    再在**同一行内**找所属。跨行不算，否则相邻条目的所属会串味。"""
    s = seg if seg is not None else (appendix(text) or '')
    out = {}
    for m in FR_DECL.finditer(s):
        o = OWNER.search(m.group(2))
        val = o.group(1).rstrip(PUNCT) if o else None
        # ⚠️⚠️ 2026-09-04：**后面一次没写所属的提及，不许覆盖前面已声明的所属。**
        #    起因：同一个 FR 在附件 A 里通常出现两次 —— 标题（带「所属 F-xx」）
        #    和**可追溯矩阵的表格行**（不带）。矩阵把 FR 放第一列时
        #    （`| FR-011 | F-01 | … |`，完全自然的写法）正则的 `^[\s>#*\-|]*`
        #    前缀正好吃得到，于是后一次把前一次**抹成 None**。
        #    后果：`features_with_ac` 返回空集 →
        #      · `prd_completeness_check` 对一份**完整**的 PRD 报「附件 A 未覆盖」
        #      · G2 的 AC 归属对账同样静默降级
        #    ⭐ 官方模板只是**靠列序侥幸避开**（它把 FR 放第三列，前缀吃不到）——
        #      一个靠列序才成立的判据不叫成立。
        #    ⭐⭐ 这与本模块一直在治的「提一句就算数」是同一家族的反面：
        #      **提一句就把已经声明的抹掉。**
        if m.group(1) in out and val is None:
            continue
        out[m.group(1)] = val
    return out


def ac_ids(text, seg=None):
    s = seg if seg is not None else (appendix(text) or '')
    return AC_ITEM.findall(s)


def ac_pairs(text, seg=None):
    """→ [(FR编号, AC编号), …]，**带归属**。

    ⚠️ 为什么要带归属：`AC-1` 这个记号在每条 FR 下都会重复出现。
    只收全局 `AC-n` 集合的话，任意一个场景标了 `AC-3`，
    **所有 FR 的 AC-3 就都算被覆盖了** —— 那不是对账，是自我安慰。
    """
    s = seg if seg is not None else (appendix(text) or '')
    out, cur = [], None
    for line in s.split('\n'):
        m = re.match(r'^#{1,6}\s*[`*_]{0,2}((?:N?FR)-[\w-]*\d+)', line)
        if m:
            cur = m.group(1); continue
        a = AC_ITEM.match(line)
        if a and cur: out.append((cur, a.group(1)))
    return out


def features_with_ac(text, seg=None):
    """→ 附件 A 里**真的有验收标准**的功能集合（所属为 F-xx 的那些）。"""
    return {v for v in fr_owners(text, seg).values() if v and v != '全局'}


def self_test():
    """反向测试：三种写法都要认，且「只是提到」不算。"""
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(('  ✓ ' if cond else '  ✗ ') + name)
        ok = ok and cond

    two = "# 附件 A\n## FR-011　所属 F-01　MUST\n正文\n# 附件 B"
    three = "# 附件 A\n### FR-101　所属 F-01　MUST\n正文\n# 附件 B"
    mention = "# 附件 A\n本条与 F-01 无关，仅作说明。\n# 附件 B"
    glob_ = "# 附件 A\n## NFR-A11Y-001　所属 全局　MUST\n# 附件 B"

    chk("二级标题的 FR 认得出（模板写法）", features_with_ac(two) == {'F-01'})
    chk("三级标题的 FR 认得出（真 PRD 写法，旧 reconcile-gate 在这里漏判）", features_with_ac(three) == {'F-01'})
    chk("只是**提到** F-01 不算有验收标准（旧 prd_completeness 在这里误判为覆盖）",
        features_with_ac(mention) == set())
    chk("所属「全局」的 NFR 不算某个功能的验收标准", features_with_ac(glob_) == set())
    chk("NFR-A11Y-001 这类带字母段的编号解析得出", 'NFR-A11Y-001' in fr_owners(glob_))
    plain = "# 附件 A\nFR-011 所属 F-01。NFR-001 P95 ≤500ms。\n# 附件 B"
    chk("纯文本写法认得出（本 skill 自证夹具就是这种，第三种格式）",
        features_with_ac(plain) == {'F-01'})
    chk("所属值尾随的中文句号要剥掉（`所属 F-01。` → F-01，不是 'F-01。'）",
        fr_owners(plain).get('FR-011') == 'F-01')
    # ⚠️ 这条断言的第一版我写反了：曾要求「同一行里第二个 FR 编号也要收进来」。
    #    那会让正文里的**引用**（「详见 FR-011」）被当成声明 —— 正是本文件要治的
    #    「提一句就算数」。正确契约是：**只认行首声明**，行内引用不算。
    chk("行内引用不算声明（`详见 FR-011` 不能算 F-01 有验收标准）",
        features_with_ac("# 附件 A\n本条详见 FR-011 所属 F-01 的说明。\n# 附件 B") == set())
    noowner = "# 附件 A\n### NFR-001　P95 ≤500ms\n# 附件 B"
    chk("没写所属的 FR 仍进编号表(值为 None)，G2 要全量编号",
        fr_owners(noowner).get('NFR-001', 'MISSING') is None)
    chk("附件标记不存在时 appendix 返回 None（≠ 空段）", appendix("没有附件") is None)

    # ⭐ 2026-09-03 补。本模块此前 6 项自证**没有一项测 AC 解析**，
    #    于是 `AC_ITEM` 认不出真 PRD 的 `- **AC-1**` 这件事一直没被发现 ——
    #    `ac_ids` 在真文档上返回空列表，而 G2 那道名为「验收标准 → demo」的门
    #    因此**从来没有对过一条验收标准**，还一路报绿。
    #    ⛔ 没被测到的解析器会安静地返回空，而空列表在下游看起来就是「没有缺口」。
    deco = ("# 附件 A\n### FR-011　所属 F-01　MUST\n"
            "- **AC-1** 加粗写法\n- `AC-2` 反引号写法\n- AC-3 裸写法\n"
            "### FR-021　所属 F-02　MUST\n- **AC-1** 另一条 FR 下的同名编号\n# 附件 B")
    ids = ac_ids(deco)
    chk("AC 带 ** / ` 装饰时也要认得出（真 PRD 就是这么写的）", ids == ['AC-1','AC-2','AC-3','AC-1'])
    pairs = ac_pairs(deco)
    chk("ac_pairs 带归属：AC-1 在两条 FR 下各算一条",
        pairs == [('FR-011','AC-1'),('FR-011','AC-2'),('FR-011','AC-3'),('FR-021','AC-1')])
    chk("行内提到 AC-9 不算一条验收标准",
        'AC-9' not in [a for _, a in ac_pairs("# 附件 A\n### FR-011　所属 F-01\n见 AC-9 的说明\n# 附件 B")])

    # ⭐ 2026-09-04 补。上面那批（09-03）只测了「附件 A 与 B 都在」的文本 ——
    #    于是 `appendix()` 要求**结束标记也存在**这件事同样没被测到。
    #    附件 A 是最后一节（小项目 / `--only` 单跑 / 只交了附件 A）时它整段返回 None，
    #    `ac_ids` 一句 `appendix(text) or ''` 把 None 塌成空 ——
    #    **AC 集合又一次恒空，G2 又一次一条都没对上还报绿。**
    #    ⛔ 与 09-03 那条是同一形态、低一层：解析器找不到时安静返回空。
    #    ⭐⭐ 更该记的是：`appendix` 的 docstring 从第一天就写着「None ≠ 空段，
    #        调用方要能分辨」，而调用方第一行就把这个区别抹平了 ——
    #        **契约写对了不等于有人守它。**
    tail = ("# 附件 A\n### FR-011　所属 F-01　MUST\n- **AC-1** 附件 A 就是最后一节\n")
    chk("附件 A 是最后一节（没有附件 B）时也要解析得出",
        ac_ids(tail) == ['AC-1'] and features_with_ac(tail) == {'F-01'})
    chk("附件 B 之后的内容不许被吃进附件 A",
        ac_ids("# 附件 A\n### FR-011　所属 F-01\n- **AC-1** 甲\n# 附件 B\n- **AC-2** 乙") == ['AC-1'])
    chk("没有附件 A 时仍返回 None（真的「没有」要与「解析不出」可分辨）",
        appendix("# 三、功能清单\n无附件。") is None)

    # ⭐ 2026-09-04：可追溯矩阵把 FR 放第一列时，那一行会被 FR_DECL 匹配到
    #    且不带「所属」—— 此前它**把标题声明的所属抹成 None**，
    #    于是一份完整 PRD 的附件 A 覆盖率归零。
    dup = ("# 附件 A\n### FR-011　所属 F-01　MUST\n- **AC-1** 甲\n"
           "## 可追溯矩阵\n| FR | 功能 | 场景 |\n|---|---|---|\n"
           "| FR-011 | F-01 | f01-empty |\n# 附件 B")
    chk("可追溯矩阵里再提一次 FR（不带所属）不许抹掉标题里声明的所属",
        fr_owners(dup).get('FR-011') == 'F-01' and features_with_ac(dup) == {'F-01'})
    # 🚨 反向：真的从没声明过所属的 FR，仍必须是 None（不许被「修复」成瞎猜一个）
    only_tbl = ("# 附件 A\n## 可追溯矩阵\n| FR | 功能 |\n|---|---|\n"
                "| FR-099 | F-09 |\n# 附件 B")
    chk("只在矩阵里出现、从没声明过所属的 FR 仍是 None（修复不许变成瞎猜）",
        fr_owners(only_tbl).get('FR-099', 'MISSING') is None)
    return ok


if __name__ == '__main__':
    import sys
    # 统一接受 `--self-test`：元门禁 selftest-claim 按这个字面量识别，
    # 无参也跑自证（这个模块除了自证没有别的 CLI 用途）。
    if len(sys.argv) > 1 and sys.argv[1] not in ('--self-test',):
        print(__doc__); sys.exit(2)
    sys.exit(0 if self_test() else 1)
