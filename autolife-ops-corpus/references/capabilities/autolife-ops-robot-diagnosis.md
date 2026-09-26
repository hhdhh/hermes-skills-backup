# 五层健康模型与固定诊断顺序

<!-- capability_id: cap.autolife-ops.robot-diagnosis | revision: 1 | status: active -->
<!-- 来源: 机器人排障案例库/04 集成测试、健康检查与分层故障诊断（飞书语料） -->

## R — 原文

> 健康状态应分为五层：进程健康、接口健康、数据健康、依赖健康、业务健康。任何一层未通过，状态都应标记为 Not Ready。
> —— 《集成测试、健康检查与分层故障诊断》

> 出现异常时，按以下顺序逐层收敛：NRestarts与进程稳定性→日志与第一个异常→ROS graph与身份一致性→Producer上游生产者→SHM/topic传输与数据面→Consumer下游消费者→Hardware设备驱动供电。
> —— 同上

## I — 自述

判断机器人是否健康，不能只看 systemd 的 active (running)——那只证明进程被拉起，不证明 ROS 发现正常、数据在产、消费者已连接、业务真的可用。正确做法是五层递进检查：进程（无 failed、NRestarts 不增长）→ 接口（node/topic/service 齐全且身份一致）→ 数据（topic 时间戳前进、频率稳定）→ 依赖（消费者 attach 成功）→ 业务（最小端到端任务能完成）。

排障时按七步固定顺序沿数据流找**首个断点**：先查进程稳定性（NRestarts 前后采样），再找日志第一个异常（清理阶段的报错常是次生现象），再核对 ROS 身份一致性，然后沿 Producer→传输→Consumer→Hardware 数据流逐段验证。不跳层、不凭猜测换硬件。

自动重启会掩盖崩溃循环：采样瞬间 active 不代表稳定，NRestarts 在观察窗口内增长就按 crash loop 处理。版本参数以本机实际生效路径为准（从 unit ExecStart 或运行时解析确认），不凭同名文件猜。

## A1 — 书中案例

**案例类型：书中亲历案例**（402 电池恒 100%，来源：排障案例库）

- 输入/问题：前端电池恒显 100%，底盘话题僵尸，gv 驱动服务全部 active
- 方法执行：按五层检查——进程层 active✅ 但话题层 0 publisher❌，定位到"服务活着但数据不流动"的层间断层；进一步沿数据流查到 DDS 发现域分裂（两套 CYCLONEDDS_URI）
- 结论：running ≠ healthy 实锤，修复 URI 后数据恢复 1Hz

**案例类型：书中亲历案例**（320 建图导航全失效）

- 输入/问题：320 廍图空白，slam 服务反复重启
- 方法执行：NRestarts 采样发现 slam 崩溃循环（重启 70+ 次）→ journalctl 找第一个异常 = np.cross 2D ValueError → 修复后话题数 2→113
- 结论：崩溃循环必须先稳定进程层，再谈数据层

## A2 — 未来触发 ★

**用户会在什么情境下遇到这类问题？**

1. 展厅/现场机器人"看着正常"但取货、导航、对话全没反应，运营反馈"机器人又坏了"
2. 排障 SSH 登上机器人，systemctl 看服务全是 active，不知道下一步查什么
3. 验收或巡检时需要系统性判定一台机器人是否真的健康，而不是抽查几个服务
4. 修复后想验证"修好了"不只是重启成功

**语言信号：**

- "机器人不动了/又坏了/没反应" + systemd active
- "服务都在跑怎么没数据" / "topic 0 publisher"
- "这个话题一直100%/数值不变" / "前端显示不对"
- "running 不等于 healthy 吧" / "NRestarts 在涨"
- EN: "robot not responding but services active" / "topic has no publisher" / "zombie data"

**与相邻 skill 的区分：**

- ≠ autolife-dds-split：那支专修 CYCLONEDDS_URI 阵营分裂的具体病；本卡是通用的分层判定与找断点流程，先过五层再决定进哪支
- ≠ autolife-slam-troubleshooting：那支专治建图空白/导航不起；本卡不预设故障类别
- ≠ autolife-shutdown-conditions：那支判"该不该继续修"；本卡判"断点在哪"
- ≠ autolife-robot-manager-toolbox / autolife-doctor-operations：老技能是工具清单/日常保养；本卡是排障决策流程
- ≠ autolife-robot-diagnostics / autolife-robot-troubleshooting（旧技能群）：那些按单症状单修法组织；本卡是分层判定+固定顺序的决策框架，机队报修先进本卡

## E — 可执行步骤

**输入契约**：机号或 hostname（必填）；故障现象描述（必填）；SSH 可达（必填）。缺失机号时先走 autolife-find-robot 定位。三样缺一先问，不猜。

**Step 1 进程层**：`systemctl --user list-units --failed`（无 failed）；对核心服务（gv-*/vision/face/relay/slam）前后间隔 60s 采两次 `systemctl --user show <unit> -p NRestarts`，增量>0 = crash loop → 转停止条件卡（p01）判是否升级
**Step 2 日志层**：`journalctl --user -u <unit> --since "..."` 按时间序找**第一个**异常；清理阶段的 Pcan/Job canceled 是次生现象，不追
**Step 3 身份层**：核对 ROS_DOMAIN_ID/ROBOT_ID/TOPIC_NODE_ID 与机型一致；非同机型参数不可复制
**Step 4 生产者**：确认 Producer 实际启用——从 unit ExecStart 或运行时解析 ENABLED_MODULES，不凭同名文件猜（p06）
**Step 5 数据面**：`ros2 topic hz <topic>` 时间戳前进、频率稳定；SHM 存在且持续更新。**注意**：查询环境的 CYCLONEDDS_URI 必须与目标服务一致，否则 0 publisher 是假象（c01）
**Step 6 消费者**：下游 attach 成功、无 typesupport 错
**Step 7 硬件层**：以上全正常才下钻 USB 拓扑/驱动/线束/供电
**判停点**：任一层发现断点 → 停止向下、按断点修（并查残留自制服务 c02）；Step 1 crash loop 或 Step 7 前触发 p01 停止线 → 转 autolife-ops-shutdown-conditions 卡

**输出契约**：断点定位报告（层级/位置/证据命令+输出）+ 修复建议 + 是否建议升级。表头：层级｜证据｜结论｜建议动作。

## B — 边界

- **不适用**：装机/网络配置（走 s2-robox-wizard）；出货验收判定（走 autolife-ops-shipment-acceptance）；AI 对话动作配置（走 autolife-ops-ai-action-config）
- **反场景**：纯 UI 显示问题但 ROS 数据正常（前端 bug，不属诊断链）；客户网络环境问题（进场双确认范围）
- **失败模式**：只查到"服务 active"就下结论（漏数据层/业务层）；跳层换硬件（违反固定顺序）；忘记采样 NRestarts 只看瞬时值
- **相邻易混**：症状映射表（f03）是本卡 Step 4-7 的速查版，属同一能力族不单用
