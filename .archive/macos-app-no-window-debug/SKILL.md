---
name: macos-app-no-window-debug
description: 排查 macOS GUI 应用"打开了但看不到窗口"问题——进程在跑但 WindowServer 没收到窗口。覆盖 LSUIElement 误判、TCC 权限导致自终止、NSStatusItem 创建失败、launchd 守护进程残留。触发词：app 打开没窗口、NoMachine 没窗口、应用启动后白屏、菜单栏图标不出现、app 启动了但是看不到、进程在但是没界面、LSUIElement、TCC 自终止。
---

# macos-app-no-window-debug

> Class-level skill：macOS GUI 应用启动后**进程在跑但没窗口显示**的端到端排错。
> 适用于任何 .app（NoMachine / VLC / OBS / Discord / Zoom / 第三方 IDE 等），不限于具体 app。

## 核心判断（先于所有操作）

**窗口不显示 ≠ app 没启动**。要先确认 app 进程**真的在跑**，再判断窗口为什么没出来。

3 个核心区分：

| 进程状态 | 窗口状态 | 含义 |
|---------|---------|------|
| ✅ 进程在 | ✅ 窗口注册到 WindowServer | app 正常，问题在视觉层（被遮住/最小化/全屏外） |
| ✅ 进程在 | ❌ 进程没创建窗口（`osascript` 返回空） | app 启动后**没创建窗口**，原因见下方决策树 |
| ❌ 进程不在 | n/a | app 没启动成功，跳到 app 启动失败类技能 |

## 第一步：确认进程真的在跑

```bash
# 通用探针（替换 AppName）
ps aux | grep -i AppName | grep -v grep
```

如果进程**不在**，那不是本 skill 的问题（跳到 app 启动失败类技能）。如果进程**在但没窗口**，继续。

## 第二步：关键诊断三连

```bash
# 1. 看进程有没创建窗口（osascript 查 WindowServer 注册的窗口列表）
osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "AppName")'

# 2. 看进程是不是 agent app（菜单栏 daemon, 不应该显示窗口本身）
defaults read /Applications/AppName.app/Contents/Info.plist LSUIElement
# true = 菜单栏 app（点击菜单栏图标才出窗口）—— 这是设计,不是 bug
# false 或不存在 = 普通 app（应该自动出窗口）

# 3. 看进程是不是 launchd 守护（PID 用户不是你自己, killall 杀不掉）
ps -o pid,user,comm -p <PID>
# user 列不是 kk / 你的用户名 = launchd 守护跑在专用 user 下
```

**关键发现案例**：
- `osascript` 返回 `,,` 或空 = 进程**没创建窗口**
- `LSUIElement = true` = 进程**只是菜单栏 daemon**，需要点击菜单栏图标才出窗口——主人在屏幕右上角找图标
- `user != kk` = launchd 守护，killall/sudo kill 都可能杀不掉，需要 launchd 控制

## 第三步：找进程自终止原因（如果是启动了又退）

如果进程**反复重启**（PID 一直在变），用 `log show` 抓终止日志：

```bash
# 抓进程最后 5 分钟的关键日志
log show --predicate 'process == "AppName"' --last 5m --style compact 2>&1 | \
  grep -iE "tcc|terminate|exit|denied|fault|reason|windows open yet" | head -30
```

### 模式 A：TCC 自终止（最常见）

```
(TCC) TCCAccessRequest() IPC
... 50ms ...
[com.apple.AppKit:Application] terminate:
[com.apple.AppKit:Application] Termination complete. Exiting without sudden termination.
```

含义：app 启动 → 50ms 内调 TCC 请求某项权限 → 没拿到或拿不到 → AppKit 自动终止。

**TCC 权限类型**（按出现频率排序）：

| TCC service | 系统设置位置 | 触发场景 |
|------------|------------|---------|
| `kTCCServiceScreenCapture` | 隐私与安全性 → 屏幕录制 | 屏幕共享/远程桌面/录屏类（NoMachine、VLC、OBS、Zoom） |
| `kTCCServiceMicrophone` | 麦克风 | 语音通话/录音类 |
| `kTCCServiceCamera` | 摄像头 | 视频通话类 |
| `kTCCServiceAccessibility` | 辅助功能 | 输入监控/键盘记录类（Karabiner、Alfred） |
| `kTCCServiceAppleEvents` | 自动化 | 跨 app 自动化类 |

**修复**：告诉主人去对应权限开关**关掉再打开**，重启 app。授权变更不会自动通知已启动的进程。

### 模式 B：AutomaticTermination "No windows open yet"

```
[com.apple.AppKit:AutomaticTermination] void _NSDisableAutomaticTerminationAndLog(NSString *) No windows open yet
... terminate ...
```

