---
name: gnome-shell-extension-install
description: Use when manually installing GNOME Shell extensions.
version: 1
license: MIT
metadata:
  hermes:
    tags: [gnome, shell, extension, extensions-gnome-org, user-install]
---

# GNOME Shell 扩展手动安装（免注销）

为当前 GNOME Shell 安装/升级扩展。核心坑：apt 源版本滞后、运行中的 Shell 不监听扩展目录变化。

## 流程

### 1. 查 Shell 版本，再查官方源对应 tag
```bash
gnome-shell --version
# pk 从扩展主页 URL 取（如 GSConnect = 1319）
curl -s "https://extensions.gnome.org/extension-info/?pk=<pk>&shell_version=<版本>" -o /tmp/ei.json
python3 -c "import json; d=json.load(open('/tmp/ei.json')); print(d['version'], d['version_tag'])"
```
`version_tag` 才是下载要用的（不是 release 号）。不要用 apt：`gnome-shell-extension-*` 包通常落后一到两个大版本（如源里 71 只支持 GNOME 49，装到 Shell 50 上直接不兼容）。

### 2. 下载安装到用户目录
```bash
curl -fsSL -o ext.zip "https://extensions.gnome.org/download-extension/<uuid>.shell-extension.zip?version_tag=<tag>"
rm -rf ~/.local/share/gnome-shell/extensions/<uuid>
unzip -oq ext.zip -d ~/.local/share/gnome-shell/extensions/<uuid>
cd ~/.local/share/gnome-shell/extensions/<uuid> && glib-compile-schemas schemas/
```
装前看 metadata.json 的 `shell-version` 是否含当前大版本。

### 3. 让运行中的 Shell 发现它
运行中的 Shell 不监控扩展目录。触发扫描（报 NoReply 错也算成功，等 3s 再查）：
```bash
gdbus call --session --dest org.gnome.Shell.Extensions --object-path /org/gnome/Shell/Extensions \
  --method org.gnome.Shell.Extensions.InstallRemoteExtension "<uuid>"
sleep 3
gnome-extensions list | grep <uuid>   # 出现即被扫描
```
若仍未出现：X11 可 Alt-F2 → r 重载；Wayland 只能注销重登。然后：
```bash
gnome-extensions enable <uuid>
```

### 4. 验证到服务级
不要只看 enabled 列表。验证扩展的后台服务真的起来了：
```bash
gnome-extensions info <uuid> | grep 状态   # ACTIVE
busctl --user list | grep -i <关键词>       # 如 GSConnect 会注册 org.gnome.Shell.Extensions.GSConnect
ss -tln | grep <端口>                       # 如 1716
```

## Pitfalls

- **apt 版本滞后直接装 = 不兼容**：先查 `apt-cache policy <pkg>` 候选版本支持的 Shell 版本，跟不上就走官方扩展源 zip。
- **download-extension 的 version_tag 不是 release 号**：用 extension-info API 返回的 `version_tag` 字段，猜的 tag 会 404。
- **gnome-extensions 报“不存在”不等于没装**：文件在 ~/.local/share/gnome-shell/extensions/ 但 Shell 未扫描；先触发 InstallRemoteExtension 再等 3 秒重查。
- **gdbus call 的 av 参数坑**：variant 字符串必须写成 `'[<"x">]'`，裸字符串列表会解析失败；复杂调用改用 gjs（`imports.gi.Gio` + `GLib.Variant`），注意 `Gio.DBusProxy.new_sync` 需 7 个参数（接口后补 `null`）。