# OpenClaw 升级：双安装根与审批感知执行

## 适用场景

当 `openclaw update --dry-run --json --no-restart` 显示 invoking root（当前 CLI 所在目录）与 managed service root（Gateway 实际运行目录）不是同一路径时使用。

## 核心规则

1. **版本检查必须覆盖两个根。** `openclaw --version` 正常不代表 Gateway runtime 已更新。
2. **升级前备份两个包根。** 同时保存配置、service env、wrapper 与 LaunchAgent plist。
3. **以 dry-run 报出的 managed service root 为升级目标。** 不要仅凭 `command -v openclaw` 猜升级位置。
4. **用 `--no-restart` 把包升级与服务重载拆开。** 先验证文件版本和配置，再单独重载 Gateway。
5. **审批与聊天确认是两层。** 用户文字回复“继续”表达任务意图，但若运行时仍弹出工具审批，必须等用户在审批 UI 中允许；审批超时后不能重复同一动作或换命令绕过。

## 推荐分阶段

### A. 只读预检

检查当前 CLI、全局包、managed runtime 三处版本；npm dist-tags 与 engines；Node 版本；配置校验；Gateway 健康；LaunchAgent 状态；最后运行官方 update dry-run，记录实际 managed root。

#### 当旧 CLI 在 dry-run 前拒绝新版配置

这是一种引导悖论：默认 CLI 版本较旧，先用旧 schema 校验 `openclaw.json`，于是还没报告 managed root 就以 `config invalid` 退出。

1. 不要立即执行旧 CLI 建议的 `doctor --fix`。
2. 读取 LaunchAgent 的 `ProgramArguments`，定位实际运行的 `.../openclaw/dist/index.js` 与 managed root。
3. 分别读取 global/managed `package.json.version`。
4. 用 managed CLI 执行 `config validate --json`。新版校验通过即可确认配置本身没有坏。
5. 若 managed CLI 的 update dry-run 报 `package manager owner is unknown`，这是复制式 runtime 缺少包管理器归属信息；保留 managed runtime，转而用 global shim 对应的包管理器升级全局 CLI。

### B. 小步备份

不要把目录创建、多个敏感文件复制、两个大型 tar 全塞进一个难以审阅的复合命令，也不要把两个大型归档并行提交审批。分成：

1. 创建 mode-700 时间戳目录。
2. 复制配置、env、wrapper、plist，并设 mode 600。
3. 单独归档 managed runtime，等待该步明确完成。
4. 再单独归档 invoking/global runtime（若不同），等待该步明确完成。
5. 每步只输出目标路径和大小，不输出 env 内容。

小步串行执行便于审批、定位超时和确认部分完成状态；如果某一步审批被拒或超时，停在该步等待，不重做已完成步骤。

### C. 升级但不重启

执行官方更新命令并保留结构化输出。升级后分别读取两个安装根的 `package.json` 版本，确认 managed runtime 达到目标版本；若 invoking root 仍旧，再按包管理器升级全局 CLI，使两者一致。

### D. 配置与服务验证

1. 新 CLI 与 managed runtime 版本一致。
2. `openclaw config validate` 通过。
3. plist lint 通过，ProgramArguments 仍指向预期 runtime 和兼容 Node。
4. 再重载现有 Gateway。
5. 检查新 PID、`/healthz`、Dashboard HTTP 200，并确认日志无 restart loop、SecretRef 或 migration 错误。

## 不要做

- 不因当前 CLI 已最新版就跳过 managed runtime 检查。
- 不在备份未完成时开始原地 npm 更新。
- 不用聊天中的“继续”替代工具审批 UI。
- 不在审批超时后换命令绕过 guard。
- 不打印敏感 env 内容。
