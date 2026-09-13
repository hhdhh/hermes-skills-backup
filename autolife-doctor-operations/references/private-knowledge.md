# 私有飞书知识检索

在诊断机器人问题之前，用本地私有归档回忆历史事故、服务/配置模式、维修讨论和角色相关背景。所有检索结果只能当作待验证的知识，绝不能当作机器人或发布当前状态的证明。

## 来源契约

- 默认归档位置：`~/.local/share/autolife-robot-knowledge/current`。
- 可用 `AUTOLIFE_DOCTOR_KNOWLEDGE_ROOT` 环境变量或 `--archive-root` 覆盖。
- 归档和 SQLite 索引必须留在 Git 之外，目录权限 `0700`、文件权限 `0600`。
- 文档按内容 SHA-256 去重。聊天覆盖范围取决于构建归档所用的脚本：`archive_lark_chats.py` 保留 Doctor 相关群聊的完整历史，私聊仅保留强关键词命中；`archive_lark_all_chats.py` 保留全部群聊和单聊的完整可见历史。使用前先查看 `chat-manifest.json` 的 `scope`/`contract` 字段确认覆盖范围。
- `knowledge-manifest.json`、`manifest.json`、`chat-manifest.json` 绑定归档各层。任一 sidecar 哈希校验失败即拒绝使用索引。
- 每次 `search`/`search-many` 都会在返回摘录前验证目录/文件私有权限、四层清单和 sidecar、交叉绑定、数据库哈希、SQLite integrity、source/FTS 计数；失败统一返回 `knowledge_integrity_hold` 和稳定 reason code，不提供部分结果。
- 这条链的信任等级是 `self-consistent local unsigned archive`：能发现损坏、错配和未同步的局部改写，但不认证本机操作者或抵抗拥有全部归档写权限的人重算整条链。重要命中仍须回读飞书原始来源，并接受其当前权限与历史版本边界。
- PDF/纯图片内容可能已归档但在索引中仅有元数据。结果标注 `pdf_metadata_only` 时，去查看原始私有文件。

## 查询流程

1. 使用前先校验归档与索引：

   ```bash
   python3 skills/autolife-doctor-operations/scripts/private_knowledge.py status
   ```

2. 先把故障拆成 2–6 个相互独立的查询：精确错误或 stable ID、unit/配置对象、中英文症状同义词分别搜索。优先使用 `search-many`，它会保留每个查询的命中数与零命中项，避免一个过长短语掩盖有效结果：

   ```bash
   python3 skills/autolife-doctor-operations/scripts/private_knowledge.py search-many \
     --query 'camera timeout' \
     --query '相机超时' \
     --query 'autolife-vision.service' \
     --limit 6 --json
   ```

   单一精确查询仍可使用 `search --query ...`。不要把整句自然语言故障描述作为唯一查询。零命中只表示本次字符串没有命中当前授权归档，不证明历史上没有该问题。
3. 重要结论必须有两个以上独立查询支撑。优先使用精确的 stable ID、unit 名称、配置键、错误字符串，而不是泛化词。输出中的 `safety` 固定声明本地未签名信任等级、必须回读来源、历史资料不具有实时状态或修复授权效力。
4. 只打开最少必要的源文件路径或飞书链接。不要把整段对话或整篇文档粘贴进提示词、issue、证据、日志或报告。
5. 把检索到的内容拆分为：观测、假设、建议检查、已批准修复、结果、后续更正。聊天里达成的共识不等于已批准的修复策略。
6. 用新鲜的机器人基线和仓库契约对照历史假设。两者不一致时，保留双方并让决策保持 fail-closed。
7. 在工作记录中注明来源引用、时间戳和证据类别。删除凭据、个人数据和无关的私人对话。

## 归档构建流程

用已入库的归档脚本构建或刷新私有归档（需要交互式登录的 `lark-cli`；每位操作者使用自己的飞书身份）：

```bash
OUT=~/.local/share/autolife-robot-knowledge/archive-$(date +%Y%m%d)
python3 skills/autolife-doctor-operations/scripts/archive_lark_knowledge.py --output "$OUT"   # 文档
python3 skills/autolife-doctor-operations/scripts/archive_lark_all_chats.py --output "$OUT"   # 全部聊天完整历史
ln -sfn "$OUT" ~/.local/share/autolife-robot-knowledge/current
```

如只需 Doctor 相关的较小范围，改用 `archive_lark_chats.py`。所有归档脚本均可断点续跑：已完成的会话和文档有缓存，重跑时自动跳过。

## 索引刷新流程

归档经授权刷新后，重建并校验私有索引：

```bash
uv run skills/autolife-doctor-operations/scripts/private_knowledge.py build
python3 skills/autolife-doctor-operations/scripts/private_knowledge.py status
```

只有 `status` 同时给出 `query_ready=true` 与空的 `query_errors` 才能继续检索。`status` 本身只报告完整性，不证明归档覆盖了用户无权访问的资料，也不证明任何机器人当前健康。

`uv run` 构建会加载脚本隔离的 `pypdf` 依赖，使文本型 PDF 进入索引。无可提取文本的 PDF 保持 `pdf_scan_metadata_only`；保留原件，仅在事故排查确有需要时使用经批准的本地 OCR 流程。

绝不提交归档、SQLite 数据库、检索摘录或生成的索引 manifest。只提交通用的检索流程和脚本。
