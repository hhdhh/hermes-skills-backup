# DEEP_LINKS — UUMit Agent v2.7.0

深链用于把用户带到 UUMit Web 页面完成浏览、授权、确认、充值等交互。API 调用仍通过 `scripts/rest_request.js`。

## 1. URL 解析优先级

Web URL 解析顺序：

```text
UUMIT_WEB_URL > memory/uumit-config.json.web_url > memory/uumit-config.json.app_url > https://m.uumit.com
```

API URL 解析顺序：

```text
UUMIT_BASE_URL > memory/uumit-config.json.base_url > https://api.uumit.com
```

## 2. 常用页面

| 场景 | 路径 |
|---|---|
| 首页 | `/` |
| 钱包 | `/wallet` |
| 订单 | `/orders` |
| 知识商店 | `/marketplace` |
| 数据广场 | `/data-marketplace` |
| Playbooks | `/playbooks` |
| 任务市场 | `/tasks` |
| 时间市场 | `/time-market` |
| 能力上架 | `/creator/capabilities` |
| 外部 Agent | `/agents` |
| 授权帮助 | `/auth/device` |
| 社交大厅（签到/翻牌/时间胶囊） | `/hall` |

## 3. 何时使用深链

- 用户需要充值、提现、确认订单；
- 需要浏览资产详情、报告、产物；
- 需要人工完成授权、绑定、KYC 或敏感设置；
- 脚本返回 `confirmation required` 且需要用户在页面确认。

## 4. 禁止事项

- 不把 API Key、token、订单敏感字段拼进 URL；
- 不自动打开会执行付费、发布、授权的链接；
- 不把用户私有数据放入 query 参数。
