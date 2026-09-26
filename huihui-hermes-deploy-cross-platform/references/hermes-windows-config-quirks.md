# Hermes 0.19.0 on Windows 配置侧坑

> 这是 hermes-agent 0.19.0 在 Windows 上的"配置层"行为速查，部署流程见 SKILL.md 5 档；这里只列"配置时容易翻车"的事实，不重复部署步骤。

## 实际写入路径：双目录，不是一个

| 类别 | 路径 |
|---|---|
| 灵魂 / 身份 / 记忆 / skills | `C:\Users\<u>\.hermes\` |
| 运行配置 / 凭证 / .env / auth.json / config.yaml | `C:\Users\<u>\AppData\Local\hermes\` |

先看 `hermes config path` 和 `hermes config env-path` 确认实际位置，**不要假设 `~/.hermes/config.yaml`**。

## `custom_providers` 是顶级 list，不是 alias 字段

alias 字段里的 `provider: custom` 只是占位，真正生效的是：

```yaml
custom_providers:
  - name: <name>                       # 标识，跨 alias / fallback 引用
    base_url: https://...              # OpenAI 兼容端点
    api_key: ${ENV_VAR}                # 或明文（不推荐）
    key_env: ENV_VAR                   # 二选一
    api_mode: chat_completions         # 或 responses
    model: <default-model-id>
    models:
      <model-id>: { context_length: 128000 }
```

**不要把 `base_url` / `api_key` 写到 alias 里**——chat 会报 `No inference provider configured`。

## 优先用 built-in provider，不要绕 custom

hermes-agent 内置 provider（部分）：`anthropic` / `openai` / `openai-codex` / `openrouter` / `minimax` / `nous` / `google` / `deepseek` / `xai` / `kimi` / `zai` / `copilot` / `lmstudio` / ...

每个内置 provider 都已注册到 `PROVIDER_REGISTRY`，env_vars + base_url_env_var 配好：

| provider | api key env | base url env |
|---|---|---|
| `minimax` | `MINIMAX_API_KEY` | `MINIMAX_BASE_URL` |
| `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL`（可选） |
| `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL`（可选） |

**判断用哪个**：
- 直接调厂商 API 或厂商 OpenAI 兼容网关 → 用 built-in（设 env var）
- 厂商不支持或自定义路径 → 用 `custom_providers`

**绕路（用 `custom_providers` 配一个 built-in 已支持的厂商）几乎一定 401**——custom_providers 的 api_key 解析路径比 built-in 严，少几个 fallback。

## `hermes config set` 语法

```bash
# 正确（positional args）
hermes config set model.default MiniMax-M3
hermes config set model.aliases.m27 -- "minimax/MiniMax-M2.7"

# 错误（skill 文档有的版本写的 --value 形式已不工作）
hermes config set model.aliases.m27 --value "..."   # unrecognized arguments: --value
```

**复杂 dict（多层嵌套、list）不要用 `hermes config set`**——直接改 config.yaml：

```powershell
# 备份 + 改写 + 验证
$bak = "$cfgPath.bak.$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item $cfgPath $bak -Force

# 单引号 here-string 避免 PowerShell 变量展开吃掉 ${ENV} 引用
@'
custom_providers:
  - name: ...
'@ | Set-Content -Path $cfgPath -Encoding UTF8
```

## 远端推送配置：避免 PowerShell 反引号被吃

SSH 嵌套 + PowerShell 反引号（`` `n `` `` `t `` 等）在 MSYS bash 里被 shell 当命令替换。**永远走 `pwsh -EncodedCommand` + UTF-16 LE + base64**：

```bash
# Linux 端推 ps1 到 Windows 并执行
B64=$(iconv -f UTF-8 -t UTF-16LE /tmp/cfg.ps1 | base64 -w 0)
sshpass -p <pw> ssh user@win \
  "pwsh -NoProfile -ExecutionPolicy Bypass -EncodedCommand $B64"
```

或者根本不走脚本——直接 ssh + pwsh inline（**但不要在 pwsh -Command 里用反引号**，用 here-string 或子表达式）。

## fallback_providers 用 `custom:<name>`

```yaml
fallback_providers:
  - provider: custom:sub2api         # 指向 custom_providers 里 name: sub2api
    model: claude-fable-5-1
```

slug 格式是 `custom:<custom_providers[i].name>`。写 `provider: custom`（裸）不一定生效，要看具体 builtin 解析逻辑。

## dashboard auth：0.0.0.0 bind 强制

`hermes serve --host 0.0.0.0` 或 `hermes dashboard` 报：

```
Refusing to bind dashboard to 0.0.0.0 — the auth gate engages on
non-loopback binds, but no auth providers are registered.
There is no unauthenticated public-bind option.
```

三选一：

1. **绑 127.0.0.1 + 隧道**：`hermes serve --host 127.0.0.1 --port 8648`，本机或 SSH/NetBird 隧道访问
2. **配 basic auth**：

   ```yaml
   # config.yaml
   dashboard:
     basic_auth:
       username: <admin>
       password_hash: <scrypt$...>   # 用 plugins.dashboard_auth.basic.hash_password 生成
   ```
3. **OAuth**：`hermes dashboard register`（要浏览器走 Nous Portal）

**没有"裸跑公网 + 无 auth"选项**——这是 2026-06 hardening 后的硬规定。

## 验收 checklist（hermes on Windows 配置层）

```powershell
# .env 在 hermes env-path
Test-Path "$env:LOCALAPPDATA\hermes\.env"     # 应 True

# config 读得到
hermes config get model.default
hermes config get model.aliases.m27

# chat 调通（走 default）
hermes --cli -m MiniMax-M3 -z "ping"          # 应输出 pong

# chat 调通（走 alias）
hermes --cli -m m27 -z "ping"

# fallback 链路（造个无效 primary 看是否切）
hermes --cli -m invalid-model -z "ping"      # 看日志是否 fall back 到第一个 fallback_providers
```

## 常见错误速查

| 错误 | 真因 |
|---|---|
| `No inference provider configured` | 没设 `model.provider` 或 alias 写了 `custom` 但没 `custom_providers` 顶级段 |
| `HTTP 401: invalid api key` | `.env` 写在 `~/.hermes/`（不是 hermes env-path）；或 key_env 拼错；或 custom_providers 的 key 解析路径失败 |
| `Model 'X' not found` | `model.default` 或 alias 没在 `models:` 段声明；或模型 id 拼错 |
| `unrecognized arguments: --value` | 用错 `hermes config set` 语法；改 positional 或写 yaml |
| `Refusing to bind dashboard to 0.0.0.0` | 配 auth（见上）或改绑 127.0.0.1 |
