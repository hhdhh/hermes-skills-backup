# 机器人诊断与维修

> 充实版（2026-09-13）· 原 644 字骨架扩充：故障模式分类、连接方式、授权边界、修复后检查。来源：402 机 DDS 阵营分裂修复实战 + 263 机 runbook。机器人 IP 是 DHCP 动态的——全部按机号定位，不写死。

## 连接方式

```bash
# SSH（密码统一管理，不在命令行回显明文；paramiko 助手 ~/.hermes/workspace/robssh.py）
# IP 不固定(DHCP 会变) —— 按 hostname `autolife-robot-<机号>` 识别, 不写死 IP:
# 全机队统一凭据 ${ROBOT_CREDS}(含 sudo), 主人 2026-09-13 授权直接检修
robssh.py scan --force        # 重新扫网段解析所有在线机器人 → robots.json
robssh.py list                # 机队一览: 机号 → 当前 IP
robssh.py 402 15 'hostname'   # 按机号直接执行(自动用解析到的 IP, ubuntu 用户)
robssh.py sudo 402 15 'cmd'   # 以 root 执行(sudo -S, 已在 0 号机实测)
```

- 网络：工作站与机器人同一内网（Wi-Fi `192.168.64.0/23` 网段）。
- 连不上时按 `network-connectivity-diagnosis` skill 的 4 层诊断（ping → ARP → 端口 → 服务），先排除机器人休眠/掉线。

## 基线 → 诊断 → 修复 → 复检（总流程）

1. **基线**：`autolife-doctor --once`（工作站侧）+ SSH 上机器人采集：`uptime`、`free -h`、`df -h`、`systemctl --user --failed`、`journalctl --user -p err --since -1h`。
2. **诊断**：按下方故障模式分类直奔检查点，避免从 22 项从头扫。
3. **修复**：最小改动。改 unit 后必 `daemon-reload` + `restart`。
4. **复检**：再跑一次 `--once` 对比；功能性验证用 WebSocket 前端（别只看 topic echo）。

## 常见故障模式分类

