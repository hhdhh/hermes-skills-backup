# Hermes CLI 用的 Python 环境路径

主人环境是 macOS + conda，Hermes CLI 装在 `~/miniconda3` 里。**不要用系统 Python**。

## 三种 Python 来源

| 来源 | 路径 | 用途 | 是否装 hermes-agent |
|---|---|---|---|
| **系统 Python**（CommandLineTools） | `/Library/Developer/CommandLineTools/usr/bin/python3` | `pip` 默认在这里 | ❌ 没装 |
| **miniconda3 base env** | `/Users/kk/miniconda3/bin/python3` (3.13.12) | **Hermes CLI 实际跑这个** | ✅ 装在这里 |
| **用户 venv**（坏了） | `/Users/kk/.venv/` | 主人 7/3 装的，pyvenv.cfg missing | ❌ 坏了 |

## 强制用 conda 的 python 跑 pip

每次手动 `pip install` 都用 `/Users/kk/miniconda3/bin/python3 -m pip ...` 或 `uv pip --python /Users/kk/miniconda3/bin/python3 ...`。

**用 uv 的好处**：
- 清华源对 hermes-agent 是稳的（pip 走清华源找不到）
- 不用进 conda env，干跑就行
- 干 run 解 dependency 速度快

## 找现在跑 hermes-cli 的 Python

```bash
# 看 hermes CLI 入口用哪个 Python
head -1 /Users/kk/.local/bin/hermes
# 应输出：#!/Users/kk/miniconda3/bin/python3

# 看 conda env 里 hermes-agent 的版本
/Users/kk/miniconda3/bin/python3 -m pip show hermes-agent | head -5
```

## 不该动的东西

- ❌ `/Users/kk/.venv/`（pyvenv.cfg missing 是主人已知状态）
- ❌ `/Library/Developer/CommandLineTools/`（系统保护，碰了也救不回）
- ✅ `/Users/kk/miniconda3/`（可写，是事实唯一的 hermes-agent 安装点）

## uv 路径

`/Users/kk/.local/bin/uv`（已装 0.11.6），`~/.local/bin` 通常在 PATH 里。命令前要 `--python /Users/kk/miniconda3/bin/python3` 强制指定。

## conda env list 速查

```bash
/Users/kk/miniconda3/bin/conda env list
# 主人环境：base / moss-tts-nano（应该就这俩）
```

Hermes-agent 装在 **base**，不在 moss-tts-nano。
