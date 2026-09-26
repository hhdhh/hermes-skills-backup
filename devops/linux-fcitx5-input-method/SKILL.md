---
name: linux-fcitx5-input-method
description: Use when 配置本机 Ubuntu fcitx5 输入法栈：加删输入法、候选框主题、Rime/微信拼音排障。
version: 1
license: MIT
---

# fcitx5 输入法栈配置（本机 Ubuntu）

管理本机 fcitx5 + Rime + wetype 输入法栈：输入法列表、候选框主题、共存与回滚。

## 环境快照

- fcitx5 5.1.19 + GNOME Wayland，用户 `kk`
- Rime（雾凇拼音，`~/.local/share/fcitx5/rime`）与 wetype（微信拼音）并存，Ctrl+Space 切换
- wetype 引擎 = QEMU user 模式跑 Android ARM64，纯离线
- 工作目录 `~/xxd-rime/`：转换脚本 + 全部回滚备份（classicui.conf.bak / profile.bak）

## 铁律

1. **改配置前先 `pkill -x fcitx5`**——运行中的 fcitx5 退出时用内存状态覆写 `~/.config/fcitx5/profile`，边跑边改会被静默回滚。顺序固定：停进程 → 改文件 → `fcitx5 -d --replace`（后台启动）。
2. **profile 里 Items 的 `Name=` 必须等于 `~/.local/share/fcitx5/inputmethod/<名>.conf` 的文件名**（wetype-im.conf → Name=wetype-im），不是 addon 名；写错 fcitx5 静默忽略，不报错。
3. **classicui 5.1.19 没有 Radius 配置项**（`strings libclassicui.so` 可证）——圆角候选框只能用 PNG 9-patch 资产；squirrel.yaml 的 color_schemes 在 fcitx5 下完全无效，必须转成 fcitx5 主题（颜色 0xBBGGRR → #RRGGBB）。配方见 `references/theme-conversion.md`。
4. **候选框保持竖排**（用户明确偏好，改横排被退回过）；竖排 + FullWidthHighlight（默认 true）才是整行圆角高亮的官方预览效果。
5. **动配置前先备份到工作目录**，回滚 = 拷回 + 重启 fcitx5。

## 验证（每次改动后必跑）

```bash
pgrep -x fcitx5
dbus-send --session --print-reply --dest=org.fcitx.Fcitx5 /controller \
  org.fcitx.Fcitx.Controller1.FullInputMethodGroupInfo string:"默认" \
  | grep -E "string \"(rime|wetype-im)\""
~/xxd-rime/WeTypeIME-Engine-x86_64.AppImage demo nihao   # wetype 出词，首选应为你好
```

## wetype（微信拼音）要点

- 项目 yu1745/wetype-ime-linux；安装器从腾讯官方服务器下 APK 并校验 SHA-256
- **纯离线是设计使然**：harness 无 socket/connect 符号、sysroot 无 CA 证书；云候选/账号/跨设备同步不可实现，别往这个方向试
- 引擎进程 = qemu-aarch64-static 常驻（OnDemand=False）；学习数据 `~/.local/share/wetype-ime`；`AppImage uninstall` 保留词库
- 判定“是否联网”用实证：打字期间 `ss -tnp/-unp` 采样 qemu 进程 + harness 日志里的 cloud 标志，不猜

## Pitfalls

- 输入法加不进组：先查唯一名是否=conf 文件名（铁律2），再查是不是被运行中的 fcitx5 覆写了 profile（铁律1）
- 主题不生效：classicui.conf 的 Theme/DarkTheme 值必须等于 `themes/` 下目录名；改完必须重启 fcitx5
- Wayland 下无全局截图权限（gnome-screenshot/scrim/dbus Screenshot 全不可用）——验证候选框外观用 PIL 几何仿真，见 `references/theme-conversion.md`
