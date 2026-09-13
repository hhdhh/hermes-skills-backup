---
name: network-troubleshooting-ssh
description: SSH / 端口 / 网络分层诊断。当主人说"SSH 连不上"、"连不上某 IP"、"ping 不通"、"端口连不上"、"网络有问题"时触发。覆盖 ARP→路由→端口→服务→认证五层决策树，macOS nc -G / Linux nc -w 的平台差异，Windows 防火墙/OpenSSH，Linux systemd/firewalld 常见配置坑。触发词：SSH 连不上、ping 超时、端口 timeout、连不上某 IP、connect refused、connection timed out、网络问题、无法连接、ssh 失败。
---

# Network Troubleshooting · SSH/Port 分层诊断

> Class-level skill：从主人"X 连不上"开始，按 5 层决策树定位断点。
> 覆盖 macOS / Linux / Windows 三个平台，混合 LAN/WAN 场景。

## ⚠️ 主人偏好（2026-08-07）："给我完整命令" = 纯命令块，无 # 注释

**触发信号**：主人说"给我完整命令""直接命令""一条命令搞定"——

- **不要在命令块里夹 `# 注释`**（macOS zsh 默认 `setopt interactivecomments` 未开，会报 `chmod: #: No such file or directory`）
- 用 `setopt interactivecomments` 启用 → 但更稳的是**纯命令、无注释**
- `bash -c '...'` 或 `bash <<'EOF'` 也是绕开方法（bash 默认接受 # 注释）
- **不要说"先做 X，再做 Y"** —— 直接列命令，注释只在块外用 markdown `>` 块说明

## 5 层决策树（按从下到上顺序）

| 层级 | 验证什么 | 命令 | 含义 |
|------|---------|------|------|
| L1 二层 | ARP / MAC 解析 | `arp -n <ip>` 或 `ip neigh` | 设备在 LAN 上是否还活着 |
| L2 路由 | 路由表 | `route -n get <ip>` / `ip route get <ip>` | 走哪个接口、网关、是否在同一子网 |
| L3 ICMP | ping | `ping -c 3 -W 2 <ip>` | 设备是否回 IP 流量（很多设备禁 ping） |
| L4 TCP | 端口连通 | `nc -vz -G 3 <ip> <port>` (macOS) / `nc -vz -w 3 <ip> <port>` (Linux) | 服务是否在 listen + 防火墙是否放过 |
| L5 应用 | 协议握手 | `ssh -vvv user@ip` / `curl -v` / 客户端日志 | 凭据/协议/key/版本兼容 |

**关键洞察**：在主人前 3 步没跑完前，**不要跳到 L5 调 SSH 参数**——那是浪费时间。

## 平台差异表（必查）

| 项 | macOS | Linux | Windows |
|---|-------|-------|---------|
| 看自己 IP | `ipconfig getifaddr en0` | `ip -4 addr` | `ipconfig` |
| 默认网关 | `route -n get default \| grep gateway` | `ip route show default` | `ipconfig` |
| 路由到目标 | `route -n get <ip>` | `ip route get <ip>` | `route print <ip>` |
| ARP | `arp -n <ip>` | `ip neigh show <ip>` | `arp -a <ip>` |
| 清 ARP | `sudo arp -d <ip>` | `sudo ip neigh del <ip> dev <iface>` | `arp -d <ip>` |
| 端口测试 | `nc -vz -G <sec> <ip> <port>` | `nc -vz -w <sec> <ip> <port>` | `Test-NetConnection <ip> -Port <port>` |
| ping | `ping -c 3 -W <ms> <ip>` | `ping -c 3 -W <sec> <ip>` | `ping -n 3 -w <ms> <ip>` |
| 看本地 listen | `netstat -an \| grep LISTEN` | `ss -lntp` | `netstat -ano` |
| 看连接状态 | `lsof -nP -iTCP -sTCP:ESTABLISHED` | `ss -tnp state established` | `netstat -ano \| findstr ESTAB` |

⚠️ **`nc -G` vs `nc -w`**：macOS BSD `nc` 用 `-G` 设超时，Linux GNU `nc` 用 `-w`。混用会得到"看起来没超时"的奇怪行为。

## 关键诊断模式（主人案例 2026-08-07）

### 模式 A：ARP 有但所有 TCP 端口都 timeout

**症状**：
```
arp -n 192.168.10.2 → c8:98:db:40:6e:f5 on en5
nc -vz -G 3 192.168.10.2 22 → Operation timed out
nc -vz -G 3 192.168.10.2 80 → Operation timed out
nc -vz -G 3 192.168.10.2 443 → Operation timed out
# 扫 8 个常见端口全 timeout
```

