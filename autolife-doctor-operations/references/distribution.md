# Codex、Plugin 与 Skill 安装

> 对齐版（2026-09-13）：实际走 **apt + doctor agent install**（本地 marketplace），GitHub marketplace 方式仅作备选。原版两种方式并列易混淆。

Codex 可安装在 FAE 工作站、开发机或机器人上。使用当前普通用户的 `~/.codex`，并使用该用户启动 Codex。

## 安装（apt 优先 · 公司内网标准路径）

```bash
# 1. 内网 apt 源 + GPG key（公司标准，apt.gz.autolife.ai:8444）
sudo bash -c 'echo "deb [signed-by=/usr/share/keyrings/autolife-archive-keyring.gpg] https://apt.gz.autolife.ai:8444 stable main" > /etc/apt/sources.list.d/autolife.list'
sudo apt update

# 2. 安装（Codex CLI + doctor + skill 三件套）
sudo apt install codex autolife-doctor autolife-doctor-skill

# 3. 写配置 + 凭据（0600）
#    ~/.codex/config.toml  — model_provider 指向 sub2api，base_url 带 /v1（规范 API 根）
#    ~/.codex/auth.json    — OPENAI_API_KEY = sub2api 的 Codex 密钥，权限 0600

# 4. 插件装入 Codex（本地 marketplace，不是 GitHub）
autolife-doctor agent install

# 5. 启动并验证
autolife-doctor agent start
autolife-doctor agent verify   # 内容完整性校验
codex --version                # 确认 0.154.0+；若 npm 旧版遮蔽 PATH，卸 npm 版
```

**验证要点（血泪教训）**：
- `which codex` 必须指向 `/usr/bin/codex`（apt 版）。npm 装的旧版会 PATH 遮蔽 → `npm -g uninstall @openai/codex`。
- `base_url` 必须带 `/v1`：`https://sub2api.autolife-robotics.com/v1`。
- 密钥验证：`curl -sS -H "Authorization: Bearer $KEY" https://sub2api.autolife-robotics.com/v1/models` 应 200。

## 备选：GitHub Marketplace（无内网 apt 源时）

```bash
codex plugin marketplace add AutoLifeRobot/AutolifeRobotDoctor
codex plugin add autolife-doctor-operations@autolife-internal
```

本地开发检出也可以将 Skill 目录链接到 `~/.codex/skills/autolife-doctor-operations`。

## ⚠️ 插件缓存会被校验还原（重要）

`~/.codex/plugins/cache/` 里的插件内容受 `agent verify` 完整性校验保护——**直接改缓存里的 SKILL.md 会被还原**（实测 2026-09-13）。自定义/增强版技能放**用户级目录**（`~/.codex/skills/` 或 Hermes 侧 `~/.hermes/skills/`），不动缓存。

## 启动

```bash
codex
```

进入 Codex 后使用：

```text
$autolife-doctor-operations 检查并维修当前机器人
```
