---
name: autolife-robot-dds-camp-split
version: 1.0.0
description: "AutoLife S1 DDS 阵营分裂排查修复。Use when 前端电池恒100%、数据僵死、topic 查询 0 publisher、CYCLONEDDS_URI 阵营互不可见。"
metadata:
  triggers:
    - "电池恒100%"
    - "数据僵死"
    - "DDS 阵营"
    - "topic 0 publisher"
    - "CYCLONEDDS"
---

# AutoLife S1 DDS 阵营分裂（2026-09-12 实战沉淀，402 机验证）

## 病因

机器人 systemd user 服务分两套 `CYCLONEDDS_URI` 阵营，互不可见：

| 阵营 | 成员 | URI 特征 |
|------|------|----------|
| **组播派**（正确） | `gv-control`（发布底盘/电池数据）等 | `lo` + multicast，`<Peers><Peer Address="..."/></Peers>` 或默认组播 |
| **废弃单播派** | `logo-backend`、kiosk 等 9 个消费方 | `127.0.0.1` 单播指向旧地址 |

消费方在废弃阵营 → 永远收不到 gv-control 的数据 → 前端电池恒 100% 或数据僵死。

## 症状速查

- 前端电池恒 100%
- 电池/底盘数据不更新（僵死）
- `ros2 topic info /xxx` 显示 0 publisher（**跨阵营查询的假象**，不是真没发布）

## 排查流程

```bash
# 1. 列所有 user 服务的环境变量里的 CYCLONEDDS_URI
for u in $(systemctl --user list-units --type=service --no-legend | awk '{print $1}'); do
  echo "== $u"; systemctl --user show $u -p Environment | grep -i cyclonedds
  cat ~/.config/systemd/user/$u.d/*.conf 2>/dev/null | grep -i -A2 cyclonedds
done

# 2. 分阵营验证 topic（关键：必须显式 export 对应阵营 URI 再查）
# 组播派：
export CYCLONEDDS_URI=file:///path/to/multicast-uri.xml
ros2 topic info /chassis_state   # 应有 publisher
# 废弃派 URI 下查同一 topic → 0 publisher = 阵营分裂实锤
```

## 修复

把废弃阵营消费方 unit 的 `CYCLONEDDS_URI` 改成组播版：

```bash
# 1. 找到消费方 unit 的 override 或 Environment=（在 ~/.config/systemd/user/ 下）
# 2. 改成与 gv-control 一致的 lo+multicast URI
# 3. 生效：
systemctl --user daemon-reload
systemctl --user restart logo-backend.service  # 逐个重启消费方
# 4. 端到端验证：WebSocket 前端看电池数据是否恢复实时更新
```

## 坑

1. **跨阵营查 topic 永远 0 publisher** —— 别被骗，先确认自己在哪个阵营 URI 下查的
2. **改 unit 不 daemon-reload 不生效** —— 必须 reload + restart
3. **验证用 WebSocket 端到端**，别只看 topic echo（echo 可能碰到别的坑）

## 已知机队状态（按机号记录，IP 会变不写死）

- ✅ 402 机：2026-09-12 DDS 阵营分裂已修复
- ⚠️ 263 机：同症状，未处理

> **每台机器的 IP 都不是固定的（DHCP 会变）**。不要在任何地方写死 IP。
> 连接前先解析——首选 DNS PTR 法（秒级、免凭证）：`python3 ~/.hermes/skills/autolife-find-robot/scripts/find-autolife.py`（ping 扫邻居表 → `dig @网关 -x` → hostname 含 `autolife-robot-<机号>` 即机器人，自动回写 robots.json）。
> 没抓到或要验证 SSH 可达再用：`python3 ~/.hermes/workspace/robssh.py scan --force`（SSH 逐台识别，慢但能兜底 PTR 缺失的机器）。
> 之后用 `robssh.py <机号> <timeout> <命令>` 直接操作；`robssh.py list` 看全机队。找机器人完整决策树见姊妹技能 `autolife-find-robot`。
> 实测（2026-09-13）：DNS 法一次抓 10 台（402/400/308/305/303/294 PTR 缺失/255/254/277/224/0×2），SSH 法只抓到 2 台。
