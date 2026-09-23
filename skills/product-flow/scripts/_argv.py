#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命令行参数守卫 —— 未知 `--flag` 必须报错，⛔ 不许静默丢弃。

═══ 为什么要有它 ═══

本 skill 里多道门禁曾各自手写这一行：

    a = [x for x in sys.argv[1:] if not x.startswith('--')]

它把**任何**以 `--` 开头的东西都当成「选项」滤掉 —— 包括**写错的选项**。
于是：

  · `element-identity-gate.py --spec X --demo Y`（正确写法是 `X --html Y`）
    ⇒ `--html` 不存在 ⇒ 内部 `html=None` ⇒ **整个 demo 侧检查从没跑过**，
       而门禁照常打印「✅ 通过」。实测：改用正确参数后当场暴露 32 处缺口。
  · `reconcile-gate.py G2 --prd X --demo Y`（正确写法是 `G2 X Y`）
    ⇒ 取值恰好按位置排对了，**碰巧对**；顺序一换就会拿 demo 当 PRD 解析。

⭐ **「跑不了」和「跑了没问题」折叠成同一个状态，就是 fail-open。**
   这一类 fail-open 不在判据里，在**参数解析**里 —— 判据写得再好也救不回来。

⭐ 2026-09-03 普查：`design-intent` / `retro` / `research` / `definition` /
   `doc-sync-guard` / `demo-anchor` 六道用的是同一个模式。
   **同一个习惯复制六次，就有六处同样的盲区。**

用法：
    from _argv import reject_unknown
    reject_unknown({'--json', '--self-test'}, "本门禁用位置参数：gate.py <file.md>")
"""
import sys


def reject_unknown(known, usage_hint='', argv=None):
    """遇到不在 `known` 里的 `--flag` 就 UNABLE(2) 退出。

    ⚠️ 只看形如 `--x` 的记号；负数、单横杠短选项与位置参数一律不管。
    ⚠️ 调用点必须在**解析之前**，否则错误的参数已经影响了后续取值。
    """
    argv = sys.argv[1:] if argv is None else argv
    unknown = [x for x in argv if x.startswith('--') and x.split('=')[0] not in known]
    if not unknown:
        return
    msg = "UNABLE: 不认识的参数 %s" % ' '.join(unknown)
    if usage_hint:
        msg += "；%s" % usage_hint
    msg += "（⛔ 静默忽略错误参数会让门禁只跑一半而照样报绿）"
    print(msg, file=sys.stderr)
    sys.exit(2)


def _self_test():
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(('  ✓ ' if cond else '  ✗ ') + name)
        ok = ok and cond

    import subprocess, os
    me = os.path.abspath(__file__)
    prog = ("import sys; sys.path.insert(0, %r); from _argv import reject_unknown; "
            "reject_unknown({'--json'}, '用法提示'); print('OK')" % os.path.dirname(me))

    def run(args):
        r = subprocess.run([sys.executable, '-c', prog] + args,
                           capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr)

    chk("已知参数放行", run(['--json', 'x.md'])[0] == 0)
    chk("位置参数放行", run(['x.md', 'y.md'])[0] == 0)
    bad_rc, bad_out = run(['--nope', 'x.md'])
    chk("反例：未知参数必须退 2 且点名错误参数（锚定 reject_unknown 判据）",
        bad_rc == 2 and '不认识的参数 --nope' in bad_out)
    chk("反例：未知参数的错误信息必须带用法提示（锚定 usage_hint 判据）",
        '用法提示' in bad_out)
    chk("`--json=1` 这种带等号的已知参数也放行", run(['--json=1'])[0] == 0)
    chk("单横杠短选项不拦（不在本守卫职责内）", run(['-v', 'x.md'])[0] == 0)
    print("\n%s" % ("✅ 自证通过：这道守卫会出声" if ok else "❌ 自证失败"))
    return ok


if __name__ == '__main__':
    if '--help' in sys.argv:
        print(__doc__ or '')
        print('用法: _argv.py --self-test')
        sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(0 if _self_test() else 1)
    print('UNABLE: 本模块只提供共享参数判据；请使用 --self-test', file=sys.stderr)
    sys.exit(2)
