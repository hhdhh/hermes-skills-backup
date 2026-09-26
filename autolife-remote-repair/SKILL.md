---
name: autolife-remote-repair
version: 1.0.0
description: SSH 直连 AutoLife 机器人远程检修：主人说"ssh 到 X 机查/修/改"，就按机号直连进去诊断→修复→验证→汇报闭环。凭据全机队统一，支持 root（sudo）与文件双向传输（push/pull + md5 校验）。当主人说"上 X 机看看"、"连进 402 修一下"、"把 X 文件改了"、"X 机什么问题"时使用。
---

# AutoLife 远程检修（指哪打哪）

> 授权链：2026-09-13 主人授权全机队统一凭据 + "ssh 到哪台就检修哪台"。
> 工具：`~/.hermes/workspace/robssh.py`（paramiko，全部能力已真机验证）。
> 姊妹技能：`autolife-find-robot`（定位）、`autolife-doctor-operations`（doctor 诊断）、`autolife-robot-dds-camp-split`（DDS）、`autolife-robot-prompt-ops`（prompt）。
>
> **🌐 NetBird mesh 通道（2026-09-13 开通，主人已持续授权直接登录）**：公司自建 NetBird（casdoor SSO，飞书登录），165 台设备全网注册，机器人以 `autolife-robot-<机号>.netbird.selfhosted` 命名，NetBird IP `100.98.x.x`。
> **不在现场内网时**：`ping autolife-robot-402.netbird.selfhosted` 或直接用其 NetBird IP（`netbird status -d` 查）→ `robssh.py <NetBird-IP>` 连接。lazy connection 模式下 peer 状态 Idle ≠ 离线，ping 一下即唤醒。
> 本工作站 mesh 名：`kk-gdh-x.netbird.selfhosted`（100.98.198.205）。登录方式：`netbird up` → 浏览器走飞书授权（本机浏览器已有会话，`browser_exec` 打开链接点授权即可）。Session 24h 过期，过期后 `netbird up` 重登。

## 触发词

"ssh 到 X 机"、"上 X 机看看"、"连进 X 机修/查/改"、"X 机有问题"（X = 机号或 IP）。
模糊指代（"刚才那台"、"A 机"）→ 先 robots.json 备注对号，对不上就问一句。

## 标准闭环（每次检修都走全）

```
1. 定位   机号 → IP（缓存 miss 就找: 首选 DNS PTR, 兜底 SSH 扫, 见 autolife-find-robot）
2. 进入   robssh.py <机号> 连通性 + 基本面（hostname / uptime / 磁盘 / 负载）
3. 诊断   按症状走 doctor 快速通道或直接查服务/日志/unit
4. 修复   ubuntu 权限够就用普通命令; 要 root 用 sudo 子命令
5. 验证   重跑诊断命令对比修复前状态; 服务重启后确认 active + 端到端
6. 汇报   改了什么 / 前后对比 / 回滚命令
```

## 🎥 vision 起不来 · native_camera_rs/realsense 修复（2026-09-16 404 机实战）

**症状**：`vision-service` auto-restart 循环 + `data-logger-service` 每 3 秒崩一次（186 次）。日志根因：`UsbV4l2RsCameraReader unavailable; native_camera_rs is not installed` + `librealsense2.so.2.57: cannot open shared object file`。

**诊断定位（关键命令）**：
```bash
# vision 用 systemd USER unit（不是系统级!）——查询/重启要 ubuntu 身份：
export XDG_RUNTIME_DIR=/run/user/1001 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus
systemctl --user status vision-service   # 看 auto-restart / restart counter
journalctl --user -u vision-service -b    # 看真实报错（fail 根因）

# native_camera_rs.so 其实在 autolife_robot_sdk/hardware/multimedia/ 里，但缺依赖 so：
ldd <...>/autolife_robot_sdk/hardware/multimedia/native_camera_rs.so | grep 'not found'
# → 看到 librealsense2.so.2.57 not found

# 确认 sdk 是否可 import（缺 so 时 ImportError）：
cd <sitepkg> && python -c "import autolife_robot_sdk.hardware.multimedia.native_camera_rs"
uname -m && ls /dev/video*    # 相机硬件在不在
```

