---
name: skills-github-backup
description: Use when 主人要求备份技能到 GitHub、技能更新后同步远端、或推送报 403/断连需要排查时。
---


# 技能库 GitHub 备份

> 完整描述：把 ~/.hermes/skills 技能库备份/增量推送到 GitHub 私有仓库 hhdhh/hermes-skills-backup。Use when 主人要求备份技能到 GitHub、技能更新后同步远端、或推送报 403/断连需要排查时。

本地仓库 `~/.hermes/skills`（已 git init + remote origin = `github.com/hhdhh/hermes-skills-backup`，main 分支，约 55MB / 3000+ 文件）。

## 增量更新（日常）

```bash
cd ~/.hermes/skills
git add -A && git commit -m "update: <概要>"
git push origin main
```

凭据：repo 级 credential.helper 指向 `~/.hermes/.git-credentials-skills`（0600）。失效时让主人发新 PAT 重写该文件（printf 写入，不带末尾换行）。

## 推送前安全检查（每次必做）

```bash
git grep --cached -E "${ROBOT_CREDS}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{32,}"
```

- 命中 `${ROBOT_CREDS}` → clean filter 没跑：查 `.gitattributes` 规则和 `.git-sanitize.sh` 可执行位。
- 命中完整 token → 该文件本不该进库，从暂存区处理。

脱敏机制：`.gitattributes` 对 md/py/sh/html 挂 `filter=sanitize-creds`（clean = `.git-sanitize.sh`，把机队凭据替换为 `${ROBOT_CREDS}` 占位）——本地工作区明文保留，只有 git 对象脱敏。

## 排除规则（.gitignore 已配）

`_sources/ _external/ .curator_backups/ .hub/ **/node_modules/ **/.venv/ **/__pycache__/` —— 1.1G 精简到约 55M。

## 坑（真实踩过）

- **fine-grained PAT 403**：默认 Contents 权限是 No access，能读不能推（git push 和 PUT contents API 都报 "Resource not accessible"）。生成时必须把 **Contents → Read and write** 勾上（下拉框，不是勾选框）；嫌难找就用 classic token 勾 `repo` 大类。
- **credential store 文件末尾不能有换行**：`echo ... >>` 带 `\n` 会让 push 报 hostname 无效字符——用 `printf '%s'` 写入。
- **大 push 中途断连**（unexpected disconnect / Recv failure）：`git config http.postBuffer 524288000` 后重推，重试常成功；push 放后台跑避免工具超时。
- **远端与本地分叉**（远端有过 API 写入的 commit）：pull `--allow-unrelated-histories` 合并后再推，别 force。
- 推完验证：API `GET /repos/hhdhh/hermes-skills-backup/commits/main` 的 sha == 本地 `git log -1` 的 sha，才算落地；后台任务报错不代表最终结果，以 API 实查为准（迟到的失败通知可能是早已重试成功的旧任务）。

## 可见性提醒

仓库内容含公司运维细节：若远端为 public，每次会话提醒主人去网页 Settings → Danger Zone 转 private（fine-grained PAT 通常无 administration 权限，API 改不了可见性）。
