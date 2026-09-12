# -*- coding: utf-8 -*-
"""线上修复验证：gzzhike.cn 上的菜单行为 + 3D 场景（headless 9225）。

前置：headless 9225（可访问外网）。
"""
import base64
import json
import sys
import time
from io import BytesIO

import numpy as np
from PIL import Image

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
BASE_URL = "https://gzzhike.cn/web-spa/cad-coord-3d/index.html"
OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"
DID = "004bb6e6-4464-4a5c-9eb3-71113640d525"

fails: list[str] = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def two_frames(c, sid):
    c.js("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(1))))", sid)
    time.sleep(0.3)


def snap(c, sid):
    two_frames(c, sid)
    r = c.cmd("Page.captureScreenshot", {"format": "png"}, session_id=sid)
    return Image.open(BytesIO(base64.b64decode(r["result"]["data"]))).convert("RGB")


def diffcount(im1, im2):
    a1 = np.asarray(im1).astype(int)
    a2 = np.asarray(im2).astype(int)
    if a1.shape != a2.shape:
        return 10 ** 9
    return int((np.abs(a1 - a2).sum(axis=2) > 12).sum())


def menu_state(c, sid):
    return json.loads(c.js(
        "(() => { const m = document.querySelector('#export-menu');"
        " const cs = getComputedStyle(m);"
        " return JSON.stringify({hidden: m.hidden, display: cs.display}); })()", sid))


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("gzzhike.cn")
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

    url = BASE_URL + "?v=" + str(int(time.time())) + "#/detail/" + DID
    c.goto(url, sid)
    ok = False
    for _ in range(120):
        if c.js("!!window.__cadViewer", sid):
            ok = True
            break
        time.sleep(0.5)
    check("线上 viewer 就绪", ok)
    if not ok:
        print("errs:", c.js("window.__errs || 'n/a'", sid))
        return 1
    time.sleep(2.0)
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.5)

    # 1) 场景无 AxesHelper
    kids = c.js("JSON.stringify(window.__cadViewer.scene.children.map(o => o.type))", sid)
    check("线上 3D 场景无 AxesHelper", "AxesHelper" not in str(kids), str(kids))

    # 2) 菜单
    s0 = menu_state(c, sid)
    check("线上初始：菜单收起", s0["display"] == "none", str(s0))
    im0 = snap(c, sid)
    c.js("document.querySelector('#btn-export').click()", sid)
    time.sleep(0.6)
    s1 = menu_state(c, sid)
    check("线上点击：菜单展开", s1["display"] == "flex", str(s1))
    im1 = snap(c, sid)
    c.js("document.body.click()", sid)
    time.sleep(0.5)
    s2 = menu_state(c, sid)
    check("线上点外：菜单收起", s2["display"] == "none", str(s2))

    d_open = diffcount(im0, im1)
    check("线上像素：展开/收起有实际视觉差异", d_open > 500, f"changed={d_open}px")

    # 3) 3D 截图存档
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.4)
    rect = json.loads(c.js(
        "(() => { const r = document.querySelector('.viewer-wrap').getBoundingClientRect();"
        " return JSON.stringify({x: Math.round(r.x), y: Math.round(r.y),"
        " w: Math.round(r.width), h: Math.round(r.height)}); })()", sid))
    two_frames(c, sid)
    r = c.cmd("Page.captureScreenshot",
              {"format": "png",
               "clip": {"x": rect["x"], "y": rect["y"],
                        "width": rect["w"], "height": rect["h"], "scale": 1}},
              session_id=sid)
    open(OUT + r"\fix_online_viewer.png", "wb").write(base64.b64decode(r["result"]["data"]))

    print("\n==== ONLINE RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}", "====")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
