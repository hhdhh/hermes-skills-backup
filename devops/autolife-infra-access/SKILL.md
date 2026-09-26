---
name: autolife-infra-access
description: Use when 装 autolife 内网包、配 Codex/Claude Code 走 sub2api、Net...
version: 1
license: MIT
metadata:
  hermes:
    tags: [autolife, fae, apt, sub2api, netbird, ssh, fleet, lark-cli]
---

# AutoLife 基础设施访问（FAE 工作站）

> 完整描述：在工作站上配置/修复对智动未来基础设施的四层访问：内网 apt 源、sub2api 模型网关、NetBird 自托管组网、机器人机队 SSH，以及 lark-cli 密钥轮换自愈。Use when 装 autolife 内网包、配 Codex/Claude Code 走 sub2api、NetBird/100.x 地址不通、SSH 进机器人检修、lark-cli 报 client secret invalid。

工作站要碰公司资源，先过这几层。每层独立验证，别把症状混着查（比如 100.x 不通 ≠ 网络坏了，可能只是 NetBird 没登录）。

## 1. 内网 apt 源（apt.gz.autolife.ai:8444）

```bash
# agent 无 TTY 环境：curl 落临时文件再 sudo install，别用 curl | sudo tee 管道
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://apt.gz.autolife.ai:8444/autolife-apt.asc | gpg --dearmor > /tmp/autolife-apt.gpg
sudo install -m 0644 /tmp/autolife-apt.gpg /etc/apt/keyrings/autolife-apt.gpg
# /etc/apt/sources.list.d/autolife.sources：两个 stanza（根路径 + /doctor 路径），
# 都是 Suites: noble / Components: main / Architectures: amd64 / Signed-By 指向上面 keyring
sudo apt-get update
sudo apt-get install -y codex autolife-doctor autolife-doctor-skill
```

验证：`autolife-doctor --version`、`codex --version`。

坑：apt 装的 codex 可能被 `~/.npm-global/bin/codex`（npm 旧版）在 PATH 里遮蔽——二选一，`dpkg -l | grep codex` 与 `command -v codex` 报的版本对不上就是双版本。

## 2. sub2api 模型网关（sub2api.autolife-robotics.com）

**密钥是分组隔离的**：OpenAI 组（gpt-5.6-sol 等）和 GLM 组（glm-4.6 / glm-5.x 等）互不可用。写配置前先验组：

```bash
# 列出这把钥匙能用的模型（判断组的唯一可靠方法）
curl -s https://sub2api.autolife-robotics.com/v1/models -H "Authorization: Bearer <key>"
# Anthropic 协议端到端验证（Claude Code 用）
curl -s https://sub2api.autolife-robotics.com/v1/messages \
  -H "x-api-key: <key>" -H "anthropic-version: 2023-06-01" \
  -H 'content-type: application/json' \
  -d '{"model":"glm-5.3","max_tokens":20,"messages":[{"role":"user","content":"hi"}]}'
```

- Claude Code：`~/.claude/settings.json` 的 `env.ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`，顶层 `model` 填**组内真实存在**的模型名；文件 chmod 0600。
- Codex：`~/.codex/config.toml`（`wire_api = "responses"`）+ `~/.codex/auth.json`（`{"OPENAI_API_KEY":...}`），chmod 0600。

坑：401 `INVALID_API_KEY` 才是密钥坏；`model ... not supported by any configured account in this group` 是**组不匹配**，换组内模型名，别去换密钥。文档/登录页写的测试账号与默认模型名可能已过期，一切以 `/v1/models` 实测为准。

## 3. NetBird 自托管组网（netbird.autolife-robotics.com:443）

```bash
sudo netbird up --management-url https://netbird.autolife-robotics.com:443
# 输出 Casdoor SSO URL，回调落在 localhost:53000
```

- 回调是 localhost → 必须在本机浏览器完成。无桌面时用 browser automation 打开 URL → 点 `.provider-link`（飞书）→ 点「授权」按钮 → 等回调页出现 "Login Successful"。Casdoor 登录页是 React 渲染，直接 GET 只有空壳，别用 curl 判断页面内容。
- 服务端门禁：`user pending approval cannot add peers` = 账号待管理员批准（去 NetBird 后台批，或改用 `netbird up --management-url ... --setup-key <key>` 免 SSO）。
- 排查顺序：100.x 地址不通 → 先 `netbird status`（Management Disconnected = 客户端没登录，不是网络问题）→ 再看 `/var/log/netbird/client.log` 的 PermissionDenied 行。`/var/lib/netbird/default.json` 存持久化的 ManagementURL。

## 4. 机器人机队 SSH

- 助手脚本：`~/.hermes/workspace/robssh.py`（paramiko）。子命令：`run <ip> "cmd"` / `sudo <ip> "cmd"` / `fleet`（已知机队 ping 总览）/ `scan`（扫 192.168.10/50/64/65 网段在线设备）。凭据全机队统一，主人已授权直接 SSH 检修，无需逐次请示。
- 机号别名（402 机、B 机）只作备注，**以 IP 为唯一可信标识**（不同文档对同一 IP 的别名可能矛盾）。
- 本技能只管「连得上」；连上后的诊断/维修流程走 `autolife-doctor-operations` 技能（症状→检查点快速通道表）。

## 5. lark-cli 密钥轮换自愈（`client secret is invalid`）

所有调用报 `The client secret is invalid` 时是 App Secret 被服务端轮换，本地修，不用重装。完整步骤见 [references/lark-secret-recovery.md](references/lark-secret-recovery.md)。

## 6. lark-cli 文档搜索的两个形状坑

- `lark-cli api` 不吃 curl 式 `-H`，请求体用 `--data '{...}'`。
- 搜索结果实体在 `data.docs_entities[]`（字段 `docs_token`/`docs_type`/`title`/`owner_id`，**无 url 字段**），自己拼链接：docx → `https://<tenant>.feishu.cn/docx/<token>`，bitable → `.../base/<token>`。解析 `data.data` 会拿到空列表，看起来像"搜不到"。

## 验证清单（一次全过才算接入完成）

1. `apt-get update` 无 autolife 源报错
2. `/v1/models` 返回目标组的模型列表，且目标模型能出 completion
3. `netbird status` 显示 Connected 且能 ping 通目标机器人 IP
4. `robssh.py run <robot-ip> "hostname"` 正常返回
