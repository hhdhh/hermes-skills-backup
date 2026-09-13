---
name: macos-app-gui-troubleshooting
description: 排查 macOS GUI app "打不开/无窗口/启动后退出" 类问题。覆盖 LSUIElement 菜单栏应用窗口检测、AppKit AutomaticTermination "No windows open yet" 陷阱、TCC 权限请求导致进程自杀的诊断模式、需要 sudo 的 .pkg 重装工作流。触发词：app 打开没窗口、app 闪退、app 一打开就退出、macOS GUI app 起不来、窗口不显示、菜单栏没图标、NoMachine 启动没窗口、launchd 反复重启 app 但 UI 不出。
---

# macos-app-gui-troubleshooting

> Class-level skill：当 macOS GUI app 启动后无窗口、无菜单栏图标、或启动后立即退出时触发。本 skill 适用于**所有第三方 GUI app** 的同类型问题（NoMachine 10.x、Parsec、TeamViewer、Citrix Workspace 等都踩过类似坑）。

## 4 类根因（按概率排序）

### 类别 A：AppKit "AutomaticTermination" 自杀

**症状**：
- `ps aux` 看到进程启动后 50ms 内消失
- `log show` 里看到 `AutomaticTermination: No windows open yet` + `terminate:`
- 进程**永远不显示任何窗口**

**根因**：AppKit 检测到 NSWindow 没创建 → 判定是幽灵进程 → 自动 terminate

**诊断流程**（3 步）：

```bash
# 1. 看进程是否启动后立即消失
ps aux | grep -i <app> | grep -v grep
# 启动一次再查，看到 PID 0.04 秒就换 → 是这个坑

# 2. 看 osascript 是否能列出窗口
osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "<app>")'
# 返回 ",," 或 空 → 窗口没被窗口系统接受

# 3. 看 AppKit / TCC 详细日志
log show --predicate 'process == "<app-process>"' --last 1m --style compact | grep -iE "tcc|terminate|exit|denied"
# 看到 "TCCAccessRequest() IPC → terminate → exit" 链条 = 命中
```

**修复路径**：

| 子情况 | 修法 |
|---|---|
| TCC 权限未授权 | 系统设置 → 隐私与安全性 → 找到对应权限 → 打开开关 |
| TCC 已开但仍自杀 | 完全卸载重装（让 macOS 重新弹授权对话框） |
| LSUIElement=true 菜单栏 app | **不要找主窗口**——查菜单栏右上角（图标准 NSStatusItem） |
| 多个 TCC 权限都缺 | 走"卸载重装"路径让所有对话框重新弹 |

### 类别 B：LSUIElement=true 菜单栏应用设计

**症状**：app 启动后**只有菜单栏图标**，**没有主窗口**——这是设计如此，不是 bug

**判断**：
```bash
defaults read /Applications/<App>.app/Contents/Info.plist LSUIElement
# true  = 菜单栏应用（NSStatusItem only）
# false 或 missing = 普通应用（有主窗口）
```

**修法**：教主人去菜单栏右上角找图标（蓝色 N / 蓝色圆点 / 特定图标），点击会弹出主窗口。

### 类别 C：launchd 反复重启死循环

**症状**：
- 进程列表里 app 的 PID 一直在变（几十秒一换）
- CPU / 电池占用升高
- 系统日志噪音

**根因**：app 自杀 → launchd 检测到进程挂了 → KeepAlive=true 自动重启 → 又自杀 → 循环

**修复（关键：先停 launchd 再修）**：

```bash
# 1. 先 disable launchd job（停止重启循环）
launchctl disable gui/$(id -u)/<plist-name>
# 常见 plist-name: com.<vendor>.<service>, com.nomachine.localnxserver 等

# 2. 杀掉所有当前实例
killall -9 <process-name> 2>/dev/null

# 3. 排查根因（走类别 A 的诊断流程）

# 4. 修好后 enable 回来
launchctl enable gui/$(id -u)/<plist-name>
```

⚠️ **不要一上来就 disable**——主人在场时建议**先排查根因**，disable 后下次启动可能恢复不了。

### 类别 D：需要 sudo 的 .pkg 重装

**症状**：app 持续有问题但 `tccutil reset`、`killall`、清偏好都不能解决

**修复工作流**（**写脚本让主人在 Terminal 一次性跑**——工具这边拿不到 sudo 密码）：

```bash
#!/bin/bash
# <app>-reinstall.sh
set -e
DMG="/path/to/<app>-<version>.dmg"

# 1. 预授权 sudo（这一步会要密码，输一次后 5 分钟内免密）
sudo -v

# 2. 卸载（用 app 自带卸载器或厂商提供的 uninstall.sh）
if [ -f "/Library/Application Support/<vendor>/uninstall.sh" ]; then
    sudo /Library/Application\ Support/<vendor>/uninstall.sh -y
fi

# 3. 清残留 TCC 授权
tccutil reset All <bundle-id> 2>/dev/null || true

# 4. 确认卸载干净
ls /Applications/<App>.app 2>&1  # 应该 No such file
launchctl disable gui/$(id -u)/<plist-name> 2>/dev/null || true
killall -9 <process-name> 2>/dev/null || true

# 5. 挂载 DMG
hdiutil attach "$DMG"
MOUNT_POINT=$(ls -d /Volumes/<App>* | head -1)

# 6. 安装
sudo installer -pkg "$MOUNT_POINT"/*.pkg -target /

# 7. 卸载 DMG
hdiutil detach "$MOUNT_POINT"

# 8. 启动
open /Applications/<App>.app
```

**主人使用**：复制整个脚本到 Terminal.app 粘贴运行，输一次 sudo 密码后全自动。

## 工具层硬约束（Hermes 工具 / OpenClaw 工具）

