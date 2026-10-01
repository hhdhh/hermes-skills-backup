---
name: autolife-dialog-tool-authoring
description: |
  Use when 给机器人AI对话加新工具/VL视觉问答/识别恒返回旧答案。三件套部署+SHM取帧。
metadata:
  cangjie.tags: robot, robot-tools, qwen-vl, shm-camera, vision-service
---

# 给 AutoLife 机器人 AI 对话栈加新工具（含 VL 视觉）

在**已有 AI 对话栈**（vision 内置 AIChatbotManager，qwen_native_fc function calling）上最小化加装新能力。改动三件套，其余一律不碰。

## 红线（先读）
- 只加不改：不动音色（realtime voice）、人设（prompt 主体）、对话服务、任何 .so。历史上"为加导览整栈换成 AIChatV3"破音色人设全变，被当场退回。
- 重启 vision 必连带 face-detection（硬规范，两个都要重启，先 face 后 vision 或反之均可，中间 sleep 12）。
- 每处改动先备份（`*.bak.<功能>-<日期>`），改完 md5sum 记录，回滚 = 删新增 + 还备份。
- 凭据不回显：QWEN_API_KEY 只验存在/长度/前缀，不打印。

## Step 1 写工具文件
目录：`<robot_env site-packages>/autolife_robot_vision/robot_tools/<tool_name>.py`
规范（参照同目录 base_tool.py / get_weather_by_gaode.py）：
1. 模块级 `TOOL_SCHEMA` dict：`{"type":"function","name":...,"description":...,"parameters":{...}}`，description 里写清**何时调/何时不调**（防滥用）。
2. 模块级 `run(arguments: dict, ai_mgr=None)`，**返回字符串就是模型照念的话**——写"答案本身"（自然口语），不写"识别结果：""查询完成"；失败返回自然道教话术。prompt 铁律禁过程汇报，源头在返回值。
3. 不写 pre_execute_message（prompt 明令禁止）。
4. 部署方式：本地写好 → paramiko sftp 推送（heredoc/嵌套引号在 robssh 链里必炸）→ 远端 `ast.parse` 验证 → md5sum 记录。

## Step 2 注册
`robot_tools/__init__.py` 的 ENABLED_TOOLS 列表加一行 `"<tool_name>",`（sed 插在同类工具行后）。验证：重启后 vision 日志出现 `Loaded external tool schema: <tool_name>`。

## Step 3 prompt 触发段
`assets/prompt/prompt.txt` 在 `## get_current_time` 段前插入新段：功能/触发句式/规则（返回即答案、看不清直说、禁过程汇报）。插入用 Python `str.replace(anchor, add+anchor, 1)` 而非行号 sed（行号会漂）。先 assert 不含同名段防重复插入。

## Step 4 重启与验证
1. `systemctl --user restart face-detection-service && sleep 12 && systemctl --user restart vision-service && sleep 32`
2. 验日志链：`Loaded external tool schema` 数目 +1；既有 patch（voice-patch/barge-in 等）回显正常；`is-active` 双 active。
3. 单测（不经过对话）：robot_env python 直接 `import` 工具模块调 `run({"question":...})`，确认返回合理。robot_env 直跑注意用绝对路径 python，`conda run --no-capture-output` 亦可。
4. 现场实测：真人对话验证触发 + 话术。

## VL 视觉问答配方（已验证机型：S1/S2, robot_v2_x）
- 模型：dashscope compatible-mode `qwen-vl-max`，key 复用 settings.toml 的 QWEN_API_KEY（同 key 双用途，不用新依赖，urllib 即可）。
- 消息格式：content 数组 `[image_url(data:image/jpeg;base64,...), text]`；帧先缩到宽 960 再 JPEG q82，控 token 与延迟。
- prompt 要锁「离镜头最近的那个人」，防背景物品抢答（办公室背景的真笔记本/工位物品会被误报为手持物）。
- 问题透传：tool 参数 question 直接拼进 VL prompt，保持用户原意。
- 相机帧源：**必须用 rgbd_head_color 原始 RGB 段**（RealSense 彩色流，常开）——jpeg 段按需编码会冻结。细节见 references/shm-camera-feeds.md。
- 本地 Hermes 的 vision_analyze 工具不支持图片输入（messages.content.type 只支持 text），VL 一律走 dashscope 直调。

## 排查：识别/画面恒返回同一旧答案
这是帧冻结不是模型笨。按序：
1. 判活：段内容 md5 间隔 2s 连读两次不变 + mtime 停在服务启动时刻 → 冻结。手相机活跳不能反推头相机正常（不同链路）。
2. jpeg 段冻结属预期（按需编码，无视频客户端连接时只写一帧）→ 换 rgbd 原始段，别修编码器。
3. rgbd 原始段也冻结 → 查 USB：`journalctl -k | grep uvcvideo` 找 `-71`（EPROTO）；USB 重置后 v4l2 节点号漂移，vision 分配错设备，唯一可靠恢复 = 整机重启（冷启动重新枚举+重新分配）。重启后等足 60s 再验（ExecStartPre sleep 10 + 初始化）。
4. metadata 时间戳是 CLOCK_MONOTONIC **微秒**（不是 ms），跨 boot 残留旧值会算出负帧龄——判活以内容 md5 为准。

## 交付物清单
工具文件（md5）+ 备份三份（工具/`__init__.py`/prompt.txt）+ 日志验证摘录 + 现场实测结果。汇报给管理员时列 diff（文件/行号/前后值）。
