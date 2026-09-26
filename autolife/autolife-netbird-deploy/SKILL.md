---
name: autolife-netbird-deploy
description: Use when a robot isn't on the company auto-lite mesh yet...
version: 1.0.0
---

# AutoLife NetBird 装机（给未入网机器人补装 mesh 通道）

> 完整描述：Deploy NetBird mesh access onto an AutoLife robot (patch install when GitHub is blocked). Use when a robot isn't on the company auto-lite mesh yet and 主人 says install/deploy NetBird, or a robot is unreachable cross-site. Covers GitHub-blocked corporate net → mirror-deb → dpkg → netbird up → verify.

> 用途：把一台尚未入网（或重装过系统）的 AutoLife 机器人加进公司自建 NetBird mesh，让现场/异地的 FAE 能跨网段 SSH 检修。
> 工具：`~/.hermes/workspace/robssh.py`（paramiko，push/sudo/nb 子命令）。
> 姊妹技能：`autolife-remote-repair`（入网后的检修闭环）、`autolife-s2-robox-wizard`（S2 装机的 netbird stage 同款逻辑）。

## 公司 NetBird 常量（内部资料，外发文档打码）

- mgmt URL：`https://netbird.autolife-robotics.com`
- setup key：硬编码在 `robox_combined_y2_wizard.py` 的 `netbird_setup_key`（S2 向导脚本，内部引用）。
- 机器人命名：`autolife-robot-<机号>.netbird.selfhosted`；mesh IP `100.98.x.x`。

## 标准流程（2026-09-16 在 404 机闭环验证）

```bash
# 1. 拿官方 deb —— 别跑官方 install.sh！公司网络掐 github.com:443，install.sh 从 GitHub 拉 deb 必 133s 超时
#    镜像代理(ghproxy.net 等)是可靠路径；先校验再装
curl -4 -fL --max-time 170 -o /tmp/netbird.deb \
  "https://ghproxy.net/https://github.com/netbirdio/netbird/releases/download/<vsn>/netbird_<vsn>_linux_amd64.deb"
sha256sum /tmp/netbird.deb && dpkg-deb -I /tmp/netbird.deb   # 确认 amd64 + 版本 + 非空

# 2. push 到机器(自带 md5 双端校验) → dpkg 本地安装(服务自动拉起)
python3 robssh.py push <机号|IP> /tmp/netbird.deb /tmp/netbird.deb
python3 robssh.py sudo <机号|IP> 90 "dpkg -i /tmp/netbird.deb || apt-get install -y -f; which netbird && netbird version"

# 3. 入网（management-url + setup key）
python3 robssh.py sudo <机号|IP> 90 \
  "netbird up --management-url https://netbird.autolife-robotics.com --setup-key <KEY>; sleep 3; netbird status"

# 4. 端到端验证
#    工作站 ping mesh IP(9ms 级) + netbird status --detail 反查注册名
#    + robssh.py nb <机号> 'hostname' 走 mesh SSH 确认
#    装完在 robots.json 登记机号 → mesh IP + 网卡表
```

判成功：`netbird status` 里 Management/Signal = Connected + 拿到 NetBird IP；工作站 ping 通该 IP + `autolife-robot-<机号>.netbird.selfhosted` 反查得名。

**刚入网 peers 计数是 0 属正常**：全局 `Peers count: N/M Connected` 的 M 是全网设备数，本机已连对端刚入网是 0——别人一 ping 就建立 lazy connection，别当成故障。

## 坑

- **`github.com:443` 被公司网掐死**（133s connect 超时），官方 `curl pkgs.netbird.io/install.sh | sh` 必失败。`api.github.com` 能出 JSON、`pkgs.netbird.io` 能回 HTTP 头，但 **body 下载也常超时**——别浪费时间在直连 source 上，直接上 ghproxy.net。
- **镜像代理的成功率按资产分**：ghproxy.net 对 >5MB 二进制/deb 稳（15MB deb ~40s），ghfast.top 对 codeload 归档稳。大 release 资产优先 ghproxy.net。
- **版本号**：装前用 `api.github.com/repos/netbirdio/netbird/releases/latest` 拿当前 tag，别写死旧版本。
- 装完 `netbird up` 若报 Already connected 是正常的（deb PostInst 已起服务）。
- dpkg 装完后 netbird 服务自动 start；若手动管理，`systemctl start netbird`。

## 与其它技能衔接

| 需求 | 去处 |
|------|------|
| 入网后常规检修闭环 | `autolife-remote-repair` |
| S2 出厂装机全流程 | `autolife-s2-robox-wizard --stage netbird` |
| GitHub 被墙下载更多种类资产 | `github-release-asset-download` |
