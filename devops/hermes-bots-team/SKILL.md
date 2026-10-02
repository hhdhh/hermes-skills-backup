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
- 手动触发验证：`hermes -p <bot> cron run <id>`——切勿用 `timeout` 包着跑（CLI 被杀会 hard-interrupt 执行，state 变 unknown），用 terminal(background=true) 或裸跑；completed 后查 `profiles/<bot>/state.db` 的 Bot Chat session 验证投递。
- 例行任务一次跑 3-6 分钟正常（bot 会读 skill+多轮工具调用），等待轮询 cron runs 状态即可。

## 坑
- `hermes bot` 子命令不存在（v0.21.3）——bot 管理全走 `hermes profile` + 桌面 Bots 标签。
- clone 后 profile list 显示 Gateway stopped 正常——satellite profile 无独立 gateway.pid，由 multiplexer 代管。
- gateway restart 前确认自己会话不在 systemd gateway 进程树里（Studio bridge worker 独立，安全）。
- 归档技能会让 `.bundled_manifest` 出现"用户已删除"条目——正常，无副作用。
- **tirith 扫描器必须拷给每个 bot**：终端命令预扫描若发现 `$HERMES_HOME/bin/tirith` 缺失会从 GitHub 下载（本机网络超时 5-6 分钟，fail-open 但每次重试）。建完 profile 后立刻 `cp ~/.hermes/bin/tirith profiles/<bot>/bin/`。
- **fae-scheduler 健康检查密码红线**：排班 admin 密码不落盘，自动 routine 只用免认证 `/api/health`；拉全量需管理员现场给密码。
- **skills 目录的 .git 必须停用**：clone 会连 .git 一起拷，remote 指向备份仓库——bot 在自己 skills 下 git add -A 会把归档类目当删除提交，污染备份库。建队后立刻 `mv profiles/<bot>/skills/.git → .git.disabled-bots`；涉及主库操作的 routine prompt 必须写绝对路径 `/home/kk/.hermes/skills/`（~/.hermes 在 bot 环境解析到 bot 自己的 profile）。git 凭证 helper 指向 `~/.hermes/.git-credentials-skills`（绝对路径，用户级，bot 可用）。
- **lark-cli 凭证是用户级**（`~/.lark-cli/`，不随 profile 隔离）——feishu-doc 直接可用，无需 per-profile 配置。user token 需刷新时会自动处理。
- memories 也是 clone 的（MEMORY.md/USER.md 全量拷），建队后按角色裁剪：`~/.hermes/scripts/bots_memory_tailor.py`（关键词路由保留本职条目）。
- bot 桌面展示名：`profile.yaml` 写 `ui_meta: {hermes-bots: {title: ...}}`（工具 `bots_ui_meta.py`）；description 已由 create --description 写入。