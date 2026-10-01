# 动作触发链配置速查（qwen_native_fc 双层开关）

## 动作扩充快速通道（10-01 验证）

两条路均已全管线验证，产物在 `~/gh-action-hunt/`：

1. **toddlerbot 转化**（`convert.py`）：拉 hshi74/toddlerbot 的 motion/*.lz4（MIT），joblib 解出 qpos 轨迹→MuJoCo(=51,nu=30，XML 在 tbrepo/，须 sparse clone descriptions 全目录，MJCF 依赖 assets 相对路径)算左右手末端→pybullet 坐标下降 IK 拉到 AutoLife 末端目标（归一化 SCALE=AL臂展/TB臂展）→限位+碰撞过滤。贴地动作（俯卧撑/爬行/翻身）IK 自动拒绝＝质量过滤，8/59 可用，2xc/2xm 是镜像双版本去重取一。
2. **末端航点 IK 自设计**（`design_actions.py`）：给定每帧末端相对肩位置(fwd,side,up)+节拍，自动解 7-DOF+全帧校验，14/14 成功率，比手写角度可靠得多。重要：IK 达不到的目标会静默钳到可达域边缘，上线前看预览图确认形态。
复核（`verify_merged.py`）独立重跑限位/碰撞/末帧 home 三查；预览渲染（`render_previews.py`）首/中/尾三帧拼图；总表（`make_gallery.py`）出单文件 HTML(base64内嵌)。

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
