---
name: autolife-s2-field-repairs
version: 0.1.0
description: Use when S2 机器人日志刷屏/弹窗顶屏/AI对话断/导览回前台等现场故障，按真机验证套路诊断修复。
---

# AutoLife S2 现场故障处置（真机验证集）

> 本技能收纳 S2 世代（wheel 安装布局，包在 `~/miniconda3/envs/robot_env/lib/python3.12/site-packages/`，无 `~/Documents/AutolifeRobotFlow` 源码树）机器人上验证过的修复套路。与 `autolife-remote-repair`（通道/权限）互为配套，本技能只讲「症状 → 诊断 → 修」。

## 快速通道（症状 → 处置）

| 症状 | 根因 | 处置 |
|------|------|------|
| vision 日志刷 `Failed to fetch navigation positions ... no attribute '_map_command_request_slot'` | vision 包内 `robot_tools/control_robot_navigation*.py` 调用 wrapper 中不存在的属性——**包内版本错位 bug**，报研发；同时每 ~0.5s 刷一条淹日志 | 明文 .py 可打补丁：`logging.warning` → `logging.debug`（见下节）；本质修复等研发换版 |
| kiosk 屏黑/被顶掉，logo-backend restart 无效 | **Ubuntu 升级弹窗抢占全屏**（`ubuntu-release-upgrader` 的 `check-new-release-gtk`），不是浏览器死 | 杀进程 + `Prompt=never`（见下节） |
| Qwen realtime `timed out during opening handshake` 一次性报 | 出网瞬时抖动，**自带 1/3→2/3→3/3 重试**，第二轮日志出现 `Qwen realtime WebSocket connected` 即自愈 | 不用修；连续 3 次失败才是真断，查出网 |
| AI 对话彻底断（3 次重试全败） | WiFi 信号弱：`iwconfig wlo1` 看 `Signal=-84dBm` 级别 + `Bit Rate` 掉到 6Mb/s；ICMP 小包通但 TLS 握手超时 | 治本=netplan 把有线 metric 调最低当主路由（改动前备份，需主人点头）；临时=挪近 AP |
| flow 导览"讲完自己回前台" | **langham.xml 状态机设计如此**：各点位 `next_state="navigate_idle"`，该状态固定 `RobustNavigating pose_name="前台"` | 不是 bug。要改行为：`next_state` 改 `"idle"`（原地待命）或调大 `<Wait duration>`，改前备份 + 重启 flow-service |

## vision 刷屏日志降级补丁（warning→debug）

前提：确认报错文件是**明文 .py**（`robot_tools/control_robot_navigation.py` / `control_robot_navigation_flow.py`），不是 .so——.so 不能 sed。打前先 strings 验证 wrapper .so 里确实没有该属性（`strings vision_service_ros_wrapper*.so | grep -c map_command_request_slot` = 0），确认是包内错位而非环境问题。

```bash
SP=~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/robot_tools
F1=$SP/control_robot_navigation.py; F2=$SP/control_robot_navigation_flow.py
TS=$(date +%Y%m%d-%H%M%S)
cp $F1 $F1.bak.logspam.$TS; cp $F2 $F2.bak.logspam.$TS   # 备份
sed -i 's|logging.warning(f"Failed to fetch navigation positions for tool schema: {e}")|logging.debug(f"Failed to fetch navigation positions for tool schema: {e}")|' $F1 $F2
grep -n 'logging.debug(f"Failed to fetch' $F1 $F2   # 验证改到
~/miniconda3/envs/robot_env/bin/python -m py_compile $F1 $F2   # 语法门禁
systemctl --user restart vision-service.service   # Guarded 级：动手前说一声
```

**注意**：该报错会在 vision/arm-control/flow 三个服务里都刷（共享同一调用 `_get_supported_positions()`），只重启 vision 只压它那份；arm/flow 的份等自然重启或单独重启。

## kiosk 屏被升级弹窗顶掉

1. 杀弹窗：`pkill -f check-new-release-gtk`，验证用 `ps aux | grep "[c]heck-new-release"`（**别用 pgrep -f**，会匹配到自己 SSH 命令字串误报存活）。
2. 永久屏蔽：
```bash
sudo cp /etc/update-manager/release-upgrades /etc/update-manager/release-upgrades.bak.$(date +%Y%m%d-%H%M%S)
sudo sed -i 's/^Prompt=.*/Prompt=never/' /etc/update-manager/release-upgrades
grep '^Prompt' /etc/update-manager/release-upgrades   # 应输出 Prompt=never
```
3. **坑**：弹窗包是 `ubuntu-release-upgrader`，不是 `update-manager`——`apt remove update-manager` 治不了这个弹窗，且带 `2>/dev/null` 会把"没删掉"的报错吞掉造成已修假象。自启项查 `/etc/xdg/autostart/` 下 release 相关条目。
4. **杀完弹窗 kiosk 自然回来**（logo-backend 一直活着，弹窗死了就露出来），不需要 restart logo-backend。

## AI 对话断链诊断顺序

1. 先看是不是瞬时抖动（上面快速通道第 3 条）——拉全时段日志别只看报错截点：
   `journalctl --user --since "-15 min" | grep -iE "qwen|realtime|chatbot" | grep -v map_command`
2. 真断了再测出网：`curl -w '%{http_code} %{time_total}s' https://dashscope.aliyuncs.com`；ICMP 通但 HTTPS 超时 = 链路质量差（大包丢），查 `iwconfig wlo1` 信号。
3. S2 世代多网卡多默认路由是出厂常态（WiFi metric 最低当主出口是设计），`netbird status` 显示 Connected 但 ping 高丢包 = 链路在烂但没死，SSH 会时通时断——**遇到空输出/超时，等 30s 重试并给 robssh 加大连接 timeout，别急着判机器死机**。

## flow 导览状态机分析（进阶）

生产导览流程在 wheel 布局下：`~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_flow/flow/`（如 langham.xml）。诊断行为看状态机事件，别读原始日志：

```bash
journalctl --user -u flow-service --since "-3 hour" --no-pager | grep -E "switch state|Navigation command sent"
```

langham 模式结构：`<StateMachine initial_state="idle">` + 每点位一个 `<State>`（导航+`<Wait 10s>`+`<SpeakTTS>`），出口全指 `navigate_idle`，由它 `RobustNavigating pose_name="前台"` 返航。生产已验证节点名：`StateMachine`/`State`/`ChangeState`/`RobustNavigating`/`SpeakTTS`/`SetSharedParam`/`WaitVR`/`Wait`。`<Speak>`/`<TTS>` 未验证别写——最稳是抄同机现役生产 XML 的节点。

## 诊断通用坑

- **远程诊断命令里别嵌入要查的进程名字串**：`pgrep -f <name>` 会匹配到当前 bash -c 命令本身造成假阳性，用 `ps aux | grep "[n]ame"` 括号技巧或 `pgrep -x`（进程名≤15 字符时）。
- **链路抖动时远程命令输出可能整个丢失**（stdout 走一半断流）：关键结论用 `{ ...; } | base64 -w0` 包装输出，收到再本地解码，防丢字。
- **flow 日志 tick 行（`------ tick N --------`）一秒多条刷屏**，看行为要 grep 状态机事件行，别读原始日志。
