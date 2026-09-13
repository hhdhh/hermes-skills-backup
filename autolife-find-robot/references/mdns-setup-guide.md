# 在 `lan0` 和 `wlo1` 上配置与取消 mDNS

此教程用于在 Ubuntu 设备上配置 mDNS。配置 mDNS 的设备可以在内网通过域名访问，不需要查找 IP。

前置条件为：

- 使用 systemd 管理服务。
- 已经安装用于发布 mDNS 的 avahi-daemon；

配置结果为：

- 在 lan0 和 wlo1 两个网络接口上配置 mDNS。
  - 两个脚本都在文件头部通过 `readonly INTERFACES=(lan0 wlo1)` 定义接口。
  - 如果接口名不同，请修改两个脚本的 `INTERFACES` 数组，并同步替换手工配置示例中的接口名。
- 使用系统 hostname 作为 mDNS 主机名。
  - 目标名称始终是 `<hostname>.local`。例如，设备 hostname 为 `autolife-robot-304` 时，mDNS 名称是 `autolife-robot-304.local`。
  - 脚本不会修改系统 hostname。hostname 日后发生变化时，重启 Avahi 后会使用新的 `<hostname>.local` 名称。

## 一、直接使用脚本

将下面两个脚本放在 Ubuntu 的同一目录：

- `configure-mdns.sh`
- `unconfigure-mdns.sh`

脚本不依赖可执行位，直接交给 Bash 即可。

两个脚本的接口列表必须保持一致：

```bash
readonly INTERFACES=(lan0 wlo1)
```

### 配置

```bash
bash configure-mdns.sh
```

配置脚本会执行以下操作：

1. 检查 `avahi-daemon`、`lan0`、`wlo1` 和 multicast 能力。
2. 首次运行时，把原始 Avahi 配置和服务状态保存到 `/var/lib/hostname-mdns/`。
3. 保留 Avahi 配置中的其他内容，只更新本次需要的字段。
4. 删除生效中的 `host-name=` 覆盖，让 Avahi 直接使用系统 hostname。
5. 将 Avahi 接口限制为 `lan0,wlo1`，然后启用并重启服务。
6. 如果 UFW 正在运行，为两个接口添加带 `hostname-mdns-*` 注释的 UDP 5353 入站和出站规则。
7. 检查 Avahi 实际注册的名称；失败或名称冲突时恢复本次运行前的状态。

脚本可以重复运行。如果脚本运行后有人手工修改了 `/etc/avahi/avahi-daemon.conf`，再次配置会停止并提示先检查差异，防止覆盖人工修改。

### 验证

在 Ubuntu 上检查服务和实际名称：

```bash
systemctl status avahi-daemon --no-pager
busctl --system call \
  org.freedesktop.Avahi \
  / \
  org.freedesktop.Avahi.Server \
  GetHostNameFqdn
```

第二条命令应返回当前设备的 `<hostname>.local`。例如，hostname 为 `autolife-robot-304` 时会返回：

```text
s "autolife-robot-304.local"
```

从 `lan0` 或 `wlo1` 所在链路的另一台支持 mDNS 的设备测试。下面以 hostname `autolife-robot-304` 为例：

```bash
ping autolife-robot-304.local
```

`lan0` 和 `wlo1` 属于不同链路时，请分别从两个链路测试。mDNS 默认不会跨路由器或 VLAN 转发。

`resolvectl mdns lan0` 显示 `no` 并不表示本方案失效：这里由 Avahi 提供 mDNS，应以 Avahi 状态和其他设备的解析结果为准。

### 取消配置

```bash
bash unconfigure-mdns.sh
```

取消脚本会：

1. 恢复首次配置前的 `/etc/avahi/avahi-daemon.conf`。
2. 恢复 Avahi 原来的启用和运行状态。
3. 删除配置脚本添加且带 `hostname-mdns-*` 注释的 UFW 规则。
4. 删除 `/var/lib/hostname-mdns/` 中的脚本状态和备份。

