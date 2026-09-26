# GLOSSARY — autolife-ops 语料共享词典

> 阶段 3 产出 · 全部能力卡共享的术语表（t01-t14）

| ID | 术语 | 定义 | 相关卡 |
|----|------|------|--------|
| t01 | DDS 阵营分裂 | systemd 服务按 CYCLONEDDS_URI 写法分成的两个互不可见发现域——组播派（lo multicast=true）vs 单播派（127.0.0.1 废弃写法）。症状=前端僵尸数据/topic 0 publisher | autolife-ops-dds-split |
| t02 | running ≠ healthy | systemd active 只证明进程被拉起，不证明数据在产/消费已连/业务可用。NRestarts 持续增长=crash loop | autolife-ops-robot-diagnosis |
| t03 | 首个断点 | 故障链中最早异常位置。按时间序从日志找第一个错误；分派按断点不按最终报错 | autolife-ops-robot-diagnosis, autolife-ops-shutdown-conditions |
| t04 | RUN_ID | 每次测试/验收唯一标识，串联身份+版本+配置哈希+证据包 | autolife-ops-shipment-acceptance |
| t05 | R0-R4 | 集成测试五道前置门：安全身份→进程→ROS数据→模块功能→业务 | autolife-ops-shipment-acceptance |
| t06 | FAT / SAT | FAT=工厂验收（受控环境）；SAT=现场验收（客户真实条件）。与出货验收三者不得互相替代 | autolife-ops-shipment-acceptance |
| t07 | hwid 指纹 | 机器硬件身份凭证（wheel/hwid 生成，写入 relay/conf/hwid）。跨机拷贝=双机同 id=两台同时封 | autolife-ops-hwid-repair |
| t08 | qwen_native_fc | Qwen Realtime 原生工具调用通道。需 settings.toml provider + robot_v2_2.json tool_call_enabled 双配置 | autolife-ops-ai-action-config |
| t09 | 三重备份 + md5 | 改关键文件标准动作：cp 三份带日期备份 → 修改 → md5sum 校验一致 | 全卡通用 |
| t10 | 指哪 ssh 哪 | 机号→hostname→IP 定位模式。四路：DNS PTR（首选）/mDNS/SSH 扫描/NetBird | autolife-ops-find-and-ssh |
| t11 | 唯一事实源 | 每类信息只有一个权威文档（A 级），冲突按 A>B>C>D>E 裁决 | autolife-ops-doc-governance |
| t12 | pc2 桥（pc2_front_scan） | 3D 点云按高度带投影成 2D LaserScan 的桥接节点，v2_4/S3 无前雷达机型的建图修复 | autolife-ops-slam-troubleshooting |
| t13 | Discovery 参与者上限 | CYCLONEDDS_URI 缺 Discovery/ParticipantIndex=auto 段时默认参与者上限 10，nav2 14+ 进程必爆 | autolife-ops-slam-troubleshooting |
| t14 | 证据包 | 验收留存的脱敏证据集合：命令输出+截图+配置快照+时间戳+签名。永不包含密码/令牌/密钥 | autolife-ops-shipment-acceptance |