**修复步骤（补 realsense 运行时）**：
```bash
# 1. 系统 apt 有 ros-jazzy-librealsense2（版本一般 2.58，但 vision 要 2.57）：
apt-get install -y ros-jazzy-librealsense2   # 提供 /opt/ros/jazzy/lib/x86_64-linux-gnu/librealsense2.so.2.58
# 2. 把真实库拷成版本号要求的名字（不能只做软链——ldconfig 按 soname 缓存，软链别名不生效）：
cp -L /opt/ros/jazzy/lib/x86_64-linux-gnu/librealsense2.so.2.58.4 /usr/local/lib/librealsense2.so.2.57
# 3. 给 systemd user unit 加 drop-in 注入 LD_LIBRARY_PATH（/usr/local/lib 不在默认加载路径）：
mkdir -p ~/.config/systemd/user/vision-service.service.d
cat > ~/.config/systemd/user/vision-service.service.d/99-realsense.conf <<'EOF'
[Service]
Environment="LD_LIBRARY_PATH=/usr/local/lib:/opt/ros/jazzy/lib/x86_64-linux-gnu"
EOF
# 4. 用 ubuntu 身份 reload + restart（sudo 跑 systemctl --user 会 No medium found）
export XDG_RUNTIME_DIR=/run/user/1001 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus
systemctl --user daemon-reload && systemctl --user restart vision-service
# 5. 验证：restart 后 journal 出现 6 路 `opened: /camera_image_buffer_*_jpeg` + `SHMCameraFrameConsumer ... opened` = 相机初始化成功；active (running) 不崩。
```

**坑（真机踩过）**：
- `systemctl --user` 必须 ubuntu 身份 + 正确 XDG_RUNTIME_DIR，sudo 会 `No medium found`。
- 不要只建软链 `librealsense2.so.2.57`——**ldconfig 按 SONAME 缓存**，软链别名不进缓存，ldd 仍 not found；直接 cp 成真实文件最稳。
- `/usr/local/lib` 缺则 import 报错，但加 LD_LIBRARY_PATH 后 native_camera_rs import OK。
- vision 报 `AI connection publisher not available / VPN_SOCKS_PROXY_URL not set` 是**配置层**（缺 API key/代理），不是故障——相机/音频/框架已健康。
- 若还有 `data-logger-service`（vision 某版本缺 `...scripts.data_collection` 模块）→ `systemctl --user stop/disable` 它（崩溃循环烧 CPU）。

## 🌐 部署 NetBird（新机器默认流程 · 2026-09-16 定型）

> 主人 2026-09-16 指示：以后在机器人上部署 NetBird 都按这套做。别直接 `curl pkgs.netbird.io/install.sh | sh`——**公司网络掐死了 github.com**，脚本实际从 GitHub 拉 deb，会 133s 超时挂掉。

```bash
cd ~/.hermes/workspace
# 1. 用本地缓存 deb（已在 ~/.hermes/workspace/lib/netbird.deb，0.78.2 一份存档，后续可能要升级）
ls ~/.hermes/workspace/lib/netbird.deb >/dev/null 2>&1 && echo "用缓存: $(dpkg-deb -f ~/.hermes/workspace/lib/netbird.deb Version)" \
  || curl -4 -fL -o ~/.hermes/workspace/lib/netbird.deb "https://ghproxy.net/https://github.com/netbirdio/netbird/releases/download/v0.78.2/netbird_0.78.2_linux_amd64.deb"
# 2. push 到目标机 + 本地装（相连即依赖+服务自动装好）
python3 robssh.py push <机号|IP> ~/.hermes/workspace/lib/netbird.deb /tmp/netbird.deb
python3 robssh.py sudo <机号|IP> 80 "dpkg -i /tmp/netbird.deb && which netbird && netbird version"
# 3. 入网（mgmt/setup-key 取自 S2 向导脚本 robox_combined_y2_wizard.py，内部资料对外打码）
python3 robssh.py sudo <机号|IP> 80 "netbird up --management-url https://netbird.autolife-robotics.com --setup-key 1A7A41D5-653E-4B64-AAA6-764C24844FD8; netbird status | grep -iE 'netbird ip|management|signal'"
# 4. 验证：工作站 ping 它 mesh IP + netbird status --detail 找注册名 + 走 mesh SSH hostname 验明正身
```

