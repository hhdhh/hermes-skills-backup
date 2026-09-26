---
name: robot-content-deploy
description: Use when (1) 主人公司机器人需要热加载 prompt/RAG/配置 (2) 主人说'把 X 塞进机器人...
metadata:
  hermes:
    tags: [robot, edge-device, ros2, conda, cython, ssh, prompt-injection, rag, autolife]
    related_skills:
      - network-troubleshooting-ssh
      - lark-doc
      - huihui-absolute-gating
---

# robot-content-deploy — 机器人公司远程内容注入 Playbook

> 完整描述：机器人公司场景下，给 ROS2 / conda / Cython .so 后端的边缘机器人远程注入 prompt / RAG / 配置的标准流程。覆盖 SSH 密码交互（没装 sshpass 时的 Python pty.fork）、base64 流式替代 scp 失败、运行时 prompt/RAG 文件定位、Cython 编译 .so 的 strings+grep 审计、文件备份与 md5 校验、注入策略（直接替换 prompt vs 摘要塞入 vs 启用真 RAG）、主人 ABSOLUTE 模式下的拍板节奏。Use when (1) 主人公司机器人需要热加载 prompt/RAG/配置 (2) 主人说'把 X 塞进机器人 prompt'/'给机器人加知识库'/'改机器人回答' (3) 跨 SSH 给 ROS2/conda 后端的 Linux 设备写文件 (4) 主人说'配置好一切' + 远程机器人场景。

> **核心定位**：机器人公司（智动未来/类似）场景下，远程给 ROS2 + conda env + Cython 编译 .so 的边缘机器人推送内容（prompt / RAG 知识库 / 配置）的标准流程。一次建立，每次产品迭代都复用。

## 与已有 skill 的关系

- **`network-troubleshooting-ssh`**：管 SSH 本身连不上/认证失败的诊断；本 skill 假设 SSH 已通（主人给了 IP + 密码），专注"怎么把内容传过去、写到哪、怎么验证"。
- **`lark-doc`**：管飞书文档读取与编辑；本 skill 消费 lark-doc 拿到的 XML/JSON 文档内容做下游结构化处理（Q&A 抽取等）。
- **`huihui-absolute-gating`**：本 skill 假设主人在 ABSOLUTE 模式——主人说"塞进去" = 直接注入，"先备份" = 自动备份，"不动服务" = 不重启。

## 文件清单

| 文件 | 用途 |
|---|---|
| `SKILL.md`（本文件） | 5 步标准流程 + 注入策略表 + 9 大坑 |
| `references/ssh-no-sshpass-recipes.md` | 4 种无 sshpass 时的 SSH 文件传输方案对比与 Python pty.fork 完整代码 |
| `references/cython-so-audit.md` | 如何 strings + grep + nm 审计 Cython 编译的 .so 文件，找调用点与配置 |
| `references/prompt-injection-strategies.md` | 4 种注入策略（直接替换 / 摘要塞入 / 真 RAG / Cython 注入）的对比表与选型决策树 |
| `references/feishu-qa-xml-parse.md` | 飞书 docx XML 转结构化 Q&A 的完整解析模板（h3 seq-marker 模式） |
| `scripts/scp_via_base64.sh` | `cat local | base64 | ssh 'base64 -d > remote'` 流式推送小到中等文件（<5MB）的可复用脚本 |

## 何时用

| 触发 | 动作 |
|---|---|
| 主人说"把飞书 Q&A 塞进机器人 prompt"/"给机器人加知识库"/"改机器人回答" | 走本 skill 5 步流程 |
| `ssh user@host "密码"` 时没装 sshpass/expect/paramiko | §step 1 走 SSH 工具 + `references/ssh-no-sshpass-recipes.md` |
| 主人公司机器人用 ROS2 + conda env + 编译过的 .so，找不到 prompt/RAG 文件 | §step 3 走 Cython .so 审计（`references/cython-so-audit.md`） |
| 主人说"配置好一切"/"塞进去"/"做" | 走 ABSOLUTE 模式，不反问选档，直接动手 |
| 主人说"只写文件不重启" | 写完停手，主动给主人启动命令，**不要主动 systemctl restart** |
| prompt 改动涉及多份（备份、原版、新版） | §step 4 三重备份 + md5 校验 + 内容抽样核对 |

## 5 步标准流程

### Step 1 · SSH 工具准备（先决条件）

主人给 SSH 信息（IP + 用户 + 密码）→ **先尝试通用工具，失败再 fallback**：

