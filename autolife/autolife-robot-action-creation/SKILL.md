---
name: autolife-robot-action-creation
description: Use when 主人要求机器人做新动作/创建动作/加动作/动作不动了/动作触发不了。
metadata:
  requires:
    bins: ["ssh"]
  triggers:
    - "机器人创建动作"
    - "机器人加动作"
    - "让机器人做动作"
    - "动作不执行"
---

# AutoLife 机器人自定义动作创建

> 完整描述：AutoLife S1/S2 机器人自定义动作创建全流程：描述→pybullet 仿真验证→三视图预览给管理员确认→安全部署到 robot_action.json。含语音动作触发的 qwen_native_fc 链路配置。Use when 主人要求机器人做新动作/创建动作/加动作/动作不动了/动作触发不了。

> 动作本体 = `autolife_robot_arm/robot_action.json`（关键帧序列，每帧 `{type: move/reset/wait, left_arm/right_arm/neck/waist_leg: [7/3/4 个度数], duration}`）。语音触发它需要两层都通：动作管道（arm-control）+ AI 工具调用链（见下）。

## 流程总览

```
主人描述动作 → 【第0步·硬流程】网上查资料：人类动作运动学分解 + 仿人机器人同动作公开案例
→ 提炼目标关节角草案 → 适配 robot_v2_2 关节极限（±17°肩外展/肘单向，不适处最近近似并注明差异）
→ 本地 pybullet 仿真优化验证 → 限位+碰撞验证 → 三视图预览图发管理员确认
→ 确认后：三重备份 robot_action.json → 写入新动作 → 更新 control_robot_action.py 的 enum
→ 重启 vision+face（联动）+ logo-backend → 现场语音验证
```

## Step 1: 本地仿真环境（一次搭好）

- 从机器人拉 SDK 模型：`tar czf` 打包 `…/autolife_robot_sdk/descriptions/autolife_s1/`（urdfs+meshes，~45MB）→ 本地解压。
- `pip install pybullet`（清华源）。
- 加载：`p.loadURDF('autolife_s1/urdfs/robot_v2_2.urdf', useFixedBase=True, flags=p.URDF_USE_SELF_COLLISION)`，46 关节，URDF 关节值为弧度、动作库是度数，`math.radians()` 转换。
- 动作库 right_arm 7 值 → URDF 关节映射：`[Shoulder_Inner, Shoulder_Outer, UpperArm, Elbow, Forearm, Wrist_Upper, Wrist_Lower]`（度数直接对应，无需变符号——S2 右肘负值区）。

## Step 2: 安全验证（不过不上机）

1. **限位校验**：每个关节角度必须在 URDF `getJointInfo()[8:10]` 范围内（±0.05rad 容差）。
2. **自碰撞检测**：`p.performCollisionDetection()` + `getContactPoints(robot, robot)`，排除同 link 接触、Gripper 内部连杆、灵巧手内部。
3. **必须先测零位 baseline**：URDF 有 2 对静态重叠（颈部 `Neck_Roll_to_Neck_Pitch ↔ Neck_Yaw_to_Head`、腰部 `Waist_Yaw_to_Shoulder_Inner ↔ Neck_Pitch_to_Neck_Yaw`），零位就存在——这些对要列入排除表，否则所有帧都误报碰撞。

## Step 3: 三视图预览（管理员定的规范）

**预览图一律三视图：正面 + 侧面 + 俯视（上面）**。渲染配方（2026-09-28 segmask 实证，详见 skill `autolife-robot-motion-design` 坑 3 与 `/home/kk/robot-sim/render_front_calibration.py`）：`p.computeViewMatrixFromYawPitchRoll` + `ER_TINY_RENDERER`，**yaw=90=正面**（前雷达在 +x；270 背面、0/180 侧面）；解码必须 `Image.frombytes("RGBA",(w,h),bytes(rgb))` 不翻转（按 RGB 步长解=废图）；质检用 segmask 按 body id 数像素（遮挡测试定朝向 + 每面板完整性），RGB 颜色计数不可靠。取景用遍历所有 link AABB 求总包围盒（useFixedBase 时整机 getAABB 返回 0）。出图经飞书 im/v1/images 上传（image_type=message）+ post 富文本发管理员，等确认后才部署。