如果配置完成后有人手工修改过 Avahi 配置，取消脚本默认会拒绝覆盖。确认需要丢弃这些后续修改时再执行：

```bash
bash unconfigure-mdns.sh --force
```

## 二、不使用脚本，手工配置

### 1. 检查现状

```bash
hostname --short
ip link show lan0
ip link show wlo1
systemctl is-enabled avahi-daemon
systemctl is-active avahi-daemon
```

### 2. 备份配置

备份配置，注意不要覆盖已备份文件。
```bash
sudo cp -a \
  /etc/avahi/avahi-daemon.conf \
  /etc/avahi/avahi-daemon.conf.before-hostname-mdns
```

确认备份存在：

```bash
sudo ls -l /etc/avahi/avahi-daemon.conf.before-hostname-mdns
```

### 3. 编辑 Avahi 配置

```bash
sudoedit /etc/avahi/avahi-daemon.conf
```

在已有的 `[server]` 和 `[publish]` 段中合并下列设置。不要重复创建同名段。

```ini
[server]
domain-name=local
use-ipv4=yes
use-ipv6=yes
allow-interfaces=lan0,wlo1
use-iff-running=yes
enable-dbus=yes

[publish]
disable-publishing=no
publish-addresses=yes
```

同时确认：

- `[server]` 中没有生效的 `host-name=`，这样 Avahi 才会直接使用系统 hostname。
- `[server]` 中没有生效的 `deny-interfaces=`，避免它排除 `lan0` 或 `wlo1`。

### 4. 启用并重启 Avahi

```bash
sudo systemctl enable avahi-daemon
sudo systemctl restart avahi-daemon
sudo systemctl status avahi-daemon --no-pager
```

如果重启失败，先恢复备份：

```bash
sudo cp -a \
  /etc/avahi/avahi-daemon.conf.before-hostname-mdns \
  /etc/avahi/avahi-daemon.conf
sudo systemctl restart avahi-daemon
sudo journalctl -u avahi-daemon -n 50 --no-pager
```

### 5. 处理 UFW

先检查 UFW 是否启用：

```bash
sudo ufw status verbose
sudo ufw show added
```

如果状态是 `inactive`，不用添加规则。如果状态是 `active`，先核对已有规则。只添加缺少的规则，并记录本次实际新增项；已有等价规则应跳过，不修改其注释。操作期间避免其他终端并行修改 UFW。

添加 IPv4 组播入站规则：

```bash
sudo ufw allow in on lan0 to 224.0.0.251 port 5353 proto udp comment 'hostname-mdns-manual-lan0-ipv4-in'
sudo ufw allow in on wlo1 to 224.0.0.251 port 5353 proto udp comment 'hostname-mdns-manual-wlo1-ipv4-in'
```

若 `/etc/default/ufw` 中为 `IPV6=yes`，再添加 IPv6 组播入站规则：

```bash
sudo ufw allow in on lan0 to ff02::fb port 5353 proto udp comment 'hostname-mdns-manual-lan0-ipv6-in'
sudo ufw allow in on wlo1 to ff02::fb port 5353 proto udp comment 'hostname-mdns-manual-wlo1-ipv6-in'
```

`ufw status verbose` 显示默认出站为 `allow` 时，不需要另加出站允许规则。默认出站为 `deny` 或 `reject` 时，补充以下 IPv4 规则；IPv6 两条仅在 `IPV6=yes` 时执行：

```bash
sudo ufw allow out on lan0 to 224.0.0.251 port 5353 proto udp comment 'hostname-mdns-manual-lan0-ipv4-out'
sudo ufw allow out on wlo1 to 224.0.0.251 port 5353 proto udp comment 'hostname-mdns-manual-wlo1-ipv4-out'
sudo ufw allow out on lan0 to ff02::fb port 5353 proto udp comment 'hostname-mdns-manual-lan0-ipv6-out'
sudo ufw allow out on wlo1 to ff02::fb port 5353 proto udp comment 'hostname-mdns-manual-wlo1-ipv6-out'
```

