---
name: prompt-knowledge-module
description: Use when a user wants to ingest a domain FAQ / sales 100...
---


# prompt-knowledge-module

> 完整描述："Use when a user wants to ingest a domain FAQ / sales 100-questions / product knowledge doc into an existing bot's system prompt as a non-polluting trigger-conditional knowledge module. Covers Lark Docx, Notion pages, PDFs, pasted markdown, wiki exports — anything that becomes a Q&A knowledge source. Triggers: 'add this FAQ to the prompt', 'let the bot know about X', 'feed this document to the bot', '把这份百问加进去'. Default architecture is the trigger-conditional module, not 'stuff everything in'."

> Class-level skill:把一个领域知识源(常见问题 / 销售百问 / 产品手册)接入到一个**已有 prompt** 的机器人里,不让它污染机器人的主身份、不破坏对话长度限制、不撑爆上下文窗口。

## 适用判定(动手前)

读源文档前先回答 3 个问题——任何一个答"否"就先停下来跟用户确认,而不是直接动。

1. **机器人有"主身份"吗?** 它是前台 / 礼宾 / 销售 / 教师 / 助手? → 有主身份 → 走"触发式挂载",不污染
2. **有长度限制吗?** 30 秒 / 200 字 / 1 段话 / 禁 Markdown? → 有 → 必须做触发式(全文塞进去必破)
3. **用户期望"永远在线"还是"按需触发"?** → 默认按需触发(见下方 3 个执行方案)

## 3 个执行方案(列给用户拍板,默认推荐 B)

| 方案 | 做法 | 优劣 |
|---|---|---|
| **A. 全文塞 prompt** | 源文档所有问答直接写进 system prompt | ❌ prompt 爆炸 / 突破长度限制 / 浪费 token |
| **B. 触发式挂载(推荐)** | prompt 里只追加"触发关键词 + 主题索引";全量问答放外部文件 | ✅ prompt 干净 / 细节随时可调 / 不污染主身份 |
| **C. 摘要压缩** | 把源文档压成 30-50 条高频摘要塞 prompt | ⚠️ 摘要丢细节;销售/技术场景可能答不上 |

**规则**:
- **永远先列 3 个方案让用户选**——这是 SOUL v6"主权不丢"的接法(2026-09-11 实战)
- 用户说"3" / "B" / "B 试试" → 默认按 B 做
- **不要默认选 A**——A 90% 会破长度限制,只是"看似一步到位"
- 用户没明示偏好 → 列方案时**第一项放 B**,加 "(推荐)" 标签

## B 方案的标准产出

```
~/.hermes/workspace/<source>_qa_index.json   结构化索引(机器可读)
~/.hermes/workspace/<source>_qa_full.md      人类可读全量
~/.hermes/knowledge/<source>_qa_index.json   长期归档
~/.hermes/knowledge/<source>_qa_full.md      长期归档
~/.hermes/workspace/<source>_trigger_keywords.txt  触发关键词清单
~/.hermes/workspace/prompt_<source>_final.txt 最终 prompt(原 + 模块)
```

**触发式子模块的标准结构**(追加到原 prompt 末尾):

```
# 专项知识 · <项目/产品名>(触发式,仅在被问到时启用)

你是<原主身份>,不是<源文档所属角色>。但在以下情况中,你**可以**调用"<项目>"专项知识:

触发条件:用户提问中包含以下任一关键词:<关键词列表>

知识范围(共 N 条,分 M 大主题):
【主题1】共 X 条
  - 代表问题1
  - 代表问题2
【主题2】...
...

调用规则:
1. 你仍保持<主身份>,开场和语气不变,不要主动推销。
2. 被问到<项目>相关问题时,按本专项知识回答;优先用最相关的一条,长答案精简到 30 秒内能讲完。
3. 严禁 Markdown / 加粗 / 列表——保持与主 prompt 一致的纯口语输出。
4. 若用户问的细节本知识库没有,礼貌告知"这一项暂时不在我的知识库里",不要瞎编。
5. 完整结构化知识文件位于:<归档路径>

身份边界:你介绍<项目>时,仍以"我能告诉您"开头,不以"我们项目"开头——你不是销售员,你是帮访客答疑的<主身份>。
```

