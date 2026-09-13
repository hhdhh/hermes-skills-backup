# macOS 网络诊断特坑

> 2026-08-08 真实 session 沉淀：主人 `ping`/`ssh`/`nc` 全 timeout 到 `192.168.10.2`，诊断过程中踩到的 macOS 独有坑。

## 坑 1 · zsh 默认不把 `#` 当注释

**表现**：
```bash
kk@KKdeMacBook-Air-1500 ~ % # 1. 查看 Mac 当前 IP
zsh: command not found: #
```

**根因**：默认 zsh 启动不是交互模式（`~/.zshrc` 里 `setopt interactivecomments` 没开），`#` 被当成命令字面解析。

**修法**（主人贴命令前先告诉主人）：
```bash
setopt interactivecomments
```

**预防**（下次写命令块给主人时）：**只放纯命令，不放说明行**。说明放在段落文字里，不在命令块里。

## 坑 2 · macOS `nc` 不支持 GNU `-w`，要用 `-G`

**表现**：
```bash
nc -vz -w 3 192.168.10.2 22
# 在 macOS 上 -w 默默被忽略，一直等到默认超时
```

**根因**：
- **GNU `nc`（Linux）**：`nc -w SECONDS ...` 指定超时
- **macOS `nc`**（基于 original 4.4 BSD）：`-w` 不识别；用 `-G SECONDS`

**正确**：
```bash
nc -vz -G 3 192.168.10.2 22
```

**判断主机**：
```bash
nc -h 2>&1 | head -5
# 看 OPTIONS 里有没有 -w
```

## 坑 3 · 不同 interface 走不同网段，关键信号

**表现**：
```
Mac en0 (Wi-Fi)  → 192.168.65.34
Mac en5 (USB/虚拟) → 不在 192.168.65.x
目标 IP 192.168.10.2
route -n get 192.168.10.2 → 走 en5
```

**根因**：
- en0 = 默认 Wi-Fi
- en5 可能是：USB 以太网适配器 / Docker 桥接 / OrbStack 桥接 / Parallels / 雷电网桥
- 192.168.10.x 是经典内网段（路由器 / NAS / 摄像头 / 机器人控制板常用）

**判断**：
```bash
ifconfig en5
# 看 description / manufacturer
networksetup -listallhardwareports
# 找到 en5 真实硬件
```

**行动**：
- 如果 en5 是 USB 网卡：检查 USB 物理连接
- 如果是 Docker/OrbStack：检查虚拟网络
- 如果是 Parallels：检查共享网络

## 坑 4 · ARP 缓存 vs 真实在线

**表现**：
```bash
arp -n 192.168.10.2
? (192.168.10.2) at c8:98:db:40:6e:f5 on en5 ifscope [ethernet]
# MAC 还在，但所有 TCP 都 timeout
```

**真相**：
- ARP 是 Layer 2 协议，目标愿意响应 ARP 请求 ≠ 愿意响应 TCP
- 二层转发设备（如交换机）会保留 MAC 表一段时间
- 设备可能已下线，但 MAC 表没清

**修法**：
```bash
sudo arp -d 192.168.10.2
ping -c 1 -W 1000 192.168.10.2
arp -n 192.168.10.2
```

清掉后重发 ARP 请求；如果目标真在线，ARP 会立刻 re-populate；如果目标是交换机/MAC 表残留，会持续 `(incomplete)`。

## 坑 5 · `ifconfig` 已被 macOS deprecate，但还在用

macOS 13+ 推荐 `ipconfig` / `networksetup`，但旧 `ifconfig` 仍可用且很多命令依赖其输出格式（interface 名字等）。**双轨运行**：
- 看 IP：`ipconfig getifaddr en0`
- 看 MAC / flags：`ifconfig en0`
- 看硬件对应关系：`networksetup -listallhardwareports`

## 坑 6 · macOS 防火墙默认拦 ICMP

```bash
# macOS 本地若需对外开 ICMP
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --set globalstate off
# 不建议全关；用 pf 规则开 ICMP
```

但本次诊断是**目标设备**拦截 ICMP，不是本机，**先看目标侧**。

## 坑 7 · `ping` 默认一直跑

**表现**：
```bash
ping 192.168.10.2
# 不指定 -c 就一直 ping
```

**修法**：
```bash
ping -c 3 -W 1000 192.168.10.2
# -c 3 = 3 个包
# -W 1000 = 1 秒超时（毫秒）
```

## 速查表

| macOS 习惯 | 正确写法 |
|---|---|
| `nc -w 2` | `nc -G 2` |
| `ping 一直跑` | `ping -c 3 -W 1000` |
| `# 说明行` 报错 | `setopt interactivecomments` 或不放注释行 |
| `ifconfig` deprecated | 双轨：`ipconfig` + `ifconfig` |
| 删 ARP 条目 | `sudo arp -d <IP>` |
| 找 interface 硬件 | `networksetup -listallhardwareports` |

---

_session 沉淀 · 2026-08-08_
