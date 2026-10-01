---
name: autolife-robot-guide-addon
description: Use when 给已有 AI 对话的机器人加导览——保留原栈只加导航。勿整栈替换。
---

# AutoLife 机器人导览加装（保留原对话栈）

## 范围铁律

- "加导览" = 增量。机器人已有自己调好的对话栈（vision `ai_chatbot_enabled=true`、音色/人设/`robot_tools` 带本机补丁）时只补导航能力——整栈替换会改音色人设，用户第一时间听出来，属于超范围事故。点名要源机同款栈时才走移植（references/transplant-and-pitfalls.md）。
- 动手前先列 diff 清单：把"要改的行"与"不碰的行"（三开关/音色/prompt/补丁）分开写明，改完按清单回读验证。

## 判定现有栈（30 秒）

- vision `settings.toml`（site-packages/autolife_robot_vision/）`ai_chatbot_enabled=true` → vision 内置对话在用；`robot_tools/` 可能带本机补丁（音色统一、tool wait 静默），只加不改。
- `~/.config/autolife-ai-chat-v3/` 存在且有 `ai-chat-v3` unit → AIChatV3 栈（316 型）。两栈互斥，勿同时开。

## 加装流程（默认路径）

1. **启用原生导航工具**（vision 自带，多数机器被注释）
```bash
P=~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/robot_tools
cp $P/__init__.py $P/__init__.py.bak.tour-$(date +%Y%m%d)
sed -i 's|# "control_robot_navigation",|"control_robot_navigation",|' $P/__init__.py
systemctl --user restart face-detection-service vision-service   # 硬规范：重启 vision 必连带 face-detection
```
2. **地图导入**：源机拷 `autolife_robot_gv/ros_ws/maps/<map>.yaml/.png` → python 合并 `maps_index.json`（先备份）→ 重启 gv-control → map_command `{"cmd":"switch_map","map_name":"<map>"}`（cmd 是 `switch_map` 不是 set_active_map，参数键 `map_name`）
3. **新建过 unit 一律 `enable --now`**：只 start 的 unit 机器人重启后导览静默消失（"AI 对话没反应"的头号根因——先 `is-enabled` 再查日志）。

## 验证（三层）

1. 工具加载：`journalctl --user -u vision-service | grep "Loaded external tool schema: control_robot_navigation"`
2. 航点链路：map_command `get_maps` → active_map + prepared_positions（= 工具 enum，模型只能去这些点）
3. 现场：人说"带我去X" → 日志看 navigate 工具触发 → `SharedParams(domain,robot_id).get_value('nav_result')` 应为 `true`

## 排查坑

- 麦克风环静音 ≠ 坏：presence gate 要人 ~1.5m 内说话才放行，空房 smoke_listen 0 signal 属正常待机——先在健康源机跑同命令对照再下结论。
- vision 报 `No module named 'autolife_robot_vision.audio.asr'` 是 2.2.13/2.2.14 版本差异；AIChatV3 的 ShmMic 走 SDK SHM 环不依赖它，勿盲目拷补。

## 部署后沉淀

- 案例归档到飞书「机器人排障案例库」（流程见 autolife-case-log）；移植清单与更多坑：references/transplant-and-pitfalls.md
- 注意：旧技能 autolife-robot-tour-guide 仍把 flow-service 排第一且无保留原栈方案；两技能重叠，需 curator 合并。