**含义**（按概率）：
1. **目标设备已关机/网络栈异常**——ARP 是交换机/AP 缓存的旧条目
2. 目标防火墙**全 in 丢弃**所有入站流量（不仅是 SSH）
3. **网络层客户端隔离**（Wi-Fi AP 隔离、VLAN 隔离、桥接网段隔离）
4. 目标设备**实际 IP 已变**——`.2` 是旧地址，ARP 撞了同网段其他设备

**下一步**：
```bash
# 1. 清 ARP 缓存再试
sudo arp -d 192.168.10.2
ping -c 1 -W 1000 192.168.10.2
arp -n 192.168.10.2

# 2. 看 MAC 持续性（5 次扫描,看是否换 MAC = 缓存撞地址）
for i in {1..5}; do arp -n 192.168.10.2; sleep 2; done

# 3. 看 en5 是什么接口（可能是 USB 网卡/OrbStack 桥接/Docker 桥）
ifconfig en5
networksetup -listallhardwareports

# 4. 同网段扫描（找真实活设备）
arp -a
sudo nmap -sn 192.168.10.0/24  # 需 nmap
```

### 模式 B：nc 通 22 但 ssh 报 Permission denied / Connection closed

**含义**：TCP OK，**L4 通但 L5 失败**——是服务或认证问题。

**下一步**：
```bash
# 1. 看 ssh 详细握手
ssh -vvv user@ip 2>&1 | head -50

# 2. 看 server 是哪种拒绝
# - "Permission denied (publickey)" → 公钥未配 / authorized_keys 错
# - "Permission denied (password)" → 密码错 / 禁密码登录
# - "Connection closed by remote" → server 配置了 AllowGroups / 用户不在组
# - "no matching host key type" → server 禁用老算法（如 ssh-dss）

# 3. 试其他方法
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no user@ip
ssh -i ~/.ssh/id_ed25519 user@ip  # 指定密钥
```

### 模式 C：nc 报 Connection refused

**含义**：**服务没在 listen**——firewall 没拦，是服务没启/绑错接口/端口被改。

**在目标机器上**：
```bash
# Linux
sudo ss -lntp | grep ':22 '   # 看 22 端口谁在听
sudo systemctl status ssh
sudo netstat -tlnp | grep 22

# macOS
sudo lsof -nP -iTCP:22 -sTCP:LISTEN
ps aux | grep sshd | grep -v grep
sudo systemsetup -getremotelogin  # 看远程登录是否开

# Windows (管理员 PowerShell)
Get-Service sshd
Get-NetTCPConnection -LocalPort 22 -State Listen
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
```

### 模式 D：目标 Windows 启用 SSH（典型操作）

```powershell
# 安装 OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 启服务 + 设自启
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# 放防火墙
New-NetFirewallRule -Name sshd -DisplayName "OpenSSH SSH Server" `
  -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22

# 验证
Get-Service sshd
netstat -ano | findstr :22
```

### 模式 E：目标 Linux SSH 装好但防火墙拦

```bash
# 看 firewall 状态
sudo firewall-cmd --list-all   # firewalld
sudo ufw status               # ufw
sudo nft list ruleset          # nftables

# 放行
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
# 或
sudo ufw allow 22/tcp

# 验证服务在 listen
sudo ss -lntp | grep ':22 '
```

## 平台特定坑

### macOS 坑

- **`zsh` 默认 `#` 不是注释**——交互模式下 `# foo` 会报 `command not found: #`
  - 修：先 `setopt interactivecomments` 再贴带注释的命令
- **`nc -G` 是 timeout 标志，不是 `-w`**——BSD 和 GNU `nc` 不兼容
- **macOS 没 `timeout` 命令**——用 background + `pkill` 或自己用 `expect`/`bash` 实现
- **系统防火墙**：系统设置 → 网络 → 防火墙 → 高级 → 看是否勾"允许传入连接"（macOS 默认挡所有传入）
- **ssh config Host 别名**：`~/.ssh/config` 里 `Host target` 之后可以 `ssh target` 而不用 IP/端口

### Linux 坑

- **`nc` 在 busybox 嵌入式设备没 `-w`**——需要 `-q 1` 或加 timeout wrapper
- **SELinux 挡了 SSH 端口**：`sestatus` 看 `enforcing` 模式 + `ausearch -m avc -ts recent | grep sshd`
- **systemd 启了 sshd 但 listen 失败**：`journalctl -u ssh -n 50` 看错（典型：端口被占、Key 文件权限错）
- **ufw 默认 inbound drop**：新装系统 ufw 是 inactive 但 iptables 默认有规则；先 `sudo ufw status verbose`

