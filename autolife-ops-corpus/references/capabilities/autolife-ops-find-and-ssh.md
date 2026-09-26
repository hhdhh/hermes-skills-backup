# 机器人定位与远程检修工具链

<!-- capability_id: autolife-ops.find-and-ssh | revision: 1 | status: active -->
<!-- 来源: 案例002 · 机器人定位与远程检修工具链（飞书语料） -->

## R — 原文

> A·DNS PTR（首选）ping扫邻居表+dig反查hostname秒级免凭证；B·mDNS autolife-robot-XXX.local；C·SSH扫描robssh.py scan兜底；D·NetBird mesh 100.98.x.x跨网段。
> —— 《案例002 · 机器人定位与远程检修工具链》

## I — 自述

机器人按 hostname（autolife-robot-机号）识别身份，IP 是 DHCP 动态分配的——任何写死 IP 的做法都会在机器人换网后失效。给机号找人（机）用四路定位：A DNS PTR 反查（现场内网首选，ping 扫邻居表后 dig -x 反查 hostname，秒级免凭证）B mDNS（autolife-robot-XXX.local，配过 avahi 的机器）C robssh.py scan 逐台 SSH 识别（PTR 缺失时兜底，分钟级）D NetBird mesh 100.98.x.x（跨网段/远程场景，FAE 不在客户现场也能直连）。

找到只是开始：SSH 全机队 ${ROBOT_CREDS}；192.168.10.2 是全机队网线直连专用固定 IP（lan0），接哪台是哪台——用它操作前必须 hostname 验身。NetBird 的意义是打破地理限制：165 台设备在网，人在任何位置都能直接检修客户现场机器人。

## A1 — 书中案例

**案例类型：书中亲历案例**（案例002 四路定位实测）

- 输入/问题：现场 10 台机器人，只知道机号不知道 IP
- 方法执行：A 路优先——ping 扫同网段后 dig -x 反查，40 秒锁定全部 10 台 hostname↔IP 映射
- 结论：DNS PTR 免凭证秒级，实测后定为首选；PTR 记录缺失的 2 台用 C 路 robssh.py scan 兜底识别

## A2 — 未来触发 ★

**情境：**

1. 拿到机号（"帮我看看 321"）需要找到对应机器人 SSH 上去
2. 机器人在客户现场，人不在现场，需要远程检修
3. 现场多台机器人需要批量识别/盘点
4. 机器人换网/重装后旧 IP 失效

**语言信号：**

- "321 在哪" / "找到那台机器人" / "怎么连上 XX 机"
- "ssh 上去看看" / "远程修一下"
- "IP 是多少" / "连不上那台"
- EN: "find robot by id" / "remote ssh to robot"

**区分：**

- ≠ autolife-find-robot（旧技能）：本卡源自同一案例库的完整版，四路+验身规则融合一张卡
- ≠ autolife-remote-repair：那支是修什么（诊断流程）；本卡是怎么找到并连上（前置步骤）
- ≠ autolife-robot-diagnosis：连上之后的排障走那支

## E — 可执行步骤

**输入契约**：机号（必填，如 321）；机器人所在网络环境（必填：现场内网/NetBird mesh/未知）。环境未知时先试 mesh 再试内网。

**Step 1 四路定位（按序尝试）**：
A·DNS PTR（现场内网首选）：
```
# ping 扫邻居表后反查
ping -b -c1 <网关>.255 或 arp-scan --localnet
dig -x <IP> +short   # 返回 autolife-robot-321.... 即锁定
```
B·mDNS：`ping autolife-robot-321.local`（配过 avahi 的机器）
C·SSH 扫描兜底：`robssh.py scan`（22 端口逐台识别 hostname，分钟级）
D·NetBird mesh：`ssh ubuntu@100.98.x.x`（100.98 网段，跨网段/远程）
**Step 2 连接**：`ssh ubuntu@<IP>`（全机队 ${ROBOT_CREDS}，个别机型除外见技能库快照）
**Step 3 验身（192.168.10.2 必做）**：`hostname` 确认是目标机号——10.2 是网线直连共享 IP，接哪台是哪台，不验身=可能修错机
**Step 4 进入检修**：转 autolife-ops-robot-diagnosis（排障）或对应专项卡
**判停点**：A 路无 PTR 记录 → 直接换 C 路，不在 A 上反复试；mesh 里也找不到 → 确认机器人是否开机/入网，找不到不猜 IP

**输出契约**：机号↔IP 映射表 + hostname 验身结果 + 连接方式（四路中哪路命中）。

## B — 边界

- **不适用**：机器人已找到后的诊断修复（各专项卡）；NetBird 网络本身的故障修复（autolife-netbird-repair）
- **反场景**：把 IP 写死在文档/脚本里（换网必失效）；用 10.2 不验身就开工
- **失败模式**：只记 IP 不记 hostname（下次失联）；跳过 mesh 试内网（人不在现场时白忙）
- **相邻易混**：224 信令中枢（10.2:3000）是管理端，不是机器人本体
