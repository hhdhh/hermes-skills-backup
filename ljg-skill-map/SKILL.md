---
name: ljg-skill-map
description: "Skill map viewer. Scans all installed skills and renders a visual overview — name, version, description, category at a glance. Use when user says 'skills', '技能', '技能地图', 'skill map', '我有哪些技能', '看看技能', '列出技能', 'list skills'. Also trigger when user asks what skills are available or installed."
user_invocable: true
version: "1.0.0"
---

# ljg-skill-map: 技能地图

扫描 `~/.claude/skills/` 下所有已安装技能，生成一目了然的可视化地图。

## 执行

### 1. 扫描

运行 `scripts/scan.sh`，获取所有技能的 JSON 数据（name, version, invocable, desc）。

### 2. 分类

根据技能名称和描述，将技能自动归入以下类别：

| 类别 | 图标 | 含义 | 典型成员 |
|------|------|------|----------|
| 认知原子 | ◆ | 内容处理的原子操作 | ljg-plain, ljg-word, ljg-writes, ljg-paper |
| 输出铸造 | ▲ | 将内容转化为可交付物 | ljg-card |
| 联网触达 | ● | 与外部世界交互 | agent-reach |
| 系统运维 | ■ | Agent 自身的维护和管理 | datetime-check, memory-review, save-conversation, skill-creator, ljg-skill-map |
| 环境部署 | ★ | 一次性安装和配置 | Her-init |

归类依据名称前缀和描述关键词判断。遇到新技能无法归类时，放入「未分类」。

### 3. 渲染

用 ASCII 方框图呈现，格式如下：

```
╔══════════════════════════════════════════════════════════╗
║              SKILL MAP  ·  {N} skills installed         ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  ◆ 认知原子                                              ║
║  +-----------------+----------------------------------+  ║
║  | ljg-plain v4.0  | 白 — 好问题+类比让人 grok        |  ║
║  | ljg-word  v1.0  | 英文单词深度拆解                  |  ║
║  | ljg-writes v4.0 | 写作引擎                          |  ║
║  | ljg-paper v2.0  | 论文阅读与分析                    |  ║
║  +-----------------+----------------------------------+  ║
║                                                          ║
║  ▲ 输出铸造                                              ║
║  +-----------------+----------------------------------+  ║
║  | ljg-card  v1.5  | 铸 — 内容转 PNG 可视化           |  ║
║  +-----------------+----------------------------------+  ║
║                                                          ║
║  ...                                                     ║
╚══════════════════════════════════════════════════════════╝
```

规则：
- 每个类别一个区块，类别图标 + 中文名做标题
- 技能名左对齐，版本号紧跟（无版本显示 `-`）
- 描述截断到一行，保留核心语义
- user_invocable 为 true 的技能名后加 `/` 标记（表示可直接 `/技能名` 调用）
- 底部统计行：总数、可调用数、分类数

### 4. 输出

直接在对话中渲染 ASCII 地图。不生成文件，不写入磁盘。


---

## 🔴 使用前 CHECKPOINT

启动本 skill 前自问：
- 🔴 **任务范围明确吗？** — 用户要"看技能地图"或"列技能"，不是要执行某个 skill
- 🔴 **输入数据已准备好？** — `~/.claude/skills/` 路径存在 + 可读
- 🔴 **输出格式清楚吗？** — ASCII 地图，对话内渲染，不写文件
- 🔴 **反例与黑名单扫一遍了吗？** — 单 skill 详情改用 Read SKILL.md；调 skill 用 `/` 前缀

## 失败模式与降级 (Failure Modes & Fallback)

- **如果 `scripts/scan.sh` 不存在或失败** → 降级用 `ls ~/.claude/skills/*/SKILL.md` + 解析 frontmatter
- **如果 skill 数量 > 100** → 分页：先按类别分块输出，最后给"完整列表见 N 个 skill"
- **如果某 skill 缺 description** → 标"无描述"，不归类，放"未分类"
- **如果某 skill 缺 version** → 显示 `-`，但保留名字
- **如果分类规则不覆盖**（如新出现的设计类）→ 加新类别前先告知用户"建议新增 XX 类别"
- **如果终端宽度 < 80** → 折叠描述到 30 字符，加 "...（完整看 SKILL.md）"
- **如果用户要求按其他维度排序**（按安装时间 / 按调用频次）→ 暂不支持，明确告知并建议手写脚本

---

## 🚫 反例与黑名单（绝对不要做）

**ljg-skill-map 专属反模式**：

- 🚫 **不要**让 ASCII 地图超过终端宽度（默认 80 字符）— 折叠成"更多"提示
- 🚫 **不要**把同一 skill 同时归入多个类别 — 选最匹配的，避免重叠
- 🚫 **不要**为未分类 skill 静默放在 "其他" — 明示标"未分类 + 触发词"，引导用户加 skill 时补 description
- 🚫 **不要**让 description 截断时丢关键字 — 优先保留触发词（如 "Use when..."），截断中间描述
- 🚫 **不要**对 user_invocable=false 的 skill 加 `/` 标记 — 会误导用户以为可调
- 🚫 **不要**在 skill 数量 > 100 时不分页 — 输出 100+ 行 ASCII = 不可读，分页或按类别折叠
- 🚫 **不要**省略版本号（即使填 `-`）— 一致性 > 美观

**达尔文 2.0 通用反模式**：

- 🚫 **不要**为简单任务启用本 skill — 开关成本不划算
- 🚫 **不要**跳过 🔴 CHECKPOINT — 跳过 = 自残
- 🚫 **不要**输入未验证的数据 — 先验证后处理
- 🚫 **不要**为凑进度忽略反例黑名单 — 红线就是红线

---

## 📚 References（外部参考）

- **达尔文 2.0** — `~/.claude/skills/darwin-skill/SKILL.md`
- **huihui-core** — 慧慧核心基础设施
- **huihui-engineering** — Karpathy + Matt Pocock 工程原则
- **huihui-writes** — 写作引擎（ljg-writes 改造型）
