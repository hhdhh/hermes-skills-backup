---
name: autolife-s2-robox-wizard
version: 1.1.0
description: "AutoLife S2（robot_v2_2）一体化装机+联调向导：Y2 路由器自动配置、netplan 网卡绑定、软件包安装、出货配置覆盖、服务部署、NetBird、18 项集成测试、Web 前端。Use when 主人说 S2 装机、robox、wizard、Y2 路由器、192.168.10.2、集成测试、出货验证、远程摇操排查。"
metadata:
  triggers:
    - "S2 装机"
    - "robox"
    - "Y2 路由器"
    - "192.168.10.2"
    - "集成测试"
    - "出货验证"
  requires:
    bins: ["python3"]
  assets:
    wizard: "scripts/robox_combined_y2_wizard.py（单文件 7221 行，sha256 98af83a4…，2026-09-08 版）"
    frontend: "scripts/robox_wizard_frontend.html"
---

# AutoLife S2 Robox 装机联调向导（robox_combined_y2_wizard.py）

> 来源：2026-09-13 丁祥浩发来的部署到机器人里的单文件脚本（与 ~/下载/ 2026-09-08 版 sha256 一致，py_compile 通过）。
> 机型：**S2 / robot_v2_2**。注意与 S1（logo-backend/kiosk/gv-control、65/66 网段）是两套体系，路径/服务名/网段别混用。
> 姊妹技能：`autolife-find-robot`（定位）、`autolife-remote-repair`（SSH 检修）、`autolife-doctor-operations`（诊断）、`autolife-robot-dds-camp-split`（S1 DDS）。

## 这是什么

单文件四合一向导，跑在**机器人 Ubuntu**（用户 `ubuntu`；autolife 初始化 stage 用 `autolife` 用户）：

1. **Y2 路由器自动配置**（行 13-503）：requests 走路由器 HTTP CGI——`/cgi-bin/adm.cgi` LOGIN（admin）→ `/js/*_data.js` 读配置（`addCfg('k',…,'v')` 正则解析）→ `/cgi-bin/internet.cgi` 写 LAN。流程：枚举有线网卡→临时加 IP→发现路由器（新旧 IP 都试）→改 LAN 为 192.168.10.1/24 + DHCP 池 →5G WiFi `Autolife_S2_<机号>`/密码 `<机号>@Autolife`/信道 40/关 2.4G →IP/MAC 绑定机器人→自动迁移到新 IP→前后配置快照对比打印。
2. **Setup 向导**（20 个 stage，`--stage <key>` 单跑）：router / network / screen / autolife / ubuntu / udev / software / config / server / inspection / robot_reset / joint_speed_control / calibration / services / gpu / netbird / five_g / final_check / restore_routes / restore_fstab（后五个 include_in_full=False，全流程不自动跑）。
3. **集成测试 18 项**（`--integration-stage <1-18|标题|integration_ 前缀 key>`）：①二进制版本 ②本地服务连接 ③动作录制回放 ④-⑦TTS（kokoro/piper/wav/edge）⑧本地路由转发 ⑨上级路由器本地转发 ⑩3.5mm 麦克风 ⑪OpenAI 实时对话 ⑫远程服务器摇操 ⑬5G 上网 ⑭自动化动作 ⑮共享内存相机 ⑯GV 建图 ⑰GV 导航 ⑱GPU。报告追加到 `~/Documents/integration_test_report.md`。（组合主菜单显示"19 项" = 1 个"顺序执行全部"入口 + 这 18 项；Web/组合菜单的 `integration_N` key N 对应此顺序。）
4. **Web 前端**（`--web`）：http.server + PTY 任务队列（FrontendJob），浏览器点按钮驱动向导；`ROBOX_WEB_AUTO_CONFIRM=1` 自动确认，sudo 密码走 `ROBOX_WEB_SUDO_PASSWORD`（`sudo -S -v` 预验证）。

主菜单还有三个入口（已实测确认）：`8) 快捷工具箱`（quick_toolbox，含腰腿关节控制等小工具）、`9) 摇操方式快捷修改`（teleop_connection_switcher：改 vision settings.toml / relay config.toml / admin .env 的信令地址，切本地/远程/上级路由转发，改前快照、改后重启对应服务、可恢复）、`d) 下载最新二进制包`（飞书扫码 alist 下载）。

## 关键常量（排障时直接查）

| 项 | 值 |
|---|---|
| 机器人 LAN IP | `192.168.10.2`（lan0 固定；路由器 `.1`；DHCP 池 .100-.200，租期默认 86400s） |
| 路由器管理 | 新 `192.168.10.1`，默认密码 `admin`（`--password` 或 env `ROUTER_PASSWORD`） |
| 5G WiFi | SSID `Autolife_S2_<机号>`，密码 `<机号>@Autolife`，信道 40，2.4G 关 |
| 信令服务器 | 本地 `ws://127.0.0.1:3000/ws`；远程 `ws://112.94.11.147:3000/ws` |
| NetBird | mgmt `https://netbird.autolife-robotics.com`；setup key 硬编码在脚本与 `--netbird-setup-key` 默认值中（内部资料，外发文档须打码） |
| vision 配置 | `/home/ubuntu/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/settings.toml` |
| Web 前端 | 默认 `0.0.0.0:3004`，`--web-host/--web-port/--web-open` 可调 |
| 报告文件 | `~/Documents/integration_test_report.md` |

