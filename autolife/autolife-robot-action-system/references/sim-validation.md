# pybullet 动作安全验证 + 三视图渲染配方

本地仿真验证新动作（不碰机器人）+ 出预览图给主人确认。

## 环境

```bash
pip install pybullet -i https://pypi.tuna.tsinghua.edu.cn/simple  # 默认源超时用清华镜像
```

模型：从机器人 `<sdk>/descriptions/autolife_s1/` 整包 tar 拉回本地（~45MB，含 urdfs + meshes），解压到 `/home/kk/robot-sim/autolife_s1/`。关节限位表从 URDF 读出存 `joints.json` 备查。

## 自碰撞检测（必做）

```python
import pybullet as p, math, json

cid = p.connect(p.DIRECT)
p.setAdditionalSearchPath('/home/kk/robot-sim')
robot = p.loadURDF('autolife_s1/urdfs/robot_v2_2.urdf', useFixedBase=True,
                   flags=p.URDF_USE_SELF_COLLISION)
joints = {p.getJointInfo(robot, i)[1].decode(): i for i in range(p.getNumJoints(robot))}
```

**先跑 home 姿态记 baseline**——URDF 零位有 2 对静态重叠（`Link_Neck_Roll_to_Neck_Pitch↔Link_Neck_Yaw_to_Head`、`Link_Waist_Yaw_to_Shoulder_Inner↔Link_Neck_Pitch_to_Neck_Yaw`），灵巧手相邻连杆（Gripper↔Gripper）也常接触，这些与动作无关。逐帧检测后排除 baseline 对和 Gripper 对，只报**新增碰撞**。

逐帧验证骨架：

```python
rmap = {0:'Joint_Right_Shoulder_Inner',1:'Joint_Right_Shoulder_Outer',2:'Joint_Right_UpperArm',
        3:'Joint_Right_Elbow',4:'Joint_Right_Forearm',5:'Joint_Right_Wrist_Upper',6:'Joint_Right_Wrist_Lower'}
# 动作库 right_arm 7 值是度数，URDF 用弧度
for vals in frames:  # 每关键帧
    for idx, jname in rmap.items():
        lo, hi = p.getJointInfo(robot, joints[jname])[8:10]
        rad = math.radians(vals[idx])
        if not (lo-0.05 <= rad <= hi+0.05): return '越限'  # 限位硬校验
        p.resetJointState(robot, joints[jname], rad)
    p.performCollisionDetection()
    # getContactPoints(robot, robot) → 过滤 baseline → 新增碰撞即不安全
```

## 三视图渲染（主人定的固定规范：正面 + 侧面 + 俯视）

```python
def render(path, yaw, dist=2.0, pitch=-8, target_z=0.9, fov=42):
    w, h = 480, 640
    view = p.computeViewMatrixFromYawPitchRoll(cameraTargetPosition=[0,0,target_z],
                                                distance=dist, yaw=yaw, pitch=pitch,
                                                roll=0, upAxisIndex=1)
    proj = p.computeProjectionMatrixFOV(fov, w/h, 0.05, 8.0)
    img = p.getCameraImage(w, h, view, proj, renderer=p.ER_TINY_RENDERER)  # 无 GPU 可用
    from PIL import Image
    Image.frombuffer('RGBA',(w,h),bytes(img[2]),'raw','RGBA',0,1).convert('RGB').save(path)

render('front.png', yaw=45)     # 正面
render('side.png',  yaw=130)    # 侧面
render('top.png',   yaw=45, pitch=-89, target_z=0.9, dist=2.2)  # 俯视（pitch 近垂直向下）
```

坑：
- `computeProjectionMatrixFOV` **位置传参**——kwarg 名 `nearval/farval` 大小写敏感，用 kwarg 会炸 `missing required argument 'nearVal'`。
- 取景前遍历全部 link 的 AABB 求总包围盒（`p.getAABB(robot)` 对 fixed base 常返回全 0）；机器人整机高约 1.70m，target_z 取中段 ~0.9。
- 渲染质量自检（vision API 不可用时）：PIL + numpy 统计非背景像素占比（正常 ~20%）。

## 发图给主人

飞书 post 富文本消息 + `im/v1/images` 逐张上传（multipart，`image_type=message`），4 图拼一条 post 消息。token 过期（99991663）重取 tenant_access_token。
