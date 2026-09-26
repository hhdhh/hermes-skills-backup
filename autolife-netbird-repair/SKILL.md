---
name: autolife-netbird-repair
version: 1.0.0
description: AutoLife 机器人 NetBird mesh 状态维护——批量诊断每台机器人的 mesh 注册状态、安装/重装/重新注册 NetBird、排查 FQDN 命名冲突。当主人说"内网机器人 netbird 是否都正常"、"netbird 重装"、"mesh 不通"、"autolife-robot-X 注册不上"时使用。与 autolife-remote-repair(SSH 检修) 和 autolife-find-robot(定位) 互补。
---

# AutoLife NetBird 维护

> 管理面：公司自建 NetBird (`https://netbird.autolife-robotics.com`)，casdoor SSO / 飞书登录。
> 标准流程（飞书 `UJ97dr4j8oh603xnyMEcnfc4nyd` 文档）：
> 1. `curl -fsSL https://pkgs.netbird.io/install.sh | sh`
> 2. `sudo netbird up --management-url https://netbird.autolife-robotics.com --setup-key 1A7A41D5-653E-4B64-AAA6-764C24844FD8`
> 3. `sudo netbird status` 看到 "Already connected" + NetBird IP `100.98.x.x`
>
> 姊妹技能：`autolife-find-robot`（定位）、`autolife-remote-repair`（SSH 检修闭环）、`autolife-doctor-operations`（系统诊断）。

## 自带脚本

- [`scripts/nb-peers-by-robot.py`](scripts/nb-peers-by-robot.py) — `netbird status --json` 按机号聚合 peer,自动标错位/卡死/同名多条。常用 `--suspicious` 一次看全所有需要修的机器。

## 何时触发

- 主人说"检查内网机器人 netbird 是否都正常"
- "netbird 重装"、"autolife-robot-X 注册不上"、"mesh 不通"、"FQDN 错了"
- 任何时候管理面 dashboard 显示 peer 数量对不上机器人数量

## 标准工作流（4 步走）

### Step 1：盘点（mesh × 内网 × SSH 三层比对）

```bash
# 1a. 拉 mesh peer 清单
netbird status --json | jq -r '.peers.details[] | select(.fqdn | startswith("autolife-robot-")) | "\(.fqdn)\t\(.netbirdIp)\t\(.status)"'

# 1b. 扫内网在线机器人
python3 ~/.hermes/skills/autolife-find-robot/scripts/find-autolife.py --no-update

# 1c. 探测 SSH 可达性（哪些机器人我们真的能连进去做手术）
# 思路：对每个解析到的内网 IP 用 nc -zv -w 3 22 端口探测，列可达清单
```

把三层结果合并成一张表：

| 机号 | 内网 IP | 内网可达 | mesh FQDN | mesh IP | mesh 状态 |
|---|---|---|---|---|---|

按机号聚合，识别四类：

- ✅ **OK**：内网可达 + mesh FQDN = `autolife-robot-<机号>`（无后缀）
- 🔴 **未注册**：内网可达 + mesh 无该机号记录
- ⚠️ **错位**：mesh FQDN ≠ 真实 hostname（如 `autolife-robot-227-30-180` 实际是 227）
- ⚠️ **卡死**：mesh status = Connecting 且 latency > 5s / 长时间无更新
- 🟢 **离线**：内网 ping 不通 + mesh ping 不通（**远程干不了，跳过**）

### Step 2：身份校验（SSH 上去 `hostname` 验明正身）

错位是常态（实测发现 mesh 上的 `autolife-robot-227-30-180` 实际 hostname 是 `autolife-robot-227`）。即使 ping 通也要先 `hostname` 确认。

```bash
ssh ubuntu@<内网IP> 'hostname'
```

### Step 3：修复（按身份问题分两类）

#### 3a. 错位修复（已装 netbird，FQDN 错了）

**核心机制**：NetBird 用 wireguard public key 识别 peer。`netbird down && up` 不改 key，所以 management 端仍认旧 FQDN。要让 FQDN 干净必须**删 state.json + 重启服务重生 wireguard key**——但同名 peer 会触发自动加 IP 后缀去重。

```bash
ssh ubuntu@<IP> 'bash -s' <<'EOF'
netbird down 2>&1 | head -2
sleep 2
echo ubuntu | sudo -S bash -c '
  rm -f /var/lib/netbird/default.json /var/lib/netbird/state.json
  rm -f /var/lib/netbird/*.json.bak /var/lib/netbird/*.lock
  systemctl restart netbird
'
sleep 3
echo ubuntu | sudo -S netbird up \
  --hostname autolife-robot-<机号> \
  --management-url https://netbird.autolife-robotics.com \
  --setup-key 1A7A41D5-653E-4B64-AAA6-764C24844FD8
sleep 5
netbird status | head -12
EOF
```

#### 3b. 未注册修复（没装 netbird，或装了但 daemon 一直没起来）

**`install.sh` 走 apt，需要 sudo**——直接 pipe 进 `sh` 在非交互 shell 里 sudo 会失败。**两个解法二选一**：

```bash
# 解法 A：用 .deb 直接装 cli 包（避开 install.sh 内部的 sudo askpass）
ssh ubuntu@<IP> 'bash -s' <<'EOF'
cd /tmp
curl -fsSL -o netbird.deb https://github.com/netbirdio/netbird/releases/download/v0.78.2/netbird_0.78.2_linux_amd64.deb
echo ubuntu | sudo -S apt-get install -y ./netbird.deb 2>&1 | tail -3
which netbird && netbird version
# 接着走 3a 的 down/clean/up
EOF

# 解法 B：把 sudo 喂给 install.sh 内部
ssh ubuntu@<IP> 'echo ubuntu | sudo -S bash -c "curl -fsSL https://pkgs.netbird.io/install.sh 2>/dev/null | sh 2>&1 | tail -10"'
```

