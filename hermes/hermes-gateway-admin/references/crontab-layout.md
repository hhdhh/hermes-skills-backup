# Hermes 化身 crontab layout

> 2026-07-03 主人立 · 7/4 灰灰查清。
> Hermes 化身走**系统 crontab**（不是 `hermes cron` 内置 scheduler）。

## 现状

```bash
$ crontab -l | grep -i hermes
*/30 * * * * /Users/kk/.hermes/scripts/evolution_watchdog.sh >> /Users/kk/.openclaw/workspace/evolution/watchdog_logs/cron.log 2>&1
55 23 * * 0 /usr/bin/python3 /Users/kk/.openclaw/workspace/evolution/weekly_report.py >> /Users/kk/.openclaw/workspace/evolution/weekly_reports/cron.log 2>&1
50 23 * * * /Users/kk/.openclaw/workspace/evolution/master_orchestrator.sh daily >> /Users/kk/.openclaw/workspace/evolution/master_orchestrator_cron.log 2>&1
*/30 * * * * /Users/kk/.hermes/scripts/hermes-heartbeat.sh
15,45 * * * * /Users/kk/.hermes/scripts/hermes-learning-loop.sh
0 */6 * * * /Users/kk/.openclaw/bin/sync-hermes-skills-all.sh > /dev/null 2>&1
0 9 * * * /Users/kk/.hermes/scripts/version-watchdog.sh >> /Users/kk/.hermes/logs/version-watchdog-cron.log 2>&1
```

## 每个 cron 做什么

| Cron | 频率 | 脚本 | 作用 |
|------|------|------|------|
| `evolution_watchdog.sh` | 每 30 min | 主体 | 进化引擎健康检查 |
| `weekly_report.py` | 周日 23:55 | 主体 | 周报 |
| `master_orchestrator.sh daily` | 每天 23:50 | 主体 | 进化引擎主调度 |
| `hermes-heartbeat.sh` | 每 30 min | **Hermes** | 化身心跳（自己加） |
| `hermes-learning-loop.sh` | 每 15/45 分 | **Hermes** | 学习循环（自己加） |
| `sync-hermes-skills-all.sh` | 每 6 小时 | 主体→Hermes | skills 全量同步 |
| `version-watchdog.sh` | 每天 9 点 | **Hermes**（7/4 加） | 版本监控 |

## 为什么用系统 crontab 而不是 `hermes cron`

`hermes cron` 是 Hermes 框架自带的 scheduler，**但 7/4 实测 `hermes cron list` 显示 0 jobs**。主人用 `crontab -e` 直接配 — 更简单、更可控、**不需要 gateway 进程活着**（`hermes cron` 要求对应 profile gateway 跑着）。

**两层 cron 都有的话会不会重复跑？** — 看具体脚本设计。`hermes-heartbeat.sh` / `hermes-learning-loop.sh` 自己有 state 文件（`ticker_*`）防重入。

## 改动 crontab 的安全档

1. 改前 `crontab -l > /tmp/crontab.bak` 备份
2. 改后 `crontab /tmp/crontab.bak` 应用
3. 验证 `crontab -l | tail -5`
4. **不直接 `crontab -e`** — agent 改不动 vim，**用文件流式**：`cat existing + echo new | crontab -`

## 脚本在 cron 里调用 `systemctl --user` 的铁律（Ubuntu）

cron 环境没有 `DBUS_SESSION_BUS_ADDRESS` / `XDG_RUNTIME_DIR`，`systemctl --user` 会直接报 `Failed to connect to user scope bus`——健康巡检/看门狗类脚本因此把活着的 gateway 误判为挂掉，进入「每 5 分钟告警 DM + restart」风暴。**任何 cron 脚本要用 systemctl --user，必须显式注入**：

```python
SYSTEMCTL_ENV = {
    "PATH": "/usr/bin:/bin:/usr/local/bin",
    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
    "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{os.getuid()}/bus",
}
subprocess.run(["systemctl", "--user", "is-active", "hermes-gateway.service"],
               capture_output=True, text=True, env=SYSTEMCTL_ENV)
```

改完用 `env -i HOME=$HOME python3 <script>` 模拟 cron 干净环境验证一遍，确认不产生误报告警再交给 cron。

## 不要做

- ❌ `hermes cron create` 在 gateway 进程死了的情况下 — 不会跑
- ❌ 配 `hermes cron` 和系统 crontab **同一脚本**两份 — 重复跑
- ❌ 改 `~/Library/LaunchAgents/*.plist` 用 sed — 见 `launchd-bootstrap-einval.md`
