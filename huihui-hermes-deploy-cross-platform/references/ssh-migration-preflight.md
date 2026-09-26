# SSH 迁移前置连通性判定

跨机器同步开始前，先把“目标主机在线”和“SSH 可登录”拆开验证，避免在打包或认证阶段浪费时间。

## 最小探测顺序

```bash
route -n get <TARGET_IP>
ping -c 2 -W 1000 <TARGET_IP>
nc -vz -G 3 <TARGET_IP> 22
ssh -o ConnectTimeout=10 <USER>@<TARGET_IP>
```

macOS 的 `nc` 连接超时参数用 `-G`。

## 输出判定

| 结果 | 含义 | 下一步 |
|---|---|---|
| 路由走默认 Wi-Fi 网关，目标不在当前子网，Ping/22 均超时 | IP 可能填错、目标在虚拟/NAT 网段，或两机网络不互通 | 先核对目标当前局域网 IP，不进入打包/认证 |
| Ping 成功，22 `Connection refused` | 主机在线，但 SSH 服务未启动或未监听；不是密码错误 | 在目标机启用 SSH，再重试 |
| 22 超时 | 防火墙丢包、VLAN/访客网络隔离或服务路径不可达 | 查目标防火墙与网络隔离 |
| 22 连通但认证失败 | 才进入用户名、密码、密钥诊断 | 用 `ssh -v` 检查认证 |
| 其他应用端口可达、22 refused | 进一步证明设备在线且只是 SSH 未启用 | 不要把问题误判为整机离线 |

