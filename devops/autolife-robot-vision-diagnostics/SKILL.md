---
name: autolife-robot-vision-diagnostics
version: 1.0.0
description: Use when diagnosing Autolife robot vision-service voice/c...
metadata:
  requires:
    bins: ["ssh"]
---

# Autolife robot vision / voice diagnostics

> 完整描述：Use when diagnosing Autolife robot vision-service voice/conversation failures. SSH in, separate hardware from chatbot/workspace faults, and report evidence.

Use this when the user asks why an Autolife robot cannot do voice conversation, especially when they say to exclude microphone/speaker factors and focus on `vision-service`.

## Procedure

1. **Verify network and SSH before service diagnosis.**
   - Check route, ping, and TCP 22 from the current machine.
   - If the user supplied a password, use a temporary askpass helper instead of printing or logging the password.

```bash
set +x
TMPDIR=$(mktemp -d)
ASKPASS="$TMPDIR/askpass.sh"
printf '%s\n' '#!/bin/sh' 'printf %s <PASSWORD>' > "$ASKPASS"
chmod 700 "$ASKPASS"
DISPLAY=:0 SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force setsid ssh \
  -o StrictHostKeyChecking=accept-new \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no \
  <USER>@<HOST> 'hostname; date; uptime'
rc=$?
rm -rf "$TMPDIR"
exit $rc
```

2. **Inspect the running service set without restarting anything.**
   - Use `systemctl --user` first; Autolife robot services commonly run as user services.
   - Collect process, user-unit, port, and recent journal evidence in one SSH call.

```bash
systemctl --user --no-pager -l status vision-service.service || true
systemctl --user --no-pager -l status data-logger-service.service || true
systemctl --user list-units --type=service --all --no-pager | grep -Ei 'vision|camera|face|audio|voice|asr|tts|autolife|snack|robot|ros' || true
ps -eo pid,ppid,stat,etime,cmd | grep -Ei 'vision|camera|face|audio|voice|asr|tts|autolife|snack|order|ros|launch|python' | grep -v grep | head -200
ss -lntup 2>/dev/null | grep -Ei 'python|ros|vision|autolife|:4010|:4011|:4012|:7410|:8000|:9001' || true
journalctl --user -u vision-service.service --no-pager -n 240 || true
journalctl --user -u data-logger-service.service --no-pager -n 100 || true
```

3. **Separate audio hardware initialization from conversation initialization.**
   - Treat these as different gates:
     - Hardware/audio gate: microphone device resolved, GStreamer microphone started, speaker registered, hardware report says no issues.
     - Chatbot gate: AI chatbot / realtime API / workspace initialization succeeds.
   - If hardware lines are green but `Failed to initialize AI chatbot` appears, report it as a vision-service chatbot/config/backend issue, not a mic/speaker issue.

4. **Look specifically for workspace binding and chatbot startup failures.**
   - Grep the vision journal for `Failed to initialize AI chatbot`, `409`, `Conflict`, `workspace`, `chatbot`, `Registration`, `Qwen`, `ASR`, and `TTS`.
   - A `409 Conflict` from a `workspace-robot-bindings/.../workspace-id` endpoint means the robot reached the backend but the workspace/robot binding state conflicted; prioritize backend binding cleanup or workspace assignment before testing microphones again.

5. **Check sibling services that may create noise or load.**
   - An auto-restarting `data-logger-service` can raise load and flood logs.
   - If it fails with `ModuleNotFoundError` for an optional data-collection module, do not call it the primary voice-conversation cause unless the vision chatbot path depends on it. Report it as a secondary issue and avoid disabling/restarting without explicit approval.

6. **Report with evidence, not guesses.**
   - Lead with the root cause class and the decisive log line.
   - Then list what was ruled out: SSH/network, `vision-service` running, mic init, speaker init, TTS init if present.
   - End with next action: e.g. fix robot/workspace binding in admin backend, then restart or ask the user to restart `vision-service` if permitted.

## Pitfalls

- Do not equate `vision-service active (running)` with a working voice conversation; the service can run while the AI chatbot submodule failed during initialization.
- Do not keep probing microphones when the log already shows successful microphone registration; that wastes time because the conversation gate is downstream.
- Do not treat TTS initialization as proof of dialogue readiness; TTS can initialize while ASR/realtime/chatbot initialization is dead.
- Do not restart robot services during diagnosis unless the user explicitly authorizes it; restarting vision/navigation services can interrupt a live robot.
- Do not persist or echo SSH passwords; use `set +x`, a temp askpass script, and remove it immediately.
- **音色不一致（迎宾/动作播报 vs 正常对话）先查双通道**（2026-09-20 修于 321）：对话走 realtime（voice 在 `robot_v2_2.json` `audio.qwen_native_fc.realtime.voice`），迎宾/动作播报走本地 TTS（provider 由 `settings.toml` `[app_settings.tts]` 的 `TTS_PROVIDER` 决定，音色在 `robot_v2_2.json` `audio.tts.<provider>.voice`）。诊断：`journalctl --user -u vision-service | grep "TTS initialized"` 看本地 TTS 实际初始化的 model/voice。坑①：改 `TTS_PROVIDER` 后旧进程不重读配置，必须重启 vision（联动 face-detection）才生效——启动日志仍显示旧 provider 不代表配置无效。坑②：跨 provider 换音色必须整段换（base_url/model/voice 配套），只改 voice/model 而 base_url 还指向别家部署（如 openai 段指向 Azure）会请求失败→播报静音，改错立即回滚。坑③：native FC 动作英文夹杂是另一问题（编译 .so 硬编码兜底），修法见 skill: autolife-robot-action-ops 已知坑 #8。坑④（日志全绿但播报静音，2026-09-20 修于 321）：`tts.<provider>.voice` 填了该 TTS API 不存在的音色（如把 realtime 的 Tina 填给 qwen3-tts-flash）→ 初始化不校验照样打 "TTS initialized"，但每次合成 HTTP 400、错误被吞、返回空音频。诊断：绕过服务直接调 `QwenTTS(FakeHW()).play_voice("测试。")` 打点看 PCM 字节数，或直接 POST TTS base_url 看 400 InvalidParameter。实测 qwen3-tts-flash 可用音色：Cherry/Serena/Chelsie/Jada（女）、Ethan（男）；Tina 仅限 realtime 对话模型。换音色后重启双服务生效。坑⑤（天气不知道，2026-09-20 修于 321）：`robot_tools/__init__.py` 的 ENABLED_TOOLS 默认把 `get_weather_by_gaode` 注释掉了，且 `settings.toml` 的 `amap_key` 为空 → 模型无天气工具可调。修法：① 启用 ENABLED_TOOLS 里的 get_weather_by_gaode；② 给 `get_weather_by_gaode.py` 加 open-meteo 免 key 兑底（无 amap_key 时走 geocoding-api.open-meteo.com + api.open-meteo.com，支持城市名/adcode/英文，内置常用城市 adcode 前缀映射+ WMO 天气码中文表），返回结构与高德一致（lives+forecasts）。
