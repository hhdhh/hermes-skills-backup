
# docs +media-preview（预览文档素材）

> **前置条件：** 先阅读 [`../lark-shared/SKILL.md`](../../lark-shared/SKILL.md) 了解认证、全局参数和安全规则。

优先用于查看、预览文档中的图片或文件素材（`file_token`）。命令会把素材保存到本地路径，便于后续打开查看内容。

## 选择规则

- 用户说“看一下素材 / 图片 / 附件”“预览一下”时，优先使用 `docs +media-preview`
- 用户明确说“下载”时，使用 [`docs +media-download`](lark-doc-media-download.md)
- 如果目标明确是画板 / whiteboard / 画板缩略图，不要使用 `+media-preview`，改用 `docs +media-download --type whiteboard`

## 命令

```bash
# 预览图片/文件素材
lark-cli docs +media-preview --token "Z1Fjxxxxxxxx" --output ./asset

# 指定输出文件名（带扩展名则不会自动补全）
lark-cli docs +media-preview --token "Z1Fjxxxxxxxx" --output ./asset.png
```

## 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--token <token>` | 是 | 素材 token，即 `file_token` |
| `--output <path>` | 是 | 本地保存路径；不带扩展名会自动补全 |

## token 从哪里来

- 若你是从文档内容里提取：`lark-doc-fetch` 返回的 Markdown 里可能包含：
  - 图片：`<image token="..." .../>`
  - 文件：`<file token="..." name="..."/>`

## 本地批量缓存核验

- 按素材 token 去重、并发限制为 2；已有文件不要覆盖，使用相对输出路径和 `--as user`。
- 检查 CLI 返回的 `data.saved_path` 或同时匹配无后缀 token 文件与 `token.*`；`application/octet-stream` 可能保存为无扩展名的有效 PNG，不能仅凭缺少扩展名判失败或重复下载。
- 缓存成功后用本地图片库校验格式、尺寸、字节数及摘要，并保留来源文档/块映射。二进制校验不等于图中文字核实；没有可用本地 OCR/视觉能力时，明确记录像素未审查，不能把 alt 当原图转录。
- 画板仅通过 `+media-download --type whiteboard` 缓存缩略图；缩略图不代表完整节点内容。

## 参考

- [lark-doc-fetch](lark-doc-fetch.md) — 获取文档内容（用于提取 token）
- [lark-doc-media-download](lark-doc-media-download.md) — 明确下载素材，或下载画板缩略图
- [lark-shared](../../lark-shared/SKILL.md) — 认证和全局参数
