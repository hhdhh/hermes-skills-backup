---
name: autolife-doctor-operations
version: 0.5.4-hermes.6
description: Diagnose, repair, and maintain Autolife robots (Hermes adaptation); install and operate Doctor/Codex skills on robot hosts; inspect services, configuration, hardware, logs, connectivity, and OTA version; apply repairs and verify results. 中文触发场景：机器人故障排查、维修、服务恢复、配置检查、Codex 与 Doctor 技能安装、Doctor 诊断、OTA 版本与升级状态确认、电池恒100%、数据僵死。
---

# Autolife Doctor 运维（Hermes 版 · FAE 效率版）

> 移植自 autolife-doctor-operations@0.5.4（apt 包），2026-09-13 适配 Hermes。
> 缓存插件 `~/.codex/plugins/cache/` 会被 `agent verify` 完整性校验还原——本目录是用户级增强版，doctor 管不着。

## 目标

快速找到机器人故障，完成维修，并用修复后的实时结果确认问题已解决。

## 直接接入指令（2026-09-13 主人授权："让你 ssh 到哪台就进哪台"）

主人说"**让你 ssh（或接入）到哪台机器**"或"**ssh 到 X 机查/修 XX**"时，这句话本身就是完整授权，直接闭环执行，不反问、不等拍板：

1. **解析目标**（按顺序兜底）：
   - 给 IP → 直接用。
   - 给机号（402/263/274/294…）且同网段 → `robssh.py ip <编号>` 或 DNS PTR（find-autolife.py）解析。
   - **跨网段 / 机器人不在本地网络** → 走 **NetBird**（见下方"跨网段接入"）。
2. **接入**：`robssh.py <编号|ip> <timeout> <命令>`（ubuntu 用户）/ `robssh.py sudo <编号|ip> ...`（root）。凭据全机队统一 ${ROBOT_CREDS}（ssh 与 sudo 同），已授权无需请示。
3. **检修**：按"快速通道"表直奔检查点；Safe 级服务直接修，Guarded 级（vision/gv-control/gv-slam）restart 前说一声。
4. **修改内容**：改配置/prompt/文件前走对应姊妹技能流程（prompt 改动 → 三重备份 + md5，见 autolife-robot-prompt-ops）。
5. **闭环汇报**：修完复扫对比，汇报改了什么/前后差异/回滚命令。

❌ 反例（不要做）：问"要我现在连进去吗？"——主人指定目标即授权；列方案等拍板——直接干，关键决策事后汇报。

## 跨网段接入（NetBird · 2026-09-13 实测打通并授权）

机器人不在同一网段（客户现场/展会/异地）时，通过公司自托管 NetBird 组网直接 SSH 检修，**无需确认直接进**：

1. **前置**：本机 netbird 已连自托管 Management（`netbird.autolife-robotics.com:443`），本机 NetBird IP `100.98.198.205`。凭据与直连相同（${ROBOT_CREDS}）。
2. **找目标 NetBird IP**：
   ```bash
   netbird status --detail | awk '/netbird.selfhosted:/{name=$1} /NetBird IP:/{ip=$3} /Status: Connected/{print name, ip}'
   ```
   只列**在线**（Connected）的 peer；Idle = 那台机器人 NetBird 没跑或离线。网络里约 118 台设备（autolife-robot-XXX 为主）。
3. **SSH 接入**：NetBird IP 直接走 robssh.py：
   ```python
   from robssh import run
   run('100.98.76.121', 'hostname && uptime', timeout=15)   # 已实测 0.45s 登录
   ```
4. **⚠️ 注册名 ≠ 实际机号**：NetBird 名叫 `autolife-robot-303` 的机器 hostname 实际是 `autolife-robot-294`——**接入后先 `hostname` 核对真实机号**，别信注册名。机队里可能不止一台错位。
5. **优先级**：同网段直连 > DNS PTR 解析 > NetBird 兜底（跨网段时 NetBird 是唯一路径，直接走）。
6. **连不上时**：peer 显示 Idle → 机器人端 netbird 服务没跑/断网，先想别的办法联系现场；显示 Connecting → 打洞中，稍等或等 relay。

