# Hermes CLI 包在 site-packages 里的实际布局

**坑点**：`pip show hermes-agent` 显示 Location 是 `site-packages`，但**真正的目录不是 `hermes_agent/`**，是 `hermes_cli/`。第一次 tar 时直接 `tar -czf hermes_agent/` 报 "Cannot stat: No such file"。

## 实际文件清单（2026-08-05 升级 0.18.2 → 0.19.0 实测）

`/Users/kk/miniconda3/lib/python3.13/site-packages/` 下，**跟 hermes 相关的所有顶层文件 + 目录**：

| 条目 | 类型 | 来源 |
|---|---|---|
| `hermes_cli/` | 目录 | hermes-agent 包本体（CLI 全部代码） |
| `hermes_bootstrap.py` | 顶层模块 | hermes-agent 包，CLI 启动序列 |
| `hermes_constants.py` | 顶层模块 | hermes-agent 包，常量 |
| `hermes_logging.py` | 顶层模块 | hermes-agent 包，日志 |
| `hermes_state.py` | 顶层模块 | hermes-agent 包，状态管理 |
| `hermes_time.py` | 顶层模块 | hermes-agent 包，时间工具 |
| `hermes_agent-{VERSION}.dist-info/` | 目录 | pip 装的元数据（自动管理） |

## 备份命令（实测可用）

```bash
cd /Users/kk/miniconda3/lib/python3.13/site-packages
tar -czf ~/.hermes/backups/pre-{VER}/hermes_{OLD_VER}_full.tar.gz \
    hermes_cli \
    hermes_bootstrap.py \
    hermes_constants.py \
    hermes_logging.py \
    hermes_state.py \
    hermes_time.py \
    hermes_agent-{OLD_VER}.dist-info/
```

**生成 6-7MB 压缩包**。

## 回滚拆包

```bash
tar -xzf ~/.hermes/backups/pre-{VER}/hermes_{OLD_VER}_full.tar.gz \
  -C /Users/kk/miniconda3/lib/python3.13/site-packages/
# 然后跑 pip install --force-reinstall hermes-agent=={OLD_VER} 修元数据
```

## 怎么验证 hermes_agent 包的"真入口"在哪

```bash
/Users/kk/miniconda3/bin/python3 -c "
import hermes_cli
print(hermes_cli.__file__)            # 应输出 site-packages/hermes_cli/__init__.py
print(hermes_cli.__version__)         # 应输出当前版本
"
```

`hermes_cli.__file__` 就是真路径，`__version__` 就是真版本。

## dist-info 自动管理

pip 升级会自动：
1. 删除旧版本 `hermes_agent-{OLD}.dist-info/`
2. 创建新版本 `hermes_agent-{NEW}.dist-info/`

不需要手动动 dist-info —— 它是 pip 的台账。