## Step 4: 动作设计两条安全规则（管理员要求，写死）

1. **危险动作拆分**：直接执行会自碰撞的轨迹，必须拆成 2 个或多个子动作，插入安全中间姿态作过渡，逐段执行完成整个动作。
2. **安全复位**：动作结束不直接 reset 跳回零位，而是沿执行路径的中间姿态逐个倒序退回（原路返回），每步过碰撞校验，最终回初始位。
3. 新动作关键帧模板：`抬臂过渡 → 目标姿态 → 手势(灵巧手 right_dexteroushand 6 值) → wait 展示 → 松手势 → 退回过渡位 → 退回 home`。

## Step 5: 部署（三处改动 + 三重启）

1. `robot_action.json` 三重备份 `.bak.<ts>.{1,2,3}` + md5 校验（SFTP 上传，paramiko）。
2. `robot_tools/control_robot_action.py`：TOOL_SCHEMA 的 `enum` 加动作名 + `enumDescriptions` 加中文说明 + `valid_actions` 列表加动作名，`python3 -m py_compile` 语法校验。
3. 重启顺序：`vision-service` → 3s → `face-detection-service`（联动硬规范）→ `logo-backend`（它持有 robot_tools 代码，不重启则新 enum 不生效）。
4. 生效热加载：9001 端口 `POST /library/import_builtin` 可把 robot_action.json 重新导入运行库（返回导入的 poses/trajectories 列表，可当验证）。

## 语音动作触发链（排查“说了不动”）

详见 [references/action-trigger-chain.md](references/action-trigger-chain.md)。核心三条：

1. **plain `qwen` provider 不支持工具调用**——动作类工具必须切 `realtime_api_provider = "qwen_native_fc"`（settings.toml，plus 模型）。
2. **`robot_v2_2.json` 里 `audio.qwen_native_fc.realtime.tool_call_enabled` 默认 false**，深藏三层，日志表现为 `Qwen Native FC tool calling disabled by config`——改为 true。
3. **文本兜底检测器（`_infer_qwen_tool_from_transcript`）只映射时间/搜索类触发词，没有动作词映射**——prompt 里教 `<action>` 标签或自然语言动作描述都白费；模型自造的 `<action>wave</action>` 永远不会被解析。qwen 模式下 prompt 动作段要用厂商 `<tool_call>` XML 格式（见 `prompt.txt.example.qwen`），但根治靠 native_fc 原生工具调用。

**验证三件套**：`journalctl --user -u vision-service | grep -E 'session.created|Native FC'`（无 disabled 行 = 开关生效）；说话后 grep `tool_detected`（False = 没触发）；grep `Published action message: <动作名>`（出现 = 真执行）。

## 开机自动复位/手动复位

机器人臂不复位时，正确通道是 `/control_reset_<domain>_<robot_id>` 话题（SDK 示例 `example_00_ros_reset_robot.py` 自带等订阅者）。装开机自动复位走 `autolife-boot-auto-reset` 技能的 5 步。重启 arm-control-service **不会**让臂回位（只重置控制状态）。

## 已知坑

- **`<action>` 标签是模型幻觉格式**，系统任何代码都不解析它——看到 AI 回复带 `<action>xxx</action>` 而臂不动，直接查 provider 配置，不要在 prompt 里教这个格式。
- **idle 动作走独立通道**（enable_idle_action_on_response），它一直正常不代表语音工具调用链通。
- **9001 端口（rust-web-server）没有动作播放端点**——/library/pose、/library/trajectory 是保存接口不是播放接口；`/robot/status` 可读关节实际/目标值对比判断是否到位。
- **DDS 手动探测**：必须完整复刻 arm-control-service 的 CYCLONEDDS_URI（含 `MaxAutoParticipantIndex`），从 `/proc/$(systemctl --user show arm-control-service -p MainPID --value)/environ` 读；缺 Discovery 段会报 participant index 错误。
- **机器人关节状态查询**：`curl http://127.0.0.1:9001/robot/status`，对比 `position`（实际）与 `*_target_joint_state`（目标）判断臂是否到位。
- 电池 <10% 时大幅动作可能触发低电保护，测试前看 battery.percentage。
