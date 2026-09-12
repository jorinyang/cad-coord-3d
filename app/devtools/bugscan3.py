# -*- coding: utf-8 -*-
"""bug 侦查 3（全新实例）：菜单开/关对照 + 3D 场景构成拆解实验。

前置：新 headless 9225（chrome-cdp-cad3）、前端 8789。
输出：scan3d_base / scan3d_noaxes / scan3d_nolines + menuA / menuB
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


def two_frames(c, sid):
    c.js("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(1))))", sid)
    time.sleep(0.3)


def shot(c, sid, name, clip=None):
    two_frames(c, sid)
    p = {"format": "png"}
    if clip:
        p["clip"] = {**clip}
    r = c.cmd("Page.captureScreenshot", p, session_id=sid)
    open(OUT + "\\" + name, "wb").write(base64.b64decode(r["result"]["data"]))
    print("shot:", name)


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("about:blank")
    if not sid:
        print("cannot attach clean tab"); return 1
    c.cmd("Page.enable", session_id=sid)
    c.cmd("Page.bringToFront", session_id=sid)
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)

    url = FRONT + "?v=" + str(int(time.time())) + "#/detail/" + DID
    c.goto(url, sid)
    ok = False
    for _ in range(90):
        if c.js("!!window.__cadViewer", sid):
            ok = True
            break
        time.sleep(0.5)
    print("viewer ready:", ok)
    time.sleep(2.0)
    print("errs:", c.js("window.__errs || 'n/a'", sid))

    # ---------- 1) 菜单开/关对照 ----------
    c.js("window.scrollTo(0,0)", sid); time.sleep(0.3)
    print("menu state initial:", c.js("document.querySelector('#export-menu').hidden", sid))
    shot(c, sid, "menuA_closed.png")

    # 按钮组布局
    print("buttons:", c.js("""(() => {
      return JSON.stringify(Array.from(document.querySelectorAll('.detail-actions .btn'))
        .map(b => { const r = b.getBoundingClientRect();
          return b.id + ' [' + Math.round(r.x) + ',' + Math.round(r.y) + ' ' +
                 Math.round(r.width) + 'x' + Math.round(r.height) + '] ' + b.textContent.trim(); }));
    })()""", sid))

    c.js("document.querySelector('#btn-export').click()", sid)
    time.sleep(0.8)
    print("menu state after click:", c.js("document.querySelector('#export-menu').hidden", sid))
    shot(c, sid, "menuB_open.png")
    c.js("document.body.click()", sid); time.sleep(0.4)  # 关闭

    # ---------- 2) 3D 场景构成 ----------
    info = c.js("""(() => {
      const v = window.__cadViewer;
      if (!v || !v.scene) return 'no-scene-handle';
      return JSON.stringify(v.scene.children.map(o => ({
        type: o.type, visible: o.visible,
        verts: (o.geometry && o.geometry.attributes && o.geometry.attributes.position)
               ? o.geometry.attributes.position.count : null,
        name: o.name || ''
      })));
    })()""", sid)
    print("\nscene children:", info)

    # viewer 区域 rect（scroll=0 时 = 文档坐标）
    rect = json.loads(c.js("""(() => {
      const r = document.querySelector('.viewer-wrap').getBoundingClientRect();
      return JSON.stringify({x: Math.round(r.x), y: Math.round(r.y),
                             w: Math.round(r.width), h: Math.round(r.height)});
    })()""", sid))
    print("viewer rect:", rect)
    clip = {"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"], "scale": 1}

    shot(c, sid, "scan3d_base.png", clip)

    # 关掉坐标轴
    c.js("window.__cadViewer.objects.axes.visible = false", sid)
    time.sleep(0.3)
    shot(c, sid, "scan3d_noaxes.png", clip)

    # 关掉数据线（轴恢复）
    c.js("window.__cadViewer.objects.axes.visible = true; "
         "window.__cadViewer.objects.linesObj.visible = false", sid)
    time.sleep(0.3)
    shot(c, sid, "scan3d_nolines.png", clip)

    # 恢复全部
    c.js("window.__cadViewer.objects.linesObj.visible = true", sid)
    time.sleep(0.3)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
