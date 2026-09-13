---
name: uumit-publisher
description: "UUMit 发布扩展。当用户要上传文件、批量发布或批量上架时使用：①upload 上传单个文件（multipart）返回可用于上架的文件 URL ②batch-publish 枚举我的数字资产并批量发布（草稿/已分析 → 已发布）。本扩展依赖 uumit-agent 基座：批量发布等纯 JSON 调用经基座安全闸门；单文件上传因 multipart 不走基座 JSON 通道，由本扩展复用基座凭证受控直传。"
version: 2.7.0
user-invocable: true
homepage: https://m.uumit.com
requires-base: "uumit-agent >=2.0.0"
metadata: {"agent_skill":{"key":"uumit-publisher","aliases":["上传","上传文件","批量发布","批量上架","发布资产","publish","upload"],"version":"2.7.0","requires":{"base_skill":"uumit-agent","base_version":">=2.0.0"},"runtime":{"node":">=18","packages":[]},"permissions":["network:https://api.uumit.com","fs:read:{UUMIT_SKILL_DIR}/memory/","exec:node:{UUMIT_SKILL_DIR}/scripts/rest_request.js"],"output_contract":"machine: scripts emit JSON on stdout for agent parsing only; human: summarize, never paste stdout/stderr to user"}}
---

# uumit-publisher — UUMit 发布扩展（v2.7.0）

`uumit-agent` 基座的发布扩展。负责文件上传与批量发布/上架，是 Agent 把本地产物搬上 UUMit 的入口。

## 定位与边界

- **混合模型**：
  - 批量发布/上架等**纯 JSON 调用走基座 `rest_request.js`**（自动过 allowlist + L0-L5 安全闸门）。
  - 单文件上传为 **multipart/form-data**，基座 JSON 通道不支持，故本扩展受控直传，但**凭证与 base_url 完全复用基座契约**（`api_key`/`platform_user_id`/`base_url`），不另起认证。
- **写操作需确认**：批量发布会改变资产上架状态（L4 级别），Agent 应先向用户复述将发布的清单并确认。
- **发布"能力类"资产走强确认**：当发布对象是会被他人调用的**动态能力**（工作流、工具、子 Agent、数据服务等，
  发布后将进入平台能力广场、可被其他用户/Agent 调用并可能产生费用或数据流转），风险高于普通资产，
  **必须强确认**——向用户逐项复述：能力名称、谁能调用、计费方式、涉及的数据/权限，明确同意后才发布。
  不得因批量而省略对能力类条目的逐项确认。
- **依赖基座**：需先安装 `uumit-agent >=2.0.0` 并完成授权。

## 何时加载

| 触发条件 | 动作 |
|---|---|
| 用户要上传文件 | `upload` |
| 用户要批量发布 / 批量上架资产 | `batch-publish` |

## 用法

前置：确保 `UUMIT_SKILL_DIR` 指向基座目录（未设置时回退到与本扩展并列的 `uumit-agent`），且基座已授权。

```bash
# 上传单个文件，返回可用于上架的文件 URL
node scripts/publisher.js upload --file <path> [--folder <name>]

# 批量发布我的数字资产（先 --dry-run 预览将发布的清单）
node scripts/publisher.js batch-publish --dry-run
node scripts/publisher.js batch-publish --limit 20
```

## 输出契约

- 脚本 stdout 输出 JSON，仅供 Agent 内部解析；**不要把 stdout/stderr 原样粘贴给用户**。
- `upload` 成功返回 `file`（含可用于上架的 URL）；失败返回 `status: upload_failed` 与详情。
- `batch-publish` 返回 `results` 逐项发布结果与 `agent_hint`；先用 `--dry-run` 让用户确认清单再实发。publish 需要封面：列表项无 `cover_image_url`（如草稿未填封面）的资产会跳过并提示补封面，请先 `create-asset` 带 `cover_image_url` 或更新媒体后重试。
