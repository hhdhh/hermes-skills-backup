# Hermes CLI 升级前检查表

每次升级前**必打**这表，确认环境可升级、有备份、可回滚。

## Step 0: 决策点

| 问题 | 答案 |
|---|---|
| 升级目标版本 | `{填，例如 0.19.0}` |
| 当前版本（升级前快照） | `hermes --version 2>/dev/null \| head -1` |
| 这是 minor 还是 patch | （看版本号第 2 位 vs 第 3 位） |
| 是否跨大版本（fastapi 0→1, starlette 0→1） | （是 → 报告主人提风险） |

## Step 1: 升级前快照（6 项）

```
$ hermes --version   → ??
$ hermes gateway status | grep -E "PID|supervised"   → 7 profile 全活？
$ hermes doctor | tail -30   → 已知警告外有新警告？
$ curl http://localhost:8648/   → 200？
$ ls ~/.hermes/skills/ | wc -l   → 173？
$ ps aux | grep -E "hermes_cli|hermes-web-ui" | grep -v grep   → 几个 PID？
```

| 项 | 升级前 |
|---|---|
| Hermes CLI 版本 | |
| Gateway 7 profile | |
| Doctor 警告数 | |
| Web UI :8648 | |
| Skills 数 | |
| 关键 PID 数量 | |

## Step 2: 备份清单

```
$ ls -lh ~/.hermes/backups/pre-{VER}/    → 6.7M hermes_*.tar.gz + config.yaml.bak
```

```
[ ] tar.gz 备份 hermes_cli + helpers
[ ] config.yaml 备份
[ ] .env 备份（如有）
```

## Step 3: Dry-run 内容

```
$ uv pip install --upgrade hermes-agent --dry-run ... → 列出 -X.Y / +A.B 列表
```

**重点关注**：
- [ ] hermes-agent -OLD → +NEW ✅
- [ ] fastapi 是否跨位？（0→1 major risk）
- [ ] starlette 是否跨位？
- [ ] uvicorn 跳几个 minor？

## Step 4: 装完后必跑

```
$ hermes --version   → v{NEW} (date) Up to date ✅
$ /Users/kk/miniconda3/bin/python3 -c "import hermes_cli, fastapi, starlette, uvicorn; print('OK')"
$ ls /Users/kk/miniconda3/lib/python3.13/site-packages/ | grep hermes   → 旧 dist-info 已删，新 dist-info 在
```

## Step 5: 升级后快照对比

| 项 | 升级前 | 升级后 | OK? |
|---|---|---|---|
| Hermes CLI 版本 | | | |
| Gateway 7 profile | | | |
| Doctor | | | |
| Web UI | | | |
| Skills 数 | | | |
| PID 数 | | | |

## Step 6: 进程层决策（**等主人拍板，不要自决**）

- [ ] 已向主人列 3 档重启方案（A 全 / B 只 web UI / C 现在别碰）
- [ ] 等主人拍板

## 回滚（出现意外立刻跑）

```bash
tar -xzf ~/.hermes/backups/pre-{VER}/hermes_{OLD_VER}_full.tar.gz \
  -C /Users/kk/miniconda3/lib/python3.13/site-packages/ \
&& uv pip install --upgrade --force-reinstall hermes-agent=={OLD_VER} \
   --python /Users/kk/miniconda3/bin/python3 \
   --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```
