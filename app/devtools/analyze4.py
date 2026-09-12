# -*- coding: utf-8 -*-
"""像素级 ASCII 取证：把 3D 视图/轴区域"画"成字符画 + 彩色像素定位。"""
import numpy as np
from PIL import Image

D = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"


def classify(px):
    r, g, b = int(px[0]), int(px[1]), int(px[2])
    avg = (r + g + b) / 3
    # 彩色判定
    if r - g > 20 and r - b > 20:
        return "R"
    if g - r > 20 and g - b > 20:
        return "G"
    if b - r > 20 and b - g > 12:
        return "B"
    if g - r > 12 and b - r > 12:
        return "C"  # cyan-ish
    if r - b > 20 and g - b > 20:
        return "Y"
    # 灰阶
    if avg > 238:
        return " "
    if avg > 205:
        return "."
    if avg > 150:
        return ":"
    return "#"


def ascii_art(path, block=2, maxw=140):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int)
    h, w = a.shape[:2]
    lines = []
    for y in range(0, h - block + 1, block):
        row = []
        for x in range(0, w - block + 1, block):
            blk = a[y:y + block, x:x + block].reshape(-1, 3)
            chars = [classify(p) for p in blk]
            # 优先级：彩色 > 深灰 > 浅灰 > 背景
            for pref in "RGBCY#:.":
                if pref in chars:
                    row.append(pref)
                    break
            else:
                row.append(" ")
        lines.append("".join(row)[:maxw])
    return lines


print("##### axesDiff.png (diff crop of base; block=2) #####")
for ln in ascii_art(D + r"\axesDiff.png", block=2):
    print(ln)

print()
print("##### scan3d_base.png full viewer (block=6) #####")
for ln in ascii_art(D + r"\scan3d_base.png", block=6, maxw=136):
    print(ln)

# 黄绿像素定位（nolines）
a = np.asarray(Image.open(D + r"\scan3d_nolines.png").convert("RGB")).astype(int)
m = (np.abs(a - np.array([231, 248, 192])).sum(axis=2) < 80)
ys, xs = np.where(m)
print("\nyellow-green px in nolines:", len(xs))
for x, y in list(zip(xs, ys))[:20]:
    print(f"   ({x},{y}) color={tuple(a[y, x])}")

# base 全图彩色像素统计（分色系）
a = np.asarray(Image.open(D + r"\scan3d_base.png").convert("RGB")).astype(int)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
cats = {
    "R-dom": (r - g > 20) & (r - b > 20),
    "G-dom": (g - r > 20) & (g - b > 20),
    "B-dom": (b - r > 20) & (b - g > 12),
    "C-ish": (g - r > 12) & (b - r > 12) & ~((b - r > 20) & (b - g > 12)) & ~((g - r > 20) & (g - b > 20)),
    "Y-dom": (r - b > 20) & (g - b > 20) & (np.abs(r - g) < 40),
}
print("\n=== base colored px summary ===")
for k, mm in cats.items():
    n = int(mm.sum())
    if n:
        ys, xs = np.where(mm)
        print(f"{k}: {n}px  x{xs.min()}-{xs.max()} y{ys.min()}-{ys.max()}")
    else:
        print(f"{k}: 0")
