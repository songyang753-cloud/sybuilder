#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CDP 落地细节复用门禁 —— 散文教训拦不住重写，能拦住的是这道门。

═══ 它治的病 ═══
`references/competitive-research.md:503` 一字不差写着「⛔ 别取 `/json/list` 的 `t[0]`」，
连 QClaw 的 `#/sandbox-guard-bar` 都点名了。2026-09-17 重写遍历器时**照样踩进去**，
拿到 0 个控件，而脚本正常退出 0 —— 差一点得出「这个产品界面是空的」这个错误结论。

不是不够认真：写代码时读的是任务与记忆，不会去检索 1300 行文档的第 503 行。
⭐ 同一次实测的对照：抄 `grab.sh` 的部分（启动/挪虚拟屏/pkill）**一次通过**，
   凭记忆重写的部分（WebSocket 处理 / target 选择）**全踩坑**。

⇒ 结论：**落地细节以可 require 的模块存在才有约束力；以散文存在等于不存在。**
   本门禁就是那个约束：碰 CDP 的脚本必须复用 `scripts/_cdp.js`，⛔ 不许自己写。

═══ 它验不了什么 ═══
⛔ 验不了复用之后用得对不对，也验不了 `_cdp.js` 自己是否正确。
   它只保证「不再各写一份、各踩一遍」。

用法: cdp-reuse-gate.py [--root <skill 根>] ｜ --self-test
退出码: 0=干净 1=有脚本自己重写了 CDP 落地细节 2=跑不了
"""
import io, os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = '_cdp.js'

# 每条：(键, 正则, 人话, 该用什么代替)
SMELLS = [
    ('target-by-shape',
     re.compile(r"""\.find\([^)]*type\s*===\s*['"]page['"]|json/list[^\n]*\)\s*\)\.json\(\)[\s\S]{0,200}?\[0\]|list\[0\]|targets\[0\]"""),
     '按**形态**选 CDP target（type===page / [0]）—— 会选中守卫栏、加载页这类 overlay，'
     '枚举出 0 个控件而脚本正常退出 0',
     "connect(port) —— 它按**能力**选：能枚举到 ≥3 个可点击控件的才算主窗口"),
    ('raw-ws-parse',
     re.compile(r"""JSON\.parse\(\s*(?!.*\.data)([a-zA-Z_$][\w$]*)\s*\)[^\n]*\n?[^\n]*(?:addEventListener\(['"]message|onmessage)"""),
     'WebSocket 消息直接 JSON.parse 事件对象 —— Node 原生 WS 给的是 MessageEvent，'
     '会得到 "[object MessageEvent]"',
     'rpc(getWs) —— 它已经取 ev.data'),
    ('own-enumerator',
     re.compile(r"""querySelectorAll\(\s*['"][^'"]*\brole=button\b[^'"]*['"]"""),
     '自己写一份可点击元素枚举器 —— 与 probe 用不同选择器会导致「probe 绿而枚举为 0」',
     'ENUM_JS —— probe 与真实枚举必须同源'),
]

# 🚨🚨 光标安全（2026-09-17 用户强制）：遍历只用合成事件，⛔ 绝不劫走用户真实鼠标。
# 之前几次把用户光标弄消失、锁在机器外。这两条对**所有**遍历脚本查（不止 CDP）。
CURSOR_SMELLS = [
    ('physical-mouse',
     re.compile(r"CGWarpMouseCursorPosition|CGEventCreateMouseEvent|\bcliclick\b|"
                r"require\(['\"]robotjs|@nut-tree|['\"]click at\b"),
     '用了物理鼠标 API（会把用户真实光标挪走/霸占，把用户锁在机器外）',
     "合成事件:CDP `Input.dispatchMouseEvent` / Playwright(connectOverCDP) / AX `AXPress`"),
    ('hide-cursor',
     re.compile(r"CGDisplayHideCursor"),
     '隐藏了系统光标（用户看不到鼠标、无法操作)',
     "⛔ 不隐藏光标;遍历在 DeskPad 虚拟屏上用合成事件操作,物理光标留主屏"),
]


def _read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except Exception as e:
        print("UNABLE: 读不到 %s (%s)" % (p, e), file=sys.stderr)
        sys.exit(2)


