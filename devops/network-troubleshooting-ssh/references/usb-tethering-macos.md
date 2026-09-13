# USB Tethering on macOS · 诊断与配置

> **来源**：2026-08-07 主人案例（macOS 27.0 + OPPO PKB110 Android，USB tethering 不出网）
> **边界**：USB 网络共享 / USB tethering / 手机流量共享给电脑。**不**覆盖蓝牙共享、Wi-Fi 热点。
> **触发**：主人说"USB 网络共享""USB tethering""手机共享网络""电脑走手机流量""电脑用手机上 4G"。

## TL;DR

1. macOS **不能**主动激活 Android USB tethering —— 必须手机端先开
2. 手机开了之后，macOS 应该出现新网卡（一般是 `enX`，Android 默认给电脑 `192.168.42.x`）
3. 如果开了但 **没出现新网卡** —— 99% 是手机端 USB 模式没切对（要"USB 网络共享/RNDIS"）
4. 解决后用 `networksetup -ordernetworkservices` 把 USB 服务拉到第一位，让默认路由切到手机

## 完整诊断 5 步（macOS 端）

### Step 1：列接口，确认是否冒出新网卡

```bash
ifconfig -l 2>/dev/null | tr ' ' '\n' | grep -v '^lo$' | sort -u
# 或
ifconfig | grep -E "^(en|bridge)[0-9]+:" | head
```

**判读**：
- 出现新的 `enX`（如 `en8`）→ ✅ 协议层通了，看 IP/DHCP
- 出现新的 `bridge10X` → ✅ iPhone tethering 走 bridge，正常
- 没新接口 → ❌ 跳到 Step 2 看 USB 设备层

### Step 2：看 USB 设备树

```bash
system_profiler SPUSBDataType 2>/dev/null | grep -B 1 -A 10 "Vendor\|Product"
```

更详细的诊断用 ioreg：

```bash
ioreg -p IOUSB -l 2>/dev/null | grep -E "USB Product Name|USB Vendor Name|USB Serial Number"
```

**判读**：
- **看到手机型号**（如 OPPO PKB110 / Samsung SM-S9080 / Xiaomi 2201116C）→ USB 物理层 OK
- **没看到** → 数据线问题（只通电不通数据）或 USB 口供电不足

### Step 3：关键判读 —— RNDIS/Ethernet 协议有没有挂上

```bash
ioreg -p IOUSB -l 2>/dev/null | grep -B 1 -A 30 "<手机型号>"
```

找三个字段：

| 字段 | 期望值 | 含义 |
|------|--------|------|
| `bDeviceClass` | `0x02`（Communications）或 `0xEF`（Misc）/ `0xE0`（Wireless Controller） | **USB 设备类标识**。`0x00` = vendor-specific，**说明手机端 USB 没切到 RNDIS 模式** |
| `idVendor` | `0x22D9`（OPPO）/ `0x04E8`（Samsung）/ `0x2717`（Xiaomi）等 | 厂商识别，正常 |
| `bcdUSB` / `USBSpeed` | 高速连接 | 物理链路 OK |

**关键诊断**：`bDeviceClass = 0` **几乎一定是手机端 USB 配置模式错**。这时候 macOS 看到的就是个"vendor-specific 设备"，不会加载 RNDIS 网卡驱动。

### Step 4：检查现有网络服务列表

```bash
networksetup -listallnetworkservices
networksetup -listallhardwareports
```

如果 tethering 起来了，会看到 "USB 10/100/1000 LAN" 这种服务（macOS 系统名）。

### Step 5：DHCP/路由/DNS 检查

```bash
# 如果 Step 1 看到新接口如 en8
ifconfig en8
route -n get default
scutil --dns | head -20
```

**Android USB tethering 默认网段**：
- 手机本身：`192.168.42.129`
- 电脑：`192.168.42.x`（DHCP 自动）
- 子网：`255.255.255.0`
- DNS：通常 `192.168.42.129`（手机自己转发）

**iPhone USB tethering 默认网段**：
- 电脑：`172.20.10.x`
- 手机：`172.20.10.1`
- DNS：`172.20.10.1`

## 切换默认路由到 USB tethering

主人想要"电脑走手机流量（绕过 Wi-Fi 限制）"时，需要让默认路由走 USB，而不是 Wi-Fi。

### 方法 A：调整 Network 服务顺序（推荐）

```bash
# 看当前顺序
networksetup -listnetworkserviceorder

# 把 USB tethering 服务拉到第一位
networksetup -ordernetworkservices "USB 10/100/1000 LAN" "Wi-Fi" "Thunderbolt Bridge"
```

⚠️ macOS 12+ 这个命令需要先关闭 SIP 之外的服务保护；如果失败用方法 B。

### 方法 B：手动改路由 metric

```bash
# 看哪个接口在 default route
route -n get default | grep interface

# USB 网卡（en8）metric 调低，让它优先
sudo route add -net 0.0.0.0/0 192.168.42.129 -ifscope en8 -metric 100
sudo route add -net 0.0.0.0/0 <wifi 网关> -ifscope en0 -metric 200
```

### 方法 C：关 Wi-Fi（最暴力但最稳）

```bash
networksetup -setairportpower en0 off
# 用完打开
networksetup -setairportpower en0 on
```

如果主人在意 Wi-Fi 上还跑其他东西（比如局域网打印机、家里 NAS），不要用这个。