## 故障记录闭环（2026-09-13 主人授权："每次问题+解决过程写飞书文档"）

每次故障修复闭环后，**必须**把问题与解决过程写成飞书文档存入云文档，双受众：运营等同事可看 + 运营助手自己的知识库。

**⚠️ 署名身份（2026-09-13 主人指示）**：飞书消息和飞书文档中一律以"**运营助手**"身份出现，不自称灰灰/Hermes/Huihui。文档"记录人"写"运营助手"，文末落款写"本文档由运营助手自动生成"，文件夹命名同理。

- **存放位置**：云空间「机器人故障记录库（FAE·运营助手维护）」文件夹（原名"FAE·灰灰维护"，2026-09-13 起署名改口为运营助手；folder_token 不变），folder_token = `M7CrfNeZrl26eAdbJkrcCEREnCe`（https://autolife.feishu.cn/drive/folder/M7CrfNeZrl26eAdbJkrcCEREnCe）
- **文档结构**（六段固定）：故障现象 / 排查过程 / 修复过程 / 修复验证 / 经验沉淀（避坑）/ 遗留问题
- **命名**：`机器人检修记录：<机号> <故障一句话>（已修复|待观察）`
- **创建命令**：
  ```bash
  lark-cli docs +create --title "<标题>" --doc-format markdown \
    --content @/tmp/repair-log-<机号>.md \
    --parent-token M7CrfNeZrl26eAdbJkrcCEREnCe
  ```
- **写完必须回读验证**：`lark-cli docs +fetch --doc <document_id>` 确认关键段落真的写入（标题/现象/修复/经验四个关键词命中）
- **双写**：同步在本地沉淀技能（如故障模式成体系 → 新建/更新姊妹技能，参考 autolife-robot-dds-camp-split）
- 已有记录：402 机 DDS 阵营分裂 → https://autolife.feishu.cn/docx/LmEddSMvqoApJOxdPctcKQbtnNA

## 权限模式

主人已授权**全权限、以效率为主**（2026-09-13）。默认闭环执行：诊断 → 修复 → 复扫验证 → 汇报。不再逐步请示。
SSH 凭证全机队统一 ${ROBOT_CREDS}（含 sudo，2026-09-13 授权"ssh 到哪台就检修哪台"）；`robssh.py sudo <机号>` 即 root，已实测。
远程检修闭环（定位→进入→诊断→修复→验证→汇报）与 push/pull 文件传输的完整流程：姊妹技能 `autolife-remote-repair`。
仍保留的单点确认（血泪教训换来）：
- 机器人 prompt / 知识文件**替换前**必须三重备份 + md5 校验（流程见 `autolife-robot-prompt-ops` 技能）。
- Guarded 服务（vision-service / gv-control-service / gv-slam-service）restart 前说一声要动哪个、为什么。
- 不删除任何 `.bak.*` 备份（保 90 天）。
- 认证信息只写入凭据文件，不在回复中回显。

## 工作流

1. 确认目标主机（按**机号**，IP 不固定会变：402、263、274、294…）和用户反馈的现象。目标机当前 IP 首选 DNS PTR 法解析（秒级、免凭证）：`python3 ~/.hermes/skills/autolife-find-robot/scripts/find-autolife.py`（自动回写 robots.json）；没抓到再 `robssh.py scan --force`（SSH 兜底）。之后 `robssh.py <机号> <timeout> <命令>` 直接操作。完整决策树见姊妹技能 `autolife-find-robot`。
2. 按症状走"快速通道"表直奔检查点；确实模糊时才跑完整扫描：
   `autolife-doctor --config ~/.config/autolife-doctor/config.toml --once --format json`（工作站 config 已配 targets/probes，2026-09-13）。
3. 机器人侧诊断走 SSH（paramiko 助手 `~/.hermes/workspace/robssh.py`，密码凭据不回显）。
4. 结合知识库（`~/.hermes/knowledge/`）与实时现象定位原因。
5. 执行修复：优先 `autolife-doctor repair <ID> --dry-run` 看计划，Safe 级直接 `--yes`；Guarded 级或手工修复按最小改动执行。
6. 修复后再次扫描对比，并回读进程、服务、日志和目标功能。
7. 汇报：改了什么、前后对比、回滚命令、后续启动方法。

