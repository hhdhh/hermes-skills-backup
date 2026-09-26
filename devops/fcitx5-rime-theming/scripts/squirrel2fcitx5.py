#!/usr/bin/env python3
"""squirrel(Rime macOS) 配色 YAML → fcitx5 主题批量转换器。

- 解析 xxd.squirrel.yaml 式的 preset_color_schemes 块
- 0xBBGGRR / 0xAABBGGRR → #RRGGBB / #AARRGGBB
- 每套生成 theme.conf + 圆角九宫格 PNG（panel/highlight, @1x @2x）
- 需依赖：Pillow

用法:
  python3 squirrel2fcitx5.py --src xxd.squirrel.yaml --dest ~/.local/share/fcitx5/themes
  # 备选参数: --panel-radius 10 --chip-radius 6 --prefix xxd-
"""
import argparse
import os
import re
import sys

from PIL import Image, ImageDraw

# ---------- squirrel parsing ----------

def parse_schemes(path):
    """preset_color_schemes 下的缩进块解析（4 空格 scheme 名 / 6 空格键值）。"""
    schemes, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^    (\w+):\s*$", line)
            if m:
                cur = m.group(1)
                schemes[cur] = {}
                continue
            m = re.match(r"^      (\w+):\s*(\S+)", line)
            if m and cur:
                schemes[cur][m.group(1)] = m.group(2)
    return schemes

def conv_color(v):
    """squirrel 0xBBGGRR / 0xAABBGGRR -> fcitx5 #RRGGBB / #AARRGGBB, else None."""
    m = re.fullmatch(r"0[xX]([0-9A-Fa-f]+)", v.strip())
    if not m:
        return None
    h = m.group(1).upper()
    if len(h) == 8:
        return f"#{h[0:2]}{h[6:8]}{h[4:6]}{h[2:4]}"
    if len(h) == 6:
        return f"#{h[6:8]}{h[4:6]}{h[2:4]}"
    return None

def hx(col):
    col = col.lstrip("#")
    if len(col) == 8:
        col = col[2:]
    return (int(col[0:2], 16), int(col[2:4], 16), int(col[4:6], 16), 255)

# ---------- 9-patch PNG ----------

def rounded(size, radius, fill, outline=None, width=2, scale=1):
    w, h = size[0] * scale, size[1] * scale
    r, lw = radius * scale, max(1, width * scale)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if outline:
        d.rounded_rectangle([lw // 2, lw // 2, w - 1 - lw // 2, h - 1 - lw // 2],
                            radius=r, fill=fill, outline=outline, width=lw)
    else:
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=fill)
    return img

def gen_assets(s, d, panel_r, chip_r):
    bg = hx(conv_color(s["back_color"]))
    border = hx(conv_color(s.get("border_color") or s["back_color"]))
    chip = hx(conv_color(s["hilited_candidate_back_color"]))
    for scale, suffix in ((1, ""), (2, "@2x")):
        rounded((48, 48), panel_r, bg, outline=border, width=2, scale=scale) \
            .save(os.path.join(d, f"panel{suffix}.png"))
        rounded((48, 32), chip_r, chip, scale=scale) \
            .save(os.path.join(d, f"highlight{suffix}.png"))

# ---------- theme.conf ----------
PANEL_R = 10
CHIP_R = 6

def theme_conf(s, name, desc, panel_r, chip_r):
    def c(key, fallback=None):
        col = conv_color(s.get(key, ""))
        if col is None and fallback:
            col = conv_color(s.get(fallback, ""))
        return col

    border = c("border_color", "back_color")
    normal = c("candidate_text_color", "text_color")
    hl_cand = c("hilited_candidate_text_color", "hilited_candidate_label_color")
    hl_lbl = c("hilited_candidate_label_color", "hilited_candidate_text_color")
    hl_cmt = c("hilited_comment_text_color", "comment_text_color")
    hl_pre = c("hilited_text_color", "text_color")
    comment = c("comment_text_color", "label_color")

    return f"""[Metadata]
Name={name}
Name[zh_CN]={desc}
Version=1
Author=squirrel2fcitx5
Description={desc}
ScaleWithDPI=True

[InputPanel]
NormalColor={normal}
HighlightCandidateColor={hl_cand}
HighlightCandidateLabelColor={hl_lbl}
CandidateCommentColor={comment}
HighlightCandidateCommentColor={hl_cmt}
HighlightColor={hl_pre}
Spacing=3

[InputPanel/TextMargin]
Left=10
Right=10
Top=6
Bottom=6

[InputPanel/Background]
Image=panel.png
Color={c('back_color')}
BorderColor={border}
BorderWidth=2

[InputPanel/Background/Margin]
# = panel 圆角半径（九宫格切割线）
Left={panel_r}
Right={panel_r}
Top={panel_r}
Bottom={panel_r}

[InputPanel/Highlight]
Image=highlight.png
Color={c('hilited_candidate_back_color')}

[InputPanel/Highlight/Margin]
# = chip 圆角半径（九宫格切割线 + 外扩量）
Left={chip_r}
Right={chip_r}
Top={chip_r}
Bottom={chip_r}

[InputPanel/Highlight/ClickMargin]
Left={chip_r}
Right={chip_r}
Top={chip_r}
Bottom={chip_r}

[Menu]
NormalColor={normal}
HighlightCandidateColor={hl_cand}

[Menu/Background]
Image=panel.png
Color={c('back_color')}
BorderColor={border}
BorderWidth=2

[Menu/Background/Margin]
Left={panel_r}
Right={panel_r}
Top={panel_r}
Bottom={panel_r}

[Menu/ContentMargin]
Left=6
Right=6
Top=6
Bottom=6

[Menu/Highlight]
Image=highlight.png
Color={c('hilited_candidate_back_color')}

[Menu/Highlight/Margin]
Left={chip_r}
Right={chip_r}
Top={chip_r}
Bottom={chip_r}
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dest", default=os.path.expanduser("~/.local/share/fcitx5/themes"))
    ap.add_argument("--prefix", default="xxd-")
    ap.add_argument("--panel-radius", type=int, default=PANEL_R)
    ap.add_argument("--chip-radius", type=int, default=CHIP_R)
    args = ap.parse_args()

    schemes = parse_schemes(args.src)
    if not schemes:
        sys.exit("no preset_color_schemes parsed — check indentation (4/6 spaces)")

    made = 0
    for key, s in sorted(schemes.items()):
        is_night = key.endswith("_night")
        base = (key[:-6] if is_night else key).removeprefix("xxd_")
        dirname = args.prefix + base.replace("_", "-") + ("-night" if is_night else "")
        zh = s.get("name", base).replace("xxd", "").strip()
        d = os.path.join(args.dest, dirname)
        os.makedirs(d, exist_ok=True)
        gen_assets(s, d, args.panel_radius, args.chip_radius)
        with open(os.path.join(d, "theme.conf"), "w", encoding="utf-8") as f:
            f.write(theme_conf(s, dirname, zh, args.panel_radius, args.chip_radius))
        made += 1
        print(f"  {dirname}")
    print(f"generated {made} themes -> {args.dest}")
    print("activate: edit ~/.config/fcitx5/conf/classicui.conf Theme=/DarkTheme= (backup first), then fcitx5-remote -r")

if __name__ == "__main__":
    main()
