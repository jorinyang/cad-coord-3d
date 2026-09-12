# -*- coding: utf-8 -*-
"""PNG 差异比较：python cmp_png.py a.png b.png [diff_crop_out.png]"""
import sys

import numpy as np
from PIL import Image

a = Image.open(sys.argv[1]).convert("RGB")
b = Image.open(sys.argv[2]).convert("RGB")
print("sizes:", a.size, b.size)
if a.size != b.size:
    print("size mismatch — cannot diff")
    raise SystemExit(1)

aa = np.asarray(a).astype(int)
bb = np.asarray(b).astype(int)
m = np.abs(aa - bb).sum(axis=2) > 12
print("changed px:", int(m.sum()))
if m.any():
    ys, xs = np.where(m)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    print(f"changed bbox: x {x0}-{x1}  y {y0}-{y1}  ({x1-x0+1}x{y1-y0+1})")
    if len(sys.argv) > 3:
        crop = a.crop((x0, y0, x1 + 1, y1 + 1))
        crop.save(sys.argv[3])
        print("saved crop of a:", sys.argv[3])
    # 差异像素的颜色采样（前 10 个不同的）
    idx = np.argwhere(m)[:2000]
    from collections import Counter
    c1 = Counter(tuple(aa[y, x]) for y, x in idx)
    c2 = Counter(tuple(bb[y, x]) for y, x in idx)
    print("top colors in A at diff:", c1.most_common(5))
    print("top colors in B at diff:", c2.most_common(5))
