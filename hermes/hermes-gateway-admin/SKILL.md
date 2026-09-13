---
name: hermes-gateway-admin
description: Class-level admin for Hermes Agent's macOS launchd-managed gateway, profiles, scheduled tasks, and version monitoring. Use when adding a profile, auto-starting gateway at boot, diagnosing launchd plist rejection, **registering third-party skill scheduled tasks (UUMit / capability bundles / cron-to-launchd translation)**, **translating cron `0 */4 * * *` to launchd `StartCalendarInterval`**, **deciding agent_session_task uses launchd vs hermes cron**, checking for Hermes/web-UI/agent updates, switching providers / adding API keys (OpenCode Go, Anthropic, custom endpoints), or configuring TTS providers (10 built-in + custom). Triggers "gateway", "plist", "LaunchAgent", "launchctl", "装后台任务", "scheduled task", "定时任务", "StartCalendarInterval", "cron 表达式", "agent_session_task", "Bootstrap failed", "hermes version", "provider 切换", "TTS", "text_to_speech". 2026-07-04 立 gateway / provider, 2026-08-15 扩第三方 Skill 定时任务登记（UUMit 5 项后台实战）。
---

# hermes-gateway-admin

Class-level admin for Hermes Agent's macOS launchd-managed gateway stack. Owned by the Hermes 化身 (灰灰) but applies equally to any profile under `~/.hermes/profiles/`.

> **Authoritative docs**: https://hermes-agent.nousresearch.com/docs — this skill is the **playbook** distilled from real work; the docs are the source of truth when they disagree.

## 核心事实（每次操作前自检）

1. **每个 profile 是独立 launchd service**：
   - Label 格式 `ai.hermes.gateway-<profile>` (or `ai.hermes.gateway` for default)
   - Plist 在 `~/Library/LaunchAgents/`
   - 每个进程独立进程，~26-100 MB RAM，**不占网络端口**（CLI 模式）
   - 7 个 profile = 7 个 LaunchAgent = 7 个常驻 python 进程

2. **三轨 CLI 入口**（`hermes` 不在 venv/bin/，在 `~/.local/bin/`）：
   ```
   /Users/kk/.local/bin/hermes                # shebang miniconda python3.13
   /Users/kk/miniconda3/bin/python3.13        # conda base 解释器
   /Users/kk/miniconda3/lib/python3.13/site-packages/hermes_cli/  # conda 装包
   ```
   - `doctor` 的 "venv entry point not found" 是**误报**（conda 不是 venv）
   - **不要** `pip install -e .[all]` — 会破坏双轨

3. **Cron 走系统 crontab，不用 `hermes cron`**：
   - `hermes cron list` 显示 0 = **正常**（主人走 `crontab -e`）
   - 系统 crontab 已有：`hermes-heartbeat.sh` / `hermes-learning-loop.sh` / `sync-hermes-skills-all.sh`
   - 见 `references/crontab-layout.md`

4. **`hermes-web-ui` ↔ `hermes-studio` 同一项目**（2026-07-04 确认）：
   - npm 包名 = `hermes-web-ui`（latest 0.6.25，BSL-1.1 license）
   - GitHub repo = `EKKOLearnAI/hermes-studio`
   - Web 标题 = "Hermes Studio"
   - 装在 `/opt/homebrew/lib/node_modules/hermes-web-ui/`
   - Bin 入口：`hermes-web-ui` / `hermes-web-ui-mcp` / `hermes-studio-mcp`
   - 数据：`~/.hermes-web-ui/hermes-web-ui.db`
   - 端口：**8648**（HERMES_WEB_UI_PORT 可改）
   - **不要被 "hermes-studio" 名字骗去 git clone** — 直接 `npm install -g hermes-web-ui`

