---
name: autolife-robot-action-design
description: "Design AutoLife robot AI-chat actions: keyframes and sim."
triggers:
  - "加动作"
  - "新动作"
  - "动作预览"
  - "删动作"
  - "比心"
  - "握手动作"
---

# AutoLife 机器人动作设计与部署

> 完整描述：为 AutoLife S1/S2 机器人设计/部署/删除肢体动作（关键帧动作、灵巧手手势、迎宾轮播）。Use when 用户要加新动作（比心/握手/敬礼）、改动作、删动作、出动作预览图。含仿真安全验证、三视图预览、三处同步部署。

## 总流程

设计关键帧 → 仿真安全验证 → 三视图预览发用户确认 → 用户说「上」才部署 → 三处同步 + 服务重启。

## 1. 准备模型（工作站一次性）

```python
# 机器人上打包拉回：tar czf /tmp/s1.tar.gz autolife_s1/ （在 descriptions/ 目录下）
# 工作站解压到 ~/robot-sim/，含 urdfs/robot_v2_2.urdf + meshes/robot_v2_2/*.STL
import pybullet as p
p.setAdditionalSearchPath('/home/kk/robot-sim')
robot = p.loadURDF('autolife_s1/urdfs/robot_v2_2.urdf', useFixedBase=True, flags=p.URDF_USE_SELF_COLLISION)
```

关节名映射（度数，动作库顺序）：`[肩内旋 Shoulder_Inner, 肩外展 Shoulder_Outer, 上臂 UpperArm, 肘 Elbow, 前臂 Forearm, 腕上 Wrist_Upper, 腕下 Wrist_Lower]`。右臂 home = `[-20,0,0,-110,0,0,0]`，左臂镜像。限位查 `getJointInfo()[8:10]`（弧度）。灵巧手 6 值数组：0=张开，1000=全闭合，中间值=部分收（如握手轻握用 300）。

## 2. 可达性扫描（关键坑：左右臂路径不对称）

- **左右臂上举要用不同关节路径**：左臂靠肩内旋 si≈-160~-170，右臂靠肩外展 so≈165~175。强制左右参数镜像对称会永远无解。
- 机械极限（robot_v2_2 实测）：腕部最高 z≈1.36m（肩外展正方向仅 ±17°、左肘单向弯 0~149°），手臂举不过头顶正上方。用户要的动作先做可达性扫描再承诺。
- 扫描模板：多关节 for 循环 + 限位检查 + `getLinkState` 读腕位筛选（目标高度/横向/对称性），按评分取最优。

## 3. 安全验证

- 逐关键帧限位校验（lo-0.05 ≤ rad ≤ hi+0.05）。
- 自碰撞检测前先在 **home 位采集静态接触对**作 baseline（颈部/腰部连杆零位即贴合，属正常），再排除灵巧手内部连杆（Gripper/Hand 同侧互碰是机械常态）。动作位新出现的接触对才是真碰撞。
- **用户规定的硬规则**：会自碰撞的轨迹拆成多个子动作（插入安全中间姿态）；复位必须沿执行路径逐步倒序退回，不直接跳回零位。

## 4. 预览图（发给用户确认）

- pybullet TINY renderer 输出的模型是浅灰（像素 ~150-230）——判空用 `sum<730`，**不要用 `<450`**（会把渲染成功误判为白图）。增强对比：模型像素 ×0.55 压暗、背景换浅蓝。
- 三视图 = 正面/侧面/俯视（用户明确要求此三视角）。
- 发送前必须验证图非空白（暗像素计数>0）。
- 飞书发送：`im/v1/images` 上传（`image_type=message`）拿 image_key，再拼 post 富文本；`/tmp/feishu-token.txt` 会过期，401/400 时重取 tenant_access_token。发文件给用户用 `im/v1/files`，markdown 必须 `file_type=stream`（枚举只有 opus/mp4/pdf/doc/xls/ppt/stream）。
- 用户看图拍板：回「上」部署；说哪里不像就改参数重出图。**没确认不上机。**

## 5. 部署（三处同步）

1. **动作库** `autolife_robot_arm/robot_action.json`：三重备份（`.bak.<日期>.{1,2,3}`）后加关键帧数组（move+duration / wait+time）。
2. **对话工具** `autolife_robot_vision/robot_tools/control_robot_action.py`：四处同改——TOOL_SCHEMA 的 `enum`、`enumDescriptions`（中文说明帮 AI 理解何时用）、`description` 动作列举、`run()` 内 `valid_actions`。改完 `python3 -m py_compile` 验语法。
3. **prompt** `assets/prompt/prompt.txt`：动作清单行加 `name（中文）`；使用规则行加触发词（说"X/X个X"时调用 name）。
4. 迎宾轮播在 `face_detection.json` 的 `action[0].slideshow_mode`（如果动作要进打招呼序列）。

重启：**arm-control（加载动作库）+ vision（加载 enum/prompt）+ face-detection（联动硬规范）**。只重启一个会出现「AI 调了但动作库没有」或反之。验证：动作数、`'name' in d`、四服务 active。

**删动作 = 同样三处**（动作库 pop + enum 移除 + prompt 触发词移除），进了迎宾序列的还要从 face_detection.json 拿掉。

## 6. 动作编排要领（自然感）

参考人类运动学研究的结构：
- **三阶段**：伸手（reach）→ 接触（contact）→ 收回（return）；接触期再分预停→主动作→松停。
- **钟形速度**：关键帧时长分配慢-快-慢（如 1.2s→0.8s→0.4s），先抬臂后前伸（肩部两轴峰值分离），不要匀速直插。
- 摇晃类动作（握手）由肘部主导小幅 ±4°，0.35s/次。
- 先查同类研究文献再编排（用户会要求"先搜网上的正确姿势"），不要凭直觉设计人形手势。

## 7. 已知坑

- **pkl 动作可能播放即崩**（wave 实锤：回放触发编译 .so 异常 + rclpy logger 连锁，动作线程死亡手臂僵住）。崩溃的动作**重定义为关键帧版本**即可修复；idle 系列 pkl 正常（不能一刀切禁 pkl）。
- 动作库里可能有**僵尸条目**（json 注册了但 action_pkls/ 缺文件，如 316 的 idle4-6）——跨机拷动作前 `ls` 确认 pkl 真实存在，不要照 json 清单抄。
- 机器人重启后 NetBird 会重新注册换条目（IP 变），连机优先内网 WiFi IP + `hostname` 验身。
- 用户对动作效果不满意时先问清参照物（发图/描述），机械极限做不到的（如举不过头顶）如实说明，不要硬凑不像的近似解反复消耗确认轮次。

## 与其它技能衔接

- prompt/工具链路、AI 触发动作的 provider 配置：`autolife-robot-prompt-ops`（用户所有，未 curator 管理）
- 连机/找 IP：`autolife-find-robot`；检修：`autolife-doctor-operations`