⚠️ **`sudo` 在工具这边跑不了**：
- `sudo -v` → "a terminal is required to read the password"（PTY 模式也不接受 stdin）
- 唯一可行：`sudo -S` 从 stdin 读密码（但要把密码写进脚本，不安全）
- **正确路径**：写脚本让主人在 Terminal.app 里跑

⚠️ **`launchctl disable` 在工具这边能跑**，但需要明确授权（agent 协议认为这是服务级操作）

⚠️ **`killall -9` 需要明确批准**（force kill 在 Hermes 工具层是 risky 操作）

## 联动

- `hermes-agent-upgrade-recovery` / `openclaw-gateway-upgrade-recovery` —— 同构的"服务恢复"模式（备份 + 干跑 + 验证），但本 skill 是 GUI app 而非 daemon
- `workspace-hygiene` —— 卸载 app 时 `/Applications/<App>.app/` 本身是清得动的，但 `~/Library/Application Support/<App>/` 和 `~/Library/Preferences/com.<vendor>.*` 是优先清的目标
- `self-improving-agent` —— "log 字眼 ≠ 真正原因" 这个误判属于判断流程错误，应该走 self-improving

## 启动信号

- 主人说 "X 打开没窗口" / "X 闪退" / "X 一打开就退出" / "X 启动后没反应"
- `osascript` 查窗口返回空（`,,` 或 missing value）
- `log show --predicate` 看到 `AutomaticTermination: No windows open yet` 链条
- `ls /Applications/<App>.app/Contents/Info.plist` 的 LSUIElement=true
- 进程 PID 频繁换（launchd 重启循环）

## 必读（执行前）

- 主人 ABSOLUTE 行为模式 = 持续委托，**遇到 sudo 类操作需要写脚本让主人跑**——不是列选项
- 主人偏好"帮我解决好"= 全权执行，"还是不行"= 不要重试同一个修法，要换路径
- 列档时如果主人在场+状态清晰，**直接做最深的档**（卸载重装），不要再问"要不要试方法 1"

## 类别 E：GUI 进程拿不到 ssh-agent / 钥匙串（2026-08-07 主人案例）

**症状**：
- 终端 `ssh user@host` 通，IDE（VSCode / JetBrains）的 Remote-SSH 报 `Permission denied (publickey)`
- 终端 `echo $SSH_AUTH_SOCK` 有值，IDE 内置终端 `echo $SSH_AUTH_SOCK` 为空
- VSCode Remote-SSH 日志报 `LocalNetworkPermissionMacOS`（macOS 14+）或 `Permission denied (publickey)`

**根因**：
macOS GUI app 是从 launchd / Dock 起的，**不继承登录 shell 的 ssh-agent 环境**（`SSH_AUTH_SOCK` / `SSH_AGENT_PID`）。即使终端 ssh 通，IDE 进程也拿不到已经 `ssh-add` 的密钥。

**诊断两步**：

```bash
# 1. 终端 agent socket
echo $SSH_AUTH_SOCK

# 2. IDE 内置终端同样命令（VSCode: Terminal 面板；IDEA: Terminal tab）
# 一样 = 链路正常；为空 = GUI 进程环境隔离问题（命中本类别）
```

**完整修复工作流**：

| 步骤 | 操作 | 命令 |
|---|---|---|
| 1 | 私钥权限 | `chmod 700 ~/.ssh && chmod 600 ~/.ssh/id_ed25519` |
| 2 | **持久化到钥匙串**（重启电脑不丢） | `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` |
| 3 | 验证 agent 已加载 | `ssh-add -l`（必须看到私钥 SHA256） |
| 4 | config 全局开钥匙串 | 加 `Host *` 块：`AddKeysToAgent yes / UseKeychain yes / IdentityFile ~/.ssh/id_ed25519` |
| 5 | config 权限 | `chmod 600 ~/.ssh/config` |
| 6 | 终端 baseline | `ssh <目标 IP>` 通（钥匙串路径生效） |
| 7 | **macOS 14+ 本地网络授权** | 系统设置 → 隐私与安全性 → 本地网络 → 打开 VSCode/IDEA |
| 8 | 完全退出 IDE（Cmd+Q） | `killall "Visual Studio Code"` |
| 9 | 重开 IDE | `open -a "Visual Studio Code"` |

**关键坑**：

- ⚠️ `UseKeychain yes` 是 macOS 特有，**只放在 `Host *` 块，不对**——不行，必须每个具体 `Host` 块也写，或确认 `Host *` 块在 config 顶部
- ⚠️ `ssh-add --apple-use-keychain` 没跑 → 重启后 IDE 又拿到旧 agent = 又失败
- ⚠️ IDE **只关窗口不算退出**——必须 Cmd+Q 完全退出（`killall` 等价）
- ⚠️ `~/.ssh/config` 权限 ≥ 644 → ssh 拒绝读，IDE 也读不到
- ⚠️ macOS 14+ 不授权 IDE 本地网络 → 报 `LocalNetworkPermissionMacOS`，**即使 SSH 已配好也连不上**
- ⚠️ **server 端 `ubuntu` 用户没装公钥** = ssh 提示 `password:` 但能登入，**这是密码 fallback，不是密钥通**——IDE 重连时仍会失败（IDE 通常不开密码认证）

**完整命令清单（可粘贴版本）**：

主人要求"给我完整命令"时，**不要在命令块里夹 # 注释**（macOS zsh 默认不识别 `#`），用 `setopt interactivecomments` 启用，或纯命令无注释。

**联动**：
- `network-troubleshooting-ssh` —— 同口径（模式 B：nc 通但 ssh 失败），但本节专注 GUI 端
- `workspace-hygiene` —— 钥匙串已持久化的密钥属于"系统级状态"，不在 workspace 清理范围