# -*- coding: utf-8 -*-
"""修复验证：菜单可收起（元素层级+像素断言） + 3D 无坐标轴（场景断言）。

前置：headless 9225、前端 8789。
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
FRONT = "http://127.0.0.1:8789/"
OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"
DID = "004bb6e6-4464-4a5c-9eb3-71113640d525"

fails: list[str] = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def two_frames(c, sid):
    c.js("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(1))))", sid)
    time.sleep(0.25)


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
        " const cs = getComputedStyle(m); const r = m.getBoundingClientRect();"
        " return JSON.stringify({hidden: m.hidden, display: cs.display,"
        " w: Math.round(r.width), h: Math.round(r.height)}); })()", sid))


def menu_hit(c, sid):
    """菜单打开时元素层级命中检查（修复前此点命中菜单但视觉无差异）。"""
    return c.js(
        "(() => { const el = document.elementFromPoint(767, 247);"
        " return el && el.closest('#export-menu') ? 'menu' : (el ? el.tagName : 'none'); })()", sid)


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("127.0.0.1:8789")
    if not sid:
        print("cannot attach"); return 1
    c.cmd("Page.bringToFront", session_id=sid)
    c.cmd("Network.enable", session_id=sid)
    c.cmd("Network.setCacheDisabled", {"cacheDisabled": True}, session_id=sid)
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)

    url = FRONT + "?fix=" + str(int(time.time())) + "#/detail/" + DID
    c.goto(url, sid)
    ok = False
    for _ in range(90):
        if c.js("!!window.__cadViewer", sid):
            ok = True
            break
        time.sleep(0.5)
    check("viewer 就绪", ok)
    if not ok:
        return 1
    time.sleep(1.5)
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.4)

    # ---- 1) 3D 场景：无 AxesHelper ----
    kids = c.js("JSON.stringify(window.__cadViewer.scene.children.map(o => o.type))", sid)
    check("3D 场景无 AxesHelper（无悬空线来源）", "AxesHelper" not in str(kids), str(kids))
    check("3D 场景含 Points + LineSegments", "Points" in str(kids) and "LineSegments" in str(kids))

    # ---- 2) 菜单三态 ----
    s0 = menu_state(c, sid)
    check("初始：菜单收起（display:none）", s0["display"] == "none", str(s0))
    hit0 = menu_hit(c, sid)
    check("初始：该点不命中菜单", hit0 != "menu", f"hit={hit0}")
    im_closed = snap(c, sid)

    c.js("document.querySelector('#btn-export').click()", sid)
    time.sleep(0.6)
    s1 = menu_state(c, sid)
    check("点击后：菜单展开（display:flex）", s1["display"] == "flex" and s1["h"] > 50, str(s1))
    hit1 = menu_hit(c, sid)
    check("展开：该点命中菜单项", hit1 == "menu", f"hit={hit1}")
    im_open = snap(c, sid)

    c.js("document.body.click()", sid)
    time.sleep(0.5)
    s2 = menu_state(c, sid)
    check("点外部：菜单收起", s2["display"] == "none", str(s2))
    im_closed2 = snap(c, sid)

    # toggle 复测
    c.js("document.querySelector('#btn-export').click()", sid)
    time.sleep(0.4)
    d1 = menu_state(c, sid)["display"]
    c.js("document.querySelector('#btn-export').click()", sid)
    time.sleep(0.4)
    d2 = menu_state(c, sid)["display"]
    check("二次开关 toggle 正常", d1 == "flex" and d2 == "none", f"{d1} -> {d2}")

    # ---- 3) 像素断言 ----
    d_open = diffcount(im_closed, im_open)
    check("像素：展开时画面变化（菜单真实可见）", d_open > 500, f"changed={d_open}px")
    d_closed = diffcount(im_closed, im_closed2)
    check("像素：收起后与初始一致", d_closed < 200, f"changed={d_closed}px")

    im_closed.save(OUT + r"\fix_menu_closed.png")
    im_open.save(OUT + r"\fix_menu_open.png")

    # ---- 4) 3D 视图截图存档 ----
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.3)
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
    open(OUT + r"\fix_viewer.png", "wb").write(base64.b64decode(r["result"]["data"]))

    print("\n==== RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}", "====")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
