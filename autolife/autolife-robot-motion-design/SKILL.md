---
name: autolife-robot-motion-design
description: Use when 为 AutoLife 机器人设计/新增/调试 AI 对话肢体动作：关键帧设计、仿真验证、预览图...
---

# AutoLife 机器人动作设计与部署（关键帧 + 仿真验证）

> 完整描述：Use when 为 AutoLife 机器人设计/新增/调试 AI 对话肢体动作：关键帧设计、仿真验证、预览图、部署到动作库。

> 触发场景：主人描述一个新动作（比心/点赞/挥手新版本）、要求“让机器人做 X 动作”、动作效果不对要重调、查动作库。
> 原则：**先仿真后上机**——所有新动作先在本地 pybullet 用官方 URDF 验证限位+碰撞，出预览图给主人确认后才写入机器人。

## 架构 30 秒版

```
动作库本体: autolife_robot_arm/robot_action.json（32+ 个，键=动作名，值=关键帧列表）
帧类型: {"type":"move", "right_arm":[7值度], "left_arm":[...], "waist_leg":[...], "duration":s}
        {"type":"wait","time":s} / {"type":"reset","duration":s} / {"type":"pkl"}（旧录制，会崩，见坑2）
右臂 home = [-20,0,0,-110,0,0,0]，左臂 = [20,0,0,110,0,0,0]（镜像）
关节序: [肩内旋, 肩外展, 上臂, 肘, 前臂, 腕上, 腕下]（度）
播放端: arm-control-service 的 node_robot_action_service_<domain>_<robot_id>
```

## 标准流程（6 步）

### 1. 拉动作库 + 设计关键帧
```python
import paramiko
# SFTP 拉回: ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/robot_action.json
# 参考 win_an_award/bow_salute 的帧结构设计；对称动作用双臂镜像值
```

### 2. 本地仿真验证（工作站 /home/kk/robot-sim/ 已就绪）
- URDF: `autolife_s1/urdfs/robot_v2_2.urdf`（46 关节，mesh 齐全）
- 关节限位校验：每帧每关节 `math.radians(度)` 必须在 URDF lower/upper 内
- 自碰撞检测：`URDF_USE_SELF_COLLISION` + `getContactPoints`，**排除**灵巧手内部连杆（'Gripper'/'Hand' 互碰）和零位静态重叠对（颈部 Neck_Roll↔Neck_Yaw_to_Head、腰部 Waist_Yaw_to_Shoulder_Inner↔Neck_Pitch_to_Neck_Yaw——零位就接触，与动作无关）
- 判定基准：与 home 零位的接触对集合对比，无**新增**接触对即安全

### 3. 姿态求解（复杂动作用参数扫描）
```python
# 遍历 [si, so, ua, el, fa] 网格（步长5-10°），resetJointState 后 getLinkState 读腕/肘世界坐标
# 按目标位置（如“双手头顶相触”= 腕 y≈0, z>1.5, 双腕距<0.12）过滤，评分取最优
# ⚠️ 左右臂分开优化！见坑 5
```

### 4. 渲染预览图（三视图：正面/侧面/俯视——主人明确的规范）
```python
# pybullet TINY renderer 可用，但模型是浅灰白色(RGB 150-230)
# 必须增强对比: 模型像素压暗*0.55 + 浅色背景，否则人眼难辨认
# 发图前自检像素量（宽阈值 sum<730），防白图事故
# 渲染故障时用骨架图兜底: getLinkState 关键关节世界坐标 + PIL 画肩-肘-腕连线
```

### 5. 主人确认后部署（三重备份 + md5）
```bash
TARGET=~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/robot_action.json
cp $TARGET $TARGET.bak.<日期>.{1,2,3}
# SFTP 写入 + md5sum 双端校验
# 同步改 robot_tools/control_robot_action.py（enum + enumDescriptions + valid_actions 三处）
# 同步改 prompt.txt 动作调用规则段（触发词映射）
```

### 6. 重启验证
```bash
systemctl --user restart arm-control-service.service   # 加载新动作库
systemctl --user restart vision-service.service && sleep 3 && systemctl --user restart face-detection-service.service  # 硬规范: 动 vision 必联动 face
# 日志验证链: vision 侧 "Qwen function call: ... control_robot_action" → "Qwen tool executed: 成功发送动作"
#            arm 侧 "Executing action: <name>"
```

## 已知坑

1. **动作能在库里有但 AI 调不动 → 先查 provider 三件套**：普通 `qwen` 模式无 function call（AI 只嘴上说）；必须 `settings.toml` 切 `qwen_native_fc` **且** `configs/robot_v2_2.json` 的 `audio.qwen_native_fc.realtime.tool_call_enabled: true`（默认 false，藏三层嵌套，settings.toml 无对应项）。开关没开时日志只报一句 `Native FC tool calling disabled by config`。详见 skill `autolife-robot-prompt-ops` 坑 9。
2. **pkl 动作播放崩溃**：`[{"type":"pkl"}]` 类型（wave/idle 等出厂录制）回放触发 `arm_action_display._execute` 异常 + rclpy `ValueError: Logger severity cannot be changed between calls` 连锁，动作线程死亡、手臂僵住且无外部报错。**解法：重定义为关键帧动作**（move+duration 序列）。
3. **预览图白图事故**：TINY renderer 输出的模型是浅灰白色，严阈值判“有无内容”会把真模型当空白；发图前必须宽阈值（sum<730）验证像素量，且给模型压暗/换背景增强对比。骨架图（关节坐标 PIL 画线）是可靠兑底。
4. **手臂运动学极限（robot_v2_2 实测）**：肩外展正方向仅 ±17°、肘单向弯曲（左 0~149°/右 -149°~0）——人手的“侧平举”做不到。但**腕可达 z≈1.99m（远超头顶 1.5m）**，路径是肩内旋 si≈-160~-175°（左）或肩外旋 so≈+165°（右）。
5. **左右臂达高位的关节路径不对称**：左臂靠 si 负极限、右臂靠 so 正极限。强制左右镜像参数永远无解；分别优化再按手部位置对齐对称。扫描范围必须覆盖 si/so 全量（±166°），只扫 ±90 会误判“举不过头顶”。
6. **动作设计安全规则（主人要求）**：会自碰撞的轨迹拆成多个子动作插入安全中间姿态；结束复位沿执行路径逐帧倒序退回（原路返回），不直接跳回零位；对话中复位需二次确认。
7. **主人对预览图的期待是“机器人实际样子”**：骨架示意图只能应急，正式确认用 STL 模型渲染图；主人不满意的动作要主动问参照物（如“看 316 怎么做”）而不是反复盲试。

## 与其它技能衔接

| 需求 | 去处 |
|------|------|
| prompt 触发词 / Q&A | `autolife-robot-prompt-ops` |
| 机器定位 / SSH | `autolife-find-robot` / `autolife-remote-repair` |
| 开机复位 | `autolife-boot-auto-reset` |
| 服务诊断 | `autolife-doctor-operations` |
