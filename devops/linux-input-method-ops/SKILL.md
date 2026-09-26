---
name: linux-input-method-ops
description: Use when 在 Linux 配输入法：fcitx5 主题、Rime 配色移植、装微信输入法等.
---

# Linux 输入法运维（fcitx5 / Rime / WeType）

## 第一步：环境侦察（任何输入法任务先做）

```sh
im-config -l; cat /etc/X11/xinit/xinputrc   # 框架是 fcitx5 还是 ibus
pgrep -a fcitx5
ls ~/.local/share/fcitx5/themes/            # 用户主题
grep -E "^(Theme|DarkTheme|Vertical Candidate List|UseDarkTheme)" ~/.config/fcitx5/conf/classicui.conf
```

- fcitx5-rime 的 Rime 数据在 `~/.local/share/fcitx5/rime/`（不是 `~/.config/ibus/rime`）。
- `Theme=` + `DarkTheme=` 成对设，`UseDarkTheme=True` 时随系统深浅自动切换。

## 铁律

1. **fcitx5-rime 不读 squirrel.yaml 的 color_scheme** — Rime 配色必须转成 fcitx5 主题（`~/.local/share/fcitx5/themes/<name>/theme.conf`）。候选栏颜色/形状全由 fcitx5 主题控制，对所有引擎（rime/wetype/pinyin）统一生效。转换脚本见 `scripts/squirrel2fcitx5.py`，映射细节见 `references/squirrel-theme-conversion.md`。
2. **主题任务只动主题** — 不要顺手改用户没提的偏好（候选栏方向、字体、竖排/横排）。方向决定选中块形状：竖排 + FullWidthHighlight（默认开）= 整行圆角色块（官方预览形态）；横排 = 窄块只包文字。要改方向必须先问。
3. **classicui 5.1.x 没有 Radius 配置项** — 圆角只能用九宫格 PNG（`panel.png`/`highlight.png` + `Image=`，同名 `@2x` 高清版，Margin 即九宫格切割线）。承诺圆角前先 `strings /usr/lib/x86_64-linux-gnu/fcitx5/libclassicui.so | grep -i radius` 验证该版本支持。
4. **profile 编辑三步法：停→改→启** — `pkill -x fcitx5` → 改 `~/.config/fcitx5/profile` → 再 `fcitx5 -d --replace`（用 terminal background=true 启动）。运行中编辑会被内存态覆写，等于白改。
5. **输入法条目 Name = inputmethod/ 下 conf 文件名**（`wetype-im.conf` → `Name=wetype-im`）。写错名 fcitx5 静默忽略，dbus 查得到才算真加上了。
6. **改前备份**（classicui.conf、profile 拷到工作目录）；回滚 = 恢复备份 + `fcitx5-remote -r`。

## 验证（必做，不靠目测声明成功）

```sh
fcitx5-remote >/dev/null && echo running
# 输入法是否注册进组：
dbus-send --session --print-reply --dest=org.fcitx.Fcitx5 /controller \
  org.fcitx.Fcitx.Controller1.FullInputMethodGroupInfo string:"默认" | grep wetype
# WeType 引擎出词：
./WeTypeIME-Engine-x86_64.AppImage demo nihao
```

## 支持文件

- `references/squirrel-theme-conversion.md` — squirrel→fcitx5 颜色映射、九宫格 PNG 参数、几何对齐验证法、fcitx5 源码定位
- `references/wetype-linux-install.md` — 微信输入法 Linux 移植版安装/卸载全流程
- `scripts/squirrel2fcitx5.py` — 一键转换器（需 Pillow；生成 theme.conf + 圆角 PNG，浅/夜成对）
