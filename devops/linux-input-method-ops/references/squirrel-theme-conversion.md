# squirrel → fcitx5 主题转换细节

## 颜色格式

- squirrel/Windows 序：`0xBBGGRR`（8 位则 `0xAABBGGRR`，前两位是 alpha）
- fcitx5：`#RRGGBB`（带 alpha 用 `#AARRGGBB`）
- 转换：字节序反转。squirrel YAML 行内注释里的 `#RRGGBB` 是人类可读提示，别拿来当解析源。

## 字段映射

| squirrel | fcitx5 theme.conf |
|---|---|
| back_color | [InputPanel/Background] Color |
| border_color | BorderColor |
| candidate_text_color | [InputPanel] NormalColor |
| comment_text_color | CandidateCommentColor |
| label_color | （用 comment 色近似）|
| text_color / hilited_text_color | HighlightColor（输入串前景）|
| hilited_candidate_text_color | HighlightCandidateColor |
| hilited_candidate_label_color | HighlightCandidateLabelColor |
| hilited_comment_text_color | HighlightCandidateCommentColor |
| hilited_candidate_back_color | [InputPanel/Highlight] Color（选中块 = 品牌原色）|

## 圆角九宫格 PNG（classicui 无 Radius 时的唯一圆角方案）

- `panel.png`：48×48，r10，bg 填充 + border 色 2px 描边
- `highlight.png`：48×32，r6，选中色填充无描边
- 各配 `@2x` 版（尺寸×2，圆角×2）；theme.conf 用 `Image=panel.png` 指定
- `[InputPanel/Background/Margin]` 10/10/10/10 = 九宫格切割线（≥圆角半径，否则角被拉伸变形）

## 边距（实测对齐原版预览：选中块高 51px、文字上下留白≈8.5px）

- TextMargin L/R=10 T/B=6；Highlight Margin L/R=10 T/B=7；Spacing=3
- 选中块高度 = 文字高 + TextMargin(T+B) + HighlightMargin(T+B)，调"扁/胖"改这两组 Margin

## 几何验证法（拿不到屏幕截图时）

1. 官方预览图量化：PIL 扫描品牌色像素 bbox → 得选中块宽高/内边距/圆角（tol≈12）
2. 自渲染复算：按 theme.cpp `paintTile()` 九宫格算法（角 1:1、边/心拉伸）PIL 模拟渲染，比对 bbox
3. 两边几何一致才算对齐，不靠目测

## fcitx5 源码定位（行为有疑先读源码）

- `src/ui/classic/theme.cpp` `paintTile()` — 九宫格绘制、Margin 语义
- `src/ui/classic/inputwindow.cpp` — 选中块绘制：宽度 = candidateWidth（横排）或整行（竖排+fullWidthHighlight）；外扩 highlightMargin；`FullWidthHighlight` 仅竖排生效
- raw.githubusercontent.com 直连 curl 可拉（--retry 3）；确认二进制能力用 `strings libclassicui.so`
