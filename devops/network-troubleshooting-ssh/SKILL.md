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

### 模式 F：Wi-Fi 下 ARP 应答但 IP 层全死（AP 代答 / 主机睡眠）

**症状**：`ip neigh` 对目标 IP 持续有 MAC（甚至 REACHABLE），但 ping / 所有 TCP 端口 / mDNS / NBNS 全部静默丢包（连接超时，非 refused）。

**机制**：Wi-Fi AP 会替关联中但休眠的客户端代答 ARP（Proxy ARP），网卡 offload 也会在系统睡眠（Windows Modern Standby）时代答二层——「ARP 在线」只证明 NIC/关联还在，不证明 IP 栈活着。有线网络里 ARP 有 MAC 同样可能是交换机 CAM 缓存残留。

**处置顺序**：
1. 发 WoL 魔术包（python socket 广播 `ff*6 + MAC*16` 到子网广播:9）——多数设备 BIOS 未开网络唤醒，叫不醒是常态，不是排除项
2. 全网段 ping sweep 后 `ip neigh` 按目标 MAC 反查——设备若换了 IP，同一 MAC 会挂在新 IP 上（比 DNS/PTR 可靠，无需凭证）
3. 挂后台轮询守望（每 15s 探一次 22 端口，10 分钟窗口），一上线即动手，不要反复手动重试
4. 以上全空 → 结论只能是「需物理接触唤醒/检查」，停止堆探测手段

### 模式 G：Android 设备 ping 通但应用端口全聋（ROM 冻结后台 app）

**症状**：手机 IP ping 正常、ARP 正常，但目标 app 的 UDP/TCP 端口（如 KDE Connect 的 1716）零回应。

**机制**：ColorOS/MIUI/HyperOS 等国产 ROM 会冻结后台 app 的 CPU 与网络（不是杀进程）——ICMP 由内核协议栈代答所以 ping 通，app 层完全无响应。「设备在线」≠「app 活着」。

**处置**：
1. `sudo tcpdump -i any -nn "host <手机IP> and port <端口>"` 抓 30s，期间向手机单播该协议的身份/发现包——只见本机出站、零回包 = app 被冻结实锤
2. 结论即止：这是手机端 app 生命周期问题，堆网络探测无意义；需用户在手机上操作（多任务卡片锁定、电池白名单、允许自启动）
3. 评估「跨设备同步」类方案前先判对端 ROM 能否让 app 后台常驻——不能就换方案（两端都是常驻设备的 LocalSend/KDE Connect，或浏览器一次性 HTTP 拉取），别硬配
4. 附带：Android 10+ 禁止后台 app 读剪贴板——「手机→电脑」方向剪贴板同步在 app 退后台时必然失效，验证预期要按这个来


## 平台特定坑

### macOS 坑

- **`zsh` 默认 `#` 不是注释**——交互模式下 `# foo` 会报 `command not found: #`
  - 修：先 `setopt interactivecomments` 再贴带注释的命令
- **`nc -G` 是 timeout 标志，不是 `-w`**——BSD 和 GNU `nc` 不兼容
- **macOS 没 `timeout` 命令**——用 background + `pkill` 或自己用 `expect`/`bash` 实现
- **系统防火墙**：系统设置 → 网络 → 防火墙 → 高级 → 看是否勾"允许传入连接"（macOS 默认挡所有传入）
- **ssh config Host 别名**：`~/.ssh/config` 里 `Host target` 之后可以 `ssh target` 而不用 IP/端口

### Linux 坑

- **多网卡主机：服务通告的 IP 必须在"能回包"的网段**——机器有多块网卡时，默认出口往往只走其中一块（`ip route | grep default` 里 metric 最小的那块，常是 WiFi）。若把某服务（relay/admin/API）的配置 IP 改成另一块**非默认出口**网卡的地址，客户端即使同网段能到，远端回包也可能走错网卡出不去 → 表现为"改了 IP 但客户端还是找不到"。改任何"对外通告 IP"前先 `ip -4 addr` + `ip route | grep default` 确认哪个网卡是真实出口，别只对着一块网卡的地址填。
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
│   ├─ 100% loss + ARP 有 MAC → 模式 A (防火墙/设备死/主机睡眠)
│   │   ⚠️ Wi-Fi 下 ARP 应答可能来自 AP 代答(Proxy ARP/休眠客户端),
│   │      ARP REACHABLE ≠ 主机醒着——见模式 F
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

