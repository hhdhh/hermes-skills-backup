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

## 已知坑（真机踩过）

- **"0 号机"有两台**（hostname 同为 autolife-robot-0，2026-09-13 见于 64.128 / 65.240）——按 IP 操作前先 `robssh.py <机号> 'hostname && ip addr'` 确认身份。
- **DNS PTR 表会骗人**：现场动机器/断电后 PTR 残留，DNS 显示"在线"但 SSH 连不上。判在线以 SSH 实连为准。
- **sudo 输出污染**：`sudo -S` 偶尔把提示混进 stdout，判断结果别只看输出里有没有关键词，看 `[exit N]` 之外的实质内容/校验值。
- **NetBird 注册名可能错位**：`autolife-robot-303.netbird.selfhosted` 连进去真实 hostname 是 294（2026-09-13 实测）。mesh 名只是注册时的快照，机器换系统/改名不更新。**连上先 `hostname` 验明正身再操作。**
- **DHCP 换 IP**：连不上先重扫（DNS 法几秒，SSH 法几分钟），别急着判机器死机。
- paramiko 线程噪音：脚本已静音；自己写临时代码时记得 `logging.getLogger("paramiko").setLevel(logging.CRITICAL)`。

## 与其它技能的衔接

| 需求 | 去处 |
|------|------|
| 找不到机器 / 解析 IP | `autolife-find-robot`（DNS PTR 首选） |
| 系统性诊断（22 项扫描/OTA/电池） | `autolife-doctor-operations` |
| DDS 阵营分裂（电池恒 100%/数据僵死） | `autolife-robot-dds-camp-split` |
| prompt / RAG / 知识文件修改 | `autolife-robot-prompt-ops` |
