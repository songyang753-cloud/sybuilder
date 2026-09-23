#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个人飞书写入正本：官方 `lark-cli --as user` 写入，Markdown/XML 双回读。

═══ 它治的病 ═══
飞书写入的坑全是「跑起来才知道、光看命令看不出」的（记忆里 reference_feishu_docx_push 记了一堆）：
  · 旧第三方 CLI 的覆盖/图片行为不能代表官方 lark-cli
  · 图片必须由 `![说明](<@./相对路径>)` 变成非空远端图片实体
  · 像 HTML 标签的占位符 `<Button>`/`<M>` 被**吞掉**
  · 纯文本方括号 `[取证]` 有被当成空链接的风险
  · 文档以表格结尾时**尾部校验必然假红**
⇒ 「写完了」≠「内容对」。本模块把**写入 + 回读校验**变成一条可复用调用，
   ⛔ 不许各处再手搓一份 verify（手搓的那份下次就漏一种坑）。

═══ 它验不了什么（诚实边界）═══
⛔ 验不了正文**写得好不好、结论对不对**——那是 audience-gate + 人读的事。
⛔ 本模块只保证「本地有的语义单元，飞书上没被静默丢」，不保证语义没被改坏。

用法（作为库）:
  from _feishu import create_and_verify, verify_readback
  tok, ok, issues = create_and_verify("标题", "report.md")
