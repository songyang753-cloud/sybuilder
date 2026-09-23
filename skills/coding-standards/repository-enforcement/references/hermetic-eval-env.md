# Hermetic 评测/构建环境 —— 让「本地信号 = CI 信号」

> 借鉴自 gstack 的 `test/helpers/hermetic-env.ts` + `test/hermetic-wiring.test.ts`(2026-09-09 评估借入),
> 改写为栈无关配方。**上游信条只覆盖了 hermetic 的一半**(「工具与依赖版本钉死」),这份补另一半:
> **运行期环境隔离**——子进程不许继承操作者机器的会话状态、配置目录、凭据。

## 为什么这是「假绿的元形态」

版本钉死解决「今天过明天也过」;但还有一种更隐蔽的不可复现:

- 测试/评测在**你的机器上全绿**,推到 CI **全红**——因为本地子进程继承了你的 `~/.config`、你登录过的 token、你的 shell env,而 CI 是干净的。
- 或者更糟:本地绿**正是因为**借了操作者的状态(你本机装了某工具/配过某密钥),CI 没有 ⇒ 你以为测过了,其实**从没在等价环境里测过**。

隔离机制本身一旦坏掉(一个 wiring bug 让子进程重新继承了操作者环境),**整条评测层的可信度一次性蒸发,而没有任何东西报错**。这就是为什么它需要一道**守着隔离机制的门**(见下「自守」)。

## 配方(四条,栈无关)

### 1. 子进程环境**白名单洗净**,不是黑名单剔除

构造子进程的 env 时,从**空**开始,只显式放行必需项:
`PATH` / `HOME`(或指向临时目录)/ 代理与证书(`HTTPS_PROXY`/`SSL_CERT_FILE`)/ **明确点名**的凭据(如 `ANTHROPIC_API_KEY`)。
主动**丢弃**会污染的:操作者的 `*_CONFIG_DIR`、CI/编排器注入的 `CI_*`/`CONDUCTOR_*`、以及不该被测试读到的 token(`GH_TOKEN` 等)。

> 黑名单(「删掉这几个已知的坏变量」)必然漏——新加一个污染变量就漏一个(同 coding-standards **B5**:枚举式守卫)。白名单默认拒,新变量默认不进。

```
# Go
cmd.Env = []string{"PATH="+os.Getenv("PATH"), "HOME="+tmpHome, "ANTHROPIC_API_KEY="+key}
# Node
spawn(bin, args, { env: { PATH: process.env.PATH, HOME: tmpHome, ...allowlisted } })  // 不要 ...process.env
# Python
subprocess.run(cmd, env={"PATH": os.environ["PATH"], "HOME": tmp_home, **allowlisted})  # 不要 os.environ.copy()
```

### 2. 隔离配置目录,不用操作者的

给子进程一个**全新的临时 config dir**(`CLAUDE_CONFIG_DIR` / `XDG_CONFIG_HOME` / 临时 `HOME`),否则它会读到操作者的全局配置、已装插件/MCP、`~/.gitconfig` 等,让测试行为依赖「这台机器碰巧怎么配的」。CI 上这些都不存在。

### 3. 逃生阀 + 调用时求值 + override 最后合并(三个易错点)

- **逃生阀**:留一个 `HERMETIC=0` 开关字节级还原旧行为,给「就是要对着真实操作者状态调试」用。默认开启净室。
- **调用时求值,不是模块加载时**:`isHermetic()` 要在**每次构造 env 时**读开关,不能在文件顶部读一次存进常量——否则(尤其 ESM/import 提升)开关的赋值可能发生在读取之后,净室被**静默忽略**。
- **per-test override 最后 spread**:测试想故意注入某个变量(受控污染)时,它的 override 必须**最后**合并进 env——这是唯一合法的「再污染」入口,显式且可见。

### 4. ⭐ 自守:给隔离机制本身上一道 static tripwire

隔离机制坏掉不会报错,所以要有一道**免费层(不花 API、秒级)的 static-grep 门**守着它:

> **任何 runner 只要把「原始进程环境」整个 spread 进子进程**(`...process.env` / `os.environ.copy()` / `cmd.Env = os.Environ()`)**,CI 就红。**

这道门是「门禁的门禁」——它保证没人能悄悄把净室拆掉(对应 coding-standards **B20**:一处改动不得让整层守卫静默失效)。把它写成一条扫源码的测试,钉在 CI 的 gate 层。

## 验证这份隔离**真有牙**(别信没验过的门)

按 coding-standards **D20/D3** 自证,不能光写不验:

1. **反向**:故意在某个 runner 里写 `...process.env`(或 `os.environ.copy()`),跑那道 static tripwire —— **必须红**。红不了 = 门没牙,等于没有。
2. **正向**:移除污染,tripwire 变绿;同时一个真实测试在净室里仍能跑通(白名单没洗掉它真正需要的东西)。
3. 两向都验过,才能声称「本地信号 = CI 信号」。只跑正向 = 只证明了它现在是绿的,没证明它**会**红。

## 挂载点

- **阶段 2(硬化门禁)**:把「白名单洗净 + 隔离 config dir + static tripwire」作为评测/E2E 类门禁的**前置要求**——一条不 hermetic 的评测门禁,它的绿不可信。
- **阶段 5(验证收尾)**:诚实收尾时,若声称「测过了」,必须能回答「在与 CI 等价的净室里测的吗?」——答不上就标 `未验证`(coding-standards A19:不合格不许洗成没能测的反面——没在等价环境测过,也不许说成测过)。