关键点：
- 缓存：`~/.hermes/workspace/lib/netbird.deb`（0.78.2，sha256 703b70ee...77fa1）。嫌旧可在工作站重下新版本再 push。
- push 自带 md5 校验，装前确认 size≈15MB（完整 deb）。
- 入网后 `netbird up` 返回 `Connected` 即入网成功；`netbird status` 看 Management/Signal Connected + NetBird IP。
- mesh 名是注册快照，可能错位，入网后**走 mesh SSH `hostname` 核对真实机号**再操作（见下方坑）。
- 已在案：404 机 2026-09-16 按此部署成功，mesh IP 100.98.198.147，全网 171 peer。

## 命令参考（robssh.py 全集）

```bash
cd ~/.hermes/workspace
python3 robssh.py <机号> 15 'hostname && uptime -p'      # ubuntu 用户执行（内网失败自动转 mesh）
python3 robssh.py sudo <机号> 15 'whoami && df -h /'     # root 执行(sudo -S)
python3 robssh.py nb <机号> 15 'hostname'                # 显式走 NetBird mesh(跨网段, 任意位置)
python3 robssh.py nbip <机号>                            # 查该机 NetBird IP(不在 peer 列表=未注册)
python3 robssh.py push <机号> <本地文件> <远程路径>        # 上传(SFTP→sudo cp→md5 双端校验)
python3 robssh.py pull <机号> <远程路径> <本地文件>        # 下载(sudo base64 读回→md5 校验)
python3 robssh.py ip <机号>                               # 查内网 IP
python3 robssh.py list                                    # 机队一览
python3 robssh.py scan --force                            # SSH 重扫(慢, DNS 法抓不到时兜底)
```

**连接策略（核心，2026-09-13 定型）**：`robssh.py <机号>` 会自动走「内网缓存 IP → 失败/未解析 → NetBird mesh 名重试」两级链路。所以**不在现场内网也能直接说机号检修**——mesh 是跨网段通道（WireGuard 打洞，165 台设备虚拟同网，NetBird IP 100.98.x.x）。push/pull 同样吃这条链路。

**写文件的标准姿势**（改配置/改 prompt 都是这个流程）：
```bash
# 1. 先 pull 回本地 + 备份
python3 robssh.py pull 402 /目标/路径/文件.conf ~/.hermes/workspace/backup/文件.conf.$(date +%s)
# 2. 本地改好 → push 上去（push 自带 md5 校验）
python3 robssh.py push 402 ~/.hermes/workspace/改好的.conf /目标/路径/文件.conf
# 3. 验证生效（cat / 服务 reload / 端到端）
```

## 权限分级（doctor 技能同款，两处保持一致）

**直接做，不请示**：只读诊断（查服务/日志/配置/状态）、Safe 级修复、文件编辑（按上面标准姿势带备份）、daemon-reload。

**动手前说一声（单点确认）**：
- Guarded 服务 restart（vision-service / gv-control-service / gv-slam-service）——说清动哪个、为什么
- prompt / 知识文件替换——三重备份 + md5（流程见 autolife-robot-prompt-ops）
- mass-delete、改 system config、影响多台机器的操作

**不碰**：删除 `.bak.*` 备份（保 90 天）、凭据回显。

## AI 对话/TTS 启用（在线点单/语音）关键坑

**症状**："不能 ai 对话" / AI 有回答但没声音。