| 工具 | 适用 | 命令 |
|---|---|---|
| `sshpass` | Linux 上首选（apt 一行装） | `apt install sshpass && sshpass -p 'pwd' ssh user@host cmd` |
| `ssh` + `expect` | macOS 上 expect 通常预装 | `expect -c "spawn ssh user@host cmd; expect password; send \"pwd\r\"; expect eof"` |
| `ssh` + Python `pty.fork` | **任何 Python 环境**，没装第三方 | 见 `references/ssh-no-sshpass-recipes.md`（本 skill 默认 fallback） |
| `scp` 直接传 | 大文件 > 5MB，且工具齐全 | `scp -o StrictHostKeyChecking=no local user@host:remote` |

**永远带**：`-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`（避免首次连的 fingerprint 确认卡死）

**永远先 ping 验证网络**：主人给 IP 后，第一步 `ping -c 1 -W 2 <ip>` 确认通。

### Step 2 · 侦察：定位运行时文件

机器人公司软件架构典型形态：

| 层 | 路径模式 | 找什么 |
|---|---|---|
| **开发源码** | `~/Documents/<PkgName>/assets/prompt/` | 看到的可能是开发副本，**未必运行时用** |
| **运行时（conda env 内）** | `~/miniconda3/envs/<env>/lib/python3.X/site-packages/<PkgName>/assets/prompt/` | **真正加载的文件**，grep pkg `__init__.py` 看 `PROMPT_PATH = pathlib.Path(...)` |
| **systemd user service** | `~/.config/systemd/user/<service>.service` | 看 `ExecStart=` 决定启动的是哪个 main 包 |
| **运行时进程** | `ps -ef \\| grep -i <pkg>` | 确认现在跑的是哪个（开发版 vs 装版） |

**4 步侦察流程**（**重要**：主人文件备份前必做）：
1. **找运行时目录**：`grep -rn "PROMPT_PATH\\|KNOWLEDGE_PATH" <pkg>/__init__.py`
2. **找运行时进程**：`ps -ef | grep <pkg>`
3. **找启动 service**：`ls ~/.config/systemd/user/*.service` + `grep ExecStart=`
4. **交叉核对**：跑着的进程用的路径 ≠ Documents 下的开发副本 ≠ .so 里的字面路径。**以 conda env 里那个为准**。

### Step 3 · 决策：注入策略选型

| 策略 | 适用 | 工作量 | 风险 |
|---|---|---|---|
| **A. 维持现状 / 只换文件** | prompt 已经有完整版，只是被精简了 | 0（备份+替换） | 无 |
| **B. 摘要塞入 prompt** | 知识库内容可控（< 100KB），实时 LLM 上下文够大 | 1-2h（解析+组装+备份+替换） | prompt 变大 → 实时 LLM 成本/延迟上升；摘要可能漏细节 |
| **C. 旁路补丁（独立服务）** | 主流程不能改，需要在 ASR/TTS 之间插一层 | 半天 | 与现有 pipeline 冲突风险 |
| **D. 启用真 RAG（embedding + 向量检索）** | 知识库大（> 200KB），需要语义检索 | 半天-1天 | 需要 API key + 主流程改 + 重启 |

**选型决策树**：

```
机器人有现成 RAG 模块且主流程调用？
├─ 是 → 用 D（启用真 RAG）
└─ 否 → 知识库大小？
        ├─ < 100KB → 用 B（摘要塞入 prompt）
        └─ > 200KB → 用 C（旁路补丁）或 D（启用真 RAG）
```

**最容易踩的坑**（**绝对先验证再动手**）：
- grep 包里 `KnowledgeRetriever` / `load_rag` / `rag.txt` 等关键字 → **没引用 = RAG 模块装了但没启用**（这次主人场景的真实情况）
- 看 `.so` 里的函数符号（`nm` + `strings`）找主流程调用
- **关键诚实**：发现"功能存在但没启用"时，**主动告诉主人而不是假装能做**

### Step 4 · 备份 + 替换 + md5 校验

**永远做三重备份**（避免覆盖损失）：

```bash
# 三重备份（按时间戳）
cp prompt.txt prompt.txt.bak.before-b.$(date +%Y%m%d%H%M%S)
cp prompt.txt.bak.capsule.20260911 prompt.txt.bak.original-2972B.20260911
# 替换
cp staging/prompt.txt.new prompt.txt
# 校验
md5sum prompt.txt staging/prompt.txt.new   # 应一致
```

