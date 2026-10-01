---
name: hermes-git-install-upgrade
description: "Use when Ubuntu git 安装的 hermes 升级——tag 切换+依赖同步+doctor 迁移。"
---

# Hermes git 安装升级（Ubuntu / systemd）

适用：`hermes --version` 显示 `Install method: git` 且网关是 systemd user service（`hermes-gateway.service`）。这与 pip/conda 安装不同——升级走 **git fetch + checkout 稳定 tag**，不 pip install。

> pip 安装形态的技能（macOS launchd + miniconda 路径）不要照搬命令；但备份/体检/进程层决策原则通用。

## 流程（7 步）

### 1. 基线体检（记录 6 项）
```bash
hermes --version | head -2
systemctl --user show hermes-gateway.service -p ActiveEnterTimestamp -p MemoryCurrent
ls ~/.hermes/skills/ | wc -l
curl -s -o /dev/null -w '%{http_code}' -m 3 http://localhost:8648/
cd ~/.hermes/hermes-agent && git log -1 --format='%h %s' && git status --short
```

### 2. 备份
```bash
mkdir -p ~/.hermes/backups/pre-<NEWVER>-<date>/
cp ~/.hermes/config.yaml ~/.hermes/backups/pre-<NEWVER>-<date>/config.yaml.bak
cp ~/.hermes/.env ~/.hermes/backups/pre-<NEWVER>-<date>/.env.bak
cd ~/.hermes/hermes-agent
git stash push -m "pre-upgrade-<date>"      # 有本地改动时
git rev-parse HEAD > ~/.hermes/backups/pre-<NEWVER>-<date>/old_head.txt
```

### 3. 查最新版本
PyPI 的版本滞后于 GitHub releases——以 GitHub releases 页为准（newreleases.io 可查 tag 列表）。`git fetch origin` 对 github.com 可能极慢（2 分钟+超时），**放 background 跑**，别前台死等。

```bash
timeout 240 git fetch origin --tags   # background
git tag --sort=-creatordate | head -4
git log -1 --format='%h %s (%cr)' v<TARGET_TAG>
```

### 4. 切 tag + 同步依赖
```bash
git checkout v<TARGET_TAG>
.venv/bin/pip install -e ".[all]" -q --no-build-isolation   # 依赖同步
hermes --version | head -1    # 应显示新版本
```

### 5. doctor 迁移
新版本可能带 config schema 迁移（`Config version outdated (vN → vM)`）：
```bash
hermes doctor --fix
grep _config_version ~/.hermes/config.yaml   # 应为新版本号
timeout 120 包住——doctor 偶尔卡在网络检查
```

### 6. 升级后体检（对比第 1 步 6 项）
skills 数不丢、版本号正确、config 版本迁移完成、`Version files consistent`。

### 7. 网关重启（进程层）
跑着的网关仍是旧 mmap 库，重启才切新代码。先判自己在不在网关进程树内：`systemctl --user show hermes-gateway.service -p MainPID --value` 对照 `pstree -sp $$`——
- **不在树内**（如从 hermes-studio 桌面会话跑）：可直接 `systemctl --user restart hermes-gateway.service`；重启属外部操作，先向用户确认一声再执行。
- **在树内**（安全机制拦自杀）：让用户跑 `~/restart-hermes-gateway.sh`，或用户远程授权时走 cron 通道（见 `autolife-gateway-restart-from-inside` 技能）。

## 坑

- **pip 安装的 `hermes update --check` 在 git 安装上超时**（它内部同样 fetch github）；直接 git fetch 后台跑更快。
- **GitHub 代理选型（2026-10 实测）**：直连 fetch 240s 超时；ghfast.top 对 `ls-remote` 返回 403（证书/风控变了，别再用）；**gh-proxy.com 可用**（ghproxy.cc 证书过期、gitclone.com 502）。先 `timeout 20 git ls-remote https://gh-proxy.com/https://github.com/<owner>/<repo>.git HEAD` 探活，再定向 fetch 单 tag：`git fetch https://gh-proxy.com/https://github.com/<owner>/<repo>.git tag <TAG> --no-tags`（比 --tags 快得多）。
- checkout tag 后 `pip install -e .` 别忘——只切代码不同步依赖会 import 报错。
- doctor --fix 前确认 config 已备份（第 2 步）；迁移是单向的。
- npm vulnerabilities 提示是老毛病，不阻塞升级。
- **重启验证只看新时间戳之后**：旧进程下线时 journal 里的 Lark `ConnectionClosedOK / receive message loop exit` 是正常断连噪音，别误诊为升级失败；验证 = 新 MainPID + 启动横幅后 `connected to wss` + WebUI 200，且重启时间戳之后无新增 error。
- 回滚：`git checkout <old_head> && .venv/bin/pip install -e . -q && 重启网关`（old_head 存在备份目录）。
- **改 provider/model 后检查 cron job**：未 pin 的 job 会 drift_skip 静默不跑——`hermes cron list` 看 last_status，error drift_skip 的用 `hermes cron edit <id> --provider <新> --model <新>` 重新 pin。错误详情在 `~/.hermes/cron/output/<job_id>/` 的 md，gateway 日志无痕。