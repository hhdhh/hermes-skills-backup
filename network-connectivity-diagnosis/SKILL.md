---
name: network-connectivity-diagnosis
description: 网络连通性系统性诊断 playbook。当目标 IP ping/ssh/nc 全超时但设备可能还在网上时，按 4 层模型（物理链路 → IP 路由 → 端口服务 → 协议交互）逐层定位断点。覆盖 macOS zsh 注释坑、nc -G vs -w、ARP 缓存 vs 真实存活、interface 路由分流（en0 Wi-Fi vs en5 USB/虚拟网卡不同网段）、目标设备防火墙、SSH 服务未启等真实场景。Use when (1) `ping <IP>` 全 timeout (2) `ssh <IP>` Operation timed out (3) `nc -vz` 多个端口都连不上 (4) ARP 能看到但 TCP 全死 (5) 主人说"连不上某设备 / 某 IP 没人 / 帮我看看网络"。
---

# network-connectivity-diagnosis — 网络连通性 4 层诊断

> 背景：2026-08-08 主人 ping/ssh/nc 全 timeout 到 `192.168.10.2`，但 ARP 能解析到 MAC。教训：网络问题不在客户端而在"4 层断点"上，逐层查能省 90% 时间。

## 何时用本 skill

| 触发 | 走本 skill |
|---|---|
| `ping <IP>` 100% packet loss | ✅ |
| `ssh <IP>` Operation timed out | ✅ |
| `nc -vz` 多端口都 Operation timed out | ✅ |
| ARP 解析到 MAC 但 TCP 全死 | ✅（最经典场景） |
| 主人说"连不上 / 帮我看网络 / 设备找不到" | ✅ |
| 浏览器/应用层失败但 ICMP 通 | ❌ 走 `chrome-headless-debug` 或对应应用 skill |

## 4 层断点模型（必背）

```
Layer 1  物理链路  → 网线 / Wi-Fi / 客户端隔离 / VLAN
Layer 2  IP 路由   → 不同网段 / 路由表 / 网关
Layer 3  端口服务  → SSH/HTTP/RDP 是否监听、防火墙
Layer 4  协议交互  → 认证 / 密钥 / 协议版本
```

90% 的"ping/ssh 不通"是 **Layer 1-3**，Layer 4 只占 10%。

## 主人 ABSOLUTE 模式诊断话术

主人说"连不上某设备"——按以下节奏回（**不反问选档，直接给全套命令**）：

1. **第 1 句**：先列 4 层模型，告诉主人查的方向
2. **第 2 段**：给 Layer 1-3 的所有命令（每条独立一行，不带注释避免 zsh 报错）
3. **第 3 段**：补目标设备本地自查清单（Windows / Linux / 机器人控制器）
4. **第 4 句**：让主人把输出贴回来，**不要自己抢答"肯定是 X"**

## 诊断 4 件套（macOS 客户端）

**⚠️ 重要前置**：macOS 默认 zsh **不把 `#` 当注释**。命令块里只能放纯命令，不能放说明行；否则会刷 `zsh: command not found: #`。

如果主人贴的命令块含注释报错，先发：

```bash
setopt interactivecomments
```

### Layer 1 · 物理链路
```bash
ipconfig getifaddr en0
ipconfig getifaddr en5
ifconfig en5
networksetup -listallhardwareports
```

### Layer 1.5 · 看目标 ARP 状态
```bash
arp -n 192.168.10.2
sudo arp -d 192.168.10.2
ping -c 1 -W 1000 192.168.10.2
arp -n 192.168.10.2
```

**判断**：
- ARP 显示 `(incomplete)` → 设备不在线 / 隔离
- ARP 有 MAC 但 ping 不通 → 设备在线但禁了 ICMP，看 Layer 2-3
- ARP 清不掉 → 缓存强占，看路由器上是否绑死

### Layer 2 · 路由
```bash
route -n get default | grep gateway
route -n get 192.168.10.2
```

**判断**：
- 走错 interface（如 en0 Wi-Fi 网段走 en5 USB）→ 物理拓扑问题
- 不同网段（Mac `192.168.65.x` → 目标 `192.168.10.2`）→ 走 en5 是关键信号，可能 USB 网卡 / 桥接 / 虚拟网卡

### Layer 3 · 端口服务
**macOS nc 用 `-G 2`，不是 GNU 的 `-w 2`**：

```bash
for p in 22 80 443 2222 3389 5900 8080 8443; do
  nc -vz -G 2 192.168.10.2 "$p"
done
```

**判断**：
- 全部 timeout → 目标防火墙/服务全开拒绝
- 部分端口通 → 特定服务活着，定位要连的端口
- 通了但 ssh 失败 → 跳到 Layer 4

