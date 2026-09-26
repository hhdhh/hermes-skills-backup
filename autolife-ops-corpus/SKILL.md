---
name: autolife-ops-corpus
description: |
  AutoLife 机队运维语料总路由（33 篇飞书文档蒸馏）。机器人排障走 autolife-ops-robot-diagnosis，DDS 阵营走 autolife-ops-dds-split， 建图空白走 autolife-ops-slam-troubleshooting，出货验收走 autolife-ops-shipment-acceptance，AI 动作走 autolife-ops-ai-action-config， 停止条件走 autolife-ops-shutdown-conditions；低频专项（hwid 修复/连接切换/RustFS/文档治理/装机/numpy shim）在此路由直达。
metadata:
  cangjie.generated-by: cangjie-tools v2.5.0
  cangjie.variant: router
  cangjie.bundle-id: bundle.autolife-feishu-corpus
  cangjie.capability-count: 14
  cangjie.entrypoint-count: 7
---
# AutoLife 飞书运维语料全集 — 来源路由入口（compact pack）

## 触发与不触发

**适用**：与本书能力域相关的咨询与任务（见下方路由表的意图列）。
**不适用**：
- FAE 排班系统操作（autolife-fae-scheduler）
- 飞书/Lark API 操作（lark 系列）
- 机器人 prompt 对话调教（autolife-robot-prompt-ops）
- VR 遥操（autolife-vr-teleop）

## 核心原则（常驻速览，概览类问题读到这里即可回答）

1. running ≠ healthy——五层递进判定（进程/接口/数据/依赖/业务），NRestarts 窗口采样识破崩溃循环
2. 沿数据流找首个断点，不跳层、不凭猜测换硬件
3. 三类验收分离（FAT/出货/SAT），模板不是证据，退出码 0 不是放行
4. 修复完成必须走恢复验证六步，重启成功≠故障关闭
5. 机器身份（hwid/license/密钥）一机一证，跨机拷贝=封号
6. 配置修改三保：先备份、只改指定字段、改完重启验证

## 能力路由（先读本表，按意图加载 1 张能力卡）

| 用户意图 | 先读 | 补读/备注 |
|---|---|---|
| 机器人排障；健康判定；找断点；服务正常但没数据 | references/capabilities/autolife-ops-robot-diagnosis.md | 已晋级为独立 Skill `autolife-ops-robot-diagnosis`（已安装时优先直接使用；本卡仅作原文与背景补充） |
| 电池恒100%；话题僵尸；服务互相看不见；CYCLONEDDS_URI | references/capabilities/autolife-ops-dds-split.md | 已晋级为独立 Skill `autolife-ops-dds-split`（已安装时优先直接使用；本卡仅作原文与背景补充） |
| 建图空白；地图无形状；slam 收不到雷达；nav2 参与者爆限 | references/capabilities/autolife-ops-slam-troubleshooting.md | 已晋级为独立 Skill `autolife-ops-slam-troubleshooting`（已安装时优先直接使用；本卡仅作原文与背景补充） |
| 出货验收；FAT；SAT；G5 放行判定；证据包整理；恢复交付态 | references/capabilities/autolife-ops-shipment-acceptance.md | 已晋级为独立 Skill `autolife-ops-shipment-acceptance`（已安装时优先直接使用；本卡仅作原文与背景补充） |
| AI对话带动作；新增动作；tool_call 不触发；关键帧部署 | references/capabilities/autolife-ops-ai-action-config.md | 已晋级为独立 Skill `autolife-ops-ai-action-config`（已安装时优先直接使用；本卡仅作原文与背景补充） |
| 该不该继续修；升级判定；修复验证；偶发故障处置 | references/capabilities/autolife-ops-shutdown-conditions.md | 已晋级为独立 Skill `autolife-ops-shutdown-conditions`（已安装时优先直接使用；本卡仅作原文与背景补充） |
| 机号找机器人；远程 SSH；批量盘点 | references/capabilities/autolife-ops-find-and-ssh.md | references/capabilities/autolife-ops-robot-diagnosis.md |
| relay 握手失败；管理端 offline；hwid 修复 | references/capabilities/autolife-ops-hwid-repair.md | references/capabilities/autolife-ops-connection-switch.md |
| 切换连接方式；管理端 offline 排查；现场直连配置 | references/capabilities/autolife-ops-connection-switch.md | references/capabilities/autolife-ops-hwid-repair.md |
| RustFS 上传下载；rclone 超时排障 | references/capabilities/autolife-ops-rustfs-transfer.md | — |
| 文档冲突裁决；新文档定级；Agent 权限配置；归档取代 | references/capabilities/autolife-ops-doc-governance.md | — |
| 新机装机；裸机初始化；重装恢复 | references/capabilities/autolife-ops-s2-installation.md | references/capabilities/autolife-ops-shipment-acceptance.md |
| numpy 2 崩溃循环；闭源包兼容 | references/capabilities/autolife-ops-numpy-shim.md | references/capabilities/autolife-ops-slam-troubleshooting.md、references/capabilities/autolife-ops-robot-diagnosis.md |
| 按症状直查；语音无响应；导航不起；抓取失败 | references/capabilities/autolife-ops-symptom-map.md | references/capabilities/autolife-ops-robot-diagnosis.md |

**非能力类查询**：
- 书名/作者/章节/整书概览 → references/overview.md
- 术语解释 → references/glossary.md
- 决策规则速查（不需要原文依据时） → references/cheatsheet.md
- 完整意图与关键词索引（本表未覆盖的意图先查这里） → references/capability-index.md

## 加载规则

- 每次任务先读本文件，再按路由表加载 **1** 张能力卡；任务明确跨域时最多加载 2 张。
- 概览/书名类问题不加载能力卡，用「核心原则」与 overview.md 回答。
- 路由表与 capability-index.md 都无法命中的意图，明确告知超出本书范围，不要硬套。

## 边界与判停

- 安全事件（急停失效/失控/碰撞/异响/冒烟/过温）→ 立即停手上报
- crash loop/SIGSEGV 最小处置后复现 → 升级，按首个断点分派
- 需动驱动/固件/标定/License → 超出远程运维边界
- 身份文件缺失 → 本机重新生成，严禁跨机拷贝
