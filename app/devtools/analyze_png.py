# -*- coding: utf-8 -*-
"""PNG 取证分析：1) 菜单开/关两图 diff；2) 3D 视图颜色构成与特殊色分布。"""
import os
from collections import Counter

import numpy as np
from PIL import Image, ImageChops

D = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"


def main() -> int:
    im1 = Image.open(os.path.join(D, "scan1_detail_full.png")).convert("RGB")
    im2 = Image.open(os.path.join(D, "scan2_menu_open.png")).convert("RGB")
    print("sizes:", im1.size, im2.size)
    if im1.size == im2.size:
        diff = ImageChops.difference(im1, im2)
        bbox = diff.getbbox()
        print("menu-open vs closed diff bbox:", bbox)
        a1 = np.asarray(im1).astype(int)
        a2 = np.asarray(im2).astype(int)
        mask = np.abs(a1 - a2).sum(axis=2) > 12
        print("changed px:", int(mask.sum()))
        if mask.any():
            ys, xs = np.where(mask)
            print("changed region: x", int(xs.min()), "-", int(xs.max()),
                  " y", int(ys.min()), "-", int(ys.max()))

    # ---- 3D 视图颜色分析 ----
    im3 = Image.open(os.path.join(D, "scan3_viewer.png")).convert("RGB")
    w, h = im3.size
    print("\nviewer size:", (w, h))
    a = np.asarray(im3).astype(int)
    flat = a.reshape(-1, 3)
    # 三通道量化到 8 的倍数做频率统计
    q = (flat // 8 * 8)
    cnt = Counter(map(tuple, q))
    print("top quantized colors:")
    for col, n in cnt.most_common(18):
        print("  ", col, n)

    # 特殊色系检测（轴色 / 点色 / 线色）
    def find(rgb, tol=26, label=""):
        m = (np.abs(a - np.array(rgb)).sum(axis=2) <= tol)
        n = int(m.sum())
        if n:
            ys, xs = np.where(m)
            print(f"[{label}] {rgb}: {n} px, bbox x {int(xs.min())}-{int(xs.max())} "
                  f"y {int(ys.min())}-{int(ys.max())}")
        else:
            print(f"[{label}] {rgb}: 0 px")
        return m

    find((0, 113, 227), 40, "point-blue (#0071E3)")
    find((198, 198, 199), 12, "line-gray (0.22 black on bg)")
    find((135, 135, 250), 30, "axis-Z blue-ish")
    find((250, 135, 136), 30, "axis-X red-ish")
    find((135, 250, 136), 30, "axis-Y green-ish")
    find((255, 149, 0), 40, "selected-orange")

    # 背景色确认
    find((245, 245, 247), 6, "viewer bg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
