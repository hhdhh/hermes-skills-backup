---
name: autolife-ai-dialog-project
description: Use when 新机器人/新展会项目要配 AI 对话+动作+查询全家桶。323 长沙实战全流程模板。
tags: [autolife, ai-chatbot, 部署, 展会]
---

# AutoLife 机器人 AI 对话项目全流程（323 长沙智谷 · 2026-09-22 实战验证）

适用 S2 系（robot_v2_2/v2_4 · vision 2.2.13 文本 `<tool_call>` 模式）。321 的 native_fc 四层配置**不适用**于此类机器。按序执行，每步都有验证标记。

## 0. 验身与基线
- 网线直连机型：机器人固定 `192.168.10.2`（lan0），接上后先 `hostnamectl` 验身，勿凭 IP 认机。
- 版本：`pip show autolife-robot-vision` / arm 包版本；vision 2.2.13 无 native_fc，走文本 tool_call（journal 标记 `_handle_text_tool_calls`）。
- SSH：`cd ~/.hermes/workspace && python3 robssh.py <ip> <timeout> '<cmd>'`；push/pull：`python3 robssh.py push <ip> <local> <remote>`（**不带 timeout 参数**，插了就坏）。
- 服务四件：arm-control / gv-control / vision / face-detection。systemctl --user 需环境三件套：`export HOME=/home/ubuntu XDG_RUNTIME_DIR=/run/user/1001 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus`（sudo 会破坏它）。

## 1. 网络先行
- 对话哑=先查 DNS：酒店/展会 WiFi 开机时序性 DNS 失败，重启 vision 常自愈。
- NTP：`timedatectl` 确认 Asia/Shanghai 已同步——时间错则 HTTPS/Qwen 全炸。
- 出网能力矩阵要实测：323 案例中 bing(edge-tts) 被酒店网 SSL reset，dashscope/高德/qwen 正常——TTS 选型看这个。

## 2. 核心六文件（三重备份 + md5 验证后改）
SP=/home/ubuntu/miniconda3/envs/robot_env/lib/python3.12/site-packages
1. `$SP/autolife_robot_vision/settings.toml`：ai_chatbot 三开关(ai_chatbot/tts/asr_enabled)+provider=qwen+QWEN_API_KEY+amap_key；[app_settings.tts] TTS_PROVIDER。
2. `$SP/autolife_robot_vision/assets/prompt/prompt.txt`：人设+知识+工具规则（见 §5）。
3. `$SP/autolife_robot_arm/robot_action.json`：动作关键帧库。缺的动作从兄弟机拷（如 316 的 right_handshake 11 关键帧）。
4. `$SP/autolife_robot_vision/robot_tools/control_robot_action.py`：动作工具（enum 三处同步：enum/enumDescriptions/valid_actions）。**2.2.13 上要 getattr 防御 2.2.14-only 属性**。
5. `robot_tools/__init__.py`：ENABLED_TOOLS 白名单。
6. `robot_tools/base_tool.py`：等待语逻辑（不显式给就不播）。

## 3. 动作链路（易踩坑）
- **真 topic 是 `/topic_arm_robot_action_0_<机号>`**（8 publishers）；`/robot_action_0_<机号>` 是死的；过滤时排除 nav2 的 `.../_action/...` topic。
- 测脚本必须带 RMW 环境三件：`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=<127.0.0.1 XML>`，否则看不见 topic（详见 skill: autolife-robot-action-ops）。
- 成功标记：arm journal `Executing action: <name>`。
- 动作执行=ros2 topic publish 一条 JSON 消息，工具返回值只要 `"好"`。

## 4. TTS 决策树（settings.toml TTS_PROVIDER）
- `wav`：只播预录音，没文件就**静默丢句**——只适合固定话术。
- `edge`：免费在线，但要 bing 可达（酒店网可能 SSL reset）。
- `qwen`：走 dashscope，复用 QWEN_API_KEY，与主对话同通道最稳——**首选**。
- `piper`：纯离线兜底，机上 `autolife_robot_inspection/models/MediumOnnx/zh_CN-huayan-medium.onnx` 可用。
- 验证：journal 无 `TTS playback failed`；直测 API 能出音频字节数。

## 4.5 会话状态机三坑（“说话手不动”根治，2026-09-22 实战）
- **症状**：AI 说话时手势被拦腰打断，idle 手势大量 `ignored`。
- **根因**：`enable_wake_sleep_control` 缺省时睡眠状态机空转——每次 chat_active_timeout(60s) 超时就发 home_status，一小时 75 次，把手势通道全占。
- **修法**：settings.toml [app_settings.ai_chatbot] 加 `enable_wake_sleep_control = false`（321 同款）→ home_status 降到对话结束才回位。
- **验证**：`journalctl -u vision-service | grep -c "Published action message: home_status"` 部署前后对比；互动时段 arm journal 应见 `Executing action:` 不再被 `interrupted!`。

