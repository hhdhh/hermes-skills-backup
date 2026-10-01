---
name: external-skill-deploy
description: Use when 部署 GitHub 第三方 skill 到 Hermes。装机+多用户隐私隔离适配。
---

# 外部 Skill 装机与多用户适配（GitHub 单仓形态）

一个 GitHub 仓库自带 SKILL.md 直接装进本 Hermes 环境的流程与护栏。与 third-party-skill-bundle-install（manifest.json 套件分发形态）互补：那边严格按第三方 install_guide 走，这边自己控制全部步骤。

## 装机流程

1. **Clone 走代理**（GitHub 直连常超时）：
```bash
git clone --depth 1 https://github.com/<org>/<repo>.git /tmp/<repo>
# 环境注入 https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
```
2. **跑仓库自带校验**（有 validate/verify 脚本必跑）；复制到正式目录后再跑一次复核。
3. **复制进 `~/.hermes/skills/<name>/`**（copytree，忽略 `.git/` 与大 assets 目录）。
4. **多用户适配审计**（见下——单用户 skill 直接上多用户网关会互相串档案）。
5. **端到端验收**：两个身份各跑 enable/写入/隔离/读回/清理，全绿才算装好。

## 多用户隐私隔离（核心护栏）

外部 skill 多为单人设计；本环境是飞书网关，管理员+多位同事共用同一个 agent，任何本地档案/记忆都是高度隐私。

1. **先读存储代码找重定向钩子**：环境变量 override（如 `GOUTOUJUNSHI_MEMORY_DIR`）优于改源码——写薄包装脚本注入 per-user 目录，原逻辑零改动。
2. **身份键只认 gateway 元数据**（open_id，`ou_`+32hex），不靠自报姓名；包装器用正则校验 open_id 防目录穿越。
3. **物理分库**：`~/.local/share/<skill>/users/<短哈希_open_id片段>/`，一人一库；原脚本自带的 0700/0600 权限保留。
4. **SKILL.md 追加多用户硬规则段**：不跨库读写、不聚合分析、群里收到相关话题引导私聊、无 open_id 通道（cli/cron）不开记忆。
5. **备份边界**：私有数据目录从 skills git 备份仓库排除（.gitignore 加条目）——档案永不上 GitHub。
6. **同意门禁保留并验收**：enable 需显式 `--confirm` 的设计原样保留，不绕过。

## 坑

- `~/.hermes/skills/` 是 git 备份仓库——放新 skill 前想清楚哪些内容可公开；私有数据一律放 `~/.local/share/` 外部目录。
- 原版 CLI 的枚举字段（scope/confidence/source_type）以脚本源码为准，先 grep 合法值再构造，猜枚举值会 INVALID_DELTA。
- 技能 create 的 description 有 60 字预算，超长被截断破坏路由——细节写进 SKILL.md 正文。
- 装机当场的会话里技能索引不含新技能——触发要等新会话。
