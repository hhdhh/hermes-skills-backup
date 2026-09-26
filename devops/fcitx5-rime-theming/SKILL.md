---
name: fcitx5-rime-theming
description: Use when 给 fcitx5/Rime 换配色主题或排查 Rime 配色不生效。
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [fcitx5, rime, theming, input-method, linux, ubuntu]
---

# fcitx5 / Rime 输入法换肤

> 完整描述：给 fcitx5（含 fcitx5-rime）候选栏换配色/主题，移植 Rime squirrel 配色包到 Linux；含圆角九宫格 PNG 生成与几何验证。

## 铁律（always-on）

1. **先判前端再动手**：`dpkg -l | grep -E 'fcitx5-rime|ibus-rime'` + `im-config -l` + `pgrep -a fcitx5`。Rime 的 `squirrel.yaml`/`weasel.yaml` `color_scheme` **在 fcitx5 下完全不生效**——librime 只出候选词，候选栏由 fcitx5 classicui 自绘，必须走 fcitx5 主题（`~/.local/share/fcitx5/themes/<name>/theme.conf`）。
2. **样式任务最小 diff**：只改主题文件 + `classicui.conf` 的 `Theme=`/`DarkTheme=`。**绝不顺手改布局偏好**（`Vertical Candidate List`、字体等）——那是用户的，不是任务的一部分。
3. **改 `~/.config/fcitx5/conf/classicui.conf` 前先备份**，改完 `fcitx5-remote -r` 重载。
4. **验证靠数据不靠感觉**：拿不到真实截屏时，用 PIL 九宫格模拟渲染 + 像素测量官方预览图对齐几何参数（选中块高度/圆角/padding），量化一致才算完成。

## 工作流

### 1. 侦察输入法栈

```bash
dpkg -l | grep -iE 'fcitx5-rime|ibus-rime|squirrel' ; im-config -l ; pgrep -a fcitx5
ls ~/.local/share/fcitx5/rime/            # fcitx5-rime 用户目录（不是 ~/.config/ibus/rime）
cat ~/.config/fcitx5/conf/classicui.conf  # 当前主题/布局
ls ~/.local/share/fcitx5/themes/ /usr/share/fcitx5/themes/
```

### 2. 配色来源是 squirrel 格式 → 跑转换器

squirrel 颜色是 Windows 字节序 `0xBBGGRR`（带透明度则 `0xAABBGGRR`），fcitx5 要 `#RRGGBB`/`#AARRGGBB`，**必须换序**，直接当 RGB 用会红蓝反。用现成脚本一键生成整套主题（含圆角 PNG）：

```bash
python3 scripts/squirrel2fcitx5.py --src xxd.squirrel.yaml --dest ~/.local/share/fcitx5/themes
```

### 3. 圆角 = 九宫格 PNG，不是配置项

fcitx5 classicui（5.1.x，Debian/Ubuntu 构建）**没有 `Radius` 配置项**——用 `strings /usr/lib/x86_64-linux-gnu/fcitx5/libclassicui.so | grep -i radius` 可验证（空=无此选项）。官方主题的做法是 9-patch PNG：`panel.png`（面板）+ `highlight.png`（选中块），同名 `@2x` 高清版。PNG 的 `Margin=` 就是九宫格切割线，**margin 值应等于圆角半径**（切割线内侧 1:1 拷贝角落，不缩放）。转换器已内置生成。

### 4. 激活

`classicui.conf`：`Theme=<name>` + `DarkTheme=<name>-night`（用户若开 `UseDarkTheme=True`，浅色/夜色**成对**部署）。然后 `fcitx5-remote -r`。

### 5. 几何验证（无法截屏时）

Wayland 会话常见无授权截图工具；此时：
- PIL 像素测量官方预览图：选中块 bbox 高度、角半径阶梯扫描、文字 padding；
- PIL 按九宫格算法模拟渲染候选栏，核对选中块高度/圆角与预览一致（见 references/fcitx5-theme-anatomy.md 的算法摘要）。

渲染行为拿不准时**读上游源码**而不是猜：`https://raw.githubusercontent.com/fcitx/fcitx5/master/src/ui/classic/{theme,inputwindow}.cpp`（直连超时就走本机代理 `-x socks5h://127.0.0.1:7890`）。

## Pitfalls

### P1：Rime color_scheme 在 fcitx5 不生效
机制：librime 只管候选词，classicui 自绘候选栏。装 Rime 配色包到 fcitx5 机器 = 写 fcitx5 主题，改 squirrel.yaml 无用。

### P2：用户说"还不如之前的"→ 先 diff 全部改动，优先回滚越权的偏好改动
换肤任务变丑的最常见根因不是颜色，而是顺手改了布局：横排时选中块收缩成窄条；竖排 + `FullWidthHighlight`（默认开）才是整行圆角色块、对应 macOS 风预览。回滚所有非任务必需的改动（布局、字号系数等花活）再精调。

### P3：颜色字节序反了会"整个怪"但能跑
squirrel `0xD0D881` 实为 `#81D8D0`。8 位 `0xAABBGGRR` → fcitx5 `#AARRGGBB`（alpha 前置、RGB 换序）。

### P4：圆角 PNG 的 Margin 语义
`[InputPanel/Highlight/Margin]` 既是九宫格切割线也是选中块外扩量：块实际大小 = 候选文字 + margin 全方向外扩。margin ≠ 圆角半径会导致角落被拉伸变形。

### P5：丢注释色会显得"半成品"
fcitx5 主题必须齐 `CandidateCommentColor`/`HighlightCandidateCommentColor`/`HighlightCandidateLabelColor`，否则注释回退默认色，观感割裂。

## 支撑文件

- `references/fcitx5-theme-anatomy.md` — theme.conf 键位、九宫格绘制算法（theme.cpp 摘要）、选中块绘制公式（inputwindow.cpp）、几何测量配方
- `scripts/squirrel2fcitx5.py` — squirrel→fcitx5 主题批量转换器（含圆角 PNG @1x/@2x 生成）
