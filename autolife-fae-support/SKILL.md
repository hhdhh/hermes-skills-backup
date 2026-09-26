---
name: autolife-fae-support
description: Use when the task involves autolife fae support.
---


# AutoLife FAE 支持：知识库问答 + 现场排障

Use when 主人问智动未来/AutoLife 公司、产品、机型、手册、太空舱业务问题，或排查已部署机器人现场故障（如下发 quest 不抓取、服务异常）。核心原则：**先检索本地知识库再回答**；排障按业务链路分层定位，不凭空猜。

## 问答流程（产品/手册/流程类问题）

1. **检索入口**（都在 `/home/kk/.hermes/knowledge/`）：
   - `wiki/manuals/autolife-s2/00-索引.md` — 三份手册摘要索引（装机 67 页 / VR 36 页 / S2 使用手册 42 页），30 秒速查表在这里
   - `wiki/robots/` — W1 等机型入口
   - `feishu-study/reviews/<token>.md` — 飞书文档逐文档精读（业务逻辑、疑点、版本冲突已提炼）
   - `feishu-study/raw/<token>.json` — 原文 XML 快照（正文在 `data.document.content`）
   - `feishu-study/structured-reviews/bitable-*.md` — 多维表格结构审阅
2. **找文档标题定 token**：`grep '<title' feishu-study/reading-round*/*.txt`，或查 `coverage.json` 的 `"title"` 字段；按标题选中后读对应 reviews/raw。
3. **回答规范**：标注证据层级（生效手册 / 精读推断 / 历史问题清单记录）；手册参数与实机有出入时以实机实测为准并注明。

## 排障流程（已部署机器人不执行业务）

太空舱下单→抓取链路的分层排查清单见 `references/capsule-order-chain.md`。通用顺序：先确认任务有没有下发到机器人（服务器 quest / 订单映射），再查机器人侧六个服务，再查 AI 识别与 dataset 参数——从链路上游往下游切，不跳步。

## 坑

- **精读 review 对命令脱敏**（正文写"完整行序解释见上方同ID"）——要逐字命令必须去 `raw/<token>.json` 提取 pre 块，不要凭 review 复述命令。
- **bitable records 是位置数组**：`structured/bitable/<token>/<tbl>-records-*.json` 的行在 `data.data` 里是无键数组，必须与同名 `-fields-*.json` 的 `data.fields` 按顺序 zip；假设 `items`/dict 结构会得到 0 行。
- **两代流程不能混拼**：老教程（robot_v2_0、商品参数在 AI dataset 的 config.xml）与新 Flow 指南（dataset/config.json、服务器端 quest XML）是不同版本体系——排障前先确认机型与软件版本，按对应一代文档走。
- **验证命令会动真机**：test_pub.py 的 order、empty_orderlist.py 会驱动整机运动或真实下单——输出时必须带清场与急停提示（test_pub 菜单 2=stop，1=go 回前台）。