4a. **Agent bridge 路径解析**（2026-07-12 立，最常翻车的 web UI 故障点）:
   - Web UI 启的 Python 子进程 = `hermes_bridge.py`（在 `dist/server/agent-bridge/python/`）
   - 启动命令：`python3 <hermes_bridge.py> --endpoint ipc:///tmp/hermes-agent-bridge.sock --hermes-home <HERMES_HOME> --agent-root <AGENT_ROOT>`
   - **关键**：bridge 启动时 `import run_agent.py`，找路径的顺序是 `I.agentRoot → $HERMES_AGENT_ROOT → ~/.hermes/hermes-agent → 自动反推 → 默认路径`
   - 主人是 conda 装的：`run_agent.py` 在 `/Users/kk/miniconda3/lib/python3.13/site-packages/run_agent.py`（不是 `~/.hermes/hermes-agent/run_agent.py`）
   - **没设 `HERMES_AGENT_ROOT` 时 bridge 秒退**，错误日志里只看到一行 `agent bridge exited before ready code=1 signal=null`，**没 stderr**（JS 端吞了），调试必须手跑 Python 脚本才能看到真因
   - **解法**：`export HERMES_AGENT_ROOT=/Users/kk/miniconda3/lib/python3.13/site-packages`（主人 7/12 已加 `~/.zshrc`）
   - 完整诊断流见 `references/web-ui-bridge-not-reachable.md`

5. **Provider 切换走 `.env` + `config.yaml`**，不走 MCP `provider_add`（2026-07-12 立）：
   - `~/.hermes/.env` 存 `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY`（Anthropic 协议）
   - `~/.hermes/config.yaml` 的 `model` 段定默认模型
   - CLI 缓存 .env，**改完 .env 后同 session 不重新读** — 主人 `/new` 才生效

## 标准操作

### A. 给新 profile 装 launchd plist（auto-start）

```bash
# 1. 复制 working plist 模板
cp templates/profile-plist.template.plist \
   /Users/kk/Library/LaunchAgents/ai.hermes.gateway-<NEWPROFILE>.plist

# 2. **用 plutil 改，不用 sed**（见 references/launchd-bootstrap-einval.md）
plutil -replace Label -string "ai.hermes.gateway-<NEWPROFILE>" <plist>
plutil -replace EnvironmentVariables.HERMES_HOME \
        -string "/Users/kk/.hermes/profiles/<NEWPROFILE>" <plist>
plutil -replace StandardOutPath \
        -string "/Users/kk/.hermes/profiles/<NEWPROFILE>/logs/gateway.log" <plist>
plutil -replace StandardErrorPath \
        -string "/Users/kk/.hermes/profiles/<NEWPROFILE>/logs/gateway.error.log" <plist>

# 3. 建 logs 目录
mkdir -p /Users/kk/.hermes/profiles/<NEWPROFILE>/logs

# 4. lint
plutil -lint <plist>

# 5. 启动（重试 2-3 次，launchd 偶发 EINVAL 需 unload + reload）
for i in 1 2 3; do
  launchctl bootstrap gui/$(id -u) <plist> 2>&1
  sleep 1
done
```

### B. 验证 gateway 跑着

```bash
launchctl list 2>&1 | grep "ai.hermes"           # launchd 视角
ps aux | grep "hermes_cli.main" | grep -v grep   # OS 视角
hermes gateway list                              # Hermes 视角
hermes profile list                              # Profile 状态矩阵
```

### C. 诊断 plist 拒收

**症状**：`Bootstrap failed: 5` 持续

**陷阱**：plist 跟 working plist 几乎一样仍然失败 — **launchd 内部 cache 卡了**，需 `sudo launchctl print system` 才能清（agent 做不到）。**兜底** = `nohup` 手动启（不持久化，重启会丢）：

```bash
# 主人授权后：
HERMES_HOME=/Users/kk/.hermes/profiles/<PROFILE> \
  nohup /Users/kk/miniconda3/bin/python3.13 \
    -m hermes_cli.main --profile <PROFILE> gateway run --replace \
    > /Users/kk/.hermes/profiles/<PROFILE>/logs/manual-gateway.log 2>&1 &
```

主人授权前**不要**自启 — 7/4 主人对 background 启 gateway 实际 partial-approve（3 个里批 1 个）。

### D. 升 hermes-web-ui

```bash
# 1. 备份当前装
cp -r /opt/homebrew/lib/node_modules/hermes-web-ui \
      ~/.hermes/backups/hermes-web-ui-$(date +%Y%m%d).npm.bak

# 2. 升（npm 镜像走 npmmirror，国内默认）
npm install -g hermes-web-ui

# 3. 验证
npm list -g hermes-web-ui
ls -la /opt/homebrew/bin/hermes-web-ui /opt/homebrew/bin/hermes-studio-mcp
# 三个 bin 入口都得在

# 4. 重启服务（kill PID 96046 + 重启）
```

**不要 git clone repo** — npm 装就是 0.6.25 latest。

