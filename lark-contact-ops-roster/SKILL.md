---
name: lark-contact-ops-roster
description: Use when 用户说「现在可以读取运营部每个成员的信息了」或需要按部门批量取同事 open_id 以便发消息/...
version: 0.1.0
---

# 部门成员拉取（原生 OpenAPI）

> 完整描述：拉取运营部/FAE 团队全员名单（部门→成员→open_id 映射）。Use when 用户说「现在可以读取运营部每个成员的信息了」或需要按部门批量取同事 open_id 以便发消息/排日程。

lark-cli contact 只做单人搜/查；按部门列成员走原生 API：

```bash
# 1. 部门列表（fetch_child 拿子部门）
curl "https://open.feishu.cn/open-apis/contact/v3/departments?department_id=0&page_size=50&fetch_child=true" \
  -H "Authorization: Bearer $TENANT_TOKEN"
# 2. 按部门列成员
curl "https://open.feishu.cn/open-apis/contact/v3/users/find_by_department?department_id=od-xxx&page_size=50&department_id_type=open_department_id" \
  -H "Authorization: Bearer $TENANT_TOKEN"
```

坑：
- `departments/find_by_department` 返回空 items 时改用 `departments?department_id=0`。
- `users/find_by_department` 必须带 `department_id_type=open_department_id`，否则 400。
- `job_title` 常为空（后台没填），不要据此判断职位。
- 成员遍历要用 open_department_id（od- 前缀），不是 department_id（如 ZD004）。

拉完把 name→open_id 映射落盘（如 robots.json 同级），供后续发消息/排日程复用。