**校验三层**（不只是 md5）：
1. **md5 一致**（本地 vs 远端 vs staging）
2. **字节数 / 行数 / 关键行（grep -c "^问："）一致**
3. **头尾抽样肉眼对**（`head -10` + `tail -3` 贴出来）

### Step 5 · 报告 + 等主人拍板是否重启

主人说"只写文件不重启"——**就只写到 Step 4**，**不要 systemctl restart**。然后主动给：

1. **做了什么清单**（哪些文件被替换、备份、保留）
2. **重启命令**（精确路径 + 服务名）让主人自己执行：
   ```bash
   # 找到启动 kiosk 的 service
   grep -l "kiosk" ~/.config/systemd/user/*.service
   # 重启
   systemctl --user restart <service-name>
   ```
3. **回滚命令**（从备份恢复）：
   ```bash
   cp prompt.txt.bak.original-2972B.20260911 prompt.txt
   systemctl --user restart <service-name>
   ```
4. **潜在风险**（成本/延迟/精度）

## ⚠️ 坑表（必读）

### K1 · Documents 副本 ≠ 运行时副本

**主人公司机器人通常有 `~/Documents/<PkgName>/`（开发）+ `~/miniconda3/envs/<env>/lib/python3.X/site-packages/<PkgName>/`（conda 装）两份**。Documents 里的 prompt 是开发副本，**机器人运行时加载的是 conda 里那个**。改了 Documents 没用，改 conda 才有用。

- **解决**：永远在 Step 2 跑 `grep -rn "PROMPT_PATH" <conda_pkg>/__init__.py` 锁定真实路径
- **验证**：`fuser <prompt.txt>` 看哪个进程打开了它 / `ps -ef | grep pkg` 看跑的是哪个环境

### K2 · Cython 编译的 .so 文件看不见源码

机器人包用 Cython 编译 .so（性能 + 防代码泄露）—— `.py` 没了，但 **`.so` 里所有字符串、函数签名、模块路径都在**。要看代码：

```bash
# 找所有字符串
strings path/to/module.cpython-312-x86_64-linux-gnu.so | grep -iE "prompt|rag|knowledge|workspace"

# 看所有模块路径（确认哪个 .so 对应哪个 .py）
strings path/to/module.cpython-312-x86_64-linux-gnu.so | grep "^src/"

# 找函数签名（PyInit_xxx 是模块入口）
nm -D path/to/module.cpython-312-x86_64-linux-gnu.so 2>/dev/null | grep -i "Workspace\|Knowledge"
```

`.so` 字符串通常会暴露关键信息：`PROMPT_PATH = '{ASSETS_ROOT}/prompt/prompt.txt'`、`KnowledgeRetriever(openai_client, knowledge_file_path, model='text-embedding-v4')` 等。

### K3 · .so 有定义 ≠ 主流程调用

最常见的"假装能做"陷阱：`.so` 里 `KnowledgeRetriever` 类有完整定义，但主流程根本 `import` 它也没 `call` 它——RAG 是预留 API，从未启用。**改了 rag.txt 没任何效果**，因为没人读。

- **解决**：grep `KnowledgeRetriever` / `rag.txt` / `load_rag` 在整个包源码（排除 .so 和 __pycache__）—— 0 引用 = RAG 没启用

### K4 · 脚本里的文件名 ≠ 代码里的文件名

包内提供的 `scripts/ai_tools/generate_kb_embedding.py` 写 `EMBEDDING_SAVE = "kb_embeddings.json"`，但 `__init__.py` 里 `KB_EMBEDDINGS_PATH = "knowledge.vec.jsonl"`——**别照搬脚本路径**。以 `__init__.py` 里的 `pathlib.Path(...)` 为准。

### K5 · 大文件的 scp 密码交互陷阱

`scp` 在 subprocess.run 里传 `input=PWD + "\n"` 不被读取（scp 不读 stdin 密码，走 ssh-askpass）→ `Permission denied`。**fallback**：`base64 -d > remote < <(base64 local)` 流式推：

```bash
# 本地分块
base64 local | split -b 70000 - chunk_
# 远端拼
ssh user@host "cat chunk_* | base64 -d > remote && rm chunk_*"
```

**Python pty.fork 模式**（推荐，所有 SSH+scp 场景通用）：见 `references/ssh-no-sshpass-recipes.md`。

### K6 · "30s 长度限制"是讲输出，不是 prompt 输入

