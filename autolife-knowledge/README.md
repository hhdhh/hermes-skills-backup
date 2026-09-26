# Autolife FAE Knowledge Skill

用于从 Autolife FAE 知识库检索机器人、太空舱、产品手册、部署配置和故障处理经验；
内部使用还可把新的排查记录写回知识库。

支持两种模式：**公网模式**（HTTPS + API 密钥，无需 VPN，适合分发给客户）
和**内网模式**（NetBird + AstrBot，功能更全）。配置 `KB_API_TOKEN` 即切到公网模式。

## 功能概览

- **两种运行模式**：配置 `KB_API_TOKEN` 走**公网模式**（HTTPS + 密钥，无需 VPN，适合分发给客户）；留空则走**内网模式**（NetBird + AstrBot，功能更全）。
- **知识库检索**：把自然语言问题发送到知识库接口，返回最相关的知识片段和来源文档名。
- **上下文补齐**：远端切片器用固定宽度切分且**未应用重叠**，实测 91.3% 的块开头被切断、93.1% 的结尾被切断、只有 2.0% 的块从标题开始。检索后会把命中块补回所在小节，并用 `--- 命中片段开始/结束 ---` 标出真正匹配的部分。
- **结果去重**：按三个键折叠重复——完全相同的内容、归一化后的文档名（`手册 副本.txt` / `手册 (1).txt` / `手册（多图需修）` / `手册_多图需修_` 均视为同一份）、以及同文档同块号；再限制单文档片段数，避免一份长手册挤占全部结果。
- **一键安装引导**：`python scripts/setup.py` 提示粘贴密钥，当场打一次真实检索验证，通过后写入 `.env`。
- **JWT 复用**（内网模式）：登录令牌有效期约 7 天，缓存在本地临时目录，避免每次检索都重新登录。
- **经验文档上传**（内网模式）：把维修/排查 Markdown 上传到知识库，等待后台分块和向量化完成。
- **NetBird 强制预检**（内网模式）：访问远端知识库前先确认本机已连接到指定自托管 NetBird 服务器。
- **修复后沉淀**：提供统一的问题排查、根因、修复、验证和遗留事项文档结构，便于后续检索。

## 总体架构

Skill 有两种模式，由是否配置 `KB_API_TOKEN` 自动决定。

### 公网模式（推荐，客户分发用这个）

```text
Agent / 用户
    |
    |  本地 Python Skill
    v
https://fae.gz.autolife.ai:8866/kb
    |  HTTPS，API 密钥鉴权（?token= 或 X-API-Key）
    |
    |  上级路由反向代理 → 排班系统（:8000）的 /kb 路由
    v
hybrid_retrieve  http://127.0.0.1:6187
    |
    +-- POST /retrieve     检索知识片段（服务端已做上下文补齐）
    |
    +-- 向量检索 --> AstrBot  http://127.0.0.1:6185
    `-- 关键词检索 --> 本地文档镜像
```

**不需要 NetBird、不需要 AstrBot 账号**，只要一把 API 密钥。

### 内网模式（内部使用，功能更全）

```text
Agent / 用户
    |
    |  本地 Python Skill
    v
NetBird 客户端
    |
    |  自托管 NetBird 虚拟局域网
    |  Management: https://netbird.autolife-robotics.com:443
    v
远端 AstrBot Dashboard
    |  http://100.98.150.220:6185
    |
    +-- POST /api/auth/login                         登录，获取 JWT（缓存复用）
    +-- POST /api/kb/retrieve                        检索知识片段
    +-- GET  /api/kb/list                            列出知识库（自动翻页）
    +-- POST /api/kb/document/upload                 创建上传任务
    `-- GET  /api/kb/document/upload/progress        查询分块/向量化进度
```

公网模式只能检索；**列库、上传、按小节精确补齐等能力仅内网模式可用**。

脚本只使用 Python 标准库，不依赖第三方包。

## 项目结构

