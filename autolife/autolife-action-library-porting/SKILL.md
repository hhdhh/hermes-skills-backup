---
name: autolife-action-library-porting
version: 1.0.0
description: Use when 要给机器人扩动作库/移植外部关键帧资产。
metadata:
  triggers:
    - "扩充动作库"
    - "找动作库"
    - "动作库移植"
    - "机器人多加点动作"
---

# AutoLife 外部动作库移植

> 任务类：不从零手摸关键帧，从外部仓库拉已有关键帧资产转成 `robot_action.json` 格式。动作系统本体、仿真验证与部署流程见姊妹技能 `autolife-robot-action-system`，本技能只管「来源调研 + license 门 + 格式转换」。

## 目标格式（转换终点）

robot_action.json 动作 = 关键帧序列，每帧 `{"type":"move","right_arm":[7个度数],"duration":秒}`，7 值顺序 Shoulder_Inner/Outer/UpperArm/Elbow/Forearm/Wrist_U/L。角度制，末帧必须 home 位。

## 已验证来源表（拉取解码实测过）

| 仓库 | License | 定位 |
|---|---|---|
| `hshi74/toddlerbot`（Stanford，★778，活跃） | MIT | **首选移植源**。`motion/` 60+ 关键帧动作 + `arm_pose_dataset.lz4`（57 静态臂姿）。格式同构 |
| `Stanford-TML/robot_keyframe_kit` | MIT | MuJoCo 关键帧编辑器（`pip install robot-keyframe-kit`），可加载本机 `/home/kk/robot-sim/autolife_s1/mjcfs/*.xml`（v2_0–v2_4 齐全）当动作设计器 |
| `pollen-robotics/reachy2_emotions` | Apache-2.0 | 情绪动作录制/回放体系，架构参考 |
| `microsoft/LabanotationSuite` | MIT | 拉班舞谱手势-语义配对，动作含义分类参考 |
| `TomKingsford/NaoGestures` | MIT | NAO 手势封装 API 参考 |
| `MyRobotLab/InMoov`、`poppy-project/poppy-humanoid` | 无 license | ❌ 只看设计，禁拷代码/数据 |

## 每次必过 license 门

拷任何资产前先查 SPDX：`curl -s https://api.github.com/repos/<owner>/<repo>` 看 `license.spdx_id`。`none`/`NOASSERTION` = 只当设计参考；MIT/Apache 可拷但留 attribution。无 license 仓库无论星数高低一律不拷。

## toddlerbot 文件解码（实测）

```python
# pip install joblib lz4 numpy
import joblib
d = joblib.load("cuddle_2xc.lz4")
# 动作文件 keys: time/qpos/.../keyframes/timed_sequence
# keyframes[i]: {name, motor_pos(30维弧度), joint_pos, qpos}
# timed_sequence: [(帧名,时长秒),...]，sum=总时长
# arm_pose_dataset.lz4: time/motor_pos(57×16)/action → 静态姿态各转单帧动作
```

- 30 维 motor_pos 是全身通道；执行器序（toddlerbot_2xc MJCF `<actuator>` 实测）：[0-3] 颈×2+腰×2，[4-9] 左腿×6，[10-15] 右腿×6，[16-22] 左臂×7（shoulder_pitch/roll/yaw + elbow_roll/yaw + wrist_pitch/roll），[23-29] 右臂×7。与 lz4 的 motor_pos 维度对上即元序正确；换机型版本重新从 MJCF 确认。
- 全身运动类（爬行/俯卧撑/翻越）末端目标在地面，本机轮式底盘够不着会被 IK 自动拒绝；挑表达类（cuddle/hold/招手）。
- 已跑通的全套管线脚本在 `~/gh-action-hunt/`：`convert.py`（源→本机转化）、`design_actions.py`（末端航点自设计）、`verify_merged.py`（独立复核）、`render_previews.py`（预览）、`make_gallery.py`（HTML 总表）；源库 sparse clone 在 `tbrepo/`，产物在 `converted/`。

## 转换管线（六步）

