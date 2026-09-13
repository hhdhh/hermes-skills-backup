# 只读命令白名单（工作站 / 机器人 分册版）

> 2026-09-13 按机队实际情况分两份。**工作站分册**：本机 kk-GDH-X（核显、无 NVIDIA、机器人服务不在此跑）。
> **机器人分册**：SSH 到机器人上执行（按机号定位，IP 动态解析：`robssh.py ip <机号>`）。
> 检查、诊断和修复后验证阶段，只从对应分册中选择。参数只能缩小查询范围，不得加入写入、删除、重启、信号或执行动作。

## 分册判定

```text
本机（工作站）执行  → 用【工作站分册】
ssh ubuntu@<robot> → 用【机器人分册】（SSH 本身经 kk-fae-repair.rules 放行）
```

## 工作站分册（kk-GDH-X · 核显无独显）

### Doctor

```bash
autolife-doctor --version
autolife-doctor --config "$HOME/.config/autolife-doctor/config.toml" --validate-config
autolife-doctor --config "$HOME/.config/autolife-doctor/config.toml" --once
autolife-doctor --config "$HOME/.config/autolife-doctor/config.toml" --once --format json
autolife-doctor --config "$HOME/.config/autolife-doctor/config.toml" --check CHECK_ID
autolife-doctor repair-policy
autolife-doctor report-status
autolife-doctor ownership-status
autolife-doctor release-status
autolife-doctor agent status
```

`CHECK_ID` 限于 Doctor 已有的 22 个 stable ID。只读阶段不使用 `repair`、`watch --heal` 或任何 `--yes`。

### 主机与资源

```bash
date --iso-8601=seconds
hostnamectl --static
id
uname -a
uptime
free -h
df -h
df -h PATH
lsblk
mount
findmnt
ps -ef
pgrep -af PATTERN
sensors        # 核显温度走 sensors；本机无 nvidia-smi
```

### systemd 与日志（工作站只跑 Hermes/gateway 等 user 服务）

```bash
systemctl --user status UNIT --no-pager
systemctl --user show UNIT PROPERTY_ARGS
systemctl --user list-units --all PATTERN
systemctl --user list-unit-files PATTERN
systemctl --user --failed --no-pager
journalctl --user -u UNIT --since TIME --until TIME --no-pager
journalctl --user -u UNIT -n LINES --no-pager
```

`systemctl` 只允许查询类动词；变更类（start/stop/restart/reload/enable/disable/mask/unmask/set-property/daemon-reload）在 read-only rules 中 forbidden。

### 网络

```bash
ip -brief address
ip address show
ip route show
ip route get ADDRESS
ip neigh show
ss -lntup
ping -c COUNT -W SECONDS ADDRESS
iw dev
iw dev INTERFACE link
nmcli -t device status
nmcli -t connection show --active
resolvectl status
```

### 文件元数据与版本

```bash
ls -la APPROVED_PATH
stat APPROVED_PATH
file APPROVED_PATH
readlink APPROVED_PATH
readlink -f APPROVED_PATH
sha256sum APPROVED_PATH
command -v PROGRAM
PROGRAM --version
```

`APPROVED_PATH` 限于用户指定的目标或 Doctor/Hermes 配置中已列出的路径。除技能指令文件外，不使用 `cat`、`head`、`tail`、`grep`、`find` 或递归遍历读取未知文件内容。

### 工作站分册不含

- `nvidia-smi`（本机核显，无 NVIDIA）
- 机器人服务单元（rust-web-server 等，这些在机器人上）

## 机器人分册（SSH 到机器人后执行）

### 服务与日志（机器人服务全在 systemd user 层）

```bash
systemctl --user status UNIT --no-pager
systemctl --user show UNIT -p Environment      # 查 CYCLONEDDS_URI 阵营归属（DDS 排查核心）
systemctl --user list-units --type=service --no-legend
systemctl --user --failed --no-pager
journalctl --user -u UNIT -n LINES --no-pager
journalctl --user -p err --since -1h --no-pager
```

### DDS / ROS2 诊断（机器人特有）

```bash
ros2 topic list
ros2 topic info /TOPIC            # 注意阵营：必须先 export 对应 CYCLONEDDS_URI 再查（见 dds-camp-split 技能）
ros2 node list
export CYCLONEDDS_URI=file:///path/to/camp-uri.xml   # 显式进入某阵营后查询
findmnt
```

### 主机与硬件（机器人有电机/传感器/急停）

```bash
date --iso-8601=seconds
uptime
free -h
df -h
sensors
cat /proc/mdstat 2>/dev/null || true
# 机器人专属状态（按机型实际路径）：
#   电机/传感器/急停状态文件路径见 robot-recovery.md
```

### 网络（机器人侧视角）

```bash
ip -brief address
ip route show
ss -lntup
ping -c COUNT -W SECONDS ADDRESS
```

### 文件检查

```bash
md5sum /path/to/prompt.txt        # prompt 版本链校验（v10-reading = 9ea681d65ab392e2e5a732fdacdec773）
ls -la /path/to/config
cat ~/.config/systemd/user/UNIT.d/*.conf   # 看 unit override 里的环境变量
```

## 管道和格式化（两分册通用）

可以将上述命令的输出传给 `awk`、`sed`、`sort`、`uniq`、`wc` 或只读 Python/JSON 解析器，但解析器不得写文件、启动子进程或访问网络。

## 不在白名单中

任何会修改文件、包、服务、进程、网络、设备、配置、权限或系统时间的命令都不属于只读白名单。需要维修时转入维修步骤（Safe 级 doctor auto-safe / Guarded 级先说明），执行最小必要动作，然后回到本白名单进行验证。
