---
name: agent-reach
description: 需要从互联网「拿内容」时使用：调研/全网调研/搜索/查资料/research，或读取 小红书(xhs)·推特(Twitter/X)·B站(bilibili)·Reddit·V2EX·雪球(股票)·LinkedIn(领英/招聘)·YouTube·小宇宙播客·GitHub·RSS·任意网页/链接。多后端平台先跑 `agent-reach doctor --json` 看 active_backend 再调命令。本技能只负责获取内容，写报告/分析/翻译等加工不在此列。
---
# Agent Reach — 互联网能力路由器

需要从互联网「拿内容」时用本技能（搜索/调研/读社媒/读视频字幕/读网页）。
**本技能只负责获取内容**；写报告、分析、翻译等加工不在此列。
**绝不自己开浏览器或瞎编命令** —— 严格按下面的路由走。

## 铁律
1. **先体检再动手**：多后端平台（小红书 / Reddit / B站 / 推特）动手前先跑
   `agent-reach doctor --json`，看目标平台的 `active_backend` 字段，再用对应命令组。
2. **命令 not found**（`agent-reach` / `mcporter` / `opencli` / `yt-dlp` / `bili` / `gh` 缺失）
   = 联网能力没装好。告诉用户「需要先安装 Agent Reach 联网能力」，在允许联网时可自行执行：
   `pipx install https://github.com/Panniantong/agent-reach/archive/main.zip && agent-reach install --env=auto`
   （pipx 不可用退回 `pip install ...`）。装系统包前先征得用户同意。
3. 失败别瞎试，按平台说明的重试链处理；拿不到就如实说，**绝不编造内容**。

## 零配置即用（无需登录 / 无需 Key）
```bash
# 全网搜索：在线 AI 已内置 exa 工具，直接调 web_search_exa；其它 agent 用下面这条
mcporter call 'exa.web_search_exa(query: "关键词", numResults: 5)'
# 任意网页正文（去广告/标签，干净 markdown）
curl -s "https://r.jina.ai/<URL>"
# GitHub 仓库 / 代码搜索
gh search repos "关键词" --sort stars --limit 10
# YouTube 字幕（注意：B站不要用 yt-dlp）
yt-dlp --write-sub --skip-download -o "/tmp/%(id)s" "<URL>"
# B站搜索 / 视频详情（bili-cli，无需登录）
bili search "关键词" --type video -n 5
# V2EX 热门
curl -s "https://www.v2ex.com/api/topics/hot.json" -H "User-Agent: agent-reach/1.0"
```

## 需要登录态 / 配置才解锁
小红书、推特(搜索/时间线/长文)、Reddit(搜索/读帖)、LinkedIn、雪球、小宇宙播客等：
- 先 `agent-reach doctor --json` 看 `active_backend`；没配的告诉用户「帮我配 XXX」。
- Cookie 类平台统一用浏览器 **Cookie-Editor** 导出 Cookie 发给 agent（别走扫码）。
- **小红书 xsec_token**：不能裸 note_id 直读，先 search/feed 拿完整 URL 再读。
- 各平台详细命令：装好后见 `agent-reach` 的 references（social / web / video / dev / career / search）。

## 调研类任务
多平台并行收集再汇总：exa 搜全网 + 推特/Reddit 看讨论 + 小红书/B站看中文场景，
**每条结论标来源**，拿不到的如实说明。