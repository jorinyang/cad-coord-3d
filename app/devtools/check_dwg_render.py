# -*- coding: utf-8 -*-
"""DWG 转换图 3D 渲染检查（3846 点真实工程图）。

验证 DWG → DXF → 解析 → 入库 → 3D 展示 全链路最后一环。
前置：headless 9225；local 模式需 8789 前端在跑。
用法：python app/devtools/check_dwg_render.py local|online
"""
import base64
import json
import re
import sys
import time
from io import BytesIO

import numpy as np
from PIL import Image

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
DID = "07cf015e-1c0b-4da3-940e-c7b6ad7875d1"
EXPECT_POINTS = 3846
EXPECT_LINES = 3736
OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"

TARGET = (sys.argv[1] if len(sys.argv) > 1 else "local").lower()
if TARGET == "online":
    BASE = "https://gzzhike.cn/web-spa/cad-coord-3d/index.html"
    ATTACH = "gzzhike.cn"
else:
    BASE = "http://127.0.0.1:8789/"
    ATTACH = "127.0.0.1:8789"

fails: list[str] = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page(ATTACH)
    if not sid:
        print("cannot attach; creating new tab")
        r = c.cmd("Target.createTarget", {"url": "about:blank"})
        tid = r["result"]["targetId"]
        r2 = c.cmd("Target.attachToTarget", {"targetId": tid, "flatten": True})
        sid = r2["result"]["sessionId"]
    c.cmd("Page.bringToFront", session_id=sid)
    c.cmd("Network.enable", session_id=sid)
    c.cmd("Network.setCacheDisabled", {"cacheDisabled": True}, session_id=sid)
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)

    url = BASE + "?v=" + str(int(time.time())) + "#/detail/" + DID
    c.goto(url, sid)
    ok = False
    for _ in range(120):
        if c.js("!!window.__cadViewer && window.__cadViewer.pointCount > 0", sid):
            ok = True
            break
        time.sleep(0.5)
    check(f"{TARGET} viewer 就绪", ok)
    if not ok:
        print("page state:", str(c.js("document.body.innerText.slice(0, 300)", sid)))
        return 1
    time.sleep(3.0)  # 大图多给渲染时间

    pc = c.js("window.__cadViewer.pointCount", sid)
    check(f"点数 = {EXPECT_POINTS}", pc == EXPECT_POINTS, f"pointCount={pc}")
    lv = c.js("window.__cadViewer.objects.linesObj.geometry.attributes.position.count", sid)
    check(f"线数 = {EXPECT_LINES}", lv == EXPECT_LINES * 2, f"line vertices={lv}")
    pv = c.js("window.__cadViewer.objects.pointsObj.geometry.attributes.position.count", sid)
    check(f"点云顶点 = {EXPECT_POINTS}", pv == EXPECT_POINTS, f"point vertices={pv}")

    c.js("window.__cadViewer.fitView()", sid)
    time.sleep(0.8)
    c.js("window.__cadViewer.select(100)", sid)
    time.sleep(0.6)
    idx = c.js("window.__cadViewer.selectedIndex", sid)
    info = str(c.js("document.querySelector('.pick-info')?.innerText?.replace(/\\n/g, ' | ') || '(none)'", sid))
    check("选中第 100 个点", idx == 100, f"selectedIndex={idx} | {info}")

    rect = json.loads(c.js(
        "(() => { const r = document.querySelector('.viewer-wrap').getBoundingClientRect();"
        " return JSON.stringify({x: Math.round(r.x), y: Math.round(r.y),"
        " w: Math.round(r.width), h: Math.round(r.height)}); })()", sid))
    c.js("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(1))))", sid)
    time.sleep(0.3)
    r = c.cmd("Page.captureScreenshot",
              {"format": "png",
               "clip": {"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"], "scale": 1}},
              session_id=sid)
    img = Image.open(BytesIO(base64.b64decode(r["result"]["data"]))).convert("RGB")
    path = f"{OUT}\\dwg_verify_{TARGET}_viewer.png"
    img.save(path)
    print(f"   saved {path}")

    a = np.asarray(img).astype(int)
    nonbg = int(((a[..., 0] < 240) | (a[..., 1] < 240) | (a[..., 2] < 240)).sum())
    check("画面含图元像素", nonbg > 2000, f"nonbg_px={nonbg}")
    blue = (a[..., 2] - a[..., 0] > 30) & (a[..., 2] - a[..., 1] > 12)
    n_blue = int(blue.sum())
    check("3D 画面含蓝色点像素", n_blue > 800, f"blue_px={n_blue}")
    if n_blue:
        ys, xs = np.where(blue)
        bw, bh = int(xs.max() - xs.min()), int(ys.max() - ys.min())
        check("点分布横纵铺展", bw > rect["w"] * 0.25 and bh > rect["h"] * 0.25,
              f"bbox {bw}x{bh} of {rect['w']}x{rect['h']}")

    print("\n==== RESULT:", "ALL PASS ✓" if not fails else f"FAILURES: {fails}", "====")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
