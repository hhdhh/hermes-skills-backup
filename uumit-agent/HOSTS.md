# HOSTS — UUMit Agent v2.7.0

宿主兼容矩阵。未验证客户端不得宣称完全兼容。

| 宿主 | tested | 等级 | 说明 |
|---|---:|---|---|
| Trae IDE | true | L2 | 当前仓库内开发验证：文档 + Node 脚本 |
| Cursor | false | L1 | 文档兼容，Node 脚本理论可用 |
| Claude Code | false | L1 | 文档兼容，需宿主允许本地 Node 执行 |
| Codex | false | L1 | 文档兼容，脚本执行能力待验证 |
| OpenClaw | false | L2 | manifest 兼容字段已保留，需安装链路验证 |
| WorkBuddy | false | L1 | 文档兼容 |
| 悟空（WUKONG） | false | L1 | 有独立技能注册机制（`skill_manage`）+ SandboxV2 沙箱临时目录；**须用宿主技能注册命令装入全局技能库**，见下「特殊宿主安装注意」 |
| Marvis（马维斯） | false | L1 | 通过 shell executor 执行脚本；子进程 PATH 可能无 `node`，脚本已用 `process.execPath` 规避 |

## 特殊宿主安装注意

部分宿主不是"把文件放进某个 skills 目录"这么简单，安装时需对齐宿主自身机制，否则会"装了但用不上"。

### 悟空（WUKONG）— 须注册进全局技能库

- **现象**：Agent 按 fallback 逐文件下载到当前**工作目录/沙箱临时目录**并跑 `install.js`，授权能成功，但 **skill 不在悟空的全局技能库**，下次会话/换任务时发现不到。
- **根因**：悟空有独立的技能注册机制（`skill_manage` / `skill_manage create`）与 SandboxV2 沙箱（`ephemeral_node`，无持久化）；只把文件放进临时目录不等于"注册进技能库"。
- **正确安装姿势**：
  1. 优先用悟空的技能管理命令把本套件**注册进全局技能库**（如 `skill_manage create`，将 `manifest.json` + `SKILL.md` + `scripts/` 一并登记），而非仅下载到工作目录；
  2. 沙箱无持久化时，`memory/` 凭证可能丢失——按「降级策略」每次通过环境变量注入 `UUMIT_API_KEY` / `UUMIT_USER_ID`；
  3. 安装后做「安装位置自检」（见 SKILL.md）：确认 skill 出现在全局技能库，而非仅当前目录。

### Marvis（马维斯）— shell executor 的 node 路径

- **现象**：`install.js` 内部调用 `auth.js` 时报"找不到 node"。
- **根因**：Marvis 用 shell executor 执行脚本，其子进程 PATH 不含 `node`（或为非标准路径）。
- **修复**：本套件所有脚本拉起子脚本时已改用 `process.execPath`（当前 Node 解释器绝对路径），不依赖子进程 PATH 中的 `node`。若用户仍遇到，确认宿主用 `node install.js` 形式启动（而非把脚本喂给一个无 node 的子 shell）。

## 最低要求

- Node.js >= 18；
- 允许执行 `scripts/*.js`；
- 允许读写 `memory/`；
- 能设置或读取 `UUMIT_API_KEY` / `UUMIT_USER_ID`，或完成设备授权。

## 降级策略

- 无法执行脚本：只保留文档引导，不自动调用 API；
- 无网络：不进入 UUMit，交还宿主本地处理；
- 无法持久化 memory：要求每次通过环境变量注入凭证；
- 无法打开浏览器：把授权 URL 与 user code 展示给用户手动完成。
