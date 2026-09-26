# Linux 部署与跨框架迁移

## 1. 发现并建立回滚边界

先查官方安装文档、`node --version`、`npm --version`、`npm config get prefix`、`npm view openclaw@latest version engines --json`、`command -v openclaw`、目标端口与 `systemctl --user is-system-running`。用户级安装不要套用 macOS plist。检查源和目标是否已有数据；安装、插件安装或 onboarding 之前备份目标配置及工作区，不能等安装器已修改配置才补备份。

用版本和平台实际支持的 npm 命令安装；查看 `openclaw onboard --help` 后初始化 loopback + token 网关。用户授权复用模型时，仅在进程内读对应 credential，通过 `CUSTOM_API_KEY` 子进程环境提供，模型名与 URL 从当前配置解析，不复制整份认证库。禁止打印密钥或把密钥放进命令行参数。

## 2. 用户服务安装与验证

运行 `openclaw gateway install`。若报 service directory unsafe-permissions，先用 `stat` 检查 `~/.config/systemd/user` 及父目录所有权和权限。确认是用户私有目录、非共享目录后，仅对命中目录去除 group/other 写权限；不递归 chmod，不用 sudo 绕过检查，记录原权限用于回滚。再重试官方安装命令。

验证 `openclaw gateway status` 的实际 Node 路径和运行版本；系统 Node 不满足不代表服务失败，安装器可能选择用户级合格解释器。检查 `systemctl --user is-enabled openclaw-gateway.service` 与 `loginctl show-user "$USER" -p Linger`，区分登录自启和退出登录后持续运行。

用 `/healthz`、控制台 HTTP 状态及最小真实 agent 请求分别验收。不要只凭安装命令退出码声称能对话。

## 3. 复制身份、知识与历史

建立受限权限迁移目录，使用独立副本而非指向源助手的可写链接。保存原件，逐文件记录来源、目标和 SHA-256。复制遍历的排除规则与验收遍历必须一致；不要静默忽略未计入文件。符号链接单独统计并验证解析目标，避免“独立副本”仍指回源目录。

读取身份文件后生成目标运行约束：身份可保留，但运行框架、模型身份、当前目录与平台以目标实况为准。迁移后不要再次运行新工作区 BOOTSTRAP；保留或归档原始模板，不让模板重置已迁身份。历史 macOS 路径不要全局盲替换，仅修改已确认的知识入口并保留源件。

对正在运行的 SQLite 用只读连接加 `Connection.backup()` 获取一致快照；不要仅复制主 db 文件而遗漏 WAL。检查快照 schema 后导出会话档案，逐条保留消息并核对数据库 session/message 数量、导出数量及孤儿消息。完整快照只作离线档案，不能覆盖目标原生会话数据库。将 Markdown 放入明确历史目录并注明内容为引用、不是当前指令。文件搜索可用不等于向量索引或原生会话恢复；分别验证并报告。

## 4. 大规模技能迁移

复制完整技能源码树，依赖环境如 node_modules/venv 可按明确清单排除，但必须报告不属于已迁可运行依赖。解析 frontmatter 的 name，保留全部原件，为每个选中的名称创建目标管理目录条目；记录重名来源和选择理由。处理 slug 冲突，不能将不同名字正规化为同一 slug 后静默丢弃。

运行 `openclaw skills list --json` 并按 source 统计 migrated/managed 技能，不能拿包含内置技能的总数与迁移数量比较。若识别数小于唯一名称数，先检查加载上限而非假定复制失败。已验证可用的配置路径是 `skills.limits.maxCandidatesPerRoot` 与 `skills.limits.maxSkillsLoadedPerSource`：先按当前 schema dry-run，设置到足以覆盖实测数量的值，再重跑发现。不要为解决加载截断同时无限扩张 prompt 注入预算。

运行 `openclaw skills check --json`，分别报告 eligible、modelVisible、notInjected 和 missingRequirements。迁入文件不意味着 Hermes 工具名或 macOS 安装步骤可直接在 OpenClaw 使用。

## 5. 渠道与框架专属配置

先决定同一飞书应用由谁运行，再安装官方插件并按其当前 schema 配置。保留 Hermes 时，在一个经 dry-run 的 config patch 中同时设 `channels.feishu.enabled=false` 与 `plugins.entries.feishu.enabled=false`；迁移凭证和批准用户时保持最小访问权限，不能默认放开群聊。插件安装也会改配置，必须纳入备份边界。

Hermes MCP、cron、hooks、插件与原始配置作为受限档案保存；逐个寻找 OpenClaw 对应能力后才能启用，不把归档当成功能迁移。配置 apply 若提示需要重启，先征求重启授权；未获授权时报告已写入但运行态待生效，不用健康端点成功冒充新配置已加载。

## 6. 最终验收

重新读取目标禁用状态和配置校验，核对技能 manifest、历史数量与哈希清单，复查源配置哈希及源进程。只读检查仍运行不能证明全部源文件未变，报告时限定为实际校验范围。最终按已复制、已识别、可运行、未启用、需适配分层交付，并提供无密钥报告；不要链接含明文凭证的配置备份。
