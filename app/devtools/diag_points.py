# -*- coding: utf-8 -*-
"""点渲染诊断：为什么大图蓝像素偏少？

读数（顶点/材质/相机/NaN/坐标范围）+ 对照实验（临时放大点尺寸，内存态）。
用法：python app/devtools/diag_points.py
"""
import base64
import sys
import time
from io import BytesIO

import numpy as np
import PIL.Image

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"

c = CDP(port=9225)
t, sid = c.attach_page("127.0.0.1:8789")
if not sid:
    print("no tab at 8789")
    sys.exit(1)


def snap(name):
    r = c.cmd("Page.captureScreenshot", {"format": "png"}, session_id=sid)
    img = PIL.Image.open(BytesIO(base64.b64decode(r["result"]["data"]))).convert("RGB")
    img.save(f"{OUT}\\{name}")
    a = np.asarray(img).astype(int)
    bg = (a[..., 0] > 240) & (a[..., 1] > 240) & (a[..., 2] > 240)
    strict = (a[..., 2] - a[..., 0] > 30) & (a[..., 2] - a[..., 1] > 12)
    loose = (a[..., 2] > a[..., 0] + 8) & (a[..., 2] > a[..., 1] + 4)
    tint = (a[..., 2] > a[..., 0]) & (a[..., 2] > a[..., 1])
    print(f"[{name}] nonbg={int((~bg).sum())} strict_blue={int(strict.sum())} "
          f"loose_blue={int(loose.sum())} blue_tint={int(tint.sum())}")


print("== 读数 ==")
print("points verts :", c.js("window.__cadViewer.objects.pointsObj.geometry.attributes.position.count", sid))
print("lines verts  :", c.js("window.__cadViewer.objects.linesObj.geometry.attributes.position.count", sid))
print("mat size     :", c.js("window.__cadViewer.objects.pointsObj.material.size", sid))
print("visible      :", c.js("window.__cadViewer.objects.pointsObj.visible", sid))
print("frustumCulled:", c.js("window.__cadViewer.objects.pointsObj.frustumCulled", sid))
print("drawRange    :", c.js("JSON.stringify(window.__cadViewer.objects.pointsObj.geometry.drawRange)", sid))
print("NaN count    :", c.js(
    "(() => { const a = window.__cadViewer.objects.pointsObj.geometry.attributes.position.array;"
    " let n = 0; for (let i = 0; i < a.length; i++) if (!isFinite(a[i])) n++; return n; })()", sid))
print("coord min/max:", c.js(
    "(() => { const a = window.__cadViewer.objects.pointsObj.geometry.attributes.position.array;"
    " const mn = [1e30,1e30,1e30], mx = [-1e30,-1e30,-1e30];"
    " for (let i = 0; i < a.length; i += 3) for (let k = 0; k < 3; k++) {"
    "  mn[k] = Math.min(mn[k], a[i+k]); mx[k] = Math.max(mx[k], a[i+k]); }"
    " return JSON.stringify({mn, mx}); })()", sid))
print("distinct pts :", c.js(
    "(() => { const a = window.__cadViewer.objects.pointsObj.geometry.attributes.position.array;"
    " const s = new Set(); for (let i = 0; i < a.length; i += 3)"
    "  s.add(a[i].toFixed(3)+','+a[i+1].toFixed(3)+','+a[i+2].toFixed(3)); return s.size; })()", sid))

print("\n== 现状截图 ==")
snap("diag_before.png")

print("\n== 实验：size 7 → 30（内存态） ==")
c.js("window.__cadViewer.objects.pointsObj.material.size = 30", sid)
time.sleep(0.8)
snap("diag_size30.png")

print("\n== 恢复 size = 7 ==")
c.js("window.__cadViewer.objects.pointsObj.material.size = 7", sid)
time.sleep(0.5)
snap("diag_restored.png")
print("done")
