# 目标设备本地诊断清单

> 客户端命令只能看到"客户端能看到的世界"。当 ping/nc 全失败时，**目标设备本地状态** 是关键盲区。本文件是按设备类型分组的本地自查命令。

## Windows

### 1. 基础网络
```powershell
ipconfig
Get-NetIPAddress -AddressFamily IPv4 | Format-Table
Get-NetConnectionProfile
# 看 IPv4Address, InterfaceAlias, NetworkCategory（Public/Private）
```

### 2. 防火墙
```powershell
Get-NetFirewallProfile
# 看 Enabled 是不是 True
# Private 应该放行，Public 应该拦
Get-NetFirewallRule -DisplayGroup "File And Printer Sharing" | Format-Table
# 找 "Echo Request (ICMPv4-In)" 看是否启用
```

### 3. SSH 服务
```powershell
Get-Service sshd
# Status: Running / Stopped
Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue
# 看是否有 listener
```

### 4. 一键装启 SSH（管理员 PowerShell）
```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd -DisplayName "OpenSSH SSH Server" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

### 5. 开 ICMP（让 ping 通）
```powershell
New-NetFirewallRule -DisplayName "ICMPv4 Allow Ping" -Protocol ICMPv4 -IcmpType 8 -Direction Inbound -Action Allow -Profile Any
```

### 6. 网络类别（重要！Public 会拦一切）
```powershell
Get-NetConnectionProfile
# 如果 NetworkCategory 是 Public，改成 Private：
Set-NetConnectionProfile -InterfaceAlias "以太网" -NetworkCategory Private
```

### 7. 重启网络栈
```powershell
netsh winsock reset
netsh int ip reset
# 重启生效
```

## Linux

### 1. 基础网络
```bash
ip -4 addr
ip route
ip link show
# 看 NIC 是否 UP
```

### 2. SSH 服务
```bash
sudo systemctl status ssh
sudo systemctl status sshd
sudo ss -lntp | grep ':22'
# 看 LISTEN
```

### 3. 防火墙
```bash
# nftables（新）
sudo nft list ruleset

# iptables（旧）
sudo iptables -L -n -v
sudo iptables -L INPUT -n -v

# ufw
sudo ufw status verbose

# firewalld
sudo firewall-cmd --list-all
```

### 4. 一键放行 SSH
```bash
# ufw
sudo ufw allow 22/tcp

# firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload

# iptables（临时）
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
```

### 5. 关掉 ICMP 拦截
```bash
# sysctl
sudo sysctl -w net.ipv4.icmp_echo_ignore_all=0

# iptables（如果之前被拦了）
sudo iptables -D INPUT -p icmp --icmp-type echo-request -j DROP
```

## 机器人 / 嵌入式（NVIDIA Jetson / Raspberry Pi / Unitree / 灵巧手控制器等）

### 1. 用串口 console（不依赖网络）
```bash
# Mac 找串口
ls /dev/tty.usb*
screen /dev/tty.usbserial-1410 115200
# 退出: Ctrl-A K
```

### 2. 找设备的真实 IP
- 看路由器后台的 DHCP 客户端列表（最稳）
- 设备面板上的 LED（Wi-Fi 指示）
- 串口 console 里 `ip addr` / `ifconfig`

### 3. 重启网络栈
```bash
sudo systemctl restart NetworkManager
# 或
sudo nmcli networking off && sudo nmcli networking on
```

### 4. 看设备是否在广播
```bash
# Mac 端用 arp -a 看同网段
arp -a
# 看哪些 IP 有 MAC 对应
```

## NAS（群晖 / 威联通）

- DSM/QTS 后台看网络状态
- 群晖：`控制面板 > 网络 > 网络接口`
- 检查 SSH 是否启用：群晖 `控制面板 > 终端机和 SNMP > 终端机`
- 群晖防火墙： `控制面板 > 安全性 > 防火墙`

## 通用：让目标能被你看到

| 设备 | 最佳实践 |
|---|---|
| Windows | 装 OpenSSH + 改网络类别为 Private + 防火墙放行 |
| Linux | `systemctl enable --now ssh` + `ufw allow 22/tcp` |
| NAS | 控制面板开 SSH + 关防火墙/加白名单 |
| 机器人 | 串口 console 验证 + DHCP 静态 IP + 路由器后台白名单 |
| 树莓派 | SD 卡写好 `ssh` 文件 + 配 wpa_supplicant.conf 一次性接入 Wi-Fi |

---

_2026-08-08 session 沉淀_
_客户端诊断到极限后，**目标设备本地** 是下一个战场_
