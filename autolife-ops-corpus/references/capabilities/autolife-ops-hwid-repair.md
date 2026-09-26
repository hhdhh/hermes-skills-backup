# relay hwid 身份修复

<!-- capability_id: autolife-ops.hwid-repair | revision: 1 | status: active -->
<!-- 来源: hwid 缺失导致 signaling handshake 失败（224）（飞书语料） -->

## R — 原文

> conf/hwid 是0字节空文件→relay注册时手里是"白条"→握手校验失败反复重连。绝对禁止把其他机器的fingerprint拷过来——会触发双机同id反作弊同时封两台。
> —— 《hwid 缺失导致 signaling handshake 失败（224）》

## I — 自述

relay 注册 signaling 服务器时用 conf/hwid 里的硬件指纹做身份凭证。这个文件是 0 字节空文件时，relay 拿着"白条"去握手——服务 active、日志里 Sent REGISTER 后无 Handshake complete，反复重连。判定链很简单：查文件大小，0 字节=缺指纹；license.key 配对正常则问题不在 license。

修复是用本机 wheel/hwid 工具生成**本机**指纹写入 conf/hwid，重启 relay，验证 Handshake complete。

最重要的红线：hwid 是机器身份，**绝对禁止**从别的机器拷贝——复制会触发"双机同 id"反作弊机制，两台机器同时封禁。同类的身份文件（license.key/id_ed25519.pub）同理，都是一机一证。

## A1 — 书中案例

**案例类型：书中亲历案例**（224 hwid 修复）

- 输入/问题：224 relay 服务 active 但管理端始终 offline，日志反复 REGISTER→无握手
- 方法执行：查 conf/hwid 文件大小=0 字节 → license.key 校验正常（排除 license）→ 判定缺指纹 → 备份空文件 → wheel/hwid fingerprint 生成 → 写入 → restart relay
- 结论：日志出现 Handshake complete，管理端上线

## A2 — 未来触发 ★

**情境：**

1. relay/信令服务 active 但管理端一直 offline
2. 新机器/重装后 relay 反复重连握手失败
3. 机器人换主板/重装系统后信令异常
4. 任何需要动 hwid/license/身份文件的场景（红线提醒）

**语言信号：**

- "relay 连不上" / "handshake 失败" / "管理端 offline"
- "hwid" / "fingerprint" / "指纹"
- "注册不上" / "反复重连"
- EN: "relay handshake failure" / "hwid missing"

**区分：**

- ≠ autolife-robot-diagnosis：那是通用找断点；本卡是信令断点定位后的**专项修复**
- ≠ autolife-netbird-repair：那修网络层 mesh；本卡修应用层身份
- ≠ 出货装机流程：新机身份初始化走 s2-robox-wizard，本卡是修复场景

## E — 可执行步骤

**输入契约**：机号（必填）；relay 日志或"管理端 offline"现象（必填）；确认有本机 wheel/hwid 工具（必填——没有时向负责人索取，不跨机借）。

**Step 1 现象确认**：`journalctl --user -u relay --since "1h ago" | grep -E "REGISTER|Handshake"`——有 REGISTER 无 Handshake complete = 握手失败
**Step 2 判定**：`ls -la <relay目录>/conf/hwid`——0 字节=缺指纹；同时 `license.key` 正常存在则排除 license 问题
**Step 3 修复**：
```
cp conf/hwid conf/hwid.bak.$(date +%Y%m%d)   # 备份
wheel/hwid fingerprint > conf/hwid            # 本机生成本机指纹
systemctl --user restart relay
```
**Step 4 验证**：日志出现 "Handshake complete" + 管理端设备状态 online
**判停点**：Step 2 hwid 非空但仍握手失败 → 不是缺指纹，查网络可达 signaling 服务器 / license 配对；**任何情况下不跨机拷贝 hwid/license.key/id_ed25519.pub**（双机同 id=两台同时封）

**输出契约**：判定结果（缺指纹/其他）+ 修复动作（生成命令+写入时间）+ 验证证据（Handshake complete 日志行+管理端状态）。

## B — 边界

- **不适用**：网络层不通（NetBird/路由）；license 过期/无效（换 license 流程）；机器人本体服务故障
- **反场景**：从"正常机器"拷 hwid 过来"先跑起来"（封号级红线，绝对禁止）
- **失败模式**：只 restart 不看日志验证 Handshake；生成工具路径错写了空输出（Step 4 必须看到完整握手链）
- **相邻易混**：relay 的 config.yaml IP 配置错（连接切换三文件法，f21 能力卡）症状类似但修法完全不同
