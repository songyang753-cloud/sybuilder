#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞品遍历串行编排门禁 —— 「一次只跑一件」从散文变成机器红线。

═══ 它治的病（2026-09-17 用户当场点名）═══
竞品遍历每个都起一个浏览器 + node 进程，并发跑会把内存打爆。
「一次只跑一件」这条 CLAUDE.md 写着、记忆里写着，我**照样并发、照样爆**。
⭐ M11 的判决用在这里：以散文存在的纪律等于不存在 ⇒ 把「串行」变成机器保证：
   1) 唯一的串行编排器 `competitor-sweep.mjs`（for…of + await 逐个，⛔ 无并发旋钮）；
   2) 本门禁守着它不许退化成并发，并拦下任何**绕过它直接起 competitor-walk** 的脚本。

═══ 它验不了什么（诚实边界）═══
⛔ 本门只管**仓库里的脚本**。它拦不住我在会话里 ad-hoc 并行起多个 Bash / 子代理——
   那一层靠纪律 + competitor-sweep 存在（有了正规串行路径，就没有理由再手搓并发）。
⛔ 也不验串行编排器**跑得对不对**，只验它的**形状是串行**、且没人绕过它。

用法: serial-orchestration-gate.py [--root <skill 根>] ｜ --self-test
退出码: 0=干净 1=有并发/绕过编排器 2=跑不了
"""
import io, os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEP = 'competitor-sweep.mjs'   # 唯一允许起 competitor-walk 的串行编排器
WALK = 'competitor-walk.mjs'     # 叶子工具本身，不是编排器
LAUNCH = re.compile(r'\b(spawn|exec|execFile|execFileSync|fork)\b')
PARALLEL = re.compile(r'Promise\.(all|allSettled)\s*\(')
SERIAL_FOR = re.compile(r'for\s*\(')


def _read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except Exception as e:
        print("UNABLE: 读不到 %s (%s)" % (p, e), file=sys.stderr)
        sys.exit(2)


def _strip_comments(src):
    """量代码不量注释：剥 /* */ 块注释与 // 行注释。
    ⚠️ `(?<!:)` 放过 URL 里的 `://`。⭐ 必须先剥——competitor-sweep.mjs 的注释里
       写着「不许改成 Promise.all」，不剥就会把这条警告当成违规（量错对象）。"""
    src = re.sub(r'/\*[\s\S]*?\*/', '', src)
    src = re.sub(r'(?m)(?<!:)//.*$', '', src)
    return src


def scan(root):
    bad = []
    for p in sorted(glob.glob(os.path.join(root, 'scripts', '*.js')) +
                    glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        fn = os.path.basename(p)
        if fn == WALK:
            continue                              # 叶子工具，不在量程内
        code = _strip_comments(_read(p))
        if fn == SWEEP:
            # 唯一的编排器：守住它的串行形状
            if PARALLEL.search(code):
                bad.append((fn, 'sweep-parallel',
                            '串行编排器里出现 Promise.all/allSettled —— 会同时起多个浏览器，正是要防的事',
                            '改回 for…of + await 逐个（上一个子进程 close 才起下一个）'))
            if not (SERIAL_FOR.search(code) and 'await' in code):
                bad.append((fn, 'sweep-not-serial',
                            '编排器没有「for 循环里 await 逐个」的串行形状',
                            '用 for…of 串行 await runOne，⛔ 不要 map+并发'))
            continue
        # 其余任何脚本：起 competitor-walk = 绕过串行编排器 = 会并发的路径
        if 'competitor-walk' in code and LAUNCH.search(code):
            bad.append((fn, 'bypass-orchestrator',
                        '绕过 competitor-sweep 直接起 competitor-walk —— 那正是会并发的路径',
                        '统一走 competitor-sweep.mjs（它按 for…of 串行起）'))
    return bad


def main(root=None):
    root = root or ROOT
    sweep = os.path.join(root, 'scripts', SWEEP)
    if not os.path.exists(sweep):
        print("❌ 缺 scripts/%s —— 没有串行编排器，竞品遍历就没有一条「串行」的正规路径，"
              "人会各自 spawn 然后并发" % SWEEP)
        return 1
    bad = scan(root)
    for fn, key, why, fix in bad:
        print("❌ [%s] %s" % (key, fn))
        print("   %s" % why)
        print("   ⇒ %s" % fix)
    if not bad:
        print("✅ 竞品遍历只走串行编排器 %s，没有并发、没有旁路" % SWEEP)
    print("⚠️ 本门只管仓库脚本——⛔ 拦不住会话里 ad-hoc 并行起 Bash/子代理，那层靠纪律 + 本编排器的存在。")
    return 1 if bad else 0


def self_test():
    import tempfile, shutil
    t = tempfile.mkdtemp(prefix='serial-'); ok = True
    os.makedirs(os.path.join(t, 'scripts'))

    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-56s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    def w(name, s):
        io.open(os.path.join(t, 'scripts', name), 'w', encoding='utf-8').write(s)

    def rm(name):
        os.remove(os.path.join(t, 'scripts', name))

    SERIAL = ("import {spawn} from 'node:child_process';\n"
              "for (const c of list) {\n"
              "  await new Promise(r => spawn('node',['competitor-walk.mjs',c.port]).on('close',r));\n"
              "}\n")

    case("反例 连 competitor-sweep.mjs 都没有 → 判红", main(t), 1)
    w(SWEEP, SERIAL)
    case("正例 串行编排器（for…of + await）→ 放行", main(t), 0)

    # 关键正例：注释里写 Promise.all 的警告，不许被当成违规（量错对象）
    w(SWEEP, "// ⛔ 不许改成 Promise.all(list.map(...))\n" + SERIAL)
    case("正例 注释里提到 Promise.all（警告语）→ 不误伤", main(t), 0)

    w(SWEEP, "import {spawn} from 'node:child_process';\n"
             "await Promise.all(list.map(c => new Promise(r => spawn('node',['competitor-walk.mjs',c.port]).on('close',r))));\n")
    case("反例 编排器用 Promise.all 并发 → 判红", main(t), 1)
    w(SWEEP, SERIAL)   # 复原

    w('rogue.mjs', "import {spawn} from 'node:child_process';\n"
                   "list.forEach(c => spawn('node',['competitor-walk.mjs',c.port]));\n")
    case("反例 别的脚本绕过编排器直起 competitor-walk → 判红", main(t), 1)
    rm('rogue.mjs')

    w('unrelated.mjs', "import {spawn} from 'node:child_process';\nspawn('ls',['-l']);\n")
    case("正例 spawn 别的东西、不碰 competitor-walk → 不误伤", main(t), 0)
    rm('unrelated.mjs')

    w(WALK, "// 用法: node competitor-walk.mjs <port>\nconsole.log('leaf');\n")
    case("正例 叶子工具 competitor-walk.mjs 自身 → 不误伤", main(t), 0)

    shutil.rmtree(t, ignore_errors=True)
    print("\n%s" % ("✅ 串行编排门禁自证通过" if ok else "❌ 自证失败"))
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