# 解法 C：机器人内网出不了 GitHub 时（install.sh 空输出/超时，alist 无 guest 凭证）——本机中转
# 1) 本机下载（本机网络可达 GitHub）：curl -fsSL -o /tmp/netbird.deb https://github.com/netbirdio/netbird/releases/download/v0.78.2/netbird_0.78.2_linux_amd64.deb
# 2) scp 传过去 + md5 校验：sshpass -p<密码> scp /tmp/netbird.deb ubuntu@<IP>:/tmp/
# 3) 远端装：ssh ubuntu@<IP> 'echo <密码> | sudo -S apt-get install -y /tmp/netbird.deb'
# 2026-09-19 修 328 机验证可行：install.sh 在机器人上 curl GitHub 60s 超时且无报错回显，装完 which netbird 为空。

注意：github release 有 3 个 .deb，**一定要选 `netbird_xxx_amd64.deb`**（cli），**不要选 `netbird-ui-gtk3_xxx_amd64.deb`**（依赖 netbird cli 包，装不上），也不要选 `netbird-ui_xxx_amd64.deb`。

注意：alist（`https://alist.gz.autolife.ai:8444`）是 AList V3，guest 用户被禁用，`/api/fs/list` 返回 401，没有凭证时下不了包；网页直接 curl 拿到的是 SPA HTML（几 KB 假 deb），务必 `file xxx.deb` 验真再装。

### Step 4：验证（本机 mesh 视角）

```bash
# 触发 lazy handshake
ping -c 2 -W 3 autolife-robot-<机号>.netbird.selfhosted

# 30s 后看 mesh 上是否出现新 peer
netbird status --json | jq -r '.peers.details[] | select(.fqdn | startswith("autolife-robot-<机号>")) | "\(.fqdn)\t\(.netbirdIp)\t\(.status)"'
```

## 已知坑（真机踩过，写死规则）

- **NetBird 同名 peer 自动加 IP 后缀去重**：management dashboard 上已存在 `autolife-robot-0` 时，新机器用 `--hostname autolife-robot-0` 注册会被改成 `autolife-robot-0-198-23`（后缀是内网 IP 末段）。**要让 FQDN 干净，必须在 management dashboard 手动删旧 peer**——目前只有 @陈龙 有权限。临时绕开：接受 `-<IP末段>` 后缀，功能完全正常只是名字不规范。
- **down+up 不改 public key**：必须删 `default.json` + `state.json` + `systemctl restart netbird` 三连才会重生 wireguard key。少一步 registration 都还是用旧 key。
- **`robssh.py` 不适合做 NetBird 修复**：① `--sudo` 路径需要交互 sudo password；② 内部用 SSH client exec_command 不便于多行 heredoc；③ mesh 名 NXDOMAIN 时它直接报错退出，不回退到内网 IP。**用 `sshpass` + `ssh` + heredoc 直连**更快更可控。
- **320 是 S3 密码例外**：`ssh ubuntu@192.168.65.48` 用 `ubuntu` 密码被拒，**必须用 `robot_initpd`**。robssh.py 不支持这台——直接 `sshpass -probot_initpd ssh ...`。
- **"0 号机"有两台**：两台机器 hostname 都是 `autolife-robot-0`。按 IP 操作前 `ssh ubuntu@<IP> 'hostname && ip addr'` 确认是哪台。skill `autolife-remote-repair` 已记录这条。
- **管理端总 peer 数 ≠ 机器人总数**：mesh 上看到 180+ peer，其中只有 ~80 个是机器人（`autolife-robot-*`），其余是同事工作站 / iPhone / edge 设备 / 调试机。**判断标准是 FQDN 前缀**，不要按总 peer 数判断。
- **lazy connection 模式**：peer 显示 Idle ≠ 离线。但**真正的 "Idle 且 lastWireguardHandshake = 0001-01-01"** = 该 peer 长期未通讯（可能真离线或被防火墙挡），ping 不通就是真离线。

## 远程不可达的处置

如果一批机器**内网 ping 不通 + mesh ping 也不通**（典型场景：NAT 后 / 公司外 / 防火墙挡）：

1. 不要硬撞 SSH（连接超时 = 浪费 10s×N）
2. 输出一份"现场操作卡"——把 3a/3b 的命令按机号填好，让现场同事或主人 1 分钟一台执行
3. 每次现场执行完回来 ping 验明
4. 长期方案：在那些机器上配 avahi/mDNS 或确保 mesh 路由能穿透（这是网络组的事）

## 状态汇报模板

完成一批后给主人这样的表（**用 markdown，不用截图**）：

```
| 机号 | 修前 FQDN | 修后 FQDN | 状态 |
|---|---|---|---|
| 294 | autolife-robot-303 | autolife-robot-294 | ✅ |
| 336 | (未注册) | autolife-robot-336 | ✅ |
| 227 | autolife-robot-227-30-180 | autolife-robot-227-17-67 | ⚠️ 后缀冲突 |
```

最后一行加汇总：
- ✅ 完美修复（FQDN 干净）
- ⚠️ 功能正常但 FQDN 加后缀（management 端有同名旧 peer，需 @陈龙 删）
- ❌ 远程不可达（列机号清单）
- 🟢 本就正常（保持）
