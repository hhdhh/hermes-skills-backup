# 连接方式切换三文件法

<!-- capability_id: autolife-ops.connection-switch | revision: 1 | status: active -->
<!-- 来源: Autolife 机器人现场常见问题处理指南 §一（飞书语料） -->

## R — 原文

> relay config.yaml广播IP改wlo1 IP；管理后台.env.production的PUBLIC_API_BASE_URL改wlo1 IP（端口3000不变）；vission settings.toml的signaling_server_url改目标环境IP（协议ws://端口3000路径/ws不变）。
> —— 《Autolife 机器人现场常见问题处理指南 §一》

## I — 自述

机器人从一种连接方式切到另一种（如云控→现场局域网直连）时，要同步改三个文件里的 IP：①relay 的 conf/config.yaml（广播地址）②管理后台 Admin 的 .env.production（PUBLIC_API_BASE_URL）③vision 的 settings.toml（signaling_server_url）。

铁律是"只换 IP，不动其他"：协议（ws://）、端口（3000）、路径（/ws）保持原样，只替换 IP 字段。改前备份，改后重启对应服务（relay/admin/vision），并验证设备在管理端的状态。

IP 以现场实际分配为准（ifconfig wlo1 查），不沿用文档示例值——示例里的"广州 IP"等占位值直接抄必错。

## A1 — 书中案例

**案例类型：书中亲历案例**（现场切换直连，来源：常见问题处理指南）

- 输入/问题：客户现场网络隔离，需要机器人从云信令切到现场局域网直连
- 方法执行：ifconfig wlo1 拿现场 IP → 三文件逐个只改 IP 字段（relay config.yaml / Admin .env.production / vision settings.toml）→ 分别 restart relay/admin/vision
- 结论：管理端设备 online，直连链路通

## A2 — 未来触发 ★

**情境：**

1. 机器人要切换连接环境（云端↔现场直连↔展会临时网络）
2. 管理端显示设备 offline 但 relay 服务正常
3. 换了路由器/网络环境后信令不通
4. 客户要求机器人脱离云端本地化管理

**语言信号：**

- "切换连接方式" / "改成直连" / "切到现场网络"
- "管理端 offline" / "设备不上线"
- "signaling_server_url" / "PUBLIC_API_BASE_URL" / "relay config"
- EN: "switch connection mode" / "device offline after network change"

**区分：**

- ≠ autolife-dds-split：那修的是机器人内部话题互见性；本卡修的是机器人↔管理端的信令连接
- ≠ autolife-ops-hwid-repair：那修身份指纹（REGISTER 后无握手）；本卡修地址指向（连错服务器）
- ≠ autolife-network 系列：那些是网络层诊断；本卡是应用层配置切换

## E — 可执行步骤

**输入契约**：机号（必填）；目标连接环境（必填：云/现场直连 IP）；SSH 可达（必填）。目标 IP 未知时先现场确认，不猜。

**Step 1 取现场 IP**：`ifconfig wlo1`（或对应网卡）——以实测为准，不用文档示例
**Step 2 三文件修改（只换 IP）**：
1. relay：`conf/config.yaml` 广播 IP 字段
2. 管理后台：`Admin/.env.production` 的 PUBLIC_API_BASE_URL=http://<新IP>:3000（端口不变）
3. vision：`settings.toml` 的 signaling_server_url=ws://<新IP>:3000/ws（协议/端口/路径不动）
**Step 3 重启对应服务**：relay → admin → vision 各自 restart
**Step 4 验证**：管理端设备状态 online + 从机器人 ping/curl 目标服务器可达
**判停点**：三文件都改了仍 offline → 查防火墙/端口开放（3000）；改错想回退 → 用 Step 2 前的备份直接还原，不手改回去

**输出契约**：三文件修改 diff（只含 IP 行）+ 重启记录 + 管理端状态截图/输出。

## B — 边界

- **不适用**：机器人内部服务故障（各诊断卡）；NetBird mesh 问题；sim 卡/4G 模块硬件问题
- **反场景**：连协议/端口/路径一起"顺手规范化"（改了必断）；用示例文档里的 IP 直接抄
- **失败模式**：只改两处漏一处（三件套必须齐）；改完不 restart 对应服务；不备份直接改
- **相邻易混**：224 信令中枢自身故障（整个管理端都打不开）不是本卡范围