| # | 故障模式 | 典型症状 | 第一检查点 | 修复 |
|---|---------|---------|-----------|------|
| 1 | **DDS 阵营分裂** | 前端电池恒 100% / 数据僵死 / topic 查询 0 publisher | `systemctl --user show <unit> -p Environment` 看两套 CYCLONEDDS_URI | 把废弃单播派 URI 改组播版 + daemon-reload + restart（完整流程见 `autolife-robot-dds-camp-split` 技能） |
| 2 | **prompt 版本错位** | 对话啰嗦/破碎/行为异常 | `md5sum prompt.txt` 对照版本链（v10-reading = `9ea681d65ab392e2e5a732fdacdec773`） | 按 `autolife-robot-prompt-ops` 技能三重备份后替换 |
| 3 | **VAD/ASR 配置漂移** | ASR 断句乱、抢话 | `settings.toml`: `enable_hybrid_vad=true` + `asr_provider=qwen_realtime` | 对齐标准配置 |
| 4 | **TTS 读法问题** | 编号被读成日期（XX-XX） | prompt 是否要求逐位中文读法 | prompt 加"零二零九地块"式读法要求 |
| 5 | **服务改 unit 不生效** | 改了配置没变化 | `systemctl --user show <unit> -p Environment` 对比 | `daemon-reload` + `restart`（最常见的坑） |
| 6 | **服务挂了/failed** | 前端整体无响应 | `systemctl --user --failed` + `journalctl --user -u <unit> -n 100` | Safe 级服务 doctor 自动修（auto-safe）；Guarded 级先诊断根因 |
| 7 | **OTA 卡 phase** | 升级中途不动 | ota-version-state.md 流程查版本状态 | 按 OTA 状态机处理，勿盲重启 |
| 8 | **相机/视觉超时** | vision-service 反复重启 | `journalctl --user -u vision-service.service -n 200` 找超时/设备枚举错误 | 检查 USB/相机链路；Guarded 服务，restart 前说一声 |
| 9 | **开机白屏（kiosk 前端进不去）** | 机器人屏幕卡在"Loading..."白屏 | `systemctl --user is-active logo-backend` + `ss -tlnp \| grep 8000` | Chrome autostart 等 8000，logo-backend 没起来就白屏；先 `systemctl --user restart logo-backend`（详见下方"前端白屏"） |
| 10 | **上位机"No device found"** | 手机/桌面 App 扫不到本机机器人 | `cat ~/Documents/autolife-relay/conf/config.yaml` 看 `ip:` + `.env.production` 的 `PUBLIC_API_BASE_URL` | relay 通告的 IP 必须与上位机实际可到达的网络一致（详见下方"上位机设备发现"） |
| 11 | **上位机卡 connecting** | 设备列表拿到了但一直转圈 | 机器人 `tcpdump -i lan0 udp portrange 30001-30004 -c 30` 抓 30 秒 | 0 包到达 = 上位机端拉流地址缓存陈旧；杀 App 重连或重新发现（详见下方"卡 connecting"） |
| 12 | **arm 启动报"找不到 robot_vX_Y.json"** | arm service 启动时 `error: 找不到文件 .../descriptions/autolife_s1/dynamics/robot_vX_Y.json` | `ls <robot_env>/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/dynamics/` 看哪些是真文件（其他是 `.example`） | 备份 `autolife_robot_arm/settings.toml` 后把 `active_robot_version` 改回 SDK 实际有真 json 的版本号 → `systemctl --user restart arm-control-service.service`。**settings.toml 的版本号 ≠ SDK 实际部署 ≠ 硬件**——三个里任一对不上都会触发本症状。详见 [arm-startup-config-mismatch.md](references/arm-startup-config-mismatch.md) |
| 13 | **App 控制底盘没反应**（VR 数据到达 arm 但底盘不动 / 显示"VR disconnected"） | 整个 App→Server→Vision→Arm→GV 链路有一处断裂。**控制链路是单向 7 跳**：App UI → Rust-Web (云端 / 本地 192.168.10.2:3000) → Vision (vision-service 持有 robot device WS) → DDS /topic_arm_set_dexterous_hand_vr_cmd_0_0 等 → Arm main (ArmVrCmdHandler/GvVrCmdHandler) → DDS /topic_gv_target_cmd_vel_0_0 → GV control → mod_motor_gv (PCAN_USBBUS3) | 详见 [app-chassis-control-chain.md](references/app-chassis-control-chain.md) | 路径里任一跳坏都会导致"按了没反应"。**第一跳验证**：`journalctl --user -u rust-web-server` 看 `TIME_SYNC_REQUEST command received`（App 在连 + 收到 App 数据）；**最后一跳验证**：`ros2 topic hz /topic_gv_target_cmd_vel_0_0` 实际有数据（注意 `Publisher count: 1` 不可信，必须 hz 测），`journalctl --user -u arm-control-service` 看 `read_vr count fps` 实际频率，频率 ≈ 21 fps 但 cmd_vel topic 0 hz = arm 收到 VR 数据但未发底盘指令 |

## 服务分级（与 doctor repair-policy 一致）

- **Safe 级**（auto-safe 可自动 restart）：`rust-web-server`、`logo-backend`、`dashboard-backend`、`autolife-admin-build`、`autolife-relay`
- **Guarded 级**（restart 前必须说明）：`vision-service`、`gv-control-service`、`gv-slam-service`

## 最小修复授权边界

| 动作 | 授权 |
|------|------|
| 只读检查（白名单命令） | 直接做 |
| Safe 级服务 restart / doctor repair --safe-all | 直接做（auto-safe） |
| Guarded 级服务 restart | 说一声要动哪个、为什么，再动 |
| 机器人 prompt / 知识文件替换 | 三重备份 + md5 校验后才动 |
| mass-delete / 恢复出厂 / 系统 OTA 强推 | 必须主人明确批准 |
| 认证信息 | 只写凭据文件，不回显 |

## 修复后检查

1. `autolife-doctor --once` 对比修复前后。
2. 受影响服务 `systemctl --user status <unit>` 确认 active。
3. **端到端**：WebSocket 前端验证目标功能（电池数据、对话、导航）真的恢复。
4. 汇报：改了什么、前后对比、回滚命令。

## 工作站 vs 机器人的诚实语义（2026-09-13 原则）