### E. 切 provider / 加 API key（2026-07-12 立）

主人切 OpenCode Go 走的真实路径——MCP `provider_add` 工具 **fetch 失败**（agent 进程内调用 sandbox 限制），靠 fallback 三件套：

```bash
# 1. 改 .env（ANTHROPIC_BASE_URL 指向新端点 + 加新 key）
#   - OpenCode Go: ANTHROPIC_BASE_URL=https://opencode.ai/zen/go
#   - ANTHROPIC_API_KEY=sk-...（新 key）
#   - 加 OPENCODE_GO_API_KEY=sk-...（备份, 某些 CLI 路径走这个）
# 关键: 同时把旧的 MINIMAX_API_KEY 注释掉（doctor 会报 invalid）

# 2. 改 config.yaml 默认模型
hermes config set model.default minimax-m3
# (model.provider 留 anthropic — base_url 决定实际走哪)

# 3. **直接 curl 验 API 通**（比 CLI 验更可靠）
curl -s -X POST https://opencode.ai/zen/go/v1/messages \
  -H "x-api-key: sk-..." \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax-m3","max_tokens":50,"messages":[{"role":"user","content":"hi"}]}'
# 期望: 返回 assistant text, cost 0
```

**坑**（2026-07-12 主人切 OpenCode Go 实战）:

1. **MCP `provider_add` 会 fetch failed** — agent 进程内调用受 sandbox 网络限制。**直接改 .env + config.yaml**, 不要死磕 MCP 工具.
2. **CLI 缓存 .env, 同一 session 报 401/403** — 改完 .env 后 `hermes -m <model>` 仍用旧 key. 两种解法:
   - 主人说 `/new` 开新 session（最稳）
   - 临时绕: `env -i ANTHROPIC_BASE_URL=... ANTHROPIC_API_KEY=... hermes -m <model> -z "hi"`
3. **API 通了 ≠ CLI 通了** — `hermes -m opencode-go/<model>` 会 403（CLI 不认这个 providerKey 命名, OpenCode 自己的 ID 格式 vs Hermes CLI 内部命名空间不通用). 用 `hermes -m <model>` 即可（base_url 走 .env）.
4. **doctor 报 "Anthropic API (couldn't verify)" 是正常的** — base_url 是 opencode, CLI 直验失败. 看 "OpenCode Go: ✓ key configured" 这行就够.
5. **OpenCode Go 走 Anthropic 协议** — `POST /v1/messages`, headers `x-api-key` + `anthropic-version: 2023-06-01`. minimax 走的是 `/v1/messages`（不是 `/v1/chat/completions`, 那是 OpenAI-compatible 给其它模型的）.
6. **`/v1/models` 列出所有可用模型** — `curl https://opencode.ai/zen/go/v1/models -H "Authorization: Bearer sk-..."` 一次拿全, 不用 docs 翻.
7. **MINIMAX_API_KEY 旧 key 残留会让 doctor 报 "MiniMax invalid"** — 切到 OpenCode Go 后把旧行注释掉.

完整诊断流程见 `references/provider-switching.md`.

### F. Codex CLI + OpenCode Go（非 Anthropic 模型）—— 需要本地代理（2026-07-12 立）

**核心冲突**: Codex CLI `wire_api` 只支持 `responses`（二进制 strings 确认，无其他选项）。但 OpenCode Go 的 GLM/Kimi/DeepSeek/MiMo 只提供 `/v1/chat/completions` 端点，没有 `/v1/responses` 端点（404）。**Codex 无法直连这些模型。**

**解法**: 在 `~/.codex/responses-proxy.py` 跑一个本地代理（纯 stdlib HTTP server），监听 8848 端口，把 Codex 的 Responses API 请求转成 Chat Completions 发给 opencode.ai。

```toml
# ~/.codex/config.toml
model_provider = "custom"
model = "glm-5.2"
[model_providers.custom]
name = "OpenCode Go"
base_url = "http://127.0.0.1:8848/v1"
wire_api = "responses"          # Codex 唯一支持的值
requires_openai_auth = true
```

```bash
# 启动代理
python3 ~/.codex/responses-proxy.py --port 8848 --api-key sk-...
```