含义：app 启动 → 创建了 `NSApplication` 但**没创建任何窗口**（也没创建 `NSStatusItem`）→ AppKit 自动终止"无窗口的孤儿进程"。

**这是 NSStatusItem 创建失败或 NSWindowController 初始化失败的硬信号**。这种情况通常需要：
1. 先确认是不是 `LSUIElement=true` 菜单栏 app（如果是，菜单栏应有图标）
2. 看 app 自己的 stderr 输出（如果能直接跑二进制）
3. 看 DiagnosticReports：`~/Library/Logs/DiagnosticReports/` 有没有 `.crash` 文件

### 模式 C：launchd 守护拉起失败

```
ps -o pid,user,comm → user 列是 _nx / _spotlight 等系统用户
```

含义：app 的核心组件是 launchd 跑的守护进程，跑在专用 user 下。

**killall/sudo kill 杀不掉**——因为你的 shell 是你的 user，跨 user 杀进程受 SIP / TCC 限制。

**修复**：
```bash
# 1. launchctl 控制（需要知道 launchd job label）
launchctl list | grep -i AppName
# 看到 com.AppName.daemon 之类的 label

# 2. 停掉守护
launchctl kill SIGTERM system/com.AppName.daemon  # system 域
launchctl kill SIGTERM gui/$(id -u)/com.AppName.useragent  # user 域

# 3. 等 2-3 秒,看进程是不是真退了
ps aux | grep -i AppName | grep -v grep
```

## 第四步：菜单栏 app 排查（如果 LSUIElement=true）

`LSUIElement=true` 的 app 设计就是**不显示窗口，只在菜单栏显示图标**。如果主人说"没窗口"：

```bash
# 看菜单栏（SystemUIServer 的菜单栏）
osascript -e 'tell application "System Events" to get name of every menu bar item of menu bar 1 of (first process whose name is "SystemUIServer")' 2>&1 | tr ',' '\n' | grep -i AppName

# 看菜单栏上是否能看到 app 的 NSStatusItem
# 没看到 = NSStatusItem 没创建成功（回到第二步模式 B）
```

**告诉主人**：屏幕右上角菜单栏**找图标**（一般是 app 的首字母或方块）。找到点一下就出窗口。

## 第五步：偏好清理（杀进程 + 清缓存 + 重启）

很多"幽灵 app"问题是**窗口状态 / 偏好文件损坏**。最后试一次：

```bash
# 1. 杀掉所有相关进程（杀不掉的就 kill -9）
killall AppName 2>/dev/null
killall -9 AppName 2>/dev/null
sleep 2

# 2. 备份 + 清理偏好（trash > rm）
find ~/Library/Preferences -maxdepth 1 -name "*AppName*" -o -name "*app.identifier*" 2>/dev/null | while read f; do
  echo "Moving: $f"
  mv "$f" "$f.bak.$(date +%s)" 2>/dev/null
done

# 3. 清理 Application Support（如果存在,先备份）
[ -d ~/Library/Application\ Support/AppName ] && \
  mv ~/Library/Application\ Support/AppName ~/Library/Application\ Support/AppName.bak.$(date +%s)

# 4. 重启 app
open /Applications/AppName.app

# 5. 验证窗口是否出来
sleep 4
osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "AppName")'
```

## 完整决策树

```
app 打开没窗口
├─ ps aux 有进程?
│   ├─ 没有 → 跳到 app 启动失败类技能（不是本 skill 范围）
│   └─ 有 → 继续
│
├─ osascript 'every window' = 空?
│   ├─ 否（有窗口名）→ 窗口存在但被遮住 / 最小化 / 全屏外
│   │   └─ 试 ⌘+Tab 切换 / 检查 Mission Control / N 秒后再次确认
│   └─ 是（空）→ 继续
│
├─ LSUIElement = true?
│   ├─ 是 → 菜单栏 app,找菜单栏图标
│   │   ├─ 有图标 + 点了出窗口 → 解决
│   │   ├─ 有图标 + 点了没反应 → 看 NSStatusItem 是否卡死,试 killall + 启
│   │   └─ 没图标 → 跳到 NSStatusItem 创建失败模式（继续下面）
│   └─ 否 → 普通 app,应该自动出窗口 → 继续
│
├─ 进程反复重启（PID 一直在变）?
│   ├─ 是 → 看 log show 找自终止原因
│   │   ├─ 模式 A: TCC → 系统设置 → 权限 → 关掉重开 + 重启 app
│   │   ├─ 模式 B: AutomaticTermination "No windows open yet" → NSStatusItem/NSWindow 创建失败,通常需要等 app 修复或换版本
│   │   └─ 模式 C: launchd 守护拉起失败 → launchctl kill
│   └─ 否（进程稳定但没窗口）→ 看 app 自己的 stderr / DiagnosticReports
│
└─ 上述都不行?
    ├─ 备份偏好 + 清缓存 + 重启（第五步）
    └─ 重装最新版
```

