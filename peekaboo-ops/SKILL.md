---
name: peekaboo-ops
version: 0.1.0
description: "Peekaboo MCP 已接入 — macOS 截图 / GUI 自动化 / AI 视觉的 stdio MCP server。27 个 mcp__peekaboo__* tools 全可用,默认走 minimax-cn/MiniMax-M3(anthropic-compatible,复用主人 ANTHROPIC_AUTH_TOKEN env)。Use when user asks for macOS 截图 / 截屏 / 看屏 / 描述屏幕 / GUI 自动化 / 点击 / 输入文字 / 打开应用 / 切换窗口 / list apps / describe UI / 'what's on screen' / '截一张图' / '点这个按钮' / '描述屏幕上有什么'。"
metadata:
  requires:
    bins: ["peekaboo"]
  env:
    - ANTHROPIC_AUTH_TOKEN  # 主人 MiniMax 的 anthropic-compatible token (peekaboo config 引用 ${ANTHROPIC_AUTH_TOKEN})
  mcp:
    server: peekaboo
    transport: stdio
    binary: /opt/homebrew/bin/peekaboo
  config:
    - ~/.peekaboo/config.json
    - ~/.claude/settings.json (mcpServers.peekaboo)
  wiki: "~/.openclaw/workspace/wiki/peekaboo-integration.md"
  smokeTests: "~/.openclaw/workspace/exports/peekaboo-restart-smoke.md"
---

# peekaboo-ops · Peekaboo MCP 操作手册

> **装好了就用，别再 exec CLI。** 任何 Claude Code session 启动时自动有 27 个 `mcp__peekaboo__*` tools。

## 何时调我（自动触发）

| User 说 | 用什么 mcp__peekaboo__* |
|---|---|
| "截一张图" / "截图" / "screenshot" | `image` (mode: screen/window/frontmost) |
| "看屏" / "描述屏幕" / "what's on screen" / "describe this window" | `image` + `analyze` (or `see` for element map) |
| "列运行的应用" / "list apps" / "现在跑着什么" | `list` |
| "点 X" / "click X" / "点这个按钮" | `see` (拿 snapshot) → `click` (--on label/id) |
| "输入文字" / "type X" | `type` (--text, --foreground 视情况) |
| "按快捷键" / "cmd+s" | `hotkey` |
| "打开 Safari" / "launch app" / "切到微信" | `app` (launch/switch/focus) |
| "窗口最大化" / "resize window" | `window` |
| "打开 xxx 然后 yyy" (自然语言多步) | `agent` ("natural language task") |
| "看 Dock" / "看 menubar" | `dock` / `menubar` |
| "切 Spaces" / "切桌面" | `space` |
| "看权限" / "peekaboo permissions" | `permissions` |
| "截一段视频" / "record screen" | `capture` (bounded screen recording) |
| "看 UI 树" / "accessibility tree" | `inspect_ui` |

## 何时不调我

- ❌ Linux / Windows（Peekaboo 是 macOS only）
- ❌ 远程 SSH session（peekaboo 抓的是**当前 Mac 的桌面**）
- ❌ 真后台 headless（macOS Server 无 GUI 时 TCC 不会授权）
- ❌ 已经有现成的 `pyautogui` / AppleScript 任务且主人不想换

## 27 个 tools 速查

```
agent           analyze         app             browser         capture
click           clipboard       dialog          dock            drag
hotkey          image           inspect_ui      list            menu
move            paste           perform_action  permissions     scroll
see             set_value       sleep           space           swipe
type            window
```

完整 schema 在 handshake 里：`/opt/homebrew/bin/peekaboo mcp serve` 后 `tools/list`。

## 默认 AI model

```
agent.defaultModel = "minimax-cn/MiniMax-M3"
```

走 **MiniMax anthropic-compatible endpoint** ——`https://api.minimaxi.com/anthropic`，用主人现有的 `ANTHROPIC_AUTH_TOKEN` env（**token 没进 config 文件**，安全）。

显式指定 model 跑：
```
mcp__peekaboo__agent --model minimax-cn/MiniMax-M3 "..."
```

可选 fallback：`minimax-cn/MiniMax-M3[1M]`（1M context variant）。

## 关键 flag 速记

| 场景 | 加什么 |
|---|---|
| Retina 2x 截图 | `--retina` |
| 截图 + AI 描述 | `image --mode screen --analyze "描述"` |
| 拿 UI element map（后续要 click） | `see --app X --json`（返回 snapshot_id）|
| 不抢前台焦点（默认已 background） | `--app Safari`（自动 background input）|
| 必须前台才能输 | `--foreground` |
| 等元素出现再操作 | `--wait-for "element"` |
| 坐标点击（fallback） | `--coords 100,200` |
| 滚轮 | `scroll --direction up/down --amount N` |

## 失败时怎么 debug

| 症状 | 修法 |
|---|---|
| `tool not found` mcp__peekaboo__* | session 没重启 → `! exit && claude` |
| `unsupported call` (Codex) | Codex 0.141 rmcp runtime bug，等 0.142+（v1 wiki 段有详）|
| MiniMax `401` | `echo $ANTHROPIC_AUTH_TOKEN` 看 env 还在 |
| MiniMax `model not found` | 看 `~/.peekaboo/config.json` 的 `customProviders.minimax-cn.models` 有没有声明该 model id |
| Screen Recording 失效 | `mcp__peekaboo__permissions` 重 check；或系统设置手动给权限 |
| 截图返回黑屏 | TCC 没授——`peekaboo permissions request-screen-recording` 弹窗授权 |
| 点击没反应 | 用 `mcp__peekaboo__see --app X` 拿新 snapshot，可能 UI 变了 |

## 紧急回滚

```bash
# MCP entry 还原
cp ~/.claude/settings.json.bak-pre-peekaboo-mcp-20260621-024843 ~/.claude/settings.json

# Peekaboo config 还原（去掉 customProviders）
cp ~/.peekaboo/config.json.bak-pre-minimax-20260621-030119 ~/.peekaboo/config.json

# 完全卸载
brew uninstall steipete/tap/peekaboo
```

## 主人偏好（在 peekaboo 上下文里适用）

- **trust-but-verify**：长任务先 dry-run / 单步验证，不要一把梭
- **删除走 trash 不走 rm**（即使 peekaboo 不删文件，提醒）
- **中文输出**：mcp__peekaboo__agent 的 prompt 用中文能拿到中文回答
- **不要重启服务**：peekaboo daemon 自管理，不需要手动 restart

## 参考

- 完整 wiki（v1 Codex + v2 Claude Code）：`~/.openclaw/workspace/wiki/peekaboo-integration.md` (257 行)
- Restart-ready smoke tests：`~/.openclaw/workspace/exports/peekaboo-restart-smoke.md`
- Peekaboo 官方 docs：https://github.com/openclaw/Peekaboo/tree/main/docs
- Tachikoma anthropic-compatible provider 源码：`steipete/Tachikoma/Sources/Tachikoma/Providers/Compatible/AnthropicCompatibleProvider.swift`

---

_慧慧 prep · 2026-06-21 · v0.1.0_