客户端确需额外单播规则时，应按实际可信网段配置，不直接放行任意地址的 UDP 5353。入站限制可信来源及目标端口 5353；默认禁止出站时，单播回复限制目标可信网段及源端口 5353，接收端口按客户端需求处理。

然后按前文“验证”一节检查服务和名称解析。

### 6. 停用 nxserver 的广播

nxserver.bin 默认会在所有接口监听 UDP 5353，这会导致用于蜂窝网络的 lan1 等接口的 IP 被 mDNS 匹配到，干扰域名解析，需要关闭它的广播。广播关闭之后，NoMachine 不能再自动发现此设备。

备份配置：
```bash
sudo cp -a \
  /usr/NX/etc/server.cfg \
  /usr/NX/etc/server.cfg.before-hostname-mdns
```

编辑 `/usr/NX/etc/server.cfg`：
```bash
sudoedit /usr/NX/etc/server.cfg
```
在其中中找到或添加：
```
EnableNetworkBroadcast 0
```

保存后重启 NoMachine 服务：
```bash
sudo /usr/NX/bin/nxserver --restart
```

然后确认 UDP 5353：
```bash
sudo ss -ulpn | grep ':5353'
```

理想结果是只剩 `avahi-daemon` 进程。

## 三、不使用脚本，手工取消

### 1. 恢复 Avahi 配置

```bash
sudo test -f /etc/avahi/avahi-daemon.conf.before-hostname-mdns
sudo cp -a \
  /etc/avahi/avahi-daemon.conf.before-hostname-mdns \
  /etc/avahi/avahi-daemon.conf
sudo systemctl restart avahi-daemon
```

确认恢复成功后删除手工备份：

```bash
sudo rm /etc/avahi/avahi-daemon.conf.before-hostname-mdns
```

如果配置前 Avahi 是停用状态，应恢复原状态，而不是重启：

```bash
sudo systemctl disable --now avahi-daemon
```

取消时应恢复配置前记录的服务状态。如果配置前 Avahi 已经启用并运行，就恢复配置并保持服务运行；如果原来停用，则执行上面的 `disable --now` 命令。

### 2. 删除手工添加的 UFW 规则

查看持久规则，并与本次实际新增记录核对；UFW 停用时也可以使用：

```bash
sudo ufw show added
```

只删除本次新增的完整规则，不要仅凭 `hostname-mdns-` 注释或编号判断归属。删除时在对应的 `allow` 命令前加 `delete`。例如，确认下面这条 IPv4 入站规则是本次新增后，执行：

```bash
sudo ufw delete allow in on lan0 to 224.0.0.251 port 5353 proto udp comment 'hostname-mdns-manual-lan0-ipv4-in'
```

再次检查：

```bash
sudo ufw show added
sudo ufw status verbose
```

不要删除没有 `hostname-mdns-` 注释的规则；它们可能由其他服务或管理员创建。

### 3. 恢复 nxserver 的配置

```bash
sudo test -f /usr/NX/etc/server.cfg.before-hostname-mdns
sudo cp -a \
  /usr/NX/etc/server.cfg.before-hostname-mdns \
  /usr/NX/etc/server.cfg
sudo /usr/NX/bin/nxserver --restart
```

确认恢复成功后删除手工备份：

```bash
sudo rm /usr/NX/etc/server.cfg.before-hostname-mdns
```

## 四、异常排查

### 提示 `avahi-daemon is not installed`

配置脚本不会安装软件包。先确认包状态：

```bash
dpkg-query -W -f='${Status}; version=${Version}\n' avahi-daemon
```

只有明确提示未安装时，才手工安装：

安装 `avahi-daemon` 可能自动启动服务，在限制接口前会按默认或已有配置运行。

```bash
sudo apt-get update
sudo apt-get install -y avahi-daemon
```

安装完成后重新运行 `configure-mdns.sh`。