```text
.
├── SKILL.md                          # Skill 行为约束和使用入口
├── INSTALL.md                        # 面向客户的简明安装说明
├── README.md                         # 本文档
├── .env.example                      # 配置模板
└── scripts/
    ├── setup.py                      # 安装引导：提示输入密钥、验证、写入 .env
    ├── kb_client.py                  # 共享客户端：配置、HTTP、检索、去重、上下文补齐、上传
    ├── netbird_preflight.py          # NetBird 连接预检（仅内网模式）
    ├── retrieve_kb.py                # 检索知识库（自动选择模式）
    ├── upload_to_kb.py               # 上传 Markdown 并等待向量化完成（仅内网模式）
    └── selftest.py                   # 冒烟测试（离线单元检查 + --online 在线检查）
```

## 知识库构成

同一台 AstrBot 上挂着两个知识库（数字为 2026-09-18 实测）：

| 知识库 | 文档数 | 分块数 | 说明 |
|---|---:|---:|---|
| `autolife知识库` | 58 | 910 | 主力库 |
| `autolife-docs` | 6 | 225 | 6 份**完整版**文档，均与主力库重叠 |

**历史包袱（已处理）**：主力库曾有 2640 条记录、实际只有 51 份唯一内容，平均每份重复 51.8 次，
冗余率 97.8%。根因是 `feishu_sync_all.py` 全量同步且没有幂等键，反复运行把同一批文档重复导入。
`kb6185_dedupe.py` 已清理，`\FullSync` 计划任务也已禁用——**但治本要靠带幂等键的同步器**。

`autolife-docs` 里的 6 份文档在主力库中同样存在，但主力库里同一标题往往还有更短的截断版本——
`autolife-docs` 保存的是完整版。

检索默认**两个库都查**（`KB_NAMES=autolife知识库,autolife-docs`），去重会按文档名合并，保留得分最高（通常也是最完整）的片段。

> 公网模式下库名由服务端固定，客户端无需也无法指定。

### 库内文档分类（51 份唯一文档）

- **运维排查**：机器人运维及问题处置手册（中/英）、VR 应用操作及问题处置手册（中/英）、手机 App 应用操作及问题处理手册（中/英）、屏幕故障排查
- **手册说明书**：Autolife-S2 使用手册、智动未来现场应用必备手册、VR 环境搭建和系统配置手册（中/英）、机器人装机和系统配置手册（中/英）、测试设备启动及调整说明手册、VR 摇操数采操作手册
- **配置部署**：机器人数据采集配置、机器人本地服务器部署说明、Netbird 机器人部署与 PC 使用、Data Logger 开机自启动配置指南、头部跟随 AI 语音对话配置文档、太空舱自动售卖饮料配置教程、Autolife 太空舱饮品零食配置流程、语音点单临时版、自动化导览
- **标定**：Autolife 语音标定、机械臂动力学标定流程、机械臂运动学标定流程
- **流程**：机器人模块集成测试流程详解（中/英）、数据采集和清洗流程、数据采集下载流程、数据自动上传部署流程、安全策略板更新流程、系统编号修改流程
- **培训话术**：FAE 新人培训文档、FAE 新人快速上手学习顺序、智动未来对外常用话术、FAE 常用命令检索及关键文件位置存放目录、机器人常用命令、AI 语音&导航
- **其他**：太空舱更新说明、3D 扫描仪使用方法、Linux 系统下声学测试抓取数据、S2-AI 面部识别与动作预设、Autolife-S2 太空舱（交付模板）、flow 引导接待说明文档
- **测试残留（建议清理）**：`Skill上传验证-本机到远端.txt`、`test_import.txt`、`测试经验文档-自动生成.md`、`测试方案.txt`

## NetBird 约束（仅内网模式）

**公网模式不受此约束**——配置了 `KB_API_TOKEN` 时不会触发 NetBird 预检。

内网模式下，远端 AstrBot 只能通过 NetBird 虚拟局域网访问。脚本在检索和上传前都会调用 `ensure_netbird()`，确认以下条件全部成立：