## 目标端启用 SSH

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
sudo ufw allow OpenSSH
sudo systemctl status ssh --no-pager
ip -4 addr
id "$USER"
```

验收应看到 `active (running)`，并确认 SSH 监听 `0.0.0.0:22` 或目标 LAN 地址。

Ubuntu 常同时显示 Wi‑Fi/以太网地址和 `virbr0` 地址。`virbr0`（常见 `192.168.122.1/24`）是 libvirt NAT 网桥，不等于目标机供局域网访问的地址；跨物理机器连接应选择与源机同网段、状态为 `UP` 的 Wi‑Fi/以太网 IPv4。

### macOS

系统设置 → 通用 → 共享 → 远程登录，允许目标用户登录。

也可在目标机本地执行：

```bash
sudo systemsetup -setremotelogin on
```

### Windows（管理员 PowerShell）

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd -DisplayName "OpenSSH SSH Server" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

## 安全与执行纪律

- 密码仅通过环境变量或交互输入交给 SSH 工具，不写入脚本、日志、迁移包或命令回显。
- SSH 尚不可用时，不要先生成可能迅速过期的大型迁移包；先恢复传输通道，再做远端备份和即时打包。
- 不复制 `auth.json`、API key、会话数据库或平台专属守护配置。
- SSH 可用后顺序固定：远端盘点 → 远端备份 → 本地展开软链接并打包/rsync → 平台适配 → 数量与实际对话验收。

## 凭证安全：先用交互 SSH 引导公钥，再传大目录

用户提供密码后，不要把密码放进 `sshpass -p ...`、同步脚本、环境文件或可回显的命令行。推荐流程：

1. 用 PTY 启动一次交互式 `ssh`，通过 stdin 提交密码。
2. 读取源机现有 `~/.ssh/*.pub`；若有合适的 Ed25519 公钥，就在已认证会话中幂等加入远端 `~/.ssh/authorized_keys`。
3. 立即用独立连接验证：`ssh -o BatchMode=yes -o ConnectTimeout=10 user@host 'echo KEY_AUTH_OK'`。
4. 只有验证成功后，才用无密码 `rsync` 传大量文件。
5. 不自动生成或替换用户现有密钥；没有公钥时，先说明再决定是否创建专用迁移密钥。

这样既避免密码进入进程参数，也能让后续多个分段同步可恢复、可验证。

## 外部写入审批：把同步拆成有界阶段

全量迁移不要把目录创建、多个大目录 `rsync`、配置适配和验收串成一个超长 shell 命令。外部写入可能需要交互审批；单条命令等待审批时超时，会让执行进度和恢复点不清晰。

如果运行时明确返回“用户拒绝/安全审批拒绝，并要求不要重试”，必须立即停止该写入阶段：

- 不得改写命令，或换 `scp`、压缩包、共享目录等方式绕过；
- 不得把原始任务授权解释为对本次运行时拒绝的覆盖；
- 保留已建立的远端备份、公钥登录和盘点结果；
- 向用户准确报告恢复点与尚未执行的阶段，等待新的明确指令后再继续。

这类拒绝是执行边界，不应记录成“SSH/rsync 不可用”的环境结论。

推荐拆分为：

1. 创建远端目录并验证。
2. 单独同步 `skills/`，使用 `rsync -aL --partial` 展开源端软链接并支持续传。
3. 单独同步 `SOUL.md`、`IDENTITY.md`、`AGENTS.md` 与 `memories/`。
4. 单独同步 wiki、长期知识与 daily memory。
5. 单独执行 Ubuntu 路径适配，不整份覆盖远端 `config.yaml`。
6. 单独执行文件计数、断链检查、配置解析、CLI 与实际对话验收。

每阶段完成后立即记录计数或校验结果，再进入下一阶段。默认不加 `--delete`，保留远端独有技能；排除 `__pycache__/`、`*.pyc`、运行缓存、凭证和状态数据库。若用户已明确授权但审批 UI 再次出现，应提示批准该次具体写入，不要误判为 SSH、密码或文件权限故障。

## 2026-09-06 示例（已去除凭证）

最初目标地址位于不同网段，路由经默认 Wi-Fi 网关，Ping 和 22 都超时。用户纠正为同网段地址后 Ping 成功、Hermes Web UI 端口可达，但 22 返回 `Connection refused`。结论是目标 Hermes 已运行、SSH 未开启；应先启用 SSH，而不是继续排查密码或重新安装 Hermes。

## NetBird：WireGuard 上的远程登录预检

NetBird 把 SSH 套在 WireGuard overlay 之上（管理面 + 数据面），所以同样的“三件事拆开验证”要换成 NetBird 自己的层：

```bash
# 1. 本机 netbird daemon 在线 & 加入了正确的 management
netbird status

# 2. 本机与你直连的 peer 数 vs 在线总数
netbird status | grep "Peers count"
# 例：Peers count 3/167 Connected
#     X/167 中 X 远小于总数 = 你没和大多数 peer 建立 WireGuard 直连（含目标机器）

# 3. 目标机器的 SSH server 是否启用
netbird ssh <user>@<host>            # 报 SSH server detection failed = 默认 Disabled
netbird status | grep "SSH Server"   # 本机状态字段同上，验证默认行为一致

# 4. FQDN 解析（mDNS 由 netbird daemon 代理）
getent hosts <host>                                      # 系统 DNS 查不到 .selfhosted 域是预期
netbird ssh <user>@<host>.netbird.selfhosted             # 走 daemon 解析
```

### 输出判定

| 结果 | 含义 | 下一步 |
|---|---|---|
| `netbird status` 本机 Connected，但 `Peers count 3/167 Connected` 且目标不在 3 之列 | 你与目标机器未建立 WireGuard 直连隧道；WireGuard 是按需 lazy connection，需要目标机器的 daemon 也跑着且两个 peer 都被同 management 授权 | 在目标机器确认 `netbird status` + 同 management；若是，需要授权侧检查 ACL/group |
| `netbird ssh ...` 报 `SSH server detection failed` 或 `SSH Server: Disabled` | 目标机器 netbird SSH server 没开（这是默认安全策略，不是 bug） | 在目标机器执行 `sudo netbird ssh-server enable` 然后 `sudo systemctl restart netbird`（macOS：`brew services restart netbird`） |
| `netbird ssh <user>@<host>` 报 `lookup ... server misbehaving` | 系统 DNS 127.0.0.53 不转发 `.selfhosted`，但 netbird daemon 在用 mDNS；通常是 daemon 没在跑或 peer 未在线 | 先看本机 daemon 状态、再确认目标机器也在线 |
| `netbird ssh` 输入了密码仍 Permission denied | SSH server 已开，但目标 netbird daemon 上的用户白名单不含这个用户名 | `netbird ssh-server users list`（目标端）添加；或换已授权的用户名 |
| mDNS / SSH 都通了 | 才进入凭证、密钥、配置推送 | 走正常 SSH 路径，凭证策略同上 |

### 凭证安全（NetBird 同样适用）

- 涉及 API key / token / 私钥的远端配置推送，**必须先确认主机身份和用户名**，再考虑写入。WireGuard 把所有 peer 都路由到同一 overlay，DNS / mDNS 解析错了会把凭证写到错误机器——而日志里只能看到"成功了"。
- 不要把密码喂给 `netbird ssh` 的 stdin 脚本化回放；走交互或已经预置的 SSH 密钥。
- 写配置前先 `netbird ssh <user>@<host> 'hostname && id'` 验明身份，这是写入操作前的最后一道闸。

### 与传统 SSH 的取舍

- NetBird 优势：跨 NAT / 跨家庭网络无配置；自带管理面板审计 peer 状态。
- NetBird 劣势：默认 lazy connection + 默认 SSH server Disabled → 首次配对必须双方手动确认，比传统 SSH 多一步。
- 已有传统 SSH（LAN / Tailscale / 公网直连）的场景不必为了一次配置切到 NetBird——一次性配置不值这个预检成本。

## 2026-09-14 NetBird 示例（已去除凭证）

用户说"用 netbird 连接到 faeljwj-gdh-x 给那台电脑的 Codex 配置 SUB2API key"。本机 netbird 在线（kk-gdh-x.netbird.selfhosted），但 `Peers count 3/167 Connected`，`netbird ssh ...` 三种写法都失败。原因不是 DNS，也不是密码——而是两件事叠加：目标机器不在 3 个直连 peer 之列（需要目标机器 netbird daemon 在线 + 同 management 授权），且 netbird SSH server 默认 Disabled。正确动作：让用户在目标机器跑 `sudo netbird ssh-server enable` + 重启 daemon，而不是猜密码或继续重试。**API key 全程未写入任何文件。**
