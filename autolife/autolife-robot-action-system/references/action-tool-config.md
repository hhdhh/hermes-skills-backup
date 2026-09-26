# 动作触发链配置速查（qwen_native_fc 双层开关）

AI 对话触发动作需要两个开关同时打开，缺一不可：

## 第 1 层：settings.toml（provider 模式）

路径：`<vision包>/settings.toml`，`[app_settings.ai_chatbot]` 段：

```toml
realtime_api_provider = "qwen_native_fc"   # 普通值 "qwen" 不带工具
```

切换后模型从 `qwen3.5-omni-flash-realtime` 变为 `qwen3.5-omni-plus-realtime`（更强）。

## 第 2 层：robot_v2_2.json（工具总开关）

路径：`<vision包>/configs/robot_v2_2.json`，三层嵌套：

```json
{"audio": {"qwen_native_fc": {"realtime": {
  "tool_call_enabled": false   ← 改 true，默认是 false
}}}}
```

用 python json 改（保留结构）：

```bash
python3 -c "
import json
p = '<vision>/configs/robot_v2_2.json'
d = json.load(open(p))
d['audio']['qwen_native_fc']['realtime']['tool_call_enabled'] = True
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2)
"
```

settings.toml 里**没有**这个键（probe 键名试探无效）——它只存在于 json 配置。

## 生效与验证

重启 vision（联动 face）后看日志：

- ❌ 仍显示 `Qwen Native FC tool calling disabled by config` = 第 2 层没打开
- ✅ 消失该行 + 出现 `Qwen session.created: ... model=qwen3.5-omni-plus-realtime`
- 功能验证：对机器人说"鞠躬"，日志应出现 `Qwen function call: ... control_robot_action` → `Qwen tool executed: 成功发送动作：<名>` → arm 侧 `Executing action: <名>`

## 为什么普通 qwen 模式动作必失败

普通模式无 function_call 事件，系统兜底是 `_check_qwen_transcript_tools` 文字触发词检测——实测该词表只含时间（"我查一下时间"→get_current_time）/搜索类映射，**动作类无映射**。模型输出 `<action>wave</action>` 之类标签系统不认（那是模型自发明格式），tool_detected 恒 False。
