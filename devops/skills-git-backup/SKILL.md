---
name: skills-git-backup
description: Use when 主人说"备份技能/上传技能库到 github"、技能大改后例行备份、或验证备份仓库无敏感泄露。
---


# 技能库 git 备份（脱敏 → commit → push GitHub）

> 完整描述：把 Hermes 技能库（~/.hermes/skills）做凭据脱敏的 git 备份并推 GitHub。Use when 主人说"备份技能/上传技能库到 github"、技能大改后例行备份、或验证备份仓库无敏感泄露。

## 现状

`~/.hermes/skills` 已是 git 仓库（main 分支，初始提交 941afc2，3040 文件 / 约 55 MiB），配好 .gitignore 与脱敏 filter。例行备份只需增量 commit + push。

## 流程

1. **增量提交**：`cd ~/.hermes/skills && git add -A && git commit -m "skills update: <摘要>"`（add 时 clean filter 自动脱敏）。
2. **验证脱敏**（每次 push 前必做）：
   ```bash
   git grep --cached -l '${ROBOT_CREDS}'   # 应只剩 .gitattributes（规则字符串本身）
   git grep --cached -E 'ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}'  # 应为空
   ```
3. **推送**：需要 GitHub PAT（repo 权限，建议私有仓库）。
   ```bash
   git remote add origin https://<用户名>:<PAT>@github.com/<用户名>/<repo>.git  # 首次
   git push -u origin main
   ```
4. push 后回读验证：`git ls-remote origin main` 与本地 `git rev-parse main` 一致。

## 排除规则（.gitignore 已配）

`_sources/`、`_external/`、`.curator_backups/`、`.hub/`、`**/node_modules/`、`**/.venv/`、`**/__pycache__/`——全量 1.1G 精简到 55MiB，技能正文一个不丢。

## 脱敏机制（clean filter）

`.gitattributes` 对 md/py/sh/html 启用 `filter=sanitize-creds`；`.git-sanitize.sh` 把 `${ROBOT_CREDS}` 等机队凭据替换为 `${ROBOT_CREDS}` 占位。**本地文件保持明文不影响使用**，只有 git 对象里是占位。

## 坑

- **filter 配置必须写绝对路径**（`git config filter.sanitize-creds.clean "$PWD/.git-sanitize.sh"`）——相对路径 fork 失败，add 时静默不过滤，凭据明文入库。
- **验证必须用 `git grep --cached`**：clean filter 在 add 时生效，普通 grep 看工作区永远是明文，验证不到 git 里存了什么。
- **分清真泄露与占位符**：`sk-Ue1...wYuG`、`ghp_xx...xxxx` 这类带省略号的是文档示例，不算泄露；`.gitattributes` 里的过滤规则字符串命中也不算。
- **推送凭据缺位时停在本地 commit**：没有 PAT/gh CLI 就明说"本地已 commit，等凭据"，不要用猜测的凭据试。
- **grep 扫敏感时排除 vendor 目录**：node_modules/.venv 里的库源码（requests/websockets 的 auth 模块）天然含 password 字样，全部命中属噪音——.gitignore 已排除，`git grep --cached` 不会踩到。