1. 本机能找到 `netbird` CLI。
2. NetBird daemon 已连接。
3. Management 通道已连接。
4. Signal 通道已连接。
5. Management URL 是自托管地址。
6. NetBird 会话未过期。

默认只允许：

```text
https://netbird.autolife-robotics.com:443
```

任何一项失败都会阻止访问知识库。此时应先启动 NetBird、切换到正确 Profile 或重新登录，不要改用公网地址。

手动预检：

```powershell
python scripts/netbird_preflight.py
```

## 安装

把本仓库克隆或复制到 Skill 目录。Codex 默认目录为
`C:\Users\<用户名>\.codex\skills\autolife-FAE-knowledge-skill`；WorkBuddy 为用户级目录
`C:\Users\<用户名>\.workbuddy-ai\skills\autolife-knowledge`。

**然后配置密钥（只需一次）**：

```bash
cd <skill 目录>/scripts
python setup.py
```

脚本会提示粘贴管理员分发的 API 密钥，**当场打一次真实检索验证**，通过后写入 `.env`。
之后即可直接检索，无需任何额外配置。

面向客户的精简版说明见 [INSTALL.md](INSTALL.md)。

推荐环境：

- Windows 10/11（`netbird_preflight.py` 也支持 macOS / Linux 的常见安装路径）
- Python 3.10 或更新版本
- **公网模式**：能访问 `fae.gz.autolife.ai:8866` 即可
- **内网模式**：额外需要已登录自托管 NetBird，且能访问远端 AstrBot Dashboard

## 配置

配置来自环境变量；技能根目录下的 `.env` 会被自动加载，但**不会覆盖**已经存在的环境变量。
不要把真实密码或密钥提交到仓库（`.env` 已在 `.gitignore` 中）。

### 模式选择

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `KB_API_TOKEN` | 空 | **一旦有值就启用公网模式**（无需 NetBird）。由 `setup.py` 写入。 |
| `KB_PUBLIC_URL` | `https://fae.gz.autolife.ai:8866/kb` | 公网网关地址。 |

### 公网模式

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `KB_TOP_K` | `5` | 检索返回的最大片段数。 |
| `KB_MAX_CHARS` | `12000` | 文本输出字符上限，0 表示不限。 |
| `KB_TIMEOUT` | `30` | HTTP 超时秒数。 |

### 内网模式

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `KB_BASE_URL` | `http://100.98.150.220:6185` | AstrBot Dashboard API 地址。 |
| `KB_USERNAME` | `autolife` | AstrBot 登录用户名；已内置默认值。 |
| `KB_PASSWORD` | `123455` | AstrBot 登录密码；已内置默认值。 |
| `KB_NAMES` | `autolife知识库,autolife-docs` | 默认知识库，逗号分隔，去重保序。 |
| `KB_MAX_PER_DOC` | `2` | 去重后单文档最多保留的片段数，0 表示不限。 |
| `KB_TIMEOUT` | `30` | 单次 HTTP 超时（秒）。 |
| `KB_UPLOAD_TIMEOUT` | `900` | 等待后台分块/向量化的最长时间（秒）。 |
| `KB_CACHE_TOKEN` | `1` | 复用 JWT；设为 `0` 则每次调用都重新登录。 |
| `KB_SUPPRESS_HTTP_WARNING` | `0` | 设为 `1` 可关闭明文 HTTP 告警。 |
| `NETBIRD_MANAGEMENT_URL` | `https://netbird.autolife-robotics.com:443` | 允许使用的 NetBird 管理服务器。 |

非法的 `KB_TOP_K` / `KB_MAX_CHARS` 等数值不会导致崩溃，脚本会打印提示并回落到默认值。

当前 PowerShell 会话覆盖示例：

```powershell
$env:KB_USERNAME = "other-account"
$env:KB_PASSWORD = "other-password"
$env:KB_NAMES = "autolife知识库"
```

用户级永久覆盖示例：

```powershell
[Environment]::SetEnvironmentVariable("KB_USERNAME", "other-account", "User")
[Environment]::SetEnvironmentVariable("KB_PASSWORD", "other-password", "User")
```