**关键设计原则**:
- **触发关键词必须是"用户真会说的词"**——地块编号 / 公司名 / 项目名 / 业务词,从源文档**反向抽取**(高频出现 + 用户视角),不要凭直觉造
- **身份边界句必须有**——防止机器人跑偏身份(销售百问装进前台机器人会乱)
- **调用规则 4(瞎编门禁)必须有**——LLM 默认会编,显式禁止
- **路径必须指向真实存在的文件**——否则机器人查不到

## 数据源适配

| 源类型 | 抓取方式 | 解析方式 |
|---|---|---|
| **飞书 Docx**(公司域) | `lark-cli docs +fetch --api-version v2 --doc <URL> --as user` | markdown 内容,按 `### ` 标题切问答 |
| **飞书 Docx**(公开 URL) | ❌ `web_extract` 撞登录墙,**不可用**——必须走 lark-cli | 同上 |
| Notion 页面 | Notion API / `ntn` CLI / `web_extract`(看权限) | markdown 同上 |
| 本地 PDF / Word | `pdftotext` / `pandoc` | 看源结构 |
| 粘贴 markdown | 直接拿 | 按 markdown 解析 |
| 公开网页 FAQ | `web_extract` | 通常自带 `### ` 结构 |

**关键警告**:
- **公开 URL 飞书文档 → 不要用 `web_extract`**——会撞登录墙,返回登录页 HTML。必须用 `lark-cli docs +fetch --as user`(主人的飞书 user 身份能访问公司域)
- `lark-cli docs` 命令前必须有 `+`(见坑 1)
- **`--as user` 是默认**——bot 身份看不到用户的云空间文档

## 解析源文档的标准流程

### Step 1:抓取 + 落盘原始

```bash
# Lark Docx 例子(其他源改对应命令)
lark-cli docs +fetch --api-version v2 \
  --doc "<URL>" --as user --doc-format markdown --scope full \
  > raw.json
```

**注意**:
- 解析 `raw.json` 用 `json.loads()`,content 字段是字符串,**里面有 `\\n` 是真换行的 JSON 转义**
- 写盘时**不要做二次解码**——Python 写文件时 `str(content)` 已经是 unicode 字符串,真换行已经在里面
- 文件里**应该看到真换行符** `\n` (0x0A),不是字面 `\n` (0x5C 0x6E)——错位就是解码搞错了

### Step 2:结构化 Q&A

源文档通常长这样:
```markdown
# 第一部分:整体规划

## 第一阶段

### 小梅沙片区前期规划设计阶段的合作方

答:深圳市城市规划设计研究院(简称"深规院")、阿特金斯中国...

### <下一个问题>?

答:...
```

**解析关键点(易踩坑)**:
- `### ` 是问题标题,**`### ` 后面到下一个 `### ` 或 `## ` 之间的所有内容**就是答案
- 答案**可能没有"答:"前缀**——必须兼容
- 答案**可能含表格 / 列表 / 多段**——保留 markdown 格式
- 附录可能用编号列表 `1. **公司名**\n\n答:...` 而不是 `### `——单独识别

**标准解析正则**:
```python
import re, json

# 主部分:### 问题
h3_pattern = re.compile(r'^### (.+?)$', re.MULTILINE)
# 答案到下一个 ## 或 ### 为止
all_h = list(re.finditer(r'^(#{1,3}) (.+?)$', text, re.MULTILINE))

qa_list = []
last_h1 = None
for i, m in enumerate(all_h):
    hashes, title = m.group(1), m.group(2).strip()
    if hashes == '###':
        # 找下一个 ## 或 ###
        next_pos = len(text)
        for nm in all_h[i+1:]:
            if nm.group(1) in ('##', '###'):
                next_pos = nm.start()
                break
        raw = text[m.end():next_pos].strip()
        raw = re.sub(r'^答[:：]\s*', '', raw).strip()
        if raw:
            qa_list.append({
                'h1': last_h1,
                'q': title,
                'keywords': extract_keywords(title),
                'a': raw,
            })
    elif hashes == '#':
        last_h1 = title
```

### Step 3:关键词抽取

