# -*- coding: utf-8 -*-
"""榫卯格构演示（647节点）验证：数据层度数复核 + 3D 渲染 + 点选 + 截图。

前置：headless 9225；local 模式需 8789 前端在跑。
用法：python app/devtools/verify_mortise_frame.py local|online
"""
import base64
import json
import re
import sys
import time
from collections import Counter
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
DID = "85812cf9-0b35-4d22-b3f1-9d18089e1945"
OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"
EXPECT_POINTS, EXPECT_LINKS, MIN_DEG = 647, 1433, 3

# Supabase 配置从前端 config.js 动态提取（publishable key 设计上公开，避免硬编码）
_cfg = Path(__file__).resolve().parent.parent.joinpath("web", "js", "config.js").read_text(encoding="utf-8")
SB_URL = re.search(r"SUPABASE_URL\s*=\s*'([^']+)'", _cfg).group(1)
SB_KEY = re.search(r"SUPABASE_ANON_KEY\s*=\s*'([^']+)'", _cfg).group(1)

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


def sb_all(table, query):
    import httpx

    out, off = [], 0
    for _ in range(20):
        sep = "&" if "?" in query else "?"
        r = httpx.get(f"{SB_URL}/rest/v1/{table}{query}{sep}limit=1000&offset={off}",
                      headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}, timeout=30)
        r.raise_for_status()
        rows = r.json()
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000
    raise RuntimeError("翻页超限")


def check_data_layer():
    """独立复核：直接从 Supabase 拉取并重算每节点连接数。"""
    print("---- 数据层复核（Supabase 直查） ----")
    pts = sb_all("cad_points", f"?drawing_id=eq.{DID}&select=id,name,x,y,z&order=seq.asc")
    links = sb_all("cad_links", f"?drawing_id=eq.{DID}&select=from_point_id,to_point_id")
    id2name = {p["id"]: p["name"] for p in pts}
    deg = Counter()
    valid = 0
    for l in links:
        a, b = id2name.get(l["from_point_id"]), id2name.get(l["to_point_id"])
        if a and b:
            deg[a] += 1
            deg[b] += 1
            valid += 1
    degs = [deg.get(p["name"], 0) for p in pts]
    dmin, dmax = min(degs), max(degs)
    davg = sum(degs) / len(degs)
    hist = dict(sorted(Counter(degs).items()))

    check(f"入库点数 = {EXPECT_POINTS}", len(pts) == EXPECT_POINTS, f"got={len(pts)}")
    check(f"入库线数 = {EXPECT_LINKS}", len(links) == EXPECT_LINKS, f"got={len(links)}")
    check("全部连线端点有效", valid == len(links), f"{valid}/{len(links)}")
    check(f"最小连接数 >= {MIN_DEG}", dmin >= MIN_DEG, f"deg min/avg/max={dmin}/{davg:.2f}/{dmax}")
    print(f"   度数分布: {hist}")
    check("名称全部为 M#-## 格式",
          all(re.fullmatch(r"M\d-\d{2}", p["name"]) for p in pts))
    zs = {round(p["z"], 1) for p in pts}
    check("三维结构（>=5 个不同 z 层）", len(zs) >= 5, f"z_levels={len(zs)}")
    return pts, links


def main() -> int:
    check_data_layer()
    print("---- 3D 渲染验证 ----")

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

    pc = c.js("window.__cadViewer.pointCount", sid)
    check(f"点数 = {EXPECT_POINTS}", pc == EXPECT_POINTS, f"pointCount={pc}")
    lv = c.js("window.__cadViewer.objects.linesObj.geometry.attributes.position.count", sid)
    check(f"线数 = {EXPECT_LINKS}", lv == EXPECT_LINKS * 2, f"line vertices={lv}")
    pv = c.js("window.__cadViewer.objects.pointsObj.geometry.attributes.position.count", sid)
    check(f"点云顶点 = {EXPECT_POINTS}", pv == EXPECT_POINTS, f"point vertices={pv}")

    # 程序化选中 + 名称格式
    c.js("window.__cadViewer.fitView()", sid)
    time.sleep(0.6)
    c.js("window.__cadViewer.select(0)", sid)
    time.sleep(0.5)
    idx = c.js("window.__cadViewer.selectedIndex", sid)
    check("select(0) 生效", idx == 0, f"selectedIndex={idx}")
    info = str(c.js("document.querySelector('.pick-info')?.innerText?.replace(/\\n/g, ' | ') || '(none)'", sid))
    print("   pick-info:", info)
    check("选中名称格式 M#-##", bool(re.search(r"M\d-\d{2}", info)), info)

    # 真实鼠标点选
    xy = json.loads(c.js("JSON.stringify(window.__cadViewer.projectToScreen(300))", sid))
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

    # 截图 + 像素统计
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
    path = f"{OUT}\\mortise_{TARGET}_viewer.png"
    img.save(path)
    print(f"   saved {path}")

    a = np.asarray(img).astype(int)
    nonbg = int(((a[..., 0] < 240) | (a[..., 1] < 240) | (a[..., 2] < 240)).sum())
    check("画面含图元像素", nonbg > 3000, f"nonbg_px={nonbg}")
    blue = (a[..., 2] - a[..., 0] > 30) & (a[..., 2] - a[..., 1] > 12)
    n_blue = int(blue.sum())
    check("3D 画面含蓝色点像素", n_blue > 800, f"blue_px={n_blue}")
    if n_blue:
        ys, xs = np.where(blue)
        bw, bh = int(xs.max() - xs.min()), int(ys.max() - ys.min())
        check("点分布横纵铺展（立体感）", bw > rect["w"] * 0.3 and bh > rect["h"] * 0.3,
              f"bbox {bw}x{bh} of {rect['w']}x{rect['h']}")

    print("\n==== RESULT:", "ALL PASS ✓" if not fails else f"FAILURES: {fails}", "====")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
