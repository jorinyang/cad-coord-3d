# -*- coding: utf-8 -*-
"""C3 端到端：上传→详情页 3D→列表→重命名→删除 全流程（headless Chrome 9225）。

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
NEW_NAME = "E2E \\u6d4b\\u8bd5\\u56fe\\u7eb8"  # JS 字符串字面量（unicode 转义）

HOOK = ("window.__errs=[];"
        "window.addEventListener('error',function(e){window.__errs.push(String(e.message||e))});"
        "window.addEventListener('unhandledrejection',function(e){window.__errs.push('rej:'+String(e.reason))});")


def wait_for(c, expr, sid, timeout=90, interval=1.0):
    end = time.time() + timeout
    while time.time() < end:
        if c.js(expr, sid):
            return True
        time.sleep(interval)
    return False


def upload(c, sid, path):
    doc = c.cmd("DOM.getDocument", {}, session_id=sid)
    q = c.cmd("DOM.querySelector", {"nodeId": doc["result"]["root"]["nodeId"], "selector": "#file-input"}, session_id=sid)
    return c.cmd("DOM.setFileInputFiles", {"files": [path], "nodeId": q["result"]["nodeId"]}, session_id=sid)


def click_ok(c, sid):
    c.js("Array.from(document.querySelectorAll('.dialog-actions .btn'))"
         ".find(b=>b.getAttribute('data-a')==='ok').click()", sid)


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("")
    c.cmd("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK}, session_id=sid)
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)
    c.goto(FRONT, sid)
    for _ in range(40):
        if c.js("document.readyState", sid) == "complete":
            break
        time.sleep(0.3)
    time.sleep(0.8)

    # 1) 上传 → 自动跳转详情页
    c.js("location.hash = '#/upload'", sid); time.sleep(0.5)
    upload(c, sid, TESTFILE)
    ok = wait_for(c, "location.hash.startsWith('#/detail/')", sid, 90)
    print("1) navigated to detail:", ok, "|", c.js("location.hash", sid))
    assert ok, "no navigation to detail"

    # 2) 详情页 3D 就绪
    ok = wait_for(c, "(function(){return !!document.querySelector('#viewer-host canvas')})()", sid, 60)
    print("2) detail viewer ready:", ok); assert ok

    title = c.js("document.getElementById('d-title').textContent", sid)
    meta = c.js("document.querySelector('#detail-body .muted.small').textContent", sid)
    print("3) title:", title, "| meta:", (meta or "").strip())
    assert "test_input" in (title or "")

    # 4) 详情页点选（CDP 真实鼠标注入）
    c.js("document.getElementById('viewer-host').scrollIntoView({block:'center'})", sid)
    time.sleep(0.5)
    rect = json.loads(c.js(
        "JSON.stringify((function(){var r=document.querySelector('#viewer-host canvas').getBoundingClientRect();"
        "return {l:r.left,t:r.top,w:r.width,h:r.height}})())", sid))
    target = None
    for i in range(6):
        p = json.loads(c.js(f"JSON.stringify(window.__cadViewer.projectToScreen({i}))", sid))
        if rect["l"] <= p["x"] <= rect["l"] + rect["w"] and rect["t"] <= p["y"] <= rect["t"] + rect["h"]:
            target = p
            break
    assert target, "no visible point to click"
    c.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": target["x"], "y": target["y"],
                                       "button": "left", "clickCount": 1, "buttons": 1}, session_id=sid)
    c.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": target["x"], "y": target["y"],
                                       "button": "left", "clickCount": 1, "buttons": 0}, session_id=sid)
    time.sleep(0.5)
    picked = json.loads(c.js(
        "(function(){var el=document.getElementById('pick-info');return JSON.stringify({hidden:el.hidden,"
        "name:(document.getElementById('pi-name')||{}).textContent})})()", sid))
    print("4) pick on detail page:", picked)
    assert not picked["hidden"] and picked["name"], "pick failed"

    # 5) 返回列表 → 卡片存在
    c.js("location.hash = '#/'", sid)
    ok = wait_for(c, "!!document.querySelector('.drawing-card')", sid, 30)
    n = c.js("document.querySelectorAll('.drawing-card').length", sid)
    name0 = c.js("document.querySelector('.drawing-card .dc-name').textContent", sid)
    print(f"5) library: {n} card(s), first name:", name0)
    assert ok and n >= 1

    # 6) 进详情 → 重命名
    c.js("document.querySelector('.drawing-card').click()", sid)
    assert wait_for(c, "!!document.getElementById('btn-rename')", sid, 30), "detail re-open failed"
    time.sleep(0.5)
    c.js("document.getElementById('btn-rename').click()", sid)
    time.sleep(0.5)
    c.js(f"document.querySelector('.dialog-input').value = '{NEW_NAME}'", sid)
    click_ok(c, sid)
    ok = wait_for(c, "document.getElementById('d-title').textContent.indexOf('E2E') === 0", sid, 30)
    print("6) renamed to:", c.js("document.getElementById('d-title').textContent", sid))
    assert ok, "rename failed"

    # 7) 回列表验证名称更新
    c.js("location.hash = '#/'", sid)
    ok = wait_for(c, "!!document.querySelector('.drawing-card')", sid, 30)
    n2 = c.js("document.querySelector('.drawing-card .dc-name').textContent", sid)
    print("7) list name after rename:", n2)
    assert ok and "E2E" in (n2 or ""), "rename not persisted in list"

    # 8) 删除：进详情 → 删除 → 确认 → 空列表
    c.js("document.querySelector('.drawing-card').click()", sid)
    assert wait_for(c, "!!document.getElementById('btn-delete')", sid, 30), "detail re-open failed (2)"
    time.sleep(0.5)
    c.js("document.getElementById('btn-delete').click()", sid)
    time.sleep(0.5)
    click_ok(c, sid)
    ok = wait_for(c, "(function(){return location.hash === '#/' && !!document.querySelector('.empty-state')})()", sid, 40)
    print("8) deleted, library empty:", ok)
    assert ok, "delete flow failed"

    # 9) 页面错误
    errs = c.js("JSON.stringify(window.__errs||[])", sid)
    print("9) page errors:", errs)
    print("C3 E2E: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