### Windows 坑

- **网络类型**决定防火墙策略——"专用网络"放行，"公用网络"挡所有传入
  - 改：设置 → 网络和 Internet → 状态 → 属性 → 网络配置文件类型 → 专用
- **OpenSSH Server 安装后默认不放防火墙**——必须手动加规则
- **PowerShell 远程 + SSH 不一样**——本 skill 说的是 `sshd` 服务，不是 WinRM
- **`Get-Service sshd` 不存在**——OpenSSH 没装；先 `Get-WindowsCapability` 装

## zsh 注释坑（主人反复踩）

```bash
# 主人常用的多行命令带 # 注释 → macOS zsh 会报 command not found
# 解法 1: 启用交互注释
setopt interactivecomments
# 解法 2: 不带注释,直接复制命令
# 解法 3: 用 here-doc + bash 跑（bash 默认接受 # 注释）
bash <<'EOF'
# 这一行是真正的 bash 注释
ssh -vvv user@ip
EOF
```

## SSH 客户端速查（按主人偏好）

主人问"有什么 SSH 工具"时按这个顺序推荐：

| 场景 | 推荐 | 中文支持 |
|------|------|---------|
| macOS 命令行 | **系统 ssh + iTerm2** | — |
| macOS 颜值党 | **Core Shell**（`brew install --cask core-shell`） | ✅ 原生中文 |
| macOS 全功能 | **Termius** | ❌ 仅英文（验证：9.42.2 解 asar 后只有 en.lproj） |
| 跨平台 | **WindTerm**（`brew install --cask windterm`） | ✅ |
| Windows | **MobaXterm / WindTerm** | ✅ |
| 移动端 | **Termius**（iOS/Android） | ❌ |
| 开发场景 | **VS Code Remote-SSH** | — |
| 弱网 | **Mosh** | — |
| 跳板 | **sshuttle / Tailscale** | — |

**关键发现（2026-08-07）**：
- Termius 9.42.2 不支持中文界面（asar 内 UI 资源全是 hash `.js` 块，没有 i18n 资源）
- 主人若要中文 SSH GUI 客户端，首选 **Core Shell**（macOS 原生） 或 **WindTerm**（跨平台免费）
- **不要**在 Termius 找语言切换——浪费 30 分钟找不到

## 决策树（完整版）

```
主人："SSH 连不上 X" / "ping 不通 X" / "端口连不上 X"
│
├─ Step 1: L1 ARP 验证（30s 决策断点）
│   arp -n X
│   ├─ 有 MAC → 设备在 LAN,跳 Step 2
│   └─ "no entry" → 看是不是同子网
│       ├─ 不同子网 + 路由表也没路由 → 跨网段,跳 Step 5
│       └─ 同子网但 ARP 没有 → 真断网 / 设备未联网
│
├─ Step 2: L2 路由验证（20s）
│   route -n get X (mac) / ip route get X (linux)
│   ├─ interface 字段是 en0/en1/wlan0 → 走 Wi-Fi
│   ├─ interface 是 en5/eth1 → 有线/USB/虚拟网卡
│   └─ "no route to host" → 路由没配
│
├─ Step 3: L3 ICMP 验证
│   ping -c 3 -W 2000 X
│   ├─ 通 → 设备在线,跳 Step 4
│   ├─ 100% loss + ARP 有 MAC → 模式 A (防火墙/设备死)
│   └─ 100% loss + ARP 无 → 真断网
│
├─ Step 4: L4 端口验证
│   nc -vz -G 3 X 22  (mac)
│   nc -vz -w 3 X 22  (linux)
│   ├─ 成功 (succeeded) → L4 OK,跳 Step 5
│   ├─ Connection refused → 服务没 listen (模式 C)
│   └─ Operation timed out → 防火墙挡 (模式 A)
│
├─ Step 5: L5 协议/服务验证
│   ├─ 服务在目标机器本地验证
│   │   Linux: ss -lntp / systemctl status ssh
│   │   Windows: Get-Service sshd / Get-NetTCPConnection
│   │   macOS: sudo lsof -nP -iTCP:22 -sTCP:LISTEN
│   ├─ ssh -vvv user@X 看握手
│   └─ 根据握手报错分支修
│
└─ 全部通过但还是连不上
    ├─ 看代理 / VPN (system_profiler | grep -i proxy)
    ├─ 看 /etc/hosts 有没有 override
    ├─ 试 mosh / telnet / 浏览器同 IP 访问 Web UI
    └─ 换网络（手机热点对比测试）
```

