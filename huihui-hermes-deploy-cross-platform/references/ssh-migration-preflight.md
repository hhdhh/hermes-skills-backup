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
