#!/usr/bin/env python3
"""Convert a Rime squirrel color-scheme YAML into fcitx5 themes.

Usage: python3 squirrel2fcitx5.py <squirrel.yaml> <output_themes_dir>
Generates one theme dir per scheme (light + *_night), each with theme.conf
and 9-patch rounded PNGs (panel.png/highlight.png + @2x).
Requires: Pillow. Colors in squirrel YAML are 0xBBGGRR (8-digit: 0xAABBGGRR).
"""
import os
import re
import sys

from PIL import Image, ImageDraw

SRC = sys.argv[1] if len(sys.argv) > 1 else "xxd.squirrel.yaml"
DEST = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/.local/share/fcitx5/themes")
PREFIX = "xxd-"  # scheme key xxd_foo[_night] -> dir xxd-foo[-night]


def conv_color(v):
    v = v.strip()
    m = re.fullmatch(r"0[xX]([0-9A-Fa-f]+)", v)
    if not m:
        return None
    h = m.group(1).upper()
    if len(h) == 8:  # AABBGGRR -> AARRGGBB
        a, b, g, r = h[0:2], h[2:4], h[4:6], h[6:8]
        return f"#{a}{r}{g}{b}"
    if len(h) == 6:  # BBGGRR -> RRGGBB
        b, g, r = h[0:2], h[2:4], h[4:6]
        return f"#{r}{g}{b}"
    return None


def parse(path):
    """Parse top-level scheme blocks: 4-space key, 6-space fields."""
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


def hx(col):
    col = col.lstrip("#")
    if len(col) == 8:
        col = col[2:]
    return (int(col[0:2], 16), int(col[2:4], 16), int(col[4:6], 16), 255)


def rounded(size, radius, fill, outline=None, width=2, scale=1):
    w, h = size[0] * scale, size[1] * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if outline:
        d.rounded_rectangle([1, 1, w - 2, h - 2], radius=radius * scale,
                            fill=fill, outline=outline, width=max(1, width * scale))
    else:
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius * scale, fill=fill)
    return img


def gen_assets(s, d):
    bg = hx(conv_color(s["back_color"]))
    border = hx(conv_color(s.get("border_color") or s["back_color"]))
    chip = hx(conv_color(s["hilited_candidate_back_color"]))
    for scale, suffix in ((1, ""), (2, "@2x")):
        rounded((48, 48), 10, bg, outline=border, width=2, scale=scale).save(
            os.path.join(d, f"panel{suffix}.png"))
        rounded((48, 32), 6, chip, scale=scale).save(
            os.path.join(d, f"highlight{suffix}.png"))


def theme_conf(s, name, desc):
    def c(key, fallback=None):
        col = conv_color(s.get(key, ""))
        if col is None and fallback:
            col = conv_color(s.get(fallback, ""))
        return col

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
BorderColor={c('border_color', 'back_color')}
BorderWidth=2

[InputPanel/Background/Margin]
Left=10
Right=10
Top=10
Bottom=10

[InputPanel/Highlight]
Image=highlight.png
Color={c('hilited_candidate_back_color')}

[InputPanel/Highlight/Margin]
Left=10
Right=10
Top=7
Bottom=7

[InputPanel/Highlight/ClickMargin]
Left=10
Right=10
Top=7
Bottom=7

[Menu]
NormalColor={normal}
HighlightCandidateColor={hl_cand}

[Menu/Background]
Image=panel.png
Color={c('back_color')}
BorderColor={c('border_color', 'back_color')}
BorderWidth=2

[Menu/Background/Margin]
Left=10
Right=10
Top=10
Bottom=10

[Menu/ContentMargin]
Left=6
Right=6
Top=6
Bottom=6

[Menu/Highlight]
Image=highlight.png
Color={c('hilited_candidate_back_color')}

[Menu/Highlight/Margin]
Left=10
Right=10
Top=7
Bottom=7
"""


def main():
    schemes = parse(SRC)
    for key, s in sorted(schemes.items()):
        is_night = key.endswith("_night")
        base = (key[:-6] if is_night else key).removeprefix("xxd_")
        dirname = PREFIX + base.replace("_", "-") + ("-night" if is_night else "")
        zh = s.get("name", base).replace("xxd", "").strip()
        desc = f"{zh}" + ("·夜" if is_night else "")
        d = os.path.join(DEST, dirname)
        os.makedirs(d, exist_ok=True)
        gen_assets(s, d)
        with open(os.path.join(d, "theme.conf"), "w", encoding="utf-8") as f:
            f.write(theme_conf(s, dirname, desc))
    print(f"generated {len(schemes)} themes under {DEST}")
    print("next: set Theme=/DarkTheme= in ~/.config/fcitx5/conf/classicui.conf, then fcitx5-remote -r")


if __name__ == "__main__":
    main()
