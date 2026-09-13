# Case: NoMachine 10.0.57 + macOS 27 Tahoe — 启动后无窗口

> 实战沉淀：2026-08-06 主人找灰灰排查 NoMachine "打开没窗口显示"。
> 这是 `macos-app-no-window-debug` skill 的第一个完整案例。

## 主人原话

> "电脑上的 nomachine 没办法正常使用，打开后没有窗口显示怎么回事"

## 环境快照

| 项 | 值 |
|----|----|
| App | `/Applications/NoMachine.app` |
| 版本 | 10.0.57（最新 stable，2026-08-04 发布） |
| macOS | 27.0 (Tahoe) |
| 架构 | Apple Silicon (M5) |
| 启动时间 | 2026-08-06 15:38（首次观察到） |

## 诊断时间线

### 15:49 · 第一次探针

```bash
$ ps aux | grep -i nomachine | grep -v grep
kk  66143 /Applications/NoMachine.app/Contents/MacOS/nxdock
kk  70535 /Applications/NoMachine.app/Contents/MacOS/nxplayer
kk  66102 nxrunner --monitor
kk  66074 nxnode --localsession
nx  62330 nxd    # ← 注意 user 是 nx, 不是 kk
```

**发现 1**：进程都在跑。`nxd` 跑在 `nx` 用户下（launchd 守护，跨 user）。

### 15:49 · 窗口检测

```bash
$ osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "nx")'
,,
```

**发现 2**：返回空 `,,` = nxplayer **没注册窗口到 WindowServer**。

### 15:50 · LSUIElement 检测（关键转折）

```bash
$ defaults read /Applications/NoMachine.app/Contents/Info.plist LSUIElement
true
```

**发现 3**：NoMachine 是**菜单栏 app**！`LSUIElement=true` = 不创建主窗口，只创建菜单栏图标。

**主人预期应该看到**：屏幕右上角菜单栏有 NoMachine 图标（蓝色 N）。

### 15:51 · 自终止日志

```bash
$ log show --predicate 'process == "nxplayer"' --last 5m --style compact | grep -iE "tcc|terminate"
(TCC) TCCAccessRequest() IPC
(TCC) TCCAccessLaunchDisclosurePromptIfNeeded() IPC
[com.apple.AppKit:Application] terminate:
[com.apple.AppKit:Application] Termination complete. Exiting without sudden termination.
[com.apple.AppKit:AutomaticTermination] void _NSDisableAutomaticTerminationAndLog(NSString *) No windows open yet
```

**发现 4**：每次 nxplayer 启动 → TCC 请求 → 50ms 后 AppKit 终止。日志里 `AutomaticTermination "No windows open yet"` = NSWindow/NSStatusItem **根本没创建出来**。

### 15:53 · TCC 授权尝试（误判 + 浪费一步）

我猜是 TCC 屏幕录制权限缺失，让主人去**系统设置 → 隐私与安全性 → 屏幕录制**打开 NoMachine。

主人开了 → 我重启 app → 日志显示**还是同样的自终止模式**。

**教训**：TCC 开权限不一定能修。如果根因不是 TCC，开了也没用。

### 15:55 · 进程重启循环确认

```bash
$ ps aux | grep -i nxplayer | grep -v grep
kk  76315 0.0 0.2 ... /Applications/NoMachine.app/Contents/MacOS/nxplayer
kk  76316 0.0 0.2 ... /Applications/NoMachine.app/Contents/MacOS/nxplayer
# 3 秒后
$ ps aux | grep -i nxplayer | grep -v grep
kk  76420 0.0 0.2 ... /Applications/NoMachine.app/Contents/MacOS/nxplayer
kk  76421 0.0 0.2 ... /Applications/NoMachine.app/Contents/MacOS/nxplayer
```

PID 持续变化 = nxdock 在疯狂重启 nxplayer（每个都自终止）。

### 15:55 · 菜单栏图标确认

```bash
$ osascript -e 'tell application "System Events" to get name of every menu bar item of menu bar 1 of (first process whose name is "SystemUIServer")' 2>&1 | tr ',' '\n' | grep -i nx
# (空)
```

**确认**：菜单栏**没 NoMachine 图标** → NSStatusItem 没创建成功。

## 主人选路

主人答："**完全没看到 NoMachine 图标**" → 确认是 NSStatusItem 创建失败。

我给了三档修法让主人选：

1. 轻量：杀进程 + 清偏好 + 重启
2. 中量：完全卸载 + 全新授权重装
3. 重量：等 app 升级

主人在我没提醒的情况下直接做了方法 1+2：杀掉所有残留进程 + 备份偏好文件 `~/Library/Preferences/com.nomachine.nxdock.plist` + 清掉重启。

**结果**：方法 1+2 没修好（因为根因是 NSStatusItem 创建失败，权限/偏好不是问题）。

## 根因结论

**NoMachine 10.0.57 在 macOS 27 Tahoe 上存在 NSStatusItem 创建失败 bug**——nxplayer 启动后没创建窗口也没创建菜单栏图标，AppKit 50ms 后自动终止。

**当前状态（截至会话结束）**：根因未修，等 NoMachine 10.0.58+ 修复，或用第三方远程桌面替代。

## 沉淀到 skill 的关键模式

1. **LSUIElement=true 不等于没窗口**——菜单栏 app 的设计是只显示菜单栏图标，要先看菜单栏再判断
2. **`osascript 'every window of process'` 返回空** = 进程没注册任何窗口到 WindowServer
3. **`AutomaticTermination "No windows open yet"` 日志** = NSWindow/NSStatusItem 都没创建出来
4. **TCC 开权限不一定修**——要看 `log show` 确认根因模式
5. **launchd 守护进程的 user 不是自己**——killall/sudo kill 杀不掉，要用 launchctl 控制
6. **`log show --predicate 'process == "X"' --last 5m --style compact | grep -iE "tcc|terminate|exit|fault|windows open yet"`** = macOS GUI app 排错的瑞士军刀

## 后续 TODO

- [ ] 监控 NoMachine 10.0.58+ 发布（子 agent `deleg_dd51f1bf` 任务）
- [ ] 如果长期不修，建议主人考虑替代：macOS 自带屏幕共享 / RustDesk / Jump Desktop
- [ ] 把这个案例的 `log show` 模式抽成 scripts/check_app_window.sh