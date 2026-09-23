#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
格式边界守卫 —— md（中间格式）↔ 飞书/钉钉文档 · Figma · HTML 的信息丢失与遗留。

═══ 它要治的病 ═══
本 skill 的中间格式是 md，而三个终点分别是**飞书文档 / Figma / HTML**。
md「只有内容没有格式」带来的问题**不是排版难看**，而是下面这三类，且都静默：

  ① 写出去丢（md → 远端）
     · 多列表格被**静默压列**（4 列落地成 2 列），返回 success、blocks_added 正常
     · `write` 静默失败：内容缺一大块而不报错（实测同一份输入，第一次丢 24 张表）
     · callout / 折叠块 / 目录块 / @人 / 状态标签在 md 里没有对应物，覆写即毁
     · 图片位置靠偏移推算，而**偏移在同一篇文档内会漂移**

  ② 读不回来（远端 → md）——**最危险的一类，此前完全没有机制**
     链接一旦发出去，别人就会直接在飞书里改。而本地 `prd/` 只是「可 diff 的副本」。
     **没有任何机制检测远端被别人改过** → 下一次本地覆写＝静默覆盖别人的修改，不可恢复。
     这不是"格式丢失"，这是**内容丢失**，而且丢的是别人的工作。

  ③ 表达不了（md 里根本没有的维度）
     · Figma：组件变体矩阵 / AutoLayout 的 hug-fill / constraints / 原型连线 / Dev Mode 标注
     · Figma：**node-id 在重排重建后会失效**，链接看着还在，点进去是别的东西
     · HTML：焦点顺序 / 滚动恢复 / hover 延迟 / reduced-motion 降级后的**实际观感**

═══ 解法（本脚本实现的）═══
**不要把富格式塞进 md** —— md 保持可 diff。改为给每份要外发的 md 配一个 sidecar
`<文件>.sync.json`，记录「结构指纹 + 远端身份 + 上次回读到的远端指纹」。
于是：**格式信息机器可读，内容仍然可 diff，而远端漂移看得见。**

用法:
  doc-sync-guard.py fingerprint <file.md>                     # 打印结构指纹
  doc-sync-guard.py record <file.md> --url <远端链接> --kind feishu|dingtalk|figma
  doc-sync-guard.py check  <file.md> [--readback <回读下来的.md>]
  doc-sync-guard.py figma-anchors <PRD.md>                     # 校验第四章的 Figma 链接双锚
  doc-sync-guard.py lease    <file.md>    # 写前租约：经飞书 CLI 取远端 revision，没动过才许覆写
  doc-sync-guard.py readback <file.md>    # 写后回读：真拿远端内容对结构+刷新基线（写 lastReadbackAt）
  doc-sync-guard.py --self-test
