# DDS 阵营分裂排查修复

<!-- capability_id: cap.autolife-ops.dds-split | revision: 1 | status: active -->
<!-- 来源: S2前端电池恒显100%排查修复记录(402) + 案例001 + 402检修记录（飞书语料） -->

## R — 原文

> 分别用两套 DDS 配置订阅同一电池话题：GV驱动侧配置✅数据正常1Hz，kiosk侧配置❌一条都收不到。kiosk日志铁证：selected interface "lo" is not multicast-capable: disabling multicast
> —— 《S2前端电池恒显100%排查修复记录(402)》

## I — 自述

机器人上的 systemd 服务按 CYCLONEDDS_URI 写法分成两个互不相通的"阵营"：组播派（NetworkInterface name="lo" multicast="true"，gv 系服务）和单播派（废弃写法 NetworkInterfaceAddress 127.0.0.1，kiosk/vision 系）。阵营间 DDS 发现互相不可见——驱动服务好好的在发数据，前端就是收不到。

诊断的关键是**对称测试**：分别 export 两套 URI 订阅同一个 topic，一套有数据一套没有，就是阵营分裂实锤。最隐蔽的陷阱是 ros2 CLI 自己也是一个 DDS 进程，它用哪套 URI 就只能看见哪个阵营——跨阵营查询永远显示 0 publisher，会误导你以为驱动挂了。

修复 = 统一 URI 写法：把单播派 unit 的 CYCLONEDDS_URI 改成与 gv-control 相同的组播版，daemon-reload + restart。前端显示的 100% 只是打包时写死的初始默认值，收不到数据就永远停在那。

## A1 — 书中案例

**案例类型：书中亲历案例**（402 S2 前端电池恒 100%）

- 输入/问题：前端电池恒 100% 充电中，底盘话题僵尸，gv 驱动 active
- 方法执行：读 /proc/<pid>/environ 对比各进程 CYCLONEDDS_URI → 发现 kiosk 与 gv 用两套配置 → 对称测试：GV 侧订阅✅1Hz，kiosk 侧订阅❌全空 → 阵营分裂实锤
- 结论：改 kiosk unit URI 为组播版 → daemon-reload → restart → 前端电池数据恢复实时

## A2 — 未来触发 ★

**情境：**

1. 前端电池/状态恒定不变（僵尸数据），但服务全 active
2. ros2 topic info 显示 0 publisher，但驱动服务日志在正常发数据
3. 新装的 kiosk/vision 服务与老 gv 系服务互相看不见对方话题
4. 同一机器人上"一半话题正常一半全空"

**语言信号：**

- "电池恒100%" / "前端数据不变" / "话题僵尸"
- "ros2 查询 0 publisher" / "话题互相看不见"
- "两套 CYCLONEDDS_URI" / "DDS 阵营"
- EN: "battery stuck at 100%" / "topic invisible between services" / "cyclonedds uri mismatch"

**区分：**

- ≠ autolife-robot-diagnosis：那是通用五层找断点流程；本卡是断点定位到 DDS 层后的**专项修复**
- ≠ autolife-slam-troubleshooting：建图空白也可能由阵营分裂引起（先跑本卡的对称测试排除），但 SLAM 链还有自己的病（雷达 merger 硬编码等）
- ≠ autolife-robot-dds-camp-split（旧技能）：本卡是其 v2 精编版，源自同一案例库的更完整记录

## E — 可执行步骤

**输入契约**：机号或 IP（必填，SSH 可达）；疑似僵尸话题名（建议提供，如 /battery_status）；目标服务名（可选，默认比对 gv-control 与 kiosk/vision 系）。

**Step 1 症状确认**：`ros2 topic hz <topic>` 在默认环境下查——若 0 publisher 别急着判死，进 Step 2
**Step 2 提取两套 URI**：
```
systemctl --user show gv-control -p Environment | grep CYCLONEDDS
tr '\0' '\n' < /proc/$(pidof kiosk前端进程)/environ | grep CYCLONEDDS
```
对比 gv 系 vs kiosk/vision 系的写法差异（组播 lo vs 单播 127.0.0.1）
**Step 3 对称测试（决定性）**：
```
export CYCLONEDDS_URI=<gv版>; ros2 topic hz <topic>   # 预期有数据
export CYCLONEDDS_URI=<kiosk版>; ros2 topic hz <topic> # 预期无数据
```
一边有一边无 = 阵营分裂实锤
**Step 4 修复**：`cp` 三重备份 kiosk unit 文件 → 把 CYCLONEDDS_URI 改为 gv 组播版（NetworkInterface name="lo" multicast="true" + AllowMulticast + ParticipantIndex=none）→ `systemctl --user daemon-reload && systemctl --user restart <unit>`
**Step 5 验证**：默认环境 `ros2 topic hz` 有数据 + 前端数值开始变化（不再恒 100%）

**判停点**：Step 3 两套都有数据 → 不是阵营分裂，回 autolife-ops-robot-diagnosis 卡继续找断点；Step 4 改完 Step 5 仍无数据 → 查 unit 是否真的加载了新 URI（show -p Environment 复核）

**输出契约**：阵营对比表（服务｜URI 写法｜阵营）+ 对称测试结果 + 修复 diff + 验证截图/输出。

## B — 边界

- **不适用**：跨机器的网络不通（NetBird/路由问题）；前端 UI bug 但数据层正常；单纯的服务崩溃（走 autolife-ops-robot-diagnosis）
- **反场景**：组播版 URI 本身没错时不要反复改写法——先做对称测试拿证据再动手
- **失败模式**：ros2 CLI 环境与目标服务不同阵营导致误判"0 publisher"；只改 unit 不 daemon-reload；修复后不验证前端实际数值
- **相邻易混**：Discovery 参与者上限问题（nav2 14+进程爆上限）属 autolife-ops-slam-troubleshooting 卡范围，症状类似（互相看不见）但修法不同