永久变量设置后需要重启终端和客户端。

## 切片质量与上下文补齐

远端切片器的配置写着 `chunk_size=512 / chunk_overlap=50`，但实测**重叠并未生效**：把一份 18,256 字符的文档切成 37 块，各块长度之和恰好等于 18,256，说明是无重叠的连续切分。652 个切片边界里只有 2 个存在重叠。

固定宽度切分的后果（实测 12 份最完整的文档、664 个块）：

| 指标 | 实测值 |
|---|---:|
| 开头被切断的块（未落在标题且上一块未以句末标点结束） | 606 / 664 = **91.3%** |
| 结尾被切断的块（未以句末标点结束） | 618 / 664 = **93.1%** |
| 块首恰好是标题的块 | 13 / 664 = **2.0%** |
| 块长度 | 48 – 548 字符，均值 475（409 块集中在 500–549） |

也就是说，单独返回一个块，经常丢掉它所属的条件、标题或前一步。

### 三个缓解手段

1. **`--expand section`（默认）** —— 把命中块补回所在小节：
   - 优先取「上方最近标题 → 下一标题之前」的整段；
   - 文档没有可识别标题时（如《机器人运维及问题处置手册》37 块中零标题）回落为围绕命中块的对称窗口；
   - 单条命中最多合并 `--expand-max-chunks`（默认 8）块。
2. **`--expand window --expand-window N`** —— 固定前后各取 N 块，行为可预测。
3. **`--expand none`** —— 只用命中块，输出最紧（约 1.2 K 字符）。

命中块本体**永远完整保留**，并夹在 `--- 命中片段开始 ---` / `--- 命中片段结束 ---` 之间。这是因为对称窗口会把命中块放在约 50% 的位置，正是模型注意力最弱的地方；标记让答案落在文本接缝处，同时保留可读的上下文顺序。超出字符预算时，裁剪的是**离命中块最远的上下文**，不是命中块本身。

三种模式的输出体量（`top_k=3`，同一查询）：`none` ≈ 1.2 K 字符，`window` ≈ 3.5 K 字符，`section` ≈ 8 K 字符。

### 重索引能不能救？——实测结论：不能

直觉上会想到「改大重叠 + 结构感知切分，重新入库一遍」。实测这条路走不通（2026-09-14 用隔离的 scratch 知识库验证）：

| 验证项 | 结果 |
|---|---|
| `PUT /api/v1/knowledge-bases/{kb_id}` 改 `chunk_size` | 返回「更新知识库成功」，且**确实持久化**（回读为 200） |
| 改完之后已有文档是否重新切片 | **否**。8,097 字符的文档 20 块，改成 200 后等 5/15/30 秒，始终是 20 块 |
| 改完之后新上传的文档是否按新参数切 | **否**。旧接口与 v1 接口传同一文档，仍是 20 块（≈405 字符/块，与 512 和 200 都对不上） |

即 **`chunk_size` / `chunk_overlap` 被写入了配置，但切片器根本不读它们**。知识库也只暴露这两个参数，没有结构感知的切分选项（前端 bundle 里的 `split_words` / `regex` 属于 `segmented_reply` 机器人消息分段，与知识库无关）。

所以上面的「上下文补齐」不是权宜之计，而是当前架构下的正解。真要改善切片，只能在 AstrBot 服务端改切片器实现或配置，不是 API 层面能做的事。

## 检索流程

```powershell
python scripts/retrieve_kb.py "太空舱饮品配置在哪里配置"
```

常用参数（`--kb-name` / `--expand` / `--no-dedup` 等**仅内网模式有效**）：