退出码: 0=一致 1=不一致（丢失/漂移） 2=跑不了
"""
import io, os, re, sys, json, time, hashlib, tempfile, subprocess

def read(p):
    try: return io.open(p, encoding='utf-8').read()
    except Exception as e:
        print("UNABLE: 读不到 %s (%s)" % (p, e), file=sys.stderr); sys.exit(2)

def tables(s):
    """返回每张表的列数序列 —— 堵「静默压列」用的就是它。
    引用块里的表（`> | a | b |`）也是真表：推到飞书后同样落成表格、同样会被压列。
    先剥行首 `>` 再认表（2026-09-06 实测：PRD 3.4 的取证声明表写在引用块里，此前对守卫不可见）。
    ⭐ **飞书回读的表是 `<lark-table rows=N cols=M>`，不是管道表** —— 只认管道表的话，
    每一次「推飞书 → 回读」都会报「表数 本地=14 vs 远端=0」这种**假红**。
    而假红的门禁最终会被 `|| true` 绕过或删掉（CI 棘轮那轮的实测教训）。
    ⇒ 两种形态都认，且用 lark-table 自己的 `cols` 属性查压列（比数 `|` 更硬）。"""
    out, lines = [], [re.sub(r'^\s*(?:>\s?)+', '', ln) for ln in s.split('\n')]
    i = 0
    while i < len(lines):
        m = re.search(r'<lark-table\b[^>]*\bcols="(\d+)"', lines[i])
        if m:
            out.append(int(m.group(1))); i += 1; continue
        if lines[i].strip().startswith('|') and i + 1 < len(lines) and \
           re.match(r'^\s*\|[\s\-:|]+\|\s*$', lines[i + 1]):
            out.append(len([c for c in lines[i].strip().strip('|').split('|')]))
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'): i += 1
        else:
            i += 1
    return out

def fingerprint(s):
    heads = re.findall(r'^(#{1,4})\s*(.+?)\s*$', s, re.M)
    tb = tables(s)
    return {
        "sha256": hashlib.sha256(s.encode('utf-8')).hexdigest()[:16],
        "chars": len(s),
        "headings": ["%s %s" % (h[0], h[1]) for h in heads],
        "heading_count": len(heads),
        "table_count": len(tb),
        "table_cols": tb,
        "image_count": len(re.findall(r'!\[[^\]]*\]\(', s)),
        "_raw": s,
        "link_count": len(re.findall(r'(?<!!)\[[^\]]+\]\(', s)),
        # 抽查锚：每章第一个独有长串，用于判「内容缺一大块」
        "anchors": [h[1][:24] for h in heads if h[0] == '#'][:40],
    }

def side(p): return p + ".sync.json"

def cmd_record(p, url, kind, replace_reason=None):
    fp = fingerprint(read(p))

    # ⭐ 正本唯一性（2026-09-16 补）：**登记新远端之前**先问「这份交付是不是已经有正本」。
    #   实证：我给一份已在飞书 wiki 的文档，又在个人知识库另建了一份 docx ⇒ 两个「正本」，
    #   读的人不知道信哪份，而且两边各自往前漂。
    #   ⚠️ 量程说准：它守的是**同一个本地文件被登记到第二个远端**。
    #      两个窗口各写各的本地文件、各推一个远端 —— 文件键状态里没有可比对的东西，
    #      这条**抓不到**，只能靠写入前的人工前置检查（见 iron-rules 28）。⛔ 别把它说成全能。
    if os.path.exists(side(p)):
        try: old_rec = json.loads(io.open(side(p), encoding='utf-8').read())
        except Exception: old_rec = {}
        if old_rec.get('url') and old_rec['url'] != url and not replace_reason:
            print("🔴 %s 已登记正本 %s —— 现在要登记 %s，这会变成两个正本。"
                  % (p, old_rec['url'], url), file=sys.stderr)
            print("   处置：复用既有节点（改它，别新建）。确实要换正本就带理由：", file=sys.stderr)
            print("   `record %s --url <新> --replace-reason \"<为什么旧的作废>\"`" % p, file=sys.stderr)
            return 1

    io.open(side(p), 'w', encoding='utf-8').write(json.dumps({
        "local": p, "kind": kind, "url": url,
        "pushed_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "local_fp": fp, "remote_fp_at_push": None,
        "replaced": replace_reason,
        "note": "remote_fp_at_push 由 check --readback 回填；没有它就无法判断远端是否被人改过",
    }, ensure_ascii=False, indent=1))
    if replace_reason:
        print("⚠️ 覆盖了既有正本登记，理由：%s" % replace_reason)
        print("   ⛔ 旧正本要么删除要么在正文标注作废 —— 留着不说明＝还是两个正本。")
    print("✅ 已记录 %s" % side(p))
    print("⚠️ 下一步必须做回读校验：`doc-sync-guard.py check %s --readback <回读文件>`" % p)
    print("   写入返回 success **不等于**内容进去了 —— 飞书/钉钉都会静默失败。")
    return 0

def diff_fp(a, b, la, lb):
    bad = []
    # 🚨 2026-09-17 实测：飞书 `docx create/update` **不上传本地图片**
    #    （`images_processed` 恒为 0），但它**照样建图块**，回读是 `<image token="" …/>`
    #    —— 文档里一排 100×100 的空框，而 write 返回 success。
    #    「图数相等」查不到这个：本地 md 用 📎 指路时两边都是 0，一致得很。
    #    ⇒ 直接查**远端有没有空 token 的图块**。它只会因为真失败出现。
    _empty_img = len(re.findall(r'<image[^>]*\btoken=""', b.get("_raw", "")))
    if _empty_img:
        bad.append("远端有 %d 个**空图块**（token 为空）—— 图没上传成功但块建了，"
                   "文档里是空白占位框。⇒ 用 `docx upload-image` 单独传" % _empty_img)
    if a["table_count"] != b["table_count"]:
        bad.append("表数 %s=%d vs %s=%d" % (la, a["table_count"], lb, b["table_count"]))
    else:
        for i, (x, y) in enumerate(zip(a["table_cols"], b["table_cols"])):
            if x != y:
                bad.append("第 %d 张表列数 %s=%d vs %s=%d ← **静默压列**的指纹" % (i + 1, la, x, lb, y))
    # 标题比对做格式归一化：飞书往返会把「粗体内嵌代码」拆成 `****` 碎片
    # （`**A `b` c**` 回读成 `**A ****`b`**** c**`），那是排版不是内容 ——
    # 本守卫治的是**内容丢失**（docstring 开头自己写的），⛔ 不许拿排版伪影报「丢失」。
    def _nh(h): return re.sub(r'[\s*`]+', '', h)
    na, nb = {_nh(h) for h in a["headings"]}, {_nh(h) for h in b["headings"]}
    ma = [h for h in a["headings"] if _nh(h) not in nb]
    mb = [h for h in b["headings"] if _nh(h) not in na]
    if ma: bad.append("%s 有而 %s 没有的标题 %d 个：%s" % (la, lb, len(ma), " / ".join(ma[:6])))
    if mb: bad.append("%s 有而 %s 没有的标题 %d 个：%s" % (lb, la, len(mb), " / ".join(mb[:6])))
    if a["image_count"] != b["image_count"]:
        bad.append("图片数 %s=%d vs %s=%d" % (la, a["image_count"], lb, b["image_count"]))
    return bad

def cmd_check(p, readback):
    cur = fingerprint(read(p))
    sp = side(p)
    if not os.path.exists(sp):
        print("UNABLE: 没有 %s —— 这份 md 从未登记过远端，无从判断同步状态" % sp, file=sys.stderr)
        sys.exit(2)
    rec = json.loads(read(sp))
    rc = 0
    print("# 格式边界校验　%s → %s" % (p, rec.get("kind")))
    print("远端：%s" % rec.get("url"))
    if cur["sha256"] != rec["local_fp"]["sha256"]:
        print("ℹ️ 本地自上次推送后已修改（%d → %d 字符）" % (rec["local_fp"]["chars"], cur["chars"]))
    if readback:
        rb = fingerprint(read(readback))
        lost = diff_fp(cur, rb, "本地", "远端")
        if lost:
            rc = 1
            print("🔴 写入丢失（本地有、远端没有 / 结构对不上）：")
            for x in lost: print("   · %s" % x)
            print("   → 重写一遍再回读。**判据不能只看有没有报错**：write 会返回 success 而内容缺一大块。")
        else:
            print("✅ 结构一致：标题 %d · 表 %d（列数逐张一致）· 图 %d"
                  % (rb["heading_count"], rb["table_count"], rb["image_count"]))
        prev = rec.get("remote_fp_at_push")
        if prev and prev["sha256"] != rb["sha256"]:
            same_local = (cur["sha256"] == rec["local_fp"]["sha256"])
            if same_local:
                rc = 1
                print("🔴🔴 **远端被别人改过**（本地未动，而远端指纹与上次推送时不同）")
                print("   → **绝对不许直接覆写**。先把远端改动读下来合并进本地，再推。")
                print("   这类丢失不是格式问题，是把别人的工作静默删掉，且不可恢复。")
            else:
                print("⚠️ 本地与远端都变了 —— 需要人工合并，不许单向覆盖")
        rec["remote_fp_at_push"] = rb
        rec["checked_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
        io.open(sp, 'w', encoding='utf-8').write(json.dumps(rec, ensure_ascii=False, indent=1))
    else:
        print("⚠️ 未提供 --readback：**只校验了本地，没有校验远端**。")
        print("   这不是「通过」——远端是否收全、是否被人改过，本次没有验。")
    return rc

def cmd_figma(p):
    """第四章的 Figma 链接必须**双锚**：node-id + 图层名。

    node-id 在 Figma 里重排/重建后会失效，而链接看起来完好 —— 点进去是空的或是别的东西。
    图层名（`F-01/pc/empty`）是语义锚，重建后仍能重新解析出 node-id。
    ⛔ 状态段用**英文 slug**——写「空态」会让 G3 的三元键对账全部失配。
    """
    s = read(p)
    rows = re.findall(r'\[([^\]]*?)\]\((https?://[^)]*?figma[^)]*?)\)', s)
    if not rows:
        print("UNABLE: 第四章没有 Figma 链接，无从校验", file=sys.stderr); sys.exit(2)
    bad = []
    for label, url in rows:
        if 'node-id=' not in url:
            bad.append("「%s」缺 node-id" % label)
        if not re.search(r'F-\d+\s*[/／]\s*\S+', label + ' ' + s[max(0, s.index(url) - 200):s.index(url)]):
            if not re.match(r'.*F-\d+', label):
                bad.append("「%s」缺图层名锚（应形如 `F-01/pc/empty`）—— node-id 失效后无法重新定位" % label)
    for x in bad: print("🔴 %s" % x)
    if not bad: print("✅ %d 个 Figma 链接均为双锚（node-id + 图层名）" % len(rows))
    return 1 if bad else 0

# ---------------------------------------------------- 编辑租约（登记册 #4，2026-09-08）
def _feishu_read(ref):
    """经飞书 CLI 取远端 {revision_id, content}。CLI 缺席/失败 → (None, 原因)——UNABLE 不冒充。"""
    import shutil
    if not shutil.which('feishu'):
        return None, "本机没有 feishu CLI"
    def _read(tok):
        try:
            r = subprocess.run(['feishu', 'docx', 'read', tok],
                               capture_output=True, text=True, timeout=90)
            d = json.loads(r.stdout)
            return d if isinstance(d, dict) and 'revision_id' in d else None
        except Exception:
            return None
    m = re.search(r'([A-Za-z0-9]{20,})', ref or '')
    d = _read(m.group(1)) if m else None
    if d is None and ref:
        try:
            r = subprocess.run(['feishu', 'fetch', ref], capture_output=True, text=True, timeout=180)
            tok = json.loads(r.stdout).get('token')
            d = _read(tok) if tok else None
        except Exception:
            d = None
    if d is None:
        return None, "飞书回读失败（token 解析不出或 CLI 报错）"
    return d, None


def _lark_cell(td):
    t = re.sub(r'\n+', ' ', td.strip()).replace('|', '\\|')
    return t.strip()


def _lark2md(src):
    """`feishu fetch` 的 markdown 字段里表是 <lark-table> 包裹 —— 转成 md 表再指纹。
    相邻表之间补空行（BIG-60 实测坑：不补两表并成一张）。"""
    def one(m):
        rows = []
        for tr in re.findall(r'<lark-tr>(.*?)</lark-tr>', m.group(1), re.S):
            tds = [_lark_cell(td) for td in re.findall(r'<lark-td>(.*?)</lark-td>', tr, re.S)]
            rows.append('| ' + ' | '.join(tds) + ' |')
        if not rows:
            return ''
        sep = '|' + '---|' * (rows[0].count('|') - 1)
        return '\n' + rows[0] + '\n' + sep + '\n' + '\n'.join(rows[1:]) + '\n\n'
    return re.sub(r'<lark-table[^>]*>(.*?)</lark-table>', one, src, flags=re.S)


def _feishu_markdown(ref):
    """经 `feishu fetch` 取远端 **markdown**（结构保真的那份）。

    🔴 2026-09-09 实录：`docx read` 的 `content` 字段是**拍平纯文本**（标题表格全没了），
    拿它做结构指纹得到 0 表 + 5 个「幽灵标题」（正文里字面以 `# ` 开头的行）——
    remote_fp_at_push 自 09-08 起记的就是这份垃圾，漂移检测武装的是幽灵基线，
    而真远端（fetch .markdown + lark 表转换后）与本地 195/125 零差异。
    ⛔ 指纹只许打在 markdown 上；拿不到 markdown = UNABLE，不许退回 content。"""
    import shutil
    if not shutil.which('feishu'):
        return None, "本机没有 feishu CLI"
    try:
        r = subprocess.run(['feishu', 'fetch', ref], capture_output=True, text=True, timeout=180)
        md = json.loads(r.stdout).get('markdown')
        if not md:
            return None, "fetch 结果没有 markdown 字段"
        return _lark2md(md), None
    except Exception as e:
        return None, "feishu fetch 失败：%s" % e


def cmd_lease(p):
    """写前租约：远端 revision 与上次回读一致才许覆写。

    治的是 docstring ② 那类：链接发出去后别人在飞书里改了——本地下一次覆写＝
    静默删掉别人的工作。有了 revision 原语（2026-09-08 实测 feishu docx read 暴露
    revision_id，写后递增），漂移从「靠人记得」变成机器判定。
    """
    sp = side(p)
    if not os.path.exists(sp):
        print("UNABLE: 没有 %s —— 先 record 登记远端" % sp, file=sys.stderr); sys.exit(2)
    rec = json.loads(read(sp))
    d, err = _feishu_read(rec.get('doc_token') or rec.get('url') or '')
    if d is None:
        print("UNABLE: %s —— 租约建立不了＝**不许写**（这不是通过）" % err, file=sys.stderr)
        sys.exit(2)
    rev, base = d['revision_id'], rec.get('remote_revision')
    rec['lease_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    if base is None:
        rec['remote_revision'] = rev
        io.open(sp, 'w', encoding='utf-8').write(json.dumps(rec, ensure_ascii=False, indent=1))
        print("✅ 租约基线建立：远端 revision=%s。此后每次写前先跑 lease。" % rev)
        return 0
    if rev != base:
        print("🔴 远端漂移：本地基于 revision=%s，远端已是 %s —— **禁止覆写**。" % (base, rev))
        print("   先把远端改动读下来合并（`feishu docx read`），再 `readback` 刷新基线。")
        print("   这不是格式问题：直接覆写＝把别人的修改静默删掉，不可恢复。")
        return 1
    io.open(sp, 'w', encoding='utf-8').write(json.dumps(rec, ensure_ascii=False, indent=1))
    print("✅ 租约有效：revision=%s 未动，可写。写完必须跑 readback。" % rev)
    return 0


def cmd_readback(p):
    """写后回读：**真拿远端内容**对结构（压列/缺章抓现行），刷新 revision 基线。

    与 `check --readback <文件>` 的差别：那条要人工导出回读文件，这条自己去取——
    「写入返回 success」与「内容进去了」之间的缝，由同一次调用里的真实回读补上。
    产出 contract-manifest 需要的 prd.lastReadbackAt（G7.5 原生三查⑦读它）。
    """
    sp = side(p)
    if not os.path.exists(sp):
        print("UNABLE: 没有 %s —— 先 record 登记远端" % sp, file=sys.stderr); sys.exit(2)
    rec = json.loads(read(sp))
    d, err = _feishu_read(rec.get('doc_token') or rec.get('url') or '')
    if d is None:
        print("UNABLE: %s —— 没回读到＝没验证（这不是通过）" % err, file=sys.stderr)
        sys.exit(2)
    # ⛔ 结构指纹只许打在 markdown 上（`content` 是拍平文本，见 _feishu_markdown 实录）
    md, merr = _feishu_markdown(rec.get('url') or rec.get('doc_token') or '')
    if md is None:
        print("UNABLE: %s —— 拿不到结构保真的 markdown＝没验证（⛔ 不退回拍平文本冒充）" % merr,
              file=sys.stderr)
        sys.exit(2)
    rb = fingerprint(md)
    lost = diff_fp(fingerprint(read(p)), rb, "本地", "远端")
    rec['remote_revision'] = d['revision_id']
    rec['remote_fp_at_push'] = rb
    rec['lastReadbackAt'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    io.open(sp, 'w', encoding='utf-8').write(json.dumps(rec, ensure_ascii=False, indent=1))
    # 签发 receipt（登记册 #3 本地半场）：一次真实回读一张凭据，rawEvidence=sidecar 本身。
    # PF_RECEIPT_ENV=test 只能把凭据降为 test（不解真实上限）——方向安全；默认 live。
    rcpt_path = p + '.receipt.json'
    io.open(rcpt_path, 'w', encoding='utf-8').write(json.dumps({
        'receiptSchema': '1.0',
        'receiptId': 'ER-feishu-%s' % time.strftime('%Y%m%d%H%M%S'),
        'artifactKind': 'feishu-prd',
        'artifactRef': (rec.get('doc_token') or rec.get('url') or '')[:80],
        'nativeVersion': str(d['revision_id']),
        'capabilitiesExercised': ['readback'],
        'observedAt': rec['lastReadbackAt'],
        'adapter': {'name': 'doc-sync-guard.readback', 'version': '1'},
        'rawEvidenceRef': os.path.basename(sp),
        'environment': 'test' if os.environ.get('PF_RECEIPT_ENV') == 'test' else 'live',
    }, ensure_ascii=False, indent=1))
    if lost:
        print("🔴 写入丢失（真实回读对不上）：")
        for x in lost: print("   · %s" % x)
        print("   → 重写再回读。write 返回 success 不等于内容进去了。")
        return 1
    print("✅ 回读一致（revision=%s）。receipt 已签发：%s" % (d['revision_id'], rcpt_path))
    print("   → contract-manifest 填 prd.readbackReceipt=<该文件路径>（G7.5 ⑦ 只认 receipt，裸时间戳不算）")
    return 0


# ------------------------------------------------------------------ M8 自证
BASE = """# 标题
| a | b | c | d |
|---|---|---|---|
| 1 | 2 | 3 | 4 |