```python
def extract_keywords(q_title):
    kws = []
    # 1) 抽取显式编号(地块号 / 楼栋号 / 区域号)
    land_codes = re.findall(r'\d{2}-\d{2}(?:-\d+)?', q_title)
    kws.extend(land_codes)
    # 2) 业务领域关键词库(根据源文档类型补)
    business_kws = ['规划', '设计', '建筑', '景观', '户型', '容积率', '合作方',
                    '样板房', '营销中心', '防水', '结构', '管线', ...]
    for bk in business_kws:
        if bk in q_title and bk not in kws:
            kws.append(bk)
    # 3) 公司名(若源文档涉及)
    company_kws = ['AECOM', '深规院', '欧博', ...]
    for ck in company_kws:
        if ck in q_title and ck not in kws:
            kws.append(ck)
    return kws
```

**核心原则**:关键词**从源文档反向抽**,不要凭直觉造。算法见上方"高频 + 业务词 + 公司名"三层。

## 验证(必做,不可省)

### V1:解析完整性

```python
# 主部分问答数 + 附录数 vs 源文档目录
assert sum(1 for x in qa if x['h1'] != '附录') >= 源文档目录里的"### 问题"数
assert sum(1 for x in qa if x['h1'] == '附录') == 源文档里"1. **公司**"数
```

**自我诊断规则**:
- 解析返回 0 条 → **先 debug,不要重跑同一段代码**——八成是切分点错了(`appendix_start` 取了目录里的而不是正文里的)
- 解析条数 < 源文档目录里看到的条数 → **检查"答:"前缀兼容性**——可能有一批答案没"答:"前缀,正则跳过了

### V2:触发演示

跑 3-6 个真实用户问题,模拟"关键词匹配 + 选最相关一条 + 截断到 30s":

```python
def find_best_match(question):
    scores = []
    for item in qa_list:
        score = sum(1 for kw in item['keywords'] if kw.lower() in question.lower())
        scores.append((score, item))
    scores.sort(key=lambda x: -x[0])
    return scores[:3] if scores else []
```

**验收标准**:
- ✅ 高频问题(地块号 / 知名公司 / 标准业务词)能匹配上
- ⚠️ 低频 / 长尾问题可能答非所问——**老实告诉用户精度局限**,给改进方向(向量检索 / 多关键词加权)

### V3:不污染主身份

**回到原 prompt,重新读一遍**,确认:
- 主身份段(目标 / 性格 / 语气)没动
- 长度限制没动
- 输出格式限制没动
- 只在末尾追加了"专项知识 · X"子模块
- 子模块里**身份边界句**写清楚(见上方标准结构)

## 踩坑清单(2026-09-11 实战沉淀)

### 坑 1:`lark-cli docs` 子命令前面必须有 `+`

`lark-cli docs fetch` → 报 `unknown subcommand "fetch"`,正确是 `lark-cli docs +fetch`(注意 `+`)。

**修复**:`lark-cli docs --help` 看完整列表,凡是 `<verb>` 形式的命令都带 `+`。

### 坑 2:`web_extract` 抓飞书公开 URL → 返回登录页 HTML,不是文档

```python
web_extract(['https://autolife.feishu.cn/docx/HjQhdR79DokDYKxy61ZcC1uMn8e'])
# 返回的是 {"title": "Feishu - Log in", ...} ← 不是文档内容
```

**根因**:飞书公司域文档必须登录态访问,`web_extract` 是无状态抓取,撞登录墙。

**修复**:
- **永远用 `lark-cli docs +fetch --as user`**——主人的飞书 user 身份能访问公司域
- `--as bot` 是错的——bot 看不到用户云空间文档
- 不要试 `--cookie` / `--header Authorization`——主人是用户,不是开发者凭据

### 坑 3:`lark-cli` 必须带 `--api-version v2`(2026-09 lark-doc v2.0 强制)

lark-doc skill v2.0 起,**`docs +fetch` / `+create` / `+update` 必须显式传 `--api-version v2`**,否则 v1 默认 API 调用格式不一定兼容新 schema。

**修复**:`lark-cli docs +fetch --api-version v2 --doc <URL> --as user`(永远带 v2)。

### 坑 4:`md.find('关键词')` 抓到目录里的同名词,不一定是正文

源文档通常结构:
```
# 目录
  ...附一:合作单位及其详细介绍...
# 第一部分...
  ...(没有"附一")...
# 附一:合作单位及其详细介绍   ← 真正的正文
  1. **公司1**\n\n答:...
```

**`md.find('附一:合作单位及其详细介绍')` 返回的是目录里那次出现的位置(更早),不是正文**。

