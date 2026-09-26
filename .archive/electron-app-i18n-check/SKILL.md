---
name: electron-app-i18n-check
description: 检查一个 macOS Electron 应用是否支持多语言界面（特别是中文）。当主人说"把 X 切中文"、"X 没有中文"、"X 是英文的"、"把 X 界面换中文"时触发。覆盖 ASAR 解包看 i18n 资源、Crowdin/PO/JSON 资源、Electron i18n 实现机制、给主人推荐"真有中文的同类替代品"。触发词：X 切中文、X 是英文的、把 X 换中文、应用本地化、X 没有中文界面、Electron 应用中文、应用汉化。
---

# Electron App i18n 检查

> Class-level skill：判断一个 macOS Electron 应用是否支持中文界面，并给出"有中文"或"无中文"的可信答案。
> 适用所有 Electron 打包的 macOS GUI app（VS Code、Termius、Notion、Discord、Slack、Obsidian 等都符合）。

## 30 秒速答（怎么判断）

**两个标准问法**：

```bash
# Q1: 应用包内有没有多语言 .lproj 目录？
ls /Applications/<App>.app/Contents/Resources/ | grep -E "^[a-z]{2}\.lproj$"
# 期望: en.lproj + zh_CN.lproj + zh_TW.lproj + ...
# 如果只有 en.lproj → 内置无中文

# Q2: app.asar 里有没有 i18n / locale / lang 资源？
mkdir -p /tmp/asar-check && cd /tmp/asar-check
npx --yes asar extract /Applications/<App>.app/Contents/Resources/app.asar app-extracted
find app-extracted -type d -iname "*i18n*" -o -iname "*locale*" -o -iname "*lang*" 2>/dev/null
find app-extracted -name "*.po" -o -name "messages*.json" 2>/dev/null | head -10
ls app-extracted/_locales 2>/dev/null   # 跟 Chrome extension 一样的方式
ls app-extracted/locales 2>/dev/null
```

**判定规则**：
- 有 `zh_CN.lproj` / `zh_CN.locale` / `zh-CN.json` 之一 → **可能支持中文**
- 只有 `en.lproj` / `en-US` / 没有 locale 资源 → **内置无中文**
- 有 locale 资源但全是 hash `.js` 块（`code-18d51648.js`）→ **代码内嵌翻译**，需要单独处理

## Termius 案例（2026-08-07 实测）

主人问"Termius 怎么切中文"。

```bash
$ ls /Applications/Termius.app/Contents/Resources/
app-update.yml
app.asar
app.asar.unpacked
en.lproj              # ← 只有这一个语言目录
icon.icns
```

只有 `en.lproj` → 内置没中文。

```bash
$ cd /tmp/asar-inspect
$ npx --yes asar extract /Applications/Termius.app/Contents/Resources/app.asar app-extracted
$ find app-extracted -type d -iname "*i18n*" -o -iname "*locale*" -o -iname "*lang*"
# (空)
$ find app-extracted -name "*.po"
# (空)
$ find app-extracted -name "messages*.json"
# (空)
$ ls app-extracted/ui-process/assets/ | head -10
--db573d8b.js
Access.react-1bc32b3b.svg
account.react-72823b6a.svg
act-0639134c.js
active.react-b33ee374.svg
# 全部是 webpack/vite 编译产物,没有可读 i18n 资源
```

**结论**：Termius 9.42.2 把所有 UI 资源 webpack 编译成 hash 命名的 `.js` 块，**没有 i18n 资源**。

Termius 历史上使用 Crowdin 翻译（crowdin.com/project/termius），但 9.x 集成方式未知，**官方没有开放用户切换语言**。

## 主人在 macOS 上的中文化路径

### 路径 1：系统级（仅对原生 AppKit 控件有效）

```bash
# 给当前用户所有应用加中文（仅对用系统字符串的应用有效）
defaults write -g AppleLanguages '("zh-Hans-CN", "en")'
# 重启应用
```

⚠️ **Electron 应用通常不读系统语言**——它们用 Chromium 的 V8，**不读 macOS `AppleLanguages`**。这个命令**对 Termius 99% 无效**。