1. **vision 开关默认全关**：settings.toml 默认 `face_detection_enabled=false` `ai_chatbot_enabled=false` `tts_enabled=false` `asr_enabled=false`。开启标准：face_detection/face_tracking/ai_chatbot/tts = true；**`asr_enabled` 保持 false**（该版本 ASR 集成在 realtime API 里，开 true 会报 `No module named 'autolife_robot_vision.audio.asr'`）；`enable_workspace` 看业务（空 order_server_url 时开 true 报 `order_server_url is required`，参照 401/303 正常机保持 false）。
2. **Kokoro TTS 联网卡死**（`Network is unreachable` + huggingface.co 重试）：kokoro 走 `hf_hub_download` 每次联网 HEAD 校验。机器人无外网时，即使本地 ~/.cache/huggingface/hub 里模型全齐也会卡。**解法：给 vision-service systemd unit 加 `Environment="HF_HUB_OFFLINE=1"`**，强制走本地 cache（模型 config.json/kokoro-v1_1-zh.pth/voices 确认齐全即可）。
3. **`info() takes exactly 1 positional argument (3 given)`** 出现在 `Failed to initialize AI chatbot`：非致命，Qwen session 仍建立、jieba/TTS 仍加载，忽略即可。
4. **重启后才生效**：settings.toml / face_detection.json / systemd env 改动都要 `systemctl --user daemon-reload` + `restart vision-service.service`。

参照正常机（401/303）AI 对话配置。

## VR 遥操自动退出同步（idle 回收）修复

**症状**：VR 遥操持续操作约 10-15 分钟，自动退出同步模式。

**根因**：`autolife-relay`（数据中继，224 上跑）有**硬编码默认 `idle_connection_timeout`≈600s**，把 VR 长连接当空闲回收。日志证据（判断时 grep）：
- `rust-web-server`: `device lifecycle marked offline ... reason=HEARTBEAT_TIMEOUT` + `GRACE_PERIOD_EXPIRED`
- `autolife-relay`: `CLOSE_CONNECTION Connection <id> | Reason: HEARTBEAT_TIMEOUT` ← 真正判死那环

**排查链路**：`ss -tnp | grep :3000` 找 VR 源 IP → 确认 VR 连 lan0 网段（`192.168.10.x`）、ping 延迟极低（0.4ms）→ 排除网络断 → 定位是中继层的空闲回收。

**修复**（改 `/home/ubuntu/Documents/autolife-relay/conf/config.yaml`，配置里没有这些字段=用硬编码默认）：
```yaml
idle_connection_timeout: 0   # 禁用空闲清理(根治)
heartbeat_timeout: 300       # 心跳超时放宽
send_timeout: 60
```
改完 `systemctl --user restart autolife-relay.service`。**验证**：启动日志 `Handshake complete. Heartbeat: 5s, Timeout: 300s`，且 config 打印行里有 `idle_connection_timeout: 0`。

**坑**：改动前先确认 relay 二进制支持的字段名（`strings bin/autolife-relay | grep -i timeout` 能看到 `idle_connection_timeout`/`heartbeat_timeout`/`send_timeout`，且注释明示 `0 disables idle cleanup`）。

## 已知坑（真机踩过）

- **"0 号机"有两台**（hostname 同为 autolife-robot-0，2026-09-13 见于 64.128 / 65.240）——按 IP 操作前先 `robssh.py <机号> 'hostname && ip addr'` 确认身份。
- **DNS PTR 表会骗人**：现场动机器/断电后 PTR 残留，DNS 显示"在线"但 SSH 连不上。判在线以 SSH 实连为准。
- **sudo 输出污染**：`sudo -S` 偶尔把提示混进 stdout，判断结果别只看输出里有没有关键词，看 `[exit N]` 之外的实质内容/校验值。
- **NetBird 注册名可能错位**：`autolife-robot-303.netbird.selfhosted` 连进去真实 hostname 是 294（2026-09-13 实测）。mesh 名只是注册时的快照，机器换系统/改名不更新。**连上先 `hostname` 验明正身再操作。**
- **DHCP 换 IP**：连不上先重扫（DNS 法几秒，SSH 法几分钟），别急着判机器死机。
- **robssh.py 第二参数是 SSH 连接 timeout（秒），不是命令执行 timeout**：要远程 `sleep N` 等服务启动再 `journalctl`，必须把 N 加到 robssh 参数里，否则 sleep 在 ssh session 里被一并截断——连 N+5 都执行不到。
- **192.168.10.2 = 全机队网线直连固定 IP（lan0），接哪台就是哪台**（2026-09-18 主人明确；S2 装机向导把每台机器人 lan0 静态配成 192.168.10.2/24、网关 .1）。经此 IP 连入后必先 `hostname` 验明是哪台再动手，ROBOT_ID 按实查为准（2026-09-17 实连是 316）。
- **journalctl 看错误要跨 service 不要只盯 `-u <unit>`**：arm service 启动报的错误，可能来自 action control 子进程、`autolife_robot_arm/settings.toml` 解析路径、SDK 子目录加载，输出仍打 `-u arm-control-service.service` 但**根因不在那个 unit 文件里**。**用 `journalctl --user --since today | grep -iE 'error|exception|robot_v'`** 横跨所有 user service 抓全，再按时间戳归类。
- paramiko 线程噪音：脚本已静音；自己写临时代码时记得 `logging.getLogger("paramiko").setLevel(logging.CRITICAL)`。