def scan(root):
    bad = []
    for p in sorted(glob.glob(os.path.join(root, 'scripts', '*.js')) +
                    glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        fn = os.path.basename(p)
        src = _read(p)
        # 🚨 光标安全:对**所有**遍历脚本(含 _cdp.js)查禁用的物理鼠标/隐藏光标 API
        for key, rx, why, fix in CURSOR_SMELLS:
            if rx.search(src):
                bad.append((fn, key, why, fix, False))
        if fn == CANON:
            continue
        if 'CDP' not in src and 'json/list' not in src and 'webSocketDebuggerUrl' not in src:
            continue                      # 不碰 CDP 的脚本不在量程内(仅 CDP-target 类判据)
        # ⛔ **自己启动浏览器**的脚本不在量程内 —— 那是它自己的进程、自己的页面，
        #    只有一个 target，按形态选完全正确。本门治的是**连接外部应用**：
        #    别人的 Electron 有守卫栏 / 加载页 overlay，形态判据会选错。
        #    ⚠️ 首版没这个条件，当场误伤 `_browser.mjs` 与 `browser-audit.mjs`
        #    （S6 自启 headless Chrome 审计自己渲染的 demo）——门不许惩罚正确代码。
        if re.search(r'findChrome|spawn\(|child_process|puppeteer\.launch|chromium\.launch', src):
            continue
        uses = re.search(r"require\([^)]*_cdp(?:\.js)?['\"]\)", src)
        for key, rx, why, fix in SMELLS:
            if rx.search(src):
                bad.append((fn, key, why, fix, bool(uses)))
    return bad


def main(root=None):
    root = root or ROOT
    canon = os.path.join(root, 'scripts', CANON)
    if not os.path.exists(canon):
        print("❌ 缺 scripts/%s —— 落地细节没有可复用的落点，"
              "这道门也就无从要求复用" % CANON)
        return 1
    bad = scan(root)
    for fn, key, why, fix, uses in bad:
        print("❌ [%s] %s" % (key, fn))
        print("   %s" % why)
        print("   ⇒ 用 %s 的 %s" % (CANON, fix))
        if uses:
            print("   ⚠️ 它已经 require 了 %s 却还自己写了一份 —— 两份并存比没有更糟" % CANON)
    if not bad:
        print("✅ 碰 CDP 的脚本都复用 scripts/%s，没有自己重写落地细节" % CANON)
    print("⚠️ 本门**验不了**复用之后用得对不对，也验不了 %s 自身正确——"
          "它只保证不再各写一份、各踩一遍。" % CANON)
    return 1 if bad else 0


def self_test():
    import tempfile, shutil
    t = tempfile.mkdtemp(prefix='cdp-'); ok = True
    os.makedirs(os.path.join(t, 'scripts'))

    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-52s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    def w(name, s):
        io.open(os.path.join(t, 'scripts', name), 'w', encoding='utf-8').write(s)

    case("反例 连 _cdp.js 都没有 → 判红", main(t), 1)
    w(CANON, '// canonical\nmodule.exports={};\n')
    case("正例 没有任何碰 CDP 的脚本 → 放行", main(t), 0)

    w('good.js', "const {connect}=require('./_cdp.js');\n// webSocketDebuggerUrl 由它处理\n")
    case("正例 复用了正本 → 放行", main(t), 0)

    w('bad1.js', "const l=await (await fetch(u+'/json/list')).json();\nconst t=l.find(x=>x.type==='page');\n")
    case("反例 按形态选 target（type===page）→ 判红", main(t), 1)
    os.remove(os.path.join(t, 'scripts', 'bad1.js'))

    w('bad2.js', "const l=await (await fetch('http://x/json/list')).json();\nconst t=l[0];\nws=new WebSocket(t.webSocketDebuggerUrl);\n")
    case("反例 取 list[0] → 判红", main(t), 1)
    os.remove(os.path.join(t, 'scripts', 'bad2.js'))

    w('bad3.js', "// webSocketDebuggerUrl\nconst els=document.querySelectorAll('a,button,[role=button]');\n")
    case("反例 自己写枚举器 → 判红", main(t), 1)
    os.remove(os.path.join(t, 'scripts', 'bad3.js'))

    w('selflaunch.mjs', "import {spawn} from 'child_process';\n// 自起 headless Chrome\n"
                        "const l=await (await fetch('http://127.0.0.1:9222/json/list')).json();\n"
                        "const pg=l.find(t=>t.type==='page');\n")
    case("正例 自启浏览器的脚本按形态选 target → 不误伤（它只有一个 target）", main(t), 0)
    os.remove(os.path.join(t, 'scripts', 'selflaunch.mjs'))

    w('unrelated.js', "console.log('我不碰 CDP');\nconst x=[1,2,3];\nconst y=x[0];\n")
    case("正例 不碰 CDP 的脚本用 x[0] → 不误伤", main(t), 0)

    # 🚨 光标安全双向自证
    w('badcur1.mjs', "import {spawn} from 'node:child_process';\nspawn('cliclick',['c:100,100']);\n")
    case("反例 物理鼠标 cliclick → 判红", main(t), 1)
    os.remove(os.path.join(t, 'scripts', 'badcur1.mjs'))
    w('badcur2.mjs', "// 遍历前\nCGDisplayHideCursor();\n")
    case("反例 隐藏系统光标 CGDisplayHideCursor → 判红", main(t), 1)
    os.remove(os.path.join(t, 'scripts', 'badcur2.mjs'))
    w('goodcur.mjs', "// 合成事件,不动物理光标\nc.send('Input.dispatchMouseEvent',{type:'mousePressed',x:1,y:1});\n")
    case("正例 合成事件 Input.dispatchMouseEvent → 不误伤", main(t), 0)

    shutil.rmtree(t, ignore_errors=True)
    print("\n%s" % ("✅ CDP 复用门禁自证通过" if ok else "❌ 自证失败"))
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

    def _entry():
        sys.exit(main())

    _main_guarded(_entry)
