---
name: openharness
description: HKUDS OpenHarness agent harness + ohmo personal agent. Use `oh -p "..."` for one-shot prompts, `ohd "..."` for dry-run preview, `ohmo -p "..."` for personal-agent mode. Delegates complex coding/research tasks to a 43-tool harness with full MiniMax M3 support.
---

# OpenHarness / ohmo Skill Bridge

**Version**: 0.1.9 (HKUDS)  
**Installed**: 2026-06-19  
**Purpose**: 让 慧慧（main session）和子 agent 能用 `oh` 把复杂任务下放给 OpenHarness 跑

## 快速调用

| 命令 | 用途 | TTY |
|------|------|-----|
| `ohd "fix login bug"` | **Dry-run preview** — 不调模型，只看 skills/tools/commands 匹配 | ❌ 不需要 |
| `oh -p "read X, then Y"` | **真模型调用** + 工具执行 + 流式输出 | ✅ 需要 pty |
| `ohmo -p "..."` | **个人代理模式** — 带 慧慧 soul/user 上下文 | ✅ 需要 pty |
| `oh --print -p "..."` | 同 `oh -p` | ✅ |

## 关键：PTY 包装

`oh` 和 `ohmo` 内部走 React TUI（Ink），需要真 TTY。zshrc 已用 `script -q` 包装：
```bash
oh() { source ~/.openharness-venv/bin/activate; script -q /dev/null command oh "$@"; }
ohmo() { source ~/.openharness-venv/bin/activate; script -q /dev/null command ohmo "$@"; }
```
所以在 exec 调用里：**必须 `< /dev/null` 重定向 stdin**，否则 Ink raw mode 崩。

## 调用模式

### 模式 A：Dry-run preview（推荐先用这个）
```bash
ohd "用 browser 打开 https://example.com 并截图"
# 输出：readiness + 186 skills + 247 commands + 39 tools + 匹配建议
```

### 模式 B：One-shot 任务
```bash
oh -p "用 read_file 读 /path/to/file.md 然后总结要点" < /dev/null
```

### 模式 C：带 ohmo 灵魂（自动加载 soul/user/identity）
```bash
ohmo -p "今天有什么 todo 吗？" < /dev/null
```

## 与慧慧栈的集成点

| 维度 | 状态 |
|------|------|
| **MiniMax M3** | ✅ 用 `~/.openharness/settings.json` 配好（api.minimaxi.com） |
| **Soul 继承** | ✅ `~/.ohmo/soul.md → ~/.openclaw/workspace/SOUL.md` 软链接 |
| **User 继承** | ✅ `~/.ohmo/user.md → ~/.openclaw/workspace/USER.md` 软链接 |
| **Skills 复用** | ✅ 自动扫描 186 个 skills（= `~/.openclaw/workspace/skills/`） |
| **Feishu** | ❌ 不用 ohmo gateway（避免和 OpenClaw 主体抢同一 app） |
| **MCP** | ⚠️ 0 servers configured（用的时候再 add） |
| **Codex++ 复用** | ⏳ 待集成（OpenHarness 内置 codex profile） |

## 已发现的问题

1. **TTY 必需** — Ink raw mode 限制，已用 `script -q` 包装绕过
2. **npm proxy `localhost:8767` 死掉** — 影响 React TUI install 第一次跑；已在 `frontend/terminal/.npmrc` 改为公共 registry
3. **ohmo doctor 失败** — 走 typer interactive prompt，与 script -q 冲突；不影响 `-p` 模式
4. **cwd 默认 = openclaw workspace** — 任务前可加 `--cwd <path>` 切换

## 真实调用示例

```bash
# Dry-run: 看看任务会怎么路由
ohd "用 browser 自动化打开飞书并发送消息"

# 工具调用
oh -p "用 grep 在 ~/.openclaw/workspace/skills 找包含 'feishu' 的所有 SKILL.md" < /dev/null

# Code review 风格
oh -p "用 read_file 读 ~/.openclaw/workspace/skills/openharness/src/openharness/cli.py 第 2240-2260 行，分析 print_mode 的实现" < /dev/null
```

## 故障排查

```bash
# 卡住/无响应
pkill -9 -f "openharness-venv/bin/oh"
pkill -9 -f "npm exec tsx"

# 看 settings
cat ~/.openharness/settings.json
cat ~/.ohmo/gateway.json

# 验证连接
ohd "test"  # 跑出来 readiness: ready 就是好的
```