**修复**:
```python
# 错:用 find 取第一个匹配
appendix_start = md.find('附一:合作单位及其详细介绍')

# 对:用 re.findall 取最后一个匹配,或 slice 排除目录段
positions = [m.start() for m in re.finditer(r'附一:合作单位及其详细介绍', md)]
appendix_start = positions[-1]  # 最后一次出现
```

**通用规则**:源文档里的"标志性章节名"出现 ≥ 2 次(目录 + 正文)时,**永远取最后一次匹配**。

### 坑 5:`re.search(r'^### ', text[pos+1:])` 会找到 `## ` 而非下一个 `### `(2026-09-11 实战)

```python
m = re.search(r'^### (.+?)$', text, re.MULTILINE)
pos = m.start()                    # ← pos 是 `###` 中 `#` 的位置
q_title = m.group(1).strip()
rest = text[pos+1:]                # ← 跳过 `#`,但剩下 `## <同标题>`!!!
end_match = re.search(r'^### |^## ', rest, re.MULTILINE)
# end_match 立刻命中,end_pos = pos + 1 + 0 = pos+1 → raw = "" → 0 条结果
```

**根因**:`### ` 三个字符,`pos` 指向第一个 `#`,`pos+1` 指向第二个 `#`,剩下 `## ` 立刻被"下一个标题"正则命中。

**修复**:**永远用 `m.end()` 而不是 `m.start()`+len** 作为切片起点。

```python
# 错:
raw = text[pos + len('### ') + len(q_title):end_pos].strip()
# 对(用 m.end() 跳过整个 "### " 前缀,或扫所有标题统一切):
all_matches = list(re.finditer(r'^(#{1,3}) (.+?)$', text, re.MULTILINE))
for i, m in enumerate(all_matches):
    if m.group(1) == '###':
        next_pos = len(text)
        for nm in all_matches[i+1:]:
            if nm.group(1) in ('##', '###'):
                next_pos = nm.start()
                break
        raw = text[m.end():next_pos].strip()  # ← m.end() 跳过 "### " 本身
```

### 坑 6:答案没有"答:"前缀时,正则要求"答:"会跳过

飞书文档常见两种风格:
- 风格 A:`### 问题\n\n答:答案内容`(95% 情况)
- 风格 B:`### 问题\n\n答案直接接在标题后`(5%,但每份文档都有几处)

只匹配风格 A 会**漏掉 5-20%** 的真实答案。

**修复**:`re.sub(r'^答[:：]\s*', '', raw).strip()` 兼容两种,而不是把"答:"当成匹配条件。

### 坑 7:附录用 `1. **公司**` 编号列表而不是 `### ` 标题

源文档结构:
```
# 主部分(用 ### 问题 + 答:)
...265 条问答...

# **附一:合作单位及其详细介绍**
1. **深圳市城市规划设计研究院**\n\n答:起步于1990年...
2. **阿特金斯中国**\n\n答:...
```

**只扫 `### ` 会漏掉整个附录**。

**修复**:附录用单独正则:
```python
unit_pattern = re.compile(
    r'^\d+\.\s+\*\*(.+?)\*\*\s*\n+(.+?)(?=\n\s*\d+\.\s+\*\*|\Z)',
    re.MULTILINE | re.DOTALL
)
```

### 坑 8:解析返回 0 条 → debug,不要重跑

我两次撞这个坑:重写一遍代码,把同一个 bug 跑了两遍,每次都返回 0。

**强制规则**:
- 解析返回 0 条 / 比预期少 → **加 debug 输出**,看每个循环变量实际是什么
- 不要"换个正则试试"——大概率**算法层面错了**(切分点 / 切片起点 / 文件本身)
- 不要"再跑一次"——结果一样

**Debug 三段**:
```python
print('文件大小:', len(text), '字符')
print('真换行数:', text.count('\n'))
print('### 出现次数:', len(re.findall(r'^### ', text, re.MULTILINE)))
print('appendix_start:', appendix_start, '(文件总长', len(text), ')')
print('主部分 ### 数:', len(re.findall(r'^### ', text[:appendix_start], re.MULTILINE)))
```

哪个数对不上预期,就是那一段错了。

### 坑 9:触发关键词必须从源文档**反向抽取**,不要凭直觉造

