# 微信输入法（WeType）Linux 安装

腾讯官方无 Linux 版。社区移植 `yu1745/wetype-ime-linux`：fcitx5 插件 + QEMU user 模式跑 Android ARM64 引擎；APK 从腾讯官方服务器下载并校验 SHA-256 后本机打补丁（不二次分发、不联网输入、保留学习数据）。仅 x86_64。

## 前置确认

- fcitx5 框架 + FUSE（fusermount3 存在）；容器内无 FUSE 用 `APPIMAGE_EXTRACT_AND_RUN=1`
- 依赖：`sudo apt install patchelf unzip curl`（sudo 密码 `hermes config get SUDO_PASSWORD` 取，不回显聊天）

## 安装步骤

```sh
# 1. 下载 release AppImage（~4MB）+ 校验
#    https://github.com/yu1745/wetype-ime-linux/releases
sha256sum -c <(curl -sL .../WeTypeIME-Engine-x86_64.AppImage.sha256)  # 比对手动也行
chmod +x WeTypeIME-Engine-x86_64.AppImage
# 2. 安装到 ~/.local（首次自动从 download.z.weixin.qq.com 拉 214MB APK，缓存 ~/.cache/wetype-ime，只下一次）
./WeTypeIME-Engine-x86_64.AppImage install
# 3. 引擎自检
./WeTypeIME-Engine-x86_64.AppImage demo nihao
```

## 加入输入法列表（关键：停→改→启）

安装器只落文件：`~/.local/share/fcitx5/addon/wetype.conf`、`~/.local/share/fcitx5/inputmethod/wetype-im.conf`、`~/.local/lib/fcitx5/libfcitx5-wetype.so`。条目要手动进组：

```sh
pkill -x fcitx5   # 必须先停，否则 profile 被覆写
# ~/.config/fcitx5/profile 在 [GroupOrder] 前插入：
# [Groups/0/Items/N]
# Name=wetype-im        ← = conf 文件名，不是 wetype
# Layout=
fcitx5 -d --replace
```

验证：`dbus-send ... Controller1.FullInputMethodGroupInfo string:"默认"` 里出现 `wetype-im / 微信拼音`。

## 路径与卸载

- 学习数据 `~/.local/share/wetype-ime`（uninstall 保留）
- APK 缓存 `~/.cache/wetype-ime`（217MB，可删，重装重下）
- 卸载：`./WeTypeIME-Engine-x86_64.AppImage uninstall`；从 profile 删条目同样走停→改→启

## 网络注意

GitHub release 直连慢但可用（`--retry 3`）；代理 socks5h://127.0.0.1:7890 对部分域会 exit 35，直连失败再换代理，别死磕一个通道。