❌ **不要因一次 background SSH 启动失败/超时就判网络或 SSH 服务不通**：
- background 会话创建失败（PTY 分配、auth 提示等待、句柄丢失）≠ 22 端口不通、≠ 主机离线
- 判定顺序：先用 TCP 探活 `timeout 4 bash -c 'cat </dev/tcp/<ip>/22 | head -c 80'` 看 banner 字符（如 `SSH-2.0-OpenSSH_x.y`）→ 端口在线；再下“SSH 不通”的结论。
- 客户端 PTY/句柄工具缺失不阻塞端口可达；TCP 层结果才是网络层真相。

❌ **不要在 L1-L4 没跑完就调 SSH 参数**（改 key / 加 -i / 改端口）——浪费时间
❌ **不要 `ssh -o StrictHostKeyChecking=no` 给主人**——这是安全降级，不是排错手段
❌ **不要 echo SSH password 到日志/MEMORY**——密码是凭据
❌ **不要 `kill -9 sshd` 试着重连**——可能让目标机彻底失联
❌ **不要把主人 `~/.ssh/id_ed25519` 复制到其他机器**——密钥是身份凭证
❌ **不要靠 ping 判定设备在线**——很多设备（云服务器、IoT、防火墙后主机）禁 ping
❌ **不要靠 ARP 判定主机在线**——Wi-Fi AP 替休眠客户端代答 ARP；TCP refused/静默丢包才是主机死活的可靠证据（见模式 F）
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

## 延伸场景：NetBird / Tailscale 等 mesh VPN 连远端机

mesh VPN 通过主机名直连对方机器时，**错误信号常常伪装成"主机名解析失败"或"连接超时"**，而不是真正的"对方没开"。诊断顺序：

1. **本机 netbird 必须 Connected**：`netbird status` 看 Management + Signal 都 Connected。**⚠️ 会话会过期**：NetBird 自建 session 约 24h 过期，过期后 `netbird status` 变 `Daemon status: NeedsLogin`——**此时到 mesh 里任意目标机都 ping 不通 / TCP 失败**，会把你自己的掉线误判成目标机故障。**先看自己**：任何"连不上 mesh 节点"先 `netbird status` 确认本机还在线，NeedsLogin 就 `netbird up`（自建无 SSO 用 `--management-url`+ 新 setup key）重登再测。
2. **本机 netbird SSH server 状态看参考**：`netbird status -d` 输出里有 `SSH Server: Disabled/Enabled` —— 这是**本机的**设置，**对方机器默认也是 Disabled**，除非对方显式 `sudo netbird ssh-server enable`。
3. **`netbird ssh` 报错的真实含义**（按概率）：
   - `dial tcp: lookup <hostname>` / `server misbehaving` → 对方机器没在 netbird 上登录，或 mDNS 没注册 — **不**是网络问题
   - `SSH server detection failed` / `Failed to connect to user@host:22` → **对方**机器 netbird SSH server 是 Disabled；解决：在对方机器跑 `sudo netbird ssh-server enable && sudo systemctl restart netbird`
   - `Permission denied (publickey)` → 走到对方 SSH 协议层，密钥未配（fallback 到 P3 SSH 认证路径）
4. **`peers` 子命令不存在**：netbird 0.77.x CLI 没有 `netbird peers list`；要列所有 peer（包括对方），看 `netbird status -d` 输出的 "Peers detail" 段（但**默认只显示直连的 peer**，远端机器即便在管理面板在线也不一定出现在这里，受 lazy connection 模式影响）。
5. **确认对方是否在你的 netbird 同一个 ACL 组**：管理面板 https://netbird.<your-domain>:443 看 Groups / ACLs —— 如果没共享 ACL，wireguard 不会建 tunnel，再怎么 ssh 都连不上。
6. **不要在没确认对方机器能 ssh 时把凭证/API key 写过去**：除非 `ssh user@host` 真返回 `whoami`，否则视为连接失败 —— 绝不盲推密码或 token。

**回退路径**：如果 netbird 走不通但对方在物理 LAN（共享路由器），直接试 `ssh user@<lan-ip>` （如 192.168.x.x）—— 不需要 mesh VPN 也能走。

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
