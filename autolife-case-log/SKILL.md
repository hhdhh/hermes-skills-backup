---
name: autolife-case-log
version: 1.0.0
description: AutoLife 机器人排障案例归档：每解决一个问题，写成飞书文档存入"机器人排障案例库"云空间文件夹（供运营同事阅读 + 灰灰知识库）。当主人说"记录这个案例"、"归档到案例库"，或排障修复验证完成后的收尾归档时使用。
---

# AutoLife 排障案例归档（飞书云文档）

> 2026-09-13 主人要求：每次遇到的问题 + 解决过程详细记录成飞书文档，放云文档，供运营同事看 + 作灰灰知识库。
> 案例库位置：飞书云空间文件夹「机器人排障案例库」`VnMXfk0rTl4gBndGKwzcsoqjnof`
> 索引文档：`JgYwdXtTkouDAmxrTLFcQJPcnWc`（https://autolife.feishu.cn/docx/JgYwdXtTkouDAmxrTLFcQJPcnWc）

## 触发时机

- 排障完成并验证通过后（修复闭环的最后一步）
- 主人明确说"记录/归档这个案例"
- 发现有价值的新坑/新方法（即使没修，也记"待办"）

## 标准流程

```bash
FOLDER=VnMXfk0rTl4gBndGKwzcsoqjnof
INDEX=JgYwdXtTkouDAmxrTLFcQJPcnWc

# 1. 建骨架（标题 + callout 结论 + 六章 h1）
lark-cli docs +create --api-version v2 --parent-token $FOLDER \
  --content '<title>案例NNN · 症状 —— 根因</title>
  <callout emoji="✅" background-color="light-green" border-color="green"><p>一句话结论…</p></callout>
  <h1>1. 故障现象</h1><h1>2. 排查过程</h1><h1>3. 根因</h1>
  <h1>4. 修复方案</h1><h1>5. 验证</h1><h1>6. 复用指南</h1>' --as user
# 2. 拿各章 block_id: docs +fetch --detail with-ids，grep '<h1 id='
# 3. 逐章 block_insert_after 填正文（每次一章，避免参数超限）
# 4. 更新索引文档的案例列表表格（str_replace 或加行）
```

## 文档规范（同索引文档里写的，双处一致）

1. 标题：`案例NNN · 症状关键词 —— 根因短语`（NNN 三位递增）
2. 固定六章：故障现象 / 排查过程 / 根因 / 修复方案 / 验证 / 复用指南
3. 开头 callout：一句话结论，让同事 30 秒判断"是不是我遇到的问题"
4. 排查过程写**真实命令 + 输出关键行**，别人能照着走
5. 表格放设备/日期/状态等元信息；流程/架构用 mermaid 画板
6. **敏感信息不入文**：SSH 密码、密钥、内网拓扑细节（IP 可写，密码绝不写）
7. 结尾注明：记录人 + 日期 + 内部技能库指引

## 已知坑（真实踩过）

- **画板和文字混在一次 update 里会静默丢失**：`block_insert_after` 带 `<whiteboard>` + 其他 block 时，返回 ok 但画板没进去。**画板单独一次调用插**。
- 长内容分章插入，一次 `--content` 别超过几 KB
- 安全扫描会对 emoji 变体选择符/Unicode 形近字符报警，属误报， approve 即可
- `--detail with-ids` 的 id 在 `<h1 id="...">` 属性里，正则提取

## 与其它技能衔接

- 案例内容来源：`autolife-doctor-operations` / `autolife-remote-repair` 等排障技能的修复记录
- 写文档操作细节：`lark-doc` / `lark-drive` 技能（本技能只定义流程规范）
- 修复完 → 先归档案例 → 再更新对应排障技能（两个动作连着做）
