---
name: netbird-remote-pc-config
description: Use when deploying config / installing software on a remo...
version: 1
---

# NetBird 远程 PC 配置 / 软件部署

> 完整描述：Use when deploying config / installing software on a remote PC via NetBird. Covers DNS resolution pitfalls, SSH connectivity checks, and safe config-write patterns.

通过 NetBird 客户端连接远端机器做配置或装机。适用于：跨物理网络（内网/家用/客户现场）但同 NetBird 网络的场景。

## 先查再连

远端机器连接失败时按这个顺序排查，**不要**一上来就重装 netbird 或试错：

```bash
# 1. 本机 netbird 状态（必须 Connected）
netbird status

# 2. 对方机器的 FQDN 规则：
#    <hostname>.netbird.selfhosted （本机看到的 FQDN，如 kk-gdh-x.netbird.selfhosted）
# 对方的 FQDN 不一定是 netbird ssh 接受的名字——客户端用 mDNS 解析，可能用裸 hostname
netbird ssh <user>@<hostname>           # 试裸名
netbird ssh <user>@<hostname>.netbird.selfhosted

# 3. 用 netbird 分配的 IP 直连（最稳）
netbird status -d | grep -A1 "NetBird IP"   # 看本机 IP 段
```

## 常见坑

- 主机名拼写：用户给的"faelwj-gdh-x"可能被记忆错为"kk-gdh-x"等类似名。**先用 netbird status 确认本机**，再问用户对方机器的**准确** FQDN 或 IP。
- DNS `server misbehaving` = 系统 DNS 127.0.0.53 不转发 .selfhosted 域，需要对方机器 netbird daemon 在跑 + mDNS 注册。
- 对方机器可能 netbird 根本没登录 / SSH server 没开 → netbird ssh 会报"SSH server detection failed"。
- 网络不通时的备选：让用户先在远端跑 `netbird status` 截图发来。

## 写入配置前

- 涉及 API key / token / 凭证 / 私钥的操作，**确认了目标机器身份（hostname + 用户名）再写**——猜错了会泄露到陌生机器。
- 写配置文件优先用 codex / claude code / opencode 风格的 TOML，不要发明格式。先看 ~/.codex/config.toml 在远端是否存在；如果不存在但该工具装着，复用其既有 schema。
- 改之前先 `cat` 看一遍，遵循 trust-but-verify（SOUL §程序安全边界）。

## 不在本机上代写

如果你判断"目标机器其实就是本机"（用户口误），**先确认**——把 ~/.codex/config.toml 写在本机一旦不对，没法撤回。
