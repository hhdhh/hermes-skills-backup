---
name: chrome-headless-debug
description: 用 Chrome headless 模式调试浏览器侧问题（JS 加载失败、空白页、Console 错误、Network 状态、模块 import 失败）。不打开浏览器窗口、不需要主人手动操作，agent 端到端跑出真实浏览器行为。触发词：headless 调试、抓 console 错误、dump-dom、抓 network 状态、调试 Web UI、抓浏览器错误。
---

# chrome-headless-debug

> Class-level skill：用 Chrome headless 模式 agent 端调试 Web UI，不开窗口、不打扰主人。

## 适用场景

- 主人报"页面空白"/"加载失败"/"JS 报错"，agent 需要**真实证据**而不是猜
- 排查 ES module import 失败 / Service Worker 缓存 / WebSocket 协议错误
- 验证 HTML / 静态资源 / Service Worker 是否正常 serve
- 在 macOS 本地（主人的环境）跑，不需要 Linux 服务器

## 核心命令模板

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --user-data-dir=/tmp/chrome-debug-<timestamp> \
  --enable-logging=stderr \
  --v=1 \
  --virtual-time-budget=10000 \
  --dump-dom \
  <URL> \
  > /tmp/chrome-dump.out 2> /tmp/chrome-dump.err
```

**参数解释**：

| 参数 | 作用 |
|------|------|
| `--headless=new` | Chrome 113+ 新 headless 模式（不是老的 `--headless`）|
| `--no-sandbox` | macOS 上必须，否则 sandbox 拒绝 |
| `--disable-gpu` | 避免 GPU 相关警告污染日志 |
| `--user-data-dir` | **每次必换路径**（用 timestamp）—— Chrome 不允许同 user-data-dir 跑多次 |
| `--enable-logging=stderr` | 把日志输出到 stderr 而不是日志文件 |
| `--v=1` | 详细日志（VERBOSE1），看 module / import / network |
| `--virtual-time-budget=10000` | 虚拟时间预算 10s，让 JS 有时间跑完 |
| `--dump-dom` | 输出 DOM 到 stdout（不是渲染截图） |
| `<URL>` | 目标 URL |
| `> /tmp/chrome-dump.out 2> /tmp/chrome-dump.err` | stdout 是 DOM，stderr 是 Chrome 内部日志 |

## Hermes 工具层集成

**绝对不要**：
- ❌ 用 `terminal()` 配合 `&` 后台跑（被工具禁止"shell-level background wrappers"）
- ❌ 用 `subprocess.run(timeout=30)`——Chrome headless 不响应 timeout，会卡死

**正确做法**：
- ✅ `terminal(background=true, notify_on_complete=true)` 拉起
- ✅ 等 25s 后 `terminal(command="pkill -f 'Google Chrome'; cat /tmp/...")` 收尾
- ✅ 或 `execute_code` 里用 subprocess.Popen + sleep + kill

**execute_code 模式推荐**：
```python
import subprocess, os, signal, time

chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
out, err = "/tmp/chrome-dump.out", "/tmp/chrome-dump.err"
user_dir = f"/tmp/chrome-debug-{int(time.time())}"

