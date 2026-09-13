---
name: autolife-robot-prompt-ops
version: 1.0.0
description: "智动未来 AutoLife S1 机器人的 prompt/RAG 修改流程。Use when 主人要求修改机器人 system prompt、增删 RAG 知识库、把飞书/文档转 Q&A 加入机器人。从远端读取 prompt/rag，按主人给的 4 档方案（A维持/B拼接/C补丁/D真RAG）执行。"
metadata:
  requires:
    bins: ["ssh", "lark-cli"]
  triggers:
    - "修改机器人 prompt"
    - "机器人加 Q&A"
    - "小梅沙问答加入机器人"
    - "autolife prompt"
---

# AutoLife S1 机器人 prompt/RAG 修改流程

> **目标机器人**：按机号定位（274），IP 不固定——首选 `python3 ~/.hermes/skills/autolife-find-robot/scripts/find-autolife.py`（DNS PTR 秒级、免凭证，自动回写 robots.json），兜底 `robssh.py ip 274`（hostname `autolife-robot-274`，SSH 用户 `ubuntu`）
> **跑的服务**：`autolife_robot_kiosk.main`（由 `logo-backend.service` 拉起，env=`robot_env`）
> **加载路径**：`autolife_robot_vision.assets.prompt.prompt.txt`（通过 `workspace.workspace.load_base_prompt()`）
> **重启命令**：`systemctl --user restart logo-backend.service`（**默认不动**，等主人下令）

## 远端关键路径（机器人上）

| 路径 | 作用 |
|------|------|
| `~/.huihui-staging-YYYYMMDD-HHMMSS/` | 中转 staging 目录（按时间戳建） |
| `~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/assets/prompt/prompt.txt` | **运行时 system prompt**（直接读） |
| 同目录 `rag.txt` | **运行时未使用**（grep 验证过 KnowledgeRetriever 没被调用，详见下方"重要发现"） |
| 同目录 `prompt.txt.example.capsule_salesperson` (19KB) | 商品售卖 prompt 模板 |
| 同目录 `prompt.txt.example.langham` (41KB) | 朗廷酒店 prompt 模板 |
| 同目录 `prompt.txt.example.qwen` (7KB) | Qwen LLM 适配模板 |
| `~/.config/systemd/user/logo-backend.service` | kiosk 启动单元 |

## 重要发现（2026-09-11 验证）

1. **`rag.txt` 没人调用**：vision/kiosk 包里 grep 不到任何 rag.txt 引用
2. **真 RAG 文件**：`knowledge.jsonl` + `knowledge.vec.jsonl`（schema: `{id, topic, content, embedding}`，embedding 模型 `text-embedding-v4` 即 DashScope）。**这两个文件从来没生成过 → RAG 从未启用**
3. **`KnowledgeRetriever` 是 .so 编译的**（`audio/knowledge_retrieval.cpython-312-x86_64-linux-gnu.so`），但 vision 包里没人 import 它
4. **`workspace` 模式**：`workspace.cpython-312-...so` 里的 `WorkspaceFactory.create_workspace()` 从服务端拉 workspace_id，本地 `prompt.txt` 是"无 workspace" 模式（`load_base_prompt` 直接读）
5. **当前活跃 prompt**：2972 字节（小智前台接待员版，主人 prompt1.txt 原版），不是 `prompt.txt.example.capsule_salesperson` 的 19KB 商品版
6. **重启生效**：`systemctl --user restart logo-backend.service`（kiosk 进程 PID 4131），~3-5 秒后新 prompt 生效

## 4 档方案（主人拍板用）

主人每次给"加 Q&A"任务，先汇报机器人现状 + 提 4 档选项，让主人选档：