用法（自证）: _feishu.py --self-test
退出码（自证）: 0=通过 1=失败
"""
import io, os, re, sys, json, subprocess, tempfile


def _table_seps(md: str) -> int:
    """源 markdown 里的表格数 ≈ 分隔行（|---|）数。"""
    return sum(1 for ln in md.splitlines()
               if ln.strip().startswith('|') and set(ln.strip()) <= set('|-: '))


def _strip_fences(md: str) -> str:
    """剥掉 ``` 围栏代码块（mermaid/代码）。
    ⛔ 2026-09-18 教训:mermaid 里的 `subgraph X["③ 能力层"]` 含 [xxx],
       飞书把 mermaid **原生渲染成图**后源文本消失 ⇒ _brackets 误判「标记丢失」假红。
       围栏内的 [] 不是散文标记、渲染后本就不在回读里,必须两侧对称剥掉再数。"""
    return re.sub(r'```.*?```', '', md, flags=re.DOTALL)


def _brackets(md: str) -> dict:
    """自动收集纯文本方括号标记 [xxx]（非链接：后面不跟 `(`）的计数。
    这类标记最容易被飞书当空链接吞掉，是回读必查项。⚠️ 传入前先 _strip_fences。"""
    out = {}
    for m in re.finditer(r'(?<!\!)\[([^\[\]\n]{1,12})\](?!\()', md):
        k = '[' + m.group(1) + ']'
        out[k] = out.get(k, 0) + 1
    return out


def verify_readback(source_md: str, readback_md: str, extra_markers=None):
    """纯函数：比源 md 与飞书回读 md，列出被静默丢掉的东西。
    返回 (ok, issues)。飞书回读会把表格序列化成 <lark-table>，所以表格按两种口径归一比。"""
    issues = []
    # ① 方括号标记逐个对账（先剥围栏:mermaid 渲染成图后源文本不在回读里,不算丢失）
    src_b, rb_b = _brackets(_strip_fences(source_md)), _brackets(_strip_fences(readback_md))
    for k, n in src_b.items():
        got = rb_b.get(k, 0)
        if got < n:
            issues.append("标记 %s 本地 %d → 飞书 %d（少了 %d）" % (k, n, got, n - got))
    # ② 表格数：源的 |---| 分隔行数 应 = 飞书的 <lark-table> 数
    src_t = _table_seps(source_md)
    rb_t = max(_table_seps(readback_md), readback_md.count('<lark-table'))
    if rb_t < src_t:
        issues.append("表格 本地 %d → 飞书 %d（丢了 %d 张）" % (src_t, rb_t, src_t - rb_t))
    # ③ 显式追加的必查串
    for k in (extra_markers or []):
        if k not in readback_md:
            issues.append("必查串缺失：%s" % k)
    # ④ 长度骤缩兜底（掉了一大截正文，前三条没覆盖到时兜住）
    #    先剥围栏:mermaid 源文本在本地、渲染成图后不在回读,算进来会把「渲染」误判成「缩水」
    s_len = len(re.sub(r'\s', '', _strip_fences(source_md)))
    r_len = len(re.sub(r'\s', '', _strip_fences(readback_md)))
    if s_len and r_len < s_len * 0.6:
        issues.append("正文字符 本地 %d → 飞书 %d（缩到 %.0f%%，疑似大段丢失）"
                      % (s_len, r_len, 100.0 * r_len / s_len))
    return (len(issues) == 0, issues)


def _run(args):
    return subprocess.run(['lark-cli'] + args, capture_output=True, text=True)


def _json_output(r, action):
    if r.returncode != 0:
        raise RuntimeError('%s 失败: %s' % (action, r.stderr or r.stdout))
    try:
        data = json.loads(r.stdout)
    except Exception as e:
        raise RuntimeError('%s 返回非 JSON: %s (%s)' % (action, r.stdout[:500], e))
    # lark-cli 在 Keychain/OAuth 未就绪时可能仍以进程退出码 0 返回
    # {"ok": false, "error": ...}。只看退出码会把授权失败误判成成功。
    if isinstance(data, dict) and data.get('ok') is False:
        reason = data.get('error') or data.get('message') or data
        raise RuntimeError('%s 失败: %s' % (action, reason))
    return data


def _find_value(obj, keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and v not in (None, ''):
                return v
        for v in obj.values():
            got = _find_value(v, keys)
            if got not in (None, ''): return got
    if isinstance(obj, list):
        for v in obj:
            got = _find_value(v, keys)
            if got not in (None, ''): return got
    return None


def verify_user_identity():
    data = _json_output(_run(['whoami', '--as', 'user']), 'lark-cli whoami')
    identity = _find_value(data, {'identity', 'identityType', 'type'})
    available = _find_value(data, {'available'})
    token = _find_value(data, {'tokenStatus', 'token_status'})
    if str(identity).lower() != 'user' or available is not True or str(token).lower() != 'ready':
        raise RuntimeError('个人飞书身份未就绪: identity=%r available=%r tokenStatus=%r' %
                           (identity, available, token))
    return data


def create(title: str, md_path: str) -> str:
    verify_user_identity()
    path = os.path.abspath(md_path)
    data = _json_output(_run(['docs', '+create', '--as', 'user', '--title', title,
                              '--doc-format', 'markdown', '--content', '@' + path]),
                        'lark-cli docs +create')
    tok = _find_value(data, {'document_id', 'documentId', 'doc_token', 'docToken', 'token'})
    if not tok:
        raise RuntimeError('create 成功但找不到文档 token: %s' % json.dumps(data, ensure_ascii=False)[:1000])
    return str(tok)


def _fences(md: str) -> int:
    return md.count('```') // 2


def _split_render_heavy(md: str, max_fences: int = 2):
    """按标题(## / ### / ####)切块,贪心合并到「每块 ≤max_fences 个 ``` 围栏」。
    ⛔ 2026-09-18 教训:含 ≥3 个 mermaid 的文档,单次 create/overwrite 飞书**块转换整体失败**
       (exit 2、建成空壳、回读 0 字),必须分块 append。报告(2图)侥幸过、附件(7图)崩;
       实测每块 ≤2 张图稳过。"""
    parts = [p for p in re.split(r'(?=^#{2,4} )', md, flags=re.M) if p.strip()]
    chunks, cur, cnt = [], '', 0
    for p in parts:
        f = _fences(p)
        if cur and cnt + f > max_fences:
            chunks.append(cur); cur, cnt = '', 0
        cur += p; cnt += f
    if cur.strip():
        chunks.append(cur)
    return chunks or [md]


def _tmp(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix='.md'); os.close(fd)
    io.open(path, 'w', encoding='utf-8').write(content)
    return path


def create_chunked(title: str, md_path: str) -> str:
    """兼容旧调用名；官方 CLI 直接导入整篇 Markdown 与本地图片。"""
    return create(title, md_path)


def fetch(doc_token: str, doc_format: str = 'markdown') -> str:
    verify_user_identity()
    data = _json_output(_run(['docs', '+fetch', '--as', 'user', '--doc', doc_token,
                              '--scope', 'full', '--detail', 'full', '--doc-format', doc_format]),
                        'lark-cli docs +fetch')
    content = _find_value(data, {'content', 'markdown', 'xml', 'body'})
    if not isinstance(content, str):
        raise RuntimeError('fetch 成功但找不到 %s 正文' % doc_format)
    return content


def update(doc_token: str, md_path: str) -> str:
    """原地覆盖更新已有飞书文档(保持同一 URL,不再每次建新文档)。
    退出码 0=成功、3=成功但有警告(如 mermaid 渲染警告),都算成功。"""
    verify_user_identity()
    r = _run(['docs', '+update', '--as', 'user', '--doc', doc_token, '--command', 'overwrite',
              '--doc-format', 'markdown', '--content', '@' + os.path.abspath(md_path)])
    _json_output(r, 'lark-cli docs +update')
    return doc_token


def create_and_verify(title: str, md_path: str, extra_markers=None, doc_token: str = None,
                      evidence_manifest: str = None):
    """写 + 回读校验一步到位。返回 (doc_token, ok, issues)。⭐ ok=False 时别当成功交付。
    传 doc_token=已有文档 → 原地更新(保持 URL);不传 → 建新文档。
    ⭐ 新建且 ≥3 张图时自动分块(单次写会静默出空壳),调用方无需操心。"""
    src = io.open(md_path, encoding='utf-8').read()
    if doc_token:
        tok = update(doc_token, md_path)
    else:
        tok = create(title, md_path)
    ok, issues = verify_readback(src, fetch(tok, 'markdown'), extra_markers)
    if ok and evidence_manifest:
        xml_tmp = _tmp(fetch(tok, 'xml'))
        try:
            r = subprocess.run([sys.executable, os.path.join(_HERE, 'feishu-delivery-gate.py'),
                                '--source', md_path, '--readback', xml_tmp,
                                '--evidence-manifest', evidence_manifest],
                               capture_output=True, text=True)
            if r.returncode != 0:
                issues.append('飞书图片交付门未通过:\n' + (r.stdout or '') + (r.stderr or ''))
            ok = ok and r.returncode == 0
        finally:
            try: os.remove(xml_tmp)
            except OSError: pass
    return tok, ok, issues


_HERE = os.path.dirname(os.path.abspath(__file__))


def audience_ok(md_path: str):
    """跑 audience-gate 查这份交付物正文合不合「给人看」。返回 (ok, 输出)。
    ⛔ 2026-09-17 教训:v8 竞品报告通篇是过程日志(抓取管线/收敛轨迹/需求 N/内部锚点/图见文末),
       audience-gate 一跑全红——但 skill 从没在推飞书前跑它。⇒ 把它焊进推送咽喉。"""
    r = subprocess.run([sys.executable, os.path.join(_HERE, 'audience-gate.py'), md_path],
                       capture_output=True, text=True)
    return (r.returncode == 0, (r.stdout or '') + (r.stderr or ''))


def push_deliverable(title: str, md_path: str, extra_markers=None,
                     doc_token: str = None, evidence_manifest: str = None):
    """推**人看版交付物**(竞品分析/PRD/设计稿)前先过 audience-gate,红了**拒绝推送**。
    ⇒ 「正文给人看、不装我的日志」从散文变成推送链路上物理拦得住的红线。
    ⭐ 传 doc_token=已有文档 → **原地更新保持同一 URL**(修「每次建新文档堆积过时版本」);不传 → 建新。
    返回 (doc_token, verify_ok, verify_issues)。audience-gate 红时抛 RuntimeError,不推。"""
    ok, out = audience_ok(md_path)
    if not ok:
        raise RuntimeError(
            "⛔ 拒绝推送:audience-gate 判这份交付物正文混入了不该给读者看的东西"
            "(过程日志/内部路径/自检编号/把读者支出去)。先按下面清理,再推:\n\n" + out)
    return create_and_verify(title, md_path, extra_markers, doc_token=doc_token,
                             evidence_manifest=evidence_manifest)


def self_test():
    ok = True

    def case(name, cond):
        nonlocal ok
        ok &= cond
        print("  %s %s" % ("✅" if cond else "❌", name))

    src = ("# 标题\n\n证据分 [取证] [取证] [推断]。\n\n"
           "| 列1 | 列2 |\n|---|---|\n| a | b |\n\n结论段落，够长够长够长够长。\n")
    # 正例：回读完整（表格转成 lark-table）
    clean = ("# 标题\n\n证据分 [取证] [取证] [推断]。\n\n"
             "<lark-table><lark-tr><lark-td>a</lark-td></lark-tr></lark-table>\n\n"
             "结论段落，够长够长够长够长。\n")
    ok1, iss1 = verify_readback(src, clean)
    case("正例 回读完整（含 lark-table 归一）→ 无问题", ok1 and not iss1)

    # 反例①：一个 [取证] 被吞
    drop_marker = clean.replace("[取证] [取证]", "[取证]")
    ok2, iss2 = verify_readback(src, drop_marker)
    case("反例 [取证] 少一个 → 抓到", (not ok2) and any('取证' in i for i in iss2))

    # 反例②：表格被吞
    drop_table = clean.replace("<lark-table><lark-tr><lark-td>a</lark-td></lark-tr></lark-table>", "")
    ok3, iss3 = verify_readback(src, drop_table)
    case("反例 表格丢失 → 抓到", (not ok3) and any('表格' in i for i in iss3))

    # 反例③：大段正文丢失
    ok4, iss4 = verify_readback(src, "# 标题\n")
    case("反例 大段正文丢失 → 抓到（长度兜底）", (not ok4) and len(iss4) >= 1)

    # 反例④：显式必查串缺失
    ok5, iss5 = verify_readback(src, clean, extra_markers=["不存在的串"])
    case("反例 显式必查串缺失 → 抓到", (not ok5) and any('必查串' in i for i in iss5))

    # 正例②：mermaid 围栏内 [xxx] 渲染成图后从回读消失 → 不该假红
    _tail = "结论段落写得足够长足够长足够长足够长足够长足够长足够长足够长足够长。"
    src_m = ('# 标题\n\n正文 [取证]。\n\n```mermaid\ngraph TD\n'
             '  subgraph L["③ 能力层"]\n  end\n```\n\n' + _tail + '\n')
    rb_m = '# 标题\n\n正文 [取证]。\n\n' + _tail + '\n'   # 飞书把 mermaid 渲成图,源文本不在
    ok6, iss6 = verify_readback(src_m, rb_m)
    case("正例 mermaid围栏内[xxx]渲染后消失 → 不假红", ok6 and not iss6)

    # 反例⑤：围栏外真散文标记丢失,剥围栏后仍要抓到(别把真标记也漏了)
    rb_m2 = '# 标题\n\n正文 。\n\n' + _tail + '\n'
    ok7, iss7 = verify_readback(src_m, rb_m2)
    case("反例 围栏外真[取证]丢失 → 仍抓到", (not ok7) and any('取证' in i for i in iss7))

    # 正例③：render-heavy 分块——7 围栏文档切成每块 ≤2 围栏(治单次写出空壳)
    heavy = "## 头\n\n正文\n\n" + "".join(
        "### D%d\n\n```mermaid\ngraph TD\n  A-->B\n```\n\n" % i for i in range(7))
    chunks = _split_render_heavy(heavy, max_fences=2)
    case("render-heavy 7围栏 → 分块后每块≤2围栏",
         _fences(heavy) == 7 and chunks and all(_fences(c) <= 2 for c in chunks))

    print("\n%s" % ("✅ 飞书回读校验模块自证通过" if ok else "❌ 自证失败"))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    print(__doc__); sys.exit(0)
