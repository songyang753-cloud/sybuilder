#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规格 ↔ demo 对账门禁 —— sidecar 契约组说的，和 demo 里真有的，必须对得上。

═══ 它补的是哪个洞 ═══
S5.2 产出的东西一直是散文，S6 靠人读一遍再手写。
本 SOP 记过「md→md 三种衰减：丢项 / 改写漂移 / **静默降级**」——
最隐蔽的是第三种：`P95 ≤ 300ms` 被复述成「响应要快」，读起来完全通顺而约束没了。
把文案 / 校验 / 元素 / 状态 / 关键路径 / 接口搬进 json 之后，
**衰减第一次变成可机器检测的东西**。

六条规则（都会红，且都有反向用例）：
  S1 copy-used            copy.json 每条文案必须在 demo 里出现
  S2 api-declared         demo 的 api 方法集合 == operations.json 的 op 集合（双向）
  S3 element-present      elements.json 每个可访问名称必须在 demo 里出现
  S4 flow-elements        flows.json 每步引用的 role+name 必须在 elements.json 登记过
  S5 surface-declared     elements/flows 引用的界面 id 必须在 states.json 里存在
  S6 generated-in-sync    js/60-copy.js 与 js/70-validators.js 与 spec 一致（没人手改产物）

⚠️ 诚实边界：本门是**静态**对账（读文本），不开浏览器。
   「文案在 demo 里出现」不等于「用户看得到它」—— 那归 scenario-matrix / flow-walk。

用法:
  spec-sync-gate.py <spec目录> <demo.html> [--js <js目录>] [--json] [--list-rules]
  spec-sync-gate.py --self-test
