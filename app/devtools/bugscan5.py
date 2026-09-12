# -*- coding: utf-8 -*-
"""bug 侦查 5：viewer DOM 覆盖层取证（dump 元素树 + 隐藏对照截图）。"""
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
    t, sid = c.attach_page("127.0.0.1:8789")
    if not sid:
        print("no page"); return 1
    c.cmd("Page.bringToFront", session_id=sid)
    time.sleep(0.5)

    if "#/detail/" not in str(c.js("location.hash", sid)):
        c.goto(FRONT + "#/detail/" + DID, sid)
        for _ in range(60):
            if c.js("!!window.__cadViewer", sid):
                break
            time.sleep(0.5)
    time.sleep(1.2)
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.4)

    # 1) viewer-wrap 子元素 dump
    els = c.js("""(() => {
      const wrap = document.querySelector('.viewer-wrap');
      const out = [];
      const walk = (el, depth) => {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        out.push({
          d: depth, tag: el.tagName, cls: String(el.className || '').slice(0, 44),
          display: cs.display, vis: cs.visibility, pos: cs.position,
          x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
          text: (el.childElementCount === 0 ? (el.textContent || '').slice(0, 60) : ''),
          c: cs.color, fs: cs.fontSize
        });
        if (depth < 3) for (const ch of el.children) walk(ch, depth + 1);
      };
      walk(wrap, 0);
      return JSON.stringify(out, null, 1);
    })()""", sid)
    print("== viewer-wrap DOM tree ==")
    print(els)

    # 2) 取 viewer rect（scroll=0）
    rect = json.loads(c.js("""(() => { const r = document.querySelector('.viewer-wrap').getBoundingClientRect();
      return JSON.stringify({x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}); })()""", sid))
    print("viewer rect:", rect)

    # 3) 隐藏 DOM overlay 截图
    c.js("""(() => {
      window.__savedOverlay = [];
      ['.viewer-hint', '#pick-info', '.viewer-tooltip'].forEach(sel => {
        const el = document.querySelector(sel);
        if (el) { window.__savedOverlay.push([sel, el.style.display]); el.style.display = 'none'; }
      });
      return window.__savedOverlay.length;
    })()""", sid)
    time.sleep(0.4)
    shot(c, sid, "scan_domhidden.png",
         clip={"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"], "scale": 1})

    # 4) 恢复
    c.js("""(() => {
      (window.__savedOverlay || []).forEach(([sel, disp]) => {
        const el = document.querySelector(sel);
        if (el) el.style.display = disp || '';
      });
      return 'restored';
    })()""", sid)
    time.sleep(0.3)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
