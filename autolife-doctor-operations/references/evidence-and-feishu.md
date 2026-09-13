# 证据与飞书同步

用本流程生成基于证据的评审报告、更新管理层/研发/FAE 知识文档，并核查权限——确保文字表述永远不超出证据来源的支撑范围。

## 1. 先定义结论，再构建报告

先写清楚：

- 受众以及本文档要支撑的决策；
- 物理主机、Doctor 版本、配置/策略哈希、证据窗口；
- 结论属于哪一类：实机、历史、demo、fixture、候选、人工观察、自洽未签名；
- 哪些事实来自 GitHub、物理机器人、Doctor 契约、飞书；
- 有效期/失效时间，以及明确"未获授权表述"的确切语句。

不得拼接不同主机、版本、策略或窗口的数据去补齐缺失字段。用不兼容证据拼出的"看起来完整"的报告是无效的。

## 2. 优先使用原始证据加独立验证器

使用仓库自带的生成器和来自同一已评审 commit 的配套验证器。典型流程：

```bash
doctor --config CONFIG --once --format json > snapshot.json
python3 tools/verify_snapshot.py snapshot.json

doctor --config CONFIG release-status --format json > release-status.json
python3 tools/verify_release_status.py release-status.json

python3 tools/build_evidence_bundle.py snapshot.json \
  --purpose observation --doctor-exit DOCTOR_EXIT --output EVIDENCE_DIR
python3 tools/verify_evidence_bundle.py EVIDENCE_DIR

python3 tools/render_operations_review.py events.jsonl --format json > operations-review.json
python3 tools/verify_operations_review.py events.jsonl operations-review.json --format json
```

试点或管理层结论使用仓库的 `render_pilot_review.py` 或 `render_leadership_review.py`，随后用对应验证器并显式传入预期主机/版本约束。构造参数前先读各命令的 `--help` 和当前 README；契约会演进。

有效的 HOLD 文档也是有用的证据。不得为了得到一个绿色标题而重跑或修改它。原始输入、验证器 stdout/stderr、退出码、哈希与生成产物放在一起保存，权限保持私有。

## 3. 区分三个飞书受众

三个文档面从同一张事实表更新，但各自保持决策范围：

### 管理层（Leadership）

- 当前机器人与发布决策；
- 已证明的价值 vs 尚未证明的部分；
- 头部阻塞项、责任角色、待决事项、退出条件；
- GitHub PR/issue 与持久证据的链接；
- 不放命令清单，不做无依据的成本节约/车队规模宣称。

权威文档：`https://autolife.feishu.cn/wiki/Uhblwlds8iAbzOkTHbHcjGDinze`。

### 研发（Development）

- 契约、stable ID/reason code、架构、安全不变量；
- 源码/制品 SHA、测试与验证器结果；
- 服务/配置/硬件发现与实现局限；
- 部署/回滚机制与未完成的技术工作。

权威文档：`https://autolife.feishu.cn/docx/F4dhdPB0uob4quxzIMwcmkYjnIe`。

### FAE

- 安全连接路径与目标身份；
- 只读命令、预期观测、停止条件、升级上报材料包；
- 明确的禁止动作与修复授权边界；
- 金丝雀/回滚检查单与当前现场阻塞项。

权威文档：`https://autolife.feishu.cn/docx/OlsxdFhU8ow66Ax3iU1cuRjDnqh`。

当 Mermaid 图能显著减少歧义时，用它表达决策流、证据链或所有权生命周期。不要把大段底层规格重复粘贴到三个文档里。

## 4. 每次写入会话前先读当前 `lark-cli` 技能

CLI 内嵌的说明与版本匹配且必须遵守。完整读完，包括操作所需引用的文件：

```bash
lark-cli skills read lark-doc
lark-cli skills read lark-drive
```

先用 `lark-cli docs +fetch`（或当前文档规定的等价命令）获取确切目标，记录当前 revision、标题、token/类型和相关内容。wiki URL 按内嵌技能的指引解析出底层文档。

更新文档前：

1. 从已验证的事实生成最小的、面向该受众的补丁；
2. 保留既有的有用内容与稳定锚点；
3. 预览或 dry-run 确切命令；
4. 支持时把写入绑定到已获取的 revision，让并发编辑失败而不是被吞掉；
5. 只在用户授权的文档范围内执行；
6. 写入后重新获取，比对插入的事实、链接、图表渲染与 revision。

若写入前 revision 已变化，重新获取并对账；绝不盲目覆盖。不得从仓库文字推断当前 revision 号。

## 5. 核查权限治理

内容验证之后再读取当前权限。项目的目标姿态是租户内可编辑协作，且：

- 外部访问关闭；
- 外部邀请关闭；
- 链接/分享范围限制在同一租户；
- 评论与安全设置与租户内查看者一致。

权限变更按独立的高风险外部变更处理：先 dry-run，要求用户对确切目标和策略的明确授权，应用最小增量，然后回读确认。绝不为图方便而放宽访问。

不得仅因存在新的权威文档就删除旧文档。获授权时做标记/归档并链接到替代文档；永久删除需要明确确认并走当前 lark-drive 的高风险流程。

## 6. 对账并发布状态矩阵

宣布同步完成前，先比对：

| 事实 | GitHub | 机器人/证据 | 管理层 | 研发 | FAE |
|---|---|---|---|---|---|
| 当前源码/制品 | 权威 | 仅安装哈希 | 概要 | 精确 | 部署版本 |
| 当前就绪/发布状态 | 源码契约 | 权威实机结果 | 标题结论 | 契约加证据 | 运维结果 |
| 阻塞项与责任人 | 追踪器 | 适用时为机器事实 | 决策责任人 | 技术责任人 | 上报角色 |
| 金丝雀/回滚 | 源码脚本 | 权威回执 | 结果 | 机制/结果 | 流程/结果 |
| 授权边界 | 策略/历史 | 实际执行行为 | 决策注意事项 | 精确不变量 | 禁止动作 |

报告任何有意的滞后或不可用的文档面。"已同步"要求新鲜的重新读取；仅凭写入成功的响应不足以宣布同步。

## 7. 保留持久审计线索

记录文档 URL、变更前后 revision、时间戳、变更摘要、来源 commit/证据 ID、权限结果、验证结论。临时的 XML/Markdown 预览除非是有意版本化的产品资产，否则不进 Git。

每次更新以下列之一收尾：

- `SYNCED`：范围内全部文档面已重新读取，且在有界事实上一致。
- `CONTENT_SYNCED_PERMISSION_HOLD`：内容正确，但权限目标未验证或未授权。
- `PARTIAL_SYNC`：指出过期或不可访问的文档面。
- `NO_WRITE_HOLD`：来源不足、revision 冲突或缺少授权。