| 档 | 说明 | 工作量 | 适用 |
|----|------|--------|------|
| **A 维持现状** | 只换 prompt.txt + rag.txt，RAG 不会生效 | 30 分钟 | 主人只是要"占位"或测试 |
| **B 拼接到 prompt** ⭐ | 把 Q&A 摘要塞进 prompt.txt 的"知识库"段，机器人基于 prompt 回答 | 1 小时 | 主人最常用档，单次 Q&A 量小（<300 条）|
| **C 对话补丁** | 写独立 Python 服务做关键词匹配 RAG（命中返固定答案，否则透传给机器人） | 半天 | 不想改机器人代码、不想 prompt 变大 |
| **D 真 RAG 启用** | 写 `knowledge.jsonl` → DashScope embedding 生成 `knowledge.vec.jsonl` → 在主流程插 KnowledgeRetriever | 半天-1 天 | Q&A 量 > 500 条或需语义检索 |

默认推荐 B（性价比最高）。

## 标准流程（按"先侦察后动手"原则）

### Step 1: 读主人给的输入
- 主人贴的原始 prompt 文件（如 `prompt1.txt`）
- 飞书/Markdown/Word 形式的 Q&A 文档 URL 或本地文件

### Step 2: 解析 Q&A 文档
- 飞书 docx 用 `lark-cli docs +fetch --api-version v2 --doc <URL>`，XML 输出，提取所有 `<h3 seq-marker="X.Y">` 作为问题标题，下方 `<p>` 作为答案
- Markdown 按 `## ` / `### ` 标题分级
- 表格（飞书常含经济指标）保留为多行答案

### Step 3: SSH 上机器人侦察（**没侦察不许动手**）
```bash
# 用 pty+fork 绕过 ssh 密码交互（python -c 'import pty,os,select,time; ...'）
# 必须确认的 4 件事：
# 1. 哪个 prompt.txt 是运行时用的
# 2. rag.txt 是否真被调用
# 3. 启动 kiosk 的 systemd 服务名
# 4. workspace 模式（capsule/restaurant/无）
```

侦察命令清单：
```bash
ls -la /home/ubuntu/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/assets/prompt/
find /home/ubuntu/miniconda3/envs/robot_env/lib/python3.12/site-packages -name "*.so" -path "*workspace*" -o -name "*.so" -path "*knowledge_retrieval*"
strings <knowledge_retrieval.so> | grep -iE "rag|knowledge|embedding|kb_emb|prompt|jsonl"
grep -rn -E "prompt\.txt|rag\.txt|knowledge\.vec|knowledge\.jsonl|KnowledgeRetriever|load_base_prompt" <vision pkg> 2>/dev/null
grep -l "autolife_robot" /home/ubuntu/.config/systemd/user/*.service
```

### Step 4: 写本地组装产物（不上机器人）
- 组装新 prompt.txt（按主人选的方案）
- 组装新 rag.txt（如果主人选 A/B 都写，方案 D 才用 knowledge.jsonl）
- 备份所有原文件到 staging（不上机器人前不破坏）

### Step 5: 上传机器人（base64 流式 SSH 传，不用 scp 因为密码交互烦）
- **scp + stdin 不行**（密码不读 stdin）
- **方案**：base64 编码 → 分块（7 万字符/块）→ `ssh ... 'echo -n ... > file.b64'` → `ssh ... 'base64 -d file.b64 > file'`
- **每次传完立即 md5sum 校验**，本地 md5 必须 == 远端 md5

### Step 6: 备份原文件 + 替换
- 三重备份原 prompt：`(1) .bak.capsule.YYYYMMDD / (2) .bak.original-2972B.YYYYMMDD / (3) .bak.before-b.YYYYMMDDHHMMSS`
- 备份原 rag：`.bak.YYYYMMDD`
- `cp -v staging/prompt.txt.new2 <target>/prompt.txt`
- **再 md5sum 校验**
- **不重启**，等主人下令