```powershell
python scripts/retrieve_kb.py "机器人视觉无法启动" --top-k 8
python scripts/retrieve_kb.py "DDS 配置" --kb-name autolife知识库   # 仅内网
python scripts/retrieve_kb.py "部署流程" --json              # 机器可读输出
python scripts/retrieve_kb.py "部署流程" --max-chars 4000    # 限制输出长度
python scripts/retrieve_kb.py "部署流程" --no-dedup          # 关闭去重（仅内网）
python scripts/retrieve_kb.py "网络配置" --expand none       # 只返回命中块（仅内网）
python scripts/retrieve_kb.py "网络配置" --expand window --expand-window 2
python scripts/retrieve_kb.py "网络配置" --internal          # 强制走内网模式
python scripts/retrieve_kb.py "网络配置" --public-url URL    # 覆盖公网网关地址
```

### 公网模式流程

1. 把 `{"query", "top_k"}` POST 到 `KB_PUBLIC_URL?token=<密钥>`。
2. 服务端（`hybrid_retrieve`）自己做向量 + 关键词混合检索与上下文补齐。
3. 解析 `results`，输出带序号、来源文档名、分数和匹配来源的片段。
4. 401 → 密钥无效或被吊销；404 → 网关地址不对。

### 内网模式流程

1. 执行 NetBird 预检。
2. 读取 JWT 缓存；有效则复用，否则调用 `POST /api/auth/login` 并写回缓存。
3. 调用 `POST /api/kb/retrieve`，按 `top_k × 4`（上限 50）多取一些候选。
4. 解析 `data.results`，按分数降序做去重与单文档限流，再截取到 `top_k`。
5. 按 `--expand` 拉取命中块的邻居并补回上下文（见上一节），命中块用标记括起。
6. 输出带序号、来源文档名、所属知识库、三位小数分数和块跨度说明的片段。

回答规则：

- 相关内容优先以知识库为准。
- 引用事实时说明来源文档名。
- 知识库没有覆盖的内容必须明确说明，不能编造。
- 不输出密码、JWT、API 密钥或原始登录响应。

## 上传流程

### 上传本地 Markdown

```powershell
python scripts/upload_to_kb.py "C:\path\to\repair-report.md"
```

指定知识库和标题：

```powershell
python scripts/upload_to_kb.py "C:\path\to\repair-report.md" `
  --kb-name autolife知识库 `
  --title "Fix: 机器人启动后视觉服务退出.md"
```

从标准输入上传：

```powershell
Get-Content "summary.md" -Raw | python scripts/upload_to_kb.py - --title "Fix: DDS 配置不匹配.md"
```

只创建任务、不等待处理完成：

```powershell
python scripts/upload_to_kb.py "repair-report.md" --no-wait
```

### 内部步骤

1. 执行 NetBird 预检。
2. 使用内置账号或环境变量覆盖值。
3. 读取本地文件，或从标准输入创建临时文件（无论成功失败都会清理）。
4. 获取 JWT（优先复用缓存）。
5. 调用 `GET /api/kb/list`（自动翻页），把 `--kb-name` 解析成 KB ID。
6. 调用 `POST /api/kb/document/upload`，以 `multipart/form-data` 上传。boundary 随机生成，中文文件名同时写入 `filename*`（RFC 5987）以免服务端乱码。
7. 从响应中读取 `data.task_id`。
8. 轮询 `GET /api/kb/document/upload/progress`，直到任务 `completed` 或 `failed`，期间输出进度。
9. 如果后台结果里有失败文档，脚本返回错误；否则输出处理结果。

后台任务默认最多等待 15 分钟，可用 `--timeout` 调整。

## 修复后沉淀流程

完成维修、复杂排查、配置修复或重要架构验证后，应先生成结构化 Markdown，**经用户确认后**再上传到知识库。

推荐文档结构：

```markdown
# [系统/组件] [问题简述] 排查修复记录

**结论**：一句话说明根因和修复方式。

## 一、问题现象
- 机器人/设备标识
- 系统版本
- 故障日期
- 耗时
- 具体症状

## 二、排查过程
- 排查思路
- 每一步实测结果
- 关键拐点和决定性测试

## 三、根因分析
- 直接原因
- 深层原因
- 因果链

## 四、修复步骤
- 改动前后对比
- 操作命令
- 回滚方案

## 五、验证结果
- 逐层验证项
- 验证命令和输出摘要

## 六、遗留事项与预防
- 遗留问题
- 后续观察点
- 下次快速判定方法
```

