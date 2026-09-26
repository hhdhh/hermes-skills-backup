---
name: macos-ssh-keychain-gui-bridge
description: macOS 上终端 SSH 通但 GUI app（VSCode / JetBrains IDEA / PyCharm / 其他 IDE）SSH 失败的完整修复链路。覆盖 ssh-agent 持久化到钥匙串、~/.ssh/config 全局开 UseKeychain、macOS 14+ LocalNetwork 权限、IDE 完全退出策略、OrbStack 虚拟网桥等。触发词：IDE SSH 失败、VSCode Remote-SSH 连不上、Permission denied publickey、SSH_AUTH_SOCK 为空、macOS 14 LocalNetwork、UseKeychain、ssh-add --apple-use-keychain、终端通 IDE 不通。
---

# macOS SSH Keychain ↔ GUI Bridge

> Class-level skill：解决"macOS 终端 ssh 通，但 IDE（VSCode / JetBrains）ssh 失败"这个 class 问题。
> 根因 = macOS GUI 进程不继承登录 shell 的 ssh-agent 环境。
> 解法 = 把密钥持久化进钥匙串 + ~/.ssh/config 全局开 UseKeychain + IDE 重启重读环境。

## 何时触发

- VSCode Remote-SSH / JetBrains SSH 报 `Permission denied (publickey)`
- VSCode Remote-SSH 报 `LocalNetworkPermissionMacOS: 找不到具有本地 IPv4 地址的远程计算机的路由`（macOS 14+）
- 终端 `ssh host` 通，IDE 同样目标失败
- 终端 `echo $SSH_AUTH_SOCK` 有值，IDE 内置终端 `echo $SSH_AUTH_SOCK` 为空
- 重启电脑后 IDE SSH 又失败（密钥只在内存 agent 里，没进钥匙串）

## 根因（一次理解，永远记得）

macOS 上**终端进程**和 **GUI 进程**是两套环境：

- **终端**（Terminal.app / iTerm / Warp）：从 shell 登录会话启动 → 拿到 `SSH_AUTH_SOCK` / `ssh-agent` / 系统钥匙串
- **GUI IDE**（VSCode / IDEA / PyCharm）：从 launchd 启动 → **不继承终端 agent** → 即使终端 ssh 能连，IDE 也拿不到已加载的密钥 → 报 `Permission denied (publickey)`

**macOS 14+ 额外一层**：本地网络访问需要显式授权（系统设置 → 隐私与安全性 → 本地网络）。VSCode / IDEA 即使 SSH 链路完整，没授权也会被静默拦截。

## 5 步完整修复（master workflow）

| # | 步骤 | 命令 | 备注 |
|---|------|------|------|
| 1 | 私钥权限 | `chmod 700 ~/.ssh && chmod 600 ~/.ssh/id_ed25519` | macOS ssh 强制 |
| 2 | **钥匙串持久化** | `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` | **最关键**——不跑这条，重启后 IDE 又失败 |
| 3 | 验证 agent | `ssh-add -l` | 必须看到私钥 SHA256 |
| 4 | config 全局钥匙串 | 加 `Host *` 块：`AddKeysToAgent yes / UseKeychain yes / IdentityFile ~/.ssh/id_ed25519` | `UseKeychain yes` 让 GUI 进程能读钥匙串密码 |
| 5 | config 权限 | `chmod 600 ~/.ssh/config` | ≥644 ssh 拒读 |
| 6 | 终端 baseline | `ssh user@host` | 通 = 客户端链路完整 |
| 7 | macOS 14+ 本地网络 | 系统设置 → 隐私与安全性 → 本地网络 → 打开 IDE | **手动一步**，agent 这边动不了 TCC db |
| 8 | 完全退出 IDE | `killall "Visual Studio Code"` | **Cmd+Q 等价，不是关窗口** |
| 9 | 重开 IDE | `open -a "Visual Studio Code"` | IDE 重读环境 |

## 可粘贴的完整命令（无 # 注释）

主人说"直接命令"时，**复制这一段进 Terminal**：

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
ssh-add -l
chmod 600 ~/.ssh/config
cat > ~/.ssh/config << 'CFG'
Include ~/.orbstack/ssh/config

Host *
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_ed25519

Host 192.168.65.207
  HostName 192.168.65.207
  User ubuntu

Host 192.168.10.2
  HostName 192.168.10.2
  User ubuntu
CFG
chmod 600 ~/.ssh/config
ssh 192.168.65.207
killall "Visual Studio Code"
open -a "Visual Studio Code"
```

⚠️ **不要在命令块里夹 # 注释**（macOS zsh 默认 `setopt interactivecomments` 未开，会 `chmod: #: No such file or directory`）

## 进阶诊断（IDE 还是不工作）

### 1. 区分是 IDE 环境问题还是 server 端公钥问题

**客户端环境验证**：
```bash
ssh -v user@host 2>&1 | grep -E "loaded pubkey|Authentications|publickey|password"
```
应该看到 `loaded pubkey from /Users/kk/.ssh/id_ed25519` + `Authentications that can continue: publickey,password`

**server 端公钥验证**（最常见的隐性失败）：
```bash
# 看 server 上 ubuntu 用户的 authorized_keys 有没有你的公钥
ssh ubuntu@host "cat ~/.ssh/authorized_keys" 2>&1
# 或者用密码登入 server，自己看
ssh ubuntu@host
cat ~/.ssh/authorized_keys
```

