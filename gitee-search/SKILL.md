---
name: gitee-search
description: "Use when 要在 Gitee 搜仓库/代码/模型，或 Gitee 搜索返回空要换通道。"
---

# Gitee 仓库搜索

Gitee 站内搜索已迁到 `so.gitee.com` 的 SPA（Indexea 引擎）：`gitee.com/search?q=` 会 301 过去，curl 只能拿到空壳 HTML；`gitee.com/api/v5/search/repositories` 匿名调用一律返回 `[]`。可用通道是 SPA 背后的 widget 搜索 API。

## 搜索（匿名可用，主力通道）

```bash
curl -s -A "Mozilla/5.0" -H "Referer: https://so.gitee.com/" \
  "https://so.gitee.com/v1/search/widget/wong1slagnlmzwvsu5ya?q=<关键词>&from=0&size=20"
```

- 响应是 ES 风格 JSON：`hits.hits[].fields` 内 `title`/`url`/`description`/`langs`/`count.star`/`last_push_at`/`license`，每个都是单元素数组
- `from=` 翻页；`hits.total.value` 带 `relation:"gte"` 时是下界
- 仓库真实路径取 `url` 字段（`gitee.com/idroid23/open-jev`），不要用 `title` 里的人类可读名（`idroid/openJev`）——后者进 API 会 404
- 热词重名多（用户名撞车），靠 `description`/`langs`/`last_push_at` 过滤噪音

## widget ID 失效时：从 JS 包重新挖（对任何搜索 SPA 通用）

widget ID 硬编码在前端，站点改版会变。挖法：

1. `curl -s https://so.gitee.com/` 从 HTML 里拿 `/assets/index-*.js` 主包（~1MB）
2. `grep -oE 'path:"/search[^"]*"' bundle.js` 确认端点形状（`/search/widget/{widget}`）
3. 找成对硬编码常量：widget ID（20 位左右小写字母数字串）与 `api:"https://so.gitee.com/v1"` 成对出现即目标
4. 探测响应判错：404 "组件 #N 不存在" = widget ID 错；401 = 需 token，回第 2 步

## 仓库详情与文件（匿名可用）

```bash
# 详情 + default_branch（用 url 路径名）
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}"
# 文件树
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}/git/trees/{branch}"
# 原始文件（master/main 都试；失败返回 [session-xxx] Repository or file not found）
curl -s "https://gitee.com/{owner}/{repo}/raw/{branch}/README.md"
```

## 坑

- **搜索 API 返回 `[]` ≠ 没有结果**——匿名就是不给结果（要 token）。判定法：先搜一个必然命中的词（如 yolo），同样空则说明是鉴权问题，换 widget 通道，别下"没找到"的结论
- web_extract / 浏览器抓 `so.gitee.com` 会超时或空壳（SPA 无 SSR），别重试，直接走 API
- browser_exec 报 "could not read the 'chrome' profile's login data" = 本机 chrome 占用了 real profile；浏览器起不来时 curl 通道不受影响，优先 curl