我直觉列了一组触发词("小梅沙/特发/03-01-1/户型/容积率..."),后来用 `Counter` 看实际高频词才发现:**真正的高频词是"设计/园林/规划/合作方/建筑/住宅"**——因为每个问题里都有这些词。

**修复**:
```python
from collections import Counter
kw_freq = Counter()
for item in qa_list:
    for kw in item['keywords']:
        kw_freq[kw] += 1
# 取 top 30-40
top_kws = [kw for kw, cnt in kw_freq.most_common(40)]
```

**结合业务常识过滤**:把"问/答/是什么"这种废词过滤掉,留下"项目名/地块号/公司名/业务词"。

### 坑 10:`unicode_escape` 不要对中文 JSON 解码

```python
content_decoded = codecs.decode(content, 'unicode_escape')
# 中文变乱码:'<title>20221031å°æ¢æ²é¡¹ç®éå®ç¾é®1.0çæ¬</title>'
```

**根因**:`unicode_escape` 把 `\uXXXX` 转成 unicode,但对**已经是 unicode 的字符串**会再编码一次,把中文当成 `\u` 形式处理。

**修复**:用 `json.loads()` 一次性解码整个 JSON 字符串(content 字段已经在 JSON 里被转义了)。

```python
d = json.loads(res.stdout)
content = d['data']['document']['content']  # ← 已经是 unicode 字符串
pathlib.Path('out.md').write_text(content, encoding='utf-8')  # ← 直接写
```

### 坑 11:f-string 不能含反斜杠(2026-09-11 实战)

```python
print(f'附录编号数: {len(re.findall(r"^\d+\.\s+\*\*", appendix, re.MULTILINE))}')
# SyntaxError: f-string expression part cannot include a backslash
```

**修复**:把正则提到变量里,或者拆成两行:
```python
pat = r'^\d+\.\s+\*\*'
print('附录编号数:', len(re.findall(pat, appendix, re.MULTILINE)))
```

### 坑 12:解析精度不够是知识架构问题,不是 bug

触发演示里**有答非所问的场景**(问"整体规划定位"答"规划设计合作方")——这不是解析错了,是**关键词匹配精度不够**。

**修复方向**(按精度/成本排):
- **A. 关键词加权**——给地块号 / 公司名高权重,业务词低权重,10 分钟搞定
- **B. 双路召回**——关键词粗排 + LLM 重排,半小时
- **C. 向量检索**——embedding + 向量数据库,精度最高但要 embedding 模型(主人机器上有 chromadb 可用)

**用户场景不需要高精度的老实交代**:前台接待场景,访客问得不深,关键词匹配够用。**告诉用户精度局限和 3 个改进方向,让用户选**——不要默认做最复杂的。

## 触发信号

- 用户给一段"销售百问 / 常见问题 / FAQ / 产品手册" + 说"加进 prompt / 让机器人知道 / 喂给机器人"
- 用户给飞书 / Notion / 文档 URL + 说"提取问答"
- 用户已经有机器人 prompt,想给机器人**新增一个领域知识源**(但不破坏主身份)
- 用户说"机器人答不上 X,需要补充知识"

## 联动 skill

- `lark-doc` —— 飞书 Docx 抓取 + 编辑(本 skill 是它的下游消费者)
- `lark-shared` —— 飞书认证 / `--as user` 选择
- `huihui-writes` —— 如果用户要求"重写答案措辞"或"翻译",用主人级写作引擎
- `self-improving-agent` —— 这次任务里踩到的坑要进 `.learnings/`
- 主人 SOUL / USER 偏好(2026-09-11)—— 主人"cancel clarify"语义 / 数字选项回复 / 简洁有温度

## 输出检查清单(写完所有产物后,逐项 ✅)

- [ ] 主部分问答数 ≥ 源文档目录里 `### 问题` 数
- [ ] 附录单位数 = 源文档里 `1. **公司**` 数
- [ ] 触发关键词清单已生成(从源文档反向抽,高频 + 业务词)
- [ ] 最终 prompt 保留了原主身份段(目标/性格/语气/长度限制)
- [ ] 子模块包含"身份边界句"——防止机器人跑偏身份
- [ ] 子模块包含"瞎编门禁"——禁止 LLM 编造
- [ ] 归档路径指向真实存在的文件
- [ ] 3-6 个真实问题触发演示跑过,精度局限已老实交代给用户