### Step 7: 汇报 + 等主人重启指令
- 列出所有改动文件 + 备份路径 + md5
- 给出 `systemctl --user restart logo-backend.service` 命令（不执行）
- 给出回滚命令：`cp prompt.txt.bak.original-2972B.YYYYMMDD prompt.txt && systemctl --user restart logo-backend.service`
- 说明预期影响（如 B 档会增加 13x token 成本）

## SSH 流式 base64 传输模板（已验证可用）

```python
import pty, os, select, time, base64

def ssh_run(host, user, password, cmd, timeout=30):
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("ssh", ["ssh", "-o", "StrictHostKeyChecking=no",
                           "-o", "UserKnownHostsFile=/dev/null",
                           f"{user}@{host}", cmd])
        os._exit(127)
    out = b""
    sent = False
    end = time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try:
                chunk = os.read(fd, 4096)
                if not chunk: break
                out += chunk
                if not sent and b"password:" in out.lower():
                    os.write(fd, (password + "\n").encode())
                    sent = True
            except OSError: break
        try:
            waited_pid, status = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                try: out += os.read(fd, 65536)
                except OSError: pass
                return out.decode("utf-8", errors="replace"), status
        except ChildProcessError: break
    try: os.kill(pid, 9)
    except OSError: pass
    return out.decode("utf-8", errors="replace"), -1

# 上传文件
def upload_via_b64(host, user, pwd, local_path, remote_path, chunk=70000):
    with open(local_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    chunks = [b64[i:i+chunk] for i in range(0, len(b64), chunk)]
    ssh_run(host, user, pwd, f"rm -f {remote_path}")
    for idx, c in enumerate(chunks):
        op = ">" if idx == 0 else ">>"
        ssh_run(host, user, pwd, f"echo -n '{c}' {op} {remote_path}.b64")
    ssh_run(host, user, pwd, f"base64 -d {remote_path}.b64 > {remote_path} && rm {remote_path}.b64")
    ssh_run(host, user, pwd, f"md5sum {remote_path}")
    local_md5 = __import__('hashlib').md5(data).hexdigest()
    # 调用方负责校验
    return local_md5
```

## B 档 prompt 组装模板（已验证可用）

```python
# 1. 读主人原 prompt (1204 字符 / 2972 B)
# 2. 读飞书 Q&A JSON（已解析的 [{seq, question, answer}])
# 3. 摘要 + 截断
def smart_truncate(text, max_chars=250):
    text = re.sub(r'^答[:：]\s*', '', text.strip())
    if len(text) <= max_chars: return text
    cut = text[:max_chars]
    for sep in ['。', '；', '\n', '，', '、']:
        idx = cut.rfind(sep)
        if idx > max_chars * 0.6:
            return text[:idx+1] + "……（详见原始资料）"
    return cut + "……（详见原始资料）"

# 4. 组装新 prompt（原 prompt + Q&A + 使用规则）
# 原 prompt 末尾"你的知识库"段替换为：
NEW_KB_SECTION = """# 你的知识库

## 公司基础信息
智动未来成立于2023年底...（原版内容）

## 小梅沙项目销售百问
（资料截至2022年10月31日，共 N 个常见问题）

使用规则：
1. 当客人提问涉及...请优先从下方问答中检索答案。
2. 严格根据问答内容作答，不得编造未在问答中出现的数字、人名、合作单位、品牌或奖项。
3. 如问答中有"……（详见原始资料）"，说明资料较长，请简洁概括前段要点。
4. 若客人问的问题在下方问答中找不到答案，礼貌说明"这个我暂时没有详细信息，建议咨询项目方"。
5. 回答时不要照搬整个问答段落，要提炼成自然口语化的一段或几句话，符合 30 秒输出限制。
6. 严禁使用 Markdown 加粗符号或项目编号格式（但可以自然引用原文里的数字编号如"6 班幼儿园"）。

"""

# 5. 拼 Q&A
qa_lines = []
for q in qa_list:
    qa_lines.append(f"问：{q['question']}\n答：{smart_truncate(q['answer'])}")
qa_text = "\n\n".join(qa_lines)

new_prompt = original_prompt_until_kb + NEW_KB_SECTION + qa_text + "\n"
```

