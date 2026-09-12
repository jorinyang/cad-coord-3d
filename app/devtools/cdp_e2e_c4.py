# -*- coding: utf-8 -*-
"""C4 端到端：编辑修正（点改名 / 删点 / 删边 / 持久化）。

前置：9225 headless Chrome、后端 8791（v0.3+）、前端 8789 在运行。
"""
import sys
import time

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
FRONT = "http://127.0.0.1:8789/"
TESTFILE = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\testdata\test_input.dxf"


def wait_for(c, expr, sid, timeout=30, interval=1.0):
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


def counts(c, sid):
    """读取统计行的前两个数字（点数-线数），如 '5-6'。"""
    return c.js(
        "(function(){var el=document.getElementById('d-stats');if(!el)return '';"
        "var m=el.textContent.match(/\\d+/g)||[];return m.slice(0,2).join('-')})()", sid)


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("")
    c.goto(FRONT, sid)
    for _ in range(40):
        if c.js("document.readyState", sid) == "complete":
            break
        time.sleep(0.3)
    time.sleep(0.8)

    # 上传 → 详情页
    c.js("location.hash = '#/upload'", sid); time.sleep(0.5)
    upload(c, sid, TESTFILE)
    assert wait_for(c, "location.hash.startsWith('#/detail/')", sid, 90), "no detail nav"
    assert wait_for(c, "!!document.querySelector('#viewer-host canvas')", sid, 60), "no viewer"
    time.sleep(0.6)

    c0 = counts(c, sid)
    print("0) initial:", c0)
    assert c0 == "5-6", c0

    # 1) 点改名：第一行 → ALPHA
    c.js("document.querySelector('#tables-area .cell-name').click()", sid); time.sleep(0.5)
    c.js("document.querySelector('.dialog-input').value = 'ALPHA'", sid)
    click_ok(c, sid)
    ok = wait_for(c, "document.querySelector('#tables-area .cell-name').textContent === 'ALPHA'", sid, 20)
    in_links = c.js("document.getElementById('tables-area').textContent.indexOf('ALPHA') >= 0", sid)
    print("1) rename point -> ALPHA:", ok, "| appears in links table:", in_links)
    assert ok and in_links, "rename did not reflect in tables"

    # 2) 删点（ALPHA 在 (0,0,0)，连 3 条边 → 期望 4 点 3 线）
    c.js("document.querySelector('#tables-area [data-del-pid]').click()", sid); time.sleep(0.5)
    click_ok(c, sid)
    ok = wait_for(c, "(function(){var el=document.getElementById('d-stats');"
                     "var m=el.textContent.match(/\\d+/g)||[];return m.slice(0,2).join('-')==='4-3'})()", sid, 20)
    c1 = counts(c, sid)
    gone = c.js("document.querySelector('#tables-area').textContent.indexOf('ALPHA') === -1", sid)
    print("2) after delete point:", c1, "| ALPHA gone:", gone)
    assert ok and gone, f"delete point failed: {c1}"

    # 3) 删一条边 → 期望 4 点 2 线
    c.js("document.querySelector('#tables-area [data-del-lid]').click()", sid); time.sleep(0.5)
    click_ok(c, sid)
    ok = wait_for(c, "(function(){var el=document.getElementById('d-stats');"
                     "var m=el.textContent.match(/\\d+/g)||[];return m.slice(0,2).join('-')==='4-2'})()", sid, 20)
    c2 = counts(c, sid)
    print("3) after delete link:", c2)
    assert ok, f"delete link failed: {c2}"

    # 4) 刷新 → 持久化
    c.cmd("Page.reload", {}, session_id=sid)
    assert wait_for(c, "!!document.getElementById('d-stats')", sid, 30), "reload failed"
    time.sleep(0.8)
    c3 = counts(c, sid)
    print("4) after reload:", c3)
    assert c3 == "4-2", f"persistence failed: {c3}"

    # 5) 清理：删除测试图
    res = c.js("(async function(){var id=location.hash.slice('#/detail/'.length);"
               "var r=await fetch('http://127.0.0.1:8791/api/drawings/'+id,{method:'DELETE'});"
               "return JSON.stringify(await r.json())})()", sid)
    print("5) cleanup:", res)

    # 6) 页面错误
    errs = c.js("JSON.stringify(window.__errs||[])", sid)
    print("6) page errors:", errs)
    print("C4 E2E: DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
