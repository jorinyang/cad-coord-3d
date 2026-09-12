# -*- coding: utf-8 -*-
"""bug 侦查 1：详情页取证——导出菜单几何 + 3D 区域特写（headless 9225）。

输出：scan1_detail_full.png / scan2_menu_open.png / scan3_viewer.png
      + 控制台打印网格几何数据
"""
import base64
import json
import sys
import time

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
FRONT = "http://127.0.0.1:8789/"
OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"
DID = "004bb6e6-4464-4a5c-9eb3-71113640d525"


def shot(c, sid, name, clip=None):
    p = {"format": "png"}
    if clip:
        p["clip"] = {**clip, "scale": 1}
    r = c.cmd("Page.captureScreenshot", p, session_id=sid)
    data = base64.b64decode(r["result"]["data"])
    path = OUT + "\\" + name
    open(path, "wb").write(data)
    print("shot:", name, len(data), "bytes")


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("127.0.0.1:8789")
    if not sid:
        print("cannot attach"); return 1
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)
    c.goto(FRONT + "#/detail/" + DID, sid)
    for _ in range(80):
        if c.js("!!window.__cadViewer", sid):
            break
        time.sleep(0.5)
    print("viewer ready:", c.js("!!window.__cadViewer", sid))
    time.sleep(2.0)

    print("page errs:", c.js("window.__errs ? JSON.stringify(window.__errs) : 'no-hook'", sid))

    # 1) 整页截图（滚回顶部）
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.5)
    shot(c, sid, "scan1_detail_full.png")

    mjs = """(() => {
      const btn = document.querySelector('#btn-export');
      const menu = document.querySelector('#export-menu');
      const dd = btn.closest('.dropdown');
      const rB = btn.getBoundingClientRect(), rD = dd.getBoundingClientRect();
      const cB = getComputedStyle(btn);
      const out = {
        btn: {x:rB.x, y:rB.y, w:rB.width, h:rB.height, text: btn.textContent},
        btnStyle: {padding: cB.padding, lineHeight: cB.lineHeight, font: cB.fontSize},
        dd: {x:rD.x, y:rD.y, w:rD.width, h:rD.height},
        menuHidden: menu.hidden
      };
      if (!menu.hidden) {
        const m = menu.getBoundingClientRect(); const cM = getComputedStyle(menu);
        out.menu = {x:m.x, y:m.y, w:m.width, h:m.height, cssRight:cM.right, cssTop:cM.top};
        out.items = Array.from(menu.querySelectorAll('button')).map(b => {
          const r = b.getBoundingClientRect(); const cs = getComputedStyle(b);
          return {text:b.textContent, x:r.x, y:r.y, w:r.width, h:r.height,
                  pad:cs.padding, align:cs.textAlign, font:cs.fontSize};
        });
      }
      return JSON.stringify(out, null, 1);
    })()"""
    print("== closed ==")
    print(c.js(mjs, sid))

    # 2) 打开菜单
    c.js("document.querySelector('#btn-export').click()", sid)
    time.sleep(0.8)
    shot(c, sid, "scan2_menu_open.png")
    print("== open ==")
    print(c.js(mjs, sid))

    # 3) 3D 区域特写（clip 截图）
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.5)
    r = c.js("""(() => { const r = document.querySelector('.viewer-wrap').getBoundingClientRect();
        return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height}); })()""", sid)
    rect = json.loads(r)
    print("viewer rect:", rect)
    shot(c, sid, "scan3_viewer.png",
         clip={"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