## 飞书 Q&A 解析模板

```python
import re, json

# lark-cli docs +fetch --api-version v2 --doc "https://xxx.feishu.cn/docx/XXX"
# raw 是 JSON，提取 "content" 字段的 XML
xml = json.loads('"' + raw_content.replace('\\"', '\x00').replace('\x00', '\\"') + '"')

# 找 h2/h3 标题
heads = []
for m in re.finditer(r'<(h2|h3)[^>]*seq-marker="([^"]+)"[^>]*>([^<]+)</\1>', xml):
    heads.append({"tag": m.group(1), "seq": m.group(2), "title": m.group(3).strip(),
                  "start": m.start(), "end": m.end()})

# 对每个 h3，往后取所有 <p> 直到下一个 h2/h3
qa = []
for i, h in enumerate(heads):
    if h["tag"] != "h3": continue
    next_start = heads[i+1]["start"] if i+1 < len(heads) else len(xml)
    seg = xml[h["end"]:next_start]
    paras = re.findall(r'<p[^>]*>(.*?)</p>', seg, re.S)
    cleaned = [re.sub(r'<[^>]+>', '', p).replace('&amp;','&').replace('&quot;','"').strip()
               for p in paras]
    answer = "\n".join(c for c in cleaned if c).strip()
    qa.append({"seq": h["seq"], "question": h["title"], "answer": answer})
```

## 安全边界

- ❌ **不擅自重启** robot 服务（master 已多次授权"只写不重启"，reboot 类需明确确认）
- ❌ **不删除** 备份文件（保留至少 90 天）
- ❌ **不修改** systemd 服务单元
- ❌ **不替换** prompt.txt.example.* 模板
- ✅ prompt 变大前估算 token（中文 1 字 ≈ 1.5 token），超 50K 主动提醒主人
- ✅ 每次改动三重备份 + md5 校验
- ✅ staging 目录保留在机器人上（方便回查）
- ✅ 主人说"动"才 `systemctl restart`

## 已知坑

1. **scp + stdin 不通密码** — 必须用 pty+fork + base64 流式（上面有模板）
2. **base64 分块不要超 70K** — `echo -n '...'` 命令行长度限制
3. **`prompt.txt.example.capsule_salesperson` 不是当前 prompt** — 不要按它的 19KB 大小估算
4. **KnowledgeRetriever 没启用** — A 档只换 rag.txt 是无效操作，主动告知主人
5. **workspace 有 capsule/restaurant 模式** — 但当前机器人用默认模式（`load_base_prompt` 直接读 prompt.txt），换工作场景要慎重
6. **conda env 名是 robot_env 不是 robot** — `conda activate robot_env` 才能进

## 最近一次执行记录（2026-09-12 · autolife-robot-309）

- 任务：小梅沙项目销售百问 → 机器人知识库 + 人脸迎宾 + 精度迭代
- 最终版本：**v10-reading**（md5 `9ea681d65ab392e2e5a732fdacdec773`，122042 B，~48K token）——**主人现场测试通过"非常完美"**
- 数据源：主人提供的 docx 原件（265 条 Q&A + 10 个表格，比飞书版表格更全）

## prompt 版本演进史（v1→v10，关键路径）

