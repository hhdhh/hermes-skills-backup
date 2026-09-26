# 症状→诊断链速查表

<!-- capability_id: autolife-ops.symptom-map | revision: 1 | status: active -->
<!-- 来源: 04 集成测试 §4（飞书语料） -->

## R — 原文

> AI会话显示已连接但语音无响应→Vision/音频日志→麦克风topic/能量→输入设备→AI消费者；导航不起→GV服务→ROS域→前后雷达producer/topic→TF/里程计→SLAM/Nav2。
> —— 《04｜集成测试 §4》

## I — 自述

这是五层健康模型（autolife-ops-robot-diagnosis 卡）的速查版：常见症状直接给出排查链，跳过逐层遍历。七条实测映射覆盖语音、视觉、抓取、导航、管理端、机械臂六大症状类。

用法：先对症状找链，沿链逐项查，每条链的"判定重点"告诉你最容易命中的根因。链上找不到断点时，回 autolife-ops-robot-diagnosis 卡走完整七步。

七条链各带常见解释：语音无响应先查麦克风能量（0.000=输入设备选错）；RGBD SHM 不存在查 ENABLED_MODULES；Grasp service 创建失败查 typesupport（SHM 已开则相机非首断点）；导航不起查雷达 producer/TF/域；跨版本 USB bus ID 与 SDK 不一致；管理端 offline 查物理链路/地址/路由/DNS/端口；机械臂 CAN 超时查供电/线束/终端/通道映射。

## A1 — 书中案例

**案例类型：书中亲历案例**（语音链应用，来源：04 集成测试）

- 输入/问题：AI 会话"已连接"但说话无响应
- 方法执行：按链查——vision/音频日志 → 麦克风 topic 能量=0.000 → 判定 ai_audio_input_device 选错设备
- 结论：改输入设备配置后能量恢复，语音链通

## A2 — 未来触发 ★

**情境：**

1. 接到故障描述想快速锁定排查方向
2. 语音/抓取/导航/离线/CAN 任一症状类首发定位
3. 新人 FAE 按表排障减少乱查

**语言信号：**

- "说话没反应" / "麦克风没数据" / "语音无响应"
- "抓不住" / "Grasp 失败" / "RGBD 不存在"
- "导航不起" / "管理端 offline" / "机械臂 CAN 超时"
- EN: "voice not responding" / "grasp failing" / "can timeout"

**区分：**

- ≠ autolife-ops-robot-diagnosis：那是完整七步流程；本卡是速查捷径，链上找不到再回主流程
- ≠ autolife-ops-dds-split / autolife-ops-slam-troubleshooting：专项修复；本卡只负责"首查方向"

## E — 可执行步骤

**输入契约**：症状描述（必填，尽量含报错文本/前端表现）。

**七条链直查**：

| # | 症状 | 排查链 | 判定重点 |
|---|------|--------|----------|
| 1 | AI 会话连接但语音无响应 | Vision/音频日志→麦克风 topic/能量→输入设备→AI 消费者 | 能量 0.000=ai_audio_input_device 选错 |
| 2 | RGBD SHM 不存在 | ENABLED_MODULES→相机服务→SHM 配置 | 模块未启用比硬件故障常见 |
| 3 | AI Grasp service 创建失败 | typesupport→SHM 状态→相机 | SHM 已开则相机非首断点 |
| 4 | 导航不起 | GV 服务→ROS 域→前后雷达 producer/topic→TF/里程计→SLAM/Nav2 | 先确认雷达有数据再查 nav2 |
| 5 | 跨版本设备读不到 | USB bus ID↔SDK 映射 | 版本升级后 bus ID 变化 |
| 6 | 管理端 offline | 物理链路→地址→路由→DNS→:3000/:8000→Relay UDP | 从底层往上查，别先怀疑服务 |
| 7 | 机械臂 CAN 超时 | 供电→线束→终端电阻→通道映射 | 供电不足最常见 |

**判停点**：链上全部正常但症状仍在 → 回 autolife-ops-robot-diagnosis 卡完整七步；链上命中 → 按对应专项卡修复

**输出契约**：症状→命中链编号→断点位置→建议动作。

## B — 边界

- **不适用**：装机/验收（各自流程）；链查不到的疑难杂症（回主诊断流程）
- **反场景**：把表当 exhaustieve 清单（只覆盖六大常见类）
- **失败模式**：跳过判定重点直接换硬件；语音类不先看能量数值
- **相邻易混**：本卡是"首查方向"，诊断结论要靠 autolife-ops-robot-diagnosis 的证据链背书