工作站（kk-GDH-X）没有电机/传感器/急停硬件——`--once` 里这些项显示"未接入"**是诚实状态，不要伪造 probe 硬凑全绿**。唯一例外：应急开关曾因"未配置主因阻断"需要接入，用状态文件 `~/.local/state/autolife-doctor/emergency_stop.state`（恒 "0" 安全态）表达"工作站无需急停"。在机器人上跑 doctor 时，这些硬件 probe 才接真实驱动器状态文件。

---

## 前端白屏（Chrome kiosk 进不去 · 症状 9 详解）

**现象**：机器人开机后屏幕一直 "Loading..." 白屏，**手动 `systemctl --user restart logo-backend.service` 就恢复**。

**根因路径**：
- Chrome autostart（`~/.config/autostart/new_logo_display.desktop`）启动后跑 `logo_autostart.sh`，它写一个 `kiosk_loader.html` 轮询 `http://127.0.0.1:${KIOSK_APP_PORT}`（环境变量设 `KIOSK_APP_PORT=8000`），通了就把窗口跳到 `http://localhost:8000`。
- `logo-backend.service` 的 `ExecStartPre=/bin/sleep 20`，等 20 秒后才真正跑 `python -m autolife_robot_kiosk.main`（Uvicorn 起在 8000）。**它本身已经 enabled**，但开机时启动序列出问题：
  1. `enabled` ≠ `started`：boot 日志里没有 `Starting logo-backend.service` = 开机根本没排队起它（极少见，主要在用户 unit 异常时）。
  2. 起来后 ROS2 节点崩：`journalctl --user -u logo-backend | grep -A20 ExternalShutdown` → `rclpy.executors.ExternalShutdownException`。原因是同时开机自启的感知服务（`rgbd_shm_service.py` / `autolife_media_pointcloud.adapter` / lidar / arm）在抢共享内存（`posix_ipc.ExistentialError: No shared memory exists with the specified name`）和 `/dev/video*`，把 logo-backend 的 ROS2 依赖拖死。手动重启时这些服务早已稳定，所以一重启就好。
  3. 配置漂移：`logo-backend.service` 里有 `Environment="CYCLONEDDS_URI=...127.0.0.1..."`，这是单播派，参考 `autolife-robot-dds-camp-split`。

**诊断**：
```bash
# 1. 服务是不是 active
systemctl --user is-active logo-backend
# 2. 8000 端口有没有监听
ss -tlnp | grep 8000
# 3. 开机有没有排过起它
journalctl --user -b | grep -E "Starting logo-backend|Started logo-backend|ExternalShutdown"
# 4. 现场拉起能不能恢复（治标）
systemctl --user restart logo-backend.service
```

**根治方向**：
- **加长感知竞速窗口**：把 `logo-backend.service` 的 `ExecStartPre=/bin/sleep 20` 改到 `sleep 45`（治标但有效，等感知就绪）。
- **加 systemd 依赖**：`[Unit]` 段加 `After=rust-web-server.service`（最稳的基础依赖），或 `Wants=` 等其他感知服务（需要先弄清感知服务对应的 systemd unit 名）。
- **确认开机确实排到了队**：用 `systemctl --user show logo-backend -p UnitFileState`（应为 `enabled`），`ls -la ~/.config/systemd/user/default.target.wants/logo-backend.service` 确认 symlink 存在。

---

## 上位机设备发现失败（"No device found" · 症状 10 详解）

**现象**：手机 App / 桌面 App 列表里看不到本机机器人；扫描不到设备。

**核心规律**：机器人**多网卡**（常见 `lan0` 静态 `192.168.10.2/24` + `wlo1` DHCP `192.168.65.x/23`），**relay 通告的 IP（config 里 `ip:` 字段）+ admin 端点（`.env.production` 的 `PUBLIC_API_BASE_URL`）必须与上位机实际可到达的网络对齐**。

**决策矩阵**（上位机连法 → 应配的 IP）：

| 上位机连法 | 上位机所在网段 | relay/admin 该配 |
|----------|--------------|-----------------|
| 手机/电脑 WiFi 连现场 | `192.168.65.x`（同机器人 wlo1） | `192.168.65.x`（机器人在 WiFi 上当前真实 IP） |
| 手机/电脑 网线直连机器人 lan0 | `192.168.10.x`（手机需手配） | `192.168.10.2` |
| 远程/办公室经 NetBird | `100.98.x.x` | 写机器人 NetBird IP（通常配合云端信令，这里是特殊情况） |