### 路径 2：应用自带的语言切换

```bash
# VS Code
# Code → Settings → 命令面板 → "Configure Display Language" → 选 zh-cn → 重启

# Slack
# Preferences → Languages → 中文

# Discord
# Settings → App Settings → Language → 中文

# Obsidian
# Settings → General → Language → 中文
```

### 路径 3：环境变量（LCTT - Launch Language）

```bash
# LCTT 路径在 ~/.ltt/... (chromium-based only)
# 设置 LANG 启动
LANG=zh_CN.UTF-8 /Applications/SomeApp.app/Contents/MacOS/SomeApp
```

⚠️ 这个对**部分** Electron 应用有效，但要看应用是否真的 fallback 到环境变量取语言。

### 路径 4：换真有中文的同类应用（最现实）

Termius 没中文 → 推荐：
- **Core Shell**（macOS 原生 SSH 客户端，中文界面）
- **WindTerm**（跨平台、免费、中文）
- **FinalShell**（中文）
- **MobaXterm**（Windows 主力，Mac 版也有中文）

## 5 个 macOS 端"真有中文"的应用类型速查

| 应用类型 | 英文主流 | 中文替代/中文版 |
|----------|----------|----------------|
| SSH 客户端 | Termius | Core Shell / WindTerm / FinalShell |
| 代码编辑器 | VS Code | VS Code 中文（内置） / Cursor 中文 / Trae 中文 |
| 终端 | iTerm2 | iTerm2 中文（部分） / WindTerm |
| 笔记 | Obsidian | Obsidian 中文（内置） |
| 浏览器 | Chrome | Chrome 中文（系统语言自动）/ Edge 中文 |
| 远程桌面 | NoMachine | ToDesk 中文 / 向日葵中文 / RustDesk 中文 |
| 数据库 GUI | TablePlus | Navicat 中文（付费） / DBeaver 多语言 |

## 主人"切中文"问题的标准回答模板

```
主人："把 X 切中文" / "X 没有中文吗"

我的回答结构：
1. 一句明确答案（X 有/没有中文界面）
2. 验证证据（哪个文件/目录/命令能复现这个判断）
3. 三档方案
   档 1: 应用自带语言切换（如果有）
   档 2: 系统级 LANG/AppleLanguages 试一下（部分 Electron 有效）
   档 3: 换真有中文的同类应用（最终兜底）
4. 验证方法（打开应用后应该看到什么）
```

## ASAR 检查完整流程（可复用脚本）

```bash
#!/bin/bash
# check-electron-i18n.sh <app.app>
# 用法: ./check-electron-i18n.sh /Applications/Termius.app

set -e
APP="$1"
RES="$APP/Contents/Resources"

echo "=== 1. 内置 .lproj 资源 ==="
ls "$RES" | grep -E "^[a-z]{2}[_-][A-Z]{2,}\.lproj$" || echo "(无 lproj 多语言资源)"
ls "$RES" | grep -E "^[a-z]{2}\.lproj$" || echo "(无 lproj 资源)"

echo ""
echo "=== 2. 解 asar 看 i18n 资源 ==="
if [ -f "$RES/app.asar" ]; then
  ASAR_DIR="/tmp/asar-check-$$"
  mkdir -p "$ASAR_DIR" && cd "$ASAR_DIR"
  npx --yes asar extract "$RES/app.asar" app-extracted
  echo "--- i18n/locale/lang 目录 ---"
  find app-extracted -type d \( -iname "*i18n*" -o -iname "*locale*" -o -iname "*lang*" \) 2>/dev/null
  echo "--- .po / messages.json ---"
  find app-extracted -name "*.po" 2>/dev/null | head -10
  find app-extracted -name "messages*.json" 2>/dev/null | head -10
  echo "--- _locales / locales 直接子目录 ---"
  ls app-extracted/_locales 2>/dev/null || echo "(无 _locales)"
  ls app-extracted/locales 2>/dev/null || echo "(无 locales)"
  cd /tmp && rm -rf "$ASAR_DIR"
else
  echo "(无 app.asar,可能不是 Electron 应用)"
fi

echo ""
echo "=== 3. 结论 ==="
echo "如果上面两步都空 → 应用内置无中文资源"
```

