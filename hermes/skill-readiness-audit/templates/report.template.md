# Skill Readiness Report — {{DATE}}

> 来自 `skill-readiness-audit` skill · `scripts/audit.sh`
> 时间: {{TIMESTAMP}}
> 根目录: {{SKILL_ROOT}}

## 总览

| 项 | 数字 |
|---|---|
| 总目录 | {{TOTAL}} |
| Broken symlink | {{BROKEN}} |
| Empty 目录 | {{EMPTY}} |
| SKILL.md 数量 | {{SKILLMD}} |

## Step 3-4: 关键 bin

| Bin | 路径 | 版本 | 状态 |
|---|---|---|---|
| lark-cli | | | |
| node | | | |
| python3 | | | |
| nano-pdf | | | |
| obscura | | | |
| deno | | | |
| tsx | | | |

## Step 5: Python 包

| 包 | 版本 | 状态 |
|---|---|---|
| chromadb | | |
| pyyaml | | |
| lancedb | | |
| playwright | | |
| sqlite3 | | |

## Step 6: Smoke tests

| Skill | 测试项 | 结果 |
|---|---|---|
| fluid-memory | import + 实例化 + HAS_CHROMA | |
| lark-cli | --version | |
| huihui-core | 11 模块目录 | |
| hermes CLI | --version | |

## Step 7: Empty / placeholder skill

| 目录 | 原因 | 处理 |
|---|---|---|
| | | |

## 已知 gap（主人有意不装）

- deno (smart-memory-manager 走 fallback)
- playwright (ljg-card 等主人网络慢)
- OPENAI_API_KEY (elite-longterm-memory 主人有意)
- FEISHU_APPSECRET (占位符)

## 结论

- [ ] Ready — 全绿
- [ ] 部分就绪 — 上面 N 项需要补
- [ ] 失败 — 关键 skill 装不上

---

_下一次复跑: `bash ~/.hermes/skills/hermes/skill-readiness-audit/scripts/audit.sh`_
