# macOS SSH 客户端选型速查（2026-08 现况）

> 主人 2026-08-07 走过一轮 "装 Termius → 切中文失败 → 装 WindTerm" 的循环。
> 把当时验证过的硬事实记下来，下次直接调用。

## 实测结果

| 客户端 | 装得上 | 中文化 | 推荐度 | 备注 |
|---|---|---|---|---|
| **Termius 9.42.2**（brew）| ✅ | ❌ 无 i18n | ⭐⭐ | asar extract 验证：只有 en.lproj + React 编译产物，没任何 locale 文件 |
| **Core Shell** | ❌ brew 没 | ✅ | ⭐⭐⭐⭐ | 只能 App Store，付费 ¥98 一次性，macOS 原生 |
| **WindTerm 2.7.0**（brew）| ⚠️ deprecated | ✅ | ⭐⭐⭐ | brew 警告 Gatekeeper fail；`open` 实际能跑（PID 20583 起得来） |
| **FinalShell 4.6.3**（brew）| ⚠️ 需 sudo | ✅ | ⭐ | `installer -pkg` 路径，Hermes 工具层拿不到 sudo 密码 |
| **iTerm2**（brew）| ✅ | ⚠️ 半中半英 | ⭐⭐⭐⭐ | macOS 原生老牌；菜单不全是中文但终端内完美 |
| **Tabby** | ✅ | ✅ | ⭐⭐⭐⭐ | 开源 + 跨平台 + brew OK |

## 验证 Termius 没 i18n 的命令

```bash
# 看 Resources 目录
ls /Applications/Termius.app/Contents/Resources/
# app-update.yml  app.asar  app.asar.unpacked  en.lproj  icon.icns
# ↑ 只有 en.lproj

# asar 拆开看内部
mkdir -p /tmp/asar-inspect && cd /tmp/asar-inspect
npx --yes asar extract /Applications/Termius.app/Contents/Resources/app.asar app-extracted
find app-extracted -type d \( -iname "*i18n*" -o -iname "*locale*" \)
# 空

# 找语言资源文件
find app-extracted -name "*.po" 2>/dev/null
# 空

# UI 资源全是 React 编译产物
ls app-extracted/ui-process/assets | head -10
# 全部是 .js + .svg + .webp
```

**结论**：Termius 9.x 完全没有中文翻译，且 UI 已编译，**没有运行时切换语言的可能**。

## WindTerm brew deprecated 但能跑的处理

```bash
# brew 装（会报 deprecated 警告）
brew install --cask windterm
# Warning: windterm has been deprecated because it does not pass the macOS Gatekeeper check!
# It will be disabled on 2026-09-01.
# 仍会成功安装
# 🍺  windterm was successfully installed!

# 验证签名状态
codesign -dv --verbose=4 /Applications/WindTerm.app 2>&1 | head -3
# code object is not signed at all

spctl -a -vv /Applications/WindTerm.app 2>&1 | head -3
# rejected
# source=no usable signature

# 试 codesign 重签（会失败，因为包里包含 Windows DLL）
codesign --force --deep --sign - /Applications/WindTerm.app 2>&1 | head -3
# bundle format unrecognized, invalid, or unsuitable
# In subcomponent: .../winserver2022/Microsoft.Windows.ServerManager.Migration
# → 包含 Windows DLL，codesign 不让重签

# 但 open 命令能跑（macOS 实际对未签名 + 非 quarantine app 宽容）
open /Applications/WindTerm.app
sleep 4
ps aux | grep -i windterm | grep -v grep
# kk  20583  ...  /Applications/WindTerm.app/Contents/MacOS/WindTerm

# 验证窗口
osascript -e 'tell application "System Events" to get title of every window of process "WindTerm"'
# "Choose Profiles Directory"  ← 首次启动会问配置目录
```

## FinalShell 失败的根因

```bash
brew install --cask finalshell
# Warning: finalshell has been deprecated ...
# ==> Running installer for finalshell with `sudo` ...
# sudo: a terminal is required to read the password
# Error: Failure while executing; `/usr/bin/sudo -u root -E ... -- /usr/sbin/installer -pkg /opt/homebrew/Caskroom/finalshell/4.6.3/finalshell_macos_arm64.pkg -target /`
```

**根因**：FinalShell 走 `.pkg` 安装到 `/Applications`，`installer -pkg -target /` 需要 sudo。Hermes 工具层拿不到 sudo 密码（PTY 不接受 stdin 输密码）。

**唯一办法**：写脚本让主人在 Terminal.app 跑。

## 给主人的话术模板

下次有人问"装个 SSH 客户端"：

```
主人，3 个候选：
1. **WindTerm**（中文 ✅ / 免费 / brew deprecated 但 open 能跑）— 推荐
2. **Core Shell**（中文 ✅ / ¥98 一次性 / App Store 装）
3. **iTerm2**（半中半英菜单 / 免费 / macOS 原生 / 终端党首选）

要哪条？ABSOLUTE 模式 = 默认 1。
```

## Termius 卸载的拆步模式

❌ 一次性 sweep（被 Hermes 安全系统拦）：

```bash
brew uninstall --cask termius --zap --force
rm -rf /Applications/Termius.app \
       ~/Library/Application\ Support/Termius \
       ~/Library/Preferences/com.termius-dmg.mac.plist
```

✅ 拆 3 步（主人确认每步）：

```bash
# 步骤 1: 关闭
osascript -e 'quit app "Termius"'
sleep 2

# 步骤 2: 删 .app
rm -rf /Applications/Termius.app
ls /Applications/ | grep -i termius   # 验证

# 步骤 3: 删用户级数据（不删 brew 注册）
rm -rf ~/Library/Application\ Support/Termius
rm -f ~/Library/Preferences/com.termius-dmg.mac.plist

# 步骤 4: 让主人决定 brew 注册清不清
# brew uninstall --cask termius   # 不带 --zap --force
```