## 二章
正文。

## 三章
| x | y |
|---|---|
| 1 | 2 |
"""

def self_test():
    t = tempfile.mkdtemp(prefix="dsg-")
    def w(n, c):
        p = os.path.join(t, n); io.open(p, 'w', encoding='utf-8').write(c); return p
    def run(*a): return subprocess.call([sys.executable, os.path.abspath(__file__)] + list(a),
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-34s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    p = w('a.md', BASE)
    run('record', p, '--url', 'https://x', '--kind', 'feishu')
    case("正例：远端与本地一致", run('check', p, '--readback', w('rb.md', BASE)), 0)
    # 压列
    squashed = BASE.replace("| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |",
                            "| a | b |\n|---|---|\n| 1 | 2 |")
    p2 = w('b.md', BASE); run('record', p2, '--url', 'https://x', '--kind', 'feishu')
    case("反例：4 列被静默压成 2 列", run('check', p2, '--readback', w('rb2.md', squashed)), 1)
    # 缺一大块
    p3 = w('c.md', BASE); run('record', p3, '--url', 'https://x', '--kind', 'feishu')
    case("反例：远端缺一整章（write 静默失败）",
         run('check', p3, '--readback', w('rb3.md', BASE.split('## 三章')[0])), 1)
    # ⭐ 正本唯一性（2026-09-16）：同一本地文件被登记到第二个远端 = 两个正本
    p5 = w('dup.md', BASE)
    case("正例：首次登记远端", run('record', p5, '--url', 'https://one', '--kind', 'feishu'), 0)
    case("正例：同一远端重复登记（改完再推，常规操作）",
         run('record', p5, '--url', 'https://one', '--kind', 'feishu'), 0)
    case("反例：同一文件登记到第二个远端（造出两个正本）",
         run('record', p5, '--url', 'https://two', '--kind', 'feishu'), 1)
    case("正例：换正本写明理由则放行",
         run('record', p5, '--url', 'https://two', '--kind', 'feishu',
             '--replace-reason', '旧节点权限收回，已在正文标注作废'), 0)
    # ⚠️ 这条守不到「两个窗口各写各的本地文件、各推一个远端」——文件键状态里没有可比对的东西。
    #    ⛔ 不给它配一个假装能守的用例；那条只能靠 iron-rules 28 的写入前人工检查。

    # 远端漂移
    p4 = w('d.md', BASE); run('record', p4, '--url', 'https://x', '--kind', 'feishu')
    run('check', p4, '--readback', w('rb4.md', BASE))                    # 建立基准
    case("反例：远端被别人改过（本地未动）",
         run('check', p4, '--readback', w('rb5.md', BASE + "\n别人加的一段。\n")), 1)
    # ⭐ 2026-09-02 变异审计补：这三条判据变异后自证仍全绿 —— 从没被证明会工作。
    #    ⚠️ 反例要**只制造那一个缺口**：压列/缺章的用例会同时触发别的判据，
    #    所以下面三条都在 BASE 上「只挪走一样东西」。
    p5 = w('f.md', BASE); run('record', p5, '--url', 'https://x', '--kind', 'feishu')
    case("反例：远端少了一整张表（表数不一致）",
         run('check', p5, '--readback', w('rb6.md',
             BASE.replace("| x | y |\n|---|---|\n| 1 | 2 |\n", ""))), 1)
    p6 = w('g.md', BASE + "\n![图](a.png)\n")
    run('record', p6, '--url', 'https://x', '--kind', 'feishu')
    case("反例：远端图片少了一张（图片数不一致）",
         run('check', p6, '--readback', w('rb7.md', BASE)), 1)

    # 引用块里的表也是表（2026-09-06：PRD 取证声明表写在引用块里，压列此前对守卫不可见）
    QBASE = BASE + "\n> | q1 | q2 | q3 |\n> |---|---|---|\n> | a | b | c |\n"
    p7 = w('h.md', QBASE); run('record', p7, '--url', 'https://x', '--kind', 'feishu')
    case("正例：引用块表原样回读", run('check', p7, '--readback', w('rb8.md', QBASE)), 0)
    case("反例：引用块里的表被静默压列",
         run('check', p7, '--readback', w('rb9.md',
             QBASE.replace("> | q1 | q2 | q3 |\n> |---|---|---|\n> | a | b | c |",
                           "> | q1 | q2 |\n> |---|---|\n> | a | b |"))), 1)

    # 标题格式往返伪影不许报丢失；标题文字真变了必须照红（2026-09-06）
    HBASE = BASE + "\n## 四章 **Hermes `memory` 工具**\n"
    p8 = w('i.md', HBASE); run('record', p8, '--url', 'https://x', '--kind', 'feishu')
    case("正例：粗体内嵌代码的标题回读碎裂",
         run('check', p8, '--readback', w('rb10.md',
             HBASE.replace("**Hermes `memory` 工具**", "**Hermes ****`memory`**** 工具**"))), 0)
    case("反例：标题文字真的变了",
         run('check', p8, '--readback', w('rb11.md', HBASE.replace("## 二章", "## 二章改"))), 1)

    # figma-anchors：第四章的设计稿链接必须 node-id + 图层名**双锚**
    PRD_OK = ("# PRD\n## 四、详细设计\n"
              "| 页面 | 设计稿 | 逻辑 |\n|---|---|---|\n"
              "| a | [F-01 稿](https://figma.com/design/k/x?node-id=1-2) `F-01/pc/empty` | - x |\n")
    case("figma-anchors 正例：node-id + 图层名双锚齐", run('figma-anchors', w('pa.md', PRD_OK)), 0)
    # ⚠️ 反例造错过一次：判据认「标签里含 F-xx 也算有图层名锚」，
    #    而我的标签写的是「F-01 稿」—— 拿掉反引号那段仍然合规。
    #    要制造这个缺口，标签与上文都不能出现 F-xx。
    case("反例：只有 node-id，缺图层名锚",
         run('figma-anchors', w('pb.md',
             "# PRD\n## 四、详细设计\n| 页面 | 设计稿 | 逻辑 |\n|---|---|---|\n"
             "| a | [设计稿](https://figma.com/design/k/x?node-id=1-2) | - x |\n")), 1)
    case("反例：链接缺 node-id",
         run('figma-anchors', w('pc.md', PRD_OK.replace("?node-id=1-2", ""))), 1)

    # lease/readback：假 feishu 挡在 PATH 最前（⛔ 探针不打真网——真 CLI 排在后面轮不到）
    bindir = os.path.join(t, 'bin'); os.makedirs(bindir, exist_ok=True)
    fake_out = os.path.join(t, 'fake-feishu-out.json')
    fake_fetch = os.path.join(t, 'fake-feishu-fetch.json')
    # ⚠️ 假 CLI 必须复现真 CLI 的**格式契约**（09-09 实录：旧夹具让 content 装着
    #    结构化 md，而真 `docx read` 的 content 是拍平文本 ⇒ 自测绿、生产指纹全是垃圾——
    #    「夹具必须复现前置条件」的整形实例）。现按子命令分发：fetch → markdown JSON。
    io.open(os.path.join(bindir, 'feishu'), 'w', encoding='utf-8').write(
        '#!/bin/sh\nif [ "$1" = "fetch" ]; then cat "$FAKE_FEISHU_FETCH"; '
        'else cat "$FAKE_FEISHU_OUT"; fi\n')
    os.chmod(os.path.join(bindir, 'feishu'), 0o755)
    envF = dict(os.environ, PATH=bindir + ':/usr/bin:/bin', FAKE_FEISHU_OUT=fake_out,
                FAKE_FEISHU_FETCH=fake_fetch,
                PF_RECEIPT_ENV='test')   # 假 CLI 签的凭据必须是 test —— 不许冒充 live
    envNone = dict(os.environ, PATH='/usr/bin:/bin')          # 无 feishu 的世界
    def rune(env, *a): return subprocess.call([sys.executable, os.path.abspath(__file__)] + list(a),
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    def _flatten(md):
        # 模拟真 `docx read` 的拍平：标题记号、表格线全丢，只剩文本
        return re.sub(r'[#|\-]+', ' ', md)
    def fake(rev, content, fetch_md=None):
        io.open(fake_out, 'w', encoding='utf-8').write(
            json.dumps({'revision_id': rev, 'content': _flatten(content)}))
        io.open(fake_fetch, 'w', encoding='utf-8').write(
            json.dumps({'token': 'T', 'markdown': content if fetch_md is None else fetch_md}))
    pl = w('lease.md', BASE); run('record', pl, '--url', 'https://x/docx/AAAABBBBCCCCDDDDEEEE1111', '--kind', 'feishu')
    fake(5, BASE)
    case("lease：基线建立 → 0", rune(envF, 'lease', pl), 0)
    case("lease：revision 未动 → 0（可写）", rune(envF, 'lease', pl), 0)
    fake(7, BASE + "别人加的\n")
    case("反例 lease：远端漂移 → 1（禁止覆写）", rune(envF, 'lease', pl), 1)
    case("反例 readback：远端 4 列被压成 2 列 → 1", (fake(8, BASE.replace(
        "| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |",
        "| a | b |\n|---|---|\n| 1 | 2 |")), rune(envF, 'readback', pl))[1], 1)
    fake(8, BASE)
    case("readback：真实回读一致 → 0 且刷新基线", rune(envF, 'readback', pl), 0)
    _rec = json.loads(read(side(pl)))
    case("readback 写了 lastReadbackAt（G7.5 ⑦ 的原料）",
         0 if (_rec.get('lastReadbackAt') and _rec.get('remote_revision') == 8) else 1, 0)
    # 🚨 2026-09-09（独立复核揪出）：这条用例依赖 `scripts/receipt-check.py`，
    #   而该文件当时**尚未提交** ⇒ committed 的测试依赖 uncommitted 的文件，
    #   于是**任何全新 clone 上本脚本自证都是红的**（本机绿，别人机器红）。
    #   ⭐ 对一个要分发的 skill，「只在作者机器上绿」等于没绿。
    #   ⇒ 按本 SOP 自己的结果语义：**能力/依赖缺失是 UNABLE，不是 FAIL**。
    #     依赖在场就照常验（不降低强度）；不在场就明说跳过了什么，⛔ 不折成通过、
    #     也不冒充失败——两者的诊断完全不同。
    _rcheck = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'receipt-check.py')
    if os.path.isfile(_rcheck):
        case("readback 签发的 receipt 过 receipt-check 校验",
             subprocess.call([sys.executable, _rcheck, pl + '.receipt.json'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), 0)
    else:
        print("  ⚠️ UNABLE readback 签发的 receipt 过 receipt-check 校验 —— "
              "缺 scripts/receipt-check.py（未随本脚本一起提供），本条**没验**，不计入通过")
    _rc_env = json.loads(read(pl + '.receipt.json')).get('environment')
    case("假 CLI 环境下签发的凭据是 test 不是 live（不冒充实弹）",
         0 if _rc_env == 'test' else 1, 0)
    # 09-09 新形状：远端表以 <lark-table> 包裹（真 fetch 的实际格式）→ 转换后必须判一致
    _lark_tbl = ("<lark-table><lark-tr><lark-td>a</lark-td><lark-td>b</lark-td>"
                 "<lark-td>c</lark-td><lark-td>d</lark-td></lark-tr>"
                 "<lark-tr><lark-td>1</lark-td><lark-td>2</lark-td>"
                 "<lark-td>3</lark-td><lark-td>4</lark-td></lark-tr></lark-table>")
    fake(8, BASE, fetch_md=BASE.replace(
        "| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |", _lark_tbl))
    case("readback：远端表是 lark-table 格式 → 转换后一致 → 0", rune(envF, 'readback', pl), 0)
    # fetch 无 markdown 字段 → UNABLE(2)，⛔ 不许退回拍平 content 冒充指纹
    io.open(fake_fetch, 'w', encoding='utf-8').write('{}')
    case("UNABLE：fetch 无 markdown → 2（不拿拍平文本冒充）", rune(envF, 'readback', pl), 2)
    fake(8, BASE)
    case("lease：漂移后经 readback 刷新基线 → 再 lease 恢复 0", rune(envF, 'lease', pl), 0)
    case("UNABLE：无 feishu CLI → 2（不冒充通过）", rune(envNone, 'lease', pl), 2)
    case("UNABLE：lease 无 sidecar → 2", rune(envF, 'lease', w('nolease.md', BASE)), 2)

    # 无 sidecar 必须报 2
    case("未登记过远端 → 报 2 不报 0", run('check', w('e.md', BASE)), 2)
    # figma 双锚
    case("Figma 链接缺 node-id → 红",
         run('figma-anchors', w('f.md', "| p | [F-01 稿](https://figma.com/file/x) | l |")), 1)
    case("Figma 双锚齐全 → 绿",
         run('figma-anchors', w('g.md', "| p | [F-01/pc/empty](https://figma.com/file/x#node-id=1-2) | l |")), 0)
    case("文件不存在 → 报 2", run('fingerprint', os.path.join(t, 'nope.md')), 2)
    print("\n%s" % ("✅ 格式边界守卫会出声" if ok else "❌ 自证失败"))
    return 0 if ok else 1

if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    if '--self-test' in sys.argv: sys.exit(self_test())
    # ⚠️ 只滤掉 `--flag` 而留下它的值，会让值被当成位置参数（实测：record 拿到 4 个位置参数
    #    而不是 2 个，于是 sidecar 根本没建，随后每个用例都报 2）。必须成对剥离。
    # ⚠️ 未知 `--flag` 必须报错：静默丢弃会让门禁只跑一半而照样报绿（见 _argv.py）
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from _argv import reject_unknown
    reject_unknown({'--url', '--kind', '--readback', '--replace-reason', '--flag', '--self-test', '--json'},
        "本工具：doc-sync-guard.py <子命令> <file> [--url/--kind/--readback ...]")
    OPTS = {'--url', '--kind', '--readback', '--replace-reason'}
    argv, a, kv = sys.argv[1:], [], {}
    i = 0
    while i < len(argv):
        if argv[i] in OPTS and i + 1 < len(argv):
            kv[argv[i]] = argv[i + 1]; i += 2; continue
        if argv[i].startswith('--'): i += 1; continue
        a.append(argv[i]); i += 1
    def opt(n): return kv.get(n)
    if not a: print(__doc__); sys.exit(2)
    c = a[0]
    if c == 'fingerprint' and len(a) == 2:
        print(json.dumps(fingerprint(read(a[1])), ensure_ascii=False, indent=1)); sys.exit(0)
    if c == 'record' and len(a) == 2 and opt('--url'):
        sys.exit(cmd_record(a[1], opt('--url'), opt('--kind') or 'unknown', opt('--replace-reason')))
    if c == 'check' and len(a) == 2: sys.exit(cmd_check(a[1], opt('--readback')))
    if c == 'figma-anchors' and len(a) == 2: sys.exit(cmd_figma(a[1]))
    if c == 'lease' and len(a) == 2: sys.exit(cmd_lease(a[1]))
    if c == 'readback' and len(a) == 2: sys.exit(cmd_readback(a[1]))
    print(__doc__); sys.exit(2)