### Layer 4 · SSH 协议（最后才看）
```bash
ssh -v -o ConnectTimeout=5 192.168.10.2 2>&1 | head -30
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 user@192.168.10.2
```

## 目标设备本地自查清单

### 如果是 Windows
管理员 PowerShell：
```powershell
ipconfig
Get-NetIPAddress -AddressFamily IPv4
Get-NetConnectionProfile
Get-NetFirewallProfile
Get-Service sshd
Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue
```

如果 SSH 没装：
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd -DisplayName "OpenSSH SSH Server" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

防火墙开 ICMP（让 ping 通）：
```powershell
New-NetFirewallRule -DisplayName "ICMPv4 Allow Ping" -Protocol ICMPv4 -IcmpType 8 -Direction Inbound -Action Allow -Profile Any
```

### 如果是 Linux
```bash
ip -4 addr
ip route
sudo ss -lntp
sudo systemctl status ssh
sudo nft list ruleset
sudo iptables -L -n -v
```

### 如果是机器人控制器 / 嵌入式
- 看串口 console（不依赖网络）
- 看设备面板上 LED（Wi-Fi/有线指示）
- 重启设备 → 看是否能被路由器客户端列表发现
- 看路由器后台的 DHCP 客户端列表

## SSH 工具推荐（主人要装客户端时给）

| 场景 | 工具 | 装法 |
|---|---|---|
| 快速图形化 | **Termius** | `brew install --cask termius` |
| 开源免费 | **Tabby** | `brew install --cask tabby` |
| 移动端 | Termius iOS/Android / Prompt 3 | App Store |
| 远程开发 | VS Code Remote -SSH / JetBrains Gateway | 插件市场 |
| 弱网稳定 | **Mosh** | `brew install mosh` |
| 内网穿透 | Tailscale + SSH | `brew install --cask tailscale` |
| 端口扫描 | **nmap** | `brew install nmap && sudo nmap -Pn -p 22,80,443 192.168.10.2` |

## 常见诊断陷阱

| 坑 | 表现 | 真相 |
|---|---|---|
| ARP 有 MAC = 设备在线 | TCP 全部 timeout | ARP 是二层协议，三层被防火墙拦截也会这样 |
| 客户端不同网段是错的 | Mac en0 192.168.65.x / 目标 192.168.10.2 走 en5 | 可能是 USB 网卡 / Docker bridge / OrbStack 桥接 |
| `ping` 不通 = 设备离线 | TCP 22 通畅 | 多数防火墙只挡 ICMP，不挡 TCP |
| 改 SSH 端口能解决 | 还是 timeout | 端口不通是 Layer 3 问题，不是 Layer 4 协议问题 |
| 重启路由器能修 | 客户端 MAC/ARP 缓存未清 | 客户端要 `sudo arp -d` 同步清 |
| `nc -w 2` 不超时 | 超时反而是 macOS 成功 | macOS nc 不支持 `-w`，要用 `-G` |

## 不该说 / 容易踩雷

- ❌ "肯定是 X"——你看不到目标设备的实际状态
- ❌ 列选项问"你选 1/2/3"——主人 ABSOLUTE 模式要一键全套
- ❌ 命令块带 `# 说明`——zsh 直接报错
- ❌ 重复同一个 nc 命令 N 次浪费时间——直接 `for p in ...` 扫一轮
- ❌ 让主人重启路由器——这是 Layer 1 最后手段，先用软件层清 ARP

## 文件清单

| 文件 | 用途 |
|---|---|
| `SKILL.md` | 本 playbook（4 层模型 + ABSOLUTE 话术） |
| `references/mac-pitfalls.md` | macOS 特有坑（zsh 注释 / nc -G / interface 路由） |
| `references/target-side-diagnostics.md` | Windows / Linux / 嵌入式目标设备本地诊断 |
| `references/decision-tree.md` | 4 层模型对应的输出 → 结论决策树 |
| `templates/ssh-config-template.conf` | `~/.ssh/config` 优化模板（含 KeepAlive / ProxyJump） |
| `scripts/connectivity-probe.sh` | 一键跑 4 层诊断，输出可读报告 |

## 验收 checklist

- [ ] 命令块纯命令，零注释行
- [ ] 4 层模型先说清楚，再给命令
- [ ] 不抢答"肯定是 X"
- [ ] 含目标设备本地自查清单
- [ ] 含 SSH 工具推荐

---

_2026-08-08 真实 session 沉淀_
_4 层模型 · macOS 注释坑 · nc -G · interface 路由分流 · ABSOLUTE 话术_
