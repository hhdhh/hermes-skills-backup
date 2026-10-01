# Cython 编译 .so 的钩点与探测法（qwen realtime 栈）

适用：autolife_robot_vision 全家桶（Cython 编译，无源码），需要捕获实例/改行为时。

## 探测原则

- 实例属性（Cython cdef class）存 C 结构体，`vars(obj)`/`__dict__` 摸不到 → **不要用属性名探测**。
- 类的公开方法在类字典里，`dir(AIChatbotManager)` 可列出全部可钩方法——写钩子前先 dir 验证存在性。
- `strings <file>.so | grep __pyx_mdef` 也能列出全部方法名（离线探针，不用跑解释器）；带签名注释的行还能看到参数形态。
- 但注意同名方法归属：`update_hvad_state` 在 `AudioRealtimeAPIQwenNativeFC` 上不在 `AIChatbotManager` 上——挂错类直接 AttributeError。

## 已验证可用钩点（320 实测）

| 类 | 方法 | 捕获什么 | 触发频率 |
|---|---|---|---|
| AIChatbotManager | `_get_face_presence` | mgr 实例 + 人脸在场布尔 | hybrid VAD 周期调 |
| AIChatbotManager | `on_microphone_audio_data_received` | mgr 实例（备份） | mic 数据常流 |
| AudioRealtimeAPIQwenNativeFC | `update_hvad_state` | api 实例 + face_present 参数 | VAD 状态变化时 |
| AudioRealtimeAPIQwenNativeFC | `connect` | api 实例（会话重建后重抓） | 闲置 60s 会话重建必触发 |

## realtime 主动说话（qwen realtime 无文本 item 注入）

- `send_text(text)`：改写 session instructions（不是发消息），模型可能改写/发挥——指令式包装：「[SYSTEM EVENT] 立即一字不差说：…说完就停」。
- `create_response()`：触发模型开说（等同用户说完一句话）。
- 预期行为：指令式包装下首句迎宾词一字不差，但模型偶发在后面自然补一句场景话（如签到引导）——这是可接受的发挥，不是补丁失败，别为追「只有一句」反复收紧指令。
- 说完后调 `_restore_base_instructions()` 恢复基础人设，避免指令残留。
- 其余可用方法：`create_response_sync`/`cancel_response`/`send_event`/`update_session`（音色动态切也走这里）。

## 包裹写法骨架

```python
_orig = AIChatbotManager._get_face_presence
def _hook(self):
    r = _orig(self)
    _FACE["mgr"] = self; _FACE["present"] = bool(r)
    return r
AIChatbotManager._get_face_presence = _hook
```

- 必须 call-through 原方法（零行为变化），钩子体内 try/except 兜底。
- 补丁用模块级 dict 保存捕获的实例（Cython 重建会换实例，每次钩子触发自动刷新）。
- 机器人机 logging 只收单参（printf 风格多参会炸）——钩内日志用 `%` 先格式化成单字符串。
