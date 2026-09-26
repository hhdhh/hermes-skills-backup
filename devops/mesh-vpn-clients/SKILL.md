---
name: mesh-vpn-clients
description: Use when 装或登录 Tailscale/NetBird、切自托管 management、100.
---

# Mesh VPN clients（Tailscale / NetBird）— headless Linux

> 完整描述：Install/authenticate mesh VPN clients (Tailscale, NetBird) on headless Linux, incl. agent-completed SSO for localhost-callback flows. Use when 装或登录 Tailscale/NetBird、切自托管 management、100.64.0.0/10 CGNAT 地址不通.

## 何时用

- 安装 / 登录 Tailscale 或 NetBird；NetBird 切自托管 management URL
- 目标 IP 在 100.64.0.0/10（CGNAT 段）且 ping/nc 全超时
- SSO 回调落在 `http://localhost:<port>/` 的登录流程需要代办

## 第 0 步：先查 mesh 客户端，再做深度诊断

对 100.x.x.x 不通：`ip link | grep -E 'tailscale|wt|wg'` + `systemctl is-active tailscaled netbird`。没有虚拟网卡 = 客户端没跑，包从默认路由出去必死——先装/起客户端，不要先做端口扫描。

## Tailscale 流程

1. apt 源：`https://pkgs.tailscale.com/stable/ubuntu/<codename>.noarmor.gpg` dearmor 后进 `/usr/share/keyrings/`；`deb [signed-by=...] https://pkgs.tailscale.com/stable/ubuntu <codename> main`；`apt-get install -y tailscale`
2. `systemctl enable --now tailscaled`
3. 登录 URL 用 Popen + 正则从 stdout 抓 `https://login.tailscale.com/a/\S+`（`tailscale up`/`login` 阻塞等浏览器，绝不裸跑前台）
4. URL 由账号所有者在浏览器授权。卸载要彻底：purge 包 + 删 `/var/lib/tailscale`、`/var/cache/tailscale`、apt 源文件、keyring，最后逐项验证

## NetBird 流程

1. `netbird up --management-url https://<host>:443`（自托管必带；URL 持久化到 `/var/lib/netbird/default.json`）
2. 输出的 SSO URL 的 redirect_uri 是 `http://localhost:53000/` —— 回调在环回地址，**同机 agent 浏览器可全程代办**（仅当用户明确授权「自己登录/我授权」）：打开 URL → 点 `.provider-link`（IdP 按钮，如飞书）→ 账号识别后点 innerText 为「授权」的按钮 → 页面落到 localhost:53000 显示 Login Successful
3. `up` 进程在回调落地前必须活着；中途 kill 或重启 up 会使 state/code_challenge 作废重来
4. 回调成功 ≠ 已连通：重新 `netbird status`；仍 NeedsLogin 就看日志

## 日志解码（/var/log/netbird/client.log）

- `user pending approval cannot add peers` → 服务端等管理员审批，或改用 setup key（`netbird up --management-url ... --setup-key <key>`）——客户端无解，别瞎修
- `no peer auth method provided` → 未登录且无 setup key
- `peer login has expired, please log in once more` → 旧登录态过期，重走 SSO

## Pitfalls

- P1 `netbird up` / `tailscale up` 前台调用阻塞到超时并杀掉登录流程——用 terminal(background=true) 或 Popen 抓 URL，保持进程存活
- P2 SSO「Login Successful」后不查 status/日志就宣布连通是错的——审批类错误只在 daemon 日志里可见
- P3 Casdoor 等 React 登录页：直接 `.value=` 赋值不触发框架状态——用 `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set` + `new Event('input',{bubbles:true})`；按钮按 innerText 找（「授权」「登 录」中间可能有空格）
- P4 安装/卸载都要 root；无 NOPASSWD 时每条 sudo 用 `sudo -S` 从 env 读密码拆解执行（密码经 `~/.hermes/.env` 的 SUDO_PASSWORD 提供，回复中永不回显）
