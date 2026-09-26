---
name: macos-gui-app-troubleshooting
description: 排查 macOS GUI app 打开后窗口不显示 / 闪退 / 静默退出问题。覆盖 NSWindow 未创建、LSUIElement agent app 设计、TCC 权限拒绝自终止、launchd 守护反复拉起死循环、AppKit AutomaticTermination (No windows open yet)、osascript 查窗口等于空。触发词:app 打开没窗口、app 闪退、app 启动后立刻消失、菜单栏图标没出来、TCC 权限、launchd 重启循环、LSUIElement、Application 启动不了。
---

# macOS GUI App Troubleshooting

> Class-level skill:macOS 上任何 GUI app 出现 "进程在跑但窗口不出来 / 立刻消失" 时的标准化排查路径。

## 核心三件事先判别

进程在跑但窗口不出来,先用 30 秒判别是哪一类问题:

```
1. 进程真的在跑吗?
   → ps aux | grep -i <appname>
   → 如果没有 → 检查 .app 是否在 /Applications、launchd plist 是否设了 KeepAlive

2. 进程在跑但窗口没出来?
   → osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "<name>")'
   → 返回 ,,(空) → 窗口没创建 → NSWindow 失败

3. 进程在跑但频繁被杀 / 反复重启?
   → ps aux 短时间内 PID 一直在变 → 进程自杀 / launchd 反复拉起
```

## 4 个常见根因 + 诊断特征

### 根因 1:TCC 权限被拒 → 进程自动退出

**特征**:进程启动后约 50ms 内 `AppKit terminate` → `Termination complete. Exiting without sudden termination.`

**诊断**:
```bash
log show --predicate 'process == "<进程名>"' --last 2m --style compact \
  | grep -iE "tcc|terminate|exit|denied" | head -20
# 期望看到:TCCAccessRequest() IPC → ~50ms → terminate
```

**修复**:
```bash
# 1. 系统设置 → 隐私与安全性 → 对应权限 → 开关打开
#    常见需要的权限:
#    - 屏幕录制(kTCCServiceScreenCapture)
#    - 辅助功能 / 输入监控(kTCCServicePostEvent)
#    - 完全磁盘访问权限
#    - 文件与文件夹 / 桌面与文档
#
# 2. 如果开关已开仍自杀 → 完全卸载重装,首次启动会重新弹授权对话框
#    (卸载:见根因 4 的 uninstall 路径)
```

**判别是哪种权限的关键**:`log show` 看 TCC 报错的服务名。屏幕录制请求通常伴随着 `TCCAccessLaunchDisclosurePromptIfNeeded` 而不是 `ScreenCapture`。

### 根因 2:NSWindow 从未创建 → AppKit 静默退出

**特征**:进程启动后约 50ms 内 `AutomaticTermination: No windows open yet` → terminate

**诊断**:
```bash
log show --predicate 'process == "<进程名>"' --last 2m --style compact \
  | grep -iE "AutomaticTermination|terminate|window" | head -20
```

**可能子原因**:
- 主入口的 NSWindowController 初始化抛异常(没日志,但也不创建窗口)
- LSUIElement=true 期望有 NSStatusItem,但 NSStatusItem 创建失败

**修复**:完全卸载重装 + 首次启动观察 Console.app 看详细日志。

### 根因 3:LSUIElement=true 的 agent app 设计(不一定是 bug)

**关键认知**:`Info.plist` 的 `LSUIElement = true` 意味着这个 app 是 agent app(菜单栏图标),**不应该**有主窗口。需要看菜单栏右上角的图标,点它才弹窗口。

**诊断**:
```bash
defaults read /Applications/<App>.app/Contents/Info.plist LSUIElement
# true = agent app
# false / 缺失 = 正常 app,启动后应该有主窗口
```

如果 LSUIElement=true,**第一件事**告诉用户去菜单栏右上角找图标。**不要**误以为是 bug。

### 根因 4:launchd 守护反复拉起死循环(被根因 1 或 2 触发)

**特征**:`launchctl list` 看到 launchd job,**进程 PID 持续变化**(几秒一个新 PID)。

**诊断**:
```bash
launchctl list | grep -i <appname>
# 输出最后列 PID,PID 短时间一直变 → 重启循环
```

**修复**(阻断 launchd 重启循环):
```bash
# 1. 停 launchd 守护(防止它反复拉起进程,留时间给你修根因)
launchctl disable gui/$(id -u)/<job-label>

# 2. 杀掉所有残留进程
killall -9 <进程名>

# 3. 修根因(开权限 / 重装 / 改配置)

# 4. 修完恢复 launchd 自启
launchctl enable gui/$(id -u)/<job-label>
```

**关键经验**:
- **disable 后** launchd 不再重启 app,可以安静地修根因
- **修完务必 enable 回来**——主人可能依赖开机自启
- 不要 `pkill` launchd 本身,会破坏系统

## 标准排查流程(60 秒决策树)

```
macOS GUI app 窗口不出来
├─ 1. ps aux 确认进程在跑
│   ├─ 没有 → 看 launchd / .app 路径 / 安装状态
│   └─ 在跑 ↓
│
├─ 2. osascript 查窗口(关键判别点)
│   ├─ 返回 ,,(空) → 进程没创建窗口
│   └─ 有窗口名 → 不是这个 skill 的范围
│
├─ 3. log show --process <进程名> --last 2m | grep -iE "tcc|terminate|window"
│   ├─ 看到 TCCAccessRequest → 根因 1(开权限)
│   ├─ 看到 AutomaticTermination "No windows open yet" → 根因 2(NSWindow 失败)
│   ├─ 看到都没有但窗口空 → 看根因 4(launchd 重启循环)
│   └─ 看到其他错误 → 按错误走
│
└─ 4. defaults read <App>/Contents/Info.plist LSUIElement
    ├─ true → 根因 3(agent app 设计,菜单栏找图标)
    └─ false / 缺失 → 正常 app,问题在别处
```