| 版本 | 改动 | 结果 |
|------|------|------|
| v1 (B档初版) | 原 prompt + 265 条平铺（250字截断） | 检索不准、答相似问题 |
| v2 | 删"身份确认"反问 + 答短规则（治"是在和我说话吗"×6次） | ✅ 反问消失 |
| v3 | 每条加 [关键词] 前缀 + 规则0"默认小梅沙" | 部分改善 |
| — | settings: `enable_hybrid_vad=true`（视觉+音频融合断句） | ✅ ASR 断句变稳 |
| v5 | 按 20 章节分组 + Q编号 + 51 个重复条目打住宅/商墅标签 + 防混淆规则 | ✅ 相似问题混淆大减 |
| v6-full | 每条加「核心：」行（数字句前置）+「另问：」口语变体 + docx 表格全量 + 截断放宽到 500 字（精度优先） | ✅ 数字类精准 |
| v7 | 高频速查卡（人工精选，头部注意力区）+ 版本标识 + 防编造规则（物业费/绿化率/交付/学校/售价文档里没有→严禁编造，引导咨询销售顾问）+ 精细澄清策略 | ✅ 稳定基线 |
| v8 | ❌ 硬字数限制（两句话/50字）+ 裸数字示范 + 四连禁令 | **失败**：过度矫正，对话破碎不可用，已回滚 |
| v9 | 「自然短答」：限信息量不限字数——一轮一个信息点+一句自然完整句+渐进披露（追问才展开）+ 数字自然读法（2400X5500→"2.4米宽5.5米长"）+ 示范改自然风格 | ✅ 干练不冷 |
| v10 | 地块编号逐位中文读法（"02-09"→"零二零九地块"，防 TTS 读成"二月九号"），语音修正区+规则7 双处加固 | ✅ **主人测试通过** |

## 关键经验（血泪教训）

1. **v8 教训**：治啰嗦不能限字数，要限信息密度。硬字数上限+裸数字示范+禁令堆叠 → 机器人变报数据库的，对话破碎。正确配方是 v9 的"一轮一个信息点+自然完整句"。
2. **速查卡必须人工精选**：自动匹配的速查卡抓错条目（"车位配比"抓成户型表），放在注意力最高区错一条比没有更糟。
3. **防编造规则不可少**：知识库没有的信息（物业费/绿化率/交付时间/学校/售价），模型会瞎编——明确列出来让它"引导咨询销售顾问"。
4. **重复问题必须打标签**：265 条里 51 个问题文本跨章节重复（住宅/商墅同名不同值），不打标签必然混淆。
5. **「核心：」行是精度杀手锏**：数字句前置，模型第一眼就是精确值，不被营销长文带偏。
6. **TTS 读法坑**：XX-XX 格式会被读成日期，必须让模型输出逐位中文（"零二零九地块"）；1 在编号里写"幺"。
7. **ASR 配置**：`gummy_chat`(one-shot) → `qwen_realtime`(流式) 更准；`enable_hybrid_vad=true` 视觉+音频融合断句治嘈杂环境。
8. **验证脚本自己也会错**：count("核心：") 会把格式说明里的示例也算进去，要行首正则统计。

## settings.toml 最终状态（309）

```toml
face_detection_enabled = true        # 人脸识别
face_tracking_enabled = true
ai_chatbot_enabled = true
tts_enabled = true
TTS_PROVIDER = "qwen"
asr_provider = 'qwen_realtime'      # 流式 ASR
enable_hybrid_vad = true            # 视觉+音频融合断句
enable_input_vad = true
start_conversation_on_launch = true
enable_idle_action_on_response = true   # AI 回话时随机 idle 小动作
chat_active_timeout = 30            # 对话锁定期 60→30
```

## face_detection.json 最终状态（309）

- mode: slideshow_mode（轮换循环）
- 动作池: right_wave → left_wave → idle1 → idle2 → idle3 → bow_salute（无 scissors_hand）
- 欢迎语: "你好，我是小智，有什么可以帮你吗？" / "您好，欢迎光临，想了解什么可以问我。"
- time_interval: 3 秒

## 备份链（309 上，prompt.txt.bak.*）

original-2972B → v1-qa → v2 → v3 → v5 → v6 → v7 → v8 → v9 → v10(当前)

回滚命令模板：
```bash
TARGET=/home/ubuntu/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/assets/prompt/prompt.txt
cp $TARGET.bak.v9-20260912 $TARGET   # 例：回 v9
systemctl --user restart vision-service.service
```
