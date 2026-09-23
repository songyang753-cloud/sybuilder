# SYBuilder

[English](README.en.md) · **中文**

**Evidence-driven product delivery skills**  
从调研到交付的证据驱动产品研发套件。

**开源开发预览版** · 原创部分 Apache-2.0 · 第三方材料保留各自许可。
可下载、使用、修改和再分发；不是已完成全部真实平台验收的稳定版。

SYBuilder 把三个可独立使用的 Skill 组成一条可对账的产品研发流程：

| Skill | 职责 | 不负责 |
|---|---|---|
| `product-flow` | 调研、PRD、设计交互、技术/算法/测试方案、开发切片、GUI 验收与复盘 | 不在流程文档里复制整套编码规范或终审规则 |
| `coding-standards` | 实现阶段的编码约束、诚实性门禁、反向测试与提交前自检；内置 `repository-enforcement/` 提供 CI、章程、ADR、CODEOWNERS 与棘轮模板 | 不替代产品决策或终审 |
| `four-node-review` | 交付前的风险分档、覆盖对账、对抗式证伪、QA/安全/性能终审 | 不代替日常 CI，也不倒写产品要求 |

## 为什么是套件，不是一个巨型 SKILL.md

三个 Skill 可以作为一个整体运行，但不共享一份无限增长的规则正文。它们通过产物、门禁和阶段绑定集成：

```text
product-flow 定义做什么、为什么做、用什么证据验收
     ↓ S8 联合方案 / S9 开发切片
coding-standards 约束实现时如何做，并产出可复核的门禁证据
     ↓ 可独立上线的切片
four-node-review 独立证伪并裁决能否交付
```

任何一环缺失都必须报 `UNABLE`，不得降级成“默认通过”。套件级契约见
[`shared/integration-contract.md`](shared/integration-contract.md)，机器可读清单见
[`shared/suite-contract.json`](shared/suite-contract.json)。

## 开箱能力

调研、制图、原型与仓库治理的规则和核心工具已随 SYBuilder 打包；不代表外部平台和所有专项评测已开箱验证：

- `product-flow/modules/` 内置研究、制图、设计质量和 HTML 原型能力。
- `coding-standards/repository-enforcement/` 内置仓库章程、CI、ADR、CODEOWNERS 与棘轮模板。
- `product-flow/adapters/` 对接飞书、钉钉、Figma 与真实浏览器/桌面 GUI。
- 飞书与钉钉共享同一 Markdown 语义源和证据清单，但一次运行只选择一个远端正本。

平台本身不被复制进仓库：飞书使用官方 `lark-cli`，钉钉使用官方 `dws`，Figma 使用
官方 MCP，浏览器使用本机已授权会话。缺少某个平台时只对该平台报告 `UNABLE`。
完整的核心/可选依赖与降级边界见 [`DEPENDENCIES.md`](DEPENDENCIES.md)。

## 安装

先从本仓库 GitHub 页面的 **Code → Download ZIP** 下载并解压（也可以复制 HTTPS
地址后用 Git 克隆），进入仓库目录，再选一个你的 agent 能发现 Skill 的目录：

```bash
./install.sh /absolute/path/to/skills
```

安装器默认创建软链接，且拒绝覆盖已存在目标。请保留完整仓库，以维持跨 Skill
引用、共享契约和许可文件。再分发时不要只复制三个 Skill 目录而漏掉根目录的
`LICENSE`、`NOTICE`、`THIRD_PARTY.md`、`licenses/` 及组件许可。

安装后可让 agent 执行：“使用 product-flow，从 S1 开始为我的产品梳理需求。”
已有项目也可以单独调用 coding-standards 或 four-node-review。

## 验证

```bash
./scripts/verify-suite.sh --quick
./scripts/verify-suite.sh --full
```

- `--quick`：结构、零丢失、跨 Skill 锚点与便携性检查。
- `--full`：再运行 `product-flow` 全量 fresh 自证与 `coding-standards` 变异套件，耗时更长。

## 运行依赖

基础环境：Bash、Python 3、Node.js、Git。不同阶段还可能需要本地 Chrome/Chromium、D2/Mermaid、Figma、飞书或钉钉。这些不是“安装了就假定可用”的依赖：每次运行都要以当前环境的实测结果为准。

`product-flow` 的飞书交付使用官方 `lark-cli --as user`；钉钉交付使用官方 `dws`。
仓库不捆绑任何公司租户、个人账号、私有文档或授权信息。官方入口：
[飞书 CLI](https://www.feishu.cn/feishu-cli) ·
[钉钉 CLI](https://open.dingtalk.com/dingtalk-cli)。

支持矩阵见 [`docs/supported-environments.md`](docs/supported-environments.md)，版本兼容策略见
[`VERSIONING.md`](VERSIONING.md)。

## 公开发布状态

当前为**开源开发预览版**，不是稳定版承诺。三个核心 Skill、制图器、原型工具、
共享契约和验证脚本均保留。公开源代码与证明所有平台、所有真实项目都有效是两件事。

尚未完成的验证包括真实飞书/钉钉交付、生产项目 W5 评测，以及多任务质量与性能对照；
用例工程的已知语义缺口和部分示例图的排版问题也已列出。
这些能力不能因单元测试通过就宣称完成；缺证据仍按 `UNABLE` 处理。

源码公开检查见 [`PUBLICATION_CHECKLIST.md`](PUBLICATION_CHECKLIST.md)，稳定版待办见
[`RELEASE_BLOCKERS.md`](RELEASE_BLOCKERS.md)。公开检查不会把稳定版待办自动勾选为完成。

## 许可证与归属

原创部分采用 [Apache-2.0](LICENSE)。改编及内置的第三方材料保留各自的 MIT、Apache、
Creative Commons 或 W3C 条款，详见 [NOTICE](NOTICE) 和 [THIRD_PARTY.md](THIRD_PARTY.md)。
其中 OWASP 改编的指定章节使用 CC BY-SA 4.0，不能当成 Apache-2.0 内容转授。
SYBuilder 是独立项目，不代表任何所引用产品或组织；名称说明见 [TRADEMARKS.md](TRADEMARKS.md)。
