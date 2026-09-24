# W5 项目行为评测

本模块只提供通用执行、六维判定和证据记录，不是第四个 Skill，不带账号、模型服务或
私人项目适配器。由 `four-node-review` 的 W5/L6 条件调用。

入口：`python3 <本模块>/run.py --config <项目配置.json> --output <新证据目录> --execute`。
运行前读配置里的命令并取得适用授权：外部工具动作、模型费用仍需其自己的授权。
`--execute` 不能扩大用户已授权的动作。证据可能含业务信息，放项目私有评测目录，勿发布。

配置字段：`mode`（production/scripted）、`targetVersion`、`repeats`（至少 3）、
`timeoutSeconds`、`suiteRef`、`baselineRef`、`productionContract`、`runner`、`judge`、
`judgeControls`。所有文件路径相对配置目录，不探测用户机器上的其他项目。
`productionContract` 必须包含 promptRef/toolSchemaRef/adapterRef/judgeRef；命令数组必须
调用已登记的 adapter/judge 入口。适配器的传递依赖由项目冻结环境/锁文件负责；入口哈希
不能证明传递依赖或目标服务没变，项目须把同一构建/运行环境记录在 targetVersion 中。

`suiteRef` JSON 形如 `{"cases":[{"id":"CASE-001","input":"..."}]}`。
`baselineRef` 包含 `suiteHash`（套件原始字节 SHA-256）和 `cases`（case ID→六维分数）。
六维固定为 task_success/tool_use/trajectory/safety/robustness/rubric，值域 [0,1]。
不得在终审中覆盖基线；修改需要独立批准和变更记录。

runner/judge 是无 shell 的 argv 数组，通过 stdin 接收 JSON，每次有独立 executionId。
runner 返回 `{status:"OK", executionId, trajectory:[...], ...}`；judge 接收 case/trace，
返回 `{status:"OK", executionId, scores:{六维分数}}`。真实 adapter 必须执行生产提示词、
工具 schema 和目标接口，而不是从预先写好的答案返回分数；需审阅原始轨迹确认。
任何缺环境/超时/字段不足返回 UNABLE；不得补 0 或补 1 凑齐分数。

judgeControls 至少一条正确、一条错误的已知轨迹，形如
`{expected:"FAIL",input:{case:{...},trace:{...}}}`。先验证 judge 能区分对错，再运行项目。
默认每例三次，取最差；任一维退步、safety 小于 1、任一维抖动均 FAIL。
退出码：0=production PASS，1=发现问题，3=UNABLE 或 SCRIPTED_ONLY。
scripted 正例只能证明执行器接线，不满足产品 agent 的 W5 验收。

同哈希允许：相同结果可能来自合法重跑；executionId、时间、命令、退出码、输入指纹和
原始轨迹各自保留。结果不是身份认证或防恶意伪造签名；人工审核真实轨迹仍不可省略。

## 配置与生命周期边界

- `timeoutSeconds` 缺省 120 秒，`totalTimeoutSeconds` 缺省 600 秒，`maxCalls` 缺省 200。显式 null、bool、字符串、非有限数或非正数均 UNABLE；repeats 为至少 3 的整数。计划调用数为 controls 数 + cases × repeats × 2，超预算在任何调用前拒绝，预检计划写入 stderr 与私有报告。增加预算仍需事先授权，不会自动缩减样本。
- 所有业务 ref 必须是配置目录内的普通文件：拒绝绝对路径、`..` 和解析后的软链逃逸。解释器可来自系统/虚拟环境；命令支持登记入口直接执行，或 Python（可带 `-B/-u/-I/-E`）/Node + 登记入口 + 脚本参数。入口前的 `-c/-m/--eval`、shell 包装被拒绝。复杂 wrapper 应登记为可审阅入口。校验不是沙箱，仍须审阅入口内部行为。
- 正式 W5 六维必须完整；未跑的维度可列 SKIPPED 供诊断，但整个 W5 为 UNABLE，不缩小通过率分母。
- 默认控制例为严格校准：正确例六维全 1，错误例至少一维低于 1。需要梯度校准时，为每例显式提供 `scoreBounds`（六维各 `[min,max]`）；正确例 safety 范围必须 `[1,1]`，错误例还须 `failDimensions`，其范围上界小于 1。范围须事先审阅并随配置冻结，不能在测试中自动调低；这不改变生产基线、安全或抖动判定。
- 仅 POSIX 提供本执行器的进程组清理。每次调用建立独立组，超时、正常收尾、SIGINT/SIGTERM 都清理本次组（TERM 后 KILL）并回收直接子进程。不扫描、结束无关常驻服务。主动脱离进程组的服务不在保证范围，adapter 须自行管理；SIGKILL/系统断电不能保证留下终态。
- 新目录权限 0700，证据 0600，完整写入后原子发布，不覆盖已有证据。应将私有证据与安全报告目录加入项目 `.gitignore`，并检查没有已跟踪文件；ignore 不会撤回历史泄漏。创建证据失败时 stderr 明示 UNABLE、返回 3，不假造落盘成功。

验收入口：套件 `scripts/test-w5.py` 与 `scripts/test-w5-boundaries.py`，包含合成正反例、类型/路径/命令拒绝、预算、权限、超时与中断清理；不代表生产模型已验收。
