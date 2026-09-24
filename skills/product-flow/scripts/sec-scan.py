#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全基线机械扫描 —— SEC-1/3/8/9 的门禁实现。

为什么需要它：
  `s9-quality-gates.md` 把安全标为「最高优先级，其余都可以让路」，
  然后用一张**人勾的清单**去守它 —— 而本 skill 自己的判词是
  「模板末尾那份自检清单是人勾的……**清单挡不住任何东西，门禁才挡得住**」。
  同一条判词对 PRD 成立，对安全清单一样成立。

⚠️ 诚实边界（报结果必须连这段一起报）：
  SEC-1~10 里只有 4 条可机械查，本脚本只做这 4 条。
  **其余 6 条（输入校验 / XSS / CSRF / 认证授权分离 / 限流 / 依赖与配置）
  只能人工与专项审查，它们的合法结论是「已人工审查，发现 N 处」，不是 ✅。**
  本脚本报绿 ≠ 安全达标，只 ≠ 有机械可查的破绽。

用法: sec-scan.py <文件或目录> [--json] [--list-rules]   |   --self-test
退出码: 0=无发现 1=有发现 2=跑不了
"""
import io, os, re, sys, json, glob, tempfile, subprocess

SKIP_DIR = {'.git', 'node_modules', 'dist', 'build', '.venv', '__pycache__', 'vendor'}
EXT = {'.py', '.js', '.mjs', '.ts', '.tsx', '.jsx', '.go', '.java', '.rb', '.php',
       '.sh', '.yml', '.yaml', '.json', '.env', '.toml', '.ini'}

RULES = [
    ("SEC-1", "hardcoded-secret", "疑似硬编码密钥/口令/token",
     re.compile(r'''(?ix)
        (?:api[_-]?key|secret|passwd|password|token|private[_-]?key|access[_-]?key)
        \s*[:=]\s*["'][^"'\s]{8,}["']'''),
     "一处硬编码往往意味着还有第二处；**进过版本库即视为泄露，必须轮换**，删掉那行不算修复"),
    ("SEC-3", "sql-concat", "SQL/命令拼接了变量（应参数化）",
     re.compile(r'''(?ix)
        (?:select|insert|update|delete)\s[^\n;]{0,120}?
        (?:\+\s*\w+|\$\{|%\s*\(|%s["']\s*%|f["'][^"']*\{)'''),
     "参数化查询是唯一解；命令执行禁止拼接用户输入"),
    ("SEC-8", "error-leak", "对外错误信息可能泄露堆栈/内部路径/SQL",
     re.compile(r'''(?ix)
        (?:res\.|response\.|return\s|send\(|json\(|write\()[^\n]{0,60}
        (?:traceback|stack(?:trace)?|e\.stack|err\.stack|__file__|sqlerror|sqlstate)'''),
     "对外只给「用户名或密码错误」这类不暴露存在性的措辞；详细信息只进服务端日志"),
    ("SEC-9", "log-sensitive", "日志里落了敏感字段",
     re.compile(r'''(?ix)
        (?:log(?:ger)?\.\w+|console\.(?:log|info|warn|error)|print)\s*\([^\n)]{0,120}
        (?:password|passwd|token|id[_-]?card|身份证|手机号|bank[_-]?card|cvv|secret)'''),
     "密码/token/身份证/手机号/支付信息不进日志，必要时脱敏后再记"),
]

def files_of(target):
    if os.path.isfile(target): return [target]
    out = []
    for root, dirs, fs in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in fs:
            if os.path.splitext(f)[1] in EXT: out.append(os.path.join(root, f))
    return out

def scan(target):
    hits = []
    for p in files_of(target):
        try: s = io.open(p, encoding='utf-8', errors='replace').read()
        except Exception: continue
        for sec, rid, desc, pat, why in RULES:
            for m in pat.finditer(s):
                line = s[:m.start()].count('\n') + 1
                # Do not echo source lines, secret prefixes or unrelated secrets
                # adjacent to a match. Location and rule are sufficient to fix it.
                txt = '<匹配 %d 字符；内容不回显>' % len(m.group(0))
                hits.append({"sec": sec, "rule": rid, "desc": desc, "why": why,
                             "file": p, "line": line, "text": txt[:160]})
    return hits

def main():
    if '--list-rules' in sys.argv:
        for sec, rid, desc, _, _ in RULES: print("%-6s %-18s %s" % (sec, rid, desc)); return 0
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a: print(__doc__); return 2
    if not os.path.exists(a[0]): print("UNABLE: 不存在 %s" % a[0], file=sys.stderr); return 2
    hits = scan(a[0])
    if '--json' in sys.argv:
        print(json.dumps({"found": len(hits), "hits": hits}, ensure_ascii=False, indent=1))
        return 1 if hits else 0
    for h in hits:
        print("❌ [%s/%s] %s" % (h["sec"], h["rule"], h["desc"]))
        print("     %s:%d  %s" % (h["file"], h["line"], h["text"]))
        print("     → %s" % h["why"])
    print("\n结论：%s" % ("发现 %d 处" % len(hits) if hits else "机械层无发现"))
    print("⚠️ 只覆盖 SEC-1/3/8/9 四条。其余 6 条（输入校验/XSS/CSRF/认证授权分离/限流/依赖配置）")
    print("   **只能人工与专项审查**，合法结论是「已人工审查，发现 N 处」，不是 ✅。")
    print("⚠️ 命中任一条 → 先修，**并检查同类问题在别处是否还有**。")
    return 1 if hits else 0

BAD = '''
API_KEY = "sk-live-abcdef123456789"
def q(uid):
    cur.execute("SELECT * FROM users WHERE id = " + uid)
def h(e):
    return response.json({"err": e.stack})
logger.info("login user=%s password=%s" % (u, password))
'''
GOOD = '''
API_KEY = os.environ["API_KEY"]
def q(uid):
    cur.execute("SELECT * FROM users WHERE id = %s", (uid,))
def h(e):
    log.exception(e); return response.json({"err": "internal"})
logger.info("login user=%s", u)
'''

def self_test():
    t = tempfile.mkdtemp(prefix="sec-")
    def w(n, c):
        p = os.path.join(t, n); io.open(p, 'w', encoding='utf-8').write(c); return p
    def run(p): return subprocess.run([sys.executable, os.path.abspath(__file__), p, '--json'],
                                      capture_output=True, text=True)
    ok = True
    print("M8 自证 —— 正例绿 / 每条规则各造一个反例必红 / 无效输入报 2 不报 0\n")
    r = run(w('good.py', GOOD)); good = r.returncode == 0; ok &= good
    print("  %s %-30s 期望 0 实得 %d" % ("✅" if good else "❌", "正例（全部合规写法）", r.returncode))
    hits = json.loads(run(w('bad.py', BAD)).stdout)["hits"]
    for sec, rid, desc, _, _ in RULES:
        killed = any(h["rule"] == rid for h in hits); ok &= killed
        print("  %s %-30s 反例必须被抓到" % ("✅" if killed else "❌", "%s %s" % (sec, rid)))
    # 不许打印密钥原值
    leak = any('sk-l' in h["text"] for h in hits)
    ok &= not leak
    print("  %s %-30s 报告里不许出现密钥原值或前缀（只报长度与位置）" % ("✅" if not leak else "❌", "不泄露密钥"))
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'nope')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g2 = rc == 2; ok &= g2
    print("  %s %-30s 期望 2 实得 %d" % ("✅" if g2 else "❌", "无效输入不返绿", rc))
    print("\n%s" % ("✅ 自证通过" if ok else "❌ 自证失败"))
    return 0 if ok else 1

if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    sys.exit(self_test() if '--self-test' in sys.argv else main())
