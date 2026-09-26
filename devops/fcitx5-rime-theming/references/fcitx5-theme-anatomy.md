# fcitx5 theme.conf 解剖 + 渲染算法摘要

源码依据：fcitx5 `src/ui/classic/theme.cpp`、`inputwindow.cpp`（上游 master，5.1.x 一致）。

## 1. theme.conf 关键键位（InputPanel）

| 键 | 作用 |
|---|---|
| `NormalColor` | 非选中候选字 |
| `HighlightCandidateColor` | 选中候选字 |
| `HighlightCandidateLabelColor` | 选中候选序号 |
| `CandidateCommentColor` / `HighlightCandidateCommentColor` | 注释/选中注释 |
| `HighlightColor` | 输入串(preedit)文字色 |
| `HighlightBackgroundColor` | 输入串背景色 |
| `Spacing` | 候选间距 |
| `[InputPanel/TextMargin]` | 文字块四周留白 |
| `[InputPanel/Background] Image=panel.png Color= BorderColor= BorderWidth=` | 面板（Image 优先，Color 兜底） |
| `[InputPanel/Background/Margin]` | 面板九宫格切割线 |
| `[InputPanel/Highlight] Image=highlight.png Color=` | 选中块 |
| `[InputPanel/Highlight/Margin]` | 选中块九宫格切割线 + 外扩量 |
| `Menu` 段镜像 InputPanel（菜单） | |

字号/字体在 **classicui.conf**（`Font=`），不在 theme.conf。

## 2. 九宫格绘制（theme.cpp paintTile）

- 源图按 `[0, margin, w-margin, w] × [0, margin, h-margin, h]` 切 3×3；
- 4 角 1:1 拷贝（不缩放）；上下边横向拉伸、左右边纵向拉伸、中心双向拉伸；
- 目标区域同理切网格，角落贴角落、边贴边；
- **结论：margin 就是圆角半径。** margin > 半径 → 圆角被拉扁；margin < 半径 → 圆角被拉肥。

## 3. 选中块几何（inputwindow.cpp）

```
块位置 = 候选文字 bbox - highlightMargin(左,上)
块尺寸 = 文字尺寸 + highlightMargin(全方向)
if (FullWidthHighlight && 竖排) 块宽 = 面板内行宽   // 整行圆角条
横排时块宽 = 单个候选词宽    // 收缩窄条
```

- `FullWidthHighlight` 默认 **true**；横排模式下它不生效（块收缩）。
- 想还原 macOS squirrel 式整行色块 → **竖排 + FullWidthHighlight=true**。

## 4. squirrel → fcitx5 颜色换算

| squirrel | 含义 | fcitx5 |
|---|---|---|
| `0xBBGGRR` | BGR 字节序 | `#RRGGBB` |
| `0xAABBGGRR` | 带透明 BGR | `#AARRGGBB`（alpha 前置，RGB 换序）|

常用字段映射：`back_color→Background/Color`、`border_color→BorderColor`、`candidate_text_color→NormalColor`、`hilited_candidate_text_color→HighlightCandidateColor`、`hilited_candidate_label_color→HighlightCandidateLabelColor`、`comment_text_color→CandidateCommentColor`、`hilited_comment_text_color→HighlightCandidateCommentColor`、`text_color/hilited_text_color→HighlightColor`、`hilited_candidate_back_color→Highlight/Color + highlight.png 底色`。

## 5. 几何测量配方（无截屏验证）

1. 预览图颜色聚类：目标色 `near(px, target, tol≤14)` 全图扫 bbox → 选中块尺寸/偏移；
2. 角半径：从块左上角向右逐列扫目标色首个出现的 y 偏移，偏移≤1px 时的列距即半径；
3. 文字高：块内非块色且非背景色的行集合；块高−文字高 ≈ 上下 padding×2；
4. PIL 模拟渲染（九宫格算法同 §2）后重测，与官方预览数值对齐（±1px）即通过。

## 6. 上游源码获取

```
https://raw.githubusercontent.com/fcitx/fcitx5/master/src/ui/classic/theme.cpp
https://raw.githubusercontent.com/fcitx/fcitx5/master/src/ui/classic/inputwindow.cpp
```
直连超时 → `-x socks5h://127.0.0.1:7890`（http 代理 7890 对 raw.githubusercontent 可能 exit 35，socks5h 稳）。