**哪些模型需要代理**: GLM-5.2/5.1、Kimi K2.7/K2.6、DeepSeek V4 Pro/Flash、MiMo-V2.5/V2.5-Pro（全部走 `/v1/chat/completions`）。
**哪些不需要**: MiniMax M3/M2.7、Qwen3.7 Max/Plus、Qwen3.6 Plus（走 `/v1/messages` Anthropic 协议，Codex 原生支持）。

完整配置 + 端点速查 + 常见错误见 `references/codex-opencode-go-config.md`。
代理脚本见 `scripts/responses-proxy.py`。

**踩过的坑**:
- `wire_api = "chat_completions"` → `unknown variant`，Codex 不认
- `wire_api = "responses"` 直连 opencode.ai → `/responses` 端点 404
- Codex Desktop 运行时会**回写覆盖** config.toml → 改完先关 Desktop
- `auth.json` 可能被 Codex Desktop 同步删除 → 检查 `ls ~/.codex/auth.json`
- conda 环境的 fastapi/httpx/aiohttp/requests 全坏（版本冲突）→ 代理必须用**纯 stdlib**

### G. 诊断 web UI "Agent Bridge is not reachable"（2026-07-12 立）

**症状**：网页报 `Error: Agent Bridge is not reachable: connect ENOENT /tmp/hermes-agent-bridge.sock`，server.log 只一行 `agent bridge exited before ready code=1 signal=null`。

**根因 95% = bridge 找不到 `run_agent.py`**。JS 端吞 stderr，必须手跑 Python 脚本才看得到真错。

**完整诊断流**（5 步，3 分钟内搞定）：

```bash
# 1. 停 web UI
hermes-web-ui stop
sleep 2

# 2. 手跑 bridge 看真错（30 秒超时）
/Users/kk/miniconda3/bin/python3.13 \
  /opt/homebrew/lib/node_modules/hermes-web-ui/dist/server/agent-bridge/python/hermes_bridge.py \
  --endpoint ipc:///tmp/hermes-agent-bridge.sock \
  --hermes-home /Users/kk/.hermes
# 期望: RuntimeError: hermes-agent run_agent.py not found. Tried: ...
# 关键: 看 Tried 列表的**前 3 个**（agentRoot → env → ~/.hermes/hermes-agent）

# 3. 找 run_agent.py 真在哪
find /Users/kk/miniconda3 -name "run_agent.py" 2>/dev/null
# 主人: /Users/kk/miniconda3/lib/python3.13/site-packages/run_agent.py

# 4. 设环境变量（永久）— 写到 ~/.zshrc
echo 'export HERMES_AGENT_ROOT="/Users/kk/miniconda3/lib/python3.13/site-packages"' >> ~/.zshrc

# 5. 重启（用 env 注入，立刻生效不依赖 shell 重启）
HERMES_AGENT_ROOT=/Users/kk/miniconda3/lib/python3.13/site-packages \
  hermes-web-ui start

# 验证
tail -3 /Users/kk/.hermes-web-ui/logs/server.log | grep "agent-bridge"
# 期望: [agent-bridge] ready at ipc:///tmp/hermes-agent-bridge.sock
ls /tmp/hermes-agent-bridge.sock
# 期望: 存在
```

**为什么这个错只在 7/12 才出现**（推测）：`hermes-web-ui` 旧版本不传 `--agent-root` 参数，bridge 自己会 fallback 到自动反推。0.6.25 改成严格传参，conda 装的 `hermes-agent` 不在 `~/.hermes/hermes-agent/` 也找不到 = 秒退。

**坑**:
- 0.6.25 有可用更新（npm log 显示 0.6.28），升上去可能修了也可能没修——先不升，把环境变量这步走通
- `launchctl print-cache` 卡 launchd 时这个错**不会**触发——是 Python bridge 自己的事，跟 launchd 无关

完整错误链 + 日志见 `references/web-ui-bridge-not-reachable.md`。

### G. 版本监控

`scripts/version-watchdog.sh` 已配 crontab `0 9 * * *`，每天 9 点查 npm latest 写 ticker 到 `~/.hermes/cron/version_ticker`。手动跑：

```bash
bash ~/.hermes/scripts/version-watchdog.sh
cat ~/./hermes/cron/version_ticker
tail -20 ~/.hermes/logs/version-watchdog-$(date +%Y%m%d).log
```

### H. TTS Provider 配置（2026-07-29 立）

