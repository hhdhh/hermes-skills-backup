---
name: autolife-knowledge
description: AutoLife FAE 知识库（远端 AstrBot RAG）检索 + 维修后经验上传沉淀
---


# AutoLife 知识库（AstrBot RAG）

> 完整描述：AutoLife FAE 知识库（远端 AstrBot RAG）检索 + 维修后经验上传沉淀。当用户问 AutoLife/智动未来机器人、Robox、太空舱、产品手册、检修排障、展会，或完成一次维修/排查后要沉淀时使用。来自同事 waziiiiii 的 autolife-FAE-knowledge-skill 仓库。

> 来源：同事 `waziiiiii/autolife-FAE-knowledge-skill`（Codex skill），已接入 Hermes 技能体系。
> 与本地 `autolife-*` 排障技能互补：本地技能负责**修**，本技能负责**查知识库 + 把修好的经验沉淀进共享知识库**。

## 核心能力

1. **检索远端知识库** — 把自然语言问题发给 AstrBot Dashboard API，返回最相关片段 + 来源文档名。
2. **经验上传沉淀** — 把维修/排查 Markdown 上传到 AstrBot 知识库，后台分块向量化，供全 FAE 复用。

## 两种运行模式（2026-09-19 起）

- **公网模式（当前已配置 ✅）**：`.env` 里有 `KB_API_TOKEN`（管理员分发，`kb_` 开头），直连 `https://fae.gz.autolife.ai:8866/kb`，**无需 NetBird、无需 AstrBot 账号**。密钥 2026-09-19 由许津铭分发，`setup.py --check` 校验通过。
- **内网模式（留空 token 时）**：AstrBot API + NetBird，额外有列库/上传/按小节补上下文能力。
- 换密钥：`python scripts/setup.py --force`；校验：`python scripts/setup.py --check`。

## NetBird 硬约束（仅内网模式）

所有远端访问前强制预检，只允许自托管服务器：

```text
https://netbird.autolife-robotics.com:443
```

`retrieve_kb.py` / `upload_to_kb.py` 会自动执行预检，失败即拦下并提示启动/登录 NetBird。**不要绕过、不要改用公网地址。** 这就是 AstrBot 只能在 NetBird 网内访问的保护。

## 环境与配置

本 Ubuntu 机 NetBird 已连（`netbird status` 确认 daemon/management/signal 全绿，IP `100.98.198.205`）。

默认值已内置（与同事仓库一致）：远端 `http://100.98.140.155:6185`、账号 `autolife`、知识库 `autolife-docs`、top 5。

需要覆盖时用环境变量：`KB_BASE_URL` / `KB_USERNAME` / `KB_PASSWORD` / `KB_NAMES` / `KB_TOP_K`。

## 检索（回答前先查库）

回答 Autolife 相关问题前，先检索支撑上下文：

```bash
python scripts/retrieve_kb.py "你的问题"
# 指定条数：
python scripts/retrieve_kb.py "机器人视觉无法启动" --top-k 8
```

### 回答规则（沿用同事约定）

- 相关内容优先以知识库为准，引用事实时说明**来源文档名**。
- 知识库没覆盖 → 明确说缺什么，**不编造**。
- 不输出账号密码 / JWT / 原始登录响应。

## 沉淀（维修后必做）

完成维修 / 复杂排查 / 配置修复 / 重要架构验证后，**必须**：
1. 先按模板写成结构化 Markdown
2. 再上传到知识库：

```bash
python scripts/upload_to_kb.py "path/to/修复记录.md"
# 或从 stdin：
cat summary.md | python scripts/upload_to_kb.py - --title "Fix: 电池恒 100%"
```

### 沉淀文档模板

```markdown
# [系统/组件] [问题简述] 排查修复记录（编号）

**结论**：一句话说清根因和修复方式。

## 一、问题现象  （设备标识/系统版本/故障日期/耗时/具体症状）
## 二、排查过程  （思路/每步实测/关键拐点）
## 三、根因分析  （直接原因/深层原因/因果链）
## 四、修复步骤  （改动前后对比/命令/回滚方案）
## 五、验证结果  （逐层验证打勾）
## 六、遗留事项与预防  （遗留/观察点/下次快速判定法）
```

### 该上传 vs 不该上传

✅ 硬件/软件维修完成 · 复杂排查出非显然根因 · 有复用价值的配置修复 · 新架构限制发现
❌ 无排查结论的简单重启 · 知识库已有同因同修法 · 只有临时猜测没验证

## 运维细节（脚本行为）

- 上传用 `multipart/form-data`，后台任务最多等 15 分钟（大文档分块+embedding）。
- 上传**不会自动删旧版同名文档**；删除要另用 AstrBot WebUI / API。
- NetBird 预检是安全约束，不能用普通 TCP 连通性测试替代。

## 与其它技能衔接

- 排障能力来源：`autolife-doctor-operations` / `autolife-remote-repair` / `autolife-robot-dds-camp-split` 等。
- 修复闭环三连：**修（排障技能）→ 归档案例（`autolife-case-log` 写飞书云文档）→ 沉淀知识库（本技能）**。
- 上传的知识库条目与 `autolife-case-log` 的飞书案例内容互补——飞书给运营同事看，AstrBot 给全 FAE 检索。

## 脚本

- `scripts/netbird_preflight.py` — NetBird 预检（也可单独跑 `python scripts/netbird_preflight.py`）
- `scripts/retrieve_kb.py` — 检索
- `scripts/upload_to_kb.py` — 上传
