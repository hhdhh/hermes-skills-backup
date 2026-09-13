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
