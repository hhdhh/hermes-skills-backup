# AutoLife 机器人 NetBird 批量盘点 + 修复脚本

## 用法

```bash
# 1) 盘点 (盘点当前 mesh + 内网状态, 输出四类清单)
python3 audit-robot-netbird.py

# 2) 批量修一台 (执行修复)
python3 fix-robot-netbird.py <机号>
```

## 依赖

- `paramiko` (走 SSH 修复) 或 `sshpass` (直连)
- `jq` (处理 netbird status --json)
- `python3` 标准库

## 设计原则

- **盘点** 只读,绝不修改 mesh / 机器人状态
- **修复** 默认 DryRun, 显式 `--apply` 才动手
- **所有外部副作用** (重启服务, 改配置) 都先打印计划再执行
- **失败可中断**, 一台失败不影响别的
- **不调用 robssh.py** —— 它的 sudo 路径在 batch 修复里不可控,直接 paramiko
