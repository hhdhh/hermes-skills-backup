---
name: fcitx5-ime-management
description: Use when fcitx5 加引擎/改 profile/换候选窗主题，或新引擎加了不出现。含微信拼音移植与主题转换。
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [linux, fcitx5, input-method, rime, theming]
---

# fcitx5 输入法栈管理

管理 fcitx5（非 ibus）环境下的输入法引擎、profile、候选窗主题。适用于 Ubuntu/GNOME 桌面，用户已有 fcitx5 + rime 共存栈。

## Always-on rules

1. **任何 profile/conf 改动前先停进程**：`pkill -x fcitx5` → 改文件 → `fcitx5 -d --replace`。机制：运行中的 fcitx5 在退出时会把内存态序列化覆写 `~/.config/fcitx5/profile`，对运行中实例的文件编辑会被静默回滚。
2. **`[Groups/0/Items/N] Name=` 必须等于 inputmethod 配置文件名**（`~/.local/share/fcitx5/inputmethod/wetype-im.conf` → `Name=wetype-im`），不是 addon 名；不匹配的条目被无报错丢弃。
3. **验证只信 dbus**，文件内容不是真相：
```bash
dbus-send --session --print-reply --dest=org.fcitx.Fcitx5 /controller \
  org.fcitx.Fcitx.Controller1.FullInputMethodGroupInfo string:"默认"
```
4. **用户偏好**：竖排候选列表是既定选择，不要为了"对齐参考图"擅自改横排；rime 与新增引擎在同一 group 共存（Ctrl+Space / Ctrl+Shift 切换），不替换。

## Workflow：安装第三方引擎（worked example：微信拼音 WeType）

1. 依赖：`sudo apt install -y patchelf`（唯一系统依赖）。
2. 安装器：`./WeTypeIME-Engine-x86_64.AppImage install`（从 download.z.weixin.qq.com 下官方 APK，SHA-256 校验后本地打补丁；APK 缓存 `~/.cache/wetype-ime` ~214MB 只下一次）。
3. 离线验证引擎：`./WeTypeIME-Engine-x86_64.AppImage demo nihao` → 候选词列表，首选应为 你好。
4. 注册产物（install 自动生成，路径供排障）：插件 `~/.local/lib/fcitx5/libfcitx5-wetype.so`；`~/.local/share/fcitx5/addon/wetype.conf`（Library=绝对路径，OnDemand=False 常驻）；`~/.local/share/fcitx5/inputmethod/wetype-im.conf`（Name=显示名，Addon=wetype，LangCode=zh_CN）。
5. 按上面规则停进程→加 `[Groups/0/Items/N] Name=wetype-im`→重启→dbus 验证组内同时有 rime 与 wetype-im。
6. 数据/卸载：用户学习数据 `~/.local/share/wetype-ime`（uninstall 保留）；卸载 `./WeTypeIME-Engine-x86_64.AppImage uninstall`；日志 `/tmp/wetype-harness.log`。

## 主题：squirrel.yaml 不会迁移

fcitx5 classicui 完全忽略 Rime 的 squirrel.yaml color_schemes。复用 Rime/Squirrel 主题必须重新编码为 fcitx5 theme：

- 颜色字节序：squirrel 是 `0xBBGGRR`（或 `0xAABBGGRR`），转换时对调成 `#RRGGBB`/`#AARRGGBB`。
- classicui 5.1.x **没有圆角配置项**（二进制 strings 验证无 Radius key）：圆角必须用 9-patch PNG 资产（panel + highlight，各配 @2x）。
- 要还原 Squirrel 观感：竖排候选 + `FullWidthHighlight=True`（默认）才会画整行圆角高亮；官方芯片高≈51px，对应 TextMargin≈10/10/6/6、背景/高亮 Margin≈10、Spacing≈3。fcitx5 源码 inputwindow.cpp 的 9-tile 绘制逻辑是校准依据。
- 应用：`~/.config/fcitx5/conf/classicui.conf` 设 Theme/DarkTheme/UseDarkTheme，主题目录 `~/.local/share/fcitx5/themes/<name>/`，改完按 stop-first 规则重启。

## Pitfalls

**P1：改了 profile 没生效** = 没停进程就改了（见 always-on rule 1 的覆写机制），或 Name= 写错（rule 2）。

**P2：问"这输入法联网吗"要拿连接表说话**，不要只看日志关键词：引擎日志里出现 cloud/cloud_input 字样只代表代码路径存在。实证：`for pid in $(pgrep -f <engine>); do ss -tnup | grep "pid=$pid,"; done`（多进程时逐 pid 查，变量多行会让 grep 误匹配）；再在打字高峰连续采样 ss 确认 0 连接。

**P3：qemu-user 移植的 Android 引擎没有网络栈也不可能有云功能**（harness 无 socket/connect 符号、sysroot 无 CA 证书）——账号登录、云候选、厂商跨设备剪贴板都不存在。用户的跨设备需求引导到 KDE Connect/GSConnect（见 skill: linux-desktop-integration），不要承诺引擎联网。