## 完整排查命令模板(可直接复制)

```bash
# 第 1 步:确认进程
ps aux | grep -iE "<进程名>" | grep -v grep

# 第 2 步:查窗口
osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "<进程名>")'
# 返回 ,,(空) → 进第 3 步

# 第 3 步:看最近 2 分钟的进程日志
log show --predicate 'process == "<进程名>"' --last 2m --style compact \
  | grep -iE "tcc|terminate|window|denied|fault" | head -30

# 第 4 步:判断 app 设计类型
defaults read /Applications/<App>.app/Contents/Info.plist LSUIElement

# 第 5 步:查 launchd 重启循环
launchctl list | grep -i <appname>

# 第 6 步:查 TCC 授权状态(只能看自己的)
# 注意:TCC.db 受 SIP 保护,新版 macOS 可能打不开
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  "SELECT service, client, auth_value FROM access WHERE client LIKE '%<app>%' OR client LIKE '%<bundle-id>%';"

# 第 7 步:看应用自身日志路径(如果有)
find /Library/Application\ Support/<App> ~/Library/Application\ Support/<App> \
  /var/log -name "*.log" 2>/dev/null | head -5
```

## 修复路径决策表

| 根因 | 修法 | 是否 sudo | 是否需要重启 |
|---|---|---|---|
| TCC 权限被拒(根因 1) | 系统设置打开权限 + 完全卸载重装触发重新授权 | sudo 卸载 | 否(卸载重装不需要) |
| NSWindow 失败(根因 2) | 完全卸载重装 + 观察 Console.app | sudo 卸载 | 否 |
| LSUIElement agent app(根因 3) | 告诉用户去菜单栏找图标,不是 bug | 否 | 否 |
| launchd 重启循环(根因 4) | launchctl disable → 修根因 → launchctl enable | 否 | 否 |

## 反例(不该做的事)

❌ **不要** `killall -9` 后立即重启——没修根因就重启,只是再自杀一次
❌ **不要** 用 `defaults delete com.<bundle-id>` 清偏好 → 偏好清了 TCC 授权可能还在
❌ **不要** 改 `Info.plist` 的 `LSUIElement`——这是 app 设计意图,改完 app 行为会变
❌ **不要** 直接删 `/Library/Application Support/<App>/`——会丢 app 自己的配置 / 状态,卸载器会自动处理
❌ **不要** 在 launchd disable 状态重启电脑——可能 launchd 状态丢失,需要手动 enable 回来
❌ **不要** 主人没下令就 `launchctl disable`——launchd 自启是主人可能依赖的,先报账让主人决定
⚠️ **`launchctl disable` 抑制重启循环是好做法,但如果主人没明确下令 disable,做完根因诊断后立即 `launchctl enable` 回来**——不要把"暂时 disable"留成长期状态,主人可能等你下班后才用 app
❌ **不要** 用 macOS 系统 `python3 -m pip`——太老,装不到大部分包

## sudo 不可用时的降级路径(关键工作流)

macOS `sudo` 永远需要主人在 Terminal.app 手动输密码,工具端无法代输。当排到 "需要 sudo 才能修" 的一步时:

**第一步:把后续所有 sudo 命令打包成一个 `bash /tmp/<task>.sh` 脚本**

- 脚本里第一个命令必须是 `sudo -v`(预授权)
- 预授权后 5 分钟内所有 sudo 都免密
- 把整个卸载/清授权/挂 DMG/安装/启动流程串成单脚本

**第二步:告诉主人"打开 Terminal.app → 粘贴 `bash /tmp/<task>.sh` → 第一次 sudo 输密码 → 全自动跑完"**

**第三步:不要尝试各种 sudo 变通**(`-n`、`echo password | sudo -S`、askpass helper 等都不行)— 这些是反模式,会让主人怀疑你的能力

**反例**:不要 `sudo -n` 后看到 "password required" 还反复尝试——直接降级到脚本方案

## 联动 skill

- **`workspace-hygiene`** 坑 18-28 都是 macOS 实战,但聚焦 "清理 / 升级";本 skill 聚焦 "运行时 GUI 排查",正交
- **`openclaw-dashboard-troubleshooting`** 是 OpenClaw Dashboard 专属,本 skill 是通用 macOS GUI app;遇到 Dashboard 问题先看那个,通用 macOS 问题看本 skill
- **`diagnose`** 是通用 debugging 方法论(Reproduce → Hypothesise → Instrument),本 skill 是它在 macOS GUI 场景的实例化

## 参考案例(references/)

- `references/nxplayer-no-window-macos27.md` — 2026-08-06 排查 NoMachine 10.0.57 在 macOS 27 Tahoe 上窗口不显示的完整诊断日志、命令模板、修复尝试、未解原因推断

## 验证清单(排查完成后报账模板)

```bash
# 1. 进程在跑 + 稳定(不重启)
ps aux | grep -i <进程名> | grep -v grep | head -3
# 多次观察 PID 不变 → 不在重启循环

# 2. 窗口列表非空
osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "<进程名>")'
# 非空 → 窗口创建成功

# 3. 日志无 terminate 警告
log show --predicate 'process == "<进程名>"' --last 30s --style compact \
  | grep -iE "terminate|denied" | head -5
# 无 terminate / 无 denied → 稳定

# 4. launchd 状态正常
launchctl list | grep -i <appname>
# 有 PID 且稳定 → 不在重启循环
```