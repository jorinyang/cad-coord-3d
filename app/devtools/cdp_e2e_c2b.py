# -*- coding: utf-8 -*-
"""C2 补充验证：旋转 / 缩放交互（CDP Input.dispatchMouseEvent 真实鼠标注入）。

前置：9225 headless Chrome、后端 8791、前端 8789 在运行。
"""
import json
import sys
import time

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
FRONT = "http://127.0.0.1:8789/"
TESTFILE = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\testdata\test_input.dxf"


def wait_for(c, expr, sid, timeout=60, interval=1.0):
    end = time.time() + timeout
    while time.time() < end:
        if c.js(expr, sid):
            return True
        time.sleep(interval)
    return False


def proj(c, sid, i=0):
    return json.loads(c.js(f"JSON.stringify(window.__cadViewer.projectToScreen({i}))", sid))


def drag(c, sid, x1, y1, x2, y2, steps=10):
    c.cmd("Input.dispatchMouseEvent",
          {"type": "mousePressed", "x": x1, "y": y1, "button": "left", "clickCount": 1, "buttons": 1}, session_id=sid)
    for k in range(1, steps + 1):
        c.cmd("Input.dispatchMouseEvent",
              {"type": "mouseMoved", "x": x1 + (x2 - x1) * k / steps, "y": y1 + (y2 - y1) * k / steps,
               "button": "left", "buttons": 1}, session_id=sid)
        time.sleep(0.03)
    c.cmd("Input.dispatchMouseEvent",
          {"type": "mouseReleased", "x": x2, "y": y2, "button": "left", "clickCount": 1, "buttons": 0}, session_id=sid)


def wheel(c, sid, x, y, dy):
    c.cmd("Input.dispatchMouseEvent",
          {"type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": dy}, session_id=sid)


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("")
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)
    c.goto(FRONT, sid)
    for _ in range(40):
        if c.js("document.readyState", sid) == "complete":
            break
        time.sleep(0.3)
    time.sleep(0.8)

    c.js("location.hash = '#/upload'", sid); time.sleep(0.5)
    doc = c.cmd("DOM.getDocument", {}, session_id=sid)
    q = c.cmd("DOM.querySelector", {"nodeId": doc["result"]["root"]["nodeId"], "selector": "#file-input"}, session_id=sid)
    c.cmd("DOM.setFileInputFiles", {"files": [TESTFILE], "nodeId": q["result"]["nodeId"]}, session_id=sid)
    assert wait_for(c, "!!window.__cadViewer", sid, 90, 1.5), "viewer not ready"
    time.sleep(0.6)

    # 画布滚入视口
    c.js("document.getElementById('viewer-host').scrollIntoView({block:'center'})", sid)
    time.sleep(0.6)
    rect = json.loads(c.js(
        "JSON.stringify((function(){var r=document.querySelector('#viewer-host canvas').getBoundingClientRect();"
        "return {l:r.left,t:r.top,w:r.width,h:r.height}})())", sid))
    cx, cy = rect["l"] + rect["w"] / 2, rect["t"] + rect["h"] / 2
    print(f"canvas rect: {rect}, center=({cx:.0f},{cy:.0f})")
    assert rect["t"] >= 0 and rect["t"] + rect["h"] <= 900, "canvas not fully in viewport"

    # ---- 1) 旋转（拖拽）----
    p_before = proj(c, sid, 0)
    drag(c, sid, cx, cy, cx + 170, cy + 60)
    time.sleep(0.9)  # 等阻尼动画
    p_after = proj(c, sid, 0)
    print(f"1) rotate: before={p_before} after={p_after}")
    assert (abs(p_before["x"] - p_after["x"]) + abs(p_before["y"] - p_after["y"])) > 5, "rotate had no effect"

    # ---- 2) 缩放（滚轮）----
    q_before = proj(c, sid, 1)
    wheel(c, sid, cx, cy, -320)
    time.sleep(0.9)
    q_after = proj(c, sid, 1)
    print(f"2) zoom: before={q_before} after={q_after}")
    assert (abs(q_before["x"] - q_after["x"]) + abs(q_before["y"] - q_after["y"])) > 2, "zoom had no effect"

    # ---- 3) 旋转后点选仍准确（回归）----
    p0 = proj(c, sid, 2)
    x, y = p0["x"], p0["y"]
    c.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1, "buttons": 1}, session_id=sid)
    c.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1, "buttons": 0}, session_id=sid)
    time.sleep(0.5)
    picked = json.loads(c.js(
        "(function(){var el=document.getElementById('pick-info');return JSON.stringify({hidden:el.hidden,"
        "name:(document.getElementById('pi-name')||{}).textContent})})()", sid))
    print("3) pick after rotate:", picked)
    assert not picked["hidden"] and picked["name"], "pick after rotate failed"

    print("C2b: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
