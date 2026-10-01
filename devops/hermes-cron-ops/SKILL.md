---
name: hermes-cron-ops
version: 1.0.0
author: 运营助手
license: MIT
description: Hermes cron 定时任务创建与排障。Use when 建改 cron job 或定时通知未发出。
tags: [cron, scheduling, feishu]
related_skills: [autolife-fae-scheduler]
---

# Hermes Cron 定时任务运维

## When to Use

- 新建/修改 hermes cron 定时任务（定时通知、巡检、提醒）
- 排查「定时消息没发」「cron 显示 error」「drift_skip」
- 查存量 job 定义（收件人、prompt、排程）

## 创建（正确语法）

```bash
hermes cron create --name <名> --deliver feishu \
  --provider custom:sub2apiooo --model glm-5.3 \
  '0 17 * * 6' '<自包含 prompt>'
```

- 子命令是 `cron create`（`cron add` 不存在）；schedule 和 prompt 都是位置参数。
- `--provider/--model` **必写**：未 pin 的 job 在全局 provider 变更时被 drift_skip 安全机制静默跳过（表现：cron 照常触发、无报错、消息一条没发，输出文件里写 `No inference call was made`）。切过 provider 后要回头检查存量 job。

## 排查「定时消息没发」

1. `hermes cron list` 看 job 的 Last run / last_status（error 说明触发过但失败）。
2. 输出归档：`~/.hermes/cron/output/<job_id>/<时间>.md`——失败原因写在这里，`grep -A3 '## Error'`。
3. drift_skip 特征：worker 正常启动、几十秒后结束、无 inference、无发送日志。修法 `hermes cron edit <id> --provider custom:sub2apiooo --model glm-5.3`。

## 发信链路（排班通知类 job 通用）

飞书 app cli_aaf0558a8fb81cbb 的 tenant_access_token（POST /open-apis/auth/v3/tenant_access_token/internal，secret 在机密配置）→ 逐个 open_id 发私信。收件人 12 人 open_id 清单存在各 job 的 prompt 里（hermes cron show <id> 或直读 ~/.hermes/cron/jobs.json）。排班数据从 http://100.98.150.220:8000/api/login 拿 JWT 后调 /api/overview?from=&to=（详见 skill: autolife-fae-scheduler）。

## 坑

- 当天创建的 job 若已过当天触发时刻则不补跑，需当场向管理员确认是否手动补发。
- jobs.json 直读可拿全部定义（含 prompt/收件人）；show 命令有时无输出。
- cron job 的 prompt 必须自包含（收件人、token 获取方式、消息格式全写进去）——worker 是全新会话，不继承主会话上下文。