**配置位置**（每个都查一遍）：
```bash
# 1. relay 通告 IP（手机拉视频流去连的地址）
grep -E "^[[:space:]]*ip:|server_url" ~/Documents/autolife-relay/conf/config.yaml
# 2. admin web UI 的 API 基地址（前端连的）
cat ~/Documents/AutolifeRobotAdmin/.env.production
# 3. 当前机器人实际网卡地址
ip -4 addr show | grep inet | grep -v 127.0.0
```

**改配 + 重启（标准姿势）**：
```bash
# 改完后必须 restart 服务才能加载新配置
systemctl --user restart autolife-relay.service
systemctl --user restart autolife-admin-build.service
# 验证：端口 3000 / 3001 / 9001 / UDP 30001-30004 全在听
ss -tlnp | grep -E ":3000|:3001|:9001"
ss -ulnp | grep -E ":3000[1-4]"
```

**隐藏坑**：
- **`lan0` 没有 DHCP 服务**：机器人 lan0 是静态 `192.168.10.2`，**不会给客户端分配地址**。手机/电脑插网线拿不到 10.x 地址就掉到 169.254 自配网段，跟 10.2 不同网段，必须手动在手机上配静态 IP（IP=10.x，掩码=255.255.255.0，网关=10.1 或 10.2）。如果发现 10.x 有邻居（如 10.1/10.163），那是同一交换机上**别的设备**（如 4G 路由器/网关）给的 DHCP，不是机器人。
- **多台机器同网段都设 192.168.10.2**：会 IP 冲突。两台都设了 10.2 同网段 → 时通时不通、ARP 表漂移。配 10.2 前先确认没有第二台用同地址。
- **DHCP lease 抖动**：WiFi 上 65.x 不稳时，机器人实际地址会变，配置里写死的旧值就跟机器人当前真实地址对不上了。每次重大配置变更后看 `ip -4 addr` 确认实际值。

---

## 上位机卡 connecting（症状 11 详解）

**现象**：设备列表拿到了，但点连接后一直转圈 "connecting..."。

**与症状 10 的区别**：
- 症状 10 是**找不到设备**——根本不知道有这台机器人。
- 症状 11 是**知道有设备，但握手/拉流失败**——通常卡在第二步"建立拉流 UDP 连接"。

**关键诊断：抓 30 秒 UDP 包**（在机器人上，要 root）：
```bash
sudo tcpdump -i lan0 -n -nn "udp portrange 30001-30004" -c 30
```

| 抓包结果 | 含义 |
|---------|------|
| **30 秒 0 包** | 手机 App 没在发拉流请求 → App 端拉流地址缓存陈旧，不是机器人侧的问题 |
| 有包到达但 relay 日志没连接记录 | 端口被监听但握手没建立，看 relay 日志找上层失败 |
| 有包到达 + relay 拒绝 | relay 配置里 `region`/`license`/`service_auth` 不匹配，看 relay 启动日志 |

**根因**：
1. **手机 App 缓存了旧拉流地址**：用户先用 WiFi 连过机器人（relay 通告 65.x），App 缓存了那个地址。换网线直连 lan0 后，机器人通告的是 10.2，但 App 没刷。
2. **服务端缓存了旧设备 IP**：rust-web 在内存里记了设备上次的心跳地址，跟手机当前网络不通。
3. **防火墙挡 UDP**：少见，但部分手机系统对 UDP 直连有限制。

**修复（按操作代价递增）**：
1. **杀 App 进程重开**（最快）——清除本地拉流地址缓存。
2. **App 里"重新发现设备" / "删除设备后重新添加"**——强制重走发现流程。
3. **检查手机网络切换**：如果手机**同时连着 WiFi + 网线**，部分 App 优先走 WiFi 出站 → 拉到旧 IP 失败。**关掉 WiFi 仅留网线**再连。
4. **改客户端手机静态 IP**：网线直连 lan0 时，确保手机 IP 真的是 10.x（设置里看）；不是 10.x 就跟机器人 10.2 不同网段。
5. **最后才怀疑机器人侧**：上面都做了仍 0 包 → 看手机 App 配置的服务端 IP 是不是对的，是不是手机 App 自己版本不支持当前机器人版本。
