# web UI "Agent Bridge is not reachable" 完整诊断手册

> 2026-07-12 主人在 Hermes 化身会话里撞上，从 `hermes-web-ui start` → 网页报 `connect ENOENT` → 诊断 4 分钟 → 一行环境变量修。
> 完整修复流程见 SKILL.md §F。

## 错误链路（4 层）

```
[1] 浏览器：Error: Agent Bridge is not reachable: connect ENOENT configured endpoint
                    ↓
[2] Web UI server.log: [agent-bridge] failed to start: agent bridge exited before ready code=1 signal=null
                    ↓
[3] JS 端 stdout/stderr 被吞: 看不到 Python 进程到底为啥退
                    ↓
[4] 真错（手跑 bridge 才看得到）: RuntimeError: hermes-agent run_agent.py not found.
                                    Tried: ~/.hermes/hermes-agent, /Users/kk/miniconda3, ... (34 个)
```

**关键观察**：
- JS 端 `agent-bridge` spawn 时 `stdio: ['ignore', 'ignore', 'ignore']`（看 `index.js:375` 附近）
- 所以 server.log 只有一行 JS 视角的错误，**Python 真实 traceback 永远看不见**
- 必须脱离 web UI，手跑 `hermes_bridge.py` 才能看错

## JS 端 spawn 代码（不修，只理解）

`/opt/homebrew/lib/node_modules/hermes-web-ui/dist/server/index.js` 里的 `Kg.startProcess()`：

```js
const l = x9I()  // 找 hermes_bridge.py
const G = qg(this.options)  // 解析 python + agentRoot
const e = [...G.argsPrefix, l, "--endpoint", this.endpoint]
if (G.agentRoot) e.push("--agent-root", G.agentRoot)  // 0.6.25 严格传
if (G.hermesHome) e.push("--hermes-home", G.hermesHome)
const b = spawn(G.command, e, {
  env: n,  // n = E9I() = process.env + HERMES_AGENT_ROOT if set
  stdio: ["ignore", "ignore", "ignore"],
  detached: true,
  windowsHide: true
})
```

`qg()` 找 `agentRoot` 的顺序（决定错位从哪条路径来）：

```
1. options.agentRoot (构造参数)
2. process.env.HERMES_AGENT_ROOT   ← 主人 7/12 修这里
3. ~/.hermes/hermes-agent/         ← 0.6.25 默认会找这个（不存在）
4. A9I() 自动反推（从 hermes CLI 路径往上推）  ← conda 装的不在标准位
5. cwd
6. /usr/local/lib/hermes-agent ... etc
```

## 修复命令（一行）

```bash
echo 'export HERMES_AGENT_ROOT="/Users/kk/miniconda3/lib/python3.13/site-packages"' >> ~/.zshrc
HERMES_AGENT_ROOT=/Users/kk/miniconda3/lib/python3.13/site-packages hermes-web-ui start
```

## 为什么 conda 装的 run_agent.py 不在 `~/.hermes/hermes-agent/`

主人是 `miniconda3` 装包路径：
- `hermes` CLI 软链：`/Users/kk/.local/bin/hermes` → `/Users/kk/miniconda3/bin/hermes`
- `hermes-agent` 包：`/Users/kk/miniconda3/lib/python3.13/site-packages/hermes_agent-0.18.2.dist-info/`
- `run_agent.py`：`/Users/kk/miniconda3/lib/python3.13/site-packages/run_agent.py`

JS 端 `A9I()`（自动反推）的逻辑是从 `hermes` 二进制位置往回推 2 级 + 几个常见位置，**没覆盖 conda site-packages**。所以 `agentRoot` 落空。

## 验证修复成功的标志

1. server.log 出现 `[agent-bridge] ready at ipc:///tmp/hermes-agent-bridge.sock`
2. `/tmp/hermes-agent-bridge.sock` socket 文件存在
3. 网页不再报 ENOENT
4. `chat-run` socket 能 resume 之前 session（看 log 里 `socket xxx resumed session xxx`）

## 复发场景（什么时候这个错会再出现）

- 重装 hermes（conda 重装 → 路径可能变）
- 换 Python 环境（conda env 切到别的）
- 升级 `hermes-web-ui` 改了 agent_root 解析逻辑
- 改 `HERMES_HOME` 指向别的位置

任何时候只要 `HERMES_AGENT_ROOT` 没设 + conda 装的 hermes-agent 路径变了，立刻复发。

## 相关 1.0.6 之前版本（推测）行为

0.6.25 之前不严格传 `--agent-root`，bridge 自己 fallback 到自动反推，**侥幸**能找到 conda 路径（或者别的回退路径）。0.6.25 严格传 = 立刻暴露配置问题。

npm 0.6.28 已有 release，可能修了也可能没修。**建议先不升**，0.6.25 + `HERMES_AGENT_ROOT` 这套已经稳定。

## 主人这次触发后的复盘要点

1. **JS 端吞 stderr 是设计缺陷** — 主人想看到 Python 错要手跑，不能只看 server.log
2. **conda 装包是主人环境常态** — 任何 Python 路径解析类问题都要先检查 conda site-packages 而不是 ~/.local 或 ~/.hermes
3. **修复要写 .zshrc** — 只用 env 临时传一遍下次 shell 重启就丢。**永久解 = 写到 .zshrc**（主人 7/12 已加）