## 常用命令（在机器人上）

```bash
python3 robox_combined_y2_wizard.py                                # 交互主菜单
python3 robox_combined_y2_wizard.py --stage router                 # 单跑 setup stage
python3 robox_combined_y2_wizard.py --stage netbird
python3 robox_combined_y2_wizard.py --integration-stage 1          # 按编号单跑集成测试
python3 robox_combined_y2_wizard.py --integration-stage "GV 导航"  # 按标题
python3 robox_combined_y2_wizard.py --direct setup                 # 直接进 setup 向导
python3 robox_combined_y2_wizard.py --direct integration           # 直接进集成测试向导
python3 robox_combined_y2_wizard.py --web                          # Web 前端 :3004
ROBOX_WEB_AUTO_CONFIRM=1 ROBOX_WEB_SUDO_PASSWORD=xxx python3 robox_combined_y2_wizard.py --web
```

## 灰灰远程接入玩法

机器人已部署该脚本时：

- **非交互单跑会被 confirm() 卡住/跳过**（见坑 1），远程驱动优先走 Web 模式：SSH 里 nohup 拉起 `--web`，再 `curl http://<robot_ip>:3004/` 或浏览器点单 stage（POST /api/jobs）。
- 路由器配置也可在机器人上直接跑：`ROUTER_PASSWORD=<pwd> python3 robox_combined_y2_wizard.py --stage router`。
- 集成测试改 relay `config.yaml` / admin `.env.production` 前**自动备份、finally 恢复**——中途杀进程会留 `.bak` 尾巴，下次跑会提示。

## 坑（从代码读出来的，踩前先看）

1. **confirm() 交互**：`y`=执行、回车/n/s=跳过、q=退出。SSH 非交互（无 TTY）时 `input()` EOFError 直接崩；远程必须 Web 模式 + `ROBOX_WEB_AUTO_CONFIRM=1`。
2. **network stage 会断 SSH**：netplan 改 lan0/lan1 时可能临时断连，远程操作先 tmux/nohup 保护。
3. **本机预览必须 --test-mode**：灰灰工作站是真 Linux，不加 `--test-mode` 会真的动本机网络/写系统文件。本机只做菜单/语法检查：`--test-mode --test-user ubuntu --allow-non-linux`。
4. **路由器改 IP 后 15-30s 不可达是正常的**：脚本自动 `wait_for` 新地址重连，别误判失败。写配置 ReadTimeout 被 `tolerate_timeout` 当成功（固件不回响应的 quirk）。
5. **IP/MAC 绑定要查两个 js**（ipband_data.js + status_data.js）才能确认；首次出厂固件可能要先在网页向导设管理员密码（login 检测 login_data.js 的 login_s=1）。
6. **S1 vs S2 别混**：服务名（S2 是 vision/arm/gv/rust-web-server/relay/admin）、网段（S2 是 10.x）、conda env 路径都不同。
7. **Web 前端监听 0.0.0.0**：现场任何连上机器人网络的人都能操控（含 env 注入 sudo）——测试完关掉，注意物理网络安全。
8. **`clean_subprocess_env()` 剥离 LD_LIBRARY_PATH**：自定义库路径要在 shell 脚本内 source，别依赖外部 env。
9. **joint_speed_control / robot_reset / 自动化动作会真动关节**：全流程不含它们，必须显式 `--stage`；跑前确认机器人已打胶/复位（脚本内有警告文案）。
10. **download_packages 依赖现场 Chrome + 飞书扫码**（alist CDP 自动化抓 token 下载 OpenList 包）：纯远程无显示器跑不了，需现场配合。
11. **`--stage` 传错 key 退出码 2**：合法 key = STAGES 20 个（见上）。
12. **版本检查走飞书 API/多维表**：`feishu_tenant_access_token` + 版本清单接口，拿 tenant token 失败会降级提示（VersionApiUnavailable 重试 3 次）。

## 复用价值（为什么收进技能库）

- **Y2 路由器 CGI 自动化**是通用品：`addCfg` 正则解析 + `already_configured` 幂等检测（已配置跳过）+ 改前 snapshot/改后 verify 对比，换网段/SSID 即可复用做批量配置。
- **backup→改→finally 恢复**框架：改配置类测试的标准安全骨架。
- **PTY + http.server Web 驱动层**：把任意 CLI 向导变 Web 操控台（FrontendJob），可移植。
- **alist/OpenList CDP 自动下载**（Chrome 调试端口 + 飞书 OAuth 回调抓 token）：远程拿包的通用套路。
- **飞书版本清单拉取**：tenant_access_token + 多维表行的封装模板。
