---
name: autolife-doctor-operations
description: Diagnose, repair, and maintain Autolife robots (Hermes adaptation); install Doctor/Codex on robot hosts; inspect services, config, hardware, logs, OTA. Use when 机器人故障排查、维修、服务恢复、配置检查、Doctor 诊断、OTA 版本确认、电池恒100%、数据僵死。
---


# Autolife Doctor 运维（Hermes 版 · FAE 效率版）

> 完整描述：Diagnose, repair, and maintain Autolife robots (Hermes adaptation); install and operate Doctor/Codex skills on robot hosts; inspect services, configuration, hardware, logs, connectivity, and OTA version; apply repairs and verify results. 中文触发场景：机器人故障排查、维修、服务恢复、配置检查、Codex 与 Doctor 技能安装、Doctor 诊断、OTA 版本与升级状态确认、电池恒100%、数据僵死。

> 移植自 autolife-doctor-operations@0.5.4（apt 包），2026-09-13 适配 Hermes。
> 缓存插件 `~/.codex/plugins/cache/` 会被 `agent verify` 完整性校验还原——本目录是用户级增强版，doctor 管不着。

## 目标

快速找到机器人故障，完成维修，并用修复后的实时结果确认问题已解决。

## 权限模式

主人已授权**全权限、以效率为主**（2026-09-13）。默认闭环执行：诊断 → 修复 → 复扫验证 → 汇报。不再逐步请示。
仍保留的单点确认（血泪教训换来）：
- 机器人 prompt / 知识文件**替换前**必须三重备份 + md5 校验（流程见 `autolife-robot-prompt-ops` 技能）。
- Guarded 服务（vision-service / gv-control-service / gv-slam-service）restart 前说一声要动哪个、为什么。
- 不删除任何 `.bak.*` 备份（保 90 天）。
- 认证信息只写入凭据文件，不在回复中回显。

## 工作流

1. 确认目标主机（机队：402 机 `192.168.65.66`、B 机 `192.168.50.29`）和用户反馈的现象。
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

- `~/.config/autolife-doctor/config.toml`：targets.server_ip=402 机、gateway=192.168.64.1、component_services=7 个、probes.emergency_stop=状态文件模拟、healing=auto-safe
- 应急开关状态文件：`~/.local/state/autolife-doctor/emergency_stop.state`（工作站无急停硬件，恒 "0" 表示安全态）
- 验证：`autolife-doctor --validate-config` ✅ / `--check emergency_stop` ✅ READY


## 补充行（审批积压恢复）

| AI 对话不能用 / AI chatbot 起不来 | ①**麦克风初始化失败**：`mod_microphone_` 的 `driver_version=v2` 而 sdk 的 GStreamer 驱动只认 `v1` → 报 `initialization failed: 'v2'`（镜 320 实测）。②**选错麦克风**：AI 对话不一定用音频卡上的“内置”——USB Gadget 板载麦（card2, SigmaStar，16000/1ch）才是真麦；PCH（card0, 3.5mm 口）可能悬空无物理麦。③编译 .so 内 info() bug | ①sdk config `mod_microphone_gadget` 的 `driver_version` `"v2"→"v1"`；vision settings `ai_audio_input_device`=`main`（=gadget 真麦）。②测真麦：`arecord -D <dev> -f S16_LE -c 1 -r 16000 --duration=2 -t wav` 分段算 RMS，非零/有突发声=真麦（PCH 悬空 RMS≈0.00005 底噪）；对比 `mod_microphone_3.5mm_jack`(auxiliary,PCH)。验证日志：`Microphone registered on hw:2,0`+`/al_mic_gadget_data` SHM 建起+无 `'v2'` 错。③`info() takes exactly 1 positional argument (3 given)` 在 .so 内，非库版本，转研发 |
