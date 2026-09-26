# Squirrel → fcitx5 主题转换配方（XXD 品牌色案例）

把 Rime squirrel 配色转成 fcitx5 classicui 主题的完整参数。工具链在 `~/xxd-rime/`：convert.py（生成 40 个主题）、measure.py（量官方预览几何）、render.py（PIL 九宫格仿真）。

## 颜色转换

- squirrel 颜色是 `0xBBGGRR`（带透明则 `0xAABBGGRR`）→ fcitx5 用 `#RRGGBB` / `#AARRGGBB`，字节序必须交换

## 官方预览几何（PIL 量取）

- 候选 chip：209×51px，圆角 ≈7px，文字高 34px，内边距 ≈8.5px
- 目标：仿真渲染的 chip 高度对齐 51px 即算还原

## 9-patch PNG 资产（classicui 无 Radius 的唯一圆角方案）

- panel.png 48×48、圆角 r10；highlight.png 48×32、圆角 r6；各配 @2x 版本
- PNG 内黑线位置 = 伸缩区；fcitx5 按 9-tile 绘制（算法见 fcitx5 源码 theme.cpp 519-563 行）
- 高亮尺寸算法在 inputwindow.cpp 595-625 行：竖排 + FullWidthHighlight=true 时整行填充

## theme.conf 关键项（v3 调好的值）

- `[InputPanel/Background/Margin]` = 10 四边
- `[InputPanel/Highlight/Margin]` = 10/10/7/7
- TextMargin = 10/10/6/6；Spacing = 3
- classicui.conf：Vertical=True（竖排，用户偏好）、UseDarkTheme=True、Theme/DarkTheme=xxd-<名>/xxd-<名>-night

## 验证

- 本机 Wayland 无截图权限：用 render.py PIL 仿真九宫格渲染，与官方预览 chip 高度比对
- 回滚：`cp ~/xxd-rime/classicui.conf.bak ~/.config/fcitx5/conf/classicui.conf && fcitx5-remote -r`
