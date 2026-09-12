# -*- coding: utf-8 -*-
"""C6 端到端：分享（生成链接 → 独立页只读访问 → 撤销 → 链接失效）。

前置：9225 headless Chrome、后端 8791、前端 8789 在运行。
"""
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


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("")
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

    # 1) 点分享 → dialog 出现 → 提取链接
    c.js("document.getElementById('btn-share').click()", sid)
    ok = wait_for(c, "!!document.querySelector('.dialog-overlay .dialog-input')", sid, 30)
    link = c.js("document.querySelector('.dialog-overlay .dialog-input').value", sid)
    print("1) share dialog:", ok, "| link:", link)
    assert ok and link and "#/share/" in link, "share dialog failed"
    token = link.split("#/share/")[1]

    # 2) 新标签页打开分享链接（模拟独立访客）
    r = c.cmd("Target.createTarget", {"url": link})
    tid = r["result"]["targetId"]
    att = c.cmd("Target.attachToTarget", {"targetId": tid, "flatten": True})
    nsid = att["result"]["sessionId"]
    for _ in range(40):
        if c.js("document.readyState", nsid) == "complete":
            break
        time.sleep(0.3)
    time.sleep(1.5)

    badge = c.js("document.querySelector('.share-badge') ? document.querySelector('.share-badge').textContent : null", nsid)
    has_canvas = c.js("!!document.querySelector('#viewer-host canvas')", nsid)
    no_edit = c.js("!document.getElementById('btn-rename') && !document.getElementById('btn-delete') && !document.getElementById('btn-share')", nsid)
    stats = c.js("(document.querySelector('.muted.small')||{}).textContent || ''", nsid)
    print("2) share page:", badge, "| canvas:", has_canvas, "| read-only:", no_edit)
    print("   stats:", stats.strip()[:60])
    assert badge and has_canvas and no_edit, "share page invalid"

    # 3) 主 tab 撤销分享（dialog 中的按钮）
    c.js("Array.from(document.querySelectorAll('.dialog-overlay [data-a]'))"
         ".find(b=>b.getAttribute('data-a')==='revoke').click()", sid)
    ok3 = wait_for(c, "!document.querySelector('.dialog-overlay')", sid, 40)
    print("3) revoked, dialog closed:", ok3)
    assert ok3, "revoke click failed"

    # 4) 分享页刷新 → 链接失效
    c.cmd("Page.reload", {}, session_id=nsid)
    ok4 = wait_for(c, "!!document.querySelector('.empty-state')", nsid, 30)
    print("4) share link invalid now:", ok4)
    assert ok4, "revoked share still accessible"

    # 5) 清理：删除测试图 + 关闭分享 tab
    res = c.js("(async function(){var id=location.hash.slice('#/detail/'.length);"
               "var r=await fetch('http://127.0.0.1:8791/api/drawings/'+id,{method:'DELETE'});"
               "return JSON.stringify(await r.json())})()", sid)
    print("5) cleanup:", res)
    c.cmd("Target.closeTarget", {"targetId": tid})

    errs = c.js("JSON.stringify(window.__errs||[])", sid)
    print("6) main page errors:", errs)
    print("C6 E2E: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