## 验证出口 IP 已切换

```bash
# 看当前出口 IP
curl -s ifconfig.me; echo
curl -s https://api.ipify.org; echo

# 对比 Wi-Fi 时的 IP（如果记得）
# 手机运营商 IP 段一般是 4G/5G CGNAT 段，不是家宽 IP
```

## 三大常见失败模式 + 修法

### 模式 1：手机开了"USB 网络共享"，macOS 还是看不到新网卡

**根因**：手机端 USB 模式没切到 RNDIS。

**修法（按厂商）**：

| 厂商 | 路径 |
|------|------|
| **OPPO / vivo / realme（ColorOS / OriginOS / realmeUI）** | 下拉通知栏 → 点 USB 连接通知 → 选"**USB 网络共享**"（不是"仅充电/文件传输"） |
| **小米/Redmi（MIUI/HyperOS）** | 下拉 → USB 用法 → "**USB 网络共享 (RNDIS)**"；或 设置 → 移动网络 → 个人热点 → USB 共享 |
| **华为/荣耀（HarmonyOS）** | 下拉通知栏 → USB 连接方式 → "**USB 网络共享**"；或 设置 → 系统 → 开发人员选项 → 网络 → USB 共享 |
| **三星（OneUI）** | 设置 → 连接 → 移动热点和 tethering → **USB tethering** |
| **原生 Android / Pixel** | 设置 → 网络和互联网 → 热点和网络共享 → **USB tethering** |

**陷阱**：OPPO/vivo 的"USB 网络共享"选项**经常只在 USB 刚插上时弹窗**，错过了要**重新插拔数据线**才能再选。

### 模式 2：macOS 看到设备但提示"USB device drawing too much power"

**根因**：USB 口供电不稳（通常是 USB hub 转接或老线）。

**修法**：
1. 拔下重插到主机**直连**的 USB 口（不是 hub）
2. 换**短而粗的**原厂数据线
3. macOS → 系统设置 → USB → 把这台手机标"忽略"再插

### 模式 3：网卡起来了但 curl 没反应 / 出口 IP 没变

**根因**：默认路由还在 Wi-Fi 上，系统根本没走 USB。

**修法**：按上面"切换默认路由"做。

## 数据线诊断（基础但常被忽略）

**主人根 USB 线**如果不是原厂的，多半是"**只通电不通数据**"的廉价线（内部只接了 2 根芯：VCC + GND，D+/D- 没接）。

**快速判断**：
- macOS 完全看不到手机设备 → 100% 数据线问题
- macOS 看到"USB 充电"但看不到设备名 → 99% 数据线问题
- macOS 看到型号但 `bDeviceClass=0` 且协议层不通 → 数据线 OK，但手机端 USB 模式错

**怎么验**：用同一根线接到 Android 手机上看"USB 用法"能不能切。**只充电线**在所有手机上都不出现模式选择弹窗。

## 实战案例（2026-08-07 主人）

**场景**：macOS 27.0 + OPPO Find X 系列（PKB110） + 系统报"已通过 USB 共享网络"但电脑侧没拿到 IP。

**诊断过程**：

1. `ifconfig -l | sort -u` → 没新接口
2. `system_profiler SPUSBDataType` → 看到 OPPO PKB110（Vendor 0x22D9）
3. `ioreg -p IOUSB -l | grep -A 30 PKB110` → `bDeviceClass = 0`（vendor-specific）
4. **结论**：USB 物理层 OK（USB 2.0 480 Mbps），但手机端 USB 配置模式没切到 RNDIS
5. **修法**：让主人在手机下拉通知栏重新选 USB 连接方式（OPPO 必须重新插拔数据线才会再弹窗）

**预期下一步**（待执行）：主人重新选 USB 模式后：
- 再跑 Step 1，应该看到新 `enX`
- DHCP 应该拿到 `192.168.42.x`
- 拉默认路由切到 USB
- `curl ifconfig.me` 看到手机运营商 IP

## 反例（不该做的事）

❌ **不要在没看到手机端 USB 模式正确的情况下**就开始改 macOS 配置 —— 白费功夫
❌ **不要给手机装 HoRNDIS / 第三方 RNDIS 驱动** —— macOS 原生支持 Android USB tethering，装第三方反而破
❌ **不要 sudo `ifconfig enX down` 试着重连** —— 容易把系统的 USB 子系统搞卡，需要拔线重插
❌ **不要相信手机端"USB 网络共享"开关显示开就一定开了** —— OPPO/HyperOS 的开关有 bug，开着但协议没起，要看手机通知栏图标
❌ **不要在主人公司/受限网络环境里用 USB tethering 绕过限制** —— 这是合规问题，不是技术问题，先问主人背景
❌ **不要 echo 手机 PIN / 锁屏密码 / 流量套餐信息到 MEMORY 或日志** —— 凭据类信息

## 联动

- `network-troubleshooting-ssh` 主 skill —— 如果主人说"USB tethering 后 SSH 连不上某台机"，先看路由表，可能默认路由没切
- `macos-app-gui-troubleshooting` —— 如果 USB tethering 之后某个 app 突然没网，那是 app 自己绑了 Wi-Fi 接口
- `huihui-absolute-gating` —— 不擅自重启系统网络（`sudo ifconfig down` / 重启网络服务）；操作前先 backup 主人当前路由表