TTS 跟 LLM provider **同形**——同一个 `.env` 注 API key、同一个 `config.yaml` 选 provider、同一个 `hermes config set` 工具。**10 个 TTS provider 是 Hermes 内置**（`tools/tts_tool.py:389 BUILTIN_TTS_PROVIDERS`），不用装、不用写 plugin：

`edge` / `openai` / `elevenlabs` / **`minimax`** / `xai` / `mistral` / `gemini` / `neutts` / `kittentts` / `piper` + 用户自定义 `tts.providers.<name>: type: command`（Piper/VoxCPM/Kokoro CLI 等）。

**配置 3 件套**（以 MiniMax 为例，主人 2026-07-29 验收通过）：

```bash
# 1. 改 provider 指向
hermes config set tts.provider minimax

# 2. 改 provider 自己的参数（API key 走 .env，不写这里）
hermes config set tts.minimax.model speech-02-hd
hermes config set tts.minimax.voice_id male-qn-qingse
hermes config set tts.minimax.base_url https://api.minimax.chat/v1/t2a_v2
hermes config set tts.minimax.speed 1.0
hermes config set tts.minimax.vol 1.0
hermes config set tts.minimax.pitch 0
hermes config set tts.minimax.emotion neutral
hermes config set tts.minimax.sample_rate 32000
hermes config set tts.minimax.bitrate 128000

# 3. 端到端验证（产物 MP3 + JSON success）
MINIMAX_API_KEY=$(grep MINIMAX_API_KEY ~/.hermes/.env | cut -d= -f2) \
  /Users/kk/miniconda3/bin/python3.13 \
  /Users/kk/.hermes/skills/hermes/hermes-gateway-admin/scripts/verify-tts.py minimax
```

**`.env` 提供 API key**（gateway 启动时自动 load，无需 `export`）：
- `ELEVENLABS_API_KEY` / `OPENAI_API_KEY` / `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID` / `MISTRAL_API_KEY` / `XAI_API_KEY` / `GEMINI_API_KEY`
- `edge` / `piper` / `neutts` / `kittentts` 不用 API key

**OWN 决策矩阵**（TTS 部分）：

| 改动 | 安全档 | 备注 |
|------|--------|------|
| `hermes config set tts.*` | ✅ 直接做 | 同 `model.*` |
| 改 `~/.hermes/.env` 加 TTS key | ✅ 直接做 | gateway 自动 load |
| 跑 `python3 verify-tts.py <provider>` | ✅ 直接做 | 验证用，**写到 `~/.hermes/cache/audio/`** |
| `hermes config set tts.provider` 切回 edge | ✅ 直接做 | 中文 TTS 兜底（edge `zh-CN-XiaoxiaoNeural`） |
| 装新 TTS provider（plugin 自定义） | ⚠ 写 Python 包+测一次 | 内置 10 个够用 |
| 删 `~/.hermes/cache/audio/` 大文件 | ✅ 直接做 | 启动后会再生成 |

**踩过的坑**（TTS 段，2026-07-29 立）：

