# 动作触发链排查手册

## 完整链路

```
语音 → ASR → Qwen Realtime 会话 → 工具调用（3 条可能通道）
  A. 原生 function_call 事件 → _handle_native_tool_func_call   ← 唯一可靠通道（需 qwen_native_fc + tool_call_enabled=true）
  B. 文本检测 _check_qwen_transcript_tools → _infer_qwen_tool_from_transcript  ← 只映射时间/搜索词，无动作词
  C. 模型自造标签 <action>wave</action>                       ← 任何代码都不解析，幻觉格式
→ _publish_action → DDS /control_topic_<domain>_<robot_id> → arm-control 播放 ROBOT_ACTIONS[名字]
```

## 配置矩阵（两处都要改）

| 文件 | 键 | 值 |
|---|---|---|
| `…/autolife_robot_vision/settings.toml` | `realtime_api_provider` | `"qwen_native_fc"` |
| `…/autolife_robot_vision/configs/robot_v2_2.json` | `audio.qwen_native_fc.realtime.tool_call_enabled` | `true`（出厂 false） |

改完重启 vision-service（+3s 后 face-detection-service 联动）。

## 日志判读（journalctl --user -u vision-service）

| 日志行 | 含义 |
|---|---|
| `Qwen Native FC tool calling disabled by config` | robot_v2_2.json 开关没开 |
| `session.created: model=qwen3.5-omni-plus-realtime` | native_fc 模式生效（flash = plain qwen） |
| `tool_detected=False` 但 AI 回复带 `<action>` / `<tool_call>` 文本 | 模型想调但通道没接住，查上面两配置 |
| `Published action message: wave` | 动作真的发出去了（idle2/idle3 正常出现只代表 idle 通道通） |

## 逆向 .so 的spy技法（厂商代码全是 Cython 编译）

1. 属性探测：mock self 用 `__getattr__` 记录名字、抛 AttributeError —— Cython 静态绑定的属性名照样能抓到（如 `_qwen_tool_call_enabled`、`program_settings`）。
2. 链式深挖：DeepSpy 的 `__getattr__` 返回 self、`__getitem__`/`get()` 记录键名并按需返回真值或 self，能一路挖到三层嵌套配置键（`[app_settings][ai_chatbot] → get(audio) → get(qwen_native_fc) → get(realtime)`）。
3. 字符串常量在 Cython 编译后是 interned 运行时创建，`strings .so | grep 中文/模板串` 大概率搜不到——别在字符串追逐上耗时间，直接跑运行时 spy。
4. 调用编译方法要 `source /opt/ros/jazzy/setup.bash && conda run -n robot_env python …`，否则 rclpy/std_msgs 导入失败。

## prompt 动作段写法

- qwen_native_fc 模式：写标准 function calling 描述（工具名+参数+场景），系统自动注册工具，模型走原生 FC。
- 若被迫用 plain qwen：用厂商 `<tool_call>` XML 格式（参考 `prompt.txt.example.qwen`）：`<tool_call>\n{"name":"control_robot_action","arguments":{"action_name":"wave","action_type":"play"},"pre_execute_message":"好嘞"}\n</tool_call>`，且 max_output_tokens 要够大（模型常在闭合标签前被截断）。