主人原 prompt 写"每轮对话回答严格控制在 30s 以内"——这是**机器人回答**长度限制，**不是 system prompt 大小限制**。Q&A 摘要塞进 prompt（22KB+ / 26K token）对实时 LLM 上下文完全 OK，但每轮对话都带 26K token → 成本/延迟约 +13x。这是选 B 策略的可接受代价，要主动告诉主人。

### K7 · prompt 里要加"使用规则"

主人原 prompt 严禁 Markdown / 加粗 / 列表，但飞书 Q&A 答案里大量编号列表、加粗词。**塞进 prompt 时必须加 6 条使用规则**：

```
使用规则：
1. 客人提问涉及 X 时，请优先从下方问答中检索答案
2. 严格根据问答内容作答，不得编造未出现的数字/品牌/合作单位
3. 答案里有"……（详见原始资料）"说明资料较长，请简洁概括前段要点
4. 找不到答案时，礼貌说明 + 主动转介
5. 回答时不要照搬整个段落，提炼成自然口语化的一段或几句话
6. 严禁 Markdown 加粗符号/项目编号格式（但可引用原文里的数字编号如"6 班幼儿园"）
```

不写规则 → 机器人会"完整背诵"答案 → 30s 超时。

### K8 · 长答案必须按句号/分号/换行截断

简单 `text[:200]` 会切断在词中间。**smart_truncate** 逻辑：

```python
def smart_truncate(text, max_chars=250):
    text = text.strip().lstrip('答:').lstrip('答：').strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in ['。', '；', '\n', '，', '、']:
        idx = cut.rfind(sep)
        if idx > max_chars * 0.6:  # 不要截得太短
            return text[:idx+1] + "……（详见原始资料）"
    return cut + "……（详见原始资料）"
```

**截断标记统一用 "……（详见原始资料）"**——机器人看到就知道"前段是重点，不要复读整个原段落"。

### K9 · ABSOLUTE 模式下的拍板节奏

主人在 ABSOLUTE 模式下拍板时常给 4 句话一次性说完（"切换 X 模式 + 只 Y 不 Z + 保留 + 追加 + 全部塞"）。**不要追问**——直接列你的设计：

1. **复述主人意图**（让他知道你没听错）
2. **列你的执行计划**（4-6 步）
3. **说明每个策略的代价**（一句话）
4. **等"动手"/数字回复**才执行

**永远不要说"如果你同意上面默认"**——那是把决策权甩回给主人。直接说"我按 X 动手，做完报告"。

## 主人 ABSOLUTE 模式话术模板

```
主人说"把飞书 Q&A 塞进机器人 prompt"：

1. 第 1 句：复述意图 + 列 4 步计划
   "主人，我按 4 步走：解析 Q&A → 备份原文件 → 写入机器人 → 报告不重启。
    飞书 265 条 + 摘要策略 = prompt 大约 22 KB（26K token 输入），你能接受吗？"

2. 第 2 句：让主人补 3 个细节（一次性问完，不分多轮）
   "请告诉我：(a) 替换哪个 prompt 版本？(b) RAG 要不要真启用还是只写文件？
    (c) 备份策略：覆盖原文件还是另起新文件名？"

3. 拿到答案后：直接动手

4. 完成后：做了什么 + 重启命令 + 回滚命令 + 潜在风险
```

## 验收 checklist（每次部署完必跑）

```
[  ] SSH 通：ping <ip> -c 1 成功
[  ] 运行时路径锁定：grep -rn "PROMPT_PATH" <conda_pkg>/__init__.py 拿到唯一路径
[  ] 备份存在：ls <target_dir>/prompt.txt.bak.* 至少 1 份
[  ] md5 校验：本地 staging 文件 md5 = 远端文件 md5
[  ] 内容抽样：head -5 / tail -3 远端文件 vs 本地 staging 一致
[  ] grep 关键行：grep -c "^问：" 远端文件 = 本地 staging 一致
[  ] 重启命令已就位：systemctl --user restart <service-name> 等主人执行
[  ] 回滚命令已就位：cp *.bak.original-XXXXX prompt.txt 已验证路径
[  ] 风险已告知：成本/延迟/精度影响已报告主人
```

---

_2026-09-11 智动未来 AutoLife S1 机器人首次 prompt+RAG 注入 session 沉淀_
_护栏：永远备份 · 永远 md5 · 永远不擅自重启 · 永远告诉主人"做了什么 / 重启命令 / 回滚命令 / 风险"_
