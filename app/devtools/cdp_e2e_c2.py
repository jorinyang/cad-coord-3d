# -*- coding: utf-8 -*-
"""C2 端到端验证：3D 查看器（渲染 / 点选 / 悬浮提示 / 销毁 / 帧率基准）。

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
TESTFILE2 = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\testdata\conv_out\test_input.dwg"

HOOK = ("window.__errs=[];"
        "window.addEventListener('error',function(e){window.__errs.push(String(e.message||e))});"
        "window.addEventListener('unhandledrejection',function(e){window.__errs.push('rej:'+String(e.reason))});")


def wait_for(c, expr, sid, timeout=60, interval=1.0):
    end = time.time() + timeout
    while time.time() < end:
        if c.js(expr, sid):
            return True
        time.sleep(interval)
    return False


def upload_file(c, sid, path):
    doc = c.cmd("DOM.getDocument", {}, session_id=sid)
    q = c.cmd("DOM.querySelector", {"nodeId": doc["result"]["root"]["nodeId"], "selector": "#file-input"}, session_id=sid)
    return c.cmd("DOM.setFileInputFiles", {"files": [path], "nodeId": q["result"]["nodeId"]}, session_id=sid)


def canvas_rect(c, sid):
    return json.loads(c.js(
        "JSON.stringify((function(){var r=document.querySelector('#viewer-host canvas').getBoundingClientRect();"
        "return {l:r.left,t:r.top,w:r.width,h:r.height}})())", sid))


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("")
    c.cmd("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK}, session_id=sid)
    c.goto(FRONT, sid)
    for _ in range(40):
        if c.js("document.readyState", sid) == "complete":
            break
        time.sleep(0.3)
    time.sleep(0.8)

    # ---- 上传 ----
    c.js("location.hash = '#/upload'", sid); time.sleep(0.5)
    upload_file(c, sid, TESTFILE)
    ok = wait_for(c, "(function(){var r=document.getElementById('result-card');return !!(r&&!r.hidden)})()", sid, 90, 1.5)
    assert ok, "result card not visible"

    vok = wait_for(c, "!!window.__cadViewer", sid, 20, 0.5)
    print("1) viewer object:", vok); assert vok

    canvas = c.js("!!document.querySelector('#viewer-host canvas')", sid)
    print("2) canvas in DOM:", canvas); assert canvas

    gl = c.js("(function(){var cv=document.querySelector('#viewer-host canvas');"
              "try{return String(!!(cv.getContext('webgl2')||cv.getContext('webgl')))}catch(e){return 'err:'+e.message}})()", sid)
    print("3) webgl context present:", gl)

    stats = c.js("(function(){var v=window.__cadViewer;return JSON.stringify({pc:v.pointCount,sel:v.selectedIndex})})()", sid)
    print("4) viewer stats:", stats)

    # ---- 点选：投影一个可见点 → 合成点击 → 检查详情面板 ----
    rect = canvas_rect(c, sid)
    target = None
    for i in range(6):
        p = json.loads(c.js(f"JSON.stringify(window.__cadViewer.projectToScreen({i}))", sid))
        if rect["l"] <= p["x"] <= rect["l"] + rect["w"] and rect["t"] <= p["y"] <= rect["t"] + rect["h"]:
            target = (i, p)
            break
    assert target, "no point projected inside canvas"
    i0, p0 = target
    print(f"5) pick target: point#{i0} at ({p0['x']:.0f},{p0['y']:.0f})")
    c.js(
        "(function(){var cv=document.querySelector('#viewer-host canvas');"
        f"cv.dispatchEvent(new PointerEvent('pointerdown',{{clientX:{p0['x']},clientY:{p0['y']},bubbles:true}}));"
        f"cv.dispatchEvent(new PointerEvent('pointerup',{{clientX:{p0['x']},clientY:{p0['y']},bubbles:true}}));"
        "return true})()", sid)
    time.sleep(0.4)
    picked = json.loads(c.js(
        "(function(){var el=document.getElementById('pick-info');var n=document.getElementById('pi-name');"
        "var cd=document.getElementById('pi-coords');"
        "return JSON.stringify({hidden:el.hidden,name:n?n.textContent:null,coords:cd?cd.textContent:null})})()", sid))
    print("6) pick info:", picked)
    assert not picked["hidden"] and picked["name"], f"pick failed: {picked}"

    # ---- 悬浮提示 ----
    p2 = json.loads(c.js("JSON.stringify(window.__cadViewer.projectToScreen(2))", sid))
    time.sleep(0.25)
    c.js(
        "(function(){var cv=document.querySelector('#viewer-host canvas');"
        f"cv.dispatchEvent(new PointerEvent('pointermove',{{clientX:{p2['x']},clientY:{p2['y']},bubbles:true}}));"
        "return true})()", sid)
    time.sleep(0.3)
    tip = json.loads(c.js(
        "(function(){var t=document.querySelector('.viewer-tooltip');"
        "return JSON.stringify({hidden:t.hidden,text:t.textContent})})()", sid))
    print("7) hover tooltip:", tip)
    assert not tip["hidden"] and tip["text"], f"tooltip failed: {tip}"

    # ---- 10k 点帧率基准（headless 软渲染，仅作参考） ----
    bench = c.js(
        "(async function(){"
        "var gen=function(n){var pts=[],lnk=[];"
        "for(var i=0;i<n;i++){pts.push({name:'B'+i,x:Math.random()*100,y:Math.random()*100,z:Math.random()*30});"
        "if(i>0)lnk.push({from:'B'+(i-1),to:'B'+i});}"
        "return {meta:{},points:pts,links:lnk}};"
        "var d=document.createElement('div');d.style.cssText='width:900px;height:520px;position:absolute;left:-99999px;top:0;';"
        "document.body.appendChild(d);"
        "var v=window.__createViewer(d,gen(10000));"
        "var frames=0,t0=performance.now();"
        "await new Promise(function(res){function cb(){frames++;if(frames>=90)res();else requestAnimationFrame(cb)}requestAnimationFrame(cb)});"
        "var dt=performance.now()-t0;var fps=Math.round(frames/dt*1000*10)/10;"
        "v.dispose();d.remove();"
        "return JSON.stringify({fps:fps,frames:frames,ms:Math.round(dt)});"
        "})()", sid)
    print("8) 10k points fps (headless):", bench)

    # ---- dispose 生命周期 ----
    d1 = c.js("(function(){try{window.__cadViewer.dispose();return 'ok'}catch(e){return 'err:'+e.message}})()", sid)
    time.sleep(0.3)
    gone = c.js("!!document.querySelector('#viewer-host canvas')", sid)
    print("9) dispose result:", d1, "| canvas still in DOM:", gone)
    assert d1 == "ok" and gone is False, "dispose failed"

    # ---- 第二次上传（DWG 文件：测重传流程 + 旧 viewer 销毁 + DWG 全链） ----
    upload_file(c, sid, TESTFILE2)
    v2 = wait_for(c, "!!window.__cadViewer && !!document.querySelector('#viewer-host canvas') "
                     "&& !document.getElementById('result-card').hidden", sid, 90, 1.5)
    print("10) second upload (dwg) new viewer:", v2)
    assert v2, "second upload flow failed"

    # ---- 页面错误检查 ----
    errs = c.js("JSON.stringify(window.__errs||[])", sid)
    print("11) page runtime errors:", errs)
    print("C2 E2E: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
