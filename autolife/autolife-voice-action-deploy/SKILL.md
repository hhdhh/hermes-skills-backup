---
name: autolife-voice-action-deploy
description: Use when 部署机器人AI语音+动作联动、跨机复制动作配置、排查听懂不动类故障。
---

# AutoLife 语音+动作部署（跨机通用）

> 2026-09 在 321（v2.2.14）全链路验证、管理员验收"非常完美"；323（v2.2.13）部署时发现版本差异。

## 部署前必查：软件版本决定配置布局

```bash
cat ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision-*/METADATA | grep ^Version
```

| 版本 | provider 通道 | 工具开关位置（robot_v2_2.json） |
|------|--------------|----------------------------|
| **≥2.2.14**（321） | `realtime_api_provider = "qwen_native_fc"`（settings.toml） | `audio.qwen_native_fc.realtime.tool_call_enabled = true` |
| **≤2.2.13**（323） | 保持 `'qwen'`——旧版 .so 不支持 native_fc（settings 注释列了但 strings 零引用，切了无效） | `audio.qwen.realtime.tool_call_enabled = true`（无独立 native_fc 块） |

坑：机器人内嵌 python 脚本用裸 `python3` 可能无输出，统一用 `~/miniconda3/bin/conda run --no-capture-output -n robot_env python /tmp/xx.py`。

## 四层配置（缺一不可）

1. **通道层** `settings.toml` → provider（见上表）+ `asr_provider = 'qwen_realtime'`
2. **工具开关层** `configs/robot_v2_2.json` → tool_call_enabled（见上表位置）。不开则日志报 `tool calling disabled by config`，AI 永远不调工具。
3. **动作层**：`autolife_robot_arm/robot_action.json` 加动作定义 + `robot_tools/control_robot_action.py` enum **三处**（enum 列表 / enumDescriptions / run() 里 valid_actions）
4. **触发词层**：`assets/prompt/prompt.txt` 动作调用规则段——动作清单列动作名 + 触发词映射（说"X"调 action_name）。清单行和触发词行都要加，只加一处清单不全。

每层改前备份（`.bak.<日期>`）。

## 生效与验证

```bash
systemctl --user restart arm-control-service.service vision-service.service
sleep 3 && systemctl --user restart face-detection-service.service   # 硬规范：动 vision 必联动 face
```

注意：`systemctl --user is-active` 用**完整 unit 名**（带 .service），短名会误报 inactive。

验证日志链：
- vision 侧：`Qwen function call: xxx, control_robot_action, {...}` → `Qwen tool executed: 成功发送动作：<name>`
- arm 侧：`Executing action: <name>`

## 已验证动作模板（直接复用）

### handshake 握手（管理员验收"非常完美"）
13 帧三阶段：伸手（钟形速度 1.2s+0.8s+0.4s）→ 接触（停 0.3s + 肘主导摇 2.5 次 ±4° + 停 0.3s）→ 原路收回。设计依据 Frontiers Robotics 2022 人类握手运动学。
```json
[{"type":"move","right_arm":[5,0,-12,-50,20,0,0],"duration":1.2},
 {"type":"move","right_arm":[15,0,-20,-70,30,0,0],"right_dexteroushand":[0,0,0,0,0,0],"duration":0.8},
 {"type":"move","right_arm":[14,0,-19,-68,30,0,0],"duration":0.4},
 {"type":"wait","time":0.3},
 {"type":"move","right_arm":[16,0,-17,-65,30,0,0],"right_dexteroushand":[0,300,300,300,300,0],"duration":0.35},
 {"type":"move","right_arm":[13,0,-21,-73,30,0,0],"duration":0.35},
 {"type":"move","right_arm":[16,0,-17,-65,30,0,0],"duration":0.35},
 {"type":"move","right_arm":[13,0,-21,-73,30,0,0],"duration":0.35},
 {"type":"move","right_arm":[16,0,-17,-65,30,0,0],"duration":0.4},
 {"type":"wait","time":0.3},
 {"type":"move","right_arm":[14,0,-19,-68,30,0,0],"right_dexteroushand":[0,0,0,0,0,0],"duration":0.4},
 {"type":"move","right_arm":[5,0,-12,-50,20,0,0],"duration":0.8},
 {"type":"move","right_arm":[-20,0,0,-110,0,0,0],"duration":1.2}]
```
- 手位：前方 41cm、高 0.97m（腰胸之间）。**1.15m 偏高被管理员纠正**——前伸类动作按腰胸高度起步。
- 灵巧手：伸时张开 → 摇时四指收 300（轻握）→ 收时松开。dexteroushand 值域 0-1000，参考剪刀手 [0,1000,0,0,1000,1000]。
- 出厂可能自带同义动作（323 有 slow 版 right_handshake）——共存不冲突，enum 用哪个就触发哪个。

### 动作设计运动学约束（URDF 仿真实测，S2 机型）
- 肩外展正方向仅 ±17°，腕部最高 z≈1.36m——手臂举不过头顶，头顶类动作无解别硬试
- 左右臂上举路径不对称：左臂靠肩内旋 -160~-170、右臂靠肩外旋 +165（强制镜像参数无解）
- 碰撞检测白名单：颈部/腰部 2 对静态重叠 + 肩外展 20° 时左上臂碰腰，都是设计如此
- 仿真验证：pybullet 加载官方 URDF（工作站 ~/robot-sim/）逐帧限位+碰撞检查

## 对话风格硬规范（管理员多次纠正）

- ❌ 禁反问确认语种/身份（"是在和我说话吗"太啰唆频繁——没听清直接"抱歉我没听清，请再说一遍"）
- ❌ 工具调用不播报（不要说"我正在查询"）——pre_execute_message 留空或极简
- 性格按管理员指定人设写（如 ENFJ：热情外向、主动关怀、有感染力）
- 情感可以放开，事实纪律单独锁死（数字/价格/公司名不编造）

## 故障速查

| 症状 | 根因 | 修法 |
|------|------|------|
| AI 嘴上说动作身体不动 | 通道/开关层没配 | 查四层配置 |
| 切了 native_fc 无效 | 旧版软件不支持 | 查版本，回退 qwen + 旧开关位置 |
| pkl 动作播放崩（wave/idle） | 厂商 pkl 回放 bug + rclpy logger 连锁 | 重定义为关键帧 move 序列 |
| 开机后动作/通信全失效 | 四服务抢启动挤崩电机通信 | arm-control 加 ExecStartPre sleep 45 错峰 |
| 电池恒 100%（串口正常型） | gv battery reader 启动失败一次即永久放弃 | 先 SDK 直读验硬件（BatteryV2RS485Reader），好则 restart gv-control 重连 |