## 快速通道（症状 → 检查点，别从 22 项从头扫）

| 症状 | 第一怀疑点 | 验证 |
|------|-----------|------|
| 前端电池恒 100% / 数据僵死 | DDS 阵营分裂（两套 CYCLONEDDS_URI） | `systemctl --user show <unit> -p Environment` + 显式 export 对应阵营 URI 后 `ros2 topic info` |
| 电池/底盘数据查 topic 永远 0 publisher | 阵营 URI 不匹配，非真的没发布 | 必须显式 `export CYCLONEDDS_URI=<file://...>` 对应阵营再查 |
| 对话啰嗦/破碎 | prompt 版本不对 | `md5sum prompt.txt` 对照版本链（v10-reading = `9ea681d65ab392e2e5a732fdacdec773`） |
| ASR 断句乱 | VAD 配置 | settings.toml: `enable_hybrid_vad=true` + `asr_provider=qwen_realtime` |
| 编号被 TTS 读成日期 | XX-XX 格式 | prompt 里要求逐位中文读法（"零二零九地块"） |
| 服务改了 unit 不生效 | 忘了 daemon-reload | `systemctl --user daemon-reload && systemctl --user restart <unit>` |
| 服务 failed / 前端无响应 | 看分级 | `systemctl --user --failed` + journalctl；Safe 级 doctor 自动修，Guarded 级先查根因 |
| OTA 卡 phase | OTA 状态机 | 读 [ota-version-state.md](references/ota-version-state.md) |

完整 DDS 阵营分裂修复流程：姊妹技能 `autolife-robot-dds-camp-split`。
知识库/prompt 修改标准流程：姊妹技能 `autolife-robot-prompt-ops`。

## 服务分级（与 doctor repair-policy 一致）

- **Safe 级**（auto-safe 自动修）：rust-web-server、logo-backend、dashboard-backend、autolife-admin-build、autolife-relay
- **Guarded 级**（restart 前说明）：vision-service、gv-control-service、gv-slam-service

## 按需读取

- Codex、Plugin 或 Skill 安装：[distribution.md](references/distribution.md)（apt 优先，含缓存还原警告）
- 机器人连接、故障模式分类、诊断或维修：[robot-recovery.md](references/robot-recovery.md)（8 类故障速查表 + 授权边界）
- 只读排查命令清单：[read-only-command-whitelist.md](references/read-only-command-whitelist.md)（工作站/机器人两份分册见白名单文档头）
- 历史事故与飞书记录：[private-knowledge.md](references/private-knowledge.md)
- OTA 版本、升级落地、机队状态：[ota-version-state.md](references/ota-version-state.md)
- 飞书归档/私有知识检索脚本：`scripts/`（archive_lark_*.py / private_knowledge.py）

## 操作约定

- 可在 FAE 工作站、开发机或机器人上安装 Codex、Plugin 和 Skill（apt 优先）。
- 优先使用可重复的命令和仓库已有脚本。
- 维修后始终回读实时状态；不用"命令返回 0"代替功能检查。
- 认证信息只写入对应的用户凭据位置，不在回复和诊断输出中回显。
- SSH 到机器人：密码统一在凭据配置里，不在命令行回显明文。

## 本机 doctor 配置基线（2026-09-13）

- `~/.config/autolife-doctor/config.toml`：targets.server_ip 是**上次扫描时**的 402 机 IP（DHCP 会变，用前先 `robssh.py ip 402` 校准，变了就改 config 再跑 doctor）；gateway 取本机网段 `.1`；component_services=7 个、probes.emergency_stop=状态文件模拟、healing=auto-safe
- 应急开关状态文件：`~/.local/state/autolife-doctor/emergency_stop.state`（工作站无急停硬件，恒 "0" 表示安全态）
- 验证：`autolife-doctor --validate-config` ✅ / `--check emergency_stop` ✅ READY
- **诚实语义**：工作站无电机/传感器硬件，`--once` 显示"未接入"是诚实状态，不伪造 probe 硬凑全绿（见 robot-recovery.md 末节）。机器人上才接真实硬件 probe。
