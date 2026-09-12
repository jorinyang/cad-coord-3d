# -*- coding: utf-8 -*-
"""bug 侦查 6：目标区域 (页面坐标) elementsFromPoint + 全元素相交检测。"""
import json
import sys
import time

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("127.0.0.1:8789")
    if not sid:
        print("no page"); return 1
    c.cmd("Page.bringToFront", session_id=sid)
    c.js("window.scrollTo(0,0)", sid)
    time.sleep(0.4)
    print("scrollY:", c.js("window.scrollY", sid))

    r = c.js("""(() => {
      const pts = [[767,247],[760,232],[781,262],[740,230],[795,260],[700,250]];
      return JSON.stringify(pts.map(([x,y]) => ({
        pt: [x,y],
        els: document.elementsFromPoint(x,y).map(e =>
          e.tagName + '|' + String(e.className||'').slice(0,30) + '|' + (e.textContent||'').trim().slice(0,24))
      })), null, 1);
    })()""", sid)
    print("== elementsFromPoint ==")
    print(r)

    r2 = c.js("""(() => {
      const X0=731, Y0=223, X1=803, Y1=271;
      const hits = [];
      document.querySelectorAll('body *').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width && r.height && r.right > X0 && r.left < X1 && r.bottom > Y0 && r.top < Y1) {
          const cs = getComputedStyle(el);
          hits.push({tag: el.tagName, cls: String(el.className||'').slice(0,36),
            x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
            disp: cs.display, z: cs.zIndex, txt: (el.textContent||'').trim().slice(0,30)});
        }
      });
      return JSON.stringify(hits, null, 1);
    })()""", sid)
    print("== elements intersecting (731,223)-(803,271) ==")
    print(r2)

    # canvas 像素级验证：把 canvas 里该区域渲染的内容导出不了（webgl），
    # 但可确认 canvas 的 boundingrect 与堆叠顺序
    print("== stack at point ==")
    print(c.js("""(() => {
      const el = document.elementFromPoint(767, 247);
      return el ? el.tagName + '|' + String(el.className||'') : 'null';
    })()""", sid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
