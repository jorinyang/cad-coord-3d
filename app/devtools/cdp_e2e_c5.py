# -*- coding: utf-8 -*-
"""C5 端到端：导出（CSV / XLSX / JSON）下载与内容校验。

前置：9225 headless Chrome、后端 8791、前端 8789 在运行。
"""
import glob
import json
import os
import shutil
import sys
import time
import zipfile

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
FRONT = "http://127.0.0.1:8789/"
TESTFILE = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\testdata\test_input.dxf"
DL = r"C:\Users\Aorus\AppData\Local\Temp\cad_downloads"


def wait_for(c, expr, sid, timeout=60, interval=1.0):
    end = time.time() + timeout
    while time.time() < end:
        if c.js(expr, sid):
            return True
        time.sleep(interval)
    return False


def wait_file(pattern, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        files = glob.glob(pattern)
        if files:
            f = files[0]
            s1 = os.path.getsize(f)
            time.sleep(0.4)
            s2 = os.path.getsize(f)
            if s1 == s2 and s1 > 0:
                return f
        time.sleep(0.5)
    return None


def clear_dl():
    shutil.rmtree(DL, ignore_errors=True)
    os.makedirs(DL, exist_ok=True)


def export(c, sid, fmt):
    c.js("document.getElementById('btn-export').click()", sid)
    time.sleep(0.4)
    menu_visible = c.js("!document.getElementById('export-menu').hidden", sid)
    c.js(f"document.querySelector('#export-menu [data-fmt={fmt}]').click()", sid)
    return menu_visible


def main() -> int:
    clear_dl()
    c = CDP(port=PORT)
    t, sid = c.attach_page("")
    c.cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": DL}, session_id=sid)
    c.goto(FRONT, sid)
    for _ in range(40):
        if c.js("document.readyState", sid) == "complete":
            break
        time.sleep(0.3)
    time.sleep(0.8)

    # 上传 → 详情
    c.js("location.hash = '#/upload'", sid); time.sleep(0.5)
    doc = c.cmd("DOM.getDocument", {}, session_id=sid)
    q = c.cmd("DOM.querySelector", {"nodeId": doc["result"]["root"]["nodeId"], "selector": "#file-input"}, session_id=sid)
    c.cmd("DOM.setFileInputFiles", {"files": [TESTFILE], "nodeId": q["result"]["nodeId"]}, session_id=sid)
    assert wait_for(c, "location.hash.startsWith('#/detail/')", sid, 90), "no detail nav"
    assert wait_for(c, "!!document.querySelector('#viewer-host canvas')", sid, 60), "no viewer"
    time.sleep(0.6)

    # 1) CSV
    vis = export(c, sid, "csv")
    f = wait_file(os.path.join(DL, "*.csv"))
    print("1) csv:", f, "| menu was visible:", vis)
    assert f, "csv not downloaded"
    raw = open(f, "rb").read()
    assert raw[:3] == b"\xef\xbb\xbf", "missing UTF-8 BOM"
    text = raw.decode("utf-8-sig")
    lines = [l for l in text.splitlines() if l.strip()]
    print("   header:", lines[0])
    assert "坐标名称" in lines[0] and "产生链接的坐标名称" in lines[0], "header wrong"
    assert len(lines) == 6, f"expect 6 lines (1 header + 5 rows), got {len(lines)}"
    print("   row1:", lines[1][:120])

    # 2) XLSX
    export(c, sid, "xlsx")
    fx = wait_file(os.path.join(DL, "*.xlsx"))
    print("2) xlsx:", fx)
    assert fx, "xlsx not downloaded"
    with zipfile.ZipFile(fx) as z:
        names = z.namelist()
        assert any("xl/workbook.xml" in n for n in names), names[:8]
    print("   xlsx is valid zip:", len(names), "entries")

    # 3) JSON
    export(c, sid, "json")
    fj = wait_file(os.path.join(DL, "*.json"))
    print("3) json:", fj)
    assert fj, "json not downloaded"
    with open(fj, encoding="utf-8") as fh:
        jd = json.load(fh)
    assert len(jd["points"]) == 5 and len(jd["links"]) == 6, (len(jd["points"]), len(jd["links"]))
    print("   json content OK: points=5 links=6")

    # 4) 清理
    res = c.js("(async function(){var id=location.hash.slice('#/detail/'.length);"
               "var r=await fetch('http://127.0.0.1:8791/api/drawings/'+id,{method:'DELETE'});"
               "return JSON.stringify(await r.json())})()", sid)
    print("4) cleanup drawing:", res)
    clear_dl()

    errs = c.js("JSON.stringify(window.__errs||[])", sid)
    print("5) page errors:", errs)
    print("C5 E2E: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
