# -*- coding: utf-8 -*-
"""演示图纸（空间网架 64 节点）验证：3D 渲染 + 点选 + 截图。

前置：headless 9225；local 模式需 8789 前端在跑。
用法：python app/devtools/verify_demo_frame.py local|online
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
DID = "70120562-9800-4bf5-8e76-16adec50e482"
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
    time.sleep(2.0)
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.4)

    # 1) 场景数据构成
    pc = c.js("window.__cadViewer.pointCount", sid)
    check("点数 = 64", pc == 64, f"pointCount={pc}")
    lv = c.js("window.__cadViewer.objects.linesObj.geometry.attributes.position.count", sid)
    check("线数 = 171", lv == 342, f"line vertices={lv}")
    pv = c.js("window.__cadViewer.objects.pointsObj.geometry.attributes.position.count", sid)
    check("点云顶点 = 64", pv == 64, f"point vertices={pv}")

    # 2) 程序化选中 → 名称格式
    c.js("window.__cadViewer.fitView()", sid)
    time.sleep(0.6)
    c.js("window.__cadViewer.select(0)", sid)
    time.sleep(0.5)
    idx = c.js("window.__cadViewer.selectedIndex", sid)
    check("select(0) 生效", idx == 0, f"selectedIndex={idx}")
    info = str(c.js("document.querySelector('.pick-info')?.innerText?.replace(/\\n/g, ' | ') || '(none)'", sid))
    print("   pick-info:", info)
    check("选中名称格式 P###", bool(re.search(r"P\d{3}", info)), info)

    # 3) 真实鼠标点选（取第 10 个点的屏幕投影坐标）
    xy = json.loads(c.js("JSON.stringify(window.__cadViewer.projectToScreen(10))", sid))
    if xy.get("x") and xy.get("y"):
        c.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": xy["x"], "y": xy["y"]}, session_id=sid)
        time.sleep(0.15)
        c.cmd("Input.dispatchMouseEvent",
              {"type": "mousePressed", "x": xy["x"], "y": xy["y"], "button": "left", "clickCount": 1}, session_id=sid)
        c.cmd("Input.dispatchMouseEvent",
              {"type": "mouseReleased", "x": xy["x"], "y": xy["y"], "button": "left", "clickCount": 1}, session_id=sid)
        time.sleep(0.5)
        idx2 = c.js("window.__cadViewer.selectedIndex", sid)
        info2 = str(c.js("document.querySelector('.pick-info')?.innerText?.replace(/\\n/g, ' | ') || '(none)'", sid))
        check("真实鼠标点击选中", idx2 not in (-1, None), f"selectedIndex={idx2} | {info2}")
    else:
        check("真实鼠标点击选中", False, f"projectToScreen 返回异常: {xy}")

    # 4) 截图 + 像素统计
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
    path = f"{OUT}\\demo_{TARGET}_viewer.png"
    img.save(path)
    print(f"   saved {path}")

    a = np.asarray(img).astype(int)
    blue = (a[..., 2] - a[..., 0] > 30) & (a[..., 2] - a[..., 1] > 12)
    n_blue = int(blue.sum())
    check("3D 画面含蓝色点像素", n_blue > 100, f"blue_px={n_blue}")
    if n_blue:
        ys, xs = np.where(blue)
        bw, bh = int(xs.max() - xs.min()), int(ys.max() - ys.min())
        check("点分布横纵铺展（立体感）", bw > rect["w"] * 0.3 and bh > rect["h"] * 0.3,
              f"bbox {bw}x{bh} of {rect['w']}x{rect['h']}")

    print("\n==== RESULT:", "ALL PASS ✓" if not fails else f"FAILURES: {fails}", "====")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
