---
name: autolife-company-knowledge
description: Use when 主人问智动未来/AutoLife 公司产品、机器人规格、业务场景 — 按本地图谱检索 knowl...
category: work
---

# AutoLife 公司产品问答 · 本机检索图谱

> 完整描述：Use when 主人问智动未来/AutoLife 公司产品、机器人规格、业务场景 — 按本地图谱检索 knowledge 树作答。

适用：FAE 场景下主人问公司产品、机型规格、手册内容、装机/VR/标定流程、业务落地场景。本技能只解决「去哪找」——通用「先搜索再读、不整库载入」规则见 KNOWLEDGE.md，不在此重复。

## 检索顺序（规格/手册类问题）

1. `~/.hermes/knowledge/wiki/manuals/autolife-s2/00-索引.md` — S2 三手册总索引 + 30 秒速查（网络关键值、核心规格、VR 组合键、服务管理命令）。多数产品问题到此为止。
2. 需要细节再下钻同目录：规格/模块 → `03-Autolife-S2使用手册-摘要.md`；装机/网络 → `01-…装机…摘要.md` 与 `04-…详细解读.md`；VR 遥操 → `02-…VR…摘要.md`。装机手册的全量命令级解析另见 `wiki/robot-install-manual-deep-analysis-*.md`。
3. W1 人形机 → `~/.hermes/knowledge/wiki/robots/W1-robot.md`（入口页，链到操作 / ROS2 接口 / 故障排查子页）。
4. S1 真机 → `wiki/robot-autolife-s1-263-2026-08-07.md`（部署审计）+ 同前缀 runbook / pdf-full-analysis。
5. 业务/场景类（直营门店、XR 赛事、展会演示、公司制度）→ `~/.hermes/knowledge/feishu-study/`：`reviews/*.md` 是整理过的评审，`reading-round6/` 是飞书原文。

规格速查一页纸见 `references/product-factbook.md`（S2/S1/W1 + 配套生态 + 场景，含出处）；对外引用数字前回源文件核对版本。

## 坑

- feishu-study 的 `reading-round6/*.json` 顶层 title 字段为空——文档标题在同名 `.txt` 的 `<title id=…>` 标签里。枚举文档列表用 `grep -o '<title[^>]*>[^<]*</title>' reading-round6/*.txt`，不要解析 JSON 找标题。
- 短 token（S1/S2/W1）会撞进飞书块 ID 片段（如 `doxcnS2…`），在原始 dump 里全文 grep 全是噪声——产品事实优先用 wiki 精选摘要；原始 dump 只用来查场景/制度原文。
- KNOWLEDGE.md 和 `wiki/index.md` 是通用入口；产品手册精华直接走 `wiki/manuals/autolife-s2/`，省两层跳转。

## 作答

- 规格数字（DoF / 续航 / 速度 / FOV / 端口 / 键位）必须来自 factbook 或源手册文件，不凭记忆补。
- 「介绍一下产品」类问题用「机型分节 + 配套生态 + 落地场景」结构，末尾留可深挖的分叉（装机 / VR / 标定 / 排障）。
