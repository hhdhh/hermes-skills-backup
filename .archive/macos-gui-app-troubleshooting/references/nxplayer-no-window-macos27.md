# nxplayer 在 macOS 27 Tahoe 上"启动即死"的诊断记录

> 一次性事实记录:2026-08-06 排查 NoMachine 10.0.57 客户端时观察到的症状。
> 未来遇到 NoMachine / 类似 agent app(LSUIElement=true)在 macOS 27 上不显示窗口,回来翻这份。

## 症状

- 用户启动 `/Applications/NoMachine.app`(10.0.57,8/4 发布)
- `nxdock` 进程在跑,`nxplayer` 也在跑
- 但 macOS 菜单栏**完全没图标**,桌面无窗口
- `osascript ... get name of every window of (processes where name contains "nx")` 返回 `,,`(空)

## 关键日志片段

```
2026-08-06 15:51:08.857 nxplayer [...] [AppKit:AutomaticTermination] void _NSDisableAutomaticTerminationAndLog(NSString *) No windows open yet
2026-08-06 15:51:08.859 nxplayer [...] (TCC) TCCAccessRequest() IPC
2026-08-06 15:51:08.874 nxplayer [...] [AppKit:Application] Termination complete. Exiting without sudden termination.
```

规律:**TCC 请求 → ~50ms → AppKit terminate → 退出**。每个 nxplayer 实例生命周期 <100ms。

## 诊断特征

1. `Info.plist` 的 `LSUIElement = true`——**这是设计如此**:NoMachine 客户端是 agent app,主入口(进程)是菜单栏 daemon,真实窗口在用户点图标后才创建
2. `nxdock` 是 launchd 守护启动的中介进程,不断拉起 `nxplayer`
3. `nxplayer` 在 `LSUIElement=true` 的设计下,本应创建 `NSStatusItem`(菜单栏图标),但 NSStatusItem 创建**失败了**,所以 AppKit 报 "No windows open yet",自动 terminate
4. 真实根因不在 TCC 本身——是 NSStatusItem 创建失败的副作用

## 修复路径(本次未解决,留作未来调查)

| 尝试 | 结果 |
|------|------|
| `killall` 后重启 | ❌ 还是自杀 |
| 清偏好 `defaults delete` | ❌ 还是自杀 |
| 屏幕录制权限开关重启 | ❌ 还是自杀(问题不在屏幕录制) |
| 完全卸载 → 重装 10.0.57 → TCC reset | ❌ 重装后**首次启动仍自杀**——说明不是 TCC 残留,是代码本身 |

## 推断可能根因(未验证)

- **TCC 是 `kTCCServicePostEvent`(输入监控)而非 `ScreenCapture`**:日志里 `TCCAccessLaunchDisclosurePromptIfNeeded` 不带服务名,但 macOS 27 Tahoe 的输入监控授权对话框是**只弹一次,自动拒绝后永不弹**
- **Codex/Codex++/OpenClaw 等其他 app 抢占了 PostEvent 授权**:NoMachine 启动时检测不到,自动退出
- **NoMachine 10.0.57 在 macOS 27 Tahoe 上有未修 bug**:8/4 发布,可能是赶工版本

## 排查命令模板(NoMachine 专属)

```bash
# 进程
ps aux | grep -iE "nxdock|nxplayer|nxnode|nxrunner|nxd" | grep -v grep

# 窗口检测(关键是这一行,会返回 ,,)
osascript -e 'tell application "System Events" to get name of every window of (every process whose name contains "nx")'

# TCC + terminate 日志(核心诊断)
log show --predicate 'process == "nxplayer"' --last 2m --style compact \
  | grep -iE "tcc|terminate|AutomaticTermination|exit" | head -30

# 设计类型
defaults read /Applications/NoMachine.app/Contents/Info.plist LSUIElement
# true = agent app,菜单栏找图标

# launchd 重启循环
launchctl list | grep -i nomachine
# 看到 com.nomachine.localnxserver PID 短时间一直变 → 重启循环

# 卸载器位置(两个都可能)
ls /Library/Application\ Support/NoMachine/nxuninstall.sh
ls /Applications/NoMachine.app/Contents/Resources/uninstall.sh

# DMG 安装包路径(主人本地)
/private/tmp/openclaw/downloads/2028930a-1397-44f2-a4b4-27ac04df2899-nomachine-personal-edition_10.0.57_2.dmg
```

## 替代方案(不修 NoMachine 也能达成目标)

- **连远程服务器**:SSH 系统自带 / Parsec / Moonlight / RustDesk
- **让别人连这台 Mac**:macOS 自带屏幕共享(系统设置 → 通用 → 共享 → 屏幕共享)

## 这次学到的(已写进主 SKILL.md)

- **sudo 不可用时降级路径**:打包成 `bash /tmp/<task>.sh`,主人 Terminal 跑一次即可
- **`launchctl disable` 抑制循环后必须 `enable` 回来**:不要留成长期状态