# 后台跑
proc = subprocess.Popen(
    [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
     f"--user-data-dir={user_dir}",
     "--enable-logging=stderr", "--v=1",
     "--virtual-time-budget=10000",
     "--dump-dom", "http://127.0.0.1:18789/dashboard/"],
    stdout=open(out, "w"),
    stderr=open(err, "w"),
)
time.sleep(20)
proc.send_signal(signal.SIGTERM)
proc.wait(timeout=5)
```

## 抓 module import 失败（核心场景）

```bash
grep -iE "module|import|404|fail|exception|chunk|cors" /tmp/chrome-dump.err | head -40
```

**典型命中**：
```
Import Map: "http://127.0.0.1:18789/dashboard/assets/xxx.js" 
matches with no entries and thus is not mapped.
```
→ 这是 Vite chunk 找不到 import map（HTML 里没 `<script type="importmap">`），Chrome 降级到 module error

**关键判别**：
- VERBOSE1 级别日志**不是真错误**——只是 Chrome 记录"我找不到 import map entry"
- 真正失败要看 stderr 里 `Uncaught` / `TypeError` / `SyntaxError` / `Failed to fetch`
- 用 `grep -E "Uncaught|TypeError|Refused|404|500"` 过滤真错误

## 抓 console 输出

```bash
grep -iE "CONSOLE|^\[" /tmp/chrome-dump.err | grep -vE "VERBOSE1.*components/" | head -30
```

**注意**：Chrome headless 默认把 page console 输出到 stderr，前缀 `[页面 URL]` 区分。

## 验证渲染状态

```bash
# 看 DOM 里关键 class
grep -oE 'class="[^"]+"' /tmp/chrome-dump.out | head -10

# 看根 element
grep -oE '<(div|main|body)[^>]*id="[^"]+"' /tmp/chrome-dump.out | head -5

# 总大小（DOM 是否完整）
wc -c /tmp/chrome-dump.out
```

**判别**：
- `wc -c` < 5KB → JS 没跑完，DOM 没生成
- `wc -c` 5-30KB + 看到 `<body>` + 业务 class → 渲染成功
- 看到 `class="login-gate"` 类 → 渲染出登录页（前端预期行为）

## 抓 Network（subresource 404）

Chrome headless --dump-dom 不直接给 network 详细列表，但**可以通过 stderr 间接看**：

```bash
grep -iE "net::|404|503|connection refused|failed to load" /tmp/chrome-dump.err | head -20
```

**或**用 curl 单独验每个 subresource（更快）：

```bash
# 拿到 HTML 引用的 JS 路径
JS=$(curl -sS http://127.0.0.1:18789/dashboard/ | grep -oE 'assets/[^"]+\.js' | head -1)
curl -sS -o /dev/null -w "$JS: HTTP %{http_code} size=%{size_download}\n" \
  "http://127.0.0.1:18789/$JS"
```

## 截图替代方案（如果 --dump-dom 不够）

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless=new --no-sandbox --disable-gpu \
  --user-data-dir=/tmp/chrome-shot \
  --window-size=1280,800 \
  --screenshot=/tmp/page.png \
  http://127.0.0.1:18789/dashboard/
```

→ 输出 `/tmp/page.png`，agent 用 `vision_analyze` 看。

## 反例（不该做的事）

❌ **不要用 `chrome --headless`（老语法）**——新版是 `--headless=new`，老语法在 Chrome 113+ 行为不同
❌ **不要在 sandbox 容器内跑 Chrome headless**——`--no-sandbox` 是必需的，但生产环境不应该这么用（只用于本地调试）
❌ **不要 `--virtual-time-budget=60000`** ——太大会让 agent 等 60s
❌ **不要连续两次跑不换 user-data-dir**——Chrome 报 "Chrome is being run by another user"
❌ **不要在 stderr 里 grep `VERBOSE1`** 找错误——VERBOSE1 是普通日志，不是错误

## 联动

- `openclaw-dashboard-troubleshooting`：用本 skill 抓 Dashboard 真实错误
- 任何"Web UI 加载失败"类问题：先本 skill 抓证据，再针对性修

## 已知坑（2026-07-14 实战）

1. **macOS 没 `timeout` 命令** —— 用 background + pkill 收尾，不用 GNU timeout
2. **`subprocess.run(timeout=N)` 在 Chrome headless 上失效** —— Chrome 不响应 SIGTERM-with-timeout，用 Popen 手动控制
3. **Chrome --virtual-time-budget 不等于真实时间** —— 它是"虚拟时间"，JS 可以在 10s 内"假装"跑了 10 分钟。要更长观察时间就调大 budget
4. **Chrome stderr 巨量 VERBOSE1 日志** —— 几乎所有网络 / 模块加载都有日志，**先 grep 关键词** 别从头读