退出码: 0=对得上  1=对不上  2=跑不了
"""
import io, json, os, re, subprocess, sys

RULES = [
    ("copy-used", "copy.json 每条文案必须在 demo 里出现"),
    ("api-declared", "demo 的 api 方法集合 == operations.json 的 op 集合（双向）"),
    ("element-registered", "demo 里的静态 data-el 都在 elements.json 登记过（反方向）"),
    ("element-slug", "elements.json 每个 id（跨产物 slug）必须在 demo 里以 data-el 出现"),
    ("element-present", "elements.json 每个可访问名称必须在 demo 里出现"),
    ("flow-elements", "flows.json 每步引用的 role+name 必须在 elements.json 登记过"),
    ("surface-declared", "elements/flows 引用的界面 id 必须在 states.json 里存在"),
    ("keyboard-covered", "有键盘契约的组件必须有对应的键盘 flow（判据 见 keyboard-contracts.md）"),
    ("generated-in-sync", "js 产物与 spec 一致（没人手改产物）"),
]


def die(m):
    print("UNABLE: %s" % m, file=sys.stderr); sys.exit(2)


def load(spec_dir, name, required=True):
    p = os.path.join(spec_dir, name)
    if not os.path.exists(p):
        if required: die("缺少 %s" % name)
        return None
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception as e:
        die("%s 解析失败：%s" % (name, e))


def check(spec_dir, demo_path, js_dir):
    if not os.path.isdir(spec_dir): die("spec 目录不存在：%s" % spec_dir)
    if not os.path.exists(demo_path): die("demo 不存在：%s" % demo_path)
    html = io.open(demo_path, encoding='utf-8', errors='replace').read()
    # 🚨 2026-09-09：copy/api/element 三类判据原来只搜**单文件**，
    #   而本 SOP 的开发态是**目录版 proto**（`templates/proto/`，正本唯一，
    #   内容分散在 js/*.js 里）—— 于是拿开发态跑本门，四条判据集体误报
    #   「copy 在 demo 里找不到 / operations 声明了 demo 里没有」。
    #   ⛔ 门必须能验它自己 SOP 规定的那种形态：给了 --js 就把分片纳入搜索面。
    #   （bundle 后的单文件不受影响：那时 --js 缺省，行为与从前一致。）
    #   ⚠️ **代价（2026-09-09 独立复核指出，如实记下）**：分片是整段并进搜索面的，
    #   于是只写在 **JS 注释**里的文案也能满足 copy-used ——「文案出现在 demo 里」
    #   这条的证据强度因此下降了一档。⛔ 不假装没有这个代价：真正的行为证据归
    #   `flow-walk-gate` / `scenario-matrix-gate`（它们在浏览器里真跑），
    #   本条只验「规格与源码没分叉」，从来就不验「它真的被渲染出来了」。
    if js_dir and os.path.isdir(js_dir):
        for _n in sorted(os.listdir(js_dir)):
            if _n.endswith('.js'):
                html += '\n' + io.open(os.path.join(js_dir, _n),
                                       encoding='utf-8', errors='replace').read()
    copy = load(spec_dir, 'copy.json')
    api = load(spec_dir, 'operations.json')
    els = load(spec_dir, 'elements.json')
    flows = load(spec_dir, 'flows.json')
    states = load(spec_dir, 'states.json')
    out = []

    # S1 ------------------------------------------------------------
    miss = [k for k, v in (copy.get('strings') or {}).items() if v.get('text') and v['text'] not in html]
    out.append(("copy-used", not miss,
                "%d 条文案全部出现在 demo 里" % len(copy.get('strings') or {}) if not miss
                else ["copy.json 的 %s（「%s」）在 demo 里找不到" % (k, (copy['strings'][k]['text'])[:16]) for k in miss]))

    # S2 ------------------------------------------------------------
    declared = {e['op'] for e in (api.get('operations') or api.get('endpoints') or [])}
    found = set(re.findall(r'\b([a-zA-Z][a-zA-Z0-9]*)\s*:\s*function\s*\(', html))
    # 只认在 P.api = { … } 里的那些：取 api 对象块
    m = re.search(r'P\.api\s*=\s*\{(.*?)\n  \};', html, re.S)
    if m:
        found = set(re.findall(r'\n\s*([a-zA-Z][a-zA-Z0-9]*)\s*:\s*function', m.group(1)))
        found.discard('can')          # 权限查询是本地能力，不是接口
    bad = []
    for op in sorted(declared - found): bad.append("operations.json 声明了 %s，demo 里没有" % op)
    for op in sorted(found - declared): bad.append("demo 里有 %s，operations.json 没声明 —— 未登记的操作不会有人实现" % op)
    out.append(("api-declared", not bad, bad or "%d 个接口双向对齐" % len(declared)))

    # S3a 跨产物 slug -------------------------------------------------
    # ⭐ slug 与可访问名称是**两层身份**，各查各的：
    #   只查名称 → 改一句文案，Figma 图层名与测试选择器同时失效而没人发现；
    #   只查 slug → 改掉可访问名称，无障碍静默退化而没人发现。
    # ⚠️ 2026-09-04：有些 slug 是**运行时拼出来的**（如底部 tab 的
    #    `data-el="tab-" + n.path`），静态扫 HTML 文本找不到 —— 与场景锚点同一形态。
    #    ⛔ 判据不能因此放行（那会让「真的漏了」也过去），
    #      也不能一律判红（那会惩罚正确实现）。
    #    ⇒ 与 `dynamic` 同一条出口：**在 elements.json 里显式登记 `runtimeSlug: true`**，
    #      并要求给出 `slugFrom`（说明它从哪拼出来），登记了才豁免静态扫描。
    #    ⭐ 不写理由的豁免就是静音开关（与端差异登记同一条纪律）。
    miss, bad_rt, exempt = [], [], []
    for e in (els.get('elements') or []):
        sid = e['id']
        found = ('data-el="%s"' % sid) in html or ("data-el='%s'" % sid) in html
        if found:
            continue
        if e.get('runtimeSlug'):
            if not str(e.get('slugFrom', '')).strip():
                bad_rt.append("elements.json 的 %s 标了 runtimeSlug 却没写 slugFrom —— "
                              "不写来源的豁免就是静音开关" % sid)
            else:
                exempt.append(sid)
            continue
        miss.append(sid)
    miss += bad_rt
    # ⚠️ 2026-09-04：豁免了几个就要说几个。
    #    第一版证据写「N 个 slug 都在 demo 里以 data-el 出现」，
    #    而 runtimeSlug 豁免掉的那些**根本没出现** —— 这句话是假的，
    #    而且是我自己加豁免时引入的。⭐ **加了出口，就要在计数里体现它。**
    _tot = len(els.get('elements') or [])
    _msg = ("%d 个 slug 都在 demo 里以 data-el 出现" % _tot if not exempt
            else "%d 个 slug 中 %d 个在 demo 里以 data-el 出现，%d 个按 runtimeSlug 豁免（%s）"
                 % (_tot, _tot - len(exempt), len(exempt), "、".join(exempt)))
    out.append(("element-slug", not miss, _msg if not miss
                else ["elements.json 的 slug `%s` 在 demo 里找不到 data-el" % m for m in miss]))

    # S2c 反方向 ------------------------------------------------------
    # ⚠️ 2026-09-05：接口是**双向**对账的（S2），元素此前**只有单向** ——
    #    demo 里可以有一个 data-el 从未登记，于是它的名称契约、所在界面、
    #    键盘要求全都无人规定。本门自己的话：**反向漏＝多做了没人要的，
    #    永远不会被测试覆盖，也永远没人负责。**
    #    ⛔ 不许误伤运行时拼接的 slug（`data-el="tab-" + n.path`）——
    #       它们在 HTML 里留下的字面量含有引号/加号，按此特征排除。
    in_html = set(re.findall(r'data-el="([^"]*)"', html)) | \
              set(re.findall(r"data-el='([^']*)'", html))
    RUNTIME = re.compile(r"""['"`]|\+|\$\{""")     # 拼接痕迹
    declared_ids = {e['id'] for e in (els.get('elements') or [])}
    stray = sorted(s for s in in_html
                   if s and s not in declared_ids and not RUNTIME.search(s))
    out.append(("element-registered", not stray,
                ["demo 里有 data-el=`%s`，elements.json 没登记 —— "
                 "没登记的元素没有名称契约、没有所在界面、也没人要求它能用键盘操作" % s
                 for s in stray]
                or "demo 里 %d 个静态 data-el 全部登记在案" % len(in_html)))

    # S3 ------------------------------------------------------------
    bad = []
    types = api.get('types') or {}
    for e in (els.get('elements') or []):
        if e.get('dynamic'):
            # 动态元素没有字面量可查 —— 改查它的名称来源真的锚在数据契约上。
            # ⛔ 否则「反正是动态的」会变成一句谁也核不了的话。
            nf = e.get('nameFrom') or ''
            tn, _, fn = nf.partition('.')
            if not fn or tn not in types or fn not in (types.get(tn) or {}):
                bad.append("elements.json %s 是 dynamic，但 nameFrom=「%s」在 operations.json 的 types 里找不到" % (e['id'], nf))
        elif e.get('name') and e['name'] not in html:
            bad.append("elements.json 的 %s（%s「%s」）在 demo 里找不到" % (e['id'], e['role'], e['name']))
    out.append(("element-present", not bad,
                bad or "%d 个元素身份都对得上（含 %d 个数据驱动）" %
                (len(els.get('elements') or []), sum(1 for e in (els.get('elements') or []) if e.get('dynamic')))))

    # S4 ------------------------------------------------------------
    # ⚠️ 动态元素没有 name 键。首版直接 e['name'] → 真实数据上 KeyError，
    #    而**自证是绿的**：我加了 dynamic 这个能力，却没给它加用例。
    #    ⭐ 新增能力必须同时新增正例，否则自证覆盖的是「加之前的那个程序」。
    known = {(e['role'], e['name']) for e in (els.get('elements') or []) if e.get('name')}
    prefixes = set(known)
    bad = []
    for f in (flows.get('flows') or []):
        for i, s in enumerate(f.get('steps') or []):
            role = s.get('role') or s.get('roleExists')
            if not role: continue
            name, pref = s.get('name'), s.get('namePrefix')
            if name and (role, name) not in known:
                bad.append("%s 第 %d 步用了 %s「%s」，elements.json 没登记" % (f['id'], i + 1, role, name))
            dyn_roles = {e['role'] for e in (els.get('elements') or []) if e.get('dynamic')}
            if pref and role not in dyn_roles and not any(r == role and n.startswith(pref) for r, n in prefixes):
                bad.append("%s 第 %d 步用了 %s 前缀「%s」，elements.json 里没有匹配项" % (f['id'], i + 1, role, pref))
    out.append(("flow-elements", not bad, bad or "关键路径引用的元素全部登记过"))

    # S5 ------------------------------------------------------------
    surfaces = {s['id'] for s in (states.get('surfaces') or [])}
    bad = []
    for e in (els.get('elements') or []):
        if e.get('surface') and e['surface'] != '*' and e['surface'] not in surfaces:
            bad.append("elements.json %s 指向界面 %s，states.json 里没有这个界面" % (e['id'], e['surface']))
    out.append(("surface-declared", not bad, bad or "界面 id 引用全部有效"))

    # S5b 键盘覆盖 ---------------------------------------------------
    # ⭐ 挡的是最常见的那种漏：组件做出来了、鼠标能用、**没人想过键盘**。
    #   ⛔ 它不检查那条 flow 写得对不对（那归 flow-walk 真跑一遍），
    #   只检查「你有没有为这个组件写键盘用例」。
    KB_ROLES = {'dialog', 'combobox', 'listbox', 'tabs', 'disclosure', 'menu', 'menuitem'}
    used = {e.get('role') for e in (els.get('elements') or []) if e.get('role')} & KB_ROLES
    covered = {f.get('widget') for f in (flows.get('flows') or []) if f.get('widget')}
    # 表单是按「有没有输入框」判，不看 role 名
    if any((e.get('role') or '') in ('textbox', 'searchbox') for e in (els.get('elements') or [])):
        used.add('form')
    # menuitem 归到 menu 这一类
    if 'menuitem' in used: used.discard('menuitem'); used.add('menu')
    miss = sorted(used - covered)
    # 模板占位符没改掉 = 没写（⛔ 原样留着比不写更糟：它看起来像写了）
    ph = [f['id'] for f in (flows.get('flows') or [])
          if any('<' in str(v) and '>' in str(v) for s in (f.get('steps') or []) for v in s.values())
          or 'FR-???' in str(f.get('fr'))]
    bad = ["用到了 %s 但 flows.json 里没有 widget=%s 的键盘 flow（模板见 templates/spec/keyboard-flows.json）" % (m, m)
           for m in miss]
    bad += ["%s 还留着模板占位符（`<…>` 或 FR-???）—— 原样留着比不写更糟，它看起来像写了" % i for i in ph]
    out.append(("keyboard-covered", not bad,
                bad or ("%d 类需要键盘契约的组件都有 flow" % len(used) if used
                        else "没有用到需要键盘契约的组件（**不是「过了」，是不适用**）")))

    # S6 ------------------------------------------------------------
    if js_dir and os.path.isdir(js_dir):
        gen = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spec-to-js.py')
        rc = subprocess.call([sys.executable, gen, spec_dir, js_dir, '--check'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out.append(("generated-in-sync", rc == 0,
                    "js 产物与 spec 一致" if rc == 0 else ["js 产物与 spec 不一致（有人手改了产物，或 spec 改了没重新生成）"]))
    else:
        out.append(("generated-in-sync", None, "未提供 --js 目录，本条**没测**（不计入通过）"))
    return out


def report(rows, as_json):
    if as_json:
        print(json.dumps([{"rule": r, "ok": o, "ev": e} for r, o, e in rows], ensure_ascii=False, indent=1))
        return 1 if any(o is False for _, o, _ in rows) else 0
    fail = 0
    for rid, ok, ev in rows:
        icon = "✅" if ok else ("➖" if ok is None else "❌")
        if ok is False: fail += 1
        print("%s [%s]" % (icon, rid))
        if isinstance(ev, list):
            for x in ev[:8]: print("     · " + x)
            if len(ev) > 8: print("     …… 还有 %d 条" % (len(ev) - 8))
        else:
            print("     " + str(ev))
    na = sum(1 for _, o, _ in rows if o is None)
    print("\n通过 %d · 失败 %d · 未测 %d" % (len(rows) - fail - na, fail, na))
    if fail:
        # ⭐ 门红的那一刻，人只会读这一行。只说「不符」，下一个人的第一反应是改判据让它变绿；
        #    说清后果，他才会去看代码。（2026-09-05 由并行会话 fm-agent 提出，已核对本仓 5 道缺这句。）
        print("⚠️ 规格与 demo 对不上意味着**交互稿不能当实现依据** —— "
              "照规格写的代码和照 demo 演示的行为会是两回事，而两边各自都「看起来是对的」。")
    if na: print("⚠️ 「未测」不折叠进通过 —— 没测过的东西不许当成过了。")
    return 1 if fail else 0


# --------------------------------------------------------------- 自证（M8）
_SPEC = {
    "copy.json": {"limits": {}, "strings": {"a": {"text": "任务列表"}, "b": {"text": "提交"}}},
    "operations.json": {"operations": [{"op": "listTasks"}, {"op": "createTask"}]},
    "elements.json": {"elements": [{"id": "E-01", "surface": "f01", "role": "heading", "name": "任务列表"},
                                    {"id": "E-02", "surface": "f01", "role": "button", "name": "提交"}]},
    "flows.json": {"flows": [{"id": "F-A", "steps": [{"do": "click", "role": "button", "name": "提交"}]}]},
    "states.json": {"surfaces": [{"id": "f01", "ends": ["pc"], "states": []}]},
    "validators.json": {"fields": {}},
}
_DEMO = """<html><body><h1 data-el="E-01">任务列表</h1><button data-el="E-02">提交</button>
<script>
  P.api = {
    listTasks: function (q) { return 1; },
    createTask: function (p) { return 2; },
    can: function (a) { return true; }
  };
</script></body></html>"""


def _self_test():
    import copy as _copy, tempfile
    me = os.path.abspath(__file__)
    ok = True
    print("M8 自证 —— 正例绿 / 每条规则各有反例必红 / 无效输入报 2\n")

    def mk(spec_over=None, demo=None):
        d = tempfile.mkdtemp(prefix='ssg-')
        sd = os.path.join(d, 'spec'); os.makedirs(sd)
        spec = _copy.deepcopy(_SPEC)
        if spec_over: spec_over(spec)
        for n, v in spec.items():
            json.dump(v, io.open(os.path.join(sd, n), 'w', encoding='utf-8'), ensure_ascii=False)
        dp = os.path.join(d, 'demo.html')
        io.open(dp, 'w', encoding='utf-8').write(demo if demo is not None else _DEMO)
        return sd, dp

    def call(sd, dp, js=None):
        return subprocess.call([sys.executable, me, sd, dp] + (['--js', js] if js else []),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def gen_js(sd):
        """用 spec-to-js.py 真的生成一份产物 —— 供 S6「产物没被手改」那条判据用。"""
        jd = os.path.join(os.path.dirname(sd), 'js'); os.makedirs(jd, exist_ok=True)
        subprocess.call([sys.executable,
                         os.path.join(os.path.dirname(me), 'spec-to-js.py'), sd, jd],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jd

    cases = [("正例：spec 与 demo 完全对得上", mk(), 0)]

    def mk_split():
        """🚨 2026-09-09：**开发态是目录版 proto**（内容分散在 js/*.js），
        而 copy/api/element 三类判据原来只搜单文件 ⇒ 拿开发态跑本门，
        四条判据集体误报（实测 `templates/proto/` 5 过 4 败，全是假阳性）。
        本用例把文案与 data-el 挪进 js 分片，只留骨架 HTML —— 形状与真实开发态一致。
        """
        sd, dp = mk()
        d = os.path.dirname(dp)
        js = os.path.join(d, 'js'); os.makedirs(js, exist_ok=True)
        body = io.open(dp, encoding='utf-8').read()
        io.open(dp, 'w', encoding='utf-8').write("<!doctype html><div id=app></div>")
        io.open(os.path.join(js, '10-view.js'), 'w', encoding='utf-8').write(
            "// 渲染层（真实 proto 就是这么分片的）\nconst TPL = `%s`;\n" % body.replace('`', "'"))
        # ⚠️ 传了 --js 就会连带跑第 5 条 generated-in-sync（copy.js/validators.js
        #   必须是 spec-to-js 的产物）—— 夹具不生成它们，红的会是那一条，
        #   而不是本用例要测的四条。⭐ 隔离＝只让目标判据成为唯一变量。
        gen = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spec-to-js.py')
        subprocess.call([sys.executable, gen, sd, js],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return sd, dp, js

    _sd, _dp, _js = mk_split()
    # ⭐ runner 用 `*pair` 展开，把 js 目录作为第三个位置参数并进去即可（call 的签名就是它）。
    cases.append(("正例：目录版 proto（文案/元素在 js 分片里）不许被判成对不上",
                  (_sd, _dp, _js), 0))
    cases.append(("反例 S1：copy 里有 demo 找不到的文案",
                  mk(lambda s: s["copy.json"]["strings"].update({"c": {"text": "根本没有这句"}})), 1))
    cases.append(("反例 S2a：operations.json 声明了 demo 没有的接口",
                  mk(lambda s: s["operations.json"]["operations"].append({"op": "deleteTask"})), 1))
    # 🆕 S2c 反方向：demo 有未登记的**元素**（此前只有接口是双向的）
    cases.append(("反例 S2c：demo 有未登记的 data-el（其余全对，只违反这一条）",
                  mk(None, _DEMO.replace('<button data-el="E-02">提交</button>',
                                         '<button data-el="E-02">提交</button>'
                                         '<span data-el="野生元素">提交</span>')), 1))
    cases.append(("正例 S2c：运行时拼接的 data-el 不许被误判成未登记",
                  mk(None, _DEMO.replace('<h1 data-el="E-01">',
                                         '<h1 data-el="tab-\' + n.path + \'">占位</h1><h1 data-el="E-01">')), 0))
    cases.append(("反例 S2b：demo 有未登记的接口",
                  mk(lambda s: s["operations.json"]["operations"].pop())), )
    cases[-1] = (cases[-1][0], cases[-1][1], 1)
    cases.append(("反例 S3a：slug 在 demo 里没有 data-el",
                  mk(lambda s: s["elements.json"]["elements"].append(
                      {"id": "no-such-slug", "surface": "f01", "role": "button", "name": "提交"})), 1))
    # ⚠️⚠️ 2026-09-05 变异扫描实测：下面几条反例**存在，却没有隔离它们要守的判据** ——
    #    塞进去的元素 id 在 demo 里没有 data-el，于是 element-slug 先红了，
    #    把本该验的那条盖住。把那条判据**整条删掉，自证照样全绿**。
    #    ⇒ 反例必须「其余全对、只违反这一条」，否则它守的是另一条规则。
    cases.append(("反例 S3：元素身份在 demo 里找不到（slug 在、只有名称对不上）",
                  mk(lambda s: s["elements.json"]["elements"].append(
                      {"id": "E-09", "surface": "f01", "role": "button", "name": "并不存在的按钮"}),
                     _DEMO.replace('<button data-el="E-02">提交</button>',
                                   '<button data-el="E-02">提交</button>'
                                   '<button data-el="E-09">另一个按钮</button>')), 1))
    cases.append(("反例 S4：关键路径用了没登记的元素",
                  mk(lambda s: s["flows.json"]["flows"][0]["steps"].append(
                      {"do": "click", "role": "button", "name": "野生按钮"})), 1))
    # ⭐ 2026-09-04：运行时拼出来的 slug（如 `data-el="tab-" + n.path`）静态扫不到。
    #    出口是显式登记 runtimeSlug + slugFrom；**不写来源的豁免就是静音开关**。
    cases.append(("正例 runtimeSlug 登记了来源 → 放行",
                  mk(lambda s: s["elements.json"]["elements"].append(
                      {"id": "rt-x", "surface": "f01", "role": "link", "name": "任务列表",
                       "runtimeSlug": True, "slugFrom": "shell.js：'rt-' + key"})), 0))
    cases.append(("反例 runtimeSlug 没写 slugFrom（静音开关必须红）",
                  mk(lambda s: s["elements.json"]["elements"].append(
                      {"id": "rt-y", "surface": "f01", "role": "link", "name": "任务列表",
                       "runtimeSlug": True})), 1))
    # 🚨 反向：没标 runtimeSlug 的照样必须红（新出口不许变成放行）
    cases.append(("反例 slug 静态找不到且没登记（出口不许变成放行）",
                  mk(lambda s: s["elements.json"]["elements"].append(
                      {"id": "rt-z", "surface": "f01", "role": "link", "name": "任务列表"})), 1))
    cases.append(("反例 S5：元素指向不存在的界面（其余全对，只有 surface 错）",
                  mk(lambda s: s["elements.json"]["elements"].append(
                      {"id": "E-08", "surface": "f99", "role": "button", "name": "提交"}),
                     _DEMO.replace('<button data-el="E-02">提交</button>',
                                   '<button data-el="E-02">提交</button>'
                                   '<button data-el="E-08">提交</button>')), 1))
    cases.append(("正例：数据驱动元素（nameFrom 锚在 api.types 上）",
                  mk(lambda s: (s["elements.json"]["elements"].append(
                        {"id": "E-99", "surface": "f01", "role": "link", "dynamic": True, "nameFrom": "Task.title"}),
                      s["operations.json"].update({"types": {"Task": {"title": "string"}}}),
                      s["flows.json"]["flows"][0]["steps"].append(
                        {"do": "clickFirst", "role": "link", "namePrefix": "季度"})),
                     _DEMO.replace('<h1 data-el="E-01">',
                                   '<a href="#" data-el="E-99">季度对账单 1</a><h1 data-el="E-01">')), 0))
    cases.append(("反例 S3b：dynamic 的 nameFrom 在 api.types 里不存在（slug 在、types 也在）",
                  mk(lambda s: (s["elements.json"]["elements"].append(
                        {"id": "E-98", "surface": "f01", "role": "link",
                         "dynamic": True, "nameFrom": "Task.nope"}),
                      s["operations.json"].update({"types": {"Task": {"title": "string"}}})),
                     _DEMO.replace('<h1 data-el="E-01">',
                                   '<a href="#" data-el="E-98">任意一条</a><h1 data-el="E-01">')), 1))
    # 🆕 namePrefix 此前**只有正例**（见上面「数据驱动元素」那条），
    #    ⇒ 把 flow-elements 里的 namePrefix 分支整条删掉，自证不会红。这是它的反例。
    cases.append(("反例 S4b：namePrefix 在 elements.json 里没有匹配项",
                  mk(lambda s: (s["elements.json"]["elements"].append(
                        {"id": "E-97", "surface": "f01", "role": "link", "name": "季度对账单 1"}),
                      s["flows.json"]["flows"][0]["steps"].append(
                        {"do": "clickFirst", "role": "link", "namePrefix": "根本没有这个前缀"})),
                     _DEMO.replace('<h1 data-el="E-01">',
                                   '<a href="#" data-el="E-97">季度对账单 1</a><h1 data-el="E-01">')), 1))
    # ── keyboard-covered 的正反例（新规则必须自己有用例）──
    cases.append(("正例：有 combobox 且有对应键盘 flow",
                  mk(lambda s: (s["elements.json"]["elements"].append(
                        {"id": "proj-picker", "surface": "f01", "role": "combobox", "name": "提交"}),
                      s["flows.json"]["flows"].append(
                        {"id": "KB-1", "widget": "combobox", "fr": ["FR-1"],
                         "steps": [{"do": "key", "key": "Escape"}]})),
                     _DEMO.replace('<h1 data-el="E-01">',
                                   '<div data-el="proj-picker">提交</div><h1 data-el="E-01">')), 0))
    # ⚠️ 反例也要带 slug，否则它们是因为 element-slug 缺失而红，**不是因为键盘规则** ——
    #    「红了」不等于「因为我想验的那条红了」。
    KB_DEMO = _DEMO.replace('<h1 data-el="E-01">', '<div data-el="proj-picker">提交</div><h1 data-el="E-01">')
    cases.append(("反例 KB-a：有 combobox 却没有键盘 flow",
                  mk(lambda s: s["elements.json"]["elements"].append(
                      {"id": "proj-picker", "surface": "f01", "role": "combobox", "name": "提交"}), KB_DEMO), 1))
    cases.append(("反例 KB-b：键盘 flow 还留着模板占位符",
                  mk(lambda s: (s["elements.json"]["elements"].append(
                        {"id": "proj-picker", "surface": "f01", "role": "combobox", "name": "提交"}),
                      s["flows.json"]["flows"].append(
                        {"id": "KB-2", "widget": "combobox", "fr": ["FR-???"],
                         "steps": [{"do": "click", "role": "combobox", "name": "<下拉框名>"}]})), KB_DEMO), 1))
    # 🆕 2026-09-05 `unexecuted-check` 实测：S6「产物与 spec 一致」这条判据
    #    **一次都没执行过** —— 自证从不传 `--js`，那个分支永远走不到。
    #    ⭐ 它守的恰恰是「有人手改了生成产物」，而这正是最难靠人眼发现的一类。
    _sd, _dp = mk()
    _jd = gen_js(_sd)
    cases.append(("正例 S6：产物由 spec-to-js 生成 ⇒ 与 spec 一致", (_sd, _dp, _jd), 0))
    _sd2, _dp2 = mk()
    _jd2 = gen_js(_sd2)
    _touched = None
    for _f in sorted(os.listdir(_jd2)):
        if _f.endswith('.js'):
            _p = os.path.join(_jd2, _f)
            io.open(_p, 'a', encoding='utf-8').write('\n/* 有人手改了产物 */\n')
            _touched = _f; break
    # ⛔ 断言反例**真的制造出了那个条件** —— 首版没断言，而最小 spec 生成不出任何 .js，
    #    循环什么都没改、反例与正例逐字相同、用例「通过」了。
    #    `unexecuted-check` 抓到 S6 从没执行时，我补的第一版夹具就是这么空转的。
    assert _touched, "反例夹具没改到任何 .js —— 它没有制造出「产物被手改」这个条件"
    cases.append(("反例 S6：产物被手改 ⇒ 必须红", (_sd2, _dp2, _jd2), 1))
    # 🆕 2026-09-05 `--unable` 实测：`load()` 的两个「跑不了」出口从没被触发过 ——
    #    自证的 spec 目录永远是完整且合法的。
    #    ⭐ 这类前提守卫锚点写错时**两头都不出声**：既不报「没跑过」也不报缺陷。
    _sd3, _dp3 = mk()
    os.remove(os.path.join(_sd3, 'elements.json'))
    cases.append(("反例：spec 目录缺必需文件 → 报 2", (_sd3, _dp3), 2))
    _sd4, _dp4 = mk()
    io.open(os.path.join(_sd4, 'elements.json'), 'w', encoding='utf-8').write('{ not json')
    cases.append(("反例：spec 里的 JSON 解析不了 → 报 2", (_sd4, _dp4), 2))
    cases.append(("反例：demo 文件不存在", (mk()[0], '/nope/nope.html'), 2))
    cases.append(("反例：spec 目录不存在", ('/nope/spec', mk()[1]), 2))

    for name, pair, want in cases:
        # ⛔ 必须 `*pair` —— 首版写死两个参数，第三个（--js 目录）被静默丢掉，
        #    于是 S6 那两条用例都没带 --js，**正例也是因为错误的原因通过的**。
        got = call(*pair)
        g = got == want; ok &= g
        print("  %s %-40s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修门禁"))
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
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    def _entry():
        if '--self-test' in sys.argv: sys.exit(_self_test())
        if '--list-rules' in sys.argv:
            for r, d in RULES: print("%-20s %s" % (r, d))
            sys.exit(0)
        args = [a for a in sys.argv[1:] if not a.startswith('--')]
        ji = sys.argv.index('--js') if '--js' in sys.argv else -1
        js_dir = sys.argv[ji + 1] if ji > -1 and len(sys.argv) > ji + 1 else None
        if js_dir and js_dir in args: args.remove(js_dir)
        if len(args) < 2: print(__doc__); sys.exit(2)
        sys.exit(report(check(args[0], args[1], js_dir), '--json' in sys.argv))
    _main_guarded(_entry)
