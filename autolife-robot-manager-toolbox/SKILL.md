---
name: autolife-robot-manager-toolbox
description: AutoLife 机器人工具箱（autolife-robot-manager v0.2.0）全部功能清单与复刻命令。Use when 需要用工具箱同款方法检机器人（传感器/相机/关节/腰腿/导航地图/Flow 部署）、装机配置、摇操配置、License/HWID、语音/TTS、路由器、软件更新。
---

# AutoLife 机器人工具箱 v0.2.0（反编译全功能）

当前基准：`autolife-robot-manager-linux-x86_64.tar.gz` **v0.2.0 · workflow_schema 4 · revision aecfc4837284-dirty · built 2026-09-23T06:43Z**（md5 ef7524264114d0536bf0866c2090edf4）。发布包 CArchive cookie/TOC 为**大端**（旧版小端，是防提取改造——自写解析器要兼容两种端序）。

- 反编译源码归档：`~/.hermes/knowledge/wiki/autolife-robot-manager/decompiled-src-v0.2.0/autolife_manager/`（52 模块，pycdc；configuration_workflow 与 ssh_client 反编译失败，asm 在同目录 `cw-v0.2.0.asm`/`ssh-v0.2.0.asm`，用 pycdas 常量补全）
- 旧版（2026-09-09 构建版）源码保留在 `decompiled-src/`，仅作历史对照
- 本机安装版：`~/.local/bin/autolife-robot-manager`（2026-09-23 尚为旧版，待升级）；数据在 `~/.local/share/autolife-robot-manager/`
- 版本指纹快速识别：包内 `autolife-build-info.json`（version/workflow_schema/revision/built_at），PyInstaller 归档 TOC 里 name=autolife-build-info.json

## 架构速览

- paramiko SSH；机器人端用户 `ubuntu`（主流程），autolife 子流程走独立 `autolife` 用户 SSH
- 机器人端 Python：`$HOME/miniconda3/envs/robot_env/bin/python`（Py3.12）；ROS Jazzy：`/opt/ros/jazzy/setup.bash`
- **robot_profiles.py 新增双机型**：`ROBOT_CONFIG_VERSIONS = (('v2_2','robot_v2_2'), ('v3_1','robot_v3_1'))` —— 出现 robot_v3_1 新机型配置，Arm 配置路径只认 `configs/{model}/{version}.json`（找不到必须报错，禁止跨机型 fallback）
- 状态采集 STATUS_COMMAND：hostname/os/kernel/arch/uptime/load/cpu/Mem/df/温度/hostname -I
- conda 定位：CONDA_EXE → ~/miniconda3 → ~/anaconda3 → ~/miniforge3 → ~/mambaforge → /opt/conda；**remote_resources 会验证 conda 归属**（env list --json 唯一拥有者才算数，超时/多拥有者都拒绝）
- 凭据：sqlite robots.db + Fernet credential.key；known_hosts 独立文件
- 跨连接身份核验：SSH 主机密钥 + /etc/machine-id 双因子；跨多次连接的操作（软件更新/Flow 部署/语音配置/TTS 上传）核对不过就停

## remote_resources：机器人资源清单（新核心）