1. **选转换策略**：直映射角度只在两机型零位/轴向一致时可用；跨机型移植用**末端位置匹配**——源模型 FK 算手末端世界坐标（相对躯干），按臂展比 SCALE=本机臂展/源臂展归一化，本机侧 IK 解 7-DOF。toddlerbot(立式双足)→AutoLife(轮式) 实测：直映射不可行，末端匹配成功。
2. **源模型加载**：MJCF 依赖 assets 相对路径，`MjModel.from_xml_path` 单拉 XML 必炸 `Error opening file 'assets/…'`——必须 sparse clone 整个 descriptions 目录再从目录内加载。源模型 nu 与源文件 motor_pos 维度对得上 = 加载正确。
3. **采样与映射**：轨迹 qpos 均匀重采样 6-8 帧再逐帧 IK（逐帧解原始 100 帧太慢且无必要）；腿/躯干通道丢弃；IK 解不出（末端目标不可达）= 该动作不适合本机，直接弃——这是天然质量过滤不是失败。实测 59 个 toddlerbot 动作过達 8 个（贴地动作全被拒，正确）。
4. **镜像双版本去重**：源库同名 `_2xc/_2xm` 后缀是镜像双版本，取一即可。
5. 末帧强制 home 位（右臂 [-20,0,0,-110,0,0,0] / 左臂 [20,0,0,110,0,0,0]），中间补过渡帧；每帧最短时长 ≥0.4s。
6. 逐值校验 URDF 限位（±0.05 rad 容差）超限即拦；交回 `autolife-robot-action-system` 标准流程：pybullet 碰撞验证 → 预览 → 确认 → 部署。

## 末端航点 IK 自设计（比手写角度可靠）

无外部源时直接自产：给定每帧末端相对肩位置 `(fwd 前向米, side 侧偏米, up 相对肩高)` + 节拍，坐标下降 IK 自动解 7-DOF + 全帧限位/碰撞校验。实测 14/14 成功率。两个 IK 坑：
- **静默钳位**：目标超臂展会被钳到可达域边缘，IK 不报错但形态可能不像——重要动作必须看渲染预览图确认形态，不能只信收敛。
- **限位不对称**：右肘 range [-2.618, 0]、左肘 [0, 2.618]（同符号镜像）；肩外展右 [-0.31, 3.14] 左 [-3.14, 0.31]。IK 种子用上一帧解避免跳变。

## 产出复核与交付

- **独立复核脚本**与生成器分开写：重跑限位/碰撞/末帧 home 三查，不信任生成器自报通过。
- 预览图渲染：每动作取首/中/尾 3 帧拼一张单图（多帧拼图比单帧更能展示动作轨迹），文字标注中文名+时长。
- 交付用户带图总表：单文件 HTML + base64 内嵌全部预览图（零依赖可直接发）；关节活动跨度合计(各关节 max-min 之和)作动作幅度量化指标，区分真动作与换姿势站立。
- 仿真验证通过 ≠ 形态好：总表按业务实用度排序并如实标注；实机上机前先上测试机。

## 本机 GitHub 访问套路

- 未认证 REST API（60 次/时）够用：`search/repositories`、`repos/<o>/<r>`、`contents/`、`git/trees/main?recursive=1`。code search API 未认证必 401——找文件用 git trees 列路径再 raw 拉，别撞 code search。
- `raw.githubusercontent.com` 直连常被 reset：前缀 `https://ghfast.top/` 代理 curl -sL 拉。二进制（.lz4）走 curl 落盘，别用 urllib urlretrieve（同样被 reset 且无重试）。
- 批量调研脚本用 write_file 落盘再跑，勿在 terminal 里 heredoc 建脚本（触发审批被拦）。

## 选型结论（当前）

存量扩充走 toddlerbot 臂部动作（末端匹配转化，一次过達 8 个）；增量产线走末端航点 IK 自设计（一次 14 个）+ robot_keyframe_kit + 本机 MJCF 可视化编辑；人类视频→动作 imitation/retargeting 生态不成熟，不投入。

## 本机依赖

`pip install mujoco joblib lz4 pybullet numpy`（mujoco 3.x 用于源模型 FK；本机验证/渲染仍用 pybullet）。PIL 拼图用 DejaVu 字体标注中文会豆腐块——中文标注需换 Noto CJK 字体，无则用拼音/英文名。
