# 飞书集合读取与核验

## 前置
加载 lark-shared、lark-drive、lark-wiki、lark-doc；下钻时加载 lark-sheets、lark-base 与文件读取技能。使用当前用户身份，不把机器人视角的空结果当用户无资源。先检查认证状态，不无条件重新登录。

## 可复用读取顺序

1. `lark-cli wiki +space-list --as user --format json` 查询知识空间。个人文档库可用 `wiki spaces get --params '{"space_id":"my_library"}' --as user` 解析；节点使用 `wiki +node-list` 并沿 has_child 和分页继续。
2. `lark-cli drive +search --as user --query '<工作关键词>' --page-size 20 --format json`；逐页传回 page_token，直到 has_more=false。空关键词不能代替全部文档枚举。
3. `lark-cli drive files list --as user --params '{"folder_token":"","page_size":200}'` 读根目录。对每个 folder 独立递归，使用 data.next_page_token；根目录不是完整共享空间列表。
4. `lark-cli docs +fetch --api-version v2 --as user --doc '<实际URL或token>' --detail full` 保存整篇结构，用于确需全文精读的任务；记录 data.document.document_id/revision_id/content。Wiki入口与底层文档分别保留，后者用于规范化去重。
5. 从结构标签和真实引用继续扩展，保留未解析引用队列；含 fragment 的链接不能计作新文档，但不能丢失它指向的章节。只在既定授权范围内跟进。

## 表格与 Base

- Sheet 先 `sheets +workbook-info` 取真实 sheet_id 和维度，再 `+cells-get --include value,formula,comment --range '<实际范围>'`；保持隐藏行列可读。使用 --output-path 时仍检查 complete/truncated，因为输出文件也可能触及上限。
- 按真实响应识别容器内嵌 Base，不按搜索的 SHEET 标签强行使用单元格接口。
- Base 使用 `+table-list`、`+field-list`、`+record-list` 等 shortcut，先用 --help 核对当前分页参数。记录读取显式 JSON 格式并分页；按 record_id 去重后与实际表元数据计数比较，不以响应页数或脚本正常退出证明完整。
- Base 资源目录读取缺权限时，保存确切缺口；数据表读取成功只能设置 table_content_complete，不能推导整个 Base 完整。

## 评论与附件

- 评论读取遵循 lark-drive 当前默认范围，并在清单明确 unresolved_only 或包含已解决项；零条未解决评论不证明从无评论。
- 普通附件下载成功后核对真实文件大小/哈希，提取后检查全文字符量、页面覆盖和图片文本缺口。极少提取文本不能标记整本扫描 PDF 已读。
- ZIP 未处理属于缺口，不因子任务只接受 PDF/DOCX 而把父任务“所有附件”标为完成；若继续处理，只读列目录及安全提取，不运行包内内容。
- 图片 alt 和缓存文件仅证明描述可读、素材已取得；只有实际图像审查或明确范围的 OCR 核验才能改变视觉阅读状态。

## 规模化执行

CLI stdout 单独解析 JSON，stderr 单独保存；每页结果立即持久化，遇短暂限流进行有界重试，权限错误停止该目标并记录。先用少量资源验通，再扩展并发。正文与代码审查按实际文本量分批，结构和占位模板生成不计入语义精读完成数。
