---
name: hermes-bots-team
description: "Use when 建/管 Hermes bots 团队或多 bot profile。Bot=profile."
version: 1.0
---

# Hermes Bots 团队（Bot Mode）

Bot = Hermes profile（`~/.hermes/profiles/<name>/`），桌面端 Bots 标签内置展示。每个 bot 独立 config/.env/SOUL/技能/记忆。

## 现有团队（2026-10-01 建）

| Bot | 职责 | 技能数 |
|---|---|---|
| fleet-ops | 机队 SSH 检修/DDS/电池/SLAM/回充排障 | 38 |
| fae-scheduler | FAE 排班 API 查询 | 4 |
| feishu-doc | 飞书文档/周报/案例归档 | 27 |
| skill-keeper | 技能 GitHub 备份/蒸馏/卫生 | 18 |

管理员主对话留在 default（飞书通道只在 default，clone 时自动不拷贝）。

## 建新 bot 流程（实测 12s/个）
1. `hermes profile create <name> --clone --description "一句话职责"` — 拷 config/.env/SOUL/技能（1.8G），不拷飞书通道（防 token 冲突）。
2. 精简技能：非本职类目移入 `profiles/<name>/skills/.archive-bots/`（可逆；update 不会 sync 回来，归档不在 sync 路径）。工具：`~/.hermes/scripts/bots_team_setup.py`（BOTS 字典改 keep 清单）。
3. 嵌套技能要单独捞：很多技能嵌在 `devops/`、`autolife/`、`productivity/` 等类目下，类目归档后用 `bots_team_restore_nested.py` 捞回顶层。
4. 写 `profiles/<name>/SOUL.md` 角色卡（身份+专精+工作准则+红线+口吻）。
5. 开 multiplex（一次性，已开）：`hermes config set gateway.multiplex_profiles true` + `systemctl --user restart hermes-gateway`（config 不热生效，必须 restart）。
6. 验证：`hermes profile list`；`gateway_state.json` 的 served_profiles 含全部 bot；`<bot-name> chat -q "你是谁" -Q` 冒烟。

## Routine（bot 定时任务）
- cron 底层：`hermes cron create ... --deliver bot-chat:<profile>`，任务名前缀 `[bot:<name>]`，落在 bot 自己的 canonical chat。
- multiplex gateway 会 tick 所有 bot 的 cron（日志见 "Cron scheduler will tick N profile(s)"）。

## 坑
- `hermes bot` 子命令不存在（v0.21.3）——bot 管理全走 `hermes profile` + 桌面 Bots 标签。
- clone 后 profile list 显示 Gateway stopped 正常——satellite profile 无独立 gateway.pid，由 multiplexer 代管。
- gateway restart 前确认自己会话不在 systemd gateway 进程树里（Studio bridge worker 独立，安全）。
- 归档技能会让 `.bundled_manifest` 出现"用户已删除"条目——正常，无副作用。
- bots 无 default 的 MEMORY.md（clone 不拷 memories），关键知识写进各自 SOUL.md。