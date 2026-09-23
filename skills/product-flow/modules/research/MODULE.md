# SYBuilder 内置研究模块

主流程 S2 的研究能力已经融合在本 Skill 内，不依赖另一个研究 Skill 才能运行。

## 按需读取

- 竞品深度遍历与最细颗粒度：`../../references/competitive-research.md`
- 行业研究：`../../templates/market-landscape.md`
- 调研交付骨架：`../../templates/competitive-research-pack.md`
- 人读报告：`../../templates/research-report.md`
- 功能原子账本：`../../templates/competitive-research-pack.md` 的原子词典、逐竞品事实账与逐层比较表
- 真实客户端遍历：`../../scripts/competitor-walk.mjs`、`deep-walk.cjs`
- 质量门：`../../scripts/research-gate.py`、`traversal-coverage-gate.py`、
  `report-structure-gate.py`、`research-quality-gate.py`；
  交付按所选平台运行 `feishu-delivery-gate.py` 或 `dingtalk-delivery-gate.py`，不互相替代。
- 三模式必交付包、最细正文、逐级横比、图片与同版终审：
  `../../references/delivery-quality-contract.md`；多竞品索引
  `../../templates/research-package.json`，评审底稿 `../../templates/research-quality-review.md`。

外部研究 Skill 只作为来源证据。若某条方法会改变必交付内容，必须用 SYBuilder 自己的
语言写入上述正本并配门禁；不能让用户因为没有安装外部 Skill 而缺一整段能力。