1. **默认 base_url 是错的** — `tts_tool.py` 写死 `api.minimax.io`，主人 key 走 `api.minimax.chat`（国内）。直接 2049 invalid api key。**先 `curl` 验 endpoint 通，再改配置**。
2. **agent 不能 `patch`/`write_file` 改 `~/.hermes/config.yaml`**（工具安全敏感拒绝）。**用 `hermes config set tts.<key> <value>`** 一次一字段。
3. **`.env` 已有 `MINIMAX_API_KEY` → gateway 启动自动 load**。Python 验证脚本在 agent 进程外跑（无 launchd）时 **必须手动 `export` 或 `cmd_prefix` 注入**，否则 `get_env_value("MINIMAX_API_KEY")` 拿空。
4. **endpoint 选错 domain = 2049 invalid api key**。同 key 在 `api.minimax.chat` 通，在 `api.minimax.io` 拒。**curl 验根因**。
5. **voice_id 错 = 2054 voice id not exist**。常用 `male-qn-qingse`（清澈男声·中文）/ `female-shaonv`（少女）/`English_expressive_narrator`（英语叙述）通；`mature_man` 等幻觉 ID 拒。
6. **endpoint 形式自动切换** — `tts_tool.py` 通过 `is_t2a_v2 = "t2a_v2" in base_url` 判断用扁平参数 (`text_to_speech`) 还是嵌套参数 (`t2a_v2` 的 `voice_setting`/`audio_setting`)，**不需要手动切换 base_url 形式**，但 base_url 要写完整路径。
7. **输出位置** — `~/.hermes/cache/audio/tts_<timestamp>.mp3`（首次跑会建目录）。**不要 truncate 根目录**。
8. **`text_to_speech` 工具不接受 `voice_id` 参数**（致命坑，2026-07-29 立）— 工具签名是 `text_to_speech(text, output_path)`，**只读 `config.yaml` 当前的 `tts.minimax.voice_id`**。Agent 如果想"换 voice 发 6 个 demo 让主人选"，**默认全是用同一个当前 voice_id 发出去 6 个相同声音**。**正确做法**：每次改 voice → 跑 `hermes config set tts.minimax.voice_id <vid>` → 跑 `verify-tts.py` → 改下一个。或者**全部用 curl 直发**绕过工具（脚手架在 `scripts/verify-tts.py`）。
9. **`text_to_speech` 工具 vs curl 直发 — 路径不同、ID3 头不同**（2026-07-29 立）— 工具走 gateway 路径时 MP3 落到 `~/.hermes/cache/audio/`，ID3 头是 `ContentProducer: MiniMax` + `ProduceID: <UUID>` 完整 128kbps。curl 直发走 `tools/tts_tool.py` 调 `_generate_minimax_tts` 时落点相同，但 ID3 头有时不一样。**要验证声音差异、看真实 ProduceID、复用文件** = curl 直发 + 写到 `/tmp/voice_<name>.mp3`。
10. **TTS 真人声音差异在短文本 + 32kHz mono 下听感相近**（2026-07-29 立）— 6 个不同 voice_id 的 MP3 文件 md5/ProduceID 全不同，但人耳听短文本（"测试"）+ 32kHz mono 时容易误判为"同一种声音"。**要给人试听**：用 ≥ 2 句有情绪变化的中文文本（让声调/语气/停顿差异暴露），并且 **ProductionsID 可作为唯一指纹**（每个 voice_id 在每个文本下 = 唯一 UUID）。
11. **agent 不能 `patch`/`write_file` 改 `~/.hermes/config.yaml`**（2026-07-29 立）— 工具安全敏感拒绝这俩路径。**用 `hermes config set tts.*` 一次一字段**。10 字段就是 10 个 set 调用，全部幂等，可以放心重跑。

完整 provider 速查 + voice_id 清单 + 坑细节见 `references/tts-providers.md`。

## 决策矩阵（什么能动，什么不能动）

| 改动 | 安全档 | 主人确认 |
|------|--------|----------|
| 装 plist 给现有 profile | ✅ 直接做 | — |
| 启新 profile 的 gateway（launchd 启） | ✅ 试 plutil 路径 | 失败兜底需批 |
| 启新 profile 的 gateway（nohup 手动） | ⚠ 先 1 个做样 | 主人批 |
| `npm install -g hermes-web-ui` 升 | ✅ 直接做 | — |
| 改 system crontab | ✅ 直接做 | — |
| `hermes config migrate` v0→vN | ✅ backup 后做 | — |
| **改 `~/.hermes/.env`（切 provider / 加 key）** | ✅ 直接做 | — |
| **`hermes config set model.*`** | ✅ 直接做 | — |
| **curl 验 API 通** | ✅ 直接做 | — |
| **删 `~/.hermes/.env` 旧 key 行** | ✅ 直接做 | — |
| `pip install -e .[all]` 修 venv | ❌ **绝对不动** | 误报，conda 工作正常 |
| `sudo launchctl kill ...` | ❌ 没 sudo | — |
| 4 个 OAuth 登录（Nous/OpenAI/Gemini/xAI） | ❌ 用不到 | — |
| 删 `~/.hermes/profiles/<X>/` | ❌ 灵魂三件之一 | 必问 |

## 关联资源