一次 SSH 内联脚本发现一切（schema 1）：python/site_packages、10 个 autolife 包根（autolife_ai / autolife_ai_sdk / autolife_robot_sdk / arm / gv / vision / flow / inspection / kiosk / dashboard）、vision_settings、tts_wav_directory、action_json（arm 包 robot_action.json）、**maps_directory（gv 包 ros_ws/maps）**、ros_setup（/opt/ros/*/setup.sh）、双环境（robot_env + face_detection_env，经 AUTOLIFE_FACE_PYTHON 探测）。所有新功能模块（navigation/flow/tts/teleop）都先跑这个 manifest 再动路径，**不再依赖固定路径**。

## 集成测试四实时流（SSH 内联 python -c，前缀协议）

所有流：远端临时脚本，stdout 行 = `@AUTOLIFE_XXX@` + JSON；stdin STOP/QUIT/EXIT 或断链即停，机器人端不留文件。环境注入：`systemctl --user show <unit> --property=Environment --value` 导入 ROS_DOMAIN_ID/ROBOT_ID/RMW_IMPLEMENTATION/CYCLONEDDS_URI（解决 DDS 阵营分裂）。

### 1. 传感器流（battery/IMU/双激光雷达）
- topic：`/topic_gv_battery_0_{id}` `/topic_gv_imu_0_{id}` `/topic_gv_front_lidar_0_{id}` `/topic_gv_rear_lidar_0_{id}`，qos_profile_sensor_data
- 输出：battery{percentage,voltage,current,temperature,...}；imu{orientation_deg,angular_velocity,linear_acceleration}；lidar{nearest,valid_points,sectors,points≤360}；各带 frequency_hz
- 节点名 autolife_toolbox_sensor_monitor

### 2. 相机流
- robot_env python + cv2 + autolife_robot_sdk 共享内存相机（list_camera_shm_outputs/open_camera_shm_consumer），优先 jpeg>mjpg→color→decoded，排除 mod_camera_head_binocular/rgbd_hand_*
- 640x360 JPEG q72 base64；相机名映射 mod_camera_head_left→头部左相机 等

### 3. 关节流（模型诊断）
- /usr/bin/python3（系统 ROS）+ arm-control-service 环境注入
- topic 组：leg_waist/left_arm/right_arm/neck + 双臂夹爪/灵巧手 + gv_motor/current_motors_status 等；stale 2s 标未知
- URDF+STL 从 SDK 拉（package://autolife_robot_sdk 与相对路径，仅 .stl），本地 HTTP+Qt WebEngine(three.js+urdf-loader) 渲染

### 4. 腰腿控制流（唯一可写流，安全契约）
- **SUPPORTED_CONTROL_CONTRACTS 白名单**：目前仅 `("autolife_s1", "robot_v2_2")`；v3_1 未过审 → 拒绝 HWAPI。契约含 joints/module/max_z_conf(76,155,81)/height_range(-0.56,0)/yaw_range(±25)
- **操作员手动停 arm 服务**（工具不再自动 stop arm；工具检测 arm_service 必须为 inactive/failed 才允许初始化）
- discover_control_contract()：SDK settings.toml sdk_settings.active_robot_model/version（fallback SDK __init__.py GLOBAL_VARS ACTIVE_*）→ 白名单匹配 → arm configs/{model}/{version}.json ENABLED_MODULES 含 mod_motor_waist-leg → SDK descriptions/{model}/configs/{version}.json mod_motor_.mod_motor_waist-leg.devices 核对 joint_name 集合与 can_id 唯一性 → 全过才 HWAPI
- 运行时：joint_clear_error→enable→change_control_mode(position) 逐关节 0.1s；lease 0.5s 超时自动 hold；温度>80°C/yaw 超限/通信断/非 position 模式→blocker；lift 0.02m/s、yaw 5°/s、ramp 0.5s
- stdin JSON：arm/motion(lift_up|lift_down|yaw_left|yaw_right)/hold/disarm/shutdown

## 导航地图管理（navigation.py，新）

- 地图目录：GV 包 ros_ws/maps（从 resource manifest 发现），索引 maps_index.json（≤2MB），地图图片 ≤16MB
- 备份目录：地图目录下 `.autolife-toolbox-backups`
- 地图名规则：`[A-Za-z0-9_][A-Za-z0-9_-]{0,63}`；事件前缀 `@AUTOLIFE_NAVIGATION@`（流式列表 ≤1MB，stop 超时 8s）
- parse_map_yaml + maps_index 解析；支持上传/重命名/删除（先入 .autolife-toolbox-backups）

## Flow 部署（flow_deployment/flow_control/flow_document，新）

- flow-service.service（startup 20s/稳定3次/1s 轮询）；XML ≤4MB；名字规则 `[A-Za-z0-9][A-Za-z0-9_.\-/]{0,127}.xml` 禁 `..`
- 入口文件：Flow 包 settings.toml `[flow_settings] flow_xml_name`；部署 = 上传 XML → 备份并原子改 settings.toml（tempfile+fsync+os.replace）→ restart flow-service
- **试运行（FLOW_TRY_RUN_SCRIPT）**：ros2 action list -t 找 flow+xml 命名的唯一 action → ActionClient 发整段 XML（goal 里选 xml/text 字符串字段）→ 120s 超时自动取消。Flow 包版本不支持临时试运行会明确报错
- **运行控制（flow_control.py）**：`from autolife_robot_flow.ros_handler import ROSHandler`；`ROSHandler(f"{domain}_{robot_id}")` → `shared_para.set_value(key,value)`；keys：flow_state(idle/flow/interrupt)/flow_should_start(true)/is_waiting_vr(false)；环境同四流注入法
- flow_document.py：FlowParam/FlowNodeDefinition + XML 解析（编辑器数据模型；反编译不完整，细节看 ui/flow_editor_page.py 与 asm）

## 摇操配置四件套（teleop_configuration.py，新）

服务自启动后的配置步骤，四项均可独立执行/重试/人工完成/跳过：

1. **teleop_license**：工具读 HWID（`/home/ubuntu/Documents/assets/hwid`，64 hex 正则提取）→ 操作员在证书网站签 365 天证书 → 粘贴正文 → normalize_license_text 校验 → 写 `license.key` → 重启并检查 autolife-relay + rust-web-server。证书正文仅存进程内存：不显示/不写日志/不写断点，切换机器人或写入成功即清空
2. **teleop_vision**：Vision 网卡检查固定 lan0/wlo1（update_vision_network_text 改 vision 配置网络段）→ 重启 vision-service
3. **teleop_admin_endpoint**：读 wlo1 IPv4 → 更新 `/home/ubuntu/Documents/AutolifeRobotAdmin/.env.production`（ADMIN_API_ORIGIN http://127.0.0.1:3000）→ 重启 Admin
4. **teleop_admin_registration**：机器人本机 API（curl 127.0.0.1:3000/version 健康检查）幂等登记设备 + 回读验证
- 原子写事务协议：`.{filename}.autolife.{txid}.json`(状态)/`.rollback`(备份)/`.tmp`(临时) 三件套，mode 0600 校验；build_recover_stale_transactions_command 可恢复残留事务
- 系统服务 spec：autolife-relay.service / rust-web-server.service / autolife-admin-build.service（admin 健康 = curl 3001 + 3000/version）

## 装机配置工作流（schema v4）

断点存 `~/.local/share/autolife-robot-manager/configuration-workflow.json`。v4 可读 v2/v3；旧断点走过 service_autostart 的回退到 teleoperation_resume（摇操聚合节点）；v3/v4 的 final_audit 会重新验收。USER_AUTOSTART_UNITS（8 个 user 服务）：vision/arm-control/gv-control/logo-backend/rust-web-server/autolife-admin-build/autolife-relay/dashboard-backend。

主步骤（pycdas 提取）：preflight → identify_nics → apply_netplan → network_power_cycle → apply_lan0_priority → display → autolife_session（独立 autolife 用户 7 子步：校时/扩容/PCAN/machine-id/更新策略/apport/16G swap）→ ubuntu 七步（linger/identity/domain/service_env/chrome_profile/wifi_sudoers/pipewire + power_cycle）→ software_checkpoint → package_configs → udev_rules → **service_autostart** → **teleoperation_resume（teleop_license/teleop_vision/teleop_admin_endpoint/teleop_admin_registration）** → final_audit → cleanup_backups
可选：local_services / netbird / inspection / hardware_tests / zero_calibration / gpu_test / mobile_5g / restore_unverified_cleanup

- netplan：lan0=192.168.10.2/24 via .1，lan1=dhcp metric 100，写 /etc/netplan/zzzz-autolife-stable-wired.yaml；断连是预期（NETPLAN_APPLY_DISCONNECT_MARKERS）
- 机器身份红线不变：hwid/license.key/id_ed25519.pub 严禁跨机拷贝；每步写入前重比流程编号/hostname/ROBOT_ID/已记录 HWID，不一致停下
- 末端执行器：ENABLED_MODULES raw_decode 原位替换（先删全部 mod_eef_* 再插 selected）；robot_config_paths 新版只认 configs/{model}/{version}.json 无 fallback
- 清理：只删带精确时间戳的 fstab/robot_v2_2/robot_v3_1.json 备份 + 有生成证据的 Chrome 备份，删后复扫，有残留明确失败

## 语音/TTS 配置（voice_configuration.py）

- 配置发现：resource manifest → vision_settings（不再写死 site-packages 路径）
- 单位：vision-service.service（user，startup 30s/稳定2次/journal 200行）；**只查不动 face-detection-service**
- TTS_PROVIDER: kokoro/piper/edge/wav/openai/qwen；REALTIME: openai/qwen/qwen_native_fc/agora/doubao_end_to_end/doubao_gateway/glm；代理 original/azure
- QWEN_REALTIME_PROVIDERS = {qwen, qwen_native_fc}（+doubao？—— frozenset 见源码 19-23 行，qwen 系配 qwen key）
- 保留字段：ai_chatbot_enabled/tts_enabled/start_conversation_on_launch/realtime_api_provider/TTS_PROVIDER/QWEN_API_KEY/OPENAI_API_KEY/OPENAI_PROXY_PROVIDER
- TOML 表解析 `_TABLE_RE`；TTS 选 openai/qwen 时才显示实时 AI/API key/代理配置，其它 TTS 保留设置不提交隐藏字段
- 写法：原子写 + 失败回滚原始 settings.toml 再恢复服务；应用后只重启 vision

## TTS 批量合成（本机）

- edge-tts zh-CN-YunxiaNeural 24kHz/16bit/mono WAV（miniaudio 转换）≤5000 字
- 上传：vision 包 assets/tts/wav（重名 _1.._9999）；进度 `TTS_PROGRESS:{json}`

## 路由器配置（Y2 系列 HTTP CGI）

- LAN 192.168.10.1/24，机器人绑定 192.168.10.2，DHCP 100-200 租约 86400s
- 登录 POST cgi-bin/adm.cgi {CMD:LOGIN,USER:admin,LOGIN:密码} → js/status_data.js 校验
- 型号表：S2→Autolife_S2_{id}/{id}@Autolife/40；S3→Autolife_S3_{id}/Autolife@{id}/44；Pro→Autolife_Pro_{id}/{id}#Pro2026/48
- Wi-Fi js/wifi_data.js + POST internet.cgi wireless2__*（5GHz AES）；绑定 js/ipband_data.js 查占用→IPBANDLIST 删旧→加绑定；机器人 MAC 前缀 c8:98:db；改 LAN 后轮询新 IP 45s

## 软件更新（AList + 事务安装）

- AList 站：https://alist.gz.autolife.ai:8444（SSO 飞书登录，token 缓存 ~/.cache/alist-package-downloader/）
- 包后缀 .tar.gz/.tar.bz2/.tar.xz/.conda/.whl/.zip/.deb/.rpm；版本比较含 build 号
- 上传 ~/Documents/wheel（staging→原子 promote）；事务安装可回滚；example 收尾 PACKAGE_EXAMPLE_SPECS（settings.toml.example → 原子刷新，vision 保留语音密钥字段；无 .example 的归档包不执行收尾）
- versioning.py：NON_BLOCKING_VERSION_PACKAGES={autolife_ai, autolife_ai_sdk}；REQUIRED_ARCHIVE_VERSION_PACKAGES 含 autolife-robot-admin-deploy（必须 archive 版本）

## 姿态/动作格式（robot_pose）

- JSON {left_arm[7], right_arm[7], waist_leg[4], duration:2}，整数度；waist_leg=(Ankle,Knee,Waist_Pitch,Waist_Yaw)；arm=(Shoulder_Inner,Shoulder_Outer,UpperArm,Elbow,Forearm,Wrist_Upper,Wrist_Lower)；限位按 URDF；≤64KB；duration 固定 2.0；不含颈部/基座；只存本机不上传

## 服务健康检查协议（通用）

- show 属性：LoadState/ActiveState/SubState/Result/ExecMainStatus/MainPID/NRestarts/InvocationID/时间戳/UnitFileState/FragmentPath/ControlGroup
- 重启验收：restart 后连续 N 次 active+running 才算稳；journalctl -o json 按 _SYSTEMD_INVOCATION_ID 过滤

## UI 页面结构（ui/）

toolbox_window（主窗，标题栏版本指纹 v{version}·流程v{schema}·{revision}·{built_at}）；集成测试页（传感器/语音/相机/腰腿）；独立页：基本信息/版本更新/配置流程/TTS/路由器/**导航地图页（navigation_page）**/**Flow 编辑器页（flow_editor_page）**；机器人模型页/姿态页/配置错误对话框。腰腿页需勾选安全确认才能 Arm。

## 注意

- 本技能描述的是工具箱的实现逻辑，命令行复刻直接照各节模板 SSH 执行；工具本身 GUI（Qt WebEngine 随包）
- 配置流程中的屏幕方向/自动登录/X11/分辨率是人工步骤，工具只记录"我已手动完成"
- v3_1 机型：目前仅 robot_profiles 配置版本对 + 清理扫描含 robot_v3_1.json 备份；腰腿控制契约未收录 v3_1 → 新机型上线时工具会拒绝 HWAPI，等官方过审