## 反例（不该做的事）

❌ **不要把 `LSUIElement=true` 当成 bug**——这是设计（菜单栏 app），主人在菜单栏找图标
❌ **不要 `killall -9` launchd 守护进程**——用户切换，sudo 也杀不掉，用 launchctl 控制
❌ **不要 echo 任何 token / API key 到自己的 conversation memory**——本 skill 不涉及凭据，但排查 app 时如果看到 token，照常保护
❌ **不要盲目授权所有 TCC 权限**——一项一项开，先开最可能的（屏幕录制/麦克风/摄像头），看 log show 确认是哪个 service
❌ **不要 `rm -rf ~/Library/Application Support/AppName`**——先 `mv` 备份，可恢复
❌ **不要修改 `/Library/Application Support/AppName/`（系统级）**——这是 app 自己的配置，agent 改它可能损坏安装
❌ **不要把 app 的 stderr 直接丢给主人**——agent 先看，过滤明显的 bug 后再说

## 验证清单（每次排查前必跑）

```bash
# 1. 进程真的在
ps aux | grep -i AppName | grep -v grep

# 2. 窗口注册到 WindowServer
osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "AppName")'

# 3. LSUIElement 标志
defaults read /Applications/AppName.app/Contents/Info.plist LSUIElement 2>/dev/null

# 4. 进程是否 launchd 守护
ps -o pid,user,comm -p $(pgrep -x AppName | head -1)

# 5. DiagnosticReports（最近 10 个 app 相关崩溃）
ls -lt ~/Library/Logs/DiagnosticReports/ 2>/dev/null | grep -i AppName | head -5

# 6. log show 自终止模式（最近 5 分钟）
log show --predicate 'process == "AppName"' --last 5m --style compact 2>&1 | \
  grep -iE "tcc|terminate|exit|denied|fault|reason|windows open yet" | head -30
```

四项全跑 = 拿到足够信息判断走哪个分支。

## 联动

- `openclaw-dashboard-troubleshooting` — 浏览器侧 dashboard 问题，跟本 skill 不同（dashboard 是 web，本 skill 是 native app）
- `openclaw-gateway-upgrade-recovery` — gateway 启动阶段问题，跟本 skill 不同（gateway 是 daemon）
- `chrome-headless-debug` — 浏览器侧 headless 调试，跟本 skill 不同（浏览器 vs native app）
- `workspace-hygiene` — 磁盘清理，不直接相关但清理偏好时可联动（mv 备份而非 rm）

## 实战案例（2026-08-06 NoMachine 10.0.57 + macOS 27 Tahoe）

**症状**：主人打开 NoMachine，进程在跑（nxdock + nxplayer），osascript 返回空窗口，菜单栏也没有图标。

**诊断过程**：
1. `ps aux | grep -i nomachine` → 进程在
2. `osascript 'every window'` → 空 → 窗口没创建
3. `defaults read LSUIElement` → **true** → 是菜单栏 app，找图标
4. 让主人看菜单栏 → 主人答：**完全没看到图标**
5. `log show` → 看到 `TCCAccessRequest` 后 50ms 自终止 + `AutomaticTermination "No windows open yet"`
6. 让主人开屏幕录制权限 → 重启 app → **还是不行**（TCC 不是根因）
7. 结论：NSStatusItem 创建失败 → NoMachine 10.0.57 在 macOS 27 Tahoe 上的兼容 bug → 等 app 升级

**给主人的三档修法**（最终方案）：

| 档位 | 操作 | 风险 |
|------|------|------|
| 轻量 | 杀进程 + 清偏好 + 重启 | 无（备份了） |
| 中量 | 完全卸载 + 全新授权重装 | 中（丢 app 配置但保留服务器连接密码） |
| 重量 | 等 app 升级（看子 agent 查最新版本） | 无（等待） |

**学到的关键模式**：
- TCC 开权限**不一定能修**——如果根因不是 TCC，开了也没用，需要看 `AutomaticTermination "No windows open yet"` 这种更深日志
- NSStatusItem 创建失败的判断：菜单栏 app 启动后菜单栏**没图标** = `osascript` 查菜单栏为空
- `log show --predicate 'process == "X" --last 5m --style compact | grep -iE "tcc|terminate|exit|fault"` 是 macOS GUI app 排错的瑞士军刀