## 4.7 音色配置真身（不是 settings.toml！）
- 实时对话音色：`configs/robot_v2_2.json` 里 realtime 块的 `voice`（如 Tina）。
- 工具等待语/pre_execute_message 音色：同文件 `audio.tts.<provider>.voice`（qwen 默认 Cherry/Tina 随版本）。
- 321 同款 = realtime Tina + tts.qwen Cherry。改完 vision+face 重启，journal 看 `Qwen TTS initialized ... voice: Cherry` 验证。
- VOICE_TYPE(settings.toml) 是 bytedance TTS 的键，与此无关，别改错地方。
- **双声割裂坑（2026-09-22 323 实战）**：对话走 realtime、工具等待语走 TTS 通道，两条声道永远不同嗓——Cherry 不在 qwen3.5-omni-realtime 音色列表、Tina 不在 qwen3-tts 列表，无解。**根治 = main.py monkey-patch**：在 main() 里 `async_runtime.setup()` 之后调 `_patch_ai_chatbot_for_single_voice()`，把 `AIChatbotManager.play_tool_wait_message` 替换为 no-op（该类是普通 Python 类可 patch；`.so` 自己解析 tool_call 里的 pre_execute_message 并直调此方法，**不经 base_tool.py**——改 base_tool 无效！）。验证：journal 出现 `323 single-voice patch: tool wait message suppressed`。prompt 侧同步三禁（禁写 pre_execute_message、禁“请稍等我帮您搜一下”过场话、禁“已经准备好了随时为您服务”客服腔欢迎语）。

## 5. Prompt 人味配方（321 骨架提炼）

骨架：人设(ENFJ/ESFP 性格+口头禅禁令) → 展会角色+知识库(Q&A 素材不是台词本) → 说话方式(情绪反应半句→答案一两句→停；每句开场不重复) → 工具规则(每个工具一节：触发词+tool_call 示例+人味话术指导) → 禁词铁律。
**禁词铁律（管理员红线）**：不说“指令/执行中/已发送/调用/系统提示”，不汇报工具过程，pre_execute_message 写人话（“好嘞，我给您挥挥手！”）。工具返回值同步净化——模型会复读返回值！成功返回数据本身或 `"好"`，别写状态描述。

## 6. 高德查询工具（templates/ 里 4 个即用文件）
- 模子：模块级 `TOOL_SCHEMA` dict + `run(arguments, ai_mgr)` 平铺函数（照 get_weather_by_gaode.py；类写法/get_tool_spec() 会被静默跳过）。key 从 `PROGRAM_SETTINGS["app_settings"]["ai_chatbot"]["amap_key"]`。
- 四件：search_nearby_food(周边2km美食) / search_place(周边3km门店) / search_route(驾车+taxi_cost/公交换乘摘要/步行，模式自动选) / search_attractions(城市级景点，类型排序)。

## 6.5 名单查询工具（晚宴分桌 query_seating 模式）
- 场景：客人报名字→查桌号/岗位/房间等静态名单。xlsx 用 openpyxl 读，解析成 `{tables, lookup, pinyin}` 三层 JSON 随工具部署到 robot_tools/。
- lookup 键要做变体归一：去空格（"周 星"）、去括号注释（"胡伟（杭）"→"胡伟"），同名多人（胡伟杭/广）不猜，返回 `ambiguous+candidates` 让机器人反问。
- 拼音容错 v2（湖南口音实战）：机器人 robot_env 自带 pypinyin，工具运行时直接 lazy_pinyin；匹配链=精确→去括号→拼音全同→音节级模糊（zh/z·ch/c·sh/s 归一 0.92，n↔l·f↔h 声母互换 0.82，姓音节权重×2，阈值 0.85）→截断名前缀/首末匹配（刘伟→刘卫武，分×0.95）→difflib 字面≥0.6 兜底。近似多命中返回 ambiguous 反问，模糊命中带 guess=true 让模型先确认名字再报桌。
- 匹配链：精确→去括号→拼音同音→difflib 相似度(≥0.6)；全 miss 返回 `not_found`，prompt 教模型引导签到处。
- prompt 段落示例名用真实在表名字（蔡亮），别用不在表的假名——模型会照抄例句报错桌。
- 新项目改三处：VENUE_LOCATION / VENUE_NAME / city。
- API 权限实测（amap_key 全能）：geocode、place/text、place/around、direction/driving|transit|walking、distance、regeo、inputtips、place/detail v3 ✅；bicycling、place/detail v5 ❌。
- 详细四件套流程见 skill: autolife-robot-prompt-ops「AI 对话工具扩展套路」。

## 7. 开机自复位（可选）
详见 skill: autolife-boot-auto-reset。要点：unit 带 `ExecStartPre=/bin/sleep 90`（321 心跳风暴教训）、ROBOT_ID 对准机号、ConditionPathExists once-per-boot；脚本用 base64 直写保 ubuntu:ubuntu 属主。

## 8. 现场并发纪律与坑
- **现场同事可能同时在改**：每次 push 前必 pull 对 md5；发现别人改了（如往 enum 加了动作）就合并而不是回滚。
- robssh push 落盘 root:root → 可执行文件/脚本改用 `echo <b64> | base64 -d > target && chmod +x` 直写。
- 远端 heredoc JSON 会被引号搞坏：文件本地写好 push，或 base64。
- 重启顺序：arm-control → vision → **face-detection 必连带**（vision 改动硬规范，否则 posix_ipc shm 错）；sleep 25 再 face。

## 9. 交付验证清单（全绿才算完）
- [ ] 四服务 active
- [ ] journal：`Successfully loaded system prompt` + `Qwen realtime WebSocket connected` + 每个新工具一条 `Loaded external tool schema: <name>`
- [ ] 工具机上直跑出真数据（`python $SP/.../robot_tools/<tool>.py` 自测入口）
- [ ] 动作：真 topic publish → arm journal `Executing action:`
- [ ] 现场实喊一嗓子：唤醒→提问→工具调用→人味回答，无机器话术
- [ ] 开机自复位手动拉起一次验全链
- [ ] 启动瞬间零星竞态报错（如 arm_control_pub）只出现不持续即可忽略