适合上传的情况：

- 硬件或软件维修完成。
- 复杂调试找到了非显而易见的根因。
- 配置修复对其他机器人有复用价值。
- 发现了新的系统架构限制或部署要求。

不建议上传的情况：

- 简单重启且没有新的排查结论。
- 知识库已有同因、同修法的记录。
- 内容只有临时猜测，没有验证结果。

## 接口说明

### 公网模式

| 接口 | 方法 | 用途 |
|---|---|---|
| `KB_PUBLIC_URL`（默认 `/kb`） | `POST` | 检索片段。请求 `{"query", "top_k"}`；鉴权走 `?token=` 或 `X-API-Key` 头。 |

返回结构：

```json
{
  "query": "机器人视觉无法启动",
  "keywords_used": [],
  "vector_count": 4,
  "keyword_count": 0,
  "results": [
    {
      "doc_name": "Autolife-S2 使用手册 (1).txt",
      "section": "",
      "matched_by": ["vector"],
      "score": 0.4,
      "keywords": [],
      "content": "…",
      "vector_score": 0.999,
      "keyword_score": 0
    }
  ]
}
```

网关链路：`上级路由 → 排班系统 :8000 的 /kb 路由 → hybrid_retrieve :6187`，
其中向量那一路再回调 AstrBot `:6185`。

### 内网模式

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/auth/login` | `POST` | 用户名密码登录，返回 JWT（payload 含 `exp`，约 7 天有效）。 |
| `/api/kb/retrieve` | `POST` | 按问题和知识库名称检索片段，返回 `data.results`。 |
| `/api/kb/list` | `GET` | 列出知识库，支持 `page` / `page_size` 分页。 |
| `/api/kb/document/list` | `GET` | 按 `kb_id` 列出文档，支持分页。用于清点与去重分析。 |
| `/api/kb/chunk/list` | `GET` | 按 `kb_id` + `doc_id` 取回该文档的**全部分块**，按 `chunk_index` 有序。上下文补齐依赖它。 |

### v1 API（功能更全，同一份 JWT 即可访问）

从 Dashboard 前端 bundle（`/assets/index-*.js`）中共提取到 193 条 `/api/` 路由，其中知识库相关：

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/v1/knowledge-bases` | `GET` / `POST` | 列出 / 创建知识库。 |
| `/api/v1/knowledge-bases/{kb_id}` | `GET` / `PUT` / `DELETE` | 详情 / 更新配置 / 删除。注意 `chunk_size`、`chunk_overlap` 写入有效但不被切片器采用。 |
| `/api/v1/knowledge-bases/{kb_id}/documents` | `GET` / `POST` | 列出 / 上传。 |
| `/api/v1/knowledge-bases/{kb_id}/documents/import-url` | `POST` | 从 URL 导入。 |
| `/api/v1/knowledge-bases/{kb_id}/documents/{document_id}` | `GET` / `DELETE` | 详情 / **删除文档**（清理重复副本用这个）。 |
| `/api/v1/knowledge-bases/{kb_id}/chunks` | `GET` | 列分块，需带 `doc_id`。 |
| `/api/v1/knowledge-bases/{kb_id}/chunks/{chunk_id}` | `DELETE` | 删除单个分块。 |
| `/api/v1/knowledge-bases/{kb_id}/retrieve` | `POST` | 检索。 |
| `/api/v1/knowledge-bases/tasks/{task_id}` | `GET` | 后台任务状态。 |

已知问题：在 Windows 服务端上 `DELETE /api/v1/knowledge-bases/{kb_id}` 常因 `doc.db` 被占用而失败（`[WinError 32]`），文档可以删、知识库删不掉。
| `/api/kb/document/upload` | `POST` | 上传文档并创建后台处理任务。 |
| `/api/kb/document/upload/progress` | `GET` | 查询后台任务进度和结果。 |