## 反例（不该做的事）

❌ **不要在没解 asar 前告诉主人"X 不支持中文"**——可能错（VS Code 是 Electron 但有完整中文支持）
❌ **不要花时间给应用做 hack/i18n 改写**——成本高、易碎、版本升级就丢
❌ **不要假设 `defaults write -g AppleLanguages` 对 Electron 应用有效**——99% 无效
❌ **不要在没看 asar 时给主人列 3 个替代品**——先验证再推荐
❌ **不要把"系统语言 = 英文"归咎为应用不支持中文**——很多 Electron app 默认用 `navigator.language` 不读 macOS 偏好

## 联动

- `macos-app-gui-troubleshooting` —— 应用**启动/窗口**问题
- `macos-app-no-window-debug` —— 应用**无窗口**问题
- `darwin-skill` —— skill 自身优化
- `desktop-control` —— 用 agent 自动化给应用做操作（不是改 app）

## 实战案例（2026-08-07 Termius 9.42.2）

**主人问题**："将软件设置为中文"

**我的排查**：
1. `which brew && brew list --cask | grep -i termius` → 已装 9.42.2
2. 查 brew cask `termius` 安装信息 → app.asar 在 `Contents/Resources/`
3. `ls /Applications/Termius.app/Contents/Resources/` → **只有 `en.lproj`**
4. 解 asar 验证：
   - `find . -iname "*i18n*"` 空
   - `find . -name "*.po"` 空
   - `find . -name "messages*.json"` 空
   - `ls _locales` / `ls locales` 都空
5. 看 ui-process/assets/ → 全部是 `code-18d51648.js` 这种 hash 命名的 webpack 块

**结论**：Termius 9.x **没有官方中文界面**。

**给主人的三档方案**：
- 档 1: 保留 Termius，靠快捷键习惯（菜单英文）
- 档 2: 装 Core Shell（macOS 原生 + 中文）
- 档 3: 装 WindTerm（跨平台 + 免费 + 中文）

## 验证清单（每次帮主人查"X 中文"前必跑）

```bash
# 1. 找应用路径
ls /Applications/<X>.app 2>&1
ls /opt/homebrew/Caskroom/<x>/*/<X>.app 2>&1 | head -1

# 2. 看 Resources/
ls /Applications/<X>.app/Contents/Resources/

# 3. 找 .lproj
ls /Applications/<X>.app/Contents/Resources/ | grep "\.lproj$"

# 4. 解 asar（如果有）
mkdir -p /tmp/asar-check && cd /tmp/asar-check
npx --yes asar extract /Applications/<X>.app/Contents/Resources/app.asar app-extracted
find app-extracted -type d \( -iname "*i18n*" -o -iname "*locale*" -o -iname "*lang*" \) 2>/dev/null
```

三项结果 → 直接告诉主人"有/没有中文"。

## 已知 Electron i18n 实现模式（速查）

| 应用 | i18n 实现 | 语言切换位置 |
|------|----------|-------------|
| VS Code | `i18n/` 目录 + JSON `package.nls.zh-cn.json` | Ctrl+Shift+P → "Configure Display Language" |
| Slack | `locale/` 目录 + JSON | Settings → Preferences → Languages |
| Discord | `translations/` + JSON | Settings → App Settings → Language |
| Notion | Crowdin 集成 + JSON | Settings → Language |
| Obsidian | `translation/` 目录 + 自有 format | Settings → General → Language |
| Cursor | 类似 VS Code | Settings → 扩展 → 搜 Chinese |
| **Termius 9.x** | **未公开 i18n 资源** | **无 UI 切换** |
| Chrome | `_locales/<lang>/messages.json` | 系统语言自动 |
| Discord Canary | 跟 Discord 同 | 同 Discord |
| Figma | 自有 Crowdin 集成 | 浏览器侧设置 |
| Slack Canary | 同 Slack | 同 Slack |

**经验**：VS Code / Slack / Discord / Obsidian / Notion **都有完整中文**；Termius / Raycast / Arc 这种**不一定**——必须查。
