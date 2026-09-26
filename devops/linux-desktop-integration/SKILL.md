---
name: linux-desktop-integration
description: Use when 装 GNOME 扩展或配 KDE Connect 手机剪贴板互通、配对排障。
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [linux, gnome, extension, kde-connect, gsconnect, clipboard]
---

# Linux 桌面集成：GNOME 扩展部署 + 跨设备配对

覆盖两类任务：从 extensions.gnome.org 装扩展并免注销激活；配 KDE Connect/GSConnect 实现手机↔电脑剪贴板互通。

## 从 extensions.gnome.org 装扩展（无浏览器、免注销）

1. 解析当前 shell 对应版本——下载 API 要的是**数字 version_tag**，不是版本号：
```bash
SV=$(gnome-shell --version | awk '{print $3}')
curl -s "https://extensions.gnome.org/extension-info/?pk=<扩展PK>&shell_version=$SV"
# → version（发布号）、version_tag（下载用的数字 pk）、shell_version_map
```
2. 带 version_tag 下载（传发布号如 `72` 会 404）：
```bash
curl -fsSL -o ext.zip "https://extensions.gnome.org/download-extension/<uuid>.shell-extension.zip?version_tag=<tag>"
```
3. 部署并编译 schema：解压到 `~/.local/share/gnome-shell/extensions/<uuid>/`，进入后 `glib-compile-schemas schemas/`。装前核对 metadata.json 的 shell-version 覆盖当前 shell。
4. **免注销激活**（GNOME Shell 50.1 实证）：shell 不监控扩展目录，戳一次扩展服务强制重扫：
```bash
gdbus call --session --dest org.gnome.Shell.Extensions --object-path /org/gnome/Shell/Extensions \
  --method org.gnome.Shell.Extensions.InstallRemoteExtension "<uuid>"
```
该调用报 `NoReply` 是预期的，失败的重扫仍然发生；数秒后 `gnome-extensions enable <uuid>` 即可。
5. 三重验证：`gnome-extensions info <uuid>` 状态 ACTIVE；`gsettings get org.gnome.shell enabled-extensions` 含 uuid；扩展自身服务证据上总线（`busctl --user list | grep -i <名>`、`ss -tln` 端口）。

**API 坑**：`update-info` 端点缺参时返回空 body，用 `extension-info/?pk=`。apt 里的扩展包常落后于新 GNOME（v71 只到 GNOME 49），EGO zip 是更新路径——先 `apt-cache policy` 比版本。

## gdbus org.gtk.Actions 调用语法

- 无参动作：`gdbus call … --method org.gtk.Actions.Activate <action> '[]' '{}'`（pair/unpair/refresh 均此形式）。
- 带参动作：每个值要包 variant——`[<"文本">]`，裸 `['文本']` 解析为 v 失败。
- 签名为 `()` 的动作传参会报 `expected type () but got type s`：该动作读的是当前状态（如 GSConnect clipboardPush 推的是**当前剪贴板**），先 wl-copy 写剪贴板再调用。
- 枚举对象有哪些动作：`--method org.gtk.Actions.List`。

## GSConnect / KDE Connect 配对

**安装选型**：apt 候选版本支持当前 GNOME 就 `sudo apt install gnome-shell-extension-gsconnect sshfs`（sshfs 供远程文件系统插件）；版本落后走上面 EGO 流程。回滚：disable + 删扩展目录 + 从 enabled-extensions 去掉 uuid；保留 `~/.config/gsconnect`（配对密钥）。

**服务证据**（排障前全须成立）：`busctl --user list | grep -i gsconnect`（含 Clipboard 助手）、TCP 1716 监听、UDP 1716 发现。设备真源：
```bash
gdbus call --session --dest org.gnome.Shell.Extensions.GSConnect \
  --object-path /org/gnome/Shell/Extensions/GSConnect \
  --method org.freedesktop.DBus.ObjectManager.GetManagedObjects
# 每设备：Name / Connected / Paired / Id / EncryptionInfo
```

**配对失败分诊**：
- `Paired:true, Connected:false` 且手机停播 → 国产 ROM 省电冻结了 app（ColorOS/OnePlus 系）：ping 得通但 UDP identity 全无回应。修法在手机侧：重开 KDE Connect + 电池设置允许后台运行。
- 手机 app 重装/清数据会换设备 Id → 桌面侧旧配对失配，握手即断。修法：对设备对象执行 `unpair`（对象随即可消失），等手机重新广播后重新配对。
- 手机存活时约 30 秒一轮广播；连续数分钟零广播 = app 冻结，不是网络问题。

**主动探测**（不等广播，直接单播 identity 给手机）：
```python
identity = {"id": MY_ID, "name": HOSTNAME, "deviceType": "desktop", "protocolVersion": 7, "tcpPort": 1716}
sock.sendto(json.dumps(identity).encode(), (PHONE_IP, 1716))  # ×3，间隔 1.5s
```
MY_ID = `openssl x509 -in ~/.config/gsconnect/certificate.pem -noout -subject` 的 CN。手机活着会回 identity；ping 通但无回应 = app 冻结。旁路监听可用 SO_REUSEADDR 绑 1716 与 gsconnect 共存。

**配对解锁**：双向剪贴板同步（两端 app 内开启）、文件互传、通知中继、手机当触控板。全程局域网直连无厂商账号。

## Pitfalls

**P1：`gnome-extensions list` 看不到刚部署的扩展 ≠ 要注销**。先试 InstallRemoteExtension 重扫法（上文步骤 4）；确实无效再让用户注销重登。

**P2：配对卡死先分诊再动手**。按分诊表判断是手机冻结还是 Id 失配，方向错了会白做（对冻结手机反复 unpair/pair 无意义）。
