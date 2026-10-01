---
name: ops-assistant-doc-authoring
description: Use when 要在飞书云空间建文档给运营同事看，或主人要求“整理成飞书文档”。
---

# 运营助手飞书文档创作规范

> 完整描述：运营助手身份下写飞书对外文档（检修记录/使用指南/技能详述/周报）的规范：署名、建库、回读验证、markdown 导入的坑。Use when 要在飞书云空间建文档给运营同事看，或主人要求“整理成飞书文档”。

## 身份规则（主人明确指示）

飞书消息与飞书文档一律以“**运营助手**”自称，不出现灰灰/Hermes/Huihui/化身等内部名称。文档“记录人”写“运营助手”，文末落款“本文档由运营助手自动生成”。这是对外身份，内部技能与记忆不受影响。

## 现有对外文档库

- 「机器人故障记录库（FAE·运营助手维护）」folder_token `M7CrfNeZrl26eAdbJkrcCEREnCe`：检修记录（一灾一篇，六段：现象/排查/修复/验证/经验/遗留）
- 排障案例库 folder `VnMXfk0rTl4gBndGKwzcsoqjnof` + 索引 `JgYwdXtTkouDAmxrTLFcQJPcnWc`：可复用案例长文（详见 autolife-case-log 技能）
- 使用指南、技能详述等运营文档：放在故障记录库同文件夹或 my_library

## 流程（markdown 一次性建文）

1. 先写本地 `/tmp/<slug>.md`（write_file），结构完整可读。
2. `lark-cli docs +create --title "<标题>" --doc-format markdown --content @/tmp/<slug>.md --parent-token <folder>`（放个人空间用 `--parent-position my_library`）。
3. **回读验证**：`lark-cli docs +fetch --doc <document_id>` 确认各章关键词命中——创建返回 ok 不代表正文写入成功。
4. 改名/改署名用 `docs +update --command str_replace --pattern <旧> --content <新>`，逐处替换后同样回读。

## 坑

- **lark-cli 被 TLS reset 时的替代通路（2026-09-28 实测）**：lark-cli 整体挂掉（token 刷新都 reset）时，用 curl + user UAT 走 upload_all(.md)→import_tasks(转docx)→raw_content(回读) 全链，详见 skill: lark-cli-go-tls-reset-bypass「文档创建的同款绕过」。注意 bot TAT 缺 drive 上传 scope（403 forbidden），必须 user 身份；UAT 过期用 refresh token + client_id + client_secret 刷。
- **markdown import 保真好**：12 章+3附录+37 锚点全命中；代码块/表格/标题层级保真；但 import 转换不是实时的（轮询 job_status，~10s）。
- **`+fetch` 无 `--url` 标志**：文档定位用 `--doc <token-or-url>`；位置参数也不支持。+create 的 `--parent-token` 与 `--parent-position` 互斥。
- **markdown 导入的表格/标题层级基本保真**，但 callout/画板等富块需 XML 格式或事后插入；检修记录级别的文档用 markdown 就够。
- **建库文件夹名含内部名称时**：飞书 API 重命名文件夹器 PATCH `/open-apis/drive/v1/files/<token>?type=folder` 报 981002 params error 是接口限制；不必硬重试——新文档用新署名即可，folder_token 不变不影响使用。
- **敏感信息不入文**：SSH 密码、API key 绝不写进对外文档；机号、IP、命令可以写。