## 与其它技能的衔接

| 需求 | 去处 |
|------|------|
| 找不到机器 / 解析 IP | `autolife-find-robot`（DNS PTR 首选） |
| 系统性诊断（22 项扫描/OTA/电池） | `autolife-doctor-operations` |
| DDS 阵营分裂（电池恒 100%/数据僵死） | `autolife-robot-dds-camp-split` |
| 开机自动复位机械臂（装/查/撤） | `autolife-boot-auto-reset` |
| prompt / RAG / 知识文件修改 | `autolife-robot-prompt-ops` |


## 补充（patch，审批积压恢复）

## arm-control-service 崩溃循环 + GV 电机静默（404 机 2026-09-16）

**症状**: `journalctl --user -u arm-control-service -f` 无限重启, `restart counter` 递增。日志链:
```
PcanCanInitializationError: The value of a PCAN-Hardware handle is invalid
mod_motor_gv: 电机 1-4 Joint_Ground_Vehicle_* 在 PCAN_USBBUS1/2/3/4 都没有响应
Arm joint control process died during initialization!  → initialization timeout
GV task process died, shutting down...  → ARM service thread exiting...  → 主进程自杀
```

**两层根因**:
1. **PCAN 驱动陈旧句柄** → 修: `sudo rmmod pcan && sudo modprobe pcan`（重扫 USB 重建句柄）。验证: `python -c` 用 python-can 逐个+并行 open PCAN_USBBUS1-4 全 `BusState.ACTIVE` 即好。
2. **GV 底盘电机 CAN 静默** → 硬件层: 4 条 PCAN 总线发 0x280 状态轮询帧 0 响应, **而手臂 DM 电机正常** → GV 电机控制器没上电/接线断。软件修不了, 要现场查供电(保险丝/电源开关)。

**后续连带**: arm 服务因 GV 电机连不上 → arm joint 子进程 init 超时死 → gv task 也死 → `main.py` 监测线程(died unexpectedly) → 主进程自杀 → systemd 无限重启。

**止血**(GV 供电修好前): `systemctl --user stop arm-control-service` 停稳不进 crash 循环; gv-control-service(定位/imu/lidar)和 vision-service 保持 active 不动。

**恢复**(现场修好 GV 供电后): `export XDG_RUNTIME_DIR=/run/user/1001 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus; systemctl --user start arm-control-service`, 然后 `journalctl --user -u arm-control-service -f` 看 mod_motor_gv 是否不再报 not responding。

**架构要点**(autoły 机器人): `arm-control-service`=`autolife_robot_arm.main` 管手臂+GV底盘电机(它 config robot_v2_2.json ENABLED_MODULES 才有 mod_motor_gv, vr_gv_control_enabled=true)。`gv-control-service`=`autolife_robot_gv.main` 只管 IMU/battery/lidar(**不含 mod_motor_gv**), 定位导航用, 不抢 pcan。

**PCAN 硬件**: 2× PEAK XCAN-USB Pro FD(USB idVendor 0c72/0011) = 4 通道 /dev/pcanusbfd32-35(via pcan.ko Release 20250213)。lsusb 有、/dev 有、python-can open 成功 = 驱动层 OK; CAN 线上无电机帧 = 电机/供电/接线层。

## arm-control-service 崩溃循环
