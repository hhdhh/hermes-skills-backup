---
name: autolife-fae-scheduler
description: 智动未来 FAE 排班系统 API 接入与查询（机队状态/人员/需求统计）。查询 API 优先不开浏览器，写操作才开。Use when 用户提排班系统、FAE 资源、需求审批、机队状态分布，或贴 100.98.150.220:8000 链接。
---


# FAE 排班系统接入（Autolife FAE 团队资源排班系统）

> 完整描述："智动未来 FAE 排班系统 API 接入与查询（机队状态/人员/需求统计）。Use when 用户提排班系统、FAE 资源、需求审批、机队状态分布，或贴 100.98.150.220:8000 链接。API 优先不开浏览器；服务仅 HTTP；admin 是 Web 账号不是系统账号。"

> 跑在用户自己服务器上的 Web 服务（REST API + React 前端）。查询类需求 **API 优先，别开浏览器**；浏览器只在改排班等写操作时用。

## 接入要点

| 项 | 值 |
|---|---|
| 主地址 | `http://100.98.150.220:8000/`（NetBird IP；**必须带 `http://` 前缀**） |
| 协议 | 仅 HTTP，服务器无 TLS。https 报 wrong version number——浏览器把 http 自动升级成 https 就是"打不开"的根因 |
| 健康检查 | `GET /api/health` 免认证：`{"ok":true,"uptime":...}` |
| Web 管理员 | `admin`（密码向用户要；**不写入任何技能/文档**——skills 目录会推 GitHub 备份） |
| 服务器本体 | jkang-150-220 那台 Windows 机（同机跑 Ekko Studio 8648 / Hermes Dashboard 9119）；SSH 用户 `jk`。**Web admin ≠ 系统账号**：拿 ubuntu/机队凭据 SSH 必失败，Authentication failed ≠ 服务器故障 |

## 查询流程（已验证）

```bash
# 1. 登录拿 JWT（返回 {token, user}，token ~7 天有效）
TOKEN=$(curl -sS -m 10 -X POST http://100.98.150.220:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<向用户要>"}' \
  | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['token'])")

# 2. 查数据（Bearer 认证）
curl -sS -H "Authorization: Bearer $TOKEN" http://100.98.150.220:8000/api/robots   # 机队
curl -sS -H "Authorization: Bearer $TOKEN" http://100.98.150.220:8000/api/users    # 人员
curl -sS -H "Authorization: Bearer $TOKEN" http://100.98.150.220:8000/api/stats    # 需求/展会/项目统计
curl -sS -H "Authorization: Bearer $TOKEN" http://100.98.150.220:8000/api/me       # 当前用户
```

## 数据模型要点

- **robots**：每台有机号（name/number）+ `status`（正常/测试中/轻微问题/报废…）。**只有状态，没有 IP 和在线信息**——找 IP/在线状态走 `autolife-find-robot`（NetBird / DNS PTR），别指望排班系统。
- **users**：全员 `role=marketing`（含 admin 自己）是数据遗留，权限实际按账号判定；可提醒用户让后端修数据一致性。
- **stats**：`demandStats`（draft/pending/returned/rejected/approved）+ `entityStats`（exhibition/activity/project）。
- **404 端点别再撞**：`/api/schedules`、`/api/projects`、`/api/dashboard`、`/api/exhibitions`、`/api/activities`——排班明细在前端页面里，不在这些 API 路径。

## 浏览器操作（写操作才开）

🔴 **CHECKPOINT**：改排班等写操作前，先把改动内容截图发用户确认，回复确认后才执行提交；改完再截图回传验证。

登录表单是 React 受控组件：直接赋 value 不触发 onChange。用原生 setter 注入再 dispatchEvent（HTMLInputElement.prototype 的 value setter → input 事件）。改完截图给用户确认。

## 已知坑

- 同事说"打不开" → 先 `curl http://...` 验证 200；通的话大概率是浏览器 https 自动升级，让对方带 `http://` 前缀或用无痕窗口。
- 服务器 LAN IP 随 DHCP 漂移，NetBird IP 稳定；LAN 直连更快但用前要实测。
