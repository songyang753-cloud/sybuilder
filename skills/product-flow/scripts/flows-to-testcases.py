#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec/flows.json + states.json → S8 用例骨架（`cases/<F-xx>.md`）。

═══ 为什么值得生成 ═══
S8 的用例此前与 demo **各写各的选择器**——本 SOP 记过：
「改一个按钮所有用例静默失效」。
关键路径与状态清单已经在 S5.2 以机器可读形式存在了，
用例的**步骤、选择器、预期**就该从同一份来，而不是让人再读一遍散文重写。

⛔ 它生成的是**骨架不是成品**：
   · 只覆盖「关键路径」与「状态可达」两类，等价类/边界值/权限矩阵/安全用例不在其中
   · 每条都带 `所属 FR/AC`（来自 flows.json 的 fr 字段）——没有 fr 的流程会被**拒绝生成**，
     因为「反查不到需求的用例不许存在」
   · 生成完必须人过一遍，并跑 `coverage_check.py` 做双向对账
⭐ 本脚本**不**声称覆盖率。声称覆盖率的是 `coverage_check.py`，它读的是全部用例。

用法:
  flows-to-testcases.py <spec目录> <输出目录> [--force]
  flows-to-testcases.py --self-test
退出码: 0=已生成  1=有流程缺 fr，拒绝生成  2=跑不了
"""
import io, json, os, sys

STEP_CN = {"fill": "在", "click": "点击", "clickFirst": "点击第一个"}


def die(m):
    print("UNABLE: %s" % m, file=sys.stderr); sys.exit(2)


# 合法的步骤动作 —— 与 `flow-walk-gate.mjs` 共用同一份 `spec/flows.json`，
# 两边必须认同一套键。
STEP_DO = ("fill", "click", "clickFirst", "key", "tab", "expect")


def step_text(s):
    # ⚠️ 2026-09-04：步骤缺 `do` 键时此前直接 `KeyError` 抛原始 traceback，
    #    而外层把它带成**退出码 1** —— 而 1 在本脚本里的语义是
    #    「有流程缺 fr，拒绝生成」。于是**输入格式错误被伪装成一个具体的业务结论**，
    #    照着这条结论去找「哪个流程缺 fr」只会一无所获。
    #    ⭐ 本轮第四次遇到「一句错误的诊断把人引向不存在的问题」。
    #    ⛔ 跑不了就是跑不了：报 2，并指出是哪一步、缺什么、合法值有哪些。
    if not isinstance(s, dict) or "do" not in s:
        die("步骤缺 `do` 键：%s —— 合法动作 %s（与 flow-walk-gate.mjs 同一套 schema）"
            % (json.dumps(s, ensure_ascii=False)[:80], "/".join(STEP_DO)))
    if s["do"] not in STEP_DO:
        die("步骤的 `do` 值不认识：`%s` —— 合法动作 %s" % (s["do"], "/".join(STEP_DO)))
    if s["do"] == "fill":
        return "在 %s「%s」里填入「%s」" % (s.get("role", ""), s.get("name", ""), s.get("value", ""))
    if s["do"] in ("click", "clickFirst"):
        who = s.get("name") or (s.get("namePrefix", "") + "…")
        return "%s %s「%s」" % (STEP_CN[s["do"]], s.get("role", ""), who)
    return None      # expect 归到预期，不算步骤


def expect_text(s):
    out = []
    if s.get("urlContains"): out.append("地址栏含「%s」" % s["urlContains"])
    if s.get("textContains"): out.append("页面出现「%s」" % s["textContains"])
    if s.get("textAbsent"): out.append("页面不出现「%s」" % s["textAbsent"])
    if s.get("focusedName"): out.append("焦点在「%s」" % s["focusedName"])
    if s.get("roleExists"): out.append("存在 %s「%s」" % (s["roleExists"], s.get("name", "")))
    return out


def gen(spec_dir, out_dir, force):
    if not os.path.isdir(spec_dir): die("spec 目录不存在：%s" % spec_dir)
    try:
        flows = json.load(io.open(os.path.join(spec_dir, 'flows.json'), encoding='utf-8')).get('flows') or []
        states = json.load(io.open(os.path.join(spec_dir, 'states.json'), encoding='utf-8')).get('surfaces') or []
    except Exception as e:
        die("读不了 spec：%s" % e)

    # 铁律：反查不到需求的用例不许存在 → 缺 fr 的流程直接拒绝
    nofr = [f['id'] for f in flows if not f.get('fr')]
    if nofr:
        print("❌ 以下关键路径没有 `fr` 字段，拒绝生成用例（反查不到需求的用例不许存在）：")
        for i in nofr: print("   · " + i)
        print("\n⭐ 这不是脚本挑剔：没有 FR/AC 的用例一旦生成，就会被当成需求本身执行。")
        return 1

    os.makedirs(out_dir, exist_ok=True)
    by_surface = {}
    for f in flows:
        fr = f['fr'][0] if f.get('fr') else 'FR-???'
        key = fr.split('-')[1][:2] if '-' in fr else '00'
        surface = 'F-' + key
        steps, expects = [], []
        for s in f.get('steps') or []:
            t = step_text(s)
            if t: steps.append(t)
            expects += expect_text(s)
        by_surface.setdefault(surface, []).append({
            "id": "TC-%s-%d" % (fr.replace('FR-', ''), len(by_surface.get(surface, [])) + 1),
            "title": f.get('name', f['id']), "fr": f['fr'], "flow": f['id'],
            "pre": "打开 demo，导航到 `%s`" % f.get('start', '#/'),
            "steps": steps, "expects": expects, "type": "关键路径"})

    # 状态类用例：每个「适用」的状态一条
    for s in states:
        surface = 'F-' + (s['id'].replace('f', '') or '00')
        for st in s.get('states') or []:
            if not st.get('applicable'): continue
            by_surface.setdefault(surface, []).append({
                "id": "TC-%s-S%s" % (s['id'], st['state']),
                "title": "%s 的 %s 状态可被触发且表现符合规格" % (s.get('name', s['id']), st['state']),
                "fr": ["（状态类，依据 spec/states.json）"], "flow": None,
                "pre": "场景开关 `scn=%s`" % st.get('trigger', '—'),
                "steps": [step_text(x) for x in (st.get('steps') or []) if step_text(x)]
                         or ["导航到该界面"],
                "expects": [st.get('visible') or "界面进入 %s 状态" % st['state']],
                "type": "状态"})

    written = []
    for surface, cases in sorted(by_surface.items()):
        path = os.path.join(out_dir, surface + '.md')
        if os.path.exists(path) and not force:
            print("⚠️ 已存在，跳过（要覆盖加 --force）：%s" % path); continue
        buf = ["# %s 用例（由 flows.json / states.json 生成的骨架）\n" % surface,
               "> ⛔ 这是**骨架不是成品**。只覆盖关键路径与状态可达两类；",
               "> 等价类 / 边界值 / 权限矩阵 / 安全用例仍要人补（见 `testcases-design.md`）。",
               "> 生成后必须跑 `coverage_check.py` 做双向对账 —— 本文件不声称任何覆盖率。\n"]
        for c in cases:
            buf.append("### %s　所属 %s" % (c['id'], " · ".join(c['fr'])))
            buf.append("**标题**：%s" % c['title'])
            buf.append("**前置**：%s" % c['pre'])
            buf.append("**步骤**：" + ("　".join("%d. %s" % (i + 1, s) for i, s in enumerate(c['steps'])) or "—"))
            buf.append("**预期**：" + ("；".join(c['expects']) or "—"))
            src = "spec/flows.json#%s" % c['flow'] if c['flow'] else "spec/states.json"
            buf.append("**依据**：%s　**类型**：%s　**优先级**：P1\n" % (src, c['type']))
        io.open(path, 'w', encoding='utf-8').write("\n".join(buf))
        written.append((surface, len(cases)))
    for s, n in written: print("✅ %s.md　%d 条" % (s, n))
    print("\n⚠️ 生成的是骨架：等价类/边界值/权限/安全用例仍要人补，且必须跑 coverage_check 双向对账。")
    return 0


# --------------------------------------------------------------- 自证（M8）
_FLOWS_OK = {"flows": [{"id": "FLOW-01", "name": "新建成功", "fr": ["FR-031", "AC-2"], "start": "#/create",
                        "steps": [{"do": "fill", "role": "textbox", "name": "标题", "value": "甲"},
                                  {"do": "click", "role": "button", "name": "提交"},
                                  {"do": "expect", "urlContains": "#/inbox"}]}]}
_FLOWS_NOFR = {"flows": [{"id": "FLOW-09", "name": "没写需求编号", "start": "#/x", "steps": []}]}
_STATES = {"surfaces": [{"id": "f01", "name": "列表", "states": [
    {"state": "empty", "applicable": True, "trigger": "empty", "visible": "引导文案"},
    {"state": "no-permission", "applicable": False, "why": "只读也能看"}]}]}


def _self_test():
    import tempfile, subprocess
    me = os.path.abspath(__file__)
    ok = True
    print("M8 自证 —— 生成 / 拒绝无需求编号 / 不覆盖已存在 / 无效输入\n")

    def mk(flows):
        d = tempfile.mkdtemp(prefix='f2t-')
        sd = os.path.join(d, 'spec'); os.makedirs(sd)
        json.dump(flows, io.open(os.path.join(sd, 'flows.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        json.dump(_STATES, io.open(os.path.join(sd, 'states.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        return sd, os.path.join(d, 'out')

    def call(sd, od, *extra):
        return subprocess.call([sys.executable, me, sd, od] + list(extra),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    sd, od = mk(_FLOWS_OK)
    cases = [
        # 🚨 2026-09-04：步骤缺 `do` 时此前抛原始 traceback、带出退出码 1，
        #    而 1 的语义是「有流程缺 fr」——**输入格式错误被伪装成业务结论**。
        ("正例：生成成功", call(sd, od), 0)]
    _BAD_STEP = {"flows": [{"id": "F1", "fr": ["FR-1"], "name": "x", "start": "#/x",
                            "steps": [{"expect": {"roleExists": "table"}}]}]}
    _BAD_DO = {"flows": [{"id": "F1", "fr": ["FR-1"], "name": "x", "start": "#/x",
                          "steps": [{"do": "swipe"}]}]}
    sd3, od3 = mk(_BAD_STEP)
    cases.append(("反例 步骤缺 `do` → 报 2（跑不了），不许伪装成「缺 fr」的 1", call(sd3, od3), 2))
    sd4, od4 = mk(_BAD_DO)
    cases.append(("反例 `do` 值不认识 → 报 2", call(sd4, od4), 2))
    # 生成的内容必须真的带 FR 反查与步骤（否则「生成了」等于没生成）
    body = ""
    for f in os.listdir(od): body += io.open(os.path.join(od, f), encoding='utf-8').read()
    good_body = ("所属 FR-031" in body and "点击 button「提交」" in body
                 and "地址栏含「#/inbox」" in body and "scn=empty" in body)
    cases.append(("正例：产物含 FR 反查 + 步骤 + 预期 + 状态用例", 0 if good_body else 9, 0))
    sd2, od2 = mk(_FLOWS_NOFR)
    cases.append(("反例①：流程缺 fr → 拒绝生成", call(sd2, od2), 1))
    cases.append(("反例②：已存在不覆盖（不加 --force 也返 0 但跳过）", call(sd, od), 0))
    cases.append(("反例③：spec 目录不存在 → 报 2", call('/nope/spec', od), 2))
    for name, got, want in cases:
        g = got == want; ok &= g
        print("  %s %-46s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))
    print("\n%s" % ("✅ 自证通过" if ok else "❌ 自证失败：先修"))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    if '--self-test' in sys.argv: sys.exit(_self_test())
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2: print(__doc__); sys.exit(2)
    sys.exit(gen(args[0], args[1], '--force' in sys.argv))