**⚠️ 关键坑**：`ssh host` 提示 `password:` 但输密码登入成功 ≠ 密钥链路通——是 **server 端没装主人公钥**，ssh 自动 fallback 到密码。**IDE 通常不开密码认证**，所以 IDE 重连仍会失败。

**修复**：用 `ssh-copy-id user@host` 推公钥，或手动 `cat ~/.ssh/id_ed25519.pub | ssh user@host "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"`

### 2. IDE 内置终端能不能拿到 SSH_AUTH_SOCK

VSCode: Terminal 面板；IDEA: Terminal tab

```bash
echo $SSH_AUTH_SOCK
```

- ✅ 跟主机终端输出一样 → 链路正常，问题在别处
- ❌ IDE 内为空 → macOS GUI 进程没继承 agent（仍是 root cause，但 config / UseKeychain 没生效，要重开）

### 3. macOS 14+ LocalNetwork 权限

即使 SSH 客户端和 server 都 OK，VSCode 报：
```
LocalNetworkPermissionMacOS: 找不到具有本地 IPv4 地址的远程计算机的路由
```

**修法**：系统设置 → 隐私与安全性 → 本地网络 → 打开 VSCode / IntelliJ IDEA / PyCharm 等

agent 这边动不了 TCC 数据库，需要主人在 GUI 里手动点。

## 分 IDE 特殊设置

### VSCode Remote-SSH

- 完全退出（Cmd+Q 或 `killall "Visual Studio Code"`）
- Remote-SSH 配置**直接复用 `~/.ssh/config`**，不要在 Remote-SSH: Configuration 里再写一遍密钥
- **Terminal 启动可临时绕开 GUI 隔离**：`code .`（继承 shell 环境）
- 看详细错：Cmd+Shift+P → Remote-SSH: Show Log

### JetBrains 全家桶（IDEA / PyCharm / CLion / GoCode）

- Settings → Build, Execution, Deployment → SSH Configurations
- Authentication type: **OpenSSH config and authentication agent**（优先）
- **不要选 JSch** —— 不支持 macOS 钥匙串
- **Toolbox 启动**会比桌面图标启动好（修复 GUI 环境变量继承）
- 终端启动 IDE：`idea` / `pycharm` / `clion` 命令（继承 shell 环境）

## 4 类常见坑

### 坑 1：只跑 `ssh-add` 不跑 `--apple-use-keychain`

`ssh-add` 只把密钥加载到当前内存 agent，**重启电脑后丢失**。`--apple-use-keychain` 把密码也存进钥匙串，**IDE 重启 / 电脑重启都不丢**。

### 坑 2：IDE 没完全退出

只关窗口（Cmd+W）= 进程还在 = 还用旧的 agent socket。新环境不生效。
**`killall "Visual Studio Code"` 等价 Cmd+Q**，但更稳（确保杀干净）。

### 坑 3：`~/.ssh/config` 权限太宽

`chmod 644 ~/.ssh/config` → ssh 拒绝读 → IDE 也读不到 IdentityFile 配置。
**必须是 `chmod 600`**（或更严）。

### 坑 4：macOS 14+ LocalNetwork 没授权

SSH 链路全通，IDE 仍连不上 → 看 Remote-SSH 日志里有没有 `LocalNetworkPermissionMacOS`。
**agent 修不了**——主人必须去系统设置手动开。

## 实战案例（2026-08-07）

**主人症状**：
- 终端 `ssh 192.168.65.207` 通
- VSCode Remote-SSH 报 `LocalNetworkPermissionMacOS` + `OfflineError`

**诊断**：
1. `ls -la ~/.ssh/config` → 权限 644，**没开 UseKeychain** ❌
2. `ssh-add -l` → 密钥已加载但**没存进钥匙串** ❌
3. `chmod 600 config` + 改 config + `ssh-add --apple-use-keychain` → 客户端修好
4. 系统设置手动开 VSCode LocalNetwork → IDE 修好

**教训**：**ssh 通 ≠ 密钥链完整**。终端和 GUI 是两套进程，必须**双向修**——客户端钥匙串 + 系统授权。

## 联动

- `network-troubleshooting-ssh` —— 通用 SSH 排错（5 层决策树）；本 skill 是其 GUI 化身的细节
- `macos-app-gui-troubleshooting` —— GUI 进程环境隔离（本 skill 是其 ssh-agent 维度）
- `workspace-hygiene` —— 系统钥匙串里的 SSH 密码属于系统级状态，不在 workspace 清理范围

## 验证清单（master 跑完前）

```bash
ls -la ~/.ssh/id_ed25519 | awk '{print $1}'                    # -rw-------
ls -la ~/.ssh/config | awk '{print $1}'                        # -rw-------
ssh-add -l                                                     # 必须看到私钥 SHA256
ssh-add --apple-use-keychain --apple-load-keychain ~/.ssh/id_ed25519 2>&1 || ssh-add -l  # 已加载就不报错
ssh -v user@host 2>&1 | grep "loaded pubkey"                   # 看到客户端加载了
ssh -v user@host 2>&1 | grep -E "Authentications that can continue"  # 看认证方法列表
```

四项通过 → 客户端链路完整。剩下 macOS 14 LocalNetwork 授权是主人手动一步。