## 本地验证

冒烟测试（离线部分随时可跑，不联网）：

```powershell
python scripts/selftest.py
python scripts/selftest.py --online   # 额外验证 NetBird / 登录 / 列表 / 检索
```

语法检查：

```powershell
python -m py_compile scripts/kb_client.py scripts/netbird_preflight.py scripts/retrieve_kb.py scripts/upload_to_kb.py scripts/selftest.py
```

NetBird 预检与最小检索验证：

```powershell
python scripts/netbird_preflight.py
python scripts/retrieve_kb.py "太空舱" --top-k 1
```

## 常见问题

### 公网模式

**`API 密钥无效或已被吊销（HTTP 401）`**
密钥错误或已失效。找管理员确认，或运行 `python scripts/setup.py --force` 换一把。

**`公网检索端点不存在（HTTP 404）`**
`KB_PUBLIC_URL` 不对。应为 `https://fae.gz.autolife.ai:8866/kb`。

**连接超时**
本机访问不到 `fae.gz.autolife.ai:8866`。检查网络、代理设置或防火墙。

**想换密钥**
`python scripts/setup.py --force`

**想确认当前配置是否正常**
`python scripts/setup.py --check`

### 内网模式

**`未找到 NetBird CLI`**
安装 NetBird 客户端，或确认 `C:\Program Files\NetBird\netbird.exe` 存在。

**`Wrong NetBird server` 或 `NetBird 服务器不正确`**
当前 NetBird Profile 连接的不是自托管服务器。切换到正确 Profile 后重新执行脚本。

**`NetBird 会话已过期`**
打开 NetBird 客户端重新登录。

**检索返回 401 或登录失败**
检查 `KB_USERNAME` 和 `KB_PASSWORD` 是否正确。若刚改过凭据，删除临时目录下的
`autolife-kb-token-*.json` 以清掉旧令牌。

**提示找不到知识库**
`--kb-name` 必须和 AstrBot 中的知识库名称完全一致。脚本在名称不存在时会列出当前可用的
全部知识库名，照着改即可。

**检索偶发返回"没有相关内容"**
AstrBot 后端偶发在 200 响应里返回空结果集（同一 query 重跑即有结果）。重跑一次再下结论。

**上传长时间没有完成**
后台可能仍在解析、分块或向量化。脚本最多等待 15 分钟（`--timeout` 可调）；
embedding 服务不可用或文档异常时会更早失败。

**明文 HTTP 告警**
内网模式下服务端只提供 HTTP，脚本会提示凭据未加密（在 NetBird 隧道内）。
若 AstrBot 后续启用 TLS，把 `KB_BASE_URL` 改成 `https://` 即可消除。

## 安全要求

- **不要提交 `.env`**（含 API 密钥，已在 `.gitignore` 中）。
- **API 密钥是共享密钥，不要转发给不该有权限的人。** 需要撤销时找管理员换密钥。
- 内网模式的默认账号密码是为了开箱即用而固定在仓库中的。
  **如果仓库公开或 NetBird 边界变化，应立即轮换 AstrBot 密码，并改回环境变量注入。**
- 不要在日志或提交信息中写入密码、JWT 或 API 密钥。
- 预检失败时不要绕过 NetBird 或改用公网地址。
- 上传会把内容发布到共享知识库，务必先取得用户确认。

## 当前边界

- **公网模式只能检索**；列库、上传、按小节精确补齐仅内网模式可用。
- 上传脚本面向 AstrBot Dashboard API；它会等待知识库处理完成，但不会自动删除旧版同名文档。
- 删除远端知识库文档需要使用 AstrBot WebUI 或单独的 API 工具。
- NetBird 预检是安全约束，不能用普通网络连通性测试替代。
- 内网模式检索结果上限为 20 条，`--top-k` 超过 20 不会拿到更多。
- **公网密钥目前是一把全员共用，无法按客户单独吊销。** 后续应改为每客户独立 key + 审计。
- 仓库尚未附带 LICENSE，使用范围请与维护者确认。
