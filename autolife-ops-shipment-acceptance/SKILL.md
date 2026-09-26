---
name: autolife-ops-shipment-acceptance
description: |
  Use when 出货验收/集成测试 R0-R4/FAT/SAT/证据包整理/G5 放行判定/测试态恢复交付态——按 G0-G6 门禁链逐门判定， 五状态口径（PASS/WARN/FAIL/INCOMPLETE），退出码 0 不等于放行。不适用：日常巡检、排障诊断。
metadata:
  cangjie.generated-by: cangjie-tools v2.5.0
  cangjie.capability-id: cap.autolife-ops.shipment-acceptance
  cangjie.capability-revision: 1
  cangjie.bundle-id: bundle.autolife-feishu-corpus
  cangjie.source-title: AutoLife 飞书运维语料全集
  cangjie.tags: acceptance, shipment, quality-gate
---
# 出货验收门禁（G0-G6 + FAT/SAT + 证据包）

<!-- capability_id: autolife-ops.shipment-acceptance | revision: 1 | status: active -->
<!-- 来源: 05 出货验收 + 04 集成测试 + 23 装机部署规范（飞书语料） -->

## R — 原文

> FAT通过不等于允许出货，允许出货不等于现场交付完成；模板不等于证据，进程在线不等于业务可用，口头确认不等于验收通过。
> —— 《05｜出货验收》

> G5放行条件：自动无FAIL+人工无INCOMPLETE+所有WARN有解释批准+临时配置恢复+偏差有负责人复验+证据脱敏+双签字。
> —— 同上

## I — 自述

出货不是"测完打包"，是一条从基线冻结到现场交付的门禁链：G0（开工前基线确认）→ G1（装配质量签名）→ G2（系统初始化验证）→ R0-R4（集成测试五道前置门）→ G4（FAT 业务闭环）→ G5（出货放行）→ G6（SAT 现场验收）。每道门有明确的通过条件和失败动作（退回对应阶段、开返工单），禁止带病过门。

三类验收不得互相替代：FAT 在受控环境证明硬件/服务/业务链；出货验收把测试态恢复到交付态并脱敏证据；SAT 在客户真实网络/物料/人员条件下验证。工厂的模拟物料不能证明现场可用。

判定口径固定五状态：PASS（达自动判据）/ WARN（可选项缺失，必须有书面解释）/ FAIL（不得放行）/ INCOMPLETE（人工项未完成，不是通过）。命令退出码 0 只表示没有自动 FAIL。G5 放行 = 自动无 FAIL + 人工无 INCOMPLETE + WARN 全有解释 + 临时配置已恢复 + 证据脱敏 + 双签字。

测试态→交付态的恢复是高危步骤：不能拿 .example 模板覆盖（会清掉机器人编号/网卡/License/标定），要恢复测试前快照或字段级合并。证据包记录 RUN_ID+身份+版本+配置哈希+首断点+修复 diff，且永不包含密码/令牌/密钥。

## A1 — 书中案例

**案例类型：书中亲历案例**（出货流程标准执行，来源：05 出货验收）

- 输入/问题：一台 S2 完成 FAT 后准备发货，判断能否放行
- 方法执行：G5 清单逐项核对——自动测试无 FAIL✅；发现 Data Logger 仍启用（临时配置未恢复）→ 拦下；恢复交付态配置后复验；证据包检查发现截图含 setup key → 脱敏重做；双签字完成
- 结论：G5 通过允许出货；SAT 在客户场地独立执行，不回填 FAT 结论

**案例类型：反例警示**（来源：装机规范反模式）

- 用 .example 模板直接覆盖生产配置 → 机器人身份/硬件映射/授权全丢 → 退回 G2 重做初始化

## A2 — 未来触发 ★

**情境：**

1. 出货季/验收季批量判断"这台能不能发"
2. FAT 跑完自动测试退出码 0，问是否等于可以出货
3. 现场交付（SAT）进场前的准备与进场后的实测
4. 修复后/测试后把机器人恢复到交付态
5. 整理验收证据包给客户或内部审计

**语言信号：**

- "出货" / "能不能发" / "放行" / "验收" / "FAT" / "SAT"
- "退出码0是不是就过了" / "INCOMPLETE 算过吗"
- "恢复出厂/交付态" / "测试配置要清掉"
- "证据包" / "脱敏"
- EN: "shipment approval" / "factory acceptance test" / "release gate"

**区分：**

- ≠ autolife-robot-diagnosis：那是排障找断点；本卡是**验收放行判定**，机器人没坏也要过门
- ≠ autolife-shutdown-conditions：那判"修不修"；本卡判"发不发"——排障中发现触发停止线的，修复后仍须回本卡重走对应门
- ≠ autolife-doctor-operations：日常保养巡检；本卡是一次性交付门禁

## E — 可执行步骤

**输入契约**：机型+机号（必填）；所处阶段（必填：FAT/出货/SAT）；已完成的上一道门（必填）。缺阶段信息先问，不默认从 G0 走。

**Step 1 定位当前门**：按链核对 G0→G1→G2→R0-R4→G4→G5→G6，确认上一道门已过
**Step 2 按门执行判定**：
- G0：机型/版本/磁盘/网卡/路径/备份/急停/测试区确认——失败只允许只读检查
- G1：机械/电气/零位/急停/充电/散热/接口逐项签名，返工项重测
- G2：配置语法/身份/MAC 映射/Netplan try/路由/DNS/设备节点——失败回滚本次配置
- R0-R4：安全身份门→进程门→ROS与数据门→模块功能门→业务门（详见 04 集成测试）
- G4：FAT 业务闭环实测（摇操/录制回放/TTS/AI/建图导航/场景任务）
- G5：放行清单（见 Step 3）
- G6：SAT 进场双确认（进场前：项目场景/路线/手续；进场后实测：电压/功率/插座/独立回路/地面/通道/网络——不沿用展前假设）
**Step 3 G5 放行五查**：①自动无 FAIL ②人工无 INCOMPLETE ③WARN 全有书面解释批准 ④临时配置已恢复（Data Logger/Rosbag/调试 API key/DMZ/测试账号全清）+ 证据脱敏（无密码/令牌/setup key）⑤双签字
**Step 4 状态标注**：每个用例标 PASS/WARN/FAIL/INCOMPLETE；退出码 0 仍须人工复核 WARN/INCOMPLETE
**判停点**：任一门 FAIL → 退回对应阶段开返工单，不带病过门；证据含秘密 → 整包脱敏重做，不局部涂改

**输出契约**：门禁判定表（门｜判定｜证据｜签名）+ 证据包（RUN_ID+机器身份+版本+配置哈希+前后 NRestarts+首断点+修复 diff）+ 放行结论（放行/退回+退回门）。

## B — 边界

- **不适用**：日常巡检保养（doctor-operations）；排障诊断（autolife-ops-robot-diagnosis）；SLAM 专项（autolife-ops-slam-troubleshooting）
- **反场景**：机器人没有故障≠可以出货（门禁是独立要求）；SAT 环境不满足应暂停交付而不是回填"已完成"
- **失败模式**：拿退出码 0 当放行；模板当证据；截图当签名；恢复态用模板覆盖丢身份；偶发故障靠重启掩盖出关
- **相邻易混**：INCOMPLETE 不是 FAIL（前者补齐即过，后者必须修复）；WARN 不是可选项缺失的借口（每个 WARN 都要解释）
