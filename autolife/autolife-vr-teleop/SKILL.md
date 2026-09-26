---
name: autolife-vr-teleop
description: AutoLife 机器人 VR 遥操（同步模式）排障
---

# AutoLife VR 遥操 / 同步模式排障

> 完整描述：AutoLife 机器人 VR 遥操（同步模式）排障。症状如"VR 连上后约N分钟自动退出同步""遥操不稳定""同步一直掉线"。覆盖 rust-web-server 信令中枢诊断（心跳/会话超时日志）、心跳/grace 容错调参、现场抓退出瞬间的持久日志采集 + 实时异常告警。与 autolife-remote-repair 配套（连接/文件运维见那边）。

> 触发："VR 遥操自动退出同步"、"同步不稳定、一直掉线"、"遥操连一会就断"、"224 遥操问题"。
> 姊妹技能：`autolife-remote-repair`（SSH 连接/文件运维）、`autolife-find-robot`（定位）。

## 信令中枢认知（关键）

- 机器人上跑一个 `rust-web-server`（本地信令中枢），vision / autolife-relay / VR 控制器都连它。
- 配置：`/home/ubuntu/Documents/rust-web-server/conf/config.yaml`（引 `bin/rust-web-server --config ...`）。
- 端口：TCP 3000（WS 信令），UDP 4000/4001/4002（video/data/audio 中继）。
- 遥操的"同步模式"靠信令会话维持，服务端判定离线后终止会话 → 表现为"自动退出同步"。

## 先确认网络拓扑（别急着改配置）

VR 遥操可能跨多段网（现场 192.168.10.x 独立段 + 192.168.64/65.x + 云端 43.x）。用 `ss -tnp | grep :3000` 看谁连信令、是否跨网段中继。反复掉线的 controller 往往就是那台 VR。

## 判定根因：抓退出瞬间

"持续操作也退出"是链路/会话问题，不是 VR 休眠。区分两类根因，靠**退出瞬间的日志关键词**一锤定音：

- `HEARTBEAT_TIMEOUT` / `GRACE_PERIOD_EXPIRED` / `offline by ticker` → 心跳断（链路不稳 / controller 掉线）
- `SESSION_CLOSED` / `CLOSE_SESSION` / `quest-expired` / `session actor passivated by idle timeout` → 服务端主动回收会话

**持久日志采集（systemd，独立于 SSH）**——采集器必须用 systemd user unit 拉起，不能用 nohup+`&`（SSH 一断进程就没了）。

```bash
# unit: teleop-capture.service (systemd user)
# [Service] ExecStart=/bin/bash -c 'exec journalctl --user -u rust-web-server.service -f >> /home/ubuntu/teleop_capture.log'
# Restart=always; systemctl --user enable + start
```

用 `push` 把本地写好的 unit 传到机器人（`~/.config/systemd/user/`），不要用 echo>dotfile（触发安全告警且易损坏）。落盘后 `tail` 确认在增长。

**实时异常告警**：本地 `bash` 循环轮询远端日志 `wc -l` 增量，新增行 grep 异常关键词（HEARTBEAT_TIMEOUT|SESSION_CLOSED|expired|offline|grace|disconnect|Failed|error），命中即输出 + 后台 `notify=['ALERT',...]` 触发推送。

## 修复：心跳容错调参

```yaml
# conf/config.yaml → mediator:
heartbeat_interval_secs: 5     # 心跳间隔
heartbeat_timeout_secs: 20     # N 秒没收心跳判离线（默认 7 太紧，放大容错）
reconnection.device_grace_period_secs: 15  # 重连宽限（默认 10）
```

- 改前备份：`cp config.yaml config.yaml.bak.$(date +%s)`（机器人上）+ 本地 `pull` 一份。
- 本地改 → `yaml.safe_load` 校验 → `push`（自带 md5 双端校验）。
- `systemctl --user daemon-reload` + `restart rust-web-server`，确认 `is-active` + 端口在听。
- 重启后确认设备重新 `register command accepted` + `connection established`，密钥指标是重启后 **0 次 HEARTBEAT_TIMEOUT**。

## 判断边界（诚实交付）

- 信令中枢本地可调的是**心跳/连接容错**；如果持续操作仍断，可能是 VR 端网络质量、跨网中继抖动，或遥控端/服务端另有会话回收策略（二进制里 `actor passivated by idle timeout` 等可能是硬编码，本机配置不暴露）。别打包票改配置必然根治——用日志证据说话。
- 采集器是**诊断**工具，抓准退出瞬间原因比继续堆配置改动有用。

## 已知坑

- `strings rust-web-server` 会 dump 几 MB 二进制字符串疯狂刷屏——别直接对完整二进制 strings 找超时值，那个徒劳（数值在编译里）。看 config + 运行日志即可。
- nohup `&` + `while break` 的 sh 写法做常驻服务不可靠（SSH 断即挂）——一律用 systemd user unit。
- 远端路径用完整 `/home/ubuntu/...`，`~` 会在本地 shell 展开成 `/home/kk/...` 而找不到文件。
- 改动信令中枢会影响所有在连的遥操会话，重启前确认无人在关键时刻用。
