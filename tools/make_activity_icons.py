"""生成两枚活动道具图标（官方未放出独立图标，只能照着配色自绘）。

产物：
  image/道具图片/天工石.png   —— 青玉矿石 + 金纹，天宫宝库抽奖道具
  image/道具图片/迷迭珠.png   —— 紫玉珠 + 金环，梦之回廊抽奖道具

尺寸与项目里其它道具图一致（256×256，RGBA）。纯 PIL，无第三方依赖。
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "image" / "道具图片"
SS = 4  # 超采样倍数，先画 1024 再缩，边缘才不毛躁
SIZE = 256


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def gradient_fill(
    mask: Image.Image,
    p0: tuple[float, float],
    p1: tuple[float, float],
    c0: tuple[int, int, int],
    c1: tuple[int, int, int],
) -> Image.Image:
    """沿 p0→p1 做线性渐变，只保留 mask 内的部分。"""
    w, h = mask.size
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    denom = dx * dx + dy * dy or 1.0
    data = bytearray()
    src = mask.load()
    for y in range(h):
        for x in range(w):
            if src[x, y] == 0:
                data.extend((0, 0, 0, 0))
                continue
            t = ((x - p0[0]) * dx + (y - p0[1]) * dy) / denom
            r, g, b = lerp(c0, c1, t)
            data.extend((r, g, b, src[x, y]))
    return Image.frombytes("RGBA", (w, h), bytes(data))


def glow(img: Image.Image, radius: int, strength: float = 0.55) -> Image.Image:
    """把图自身模糊一份叠在下面，做外发光。"""
    halo = img.filter(ImageFilter.GaussianBlur(radius))
    alpha = halo.split()[3].point(lambda v: int(v * strength))
    halo.putalpha(alpha)
    return halo


def draw_shadow(canvas: Image.Image, box: tuple[int, int, int, int], blur: int) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=(0, 0, 0, 150))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def celestial_stone() -> Image.Image:
    size = SIZE * SS
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_shadow(canvas, (int(size * 0.2), int(size * 0.78), int(size * 0.82), int(size * 0.94)), size // 22)
    draw_shadow(canvas, (int(size * 0.16), int(size * 0.12), int(size * 0.88), int(size * 0.88)), size // 40)

    # 不规则矿石轮廓
    pts = [
        (0.50, 0.055), (0.74, 0.145), (0.925, 0.375), (0.905, 0.665),
        (0.735, 0.895), (0.470, 0.955), (0.215, 0.860), (0.075, 0.620),
        (0.115, 0.330), (0.300, 0.120),
    ]
    polygon = [(x * size, y * size) for x, y in pts]

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    body = gradient_fill(
        mask,
        (size * 0.2, size * 0.1),
        (size * 0.85, size * 0.95),
        (196, 232, 246),   # 冰青高光
        (34, 66, 96),      # 深海青
    )

    # 内部棱面：几条从顶角散开的面，靠亮度差塑造体积
    facets = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(facets)
    fd.polygon([polygon[0], (size * 0.355, size * 0.585), (size * 0.50, size * 0.34)], fill=(255, 255, 255, 38))
    fd.polygon([(size * 0.925, size * 0.375), (size * 0.62, size * 0.70), (size * 0.905, size * 0.665)], fill=(255, 255, 255, 26))
    fd.polygon([(size * 0.735, size * 0.895), (size * 0.47, size * 0.60), (size * 0.215, size * 0.860)], fill=(0, 0, 0, 42))
    facets.putalpha(Image.composite(facets.split()[3], Image.new("L", (size, size), 0), mask))
    body.alpha_composite(facets)

    # 金边：先画粗一圈再叠细一圈，像嵌进去的金线
    edge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    ed.line(polygon + [polygon[0]], fill=(232, 196, 106, 190), width=int(size * 0.020), joint="curve")
    edge.putalpha(Image.composite(edge.split()[3], Image.new("L", (size, size), 0), mask))
    body.alpha_composite(edge)

    # 星纹：中心四角星 + 两道细纹
    star = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(star)
    cx, cy, r = size * 0.50, size * 0.50, size * 0.155
    sd.polygon(
        [
            (cx, cy - r), (cx + r * 0.24, cy - r * 0.24), (cx + r, cy),
            (cx + r * 0.24, cy + r * 0.24), (cx, cy + r), (cx - r * 0.24, cy + r * 0.24),
            (cx - r, cy), (cx - r * 0.24, cy - r * 0.24),
        ],
        fill=(255, 240, 198, 225),
    )
    sd.arc(
        (size * 0.24, size * 0.24, size * 0.76, size * 0.76),
        start=205, end=330, fill=(246, 220, 150, 165), width=int(size * 0.010),
    )
    star.putalpha(Image.composite(star.split()[3], Image.new("L", (size, size), 0), mask))
    body.alpha_composite(glow(star, size // 42, 0.9))
    body.alpha_composite(star)

    canvas.alpha_composite(body)
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def dream_bead() -> Image.Image:
    size = SIZE * SS
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_shadow(canvas, (int(size * 0.18), int(size * 0.79), int(size * 0.82), int(size * 0.95)), size // 20)
    draw_shadow(canvas, (int(size * 0.14), int(size * 0.12), int(size * 0.86), int(size * 0.88)), size // 34)

    box = (int(size * 0.10), int(size * 0.10), int(size * 0.90), int(size * 0.90))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    body = gradient_fill(
        mask,
        (size * 0.24, size * 0.18),
        (size * 0.82, size * 0.90),
        (226, 198, 248),   # 珠光浅紫
        (58, 30, 96),      # 深紫
    )

    # 迷迭花纹：两圈偏心金环 + 一粒中心
    rings = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rings)
    rd.arc((size * 0.22, size * 0.20, size * 0.80, size * 0.78), start=25, end=250,
           fill=(244, 220, 152, 205), width=int(size * 0.014))
    rd.arc((size * 0.30, size * 0.30, size * 0.72, size * 0.70), start=160, end=20,
           fill=(244, 220, 152, 150), width=int(size * 0.010))
    rd.ellipse((size * 0.455, size * 0.455, size * 0.545, size * 0.545), fill=(250, 232, 176, 215))
    rings.putalpha(Image.composite(rings.split()[3], Image.new("L", (size, size), 0), mask))
    body.alpha_composite(rings)

    # 高光
    hi = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(hi).ellipse(
        (size * 0.275, size * 0.215, size * 0.475, size * 0.375), fill=(255, 255, 255, 165)
    )
    hi = hi.filter(ImageFilter.GaussianBlur(size // 60))
    hi.putalpha(Image.composite(hi.split()[3], Image.new("L", (size, size), 0), mask))
    body.alpha_composite(hi)

    canvas.alpha_composite(body)
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("天工石", celestial_stone), ("迷迭珠", dream_bead)):
        path = OUT / f"{name}.png"
        fn().save(path)
        print(f"✓ {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
