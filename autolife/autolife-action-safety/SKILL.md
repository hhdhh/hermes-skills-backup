---
name: autolife-action-safety
description: Use when 给机器人创建新动作（写 robot_action.
version: 1.0.0
---

# AutoLife S1 动作安全校验 + 危险动作自动拆分

> 完整描述：AutoLife S1 机器人新动作安全校验+危险动作自动拆分。Use when 给机器人创建新动作（写 robot_action.json 前）、动作描述→关键帧→仿真校验→预览图→确认部署全流程。

## 核心规则（管理员 2026-09-18 定）

1. 动作 = 一组关键帧（每帧 = {joint_name: angle}，rad）
2. **三级判定**：
   - `single`：限位✓ 无碰撞 → 可整体执行
   - `split`：有自碰撞但可拆 → 拆成 2+ 串行子动作（按运动链组）
   - `unsafe`：限位超界 / 拆两层仍碰撞 → 拒绝创建
3. **危险动作自动拆分**：一个动作会自碰撞时，按运动链组（torso_neck / left_arm / right_arm / legs）拆成串行子动作，每组单独校验，全部通过才算实现（"将一个动作拆成两个或多个动作去完成"）
4. 单臂本身就撞躯干（如深抱胸）→ 拆开也撞 → unsafe，物理不可行

## 工具链（本地 /home/kk/robot-sim/，已全部实测 2026-09-18）

| 文件 | 作用 |
|------|------|
| `action_splitter.py` | 主校验器：限位+自碰撞+自动拆分，读 split_test_cases.json 出 split_report.json |
| `autolife_s1/` | 官方 URDF+mesh（321 机拉回，robot_v2_2，46 关节） |
| `joints.json` | 关节限位表（name/lower/upper/type） |
| `render_previews.py` | 关键帧渲染 PNG 预览图（ER_TINY_RENDERER，免 GPU） |
| `gen_clap.py` / `find_mutual.py` | 测试位姿搜索（梯度优化找双臂互撞位） |

## pybullet 关键事实（踩坑记录）

1. **URDF 路径**：必须用 `autolife_s1/urdfs/robot_v2_2.urdf`（mesh 相对路径 ../meshes/ 能解析）；`models/` 下的裸 URDF 加载失败
2. **link idx == 该 link 父关节的 joint idx**：`getContactPoints` 返回的 linkIndexA/B 直接当 joint idx 上溯（`getJointInfo[16]` 是父 link idx）
3. **getJointInfo 需要 jointIndex 参数**（不能批量）；`info[12]` 是 child link 名，`info[16]` 是 parent link idx
4. **set_pose 必须先全归零**：帧里没提的关节要 reset 到 0，否则残留上一个测试的姿态 → 全是假碰撞
5. **零位基线白名单**：零位就有 13 对接触（夹爪指节、Neck↔Shoulder 接驳件 -0.0305）= 结构常态，初始化时收集成 baseline_pairs 过滤
6. **穿透阈值 -0.005m**：浅于 5mm 的接触是网格毛刺，忽略
7. **帧间插值必查**：两个安全姿态，插值途中也可能撞（check_frames steps=6）
8. **getCameraImage + ER_TINY_RENDERER** 无 GPU 出图；PIL 存 PNG
9. pybullet 的 b3Warning 噪音：重定向到文件再 grep，别管道 tail（exit code 会骗人）

## 判定算法（action_splitter.py 已实现）

```
validate(frames):
  1. 限位校验（joints.json）→ 违规 = unsafe/limit_violation
  2. check_frames：逐帧+插值6步 查碰撞（滤基线+浅毛刺）
     无碰撞 → single
  3. 碰撞归因：碰撞 link 上溯运动链 → 在动关节 → 链组
  4. 拆分：在动关节按组拆成串行子动作（torso_neck 先行→left_arm→right_arm→legs）
     每组递归 validate（max_depth=2）
     全过 → split（子 frames 已附在报告里，可直接部署）
     有 fail → unsafe（单臂也撞=物理不可行）
```

## 部署流程（对接机器人）

1. 管理员描述动作 → 设计关键帧
2. `python3 action_splitter.py`（或 import validate）→ 三级判定
3. `render_previews.py` 出预览图 → 发飞书给管理员确认
4. 确认后：split 的按子动作依次写 robot_action.json + 扩展对话 enum + prompt
5. 执行层安全网：限位校验 + 碰撞预检（关键帧序列先在仿真空跑）

## 实测用例（split_test_cases.json，全过）

| 用例 | 判定 | 说明 |
|------|------|------|
| safe_thumbs_up 点赞 | single | 基线安全 |
| danger_clap_hands 拍手 | **split** | 双夹爪互撞 -0.042m → 拆左右臂串行，各自 single ✓ |
| danger_cross_arms 抱胸 | unsafe | 前臂撞躯干中柱（单臂也撞）→ 物理不可行 |
| limit_violation 肘过限 | unsafe | 3.0 > 上限 2.618 |

## 注意

- 本地仿真用 robot_v2_2（S1/S2 通用骨架）；真机执行前仍需真机限位复核
- 拆分后的子动作是**串行**执行（先 A 后 B），中间回零衔接，不并发
