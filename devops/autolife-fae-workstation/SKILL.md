---
name: autolife-fae-workstation
description: Use when 装配 FAE 工作站、装 codex/doctor、配 sub2api 密钥、登录排班系统.
---

# Autolife FAE 工作站配置

> 完整描述：Autolife FAE 工作站装配置：内网 apt 源、Codex+sub2api、autolife-doctor 智能体、内网 Web 工具登录. Use when 装配 FAE 工作站、装 codex/doctor、配 sub2api 密钥、登录排班系统.

## 1. 内网 apt 源（apt.gz.autolife.ai:8444）

```bash
# key：curl asc → gpg --dearmor → install -m 0644 到 /etc/apt/keyrings/autolife-apt.gpg
# /etc/apt/sources.list.d/autolife.sources（deb822，两段）：
#   根路径 + /doctor 路径，均 Suites: noble, Components: main, Architectures: amd64,
#   Signed-By: /etc/apt/keyrings/autolife-apt.gpg
sudo apt-get update && sudo apt-get install -y codex autolife-doctor autolife-doctor-skill
```

无 NOPASSWD sudo 时：每条 `sudo -S` 拆解执行，密码读 `~/.hermes/.env` 的 `SUDO_PASSWORD`（见 mesh-vpn-clients P4）。

## 2. Codex 配置（sub2api 网关）

`~/.codex`（0700）两个文件均 0600：

- `config.toml`：`model_provider="OpenAI"`、`model`/`review_model`="gpt-5.6-sol"、`model_reasoning_effort="xhigh"`、`[model_providers.OpenAI]` `base_url="https://sub2api.autolife-robotics.com"`、`wire_api="responses"`、`requires_openai_auth=true`
- `auth.json`：`{"OPENAI_API_KEY":"<sub2api 控制台创建的 Codex 密钥>"}`——密钥必须用户从 sub2api 后台创建提供

注意：该网关的 base_url 不带 `/v1`（与 codex-custom-provider-troubleshooting 里的常规中转不同）——以网关文档为准，不要凭经验加。

## 3. autolife-doctor 智能体

```bash
autolife-doctor agent install   # 插件装入 ~/.codex/plugins/cache/autolife-internal/
autolife-doctor agent status
autolife-doctor agent start     # 启动 Codex TUI——必须 pty
```

`agent start` 拉起 Codex TUI，无 TTY 报 `stdin is not a terminal` 失败。用 `terminal(pty=true, background=true)` 启动，`process_manage submit` 驱动：首个交互是目录信任（提交 `1` 选 Yes 并回车），随后会话自动预载 doctor 技能。

技能本体（22 项扫描工作流、只读白名单、OTA 状态查询、飞书证据同步、8 份 references + 4 个 lark 脚本）在 `/usr/share/autolife-doctor-marketplace/plugins/autolife-doctor-operations/skills/autolife-doctor-operations/SKILL.md`——按需读，不要背进上下文。

## 4. 内网 Web 工具

- FAE 排班系统 `http://192.168.64.141:8000`：登录页印的测试账号可能过期。先 `fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})})` 探一次——400「账号或密码错误」是凭证问题，别赖表单自动化。marketing 角色对排班网格只读。
- React 受控表单填值：`fill_input` 可能静默不生效——用原生 prototype setter + input/change 事件后再按 innerText 点按钮（同 mesh-vpn-clients P3）。
- 排班页大表格截图耗时，capture_screenshot 给足 timeout。

## Pitfalls

- P1 `agent start` 无 pty 必失败（"stdin is not a terminal"）——terminal pty=true + process_manage 驱动交互
- P2 sub2api 返回 401 INVALID_API_KEY + 重连 1/5..5/5 = auth.json 还是占位符或密钥失效，不是网络问题；修法见 codex-custom-provider-troubleshooting
- P3 apt 源 Suites 跟仓库发布的代号走（noble），与本机 Ubuntu 版本无关
- P4 codex deb 包版本与 CLI 自报版本可能差一位（包 0.154.0 / CLI 自报 0.153.4）——记录以 deb 包为准
