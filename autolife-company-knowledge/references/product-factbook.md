# AutoLife 产品速查（S2 / S1 / W1）

> 出处缩写：`00` = wiki/manuals/autolife-s2/00-索引.md · `03` = 同目录 03-Autolife-S2使用手册-摘要.md · `02` = 同目录 02-VR摘要 · `deep` = wiki/robot-install-manual-deep-analysis-2026-08-10.md · `s1` = wiki/robot-autolife-s1-263-2026-08-07.md · `w1` = wiki/robots/W1-robot.md · `fs` = knowledge/feishu-study/。引用前回源核对版本。

## Autolife S2（第二代主力机型）

- 形态：双臂移动操作机器人；**26 DoF + 2 自适应夹爪**（03 §2.1）
- 续航 **>10 h**；最大移动速度 **1 m/s**（03 §2.1）
- 感知：前后双激光雷达各 **250° FOV，合并 360°**；SLAM 自动导航 + 周身多传感器（00 / 03 §2.3）
- 交互：VR 遥操（实时视频 **<120ms**）+ OpenAI 自然语音对话（用户自备 API Key）（03 §2.1、02）
- 算力：x86 主机（真机实测 Intel Core Ultra 9 185H，非 Jetson）+ 可选 GPU 算力板 + 5G 模块双网口（deep §0.2）
- 软件栈：Ubuntu 24.04 + ROS 2 Jazzy + CycloneDDS；systemd --user 服务；Web 管理页 `http://192.168.10.2:3001`；conda env `robot_env`（00）
- 网络：5G SSID `Autolife_S2_<编号>` / 密码 `<编号>@Autolife`；机器人 IP/MAC 绑定 192.168.10.2；路由器 192.168.10.1（00）
- 配件：智能充电桩、VR 眼镜、安卓平板（03 §3.2）

## Autolife S1（第一代）

- 双臂移动操作机器人，现行 **v2.2**；架构与 S2 同源（s1）
- 真机参考：#263 部署于 192.168.65.207，13 个 systemd 服务（9 活跃 4 禁用）（s1）

## W1 人形机器人

- VR 遥操方向的人形机型；资料覆盖操作手册、ROS2 接口、故障排查（w1 子页）

## 配套生态

- VR 组合键：启动电机 `TL+GL+TR+GR`；实时视频 `X+Y+TL`；切换模式 `X+Y+A+B`；进 Sync 前摆同款姿势（00）
- 运维链：NetBird 远程组网、Inspection 硬件检测、动力学/运动学/语音标定（01 装机摘要）

## 落地场景

- 直营门店点单运营（语音/平板点单，微信/支付宝真实入账）（fs round7-notes）
- XR 二开大赛统一用机（智动未来机器人 + 操控平板，赛场断网、禁 AI）（fs SJLJdLov XR 赛事文档）
- 展会 / 具身智能训练场演示（fs MW8ndRnr 展示准备清单）