## 反例（不该做的事）

❌ **不要在 L1-L4 没跑完就调 SSH 参数**（改 key / 加 -i / 改端口）——浪费时间
❌ **不要 `ssh -o StrictHostKeyChecking=no` 给主人**——这是安全降级，不是排错手段
❌ **不要 echo SSH password 到日志/MEMORY**——密码是凭据
❌ **不要 `kill -9 sshd` 试着重连**——可能让目标机彻底失联
❌ **不要把主人 `~/.ssh/id_ed25519` 复制到其他机器**——密钥是身份凭证
❌ **不要靠 ping 判定设备在线**——很多设备（云服务器、IoT、防火墙后主机）禁 ping
❌ **不要在 macOS 用 `nc -w` 设超时**——用 `-G`，否则看起来没超时
❌ **不要假设 `arp` 的 MAC 就是目标设备**——ARP 缓存可能在 L2 不通后还残留几分钟
❌ **不要看到 `password:` 提示就以为 SSH 通了**（2026-08-07 主人坑）：
  - `ssh ubuntu@host` 显示 `ubuntu@host's password:` → 输密码登入成功 ≠ 密钥链路通
  - 真实情况：server 端没装主人公钥 → ssh 自动 fallback 到密码认证 → IDE 重连仍报 publickey 拒绝（IDE 通常不开密码认证）
  - **验证方法**：`ssh -v host` 看 `Authentications that can continue` 包含 `password` + `publickey`，且 debug 日志显示 `Offering public key` 后 server 没接 = 客户端有密钥，server 没装

## 实战案例（2026-08-07）

**主人症状**：`ping 192.168.10.2` 100% loss；`ssh 192.168.10.2` timeout。

**诊断过程**：
1. `ipconfig getifaddr en0` → `192.168.65.34`（Wi-Fi 网段）
2. `route -n get 192.168.10.2` → 走 `en5`（有线/虚拟网）
3. `arp -n 192.168.10.2` → `c8:98:db:40:6e:f5`（L1 OK）
4. `nc -vz -G 3 192.168.10.2 {22,80,443,3389,8080,8443}` → **全 timeout**
5. 结论：L1 OK + L4 全 timeout = **模式 A**（目标防火墙/设备死/网段隔离）

**下一步建议（实际该跑）**：
- 在目标机本地看 `ipconfig`（如能物理接触）
- 试手机热点对比
- 试同网段其他设备 `192.168.10.x` 是否通
- nmap 全网段扫描找真实活设备

## 延伸场景：USB 网络共享 / 手机 tethering

主人说"电脑走手机流量""USB tethering 出不来网""手机共享网络电脑没 IP"时，**核心诊断不是 SSH/端口层，而是 USB 协议层（手机端 USB 模式没切到 RNDIS）**。

完整流程 + 5 步诊断命令 + 厂商路径表 + 数据线鉴别见：
**`references/usb-tethering-macos.md`**

主诊断要点（5 秒记忆版）：
1. macOS 端**不能**主动激活 Android USB tethering —— 必须手机端先开
2. `ifconfig -l` 看有没有新 `enX` —— 没新接口 = 手机 USB 模式错（不是 macOS 的问题）
3. `ioreg -p IOUSB` 找 `bDeviceClass` —— `0` = vendor-specific，手机端 USB 模式没切到 RNDIS
4. OPPO/vivo 的 RNDIS 选项经常只在 USB 刚插上时弹窗 —— 错过要**重新插拔数据线**
5. 网卡起来后默认路由还在 Wi-Fi —— 用 `networksetup -ordernetworkservices` 切

## 联动

- `macos-app-gui-troubleshooting` / `macos-app-no-window-debug` —— 主人 SSH 客户端 GUI 问题
- `desktop-control` —— agent 端鼠标键盘（不是网络）
- `huihui-absolute-gating` —— 不要越界动主人目标设备

## 验证清单（每次帮主人排错前必跑）

```bash
# 1. 自己 IP + 默认网关
ipconfig getifaddr en0  # mac
# 或 ip -4 addr show | grep inet  # linux

# 2. 路由到目标
route -n get 192.168.10.2  # mac
# 或 ip route get 192.168.10.2  # linux

# 3. ARP
arp -n 192.168.10.2

# 4. ICMP
ping -c 3 -W 2000 192.168.10.2

# 5. 端口（扫 8 个常见）
for p in 22 80 443 2222 3389 5900 8080 8443; do
  nc -vz -G 2 192.168.10.2 "$p"
done
```

四项有数据后，看 5 层决策树定位。
