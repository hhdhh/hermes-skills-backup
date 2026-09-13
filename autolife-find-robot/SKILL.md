---
name: autolife-find-robot
version: 1.0.0
description: 在现场内网快速定位 AutoLife 机器人：DNS PTR 反查法（首选，无需凭证）+ mDNS 域名 + robssh SSH 扫描兜底。当主人说"找机器人"、"机器人 IP 是多少"、"扫一下网"、"哪台机器在线"、"294 在哪"时使用。含同事邹誉鑫的 mDNS 配置教程与 find-autolife 原始脚本存档。
---

# AutoLife 找机器人（find-robot）

> 来源：2026-09-13 主人转发同事邹誉鑫的 find-autolife.bat/.sh + mDNS 配置教程，实测验证后固化成技能。
> 姊妹技能：`autolife-doctor-operations`（诊断维修）、`autolife-robot-dds-camp-split`（DDS 阵营分裂）、`autolife-robot-prompt-ops`（prompt/知识文件）、`autolife-remote-repair`（ssh 直连检修闭环）。

## 核心认知：机器人按机号识别，IP 动态解析

- 机器人 hostname 格式：`autolife-robot-<机号>`（如 `autolife-robot-294`），机号 = hostname 数字后缀。
- 机器人 IP 是 DHCP 的，**写死必失效**。定位分两层：
  1. **快找（秒级）**：DNS PTR 反查 —— ping 填邻居表 → `dig @网关 -x IP` → hostname 含 `autolife` 即机器人。**不需要 SSH 凭证**。
  2. **深查（兜底）**：`robssh.py scan` —— SSH 连上读 hostname。慢但能确认 SSH 可达性 + 抓到 PTR 缺失的机器。
- 两种方法结果都会写进 `~/.hermes/workspace/robots.json` 的 `_resolved`（机号→IP），后续 `robssh.py <机号> <命令>` 直接用。

## 三条路径（按场景选）

### 路径 A：DNS PTR 反查（默认首选）

```bash
# 一条命令：扫本机所有网段 → PTR 反查 → 打印 autolife-* → 回写 robots.json
python3 ~/.hermes/skills/autolife-find-robot/scripts/find-autolife.py
```

实测（2026-09-13 现场，192.168.64-65.0/23，507 个邻居 IP）一次抓到 10 台：402、400、308、303、294 不在线本次未抓到、255、254、277、224、0×2。
（当时 robssh SSH 扫描只发现 2 台——DNS 法多抓 8 台，含 SSH 不通但在线的。）

- DNS 服务器默认取默认网关（现场路由器惯例）。手动指定：`dig @192.168.64.1 +short -x <IP>`。
- 只看不写：`--no-update`。
- 局限：依赖路由器 DNS 有 PTR 记录。PTR 缺失的机器抓不到 → 路径 C 兜底。

### 路径 B：mDNS 域名（机器人配过 mDNS 后可用）

机器人配置 avahi 后可通过 `autolife-robot-<机号>.local` 直接访问，彻底不查 IP：

```bash
python3 ~/.hermes/skills/autolife-find-robot/scripts/find-autolife.py --mdns autolife-robot-294
# 或直接
ping autolife-robot-294.local
```

完整配置教程（在机器人上配 avahi-daemon，lan0/wlo1 双接口，含回滚）：
→ [references/mdns-setup-guide.md](references/mdns-setup-guide.md)（邹誉鑫原版，avahi 配置/UFW 规则/nxserver 广播停用/验证/回滚，脚本式与手工式两套流程）

> 本工作站未装 avahi-tools，`--mdns` 走 avahi-resolve 回退链（dig→nslookup→host→avahi-resolve）。装了更好：`sudo apt-get install -y avahi-tools`。

### 路径 C：robssh SSH 扫描（兜底 + 验证 SSH 可达）

```bash
python3 ~/.hermes/workspace/robssh.py scan --force   # 扫 22 端口 → SSH 读 hostname → 写 robots.json
python3 ~/.hermes/workspace/robssh.py list           # 机队一览
python3 ~/.hermes/workspace/robssh.py ip <机号>       # 查单台当前 IP
python3 ~/.hermes/workspace/robssh.py <机号> 10 'hostname'  # 按机号执行命令
```

### 路径 D：NetBird mesh（不在现场内网时的通道）

机器人出厂/部署时已注册进公司自建 NetBird（2026-09-13 开通确认）。现场内网扫不到时：

```bash
netbird status -d | grep -A2 "autolife-robot-<机号>\."   # 查机器人的 NetBird IP (100.98.x.x)
ping autolife-robot-402.netbird.selfhosted              # 唤醒 lazy 连接 + 判在线
python3 ~/.hermes/workspace/robssh.py <NetBird-IP> 15 'hostname'   # 直接按 IP 连
```

> lazy connection 模式：peer 显示 Idle ≠ 离线，ping 触发连接。真离线（断电/断网）ping 不通。
> 165 台设备在网（机器人 + 同事工作站 + 云主机）。本工作站：kk-gdh-x（100.98.198.205）。

## 决策树

```
要找机器人 →
  在内网且要快 → A: find-autolife.py（DNS PTR，无需凭证）
  机器人配过 mDNS → B: --mdns / ping xxx.local
  A 没抓到 / 要确认 SSH 通不通 → C: robssh.py scan
  都没抓到 → 机器真离线，或不在本网段
```

```
robots.json 结构（两法共用）:
  { "<机号>": {"note": "..."},
    "_resolved": {"<机号>": "<IP>"} }
```

## 已知坑

- **两台 "autolife-robot-0"**（2026-09-13 发现：64.128 和 65.240）——0 号机不唯一，PTR 名字相同。按 IP 操作前先 `robssh.py` 连上确认身份。
- PTR 反查慢的话先查 DNS 指向：`dig @<网关> -x <已知在线IP>`，返回空 = 路由器没记 PTR，直接换路径 C。
- 多网卡机器（有线+无线）会各自广播，同一台机器人可能在邻居表里出现两个 IP；以 SSH 实连为准。
- DNS PTR 法能发现"在线但 SSH 不通"的机器，**这恰好是要修的机器**——列入诊断清单，别当噪音。

## 原始存档（同事邹誉鑫）

- [references/find-autolife.sh](references/find-autolife.sh) — Linux 原版（交互式：输网卡/网段/DNS）
- [references/find-autolife.bat](references/find-autolife.bat) — Windows 原版（arp -a + nslookup 过滤）
- [references/mdns-setup-guide.md](references/mdns-setup-guide.md) — mDNS 配置教程原版
- 原始飞书消息：合并转发自邹誉鑫（2026-09-07/09-11），存档副本在 `~/.hermes/workspace/find-autolife/`