- `references/launchd-bootstrap-einval.md` — launchd 拒收 plist 的根因分析 + 修复模式
- `references/launchd-schedule-third-party.md` — 给第三方 Skill 装定时任务（UUMit 等场景）：cron 表达式 → `StartCalendarInterval` 翻译表 + agent_session_task 走 hermes cron 不进 launchd + 回读校对铁律（2026-08-15 立）
- `references/crontab-layout.md` — 系统 crontab 现有条目速查
- `references/provider-switching.md` — 切 provider / 加 API key 的完整诊断流（2026-07-12 立）
- `references/tts-providers.md` — 10 个内置 TTS provider 速查 + voice_id 常用表 + endpoint 域名清单 + t2a_v2 vs text_to_speech 差异（2026-07-29 立）
- `references/web-ui-bridge-not-reachable.md` — web UI "Agent Bridge is not reachable" 完整错误链 + 日志 + 修复命令（2026-07-12 立）
- `references/codex-opencode-go-config.md` — Codex CLI + OpenCode Go GLM-5.2 config.toml 正确配置 + 常见错误 + 模型端点速查表（2026-07-12 立）
- `scripts/version-watchdog.sh` — 每日版本检查 + ticker 写入
- `scripts/verify-tts.py` — TTS 端到端验证脚本（输入 provider → 调 text_to_speech_tool → 验 MP3 / 报失败原因）
- `templates/profile-plist.template.plist` — 已知 working 的 dev profile plist 模板

## Pitfalls（已踩过的坑）

0. **npm 全局升级后旧 Web UI 进程可能卡在已删除的 staging cwd**（2026-08-29 立）— `lsof -a -p <PID> -d cwd -Fn` 若显示 `/opt/homebrew/lib/node_modules/.hermes-web-ui-<随机串>`，设置页调用 `hermes profile list` 会触发 Python `OSError: failed to make path absolute` / `Fatal Python error: error evaluating path`。这是进程工作目录失效，不是 config.yaml 或模型名坏了。**修复**：显式 `hermes-web-ui stop`，再从稳定目录启动：`cd /Users/kk && HERMES_AGENT_ROOT=/Users/kk/miniconda3/lib/python3.13/site-packages hermes-web-ui start`；验证 cwd 回到 `/opt/homebrew/lib/node_modules/hermes-web-ui`、bridge socket 存在、从该 cwd 执行 `hermes profile list` 成功。

1. **sed 改 plist 改坏结构** — 2026-07-04 sed 把 `KeepAlive` dict 改成单 `<true/>`，plist 仍 OK 但 launchd 拒收。**用 plutil 替换/插入**。
2. **`hermes gateway install` 不能给非 default profile 装** — 装的是当前 default 的 plist。**用 plutil 模板** 才是 class-level 方案。
3. **`launchctl bootstrap` 第一次偶发 EINVAL** — 重试 1-2 次通常 OK。持续 3+ 次 = launchd cache 卡，**找主人 sudo**。
5. **`nohup ... &` 主体被工具拒** — 必须 `terminal(background=true, notify_on_complete=true)`，触发"start gateway outside systemd" approval，**主人逐个批**。
5a. **`brew install` 用 `terminal(background=true)` 模式 0 stdout** — 父进程 0 输出,
   看不到进度, brew log 也不写. 实测 7/4 装 deno 时第一次 background 跑 0 输出以为挂,
   实际进程早死了但 surface 看不到. **重做要前台跑** (`terminal(foreground, timeout=600)`),
   这样才能看到 `==> Pouring ...` 进度.
5. **conda base + pip .local/bin/ 双轨** — doctor 报告"venv entry point not found"是**正常**。reinstall 必坏。
6. **Profile 软链 SOUL.md 看似空** — `~/.hermes/profiles/pm/SOUL.md` 是 symlink → `~/.hermes/SOUL.md`，**已配**。`hermes profile list` 才看真实状态。
7. **`hermes cron list = 0` 不代表没 cron** — 主人用系统 crontab，**两层 cron 都有**。
8. **Web UI 标题 ≠ npm 包名** — 主人下次问"hermes-studio 装了没"要回"装了，8648 那个"。
9. **MCP `provider_add` 在 agent 进程内 fetch 失败** — sandbox 限制。**改 .env + config.yaml** 走 fallback 路径.
10. **CLI 改完 .env 报 401/403** — 同 session 缓存旧 env. 主人 `/new` 或 `env -i` 绕.
11. **`hermes -m opencode-go/<model>` 403** — CLI 不认 OpenCode 的 providerKey 命名. 用 `hermes -m <model>`（base_url 决定走哪）.
12. **web UI 报 "Agent Bridge is not reachable" 95% 是 `HERMES_AGENT_ROOT` 没解析到**（2026-07-12 立；2026-09-05 补 0.7.17）— conda 装的 `run_agent.py` 在 `/Users/kk/miniconda3/lib/python3.13/site-packages`，不在默认 `~/.hermes/hermes-agent/`。JS 吞 stderr，必须手跑 Python bridge 看真错。
    - 0.6.x：shell 中 `export HERMES_AGENT_ROOT=...` 后启动通常可解。
    - **0.7.17 daemon 坑**：即使 `~/.zshrc` 已 export、`~/.hermes/.env` 也写了变量，后台 server 在 bridge 路径解析时仍可能拿不到；启动日志会缺少 `--agent-root`，bridge 秒退。
    - **0.7.17 稳定解**：仅当 `~/.hermes/hermes-agent` 不存在时，建兼容软链：`ln -s /Users/kk/miniconda3/lib/python3.13/site-packages /Users/kk/.hermes/hermes-agent`。重启后日志必须出现 `--agent-root /Users/kk/.hermes/hermes-agent`，`/health` 的 `agent_bridge.status` 必须为 `ready`。
