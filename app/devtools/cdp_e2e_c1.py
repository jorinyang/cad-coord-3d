# -*- coding: utf-8 -*-
"""C1 端到端验证：headless Chrome (CDP 9224) 打开前端 → 上传测试图纸 → 断言解析结果。

前置：9224 headless Chrome、后端 8791、前端 8789 均在运行。
可复用：P2 端到端测试基础。
"""
import sys
import time

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
FRONT = "http://127.0.0.1:8789/"
TESTFILE = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\testdata\test_input.dxf"


def main() -> int:
    c = CDP(port=PORT)
    target, sid = c.attach_page("")
    print("attached:", (target or {}).get("url"))

    c.goto(FRONT, sid)
    for _ in range(40):
        if c.js("document.readyState", sid) == "complete":
            break
        time.sleep(0.3)
    time.sleep(1.0)  # 等 app.js 首屏渲染

    title = c.js("document.title", sid)
    home = c.js("document.body.innerText", sid) or ""
    print("title:", title)
    print("home text:", repr(home[:120]))
    assert "还没有图纸" in home, "FAIL: 首页空态未渲染"

    c.js("location.hash = '#/upload'", sid)
    time.sleep(0.6)
    has_dz = c.js("!!document.getElementById('dropzone')", sid)
    print("dropzone present:", has_dz)
    assert has_dz, "FAIL: 上传页未渲染"

    # 注入测试文件（CDP DOM.setFileInputFiles）
    doc = c.cmd("DOM.getDocument", {}, session_id=sid)
    root_id = doc["result"]["root"]["nodeId"]
    q = c.cmd("DOM.querySelector", {"nodeId": root_id, "selector": "#file-input"}, session_id=sid)
    nid = q["result"]["nodeId"]
    print("file-input nodeId:", nid)
    r = c.cmd("DOM.setFileInputFiles", {"files": [TESTFILE], "nodeId": nid}, session_id=sid)
    print("setFileInputFiles:", "ok" if "error" not in r else r)
    time.sleep(1.0)

    pa_hidden = c.js("document.getElementById('progress-area').hidden", sid)
    if pa_hidden:
        c.js("document.getElementById('file-input').dispatchEvent(new Event('change', {bubbles:true}))", sid)
        print("dispatched change manually")

    deadline = time.time() + 90
    ok = False
    while time.time() < deadline:
        rv = c.js("(function(){var r=document.getElementById('result-card');return !!(r&&!r.hidden)})()", sid)
        err = c.js("(function(){var e=document.getElementById('error-area');return e&&!e.hidden?e.textContent:''})()", sid)
        if err:
            print("ERROR SHOWN:", err)
            break
        if rv:
            ok = True
            break
        time.sleep(1.5)

    print("result visible:", ok)
    if ok:
        card = c.js("document.getElementById('result-card').innerText", sid) or ""
        print("=== RESULT CARD ===")
        print(card[:520])
        stats = c.js("Array.from(document.querySelectorAll('.stat-num')).map(x=>x.textContent).join(' / ')", sid)
        print("stats:", stats)
        assert "5" in (stats or "") and "6" in (stats or ""), f"FAIL: stats wrong: {stats}"
        print("C1 E2E: PASS")
        return 0
    print("C1 E2E: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
