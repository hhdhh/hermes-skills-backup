---
name: lark-raw-api-doc-append
description: "Use when lark-cli 被 TLS reset 打死但必须更新飞书文档，用原生 API 直调追加。"
---

# lark-cli 不可用时的原生 API 文档追加（TLS reset 兑底）

## 适用判断

- lark-cli 多次重试仍报 `accounts.feishu.cn ... connection reset by peer`，而 `curl -X POST https://accounts.feishu.cn/oauth/v3/token` 秒回 400（链路本身通）→ 是 CLI 的 Go TLS 指纹被 CDN 针对性 reset，换 TLS 栈（Python urllib / curl）即过。
- 换 IP / hosts 钉扎无效，别试。
- 首选永远是重试 lark-cli 本体（reset 常为间歇性）；确认被打死才走本兑底。

## 完整链路（往已有文档追加章节）

1. **拿 bot TAT（curl）**：`POST /open-apis/auth/v3/tenant_access_token/internal`，form 编码 app_id + app_secret（secret 从 lark-cli 加密存储解密：`~/.local/share/lark-cli/appsecret_<app_id>.enc` + master.key，AESGCM 解密；解密后只在进程内用，不 print/落盘）。curl 拿 TAT 这条链路一直稳定。
2. **wiki token → 真实 docx token**：`GET /wiki/v2/spaces/get_node?token=<wiki_token>` → `data.node.obj_token`。用户给的是 wiki 链接时必须先换，直接拿 wiki token 调 docx API 会 404。
3. **markdown 转 blocks**：`POST /open-apis/docx/v1/documents/blocks/convert`，body `{content_type:"markdown", content:<md>, document_id:<doc>}` → `data.blocks`。children API 只收 blocks JSON 不收 markdown，convert 是必经桥梁。
4. **取追加位置**：`GET /docx/v1/documents/{doc}/blocks/{doc}`（页面根块），`len(block.children)` 即顶层块数 = 插入 index。别用 `/blocks` 列表接口的 items 数（返回的不是同一层级计数）。
5. **分批创建**：`POST /docx/v1/documents/{doc}/blocks/{doc}/children`，body `{index:<起始>, children:<batch>}`，按 ≤40 块一批循环，index 逐批累加。
6. **回读验证**：`GET /docx/v1/documents/{doc}/raw_content`，grep 新增锚点关键词。

## 坑

- **children 单请求上限 50**（`field validation failed: the max len is 50`）——分批。
- **markdown 表格不可用**：convert 产出 table_cell 块（block_type 32），children 创建报 `block not support to create`——追加内容里的表格先改写成 bullet 列表再 convert。
- **勿直调 user refresh 端点**：会消耗一次性 refresh token，旧 token 立即作废，lark-cli 本地缓存的 .enc 变死链。本链路全程 bot TAT，不碰 user 身份。
- 工作脚本模板：`~/.hermes/workspace/feishu_doc_update_323.py`（read/append 两模式，含 secret 解密 + curl 拿 TAT + 分批写入）。
