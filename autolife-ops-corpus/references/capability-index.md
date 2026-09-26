# 能力索引（完整版）

| capability_id | 标题 | 重要度 | 意图 | 关键词 | 能力卡 |
|---|---|---|---|---|---|
| cap.autolife-ops.robot-diagnosis | 五层健康模型与固定诊断顺序 | critical | 机器人排障；健康判定；找断点；服务正常但没数据 | 五层健康、NRestarts、首个断点、崩溃循环、zombie、topic 0 publisher、running healthy | capabilities/autolife-ops-robot-diagnosis.md |
| cap.autolife-ops.dds-split | DDS 阵营分裂排查修复 | critical | 电池恒100%；话题僵尸；服务互相看不见；CYCLONEDDS_URI | DDS、CYCLONEDDS_URI、阵营分裂、组播、电池100%、zombie data、multicast | capabilities/autolife-ops-dds-split.md |
| cap.autolife-ops.slam-troubleshooting | SLAM 建图空白排查修复 | high | 建图空白；地图无形状；slam 收不到雷达；nav2 参与者爆限 | SLAM、建图空白、laser_merger、pc2桥、参与者上限、numpy crash | capabilities/autolife-ops-slam-troubleshooting.md |
| cap.autolife-ops.shipment-acceptance | 出货验收门禁（G0-G6 + FAT/SAT + 证据包） | critical | 出货验收；FAT；SAT；G5 放行判定；证据包整理；恢复交付态 | 出货、验收、FAT、SAT、G0-G6、R0-R4、证据包、脱敏、INCOMPLETE | capabilities/autolife-ops-shipment-acceptance.md |
| cap.autolife-ops.ai-action-config | AI 对话动作配置与新动作部署 | high | AI对话带动作；新增动作；tool_call 不触发；关键帧部署 | qwen_native_fc、tool_call_enabled、动作、关键帧、pybullet、robot_action.json、enum | capabilities/autolife-ops-ai-action-config.md |
| cap.autolife-ops.shutdown-conditions | 排障停止条件与恢复验证 | high | 该不该继续修；升级判定；修复验证；偶发故障处置 | 停止条件、升级、恢复验证、crash loop、SIGSEGV、复发、安全事件 | capabilities/autolife-ops-shutdown-conditions.md |
| cap.autolife-ops.find-and-ssh | 机器人定位与远程检修工具链 | high | 机号找机器人；远程 SSH；批量盘点 | DNS PTR、mDNS、robssh、NetBird、hostname、192.168.10.2 | capabilities/autolife-ops-find-and-ssh.md |
| cap.autolife-ops.hwid-repair | relay hwid 身份修复 | medium | relay 握手失败；管理端 offline；hwid 修复 | hwid、fingerprint、handshake、REGISTER、relay、双机同id | capabilities/autolife-ops-hwid-repair.md |
| cap.autolife-ops.connection-switch | 连接方式切换三文件法 | medium | 切换连接方式；管理端 offline 排查；现场直连配置 | relay config、PUBLIC_API_BASE_URL、signaling_server_url、wlo1、直连 | capabilities/autolife-ops-connection-switch.md |
| cap.autolife-ops.rustfs-transfer | RustFS 对象存储传输 | low | RustFS 上传下载；rclone 超时排障 | rustfs、rclone、proxy、env -u、对象存储 | capabilities/autolife-ops-rustfs-transfer.md |
| cap.autolife-ops.doc-governance | 文档治理与 Agent 工程规范 | medium | 文档冲突裁决；新文档定级；Agent 权限配置；归档取代 | 唯一事实源、权威等级、superseded、应用身份、群聊安全域 | capabilities/autolife-ops-doc-governance.md |
| cap.autolife-ops.s2-installation | S2 装机部署全流程（S0-S2） | medium | 新机装机；裸机初始化；重装恢复 | 装机、S0-S2、G0-G2、netplan try、MAC映射、模板覆盖 | capabilities/autolife-ops-s2-installation.md |
| cap.autolife-ops.numpy-shim | numpy 2.x 兼容 shim 与崩溃循环修复 | medium | numpy 2 崩溃循环；闭源包兼容 | numpy 2、np.cross、sitecustomize、shim、crash loop | capabilities/autolife-ops-numpy-shim.md |
| cap.autolife-ops.symptom-map | 症状→诊断链速查表 | high | 按症状直查；语音无响应；导航不起；抓取失败 | 症状映射、麦克风能量、typesupport、CAN 超时、离线排查 | capabilities/autolife-ops-symptom-map.md |