13. **bridge 启动失败 ≠ launchd 故障** — 看到 "agent bridge failed to start" 第一反应是看 Python 路径问题，**不是** `launchctl bootstrap`。两个完全独立。
14. **`text_to_speech` 工具不接受 `voice_id` 参数**（致命坑，2026-07-29 立）— 工具签名是 `text_to_speech(text, output_path)`，**只读 `config.yaml` 当前的 `tts.minimax.voice_id`**。Agent 想"换 voice 发 N 个 demo 让主人选" → 默认全是用同一个当前 voice_id 发出去 N 个相同声音 → 主人听感"全是同一种声音" = 实际就是同一段。**正解**：每次改 voice → 跑 `hermes config set tts.minimax.voice_id <vid>` → 跑 `verify-tts.py`，或者**全部用 curl 直发**绕过工具（见 references/tts-providers.md 做法）。
15. **TTS 短文本 + 32kHz mono 听感差异小**（2026-07-29 立）— 6 个不同 voice_id 的 MP3 文件 md5/ProduceID 全不同，但人耳听短文本（"测试" / 1 句话）+ 32kHz mono 时容易误判为"同一种声音"。**要给人试听**：用 ≥ 2 句有情绪变化的中文文本（让声调/语气/停顿差异暴露），并且 **ProduceID 可作为唯一指纹**（每个 voice_id 在每个文本下 = 唯一 UUID）。
16. **agent 不能 `patch`/`write_file` 改 `~/.hermes/config.yaml`**（2026-07-29 立）— 工具安全敏感拒绝这俩路径。**用 `hermes config set tts.*` 一次一字段**。10 字段就是 10 个 set 调用，全部幂等，可以放心重跑。
17. **Web UI 0.7.17 的主 bridge endpoint 可能被污染成 worker socket**（2026-09-06 立）— 症状是网页报 `connect ENOENT .../hermes-agent-bridge-workers/<hash>.sock` 或恢复会话时报 `unknown action: status_if_loaded`，日志中 broker 每次 `ready` 后约 2 秒 `exited code=0` 并循环重启；路径软链和 `run_agent.py` 都正常。根因是从 Web UI bridge worker 内调用 `hermes-web-ui start/restart` 时，新 Node 进程继承 `HERMES_AGENT_BRIDGE_ENDPOINT=<worker socket>`，于是把 worker 当主 broker。
    - **一次性修复**：`cd /Users/kk && unset HERMES_AGENT_BRIDGE_ENDPOINT && HERMES_AGENT_ROOT=/Users/kk/.hermes/hermes-agent /opt/homebrew/bin/hermes-web-ui restart --no-open`。
    - **永久修复**：在 PATH 优先的 `/Users/kk/.local/bin/hermes-web-ui` 放包装器，先 `unset HERMES_AGENT_BRIDGE_ENDPOINT`、固定 `HERMES_AGENT_ROOT=/Users/kk/.hermes/hermes-agent`、`cd /Users/kk`，再 `exec /opt/homebrew/bin/hermes-web-ui "$@"`。这样即便命令从 bridge worker 会话内执行也不会复发。
    - 成功后主 broker 必须监听 `/tmp/hermes-agent-bridge.sock`，worker 才监听 `.../bridge-workers/<hash>.sock`；连续检查 `/health` 20 秒须保持 `agent_bridge.status=ready`、PID 不变，并直接向主 socket 发 `status_if_loaded` 验证不返回 `unknown action`。不要删除 worker socket，它是正常的 profile worker。
