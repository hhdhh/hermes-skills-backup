# AIChatV3 导览栈移植与深度坑（仅在目标机无对话栈/点名要 316 同款时用）

## 移植清单

- 打包：AIChatV3 全仓库 + nav_tools + gv 地图（yaml/png）；**排除 hwid/license.key/relay hwid**（同 id 封号红线）；API key 从目标机自己的 vision settings.toml 提取，不跨机传
- 依赖：pip sherpa-onnx/livekit/tomli/pytest/sounddevice；core 与 packs/guide 都 `pip install -e`（同 316 editable 模式）
- 单测：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`——否则 ROS launch_testing 插件冲突报 PluginValidationError
- head-speaker ImportError `pcm_playback_core`：目标机 SDK<2.3.0 无该模块，`speaker_delay_ms>0` 触发 import → robot.toml 置 0 绕过（无 ChatMotion 的机器 delay 本无意义）；勿为此整包升级 SDK（动 vision/gv 依赖）
- 多行远程命令用 base64 传（`echo <b64> | base64 -d | bash`），直接引号会被 shell 解析错乱
- `check_voice_api.py --live` 是笔记本声卡专用；机器人上用 smoke_listen + 真人说话

## 回退（换错栈时恢复原对话）

1. vision settings 三开关还原（ai_chatbot_enabled=true / asr_enabled=false / start_conversation_on_launch=true，以迁移前备份为准）
2. `systemctl --user disable --now ai-chat-v3 ai-chat-v3-head-speaker`（进程清干净，reset-failed 清残留状态）
3. 重启 face-detection + vision，日志确认原音色 session（`voice=Tina` 类）回来

## 与 flow-service 的关系

316 现役导览不走 flow（flow/ 目录为空）：语音栈触发 navigate_to 工具→gv 导航。flow 只适合无人对话的定点循环播报，勿按 flow 模板改导览。